"""Hardware abstraction layer for GPIO.

Selects a backend via HOMEAUTO_GPIO_BACKEND:

* ``auto``     (default) - RPi.GPIO on a Pi, otherwise the in-memory mock
* ``rpi``      - real hardware via RPi.GPIO (on Pi 5 install ``rpi-lgpio``)
* ``emulator`` - nosix/raspberry-gpio-emulator Tk GUI (``EmulatorGUI``)
* ``mock``     - headless in-memory mock, used by CI and unit tests

All modules import ``GPIO`` from here, so the same code runs on a Pi, on a
laptop with the emulator, or in GitHub Actions.
"""

from __future__ import annotations

import logging
import os
import threading

log = logging.getLogger(__name__)


class _MockPWM:
    def __init__(self, pin: int, frequency: float) -> None:
        self.pin, self.frequency, self.duty = pin, frequency, 0.0

    def start(self, duty: float) -> None:
        self.duty = duty

    def ChangeDutyCycle(self, duty: float) -> None:  # noqa: N802 - mirrors RPi.GPIO
        self.duty = duty

    def ChangeFrequency(self, frequency: float) -> None:  # noqa: N802
        self.frequency = frequency

    def stop(self) -> None:
        self.duty = 0.0


class MockGPIO:
    """Minimal, thread-safe stand-in implementing the RPi.GPIO API subset we use."""

    BCM, BOARD = 11, 10
    IN, OUT = 1, 0
    LOW, HIGH = 0, 1
    PUD_OFF, PUD_DOWN, PUD_UP = 20, 21, 22
    RISING, FALLING, BOTH = 31, 32, 33

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.state: dict[int, int] = {}
        self.mode: int | None = None

    def setmode(self, mode: int) -> None:
        self.mode = mode

    def setwarnings(self, flag: bool) -> None:
        pass

    def setup(self, pin: int, direction: int, pull_up_down: int = 20, initial: int = 0) -> None:
        with self._lock:
            self.state.setdefault(pin, initial)

    def output(self, pin: int, value: int | bool) -> None:
        with self._lock:
            self.state[pin] = int(bool(value))

    def input(self, pin: int) -> int:
        with self._lock:
            return self.state.get(pin, 0)

    def set_input(self, pin: int, value: int) -> None:
        """Test helper: drive a simulated input pin."""
        self.output(pin, value)

    def PWM(self, pin: int, frequency: float) -> _MockPWM:  # noqa: N802
        return _MockPWM(pin, frequency)

    def add_event_detect(self, pin: int, edge: int, callback=None, bouncetime: int = 0) -> None:
        pass

    def remove_event_detect(self, pin: int) -> None:
        pass

    def cleanup(self, *pins: int) -> None:
        with self._lock:
            self.state.clear()


def _load_backend():
    backend = os.getenv("HOMEAUTO_GPIO_BACKEND", "auto").lower()
    if backend in {"auto", "rpi"}:
        try:
            import RPi.GPIO as rpi_gpio  # type: ignore

            return rpi_gpio, False
        except (ImportError, RuntimeError):
            if backend == "rpi":
                raise
    if backend == "emulator":
        from EmulatorGUI import GPIO as emulator_gpio  # type: ignore

        return emulator_gpio, True
    log.warning("RPi.GPIO unavailable - using in-memory MockGPIO (simulation mode)")
    return MockGPIO(), True


GPIO, IS_SIMULATED = _load_backend()


def write_active(pin: int, on: bool, active_low: bool) -> None:
    """Drive an actuator honouring its polarity (active-HIGH or active-LOW)."""
    GPIO.output(pin, GPIO.LOW if on == active_low else GPIO.HIGH)
