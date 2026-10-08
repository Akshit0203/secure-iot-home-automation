from pathlib import Path

import pytest

from smart_door.config import Settings


def test_defaults_match_reference_hardware():
    s = Settings.from_env({})
    assert s.pins.green_led == 17 and s.pins.red_led == 27
    assert s.pins.buzzer == 18 and s.pins.trig == 23 and s.pins.echo == 24
    assert s.auth_grace_seconds == 10 and s.alert_cooldown_seconds == 30
    assert s.frame_scale == 4 and s.encoding_model == "large"
    assert s.is_authorized("Akshit")
    assert not s.smtp.enabled


def test_env_overrides():
    s = Settings.from_env({
        "AUTHORIZED_NAMES": "Alice, BOB ,",
        "PIN_BUZZER": "12",
        "DOOR_OPEN_THRESHOLD_CM": "7.5",
        "ENCODINGS_PATH": "/opt/door/enc.pickle",
        "HEADLESS": "yes",
    })
    assert s.authorized_names == frozenset({"alice", "bob"})
    assert s.is_authorized("alice") and s.is_authorized("Bob")
    assert not s.is_authorized("akshit")
    assert s.pins.buzzer == 12
    assert s.door_open_threshold_cm == 7.5
    assert s.encodings_path == Path("/opt/door/enc.pickle")
    assert s.headless is True


def test_smtp_enabled_and_app_password_spaces_stripped():
    s = Settings.from_env({
        "SMTP_USER": "pi@example.com",
        "SMTP_APP_PASSWORD": "abcd efgh ijkl mnop",
        "ALERT_RECIPIENT": "me@example.com",
    })
    assert s.smtp.enabled
    assert s.smtp.password == "abcdefghijklmnop"


@pytest.mark.parametrize("key, value", [
    ("PIN_TRIG", "twenty"),
    ("ENCODING_MODEL", "huge"),
    ("DETECTION_MODEL", "yolo"),
    ("FRAME_SCALE", "0"),
    ("HEADLESS", "maybe"),
    ("AUTHORIZED_NAMES", " , "),
])
def test_invalid_values_rejected(key, value):
    with pytest.raises(ValueError):
        Settings.from_env({key: value})
