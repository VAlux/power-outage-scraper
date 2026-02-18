from datetime import date, datetime, timedelta
from typing import List, Tuple

import caldav
from caldav.lib import error as caldav_error
from icalendar import Calendar, Event


class CalendarSyncError(Exception):
    pass


class CalendarServiceUnavailable(CalendarSyncError):
    pass


class AppleCalendarSync:
    def __init__(
        self, url: str, user: str, password: str, calendar_name: str, event_prefix: str
    ):
        if not user or not password:
            raise CalendarSyncError("CALDAV_USER and CALDAV_PASSWORD are required")
        self.client = caldav.DAVClient(url=url, username=user, password=password)
        self.calendar_name = calendar_name
        self.event_prefix = event_prefix

    def _get_calendar(self):
        try:
            principal = self.client.principal()
            for cal in principal.calendars():
                if cal.name == self.calendar_name:
                    return cal
        except caldav_error.AuthorizationError as exc:
            raise CalendarSyncError("CalDAV authorization failed") from exc
        except Exception as exc:
            message = str(exc)
            if "503" in message or "Service Unavailable" in message:
                raise CalendarServiceUnavailable(
                    f"CalDAV service unavailable while fetching calendar '{self.calendar_name}'"
                ) from exc
            raise CalendarSyncError(f"CalDAV request failed: {message}") from exc
        raise CalendarSyncError(f"Calendar '{self.calendar_name}' not found")

    def _build_event(
        self, day: date, start_dt: datetime, end_dt: datetime, queue: str
    ) -> bytes:
        title = f"{self.event_prefix} (Queue {queue})"
        uid = f"poweroutage-{queue}-{day.isoformat()}-{start_dt.strftime('%H%M')}-{end_dt.strftime('%H%M')}"

        cal = Calendar()
        event = Event()
        event.add("uid", uid)
        event.add("summary", title)
        event.add("dtstart", start_dt)
        event.add("dtend", end_dt)
        event.add("description", f"Scheduled outage for queue {queue}")
        cal.add_component(event)
        return cal.to_ical()

    def replace_day_events(
        self, day: date, queue: str, ranges: List[Tuple[datetime, datetime]]
    ) -> int:
        calendar = self._get_calendar()

        title = f"{self.event_prefix} (Queue {queue})"
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        try:
            existing = calendar.date_search(day_start, day_end)
            for e in existing:
                data = e.data
                if isinstance(data, bytes):
                    haystack = data.decode("utf-8", errors="replace")
                else:
                    haystack = str(data)
                if title in haystack:
                    e.delete()

            created = 0
            for start_dt, end_dt in ranges:
                event_payload = self._build_event(day, start_dt, end_dt, queue)
                calendar.add_event(event_payload)
                created += 1
        except Exception as exc:
            message = str(exc)
            if "503" in message or "Service Unavailable" in message:
                raise CalendarServiceUnavailable(
                    f"CalDAV service unavailable while syncing date {day.isoformat()}"
                ) from exc
            raise CalendarSyncError(
                f"Failed to sync calendar events: {message}"
            ) from exc

        return created
