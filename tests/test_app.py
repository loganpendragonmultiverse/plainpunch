from plainpunch.db import connect
from tests.conftest import csrf, login


def test_health_and_login(client):
    assert client.get("/health").json == {"status": "ok"}
    response = client.post(
        "/login",
        data={"csrf_token": csrf(client), "email": "worker@example.test", "password": "wrong"},
    )
    assert b"not recognized" in response.data
    login(client)
    assert client.get("/").status_code == 200


def test_csrf_and_auth_required(client):
    assert client.post("/login", data={}).status_code == 400
    assert client.get("/").status_code == 302
    assert client.get("/admin").status_code == 403


def test_worker_punches_and_requests_correction(client, app):
    login(client)
    token = csrf(client, "/")
    assert (
        b"Clocked in"
        in client.post("/punch/clock-in", data={"csrf_token": token}, follow_redirects=True).data
    )
    assert (
        b"Break started"
        in client.post(
            "/punch/break-start", data={"csrf_token": csrf(client, "/")}, follow_redirects=True
        ).data
    )
    assert (
        b"Clocked out"
        in client.post(
            "/punch/clock-out", data={"csrf_token": csrf(client, "/")}, follow_redirects=True
        ).data
    )
    response = client.post(
        "/corrections/new/1",
        data={
            "csrf_token": csrf(client, "/corrections/new/1"),
            "clock_in": "2026-01-01T09:00",
            "clock_out": "2026-01-01T17:00",
            "reason": "Forgot the correct time",
        },
        follow_redirects=True,
    )
    assert b"submitted" in response.data


def test_worker_correction_validation_and_logout(client):
    login(client)
    client.post("/punch/clock-in", data={"csrf_token": csrf(client, "/")}, follow_redirects=True)
    response = client.post(
        "/corrections/new/1",
        data={
            "csrf_token": csrf(client, "/corrections/new/1"),
            "clock_in": "2026-01-01T17:00",
            "clock_out": "2026-01-01T09:00",
            "reason": "wrong order",
        },
    )
    assert b"later than" in response.data
    response = client.post(
        "/punch/not-real", data={"csrf_token": csrf(client, "/")}, follow_redirects=True
    )
    assert b"Unknown punch action" in response.data
    assert client.post("/logout", data={"csrf_token": csrf(client, "/")}).status_code == 302


def test_kiosk(client):
    response = client.post(
        "/kiosk",
        data={
            "csrf_token": csrf(client, "/kiosk"),
            "employee_code": "W1",
            "pin": "5678",
            "action": "clock-in",
        },
        follow_redirects=True,
    )
    assert b"Clocked in" in response.data
    response = client.post(
        "/kiosk",
        data={
            "csrf_token": csrf(client, "/kiosk"),
            "employee_code": "W1",
            "pin": "bad",
            "action": "clock-out",
        },
        follow_redirects=True,
    )
    assert b"not recognized" in response.data


def test_admin_user_review_and_export(client, app):
    login(client, "admin@example.test", "long-test-password")
    response = client.post(
        "/admin/users",
        data={
            "csrf_token": csrf(client, "/admin"),
            "name": "New Person",
            "email": "new@example.test",
            "employee_code": "N1",
            "password": "a-longer-password",
            "pin": "9999",
        },
        follow_redirects=True,
    )
    assert b"User created" in response.data
    assert client.get("/admin/export.csv").status_code == 200
    path = app.config["DATABASE"]
    db = connect(path)
    db.execute(
        "INSERT INTO time_entries(user_id,clock_in,clock_out,source) VALUES(2,'2026-01-01T14:00:00+00:00','2026-01-01T20:00:00+00:00','web')"
    )
    db.execute(
        "INSERT INTO correction_requests(entry_id,user_id,proposed_clock_in,proposed_clock_out,reason,created_at) VALUES(1,2,'2026-01-01T13:00:00+00:00','2026-01-01T20:00:00+00:00','missed','2026-01-02T00:00:00+00:00')"
    )
    db.commit()
    db.close()
    response = client.post(
        "/admin/corrections/1/approved",
        data={"csrf_token": csrf(client, "/admin"), "reviewer_note": "verified"},
        follow_redirects=True,
    )
    assert b"approved" in response.data


def test_admin_duplicate_user_and_rejection(client, app):
    login(client, "admin@example.test", "long-test-password")
    response = client.post(
        "/admin/users",
        data={
            "csrf_token": csrf(client, "/admin"),
            "name": "Duplicate",
            "email": "worker@example.test",
            "employee_code": "OTHER",
            "password": "a-longer-password",
            "pin": "9999",
        },
        follow_redirects=True,
    )
    assert b"already in use" in response.data
    db = connect(app.config["DATABASE"])
    db.execute(
        "INSERT INTO time_entries(user_id,clock_in,clock_out,source) "
        "VALUES(2,'2026-01-01T14:00:00+00:00','2026-01-01T20:00:00+00:00','web')"
    )
    db.execute(
        "INSERT INTO correction_requests(entry_id,user_id,proposed_clock_in,"
        "proposed_clock_out,reason,created_at) VALUES(1,2,'2026-01-01T13:00:00+00:00',"
        "'2026-01-01T20:00:00+00:00','missed','2026-01-02T00:00:00+00:00')"
    )
    db.commit()
    db.close()
    response = client.post(
        "/admin/corrections/1/rejected",
        data={"csrf_token": csrf(client, "/admin"), "reviewer_note": "not verified"},
        follow_redirects=True,
    )
    assert b"rejected" in response.data
    assert (
        client.post(
            "/admin/corrections/1/invalid", data={"csrf_token": csrf(client, "/admin")}
        ).status_code
        == 404
    )
