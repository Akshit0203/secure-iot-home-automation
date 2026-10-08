"""DHT11 temperature & humidity sensor.

Range 0-50 degC (+/-2 degC) and 20-80 %RH (+/-5 %). The sensor cannot be sampled
faster than 1 Hz, so the polling loop defaults to one reading every 2 s.

Run:  python -m homeauto.sensors.dht11
"""

from __future__ import annotations

import argparse
import logging
import time

from ..config import PINS

log = logging.getLogger(__name__)


def read(pin: int = PINS.dht11, retries: int = 15) -> tuple[float | None, float | None]:
    """Return ``(temperature_c, humidity_pct)``; values are ``None`` on read failure."""
    import Adafruit_DHT  # imported lazily so the package works off-device

    humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, pin, retries=retries)
    if humidity is None or temperature is None:
        return None, None
    return round(float(temperature), 1), round(float(humidity), 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream DHT11 readings")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between samples (>=1)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    sample = 0
    while True:
        sample += 1
        temperature, humidity = read()
        if temperature is None:
            log.warning("sample=%d read failed, retrying", sample)
        else:
            log.info("sample=%d temp=%.1fC humidity=%.1f%%", sample, temperature, humidity)
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
