"""Phase-angle AC dimmer (zero-cross detector + opto-isolated TRIAC).

On every zero crossing of the mains waveform the TRIAC gate is fired after a
delay alpha. The later the firing angle, the smaller the conducted part of each
half-cycle and the lower the RMS power delivered to the lamp:

    half_cycle = 1 / (2 * f_mains)           # 10 ms at 50 Hz
    delay      = (1 - level/100) * half_cycle

!! DANGER: this module switches MAINS VOLTAGE. Use an isolated dimmer board
   (e.g. RobotDyn), never touch the high-voltage side while powered, and use
   only dimmable lamps.

Note: Linux user-space timing has jitter in the 100 us range, which causes
visible flicker at intermediate levels. For production use, move the firing
logic to a microcontroller (ESP32 hardware timer) and command it from the Pi.

Run:  python -m homeauto.actuators.ac_dimmer
"""

from __future__ import annotations

import logging
import time

from ..config import PINS, SETTINGS
from ..hal.gpio import GPIO

log = logging.getLogger(__name__)

GATE_PULSE_S = 10e-6
SAFETY_MARGIN_US = 200  # never fire right before the next zero crossing

_level = 100


def firing_delay_us(level: int, mains_hz: int = SETTINGS.mains_frequency_hz) -> int | None:
    """Gate-firing delay after zero cross for a brightness ``level`` (0-100 %).

    Returns ``None`` when the TRIAC should not be fired at all (level 0).
    """
    if not 0 <= level <= 100:
        raise ValueError("level must be between 0 and 100")
    if level == 0:
        return None
    half_cycle_us = 1_000_000 / (2 * mains_hz)
    delay = (1 - level / 100) * half_cycle_us
    return int(min(delay, half_cycle_us - SAFETY_MARGIN_US))


def _on_zero_cross(_channel: int) -> None:
    delay = firing_delay_us(_level)
    if delay is None:
        return
    time.sleep(delay / 1_000_000)
    GPIO.output(PINS.dimmer_gate, GPIO.HIGH)
    time.sleep(GATE_PULSE_S)
    GPIO.output(PINS.dimmer_gate, GPIO.LOW)


def set_level(level: int) -> None:
    global _level
    firing_delay_us(level)  # validates range
    _level = level
    log.info("Brightness set to %d%%", level)


def setup() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PINS.dimmer_gate, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PINS.dimmer_zero_cross, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(PINS.dimmer_zero_cross, GPIO.RISING, callback=_on_zero_cross)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    setup()
    log.info("AC dimmer ready (%d Hz mains). Default brightness 100%%", SETTINGS.mains_frequency_hz)
    try:
        while True:
            raw = input("Brightness 0-100 (or 'exit'): ").strip().lower()
            if raw == "exit":
                break
            try:
                set_level(int(raw))
            except ValueError:
                log.warning("Invalid input %r - enter an integer 0-100", raw)
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.remove_event_detect(PINS.dimmer_zero_cross)
        GPIO.output(PINS.dimmer_gate, GPIO.LOW)
        GPIO.cleanup()
        log.info("GPIO released")


if __name__ == "__main__":
    main()
