# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2025-06-24

### Added
- Unified `homeauto` Python package for the Raspberry Pi hub, with env-driven configuration and a conflict-free BCM pin map.
- GPIO hardware abstraction layer (RPi.GPIO / raspberry-gpio-emulator / headless mock).
- Token-authenticated Flask REST API and dashboard with PIR-driven *auto* mode.
- Thread-safe SQLite event store (`motion_data`, `led_data`, `climate_data`).
- Rate-limited SMTPS e-mail alerting.
- Shared OpenWeatherMap client used by both weather applications.
- pytest suite (22 tests) and GitHub Actions CI (ruff, pytest, Arduino compile, gitleaks).
- ESP32 firmware connection watchdog, state re-sync and input validation.
- Arduino LDR sketch hysteresis to prevent relay chatter.

### Changed (relative to the original prototype scripts)
- All credentials moved out of source code into `.env` / `secrets.h`.
- ESP32 ↔ Blynk transport switched from cleartext port 80 to TLS.
- Web LED control changed from `GET /led/on|off` to authenticated `POST /api/led`.
- Desktop GUI no longer updates Tk widgets from worker threads, and no longer creates a second `Tk()` root from a thread.

### Fixed
- DHT11 print statement applied `.format()` to the wrong string, so the readings were never shown.
- TM1637 display received `temp*100+humidity` but formatted it as `TT00`. It now shows `TT:HH` correctly.
- HC-SR04 busy-wait loops could hang forever without an echo. A 38 ms timeout and median filtering were added.
- AC-dimmer delay constant assumed a 60 Hz / 128-step scale. The delay is now derived from the mains frequency (50 Hz by default), and the TRIAC is never fired at 0 %.
- PIR history counted every poll sample as a new detection. Only rising edges are counted now.

## [0.1.0] - 2024-12-09
- Initial prototypes: ESP32 + Blynk LED control, Raspberry Pi DHT11 and PWM experiments.
