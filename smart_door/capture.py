"""Enrolment tool: capture face images for one person into dataset/<name>/.

Usage:
    python -m smart_door.capture --name Akshit
    SPACE = save frame, q = quit

Aim for 15-30 images per person with varied angles, expressions and lighting.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import cv2

from .config import Settings, load_dotenv_file


def capture_photos(name: str, dataset_dir: Path, width: int = 640, height: int = 480) -> int:
    from picamera2 import Picamera2  # noqa: PLC0415 - Raspberry Pi only

    folder = dataset_dir / name
    folder.mkdir(parents=True, exist_ok=True)

    cam = Picamera2()
    cam.configure(cam.create_preview_configuration(
        main={"format": "XRGB8888", "size": (width, height)}))
    cam.start()
    time.sleep(2)  # let auto-exposure / AWB settle

    count = 0
    print(f"Capturing for '{name}'. SPACE = capture, q = quit.")
    try:
        while True:
            frame = cv2.cvtColor(cam.capture_array(), cv2.COLOR_BGRA2BGR)
            cv2.imshow("Capture", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                count += 1
                path = folder / f"{name}_{datetime.now():%Y%m%d_%H%M%S_%f}.jpg"
                cv2.imwrite(str(path), frame)
                print(f"[{count:02d}] saved {path}")
            elif key == ord("q"):
                break
    finally:
        cv2.destroyAllWindows()
        cam.stop()
        cam.close()

    print(f"Done: {count} photo(s) saved for {name} in {folder}")
    return count


def main(argv=None) -> int:
    load_dotenv_file()
    settings = Settings.from_env()
    p = argparse.ArgumentParser(prog="smart_door.capture", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True, help="identity label, e.g. Akshit")
    p.add_argument("--dataset", type=Path, default=settings.dataset_dir)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    args = p.parse_args(argv)
    capture_photos(args.name, args.dataset, args.width, args.height)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
