"""Flask control plane for the Raspberry Pi hub.

* ``GET  /``             - single-page dashboard (static, no secrets embedded)
* ``GET  /api/status``   - LED / motion / climate state           [token]
* ``POST /api/led``      - ``{"state": "on" | "off"}``             [token]
* ``POST /api/mode``     - ``{"mode": "auto" | "manual"}``         [token]

In ``auto`` mode the LED follows the PIR sensor (presence lighting); in
``manual`` mode it is driven only through the API. Motion events and LED
changes are persisted to SQLite; optional e-mail alerts on motion.

Security controls: mandatory bearer token (constant-time comparison), state
changes only via POST + JSON (no CSRF-able GET toggles), strict input
validation, CSP and hardening headers, loopback bind by default.

Run:  python -m homeauto.web.app
"""

from __future__ import annotations

import hmac
import logging
import os
import sys
import threading
import time
from functools import wraps

from flask import Flask, abort, jsonify, render_template, request

from ..config import PINS, SETTINGS
from ..hal.gpio import GPIO, IS_SIMULATED
from ..storage import EventStore

log = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024  # API payloads are tiny

_state_lock = threading.Lock()
_state = {
    "led": False,
    "mode": "manual",
    "motion": False,
    "temperature_c": None,
    "humidity_pct": None,
    "climate_updated": None,
    "simulated": IS_SIMULATED,
}
_store: EventStore | None = None
MOTION_EMAIL = os.getenv("HOMEAUTO_MOTION_EMAIL", "0") == "1"


# --------------------------------------------------------------------------- security
def require_token(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        supplied = header.removeprefix("Bearer ").strip()
        if not supplied or not hmac.compare_digest(supplied.encode(), SETTINGS.api_token.encode()):
            abort(401)
        return view(*args, **kwargs)

    return wrapper


@app.after_request
def security_headers(response):
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(404)
@app.errorhandler(413)
def json_error(err):
    return jsonify(error=err.name), err.code


# --------------------------------------------------------------------------- hardware
def _set_led(on: bool, source: str) -> None:
    with _state_lock:
        if _state["led"] == on:
            return
        _state["led"] = on
    GPIO.output(PINS.led, GPIO.HIGH if on else GPIO.LOW)
    if _store:
        _store.log_led(on, source)
    log.info("LED %s (%s)", "ON" if on else "OFF", source)


def _motion_loop(stop: threading.Event) -> None:
    time.sleep(2)  # PIR warm-up
    while not stop.is_set():
        detected = bool(GPIO.input(PINS.pir))
        with _state_lock:
            rising_edge = detected and not _state["motion"]
            _state["motion"] = detected
            auto = _state["mode"] == "auto"
        if rising_edge:
            if _store:
                _store.log_motion(True)
            if MOTION_EMAIL:
                from ..alerts.email_alert import send_email_alert

                threading.Thread(  # never block the sensor loop on SMTP
                    target=send_email_alert,
                    args=("Motion detected", f"PIR sensor triggered at {time.ctime()}"),
                    daemon=True,
                ).start()
        if auto:
            _set_led(detected, "pir")
        stop.wait(0.2)


def _climate_loop(stop: threading.Event) -> None:
    from ..sensors import dht11

    while not stop.is_set():
        try:
            temperature, humidity = dht11.read(retries=3)
        except ImportError:
            log.warning("Adafruit_DHT not installed - climate sampling disabled")
            return
        if temperature is not None:
            with _state_lock:
                _state.update(temperature_c=temperature, humidity_pct=humidity, climate_updated=time.time())
            if _store:
                _store.log_climate(temperature, humidity)
        stop.wait(SETTINGS.sensor_poll_seconds)


# --------------------------------------------------------------------------- routes
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
@require_token
def status():
    with _state_lock:
        return jsonify(_state)


@app.post("/api/led")
@require_token
def led():
    payload = request.get_json(silent=True) or {}
    state = payload.get("state")
    if state not in ("on", "off"):
        abort(400)
    with _state_lock:
        _state["mode"] = "manual"  # a manual command overrides presence automation
    _set_led(state == "on", "api")
    return jsonify(led=state, mode="manual")


@app.post("/api/mode")
@require_token
def mode():
    payload = request.get_json(silent=True) or {}
    new_mode = payload.get("mode")
    if new_mode not in ("auto", "manual"):
        abort(400)
    with _state_lock:
        _state["mode"] = new_mode
    log.info("Mode -> %s", new_mode)
    return jsonify(mode=new_mode)


# --------------------------------------------------------------------------- entrypoint
def main() -> None:
    global _store
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if len(SETTINGS.api_token) < 24:
        sys.exit(
            "HOMEAUTO_API_TOKEN must be set to a random value of >= 24 chars.\n"
            "Generate one with:  python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PINS.led, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PINS.pir, GPIO.IN)
    _store = EventStore()

    stop = threading.Event()
    for target in (_motion_loop, _climate_loop):
        threading.Thread(target=target, args=(stop,), daemon=True).start()

    log.info("Serving on http://%s:%d (simulated GPIO: %s)", SETTINGS.web_host, SETTINGS.web_port, IS_SIMULATED)
    try:
        app.run(host=SETTINGS.web_host, port=SETTINGS.web_port, threaded=True)
    finally:
        stop.set()
        GPIO.output(PINS.led, GPIO.LOW)
        GPIO.cleanup()
        _store.close()


if __name__ == "__main__":
    main()
