"""Build the face-encoding database from dataset/<name>/*.jpg.

Usage:
    python -m smart_door.train [--dataset dataset] [--output encodings.pickle]

Each image is passed through the HOG face detector; every detected face is
converted to a 128-D dlib ResNet embedding labelled with its folder name.
Use the same ENCODING_MODEL here and at runtime so embeddings are comparable.
"""

from __future__ import annotations

import argparse
import logging
import pickle
from collections.abc import Iterator
from pathlib import Path

from .config import Settings, load_dotenv_file

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def iter_dataset_images(dataset_dir: Path) -> Iterator[tuple[str, Path]]:
    """Yield (label, image_path) for every image in dataset/<label>/."""
    for person_dir in sorted(p for p in dataset_dir.iterdir() if p.is_dir()):
        for image in sorted(person_dir.rglob("*")):
            if image.is_file() and image.suffix.lower() in IMAGE_EXTENSIONS:
                yield person_dir.name, image


def build_encodings(dataset_dir: Path, encoding_model: str = "large",
                    detection_model: str = "hog") -> dict:
    import cv2  # noqa: PLC0415
    import face_recognition  # noqa: PLC0415

    encodings, names = [], []
    images = list(iter_dataset_images(dataset_dir))
    if not images:
        raise SystemExit(f"No images found under {dataset_dir}/<name>/")

    for i, (name, path) in enumerate(images, 1):
        image = cv2.imread(str(path))
        if image is None:
            log.warning("[%d/%d] unreadable, skipped: %s", i, len(images), path)
            continue
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb, model=detection_model)
        if len(boxes) != 1:
            log.warning("[%d/%d] %d faces found, skipped: %s", i, len(images), len(boxes), path)
            continue
        encodings.extend(face_recognition.face_encodings(rgb, boxes, model=encoding_model))
        names.append(name)
        log.info("[%d/%d] encoded %s", i, len(images), path.name)

    if not encodings:
        raise SystemExit("No usable faces found - re-capture with better lighting / framing")
    return {"encodings": encodings, "names": names}


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_dotenv_file()
    s = Settings.from_env()
    p = argparse.ArgumentParser(prog="smart_door.train", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", type=Path, default=s.dataset_dir)
    p.add_argument("--output", type=Path, default=s.encodings_path)
    args = p.parse_args(argv)

    data = build_encodings(args.dataset, s.encoding_model, s.detection_model)
    with args.output.open("wb") as fh:
        pickle.dump(data, fh)

    per_person = {n: data["names"].count(n) for n in sorted(set(data["names"]))}
    log.info("Saved %d encodings to %s: %s", len(data["names"]), args.output, per_person)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
