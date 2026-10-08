"""Thread-safe SQLite event store shared by the web API and the desktop GUI.

Schema (also queried by the natural-language "database chat" assistant):

    motion_data(id, timestamp, motion_detected)
    led_data(id, timestamp, led_state, source)
    climate_data(id, timestamp, temperature_c, humidity_pct)

All statements are parameterised - no string-built SQL.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime

from .config import SETTINGS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS motion_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    motion_detected INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS led_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    led_state INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'unknown'
);
CREATE TABLE IF NOT EXISTS climate_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    temperature_c REAL,
    humidity_pct REAL
);
"""


class EventStore:
    def __init__(self, path: str = SETTINGS.db_path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def _insert(self, sql: str, params: tuple) -> None:
        with self._lock, self._conn:
            self._conn.execute(sql, (datetime.now().isoformat(sep=" ", timespec="seconds"), *params))

    def log_motion(self, detected: bool) -> None:
        self._insert("INSERT INTO motion_data (timestamp, motion_detected) VALUES (?, ?)", (int(detected),))

    def log_led(self, state: bool, source: str) -> None:
        self._insert("INSERT INTO led_data (timestamp, led_state, source) VALUES (?, ?, ?)", (int(state), source))

    def log_climate(self, temperature: float, humidity: float) -> None:
        self._insert(
            "INSERT INTO climate_data (timestamp, temperature_c, humidity_pct) VALUES (?, ?, ?)",
            (temperature, humidity),
        )

    def count_led_on(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM led_data WHERE led_state = 1").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
