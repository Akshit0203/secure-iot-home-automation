# Security Policy

## Supported versions
| Version | Supported |
|---------|-----------|
| 1.x     | ✅ |

## Reporting a vulnerability
Please **do not open a public issue** for security problems. Use GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository ("Security" tab → "Report a vulnerability").

Include affected component(s), reproduction steps and impact. You can expect an initial response within 7 days.

## Handling secrets
- Never commit `.env`, `secrets.h`, tokens, Wi-Fi passwords or API keys. Both files are git-ignored, and CI runs **gitleaks** on every push.
- If a secret is ever committed, **rotate it immediately**. Rewriting Git history alone is not enough, because forks and caches may already hold a copy.

The full threat model and controls are in [docs/security-model.md](docs/security-model.md).
