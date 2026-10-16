import csv
import io

import pytest

from plainpunch.db import connect
from tests.conftest import csrf, login


@pytest.mark.parametrize(
    "value",
    [
        "=1+1",
        "+SUM(A1)",
        "-1+1",
        "@SUM(A1)",
        "\t=1",
        "\r=1",
        "\n=1",
        " =1",
        'Élodie, "quoted"\nsecond line',
        "普通の名前",
    ],
)
def test_legacy_export_formula_parity(app, client, value):
    db = connect(app.config["DATABASE"])
    db.execute("UPDATE users SET name=?, employee_code=? WHERE id=2", (value, value))
    db.execute(
        "INSERT INTO time_entries(user_id,clock_in,clock_out,source) VALUES(2,'2026-10-01T09:00:00+00:00','2026-10-01T10:00:00+00:00','web')"
    )
    db.commit()
    db.close()
    login(client, "admin@example.test", "long-test-password")
    legacy = client.get("/admin/export.csv")
    newer = client.get(
        "/admin/reports?start=2026-10-01&end=2026-10-01&format=csv&columns=name&columns=employee_code"
    )
    assert legacy.status_code == newer.status_code == 200
    old_rows = list(csv.DictReader(io.StringIO(legacy.get_data(as_text=True))))
    new_rows = list(csv.DictReader(io.StringIO(newer.get_data(as_text=True))))
    expected = (
        "'" + value
        if (value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@")))
        else value
    )
    assert old_rows[0]["name"] == old_rows[0]["employee_code"] == expected
    assert any(row["name"] == expected and row["employee_code"] == expected for row in new_rows)
    assert old_rows[0]["worked_seconds"] == "3600"


def test_export_authorization_and_expiry(app, client):
    for route in ["/admin/export.csv", "/admin/reports?format=csv"]:
        assert client.get(route).status_code == 403
    login(client)
    assert client.get("/admin/export.csv").status_code == 403
    admin = app.test_client()
    login(admin, "admin@example.test", "long-test-password")
    assert admin.get("/admin/export.csv").status_code == 200
    admin.post("/admin/users/1/revoke-sessions", data={"csrf_token": csrf(admin, "/admin")})
    assert admin.get("/admin/export.csv").status_code == 403
    login(admin, "admin@example.test", "long-test-password")
    with admin.session_transaction() as session:
        session["last_seen"] = 0
    assert admin.get("/admin/export.csv").status_code == 403


@pytest.mark.parametrize("value", ["\tordinary", "\rordinary", "\nordinary", " \t=1", "  @SUM(A1)"])
def test_csv_cell_controls(value):
    from plainpunch.app import csv_cell

    assert csv_cell(value) == "'" + value
    assert csv_cell(42) == 42
    assert csv_cell("") == ""
