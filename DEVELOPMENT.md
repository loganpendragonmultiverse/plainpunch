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

