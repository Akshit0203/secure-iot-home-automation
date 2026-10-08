"""Entry point: ``python -m smart_door [--headless] [--env-file PATH]``."""

from __future__ import annotations

import argparse
import dataclasses
import logging
import signal

from .config import Settings, load_dotenv_file


def _sigterm_handler(signum, frame) -> None:
    raise KeyboardInterrupt


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="smart_door", description=__doc__)
    p.add_argument("--env-file", default=None, help="path to .env (default: ./.env)")
    p.add_argument("--headless", action="store_true",
                   help="disable the OpenCV preview window (for systemd / SSH)")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(threadName)s] %(levelname)s %(name)s: %(message)s",
    )
    load_dotenv_file(args.env_file)
    settings = Settings.from_env()
    if args.headless:
        settings = dataclasses.replace(settings, headless=True)

    # Translate SIGTERM (systemctl stop) into the same clean shutdown path as Ctrl+C.
    signal.signal(signal.SIGTERM, _sigterm_handler)

    from .app import SmartDoorSystem  # heavy imports (cv2, dlib) only when running

    SmartDoorSystem(settings).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
