import pytest

from smart_door.controller import UNKNOWN, AccessController


@pytest.fixture
def ctrl():
    return AccessController(
        is_authorized=lambda n: n.lower() == "akshit",
        grace_seconds=10,
        cooldown_seconds=30,
        door_open_threshold_cm=5,
    )


def test_no_faces_keeps_access_denied(ctrl):
    d = ctrl.evaluate_frame([], now=100)
    assert not d.authorized_seen
    assert not d.access_granted
    assert not d.raise_alert


def test_authorized_face_opens_grace_window(ctrl):
    d = ctrl.evaluate_frame(["Akshit"], now=100)
    assert d.authorized_seen and d.access_granted and not d.raise_alert
    assert ctrl.access_granted(109.9)
    assert not ctrl.access_granted(110.0)


def test_grace_window_survives_empty_frames(ctrl):
    ctrl.evaluate_frame(["Akshit"], now=100)
    d = ctrl.evaluate_frame([], now=105)
    assert d.access_granted


def test_unknown_face_raises_alert_with_cooldown(ctrl):
    assert ctrl.evaluate_frame([UNKNOWN], now=100).raise_alert
    assert not ctrl.evaluate_frame([UNKNOWN], now=120).raise_alert
    assert ctrl.evaluate_frame([UNKNOWN], now=130.1).raise_alert


def test_multiple_unknowns_in_one_frame_alert_once(ctrl):
    d = ctrl.evaluate_frame([UNKNOWN, UNKNOWN], now=100)
    assert d.raise_alert
    assert d.unauthorized_names == (UNKNOWN, UNKNOWN)


def test_enrolled_but_not_authorized_triggers_alert(ctrl):
    d = ctrl.evaluate_frame(["Guest"], now=100)
    assert d.raise_alert and not d.access_granted


def test_mixed_frame_grants_access_but_still_alerts(ctrl):
    d = ctrl.evaluate_frame(["Akshit", UNKNOWN], now=100)
    assert d.access_granted
    assert d.raise_alert
    assert d.unauthorized_names == (UNKNOWN,)


@pytest.mark.parametrize(
    "distance, expected",
    [(2.0, False), (5.0, False), (5.01, True), (120.0, True), (None, False)],
)
def test_alarm_threshold_when_not_authorized(ctrl, distance, expected):
    assert ctrl.should_sound_alarm(distance, now=100) is expected


def test_alarm_suppressed_during_grace_window(ctrl):
    ctrl.evaluate_frame(["Akshit"], now=100)
    assert not ctrl.should_sound_alarm(200.0, now=105)
    assert ctrl.should_sound_alarm(200.0, now=111)
