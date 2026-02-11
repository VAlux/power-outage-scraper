import logging
from datetime import datetime, timedelta

from calendar_sync import AppleCalendarSync, CalendarServiceUnavailable, CalendarSyncError
from config import load_config
from parser import (
    ParseError,
    ScheduleSnapshot,
    fetch_snapshot_rendered,
    pick_queue_ranges,
)
from state import load_state, save_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def _to_datetime_ranges(day, time_ranges, tz):
    out = []
    for start_t, end_t in time_ranges:
        start_dt = datetime.combine(day, start_t, tzinfo=tz)
        end_dt = datetime.combine(day, end_t, tzinfo=tz)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        out.append((start_dt, end_dt))
    return out


def _log_extracted_events(snapshots: list[ScheduleSnapshot]) -> None:
    for snap in sorted(snapshots, key=lambda s: (s.applicable_date, s.updated_at)):
        logging.info(
            "Extracted schedule date=%s updated_at=%s groups=%d",
            snap.applicable_date,
            snap.updated_at,
            len(snap.queue_lines),
        )
        for line in snap.queue_lines:
            ranges = ", ".join([f"{a.strftime('%H:%M')}-{b.strftime('%H:%M')}" for a, b in line.ranges])
            logging.info(
                "Extracted event date=%s queue=%s ranges=%s",
                snap.applicable_date,
                line.queue or "unknown",
                ranges,
            )


def run_once() -> None:
    cfg = load_config()
    state = load_state(cfg.state_file)

    logging.info(
        "Starting scraper queue=%s source=%s calendar=%s",
        cfg.outage_queue,
        cfg.source_url,
        cfg.calendar_name,
    )
    logging.info(f"Current state {state}")

    snapshots = fetch_snapshot_rendered(
        cfg.source_url,
        chromium_executable=cfg.chromium_executable,
        launch_timeout_ms=cfg.chromium_launch_timeout_ms,
    )
    if cfg.log_extracted_events:
        _log_extracted_events(snapshots)
    now = datetime.now(cfg.timezone).date()
    allowed_days = {now, now + timedelta(days=1)}

    day_snapshots = [s for s in snapshots if s.applicable_date in allowed_days]
    if not day_snapshots:
        logging.info("No schedule blocks for today/tomorrow. Skipping.")
        return

    # If multiple blocks exist for same day, use the most recently updated one.
    latest_by_day = {}
    for snap in day_snapshots:
        prev = latest_by_day.get(snap.applicable_date)
        if prev is None or snap.updated_at >= prev.updated_at:
            latest_by_day[snap.applicable_date] = snap

    sync = AppleCalendarSync(
        url=cfg.calendar_url,
        user=cfg.calendar_user,
        password=cfg.calendar_password,
        calendar_name=cfg.calendar_name,
        event_prefix=cfg.event_prefix,
    )

    for day in sorted(latest_by_day.keys()):
        snapshot = latest_by_day[day]
        day_key = day.isoformat()
        prev_fp = state.by_day_fingerprint.get(day_key)
        if prev_fp == snapshot.fingerprint:
            logging.info("No changes for %s. State fingerprint unchanged.", day_key)
            continue

        ranges = pick_queue_ranges(snapshot, cfg.outage_queue)
        dt_ranges = _to_datetime_ranges(day, ranges, cfg.timezone)
        created = sync.replace_day_events(day, cfg.outage_queue, dt_ranges)
        logging.info(
            "Calendar updated for %s, queue %s. Created events: %d",
            day,
            cfg.outage_queue,
            created,
        )
        state.by_day_fingerprint[day_key] = snapshot.fingerprint

    # Keep small state: today and tomorrow only.
    today = now.isoformat()
    tomorrow = (now + timedelta(days=1)).isoformat()
    state.by_day_fingerprint = {
        k: v for k, v in state.by_day_fingerprint.items() if k in {today, tomorrow}
    }
    save_state(cfg.state_file, state)


if __name__ == "__main__":
    try:
        run_once()
    except ParseError as exc:
        logging.error("Parsing failed: %s", exc)
    except CalendarServiceUnavailable as exc:
        logging.warning("Calendar service unavailable: %s. Will retry next cycle.", exc)
    except CalendarSyncError as exc:
        logging.error("Calendar sync error: %s", exc)
    except Exception:
        logging.exception("Unexpected error")
        raise
