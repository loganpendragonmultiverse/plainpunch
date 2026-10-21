# Testing

Run the complete local quality gate:

```bash
ruff format --check .
ruff check .
mypy src
coverage run -m pytest
coverage report
python -m pip_audit
python -m build
```

Tests use temporary SQLite databases and cover the punch state machine, automatic break closure, CSRF enforcement, authentication, kiosk flow, correction requests and approval, export, and bootstrap CLI. The measured branch-coverage floor is 90%.

Container smoke test:

```bash
docker compose up -d --build
curl --fail http://localhost:8080/health
docker compose down
```


## Version 1.1.0: reviewed improvements

Add local-date daily/weekly summaries, configurable CSV exports, overlap-safe corrections and revocable administrator sessions.

Admin → Work summaries selects inclusive date ranges (maximum 366 days), daily or Monday-start weekly grouping, CSV columns and separators. UTC interval clipping handles daylight-saving days; breaks and overlapping work are counted once. Correction requests reject invalid/ambiguous wall times, overlapping shifts and duplicate pending requests, with approval-time overlap revalidation. Explicit offset ISO input resolves repeated hours. Punch and correction approval writes serialize through SQLite. Administrator idle expiry and per-user session revocation preserve accounts and audit events. A forward migration adds session_version without removing data. Deployment guidance covers HTTPS, secure cookies, trusted proxies and rate limits; no proxy deployment is claimed. This is a time summary, not a payroll rules engine.

See [deployment controls](docs/deployment-controls.md). Validation includes strict typing, the complete test suite and the 90% coverage gate.

## 1.1.1 — 2026-10-16

Temporary synthetic SQLite fixtures compare both CSV routes for formula/control/whitespace prefixes, Unicode, quotes and multiline values. Verify administrator-only access, revoked and expired sessions, unchanged stored values and worked seconds. Run the existing DST, break, overlap, correction and session tests.

## Installation and recovery acceptance

`tests/test_install_recovery.py` verifies that bootstrap CLI and web defaults share one database, then exercises synthetic punches, a correction approval, session revocation, online SQLite backup and restore. It compares every authoritative table, checks before/after audit evidence, and signs in against the restored database. Release acceptance also installs the built wheel into a fresh virtual environment outside the source tree and repeats default bootstrap/login.

After `python -m build`, run `python tests/accept_installed.py --wheel dist/plainpunch-1.1.2-py3-none-any.whl --report .forge-review/installed-acceptance.json`. This creates a fresh temporary virtual environment, installs the wheel outside the checkout, and exercises its console bootstrap and installed Flask routes. The existing six-platform CI matrix runs this check too; Windows exercises local Flask behavior, while Gunicorn/Docker deployment remains Linux-only.

Linux Docker acceptance: `python tests/accept_docker.py --report .forge-review/docker-acceptance.json`. This builds the documented Dockerfile and runs its real two-worker Gunicorn command with a disposable tmpfs database, no host ports and no runtime network. It checks HTTP bootstrap/login, repeated authenticated requests, health and administrator CSV. It stops only the container created by the check. It does not test a production reverse proxy or an operator's volume/backup storage.
