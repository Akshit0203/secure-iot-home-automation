import pytest

from smart_door.hardware import echo_to_distance_cm
from smart_door.train import iter_dataset_images


@pytest.mark.parametrize("echo_s, expected_cm", [
    (0.0, 0.0),
    (0.000583, 10.0),   # ~10 cm round trip at 343 m/s
    (0.0233236, 400.0), # HC-SR04 max rated range
])
def test_echo_to_distance(echo_s, expected_cm):
    assert echo_to_distance_cm(echo_s) == pytest.approx(expected_cm, rel=1e-3)


def test_negative_echo_rejected():
    with pytest.raises(ValueError):
        echo_to_distance_cm(-1e-3)


def test_iter_dataset_images_labels_by_folder(tmp_path):
    for rel in ["Akshit/a.jpg", "Akshit/b.PNG", "Akshit/notes.txt", "Guest/x.jpeg"]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    (tmp_path / "stray.jpg").write_bytes(b"")  # not inside a person folder

    found = [(label, p.name) for label, p in iter_dataset_images(tmp_path)]
    assert found == [("Akshit", "a.jpg"), ("Akshit", "b.PNG"), ("Guest", "x.jpeg")]
