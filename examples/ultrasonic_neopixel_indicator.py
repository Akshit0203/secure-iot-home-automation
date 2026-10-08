"""Standalone door-proximity indicator: HC-SR04 ultrasonic + WS2812B NeoPixel ring.

Usage:
    python examples/ultrasonic_neopixel_indicator.py

Colour coding:
    < 5 cm     RED     (door closed / object touching sensor)
    5 - 15 cm  AMBER   (door ajar / approaching)
    >= 15 cm   GREEN   (clear)

Requires (Raspberry Pi 5):
    pip install adafruit-circuitpython-neopixel Adafruit-Blinka-Raspberry-Pi5-Neopixel

Stop the main smart-door service first - both claim GPIO23/24.
"""

from __future__ import annotations

import time

import board
import lgpio
import neopixel

TRIG = 23
ECHO = 24
RGB_PIN = board.D21     # WS2812B DIN on GPIO21 (physical pin 40)
NUM_PIXELS = 12
BRIGHTNESS = 0.3
ECHO_TIMEOUT_S = 0.04

RED, AMBER, GREEN, OFF = (255, 0, 0), (255, 150, 0), (0, 255, 0), (0, 0, 0)


def get_distance(chip: int) -> float | None:
    lgpio.gpio_write(chip, TRIG, 1)
    time.sleep(10e-6)
    lgpio.gpio_write(chip, TRIG, 0)

    start = time.perf_counter()
    deadline = start + ECHO_TIMEOUT_S
    while lgpio.gpio_read(chip, ECHO) == 0:
        start = time.perf_counter()
        if start > deadline:
            return None

    stop = start
    deadline = start + ECHO_TIMEOUT_S
    while lgpio.gpio_read(chip, ECHO) == 1:
        stop = time.perf_counter()
        if stop > deadline:
            return None

    return (stop - start) * 34300 / 2


def colour_for(distance_cm: float) -> tuple[int, int, int]:
    if distance_cm < 5:
        return RED
    if distance_cm < 15:
        return AMBER
    return GREEN


def main() -> None:
    pixels = neopixel.NeoPixel(RGB_PIN, NUM_PIXELS, brightness=BRIGHTNESS, auto_write=True)
    chip = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_output(chip, TRIG, 0)
    lgpio.gpio_claim_input(chip, ECHO)

    print("Ultrasonic + NeoPixel indicator running... Ctrl+C to stop.")
    try:
        while True:
            dist = get_distance(chip)
            if dist is None:
                print("No echo (out of range or wiring fault)")
            else:
                print(f"Distance: {dist:6.2f} cm")
                pixels.fill(colour_for(dist))
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        pixels.fill(OFF)
        lgpio.gpiochip_close(chip)


if __name__ == "__main__":
    main()
