import pytest

from homeauto.actuators.ac_dimmer import firing_delay_us
from homeauto.alerts.email_alert import AlertRateLimiter
from homeauto.display.tm1637_climate import climate_digits
from homeauto.hal.gpio import GPIO, write_active
from homeauto.sensors.ldr import is_dark
from homeauto.sensors.ultrasonic import echo_to_distance_cm, should_alert


def test_echo_to_distance():
    # 500 us round trip at 343 m/s -> 8.575 cm one way
    assert echo_to_distance_cm(500e-6) == pytest.approx(8.575)


@pytest.mark.parametrize(("distance", "expected"), [(5.0, True), (10.0, False), (50.0, False), (None, False)])
def test_proximity_alert(distance, expected):
    assert should_alert(distance, threshold_cm=10.0) is expected


def test_climate_digits():
    assert climate_digits(27.6, 64.2) == [2, 7, 6, 4]
    assert climate_digits(4, 5) == [0, 4, 0, 5]
    assert climate_digits(150, -3) == [9, 9, 0, 0]  # clamped
    assert climate_digits(None, 50) == [0, 0, 0, 0]


def test_dimmer_delay_50hz():
    assert firing_delay_us(100, 50) == 0
    assert firing_delay_us(50, 50) == 5000
    assert firing_delay_us(1, 50) == 9800  # capped by safety margin
    assert firing_delay_us(0, 50) is None  # never fire


def test_dimmer_rejects_out_of_range():
    with pytest.raises(ValueError):
        firing_delay_us(101)


def test_ldr_dark_is_high():
    assert is_dark(GPIO.HIGH) and not is_dark(GPIO.LOW)


@pytest.mark.parametrize(
    ("on", "active_low", "level"),
    [(True, True, 0), (False, True, 1), (True, False, 1), (False, False, 0)],
)
def test_write_active_polarity(on, active_low, level):
    GPIO.setup(99, GPIO.OUT)
    write_active(99, on, active_low)
    assert GPIO.input(99) == level


def test_alert_rate_limiter():
    limiter = AlertRateLimiter(cooldown_seconds=60)
    assert limiter.allow("motion", now=0)
    assert not limiter.allow("motion", now=30)
    assert limiter.allow("temperature", now=30)
    assert limiter.allow("motion", now=61)
