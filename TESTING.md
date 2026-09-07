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
