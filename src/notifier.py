import smtplib
from datetime import date, datetime
from email.message import EmailMessage


class NotificationError(Exception):
    pass


def send_schedule_update_email(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_use_tls: bool,
    to_email: str,
    from_email: str,
    schedule_day: date,
    queue: str,
    updated_at: datetime,
    ranges: list[tuple[datetime, datetime]],
) -> None:
    if not smtp_host:
        raise NotificationError("SMTP_HOST is required when NOTIFY_EMAIL_TO is set")
    if not to_email:
        raise NotificationError("NOTIFY_EMAIL_TO is required for notifications")

    sender = from_email or smtp_user
    if not sender:
        raise NotificationError(
            "NOTIFY_EMAIL_FROM or SMTP_USER is required for notifications"
        )

    range_lines = "\n".join(
        [
            f"- {start.strftime('%Y-%m-%d %H:%M %Z')} -> {end.strftime('%Y-%m-%d %H:%M %Z')}"
            for start, end in ranges
        ]
    )

    subject = f"Power outage schedule updated: {schedule_day.isoformat()} (Queue {queue})"
    body = "\n".join(
        [
            "Detected schedule update.",
            f"Date: {schedule_day.isoformat()}",
            f"Queue: {queue}",
            f"Source updated at: {updated_at.isoformat()}",
            "",
            "Time ranges:",
            range_lines or "- (no ranges)",
        ]
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)

    try:
        if smtp_use_tls:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if smtp_user:
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                if smtp_user:
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)
    except Exception as exc:
        raise NotificationError(f"Failed to send schedule update email: {exc}") from exc
