"""GPIO abstraction for the Raspberry Pi 5 (RP1) using lgpio.

``lgpio`` is imported lazily so the rest of the package (and the test-suite)
can be imported on machines without a GPIO header.
"""

from __future__ import annotations

import logging
import threading
import time

from .config import PinMap

log = logging.getLogger(__name__)

SPEED_OF_SOUND_CM_S = 34300.0  # dry air at ~20 °C
TRIGGER_PULSE_S = 10e-6        # HC-SR04 requires a >= 10 µs trigger pulse
ECHO_TIMEOUT_S = 0.04          # > 38 ms "no obstacle" pulse of the HC-SR04


def echo_to_distance_cm(echo_seconds: float, speed_cm_s: float = SPEED_OF_SOUND_CM_S) -> float:
    """Convert a round-trip echo duration into a one-way distance in centimetres."""
    if echo_seconds < 0:
        raise ValueError("echo duration cannot be negative")
    return echo_seconds * speed_cm_s / 2.0


class GpioController:
    """Owns the gpiochip handle and every claimed line.

    Access is serialised with a lock because the vision loop (LEDs) and the
    door-alarm loop (buzzer, ultrasonic) run on different threads.
    """

    def __init__(self, chip: int, pins: PinMap) -> None:
        import lgpio  # noqa: PLC0415 - hardware-only dependency

        self._lg = lgpio
        self._pins = pins
        self._lock = threading.RLock()
        self._handle = lgpio.gpiochip_open(chip)

        for line in (pins.green_led, pins.red_led, pins.buzzer, pins.trig):
            lgpio.gpio_claim_output(self._handle, line, 0)
        lgpio.gpio_claim_input(self._handle, pins.echo)

        # Fail-closed default: red LED on, buzzer off.
        self.set_access_leds(granted=False)
        self.set_buzzer(False)
        log.info("GPIO ready on gpiochip%d (%s)", chip, pins)

    def _write(self, line: int, level: bool) -> None:
        with self._lock:
            self._lg.gpio_write(self._handle, line, 1 if level else 0)

    def set_access_leds(self, granted: bool) -> None:
        with self._lock:
            self._write(self._pins.green_led, granted)
            self._write(self._pins.red_led, not granted)

    def set_buzzer(self, on: bool) -> None:
        self._write(self._pins.buzzer, on)

    def measure_distance_cm(self, timeout: float = ECHO_TIMEOUT_S) -> float | None:
        """Fire one HC-SR04 ping and return the distance, or None on timeout."""
        lg, h, trig, echo = self._lg, self._handle, self._pins.trig, self._pins.echo
        with self._lock:
            lg.gpio_write(h, trig, 0)
            time.sleep(2e-6)
            lg.gpio_write(h, trig, 1)
            time.sleep(TRIGGER_PULSE_S)
            lg.gpio_write(h, trig, 0)

            deadline = time.perf_counter() + timeout
            pulse_start = time.perf_counter()
            while lg.gpio_read(h, echo) == 0:
                pulse_start = time.perf_counter()
                if pulse_start > deadline:
                    log.warning("Ultrasonic: echo never went high (check wiring / divider)")
                    return None

            deadline = pulse_start + timeout
            pulse_end = pulse_start
            while lg.gpio_read(h, echo) == 1:
                pulse_end = time.perf_counter()
                if pulse_end > deadline:
                    log.warning("Ultrasonic: echo stuck high")
                    return None

        return echo_to_distance_cm(pulse_end - pulse_start)

    def close(self) -> None:
        with self._lock:
            try:
                for line in (self._pins.green_led, self._pins.red_led, self._pins.buzzer):
                    self._lg.gpio_write(self._handle, line, 0)
            finally:
                self._lg.gpiochip_close(self._handle)
        log.info("GPIO released")
