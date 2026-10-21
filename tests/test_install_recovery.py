"""Synthetic installation and SQLite restore acceptance."""

import json
import sqlite3

import pytest
from flask import Flask

from plainpunch import create_app
from plainpunch.cli import main, parser
from plainpunch.db import connect
from tests.conftest import csrf, login


def test_default_cli_and_web_database_match(tmp_path, monkeypatch):
    monkeypatch.delenv("PLAINPUNCH_DATABASE", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        Flask, "auto_find_instance_path", lambda self: str(tmp_path / "web-instance")
    )
    assert (
        main(
            [
                "create-admin",
                "--name",
                "Synthetic Admin",
                "--email",
                "setup@example.test",
                "--employee-code",
                "SETUP",
                "--password",
                "synthetic-long-password",
                "--pin",
                "1234",
            ]
        )
        == 0
    )
    app = create_app({"TESTING": True, "SECRET_KEY": "synthetic-only"})
    assert parser().parse_args(["init-db"]).database == app.config["DATABASE"]
    client = app.test_client()
    login(client, "setup@example.test", "synthetic-long-password")
    assert client.get("/admin").status_code == 200


def test_online_backup_restores_records_audit_and_login(app, client, tmp_path):
    login(client)
    client.post("/punch/clock-in", data={"csrf_token": csrf(client, "/")})
    client.post("/punch/break-start", data={"csrf_token": csrf(client, "/")})
    client.post("/punch/clock-out", data={"csrf_token": csrf(client, "/")})
    source = connect(app.config["DATABASE"])
    source.execute(
        "UPDATE time_entries SET clock_in=?,clock_out=? WHERE id=1",
        ("2026-10-01T09:00:00+00:00", "2026-10-01T17:00:00+00:00"),
    )
    source.commit()
    client.post(
        "/corrections/new/1",
        data={
            "csrf_token": csrf(client, "/"),
            "clock_in": "2026-10-01T08:00",
            "clock_out": "2026-10-01T17:00",
            "reason": "Synthetic correction",
        },
    )
    admin = app.test_client()
    login(admin, "admin@example.test", "long-test-password")
    admin.post("/admin/corrections/1/approved", data={"csrf_token": csrf(admin, "/admin")})
    admin.post("/admin/users/2/revoke-sessions", data={"csrf_token": csrf(admin, "/admin")})
    assert client.get("/").status_code == 302
    snapshot = tmp_path / "synthetic-backup.sqlite3"
    with sqlite3.connect(snapshot) as backup:
        source.backup(backup)
    tables = ["users", "time_entries", "breaks", "correction_requests", "audit_events"]
    expected = {
        table: [tuple(row) for row in source.execute(f"SELECT * FROM {table} ORDER BY id")]
        for table in tables
    }
    source.close()
    restored_path = tmp_path / "restored" / "plainpunch.sqlite3"
    restored_path.parent.mkdir()
    with sqlite3.connect(snapshot) as backup, sqlite3.connect(restored_path) as restored:
        backup.backup(restored)
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    restored_app = create_app({**app.config, "DATABASE": str(restored_path)})
    db = connect(str(restored_path))
    for table in tables:
        assert [tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY id")] == expected[
            table
        ]
    detail = json.loads(
        db.execute(
            "SELECT detail_json FROM audit_events WHERE action='correction_approved'"
        ).fetchone()[0]
    )
    assert detail["before"]["clock_in"] == "2026-10-01T09:00:00+00:00"
    assert detail["after"]["clock_in"] == "2026-10-01T08:00:00+00:00"
    db.close()
    restored_client = restored_app.test_client()
    login(restored_client, "admin@example.test", "long-test-password")
    assert restored_client.get("/admin/export.csv").status_code == 200
    worker = restored_app.test_client()
    login(worker)
    assert worker.get("/").status_code == 200
    assert worker.get("/admin/export.csv").status_code == 403


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", " "),
        ("email", ""),
        ("employee_code", "\t"),
        ("password", "short"),
        ("pin", "x234"),
        ("pin", "123"),
        ("pin", "1234567890123"),
    ],
)
def test_account_rules_apply_to_http_and_cli(app, client, tmp_path, field, value):
    values = {
        "name": "Synthetic",
        "email": "new@example.test",
        "employee_code": "NEW",
        "password": "synthetic-long-password",
        "pin": "1234",
    }
    values[field] = value
    login(client, "admin@example.test", "long-test-password")
    response = client.post("/admin/users", data={**values, "csrf_token": csrf(client, "/admin")})
    assert response.status_code == 302
    db = connect(app.config["DATABASE"])
    assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 2
    assert (
        db.execute("SELECT count(*) FROM audit_events WHERE action='user_created'").fetchone()[0]
        == 0
    )
    db.close()
    cli_path = str(tmp_path / "rejected.sqlite3")
    arguments = ["--database", cli_path, "create-admin"]
    for key, supplied in values.items():
        arguments.extend(["--" + key.replace("_", "-"), supplied])
    # An empty password prompts interactively; these cases supply a nonempty password.
    assert main(arguments) == 2
    db = connect(cli_path)
    assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 0
    db.close()
