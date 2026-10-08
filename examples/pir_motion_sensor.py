"""Standalone HC-SR501 PIR motion-sensor diagnostic (Raspberry Pi 5, lgpio).

Usage:
    python examples/pir_motion_sensor.py [--pin 22] [--chip 0]

The HC-SR501 output is a 3.3 V logic signal, so it connects directly to a GPIO
input. The sensor needs ~10-60 s after power-up to calibrate; readings during
this window are unreliable. Only state *changes* are printed.

Note: the original prototype used GPIO17; the default here is GPIO22 so the PIR
can be wired alongside the main system, which uses GPIO17 for the green LED.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime

import lgpio


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pin", type=int, default=22, help="BCM pin of PIR OUT (default 22)")
    p.add_argument("--chip", type=int, default=0, help="gpiochip index (default 0)")
    p.add_argument("--warmup", type=float, default=10.0, help="settle time in seconds")
    args = p.parse_args()

    handle = lgpio.gpiochip_open(args.chip)
    lgpio.gpio_claim_input(handle, args.pin, lgpio.SET_PULL_DOWN)

    print(f"PIR sensor initialising ({args.warmup:.0f}s)...")
    time.sleep(args.warmup)
    print("Motion detection started (Ctrl+C to stop)")

    previous = None
    try:
        while True:
            motion = lgpio.gpio_read(handle, args.pin) == 1
            if motion != previous:
                stamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{stamp}] {'MOTION DETECTED' if motion else 'No motion'}")
                previous = motion
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nMotion detection stopped by user.")
    finally:
        lgpio.gpiochip_close(handle)


if __name__ == "__main__":
    main()
