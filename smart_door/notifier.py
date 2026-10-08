"""SMTP-over-SSL e-mail alerts with optional image evidence.

Run ``python -m smart_door.notifier`` to send a test message using the
credentials from your environment / .env file.
"""

from __future__ import annotations

import logging
import mimetypes
import smtplib
import ssl
import threading
from collections.abc import Iterable
from email.message import EmailMessage
from pathlib import Path

from .config import SmtpSettings

log = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, settings: SmtpSettings) -> None:
        self._s = settings
        if not settings.enabled:
            log.warning("SMTP not configured - e-mail alerts are disabled")

    @property
    def enabled(self) -> bool:
        return self._s.enabled

    def build_message(
        self, subject: str, body: str, attachments: Iterable[Path] = ()
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._s.user
        msg["To"] = self._s.recipient
        msg.set_content(body)

        for path in attachments:
            path = Path(path)
            if not path.is_file():
                log.warning("Attachment %s missing, skipped", path)
                continue
            ctype, _ = mimetypes.guess_type(path.name)
            maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
            msg.add_attachment(path.read_bytes(), maintype=maintype,
                               subtype=subtype, filename=path.name)
        return msg

    def send(self, subject: str, body: str, attachments: Iterable[Path] = ()) -> bool:
        """Send synchronously. Returns True on success; never raises."""
        if not self.enabled:
            return False
        msg = self.build_message(subject, body, attachments)
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self._s.host, self._s.port,
                                  timeout=self._s.timeout, context=context) as server:
                server.login(self._s.user, self._s.password)
                server.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            log.error("E-mail alert failed: %s", exc)
            return False
        log.info("E-mail alert sent to %s", self._s.recipient)
        return True

    def send_async(self, subject: str, body: str,
                   attachments: Iterable[Path] = ()) -> threading.Thread:
        """Send on a daemon thread so the vision loop is never blocked by SMTP latency."""
        thread = threading.Thread(
            target=self.send, args=(subject, body, list(attachments)),
            name="smtp-alert", daemon=True,
        )
        thread.start()
        return thread


def main() -> int:
    from .config import Settings, load_dotenv_file

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv_file()
    notifier = EmailNotifier(Settings.from_env().smtp)
    if not notifier.enabled:
        log.error("Set SMTP_USER, SMTP_APP_PASSWORD and ALERT_RECIPIENT first")
        return 1
    ok = notifier.send("Test Email from Raspberry Pi",
                       "This is a test email sent from the Smart Door Security System.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
