import smtplib
from unittest import mock

from smart_door.config import SmtpSettings
from smart_door.notifier import EmailNotifier

SETTINGS = SmtpSettings(user="pi@example.com", password="secret",
                        recipient="owner@example.com")


def test_disabled_notifier_does_not_connect():
    with mock.patch("smtplib.SMTP_SSL") as smtp:
        assert EmailNotifier(SmtpSettings()).send("s", "b") is False
        smtp.assert_not_called()


def test_message_headers_and_image_attachment(tmp_path):
    img = tmp_path / "intruder.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    msg = EmailNotifier(SETTINGS).build_message("Alert", "Body", [img, tmp_path / "missing.jpg"])

    assert msg["From"] == "pi@example.com"
    assert msg["To"] == "owner@example.com"
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_content_type() == "image/jpeg"
    assert attachments[0].get_filename() == "intruder.jpg"


def test_send_logs_in_and_sends():
    with mock.patch("smtplib.SMTP_SSL") as smtp:
        server = smtp.return_value.__enter__.return_value
        assert EmailNotifier(SETTINGS).send("Alert", "Body") is True
        server.login.assert_called_once_with("pi@example.com", "secret")
        server.send_message.assert_called_once()


def test_send_failure_is_reported_not_raised():
    with mock.patch("smtplib.SMTP_SSL", side_effect=smtplib.SMTPAuthenticationError(535, b"bad")):
        assert EmailNotifier(SETTINGS).send("Alert", "Body") is False
