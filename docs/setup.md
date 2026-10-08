# Setup & Deployment Guide

## 1. Raspberry Pi edge hub

### 1.1 OS preparation
Raspberry Pi OS (64-bit, Bookworm) on a Pi 4 or Pi 5:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-venv python3-tk mpg123 git
```

### 1.2 Install
```bash
git clone https://github.com/Akshit0203/secure-iot-home-automation.git
cd secure-iot-home-automation/raspberry-pi
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Raspberry Pi 5:** the classic `RPi.GPIO` cannot access the Pi 5 RP1 GPIO chip. Swap in the API-compatible lgpio shim:
```bash
pip uninstall -y RPi.GPIO && pip install rpi-lgpio
```

**TM1637 driver:** download `tm1637.py` from [timwaizenegger/raspberrypi-examples](https://github.com/timwaizenegger/raspberrypi-examples) into `raspberry-pi/`.

### 1.3 Configure
```bash
cp .env.example .env
chmod 600 .env
python -c "import secrets; print(secrets.token_urlsafe(32))"   # -> HOMEAUTO_API_TOKEN
```
Fill in `OWM_API_KEY` (free key from openweathermap.org) and, for alerts, `SMTP_USER`, `SMTP_APP_PASSWORD` and `ALERT_RECIPIENT`. Gmail requires 2-Step Verification plus an **App Password**.

### 1.4 Run any module
```bash
python -m homeauto.web.app                 # web dashboard + REST API
python -m homeauto.gui.sensor_monitor      # desktop console
python -m homeauto.sensors.dht11
python -m homeauto.sensors.ultrasonic
python -m homeauto.sensors.ldr
python -m homeauto.display.tm1637_climate
python -m homeauto.actuators.pwm_led
python -m homeauto.actuators.ac_dimmer
python -m homeauto.alerts.email_alert      # sends a test mail
python -m homeauto.weather.dashboard       # --no-voice / --no-map
python -m homeauto.weather.city_forecast
```

### 1.5 Run without hardware
```bash
HOMEAUTO_GPIO_BACKEND=mock     python -m homeauto.web.app       # headless simulation
HOMEAUTO_GPIO_BACKEND=emulator python -m homeauto.gui.sensor_monitor
```
The `emulator` backend needs `EmulatorGUI.py` from [nosix/raspberry-gpio-emulator](https://github.com/nosix/raspberry-gpio-emulator) on the `PYTHONPATH`.

### 1.6 Run as a service (systemd)
`/etc/systemd/system/homeauto-web.service`:
```ini
[Unit]
Description=Home Automation web API
After=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/secure-iot-home-automation/raspberry-pi
ExecStart=/home/pi/secure-iot-home-automation/raspberry-pi/.venv/bin/python -m homeauto.web.app
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now homeauto-web
```

### 1.7 Exposing the dashboard securely
Keep `HOMEAUTO_WEB_HOST=127.0.0.1` and put a TLS reverse proxy in front of it:

```nginx
server {
    listen 443 ssl;
    server_name homehub.local;
    ssl_certificate     /etc/ssl/homehub.crt;
    ssl_certificate_key /etc/ssl/homehub.key;
    location / { proxy_pass http://127.0.0.1:5000; }
}
```
For remote access, prefer a VPN (WireGuard or Tailscale) over port-forwarding.

## 2. ESP32 Blynk node

1. In **Blynk Console** create the template *IOT LED* with datastreams **V0** (Switch, int 0–1) and **V1** (LED, int 0–1), then add a device.
2. Arduino IDE: install the **esp32** board package (Espressif) and the **Blynk** library (≥ 1.3.2).
3. `cp firmware/esp32-blynk-led/secrets.example.h firmware/esp32-blynk-led/secrets.h` and fill in the template ID, auth token and Wi-Fi credentials.
4. Board **ESP32 Dev Module**, upload, then open the Serial Monitor at 115200 baud. You should see `Ready (ping: …ms)`.

## 3. Arduino UNO R4 WiFi node

1. Install the **Arduino UNO R4 Boards** package.
2. Open `firmware/arduino-ldr-relay/arduino-ldr-relay.ino` and upload.
3. Use the Serial Plotter to tune the thresholds for your room.

## 4. Development

```bash
pip install -r requirements-dev.txt
ruff check .
HOMEAUTO_GPIO_BACKEND=mock pytest -q
```
