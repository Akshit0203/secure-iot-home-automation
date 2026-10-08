"""Camera capture and face-recognition pipeline.

Pipeline per frame:
    Picamera2 (XRGB8888) -> BGR -> downscale x1/FRAME_SCALE -> RGB
    -> HOG face detector -> dlib ResNet 128-D embeddings
    -> Euclidean distance against enrolled encodings -> identity.
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import cv2
import face_recognition
import numpy as np

from .controller import UNKNOWN

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Detection:
    name: str
    distance: float
    box: tuple[int, int, int, int]  # (top, right, bottom, left) in full-frame pixels


def load_encodings(path: Path) -> tuple[list[np.ndarray], list[str]]:
    """Load and validate the serialized encodings produced by ``smart_door.train``.

    Pickle can execute arbitrary code on load: only load files you generated.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found - enrol faces with `python -m smart_door.capture` "
            "and build it with `python -m smart_door.train`"
        )
    with path.open("rb") as fh:
        data = pickle.load(fh)

    encodings, names = data.get("encodings"), data.get("names")
    if not encodings or names is None or len(encodings) != len(names):
        raise ValueError(f"{path} is empty or malformed")
    log.info("Loaded %d encodings for %d identities", len(names), len(set(names)))
    return list(encodings), list(names)


class Camera:
    """Thin wrapper around Picamera2 returning BGR frames for OpenCV."""

    def __init__(self, width: int, height: int) -> None:
        from picamera2 import Picamera2  # noqa: PLC0415 - Raspberry Pi only

        self._cam = Picamera2()
        self._cam.configure(
            self._cam.create_preview_configuration(
                main={"format": "XRGB8888", "size": (width, height)}
            )
        )
        self._cam.start()
        log.info("Camera started at %dx%d", width, height)

    def read(self) -> np.ndarray:
        # XRGB8888 is laid out as B,G,R,X in memory -> drop the padding byte.
        return cv2.cvtColor(self._cam.capture_array(), cv2.COLOR_BGRA2BGR)

    def close(self) -> None:
        self._cam.stop()
        self._cam.close()


class FaceRecognizer:
    def __init__(
        self,
        known_encodings: list[np.ndarray],
        known_names: list[str],
        tolerance: float = 0.6,
        scale: int = 4,
        encoding_model: str = "large",
        detection_model: str = "hog",
    ) -> None:
        self._known = np.asarray(known_encodings)
        self._names = known_names
        self._tolerance = tolerance
        self._scale = scale
        self._encoding_model = encoding_model
        self._detection_model = detection_model

    def identify(self, frame_bgr: np.ndarray) -> list[Detection]:
        small = cv2.resize(frame_bgr, (0, 0), fx=1 / self._scale, fy=1 / self._scale)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        boxes = face_recognition.face_locations(rgb, model=self._detection_model)
        if not boxes:
            return []
        encodings = face_recognition.face_encodings(rgb, boxes, model=self._encoding_model)

        detections = []
        for box, encoding in zip(boxes, encodings, strict=True):
            distances = face_recognition.face_distance(self._known, encoding)
            best = int(np.argmin(distances))
            best_distance = float(distances[best])
            name = self._names[best] if best_distance <= self._tolerance else UNKNOWN
            full_box = tuple(int(v * self._scale) for v in box)
            detections.append(Detection(name, best_distance, full_box))
        return detections


def annotate(frame_bgr: np.ndarray, detections: list[Detection], is_authorized) -> np.ndarray:
    """Draw labelled bounding boxes: green for authorized, red otherwise."""
    for det in detections:
        top, right, bottom, left = det.box
        color = (0, 200, 0) if is_authorized(det.name) else (0, 0, 255)
        cv2.rectangle(frame_bgr, (left, top), (right, bottom), color, 2)
        label = f"{det.name} ({det.distance:.2f})"
        cv2.putText(frame_bgr, label, (left, max(top - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return frame_bgr
