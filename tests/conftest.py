from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from plainpunch import create_app
from plainpunch.db import connect
from plainpunch.domain import utc_now


@pytest.fixture
def app(tmp_path: Path) -> Flask:
    database = tmp_path / "test.sqlite3"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": str(database),
            "TIMEZONE": "UTC",
            "SESSION_COOKIE_SECURE": False,
        }
    )
    db = connect(str(database))
    db.execute(
        "INSERT INTO users(name,email,employee_code,password_hash,pin_hash,is_admin,created_at) VALUES(?,?,?,?,?,1,?)",
        (
            "Admin",
            "admin@example.test",
            "A1",
            generate_password_hash("long-test-password", method="scrypt"),
            generate_password_hash("1234", method="scrypt"),
            utc_now(),
        ),
    )
    db.execute(
        "INSERT INTO users(name,email,employee_code,password_hash,pin_hash,is_admin,created_at) VALUES(?,?,?,?,?,0,?)",
        (
            "Worker",
            "worker@example.test",
            "W1",
            generate_password_hash("worker-test-password", method="scrypt"),
            generate_password_hash("5678", method="scrypt"),
            utc_now(),
        ),
    )
    db.commit()
    db.close()
    return app


@pytest.fixture
def client(app: Flask) -> Any:
    return app.test_client()


def csrf(client: Any, path: str = "/login") -> str:
    client.get(path)
    with client.session_transaction() as session:
        return str(session["csrf_token"])


def login(
    client: Any, email: str = "worker@example.test", password: str = "worker-test-password"
) -> None:
    client.post("/login", data={"csrf_token": csrf(client), "email": email, "password": password})
