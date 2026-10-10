"""SMTP e-mail alerts over implicit TLS (SMTPS, port 465).

Credentials come exclusively from the environment (see .env.example). For
Gmail, enable 2-Step Verification and create an *App Password*; never use the
account password. A per-subject cooldown prevents alert storms (e.g. a PIR
sensor re-triggering every second from flooding the inbox).

Run a test mail:  python -m homeauto.alerts.email_alert
"""

from __future__ import annotations

import logging
import smtplib
import ssl
import time
from email.message import EmailMessage

from ..config import SETTINGS

log = logging.getLogger(__name__)


class AlertRateLimiter:
    def __init__(self, cooldown_seconds: float) -> None:
        self.cooldown = cooldown_seconds
        self._last_sent: dict[str, float] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        last = self._last_sent.get(key)
        if last is not None and now - last < self.cooldown:
            return False
        self._last_sent[key] = now
        return True


_limiter = AlertRateLimiter(SETTINGS.alert_cooldown_seconds)


def send_email_alert(subject: str, body: str, *, force: bool = False) -> bool:
    """Send an alert; returns True on success. Never raises on network errors."""
    if not (SETTINGS.smtp_user and SETTINGS.smtp_app_password and SETTINGS.alert_recipient):
        log.error("SMTP_USER / SMTP_APP_PASSWORD / ALERT_RECIPIENT not configured")
        return False
    if not force and not _limiter.allow(subject):
        log.info("Alert %r suppressed (cooldown)", subject)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SETTINGS.smtp_user
    msg["To"] = SETTINGS.alert_recipient
    msg.set_content(body)

    try:
        context = ssl.create_default_context()  # verifies the server certificate
        with smtplib.SMTP_SSL(SETTINGS.smtp_host, SETTINGS.smtp_port, context=context, timeout=15) as server:
            server.login(SETTINGS.smtp_user, SETTINGS.smtp_app_password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Failed to send e-mail alert: %s", exc)
        return False
    log.info("Alert e-mail sent: %s", subject)
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    send_email_alert("Test alert from Raspberry Pi", "This is a test alert from the home automation hub.", force=True)
