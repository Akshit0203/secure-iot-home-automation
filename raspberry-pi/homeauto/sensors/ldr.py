"""Light-dependent-resistor (LDR) module -> relay-switched light.

The LDR comparator module's digital output (DO) is LOW when ambient light is
above the potentiometer threshold and HIGH in darkness. The light is switched
ON in darkness and OFF in daylight; state changes are logged once (edge
triggered) instead of on every poll.

Run:  python -m homeauto.sensors.ldr
"""

from __future__ import annotations

import logging
import time

from ..config import PINS, SETTINGS
from ..hal.gpio import GPIO, write_active

log = logging.getLogger(__name__)


def is_dark(do_level: int) -> bool:
    return do_level == GPIO.HIGH


def setup() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PINS.ldr, GPIO.IN)
    GPIO.setup(PINS.relay, GPIO.OUT)
    write_active(PINS.relay, False, SETTINGS.relay_active_low)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    setup()
    log.info("LDR monitoring started - Ctrl+C to exit")
    previous = None
    try:
        while True:
            dark = is_dark(GPIO.input(PINS.ldr))
            if dark != previous:
                write_active(PINS.relay, dark, SETTINGS.relay_active_low)
                log.info("%s -> light %s", "Darkness" if dark else "Daylight", "ON" if dark else "OFF")
                previous = dark
            time.sleep(0.5)
    except KeyboardInterrupt:
        log.info("Stopped by user")
    finally:
        write_active(PINS.relay, False, SETTINGS.relay_active_low)
        GPIO.cleanup()


if __name__ == "__main__":
    main()
