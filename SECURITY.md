# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's
[private vulnerability reporting](../../security/advisories/new) for this repository instead.

## Threat model & known limitations

This is an educational / hobbyist edge-AI security system. Know its limits before deploying it:

| Risk | Status | Mitigation |
|---|---|---|
| **Presentation attacks** (printed photo, phone screen) | ⚠️ Not mitigated: 2D recognition has no liveness check | Pair with a second factor (PIN, NFC); see roadmap |
| **Camera occlusion / tampering** | ⚠️ Not detected | The ultrasonic door alarm still triggers when the door opens |
| **Ultrasonic sensor disconnected** | ⚠️ Reading ignored (buzzer off), warning logged | Monitor logs (`journalctl -u smart-door`) |
| **Credential leakage** | ✅ Secrets only in `.env` (git-ignored, `chmod 600`) | Use a dedicated sender account and a revocable App Password |
| **Malicious `encodings.pickle`** | ⚠️ `pickle.load` can execute code | Only load encodings you generated yourself; keep file permissions tight |
| **Biometric data exposure** | ✅ `dataset/`, `captures/`, `*.pickle` are git-ignored | Encrypt the SD card or limit physical access to the Pi |
| **Alert flooding** | ✅ Rate-limited by `ALERT_COOLDOWN_SECONDS` | – |
| **Mail transport** | ✅ SMTP over implicit TLS (port 465) with certificate verification | – |

## Privacy

Facial images and embeddings are personal data under the GDPR and India's DPDP Act. Obtain consent from everyone you enrol. If the camera covers shared or public areas, display notice that recording is in progress.
