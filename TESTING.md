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

