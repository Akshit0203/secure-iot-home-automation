"""Orchestrates the vision loop (main thread) and the door-alarm loop (worker thread)."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import cv2

from .config import Settings
from .controller import AccessController
from .hardware import GpioController
from .notifier import EmailNotifier
from .vision import Camera, FaceRecognizer, annotate, load_encodings

log = logging.getLogger(__name__)

WINDOW_NAME = "Smart Door - Face Recognition"


class SmartDoorSystem:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.stop_event = threading.Event()
        self.controller = AccessController(
            is_authorized=settings.is_authorized,
            grace_seconds=settings.auth_grace_seconds,
            cooldown_seconds=settings.alert_cooldown_seconds,
            door_open_threshold_cm=settings.door_open_threshold_cm,
        )
        encodings, names = load_encodings(settings.encodings_path)
        self.recognizer = FaceRecognizer(
            encodings, names,
            tolerance=settings.match_tolerance,
            scale=settings.frame_scale,
            encoding_model=settings.encoding_model,
            detection_model=settings.detection_model,
        )
        self.notifier = EmailNotifier(settings.smtp)
        self.gpio = GpioController(settings.gpio_chip, settings.pins)
        try:
            self.camera = Camera(settings.camera_width, settings.camera_height)
        except Exception:
            self.gpio.close()
            raise
        settings.capture_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ loops
    def _door_alarm_loop(self) -> None:
        while not self.stop_event.is_set():
            now = time.monotonic()
            if self.controller.access_granted(now):
                self.gpio.set_buzzer(False)
            else:
                distance = self.gpio.measure_distance_cm()
                if distance is not None:
                    log.debug("Door distance: %.2f cm", distance)
                alarm = self.controller.should_sound_alarm(distance, time.monotonic())
                self.gpio.set_buzzer(alarm)
                if alarm:
                    log.warning("ALARM: door open (%.1f cm) without authorization", distance)
            self.stop_event.wait(self.s.alarm_poll_interval)

    def _vision_loop(self) -> None:
        while not self.stop_event.is_set():
            frame = self.camera.read()
            detections = self.recognizer.identify(frame)
            decision = self.controller.evaluate_frame(
                (d.name for d in detections), time.monotonic()
            )
            self.gpio.set_access_leds(decision.access_granted)

            if decision.authorized_seen:
                log.info("Access granted: %s", ", ".join(
                    d.name for d in detections if self.s.is_authorized(d.name)))

            annotate(frame, detections, self.s.is_authorized)

            if decision.raise_alert:
                self._raise_intruder_alert(frame, decision.unauthorized_names)

            if not self.s.headless:
                cv2.imshow(WINDOW_NAME, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    log.info("'q' pressed - shutting down")
                    self.stop_event.set()

    def _raise_intruder_alert(self, frame, names: tuple[str, ...]) -> None:
        stamp = datetime.now()
        path = Path(self.s.capture_dir) / (
            f"intruder_{stamp:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.jpg"
        )
        cv2.imwrite(str(path), frame)
        who = ", ".join(sorted(set(names)))
        log.warning("Unauthorized face(s) detected: %s -> %s", who, path)
        self.notifier.send_async(
            subject="\N{POLICE CARS REVOLVING LIGHT} Unauthorized Face Detected",
            body=(
                f"A non-authorized person ({who}) was detected at the door.\n"
                f"Time: {stamp:%Y-%m-%d %H:%M:%S}\n"
                f"Snapshot: {path.name} (attached)"
            ),
            attachments=[path],
        )

    # -------------------------------------------------------------- lifecycle
    def run(self) -> None:
        log.info("Smart Door System running (authorized: %s)",
                 ", ".join(sorted(self.s.authorized_names)))
        alarm_thread = threading.Thread(
            target=self._door_alarm_loop, name="door-alarm", daemon=True
        )
        alarm_thread.start()
        try:
            self._vision_loop()
        except KeyboardInterrupt:
            log.info("Interrupted - shutting down")
        finally:
            self.stop_event.set()
            alarm_thread.join(timeout=5)
            self.shutdown()

    def shutdown(self) -> None:
        try:
            self.camera.close()
        finally:
            self.gpio.close()
            if not self.s.headless:
                cv2.destroyAllWindows()
