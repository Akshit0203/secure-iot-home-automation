"""PWM LED brightness control ("breathing" effect).

Drives the LED on BCM 18 (physical pin 12) with a 1 kHz PWM carrier and sweeps
the duty cycle 0 -> 100 -> 0 %. Perceived brightness is proportional to the
average voltage V_avg = V_cc * duty / 100.

Run:  python -m homeauto.actuators.pwm_led
"""

from __future__ import annotations

import logging
import time

from ..config import PINS
from ..hal.gpio import GPIO

log = logging.getLogger(__name__)

PWM_FREQUENCY_HZ = 1000
STEP_DELAY_S = 0.01
HOLD_S = 0.5


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PINS.led, GPIO.OUT)
    pwm = GPIO.PWM(PINS.led, PWM_FREQUENCY_HZ)
    pwm.start(0)
    log.info("PWM LED on BCM %d @ %d Hz - Ctrl+C to exit", PINS.led, PWM_FREQUENCY_HZ)
    try:
        while True:
            for ramp in (range(0, 101), range(100, -1, -1)):
                for duty in ramp:
                    pwm.ChangeDutyCycle(duty)
                    time.sleep(STEP_DELAY_S)
                time.sleep(HOLD_S)
    except KeyboardInterrupt:
        log.info("Stopped by user")
    finally:
        pwm.stop()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
