"""Runtime configuration loaded from environment variables (and an optional .env file).

Secrets (SMTP credentials) are never hard-coded: they are read from the
environment so that the source tree can be published safely.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


def load_dotenv_file(path: str | os.PathLike[str] | None = None) -> None:
    """Load a .env file into os.environ if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional
        return
    load_dotenv(dotenv_path=path, override=False)


def _get(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key, "").strip()
    return value if value else default


def _get_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = _get(env, key, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got {raw!r}") from exc


def _get_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = _get(env, key, str(default))
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be a number, got {raw!r}") from exc


def _get_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = _get(env, key, "true" if default else "false").lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} must be a boolean, got {raw!r}")


@dataclass(frozen=True)
class PinMap:
    """BCM GPIO numbers for every actuator / sensor line."""

    green_led: int = 17
    red_led: int = 27
    buzzer: int = 18
    trig: int = 23
    echo: int = 24


@dataclass(frozen=True)
class SmtpSettings:
    host: str = "smtp.gmail.com"
    port: int = 465
    user: str = ""
    password: str = ""
    recipient: str = ""
    timeout: float = 15.0

    @property
    def enabled(self) -> bool:
        return bool(self.user and self.password and self.recipient)


@dataclass(frozen=True)
class Settings:
    # Identity / access policy
    authorized_names: frozenset[str] = frozenset({"akshit"})
    auth_grace_seconds: float = 10.0
    alert_cooldown_seconds: float = 30.0

    # Door sensing
    door_open_threshold_cm: float = 5.0
    alarm_poll_interval: float = 1.0

    # Vision pipeline
    camera_width: int = 1920
    camera_height: int = 1080
    frame_scale: int = 4
    match_tolerance: float = 0.6
    encoding_model: str = "large"
    detection_model: str = "hog"

    # Filesystem
    encodings_path: Path = Path("encodings.pickle")
    dataset_dir: Path = Path("dataset")
    capture_dir: Path = Path("captures")

    # Hardware
    gpio_chip: int = 0
    pins: PinMap = field(default_factory=PinMap)

    # Notifications
    smtp: SmtpSettings = field(default_factory=SmtpSettings)

    # Runtime
    headless: bool = False

    def is_authorized(self, name: str) -> bool:
        return name.strip().lower() in self.authorized_names

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        names = frozenset(
            n.strip().lower()
            for n in _get(env, "AUTHORIZED_NAMES", "Akshit").split(",")
            if n.strip()
        )
        if not names:
            raise ValueError("AUTHORIZED_NAMES must contain at least one name")

        encoding_model = _get(env, "ENCODING_MODEL", "large").lower()
        if encoding_model not in {"small", "large"}:
            raise ValueError("ENCODING_MODEL must be 'small' or 'large'")

        detection_model = _get(env, "DETECTION_MODEL", "hog").lower()
        if detection_model not in {"hog", "cnn"}:
            raise ValueError("DETECTION_MODEL must be 'hog' or 'cnn'")

        frame_scale = _get_int(env, "FRAME_SCALE", 4)
        if frame_scale < 1:
            raise ValueError("FRAME_SCALE must be >= 1")

        return cls(
            authorized_names=names,
            auth_grace_seconds=_get_float(env, "AUTH_GRACE_SECONDS", 10.0),
            alert_cooldown_seconds=_get_float(env, "ALERT_COOLDOWN_SECONDS", 30.0),
            door_open_threshold_cm=_get_float(env, "DOOR_OPEN_THRESHOLD_CM", 5.0),
            alarm_poll_interval=_get_float(env, "ALARM_POLL_INTERVAL", 1.0),
            camera_width=_get_int(env, "CAMERA_WIDTH", 1920),
            camera_height=_get_int(env, "CAMERA_HEIGHT", 1080),
            frame_scale=frame_scale,
            match_tolerance=_get_float(env, "MATCH_TOLERANCE", 0.6),
            encoding_model=encoding_model,
            detection_model=detection_model,
            encodings_path=Path(_get(env, "ENCODINGS_PATH", "encodings.pickle")),
            dataset_dir=Path(_get(env, "DATASET_DIR", "dataset")),
            capture_dir=Path(_get(env, "CAPTURE_DIR", "captures")),
            gpio_chip=_get_int(env, "GPIO_CHIP", 0),
            pins=PinMap(
                green_led=_get_int(env, "PIN_GREEN_LED", 17),
                red_led=_get_int(env, "PIN_RED_LED", 27),
                buzzer=_get_int(env, "PIN_BUZZER", 18),
                trig=_get_int(env, "PIN_TRIG", 23),
                echo=_get_int(env, "PIN_ECHO", 24),
            ),
            smtp=SmtpSettings(
                host=_get(env, "SMTP_HOST", "smtp.gmail.com"),
                port=_get_int(env, "SMTP_PORT", 465),
                user=_get(env, "SMTP_USER", ""),
                password=_get(env, "SMTP_APP_PASSWORD", "").replace(" ", ""),
                recipient=_get(env, "ALERT_RECIPIENT", ""),
                timeout=_get_float(env, "SMTP_TIMEOUT", 15.0),
            ),
            headless=_get_bool(env, "HEADLESS", False),
        )
