import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass
class Config:
    source_url: str
    outage_queue: str
    state_file: str
    timezone: ZoneInfo
    chromium_executable: str
    chromium_launch_timeout_ms: int
    calendar_url: str
    calendar_user: str
    calendar_password: str
    calendar_name: str
    event_prefix: str
    log_extracted_events: bool
    notify_email_to: str
    notify_email_from: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_use_tls: bool


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config() -> Config:
    return Config(
        source_url=os.getenv("SOURCE_URL", "https://poweron.loe.lviv.ua/"),
        outage_queue=os.getenv("OUTAGE_QUEUE", "1"),
        state_file=os.getenv("STATE_FILE", "/data/state.txt"),
        timezone=ZoneInfo(os.getenv("TZ", "Europe/Kyiv")),
        chromium_executable=os.getenv(
            "CHROMIUM_EXECUTABLE", "/usr/bin/chromium"
        ).strip(),
        chromium_launch_timeout_ms=int(
            os.getenv("CHROMIUM_LAUNCH_TIMEOUT_MS", "180000")
        ),
        calendar_url=os.getenv("CALDAV_URL", "https://caldav.icloud.com/"),
        calendar_user=os.getenv("CALDAV_USER", ""),
        calendar_password=os.getenv("CALDAV_PASSWORD", ""),
        calendar_name=os.getenv("CALENDAR_NAME", "Power Outage"),
        event_prefix=os.getenv("EVENT_PREFIX", "Power outage"),
        log_extracted_events=_get_bool("LOG_EXTRACTED_EVENTS", False),
        notify_email_to=os.getenv("NOTIFY_EMAIL_TO", "").strip(),
        notify_email_from=os.getenv("NOTIFY_EMAIL_FROM", "").strip(),
        smtp_host=os.getenv("SMTP_HOST", "").strip(),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", "").strip(),
        smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
        smtp_use_tls=_get_bool("SMTP_USE_TLS", True),
    )
