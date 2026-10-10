"""HC-SR04 ultrasonic distance measurement with proximity buzzer alert.

A 10 us pulse on TRIG makes the sensor emit an 8-cycle 40 kHz burst; ECHO stays
HIGH for the round-trip time of flight. distance = t * v_sound / 2.

The ECHO pin outputs 5 V - always use a voltage divider (e.g. 1k/2k) before the
3.3 V Raspberry Pi GPIO.

Run:  python -m homeauto.sensors.ultrasonic
"""

from __future__ import annotations

import logging
import statistics
import time

from ..config import PINS, SETTINGS
from ..hal.gpio import GPIO, write_active

log = logging.getLogger(__name__)

SPEED_OF_SOUND_CM_S = 34_300
ECHO_TIMEOUT_S = 0.038  # sensor gives up after 38 ms when nothing is in range (~4 m)


def echo_to_distance_cm(echo_seconds: float) -> float:
    """Convert an echo pulse width to a one-way distance in centimetres."""
    return echo_seconds * SPEED_OF_SOUND_CM_S / 2


def should_alert(distance_cm: float | None, threshold_cm: float) -> bool:
    """Alert when an object is closer than the threshold."""
    return distance_cm is not None and distance_cm < threshold_cm


def setup() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PINS.ultrasonic_trigger, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PINS.ultrasonic_echo, GPIO.IN)
    GPIO.setup(PINS.buzzer, GPIO.OUT)
    write_active(PINS.buzzer, False, SETTINGS.buzzer_active_low)


def _wait_for(level: int, timeout: float) -> float | None:
    deadline = time.perf_counter() + timeout
    while GPIO.input(PINS.ultrasonic_echo) != level:
        if time.perf_counter() > deadline:
            return None
    return time.perf_counter()


def measure_once() -> float | None:
    """Single measurement; returns ``None`` on timeout instead of hanging forever."""
    GPIO.output(PINS.ultrasonic_trigger, GPIO.HIGH)
    time.sleep(10e-6)
    GPIO.output(PINS.ultrasonic_trigger, GPIO.LOW)

    start = _wait_for(GPIO.HIGH, ECHO_TIMEOUT_S)
    if start is None:
        return None
    stop = _wait_for(GPIO.LOW, ECHO_TIMEOUT_S)
    if stop is None:
        return None
    return echo_to_distance_cm(stop - start)


def get_distance(samples: int = 3) -> float | None:
    """Median of several samples - robust against single spurious echoes."""
    readings = []
    for _ in range(samples):
        value = measure_once()
        if value is not None:
            readings.append(value)
        time.sleep(0.06)  # >60 ms between pings avoids echo cross-talk
    return statistics.median(readings) if readings else None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    setup()
    log.info("Ultrasonic sensor ready (threshold %.1f cm)", SETTINGS.proximity_threshold_cm)
    try:
        while True:
            distance = get_distance()
            alert = should_alert(distance, SETTINGS.proximity_threshold_cm)
            write_active(PINS.buzzer, alert, SETTINGS.buzzer_active_low)
            if distance is None:
                log.info("No object in range")
            else:
                log.info("Distance %.2f cm%s", distance, "  <-- PROXIMITY ALERT" if alert else "")
            time.sleep(0.5)
    except KeyboardInterrupt:
        log.info("Stopped by user")
    finally:
        write_active(PINS.buzzer, False, SETTINGS.buzzer_active_low)
        GPIO.cleanup()


if __name__ == "__main__":
    main()
