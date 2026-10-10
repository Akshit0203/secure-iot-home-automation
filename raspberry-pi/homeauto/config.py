"""Centralised configuration.

Every pin, threshold and secret is read from environment variables (optionally
loaded from a `.env` file) so that no credential is ever hard-coded in source.
Defaults form a single, conflict-free BCM pin map for running all modules on
one Raspberry Pi at the same time. See docs/hardware.md for the wiring table.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv is optional: plain environment variables also work
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # pragma: no cover
    pass


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Pins:
    """BCM GPIO numbers."""

    led: int = _int("PIN_LED", 18)  # hardware-PWM capable (physical pin 12)
    pir: int = _int("PIN_PIR", 17)
    dht11: int = _int("PIN_DHT11", 4)
    ultrasonic_trigger: int = _int("PIN_US_TRIGGER", 5)
    ultrasonic_echo: int = _int("PIN_US_ECHO", 6)  # 5V echo -> use a voltage divider!
    buzzer: int = _int("PIN_BUZZER", 23)
    ldr: int = _int("PIN_LDR", 26)
    relay: int = _int("PIN_RELAY", 19)
    tm1637_clk: int = _int("PIN_TM1637_CLK", 21)
    tm1637_dio: int = _int("PIN_TM1637_DIO", 20)
    dimmer_zero_cross: int = _int("PIN_DIMMER_ZC", 27)
    dimmer_gate: int = _int("PIN_DIMMER_GATE", 22)


@dataclass(frozen=True)
class Settings:
    # Actuator polarity (most low-cost relay modules are active-LOW)
    relay_active_low: bool = _bool("RELAY_ACTIVE_LOW", True)
    buzzer_active_low: bool = _bool("BUZZER_ACTIVE_LOW", False)

    # Thresholds / timing
    proximity_threshold_cm: float = _float("PROXIMITY_THRESHOLD_CM", 10.0)
    mains_frequency_hz: int = _int("MAINS_FREQUENCY_HZ", 50)  # India / EU = 50 Hz
    sensor_poll_seconds: float = _float("SENSOR_POLL_SECONDS", 5.0)

    # Persistence
    db_path: str = os.getenv("HOMEAUTO_DB_PATH", "sensor_data.db")

    # Web API
    api_token: str = os.getenv("HOMEAUTO_API_TOKEN", "")
    web_host: str = os.getenv("HOMEAUTO_WEB_HOST", "127.0.0.1")
    web_port: int = _int("HOMEAUTO_WEB_PORT", 5000)

    # E-mail alerts (Gmail: use an App Password, never the account password)
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = _int("SMTP_PORT", 465)
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_app_password: str = os.getenv("SMTP_APP_PASSWORD", "")
    alert_recipient: str = os.getenv("ALERT_RECIPIENT", "")
    alert_cooldown_seconds: float = _float("ALERT_COOLDOWN_SECONDS", 300.0)

    # Weather
    owm_api_key: str = os.getenv("OWM_API_KEY", "")
    default_lat: float = _float("DEFAULT_LAT", 28.61)  # New Delhi fallback
    default_lon: float = _float("DEFAULT_LON", 77.20)


PINS = Pins()
SETTINGS = Settings()
