# PlainPunch

PlainPunch is a small self-hosted time clock without surveillance. Employees make explicit clock-in, clock-out, and break punches; they can review their own history and request corrections. Administrators review those requests, export CSV records, and retain an immutable audit trail of every material action.

It deliberately does **not** track location, screenshots, keystrokes, browser activity, applications, or productivity scores.

## What it includes

- Employee web sign-in and a privacy-preserving shared kiosk
- Explicit shift and break punches
- Personal history with calculated worked time
- Correction requests with approve/reject review
- Before-and-after evidence for approved corrections
- Administrator-created users and CSV export
- UTC storage with configurable local-time display
- SQLite, Docker Compose, health check, and documented backup path

## Three-minute setup with Docker

```bash
cp .env.example .env
# Replace PLAINPUNCH_SECRET_KEY and set your timezone in .env.
docker compose up -d --build
docker compose exec app plainpunch --database /data/plainpunch.sqlite3 create-admin \
  --name "Administrator" --email admin@example.org --employee-code ADMIN
```

Open `http://localhost:8080`. Put TLS and rate limiting in front of the service before exposing it outside a trusted network.

## Local development

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
plainpunch init-db
plainpunch create-admin --name "Administrator" --email admin@example.org --employee-code ADMIN
flask --app plainpunch:create_app run --debug
```

## Data and backups

All authoritative records live in one SQLite file (`instance/plainpunch.sqlite3` locally or `/data/plainpunch.sqlite3` in Docker). Stop writes or use SQLite's online backup API before copying it. Back up the database and your deployment configuration; never commit either.

CSV export is an interoperability aid, not a complete backup: it excludes passwords, break detail, requests, and audit events.

## Security and privacy

Passwords and kiosk PINs use Werkzeug's scrypt password hashes. State-changing HTTP requests require session-bound CSRF tokens. Cookies are HTTP-only and SameSite=Lax; production deployments should set `PLAINPUNCH_SECURE_COOKIES=1` behind HTTPS. The application makes no third-party analytics or telemetry requests.

PlainPunch is not a payroll processor and does not encode jurisdiction-specific overtime, rounding, leave, scheduling, or record-retention rules. Operators remain responsible for legal review, backups, access control, incident response, and accurate payroll practices.

## Supported platforms

The tested runtime is Python 3.11–3.14 on Linux, macOS, and Windows. Docker deployment targets Linux containers. Modern browsers are supported.

## Project status

**Feature complete for v1.0.** Maintenance prioritizes correctness, security, import/export portability, and a deliberately narrow scope. See [DEVELOPMENT.md](DEVELOPMENT.md), [TESTING.md](TESTING.md), and [SECURITY.md](SECURITY.md).

Released under the [MIT License](LICENSE). Contributions follow [CONTRIBUTING.md](CONTRIBUTING.md).

## More open-source projects

PlainPunch is part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/).


## Version 1.1.0: reviewed improvements

Add local-date daily/weekly summaries, configurable CSV exports, overlap-safe corrections and revocable administrator sessions.

Admin → Work summaries selects inclusive date ranges (maximum 366 days), daily or Monday-start weekly grouping, CSV columns and separators. UTC interval clipping handles daylight-saving days; breaks and overlapping work are counted once. Correction requests reject invalid/ambiguous wall times, overlapping shifts and duplicate pending requests, with approval-time overlap revalidation. Explicit offset ISO input resolves repeated hours. Punch and correction approval writes serialize through SQLite. Administrator idle expiry and per-user session revocation preserve accounts and audit events. A forward migration adds session_version without removing data. Deployment guidance covers HTTPS, secure cookies, trusted proxies and rate limits; no proxy deployment is claimed. This is a time summary, not a payroll rules engine.

See [deployment controls](docs/deployment-controls.md). Validation includes strict typing, the complete test suite and the 90% coverage gate.
