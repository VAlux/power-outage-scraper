import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import List, Optional

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

TIME_RANGE_RE = re.compile(
    r"(?:з\s*)?(\d{1,2}:\d{2})\s*(?:-|до)\s*(\d{1,2}:\d{2})",
    flags=re.IGNORECASE,
)
QUEUE_LABEL_RE = re.compile(
    r"(?:група|черг[аи]|queue)\s*[:#]?\s*([\d.]+)",
    flags=re.IGNORECASE,
)
SCHEDULE_HEADER_RE = re.compile(
    r"графік\s+погодинних\s+відключень\s+на\s+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
    flags=re.IGNORECASE,
)


@dataclass
class QueueLine:
    raw_line: str
    queue: Optional[str]
    ranges: List[tuple[time, time]]


@dataclass
class ScheduleSnapshot:
    applicable_date: date
    updated_at: datetime
    queue_lines: List[QueueLine]
    fingerprint: str


class ParseError(Exception):
    pass


def _normalize_queue(value: str) -> str:
    return value.strip().strip(".,;: ")


def _parse_time(value: str) -> time:
    if value == "24:00":
        return time(0, 0)
    return datetime.strptime(value, "%H:%M").time()


def _pick_update_datetime(text: str, fallback_date: date) -> datetime:
    datetime_patterns = [
        r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+\d{1,2}:\d{2}\b",
        r"\b\d{1,2}:\d{2}\s+\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b",
    ]

    for pattern in datetime_patterns:
        for match in re.finditer(pattern, text):
            raw = match.group(0)
            try:
                return date_parser.parse(raw, dayfirst=True)
            except Exception:
                continue

    time_match = re.search(r"\b\d{1,2}:\d{2}\b", text)
    if time_match:
        t = _parse_time(time_match.group(0))
        return datetime.combine(fallback_date, t)

    return datetime.combine(fallback_date, time(0, 0))


def _extract_queue_lines(lines: List[str]) -> List[QueueLine]:
    out: List[QueueLine] = []

    for line in lines:
        ranges = [
            (_parse_time(a), _parse_time(b)) for a, b in TIME_RANGE_RE.findall(line)
        ]
        if not ranges:
            continue

        queue_match = QUEUE_LABEL_RE.search(line)
        queue = _normalize_queue(queue_match.group(1)) if queue_match else None
        out.append(QueueLine(raw_line=line, queue=queue, ranges=ranges))

    if not out:
        raise ParseError("No outage time ranges found in schedule block")

    return out


def _fingerprint(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _snapshot_from_block(
    applicable_date: date, block_lines: List[str]
) -> ScheduleSnapshot:
    block_text = "\n".join(block_lines)
    updated_at = _pick_update_datetime(block_text, fallback_date=applicable_date)
    queue_lines = _extract_queue_lines(block_lines)

    fp_source = "\n".join(
        [
            applicable_date.isoformat(),
            updated_at.isoformat(),
            *(line.raw_line for line in queue_lines),
        ]
    )

    return ScheduleSnapshot(
        applicable_date=applicable_date,
        updated_at=updated_at,
        queue_lines=queue_lines,
        fingerprint=_fingerprint(fp_source),
    )


def _extract_schedule_blocks_from_html(html: str) -> List[tuple[date, List[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select(".power-off__text")

    out: List[tuple[date, List[str]]] = []
    for block in blocks:
        lines = [
            line.strip() for line in block.stripped_strings if line and line.strip()
        ]
        if not lines:
            continue

        header_date: Optional[date] = None
        for line in lines:
            m = SCHEDULE_HEADER_RE.search(line)
            if not m:
                continue
            try:
                header_date = date_parser.parse(m.group(1), dayfirst=True).date()
                break
            except Exception:
                continue

        if header_date is None:
            continue

        out.append((header_date, lines))

    if not out:
        raise ParseError("No '.power-off__text' schedule blocks found in rendered HTML")

    return out


def fetch_snapshot_rendered(
    url: str,
    chromium_executable: str = "/usr/bin/chromium",
    launch_timeout_ms: int = 180000,
) -> List[ScheduleSnapshot]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise ParseError("Playwright is required for JS rendering") from exc

    launch_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--no-zygote",
        "--single-process",
    ]

    with sync_playwright() as p:
        try:
            launch_kwargs = {
                "headless": True,
                "args": launch_args,
                "timeout": launch_timeout_ms,
            }
            if chromium_executable:
                launch_kwargs["executable_path"] = chromium_executable
            browser = p.chromium.launch(**launch_kwargs)
        except Exception as first_exc:
            if chromium_executable:
                try:
                    browser = p.chromium.launch(
                        headless=True,
                        args=launch_args,
                        timeout=launch_timeout_ms,
                    )
                except Exception:
                    raise ParseError(
                        f"Chromium launch failed for executable '{chromium_executable}'"
                    ) from first_exc
            else:
                raise

        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        html = page.content()
        browser.close()

    if not html or len(html.strip()) < 50:
        raise ParseError("Rendered page HTML is empty; could not read schedule")

    blocks = _extract_schedule_blocks_from_html(html)
    snapshots = [_snapshot_from_block(day, block_lines) for day, block_lines in blocks]
    if not snapshots:
        raise ParseError("No schedule snapshots parsed from rendered HTML")
    return snapshots


def pick_queue_ranges(
    snapshot: ScheduleSnapshot, queue: str
) -> List[tuple[time, time]]:
    target_queue = _normalize_queue(queue)
    selected: List[QueueLine] = []
    for line in snapshot.queue_lines:
        if line.queue == target_queue:
            selected.append(line)

    if not selected:
        unlabeled = all(line.queue is None for line in snapshot.queue_lines)
        if unlabeled and queue.isdigit():
            idx = int(queue) - 1
            if 0 <= idx < len(snapshot.queue_lines):
                selected = [snapshot.queue_lines[idx]]

    if not selected:
        raise ParseError(f"No ranges found for outage queue '{queue}'")

    merged: List[tuple[time, time]] = []
    for line in selected:
        merged.extend(line.ranges)

    return merged
