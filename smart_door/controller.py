"""Hardware-independent access-control policy.

All decisions (LED state, buzzer state, when to raise an e-mail alert) live
here so they can be unit-tested without a camera or GPIO header.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass

UNKNOWN = "Unknown"


@dataclass(frozen=True)
class FrameDecision:
    """Outcome of evaluating the identities seen in one camera frame."""

    authorized_seen: bool
    access_granted: bool
    raise_alert: bool
    unauthorized_names: tuple[str, ...]


class AccessController:
    """Thread-safe state machine shared by the vision and door-alarm loops.

    * An authorized face opens a grace window of ``grace_seconds`` during which
      the green LED stays on and the buzzer is suppressed.
    * Any non-authorized face (unknown or enrolled-but-not-allowed) raises an
      alert, rate-limited to one per ``cooldown_seconds``.
    * Outside the grace window the buzzer sounds whenever the measured distance
      exceeds ``door_open_threshold_cm`` (door leaf moved away from the sensor).
    """

    def __init__(
        self,
        is_authorized: Callable[[str], bool],
        grace_seconds: float,
        cooldown_seconds: float,
        door_open_threshold_cm: float,
    ) -> None:
        self._is_authorized = is_authorized
        self._grace = grace_seconds
        self._cooldown = cooldown_seconds
        self._threshold = door_open_threshold_cm
        self._lock = threading.Lock()
        self._authorized_until = float("-inf")
        self._last_alert_at = float("-inf")

    def access_granted(self, now: float) -> bool:
        with self._lock:
            return now < self._authorized_until

    def evaluate_frame(self, names: Iterable[str], now: float) -> FrameDecision:
        names = tuple(names)
        authorized_seen = any(self._is_authorized(n) for n in names)
        unauthorized = tuple(n for n in names if not self._is_authorized(n))

        with self._lock:
            if authorized_seen:
                self._authorized_until = now + self._grace

            raise_alert = bool(unauthorized) and (now - self._last_alert_at) > self._cooldown
            if raise_alert:
                self._last_alert_at = now

            granted = now < self._authorized_until

        return FrameDecision(
            authorized_seen=authorized_seen,
            access_granted=granted,
            raise_alert=raise_alert,
            unauthorized_names=unauthorized,
        )

    def should_sound_alarm(self, distance_cm: float | None, now: float) -> bool:
        """Return True if the buzzer must be on for this distance reading.

        ``None`` means the ultrasonic sensor produced no echo (wiring fault or
        timeout); the reading is ignored and the buzzer stays off.
        """
        if self.access_granted(now) or distance_cm is None:
            return False
        return distance_cm > self._threshold
