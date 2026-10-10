"""Desktop sensor monitoring console (Tkinter).

Tabs: Motion (live PIR status, sensitivity/interval settings, statistics),
LED Control (manual toggle) and History (last 100 events). Every event is
persisted to SQLite via :class:`homeauto.storage.EventStore`.

Threading model: a worker thread only *reads* the sensor and pushes results
onto a queue; all Tk widget updates happen on the Tk main thread through
``root.after`` polling (Tkinter is not thread-safe).

Works without hardware: set ``HOMEAUTO_GPIO_BACKEND=emulator`` to drive the PIR
input from the raspberry-gpio-emulator GUI, or ``mock`` for headless runs.

Run:  python -m homeauto.gui.sensor_monitor
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from ..config import PINS
from ..hal.gpio import GPIO, IS_SIMULATED
from ..storage import EventStore

HISTORY_LIMIT = 100


class SensorMonitor:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Sensor Monitoring System" + (" [simulated]" if IS_SIMULATED else ""))
        self.root.geometry("820x600")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(PINS.led, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(PINS.pir, GPIO.IN)

        self.store = EventStore()
        self.events: queue.Queue[bool] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.led_on = False
        self.total_detections = 0
        self.last_motion: bool | None = None

        self.interval_var = tk.StringVar(value="1.0")
        self.sensitivity_var = tk.StringVar(value="Medium")
        self.detection_count = tk.StringVar(value="0")
        self.last_detection = tk.StringVar(value="N/A")

        frame = ttk.Frame(root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        self._build_controls(frame)
        tabs = ttk.Notebook(frame)
        tabs.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self._build_motion_tab(tabs)
        self._build_led_tab(tabs)
        self._build_history_tab(tabs)

        self.root.after(100, self._drain_events)

    # ------------------------------------------------------------------ layout
    def _build_controls(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Control", padding=8)
        box.pack(fill=tk.X)
        self.start_btn = ttk.Button(box, text="Start Monitoring", command=self.start)
        self.stop_btn = ttk.Button(box, text="Stop Monitoring", command=self.stop, state=tk.DISABLED)
        self.start_btn.grid(row=0, column=0, padx=5)
        self.stop_btn.grid(row=0, column=1, padx=5)
        ttk.Label(box, text="Sensitivity:").grid(row=0, column=2, padx=(20, 5))
        ttk.Combobox(box, textvariable=self.sensitivity_var, values=["Low", "Medium", "High"],
                     state="readonly", width=10).grid(row=0, column=3)
        ttk.Label(box, text="Interval (s):").grid(row=0, column=4, padx=(20, 5))
        ttk.Entry(box, textvariable=self.interval_var, width=8).grid(row=0, column=5)

    def _build_motion_tab(self, tabs: ttk.Notebook) -> None:
        tab = ttk.Frame(tabs, padding=10)
        tabs.add(tab, text="Motion")
        status = ttk.LabelFrame(tab, text="Motion Status", padding=10)
        status.pack(fill=tk.X)
        self.motion_label = ttk.Label(status, text="Idle", font=("Arial", 14, "bold"))
        self.motion_label.pack(side=tk.LEFT)
        self.indicator_canvas = tk.Canvas(status, width=20, height=20, highlightthickness=0)
        self.indicator_canvas.pack(side=tk.LEFT, padx=10)
        self.indicator = self.indicator_canvas.create_oval(2, 2, 18, 18, fill="grey")

        stats = ttk.LabelFrame(tab, text="Statistics", padding=10)
        stats.pack(fill=tk.X, pady=10)
        ttk.Label(stats, text="Total detections:").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(stats, textvariable=self.detection_count).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(stats, text="Last detection:").grid(row=1, column=0, sticky=tk.W)
        ttk.Label(stats, textvariable=self.last_detection).grid(row=1, column=1, sticky=tk.W)
        ttk.Button(stats, text="Reset Statistics", command=self.reset_stats).grid(row=2, column=0, pady=8)

    def _build_led_tab(self, tabs: ttk.Notebook) -> None:
        tab = ttk.Frame(tabs, padding=10)
        tabs.add(tab, text="LED Control")
        self.led_label = ttk.Label(tab, text="LED: OFF", font=("Arial", 14, "bold"))
        self.led_label.pack(anchor=tk.W)
        ttk.Button(tab, text="Toggle LED", command=self.toggle_led).pack(anchor=tk.W, pady=10)

    def _build_history_tab(self, tabs: ttk.Notebook) -> None:
        tab = ttk.Frame(tabs, padding=10)
        tabs.add(tab, text="History")
        self.history = ttk.Treeview(tab, columns=("ts", "sensor", "value"), show="headings")
        for col, title in (("ts", "Timestamp"), ("sensor", "Sensor"), ("value", "Value")):
            self.history.heading(col, text=title)
        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.history.yview)
        self.history.configure(yscrollcommand=scroll.set)
        self.history.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # ------------------------------------------------------------------ behaviour
    def _interval(self) -> float:
        try:
            value = float(self.interval_var.get())
        except ValueError:
            return 1.0
        return value if value > 0 else 1.0

    def _poll_sensor(self) -> None:
        self.stop_event.wait(2)  # PIR warm-up
        while not self.stop_event.is_set():
            self.events.put(bool(GPIO.input(PINS.pir)))
            self.stop_event.wait(self._interval())

    def _drain_events(self) -> None:
        while not self.events.empty():
            self._on_motion_sample(self.events.get_nowait())
        self.root.after(100, self._drain_events)

    def _on_motion_sample(self, detected: bool) -> None:
        self.motion_label.config(text="Motion Detected" if detected else "No Motion")
        self.indicator_canvas.itemconfig(self.indicator, fill="green" if detected else "red")
        if detected and not self.last_motion:  # count rising edges, not every sample
            self.total_detections += 1
            self.detection_count.set(str(self.total_detections))
            self.last_detection.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.store.log_motion(True)
            self._add_history("Motion", "Detected")
        self.last_motion = detected

    def _add_history(self, sensor: str, value: str) -> None:
        self.history.insert("", tk.END, values=(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sensor, value))
        children = self.history.get_children()
        if len(children) > HISTORY_LIMIT:
            self.history.delete(children[0])

    def start(self) -> None:
        self.stop_event.clear()
        self.worker = threading.Thread(target=self._poll_sensor, daemon=True)
        self.worker.start()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._add_history("System", f"Monitoring started (sensitivity={self.sensitivity_var.get()})")

    def stop(self) -> None:
        self.stop_event.set()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.motion_label.config(text="Idle")
        self.indicator_canvas.itemconfig(self.indicator, fill="grey")
        self._add_history("System", "Monitoring stopped")

    def reset_stats(self) -> None:
        self.total_detections = 0
        self.detection_count.set("0")
        self.last_detection.set("N/A")
        self._add_history("Motion", "Statistics reset")

    def toggle_led(self) -> None:
        self.led_on = not self.led_on
        GPIO.output(PINS.led, GPIO.HIGH if self.led_on else GPIO.LOW)
        self.led_label.config(text=f"LED: {'ON' if self.led_on else 'OFF'}")
        self.store.log_led(self.led_on, "gui")
        self._add_history("LED", "ON" if self.led_on else "OFF")

    def close(self) -> None:
        self.stop_event.set()
        time.sleep(0.05)
        GPIO.output(PINS.led, GPIO.LOW)
        GPIO.cleanup()
        self.store.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    SensorMonitor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
