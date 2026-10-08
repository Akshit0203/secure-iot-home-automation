"""Show DHT11 temperature and humidity on a TM1637 4-digit 7-segment display.

Format ``TT:HH`` - two digits of temperature (degC), colon, two digits of
relative humidity (%). The TM1637 uses a proprietary 2-wire (CLK/DIO) bus that
is I2C-like but not I2C compatible.

Driver: ``tm1637.py`` from https://github.com/timwaizenegger/raspberrypi-examples
(copy it next to this package or onto PYTHONPATH).

Wiring: TM1637 VCC=5V, GND, CLK=BCM21, DIO=BCM20 | DHT11 VCC=3V3, DATA=BCM4.

Run:  python -m homeauto.display.tm1637_climate
"""

from __future__ import annotations

import logging
import time

from ..config import PINS
from ..sensors import dht11

log = logging.getLogger(__name__)


def climate_digits(temperature: float | None, humidity: float | None) -> list[int]:
    """Return the four display digits ``[T, T, H, H]`` (values clamped to 0-99)."""
    if temperature is None or humidity is None:
        return [0, 0, 0, 0]
    t = max(0, min(99, int(temperature)))
    h = max(0, min(99, int(humidity)))
    return [t // 10, t % 10, h // 10, h % 10]


def main() -> None:
    import tm1637  # third-party driver, see module docstring

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    display = tm1637.TM1637(CLK=PINS.tm1637_clk, DIO=PINS.tm1637_dio, brightness=1.0)
    try:
        for i in range(1, 10):  # power-on self test
            display.Show([0, 0, 0, i])
            time.sleep(0.2)
        display.ShowDoublepoint(True)
        while True:
            temperature, humidity = dht11.read()
            if temperature is None:
                log.warning("DHT11 read failed, retrying")
            else:
                log.info("temp=%.1fC humidity=%.1f%%", temperature, humidity)
                display.Show(climate_digits(temperature, humidity))
            time.sleep(2)
    except KeyboardInterrupt:
        log.info("Stopped by user")
    finally:
        display.cleanup()


if __name__ == "__main__":
    main()
