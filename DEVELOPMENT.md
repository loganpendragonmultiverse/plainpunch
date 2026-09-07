# Development

PlainPunch uses a Flask application factory and the standard-library SQLite driver. `db.py` owns schema and connection behavior, `domain.py` owns punch calculations and audit events, and `app.py` owns HTTP behavior. Templates render on the server; no JavaScript is required for core operation.

## Design boundaries

- Store timestamps as timezone-aware UTC ISO 8601 values.
- Every punch, correction decision, and user creation adds an append-only audit event.
- Do not add passive monitoring, inferred activity, hidden scoring, or location collection.
- Keep kiosk actions stateless: a valid code/PIN makes one punch and does not reveal history.
- Schema changes must be forward-compatible and documented before v1.1.
- Never log passwords, PINs, session secrets, or raw CSRF tokens.

## Setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

Run the quality gate documented in [TESTING.md](TESTING.md). Build distributions with `python -m build` after installing `build`.


## Version 1.1.0: reviewed improvements

Add local-date daily/weekly summaries, configurable CSV exports, overlap-safe corrections and revocable administrator sessions.

Admin → Work summaries selects inclusive date ranges (maximum 366 days), daily or Monday-start weekly grouping, CSV columns and separators. UTC interval clipping handles daylight-saving days; breaks and overlapping work are counted once. Correction requests reject invalid/ambiguous wall times, overlapping shifts and duplicate pending requests, with approval-time overlap revalidation. Explicit offset ISO input resolves repeated hours. Punch and correction approval writes serialize through SQLite. Administrator idle expiry and per-user session revocation preserve accounts and audit events. A forward migration adds session_version without removing data. Deployment guidance covers HTTPS, secure cookies, trusted proxies and rate limits; no proxy deployment is claimed. This is a time summary, not a payroll rules engine.

See [deployment controls](docs/deployment-controls.md). Validation includes strict typing, the complete test suite and the 90% coverage gate.
