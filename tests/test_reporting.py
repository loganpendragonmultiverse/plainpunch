from datetime import UTC, date, datetime

import pytest

from plainpunch.db import connect
from plainpunch.reporting import (
    instant,
    merge_intervals,
    parse_wall_time,
    validate_shift,
    work_summary,
)
from tests.conftest import csrf, login


def seed(app):
    db = connect(app.config["DATABASE"])
    db.execute(
        "INSERT INTO time_entries(user_id,clock_in,clock_out,source) VALUES(2,'2026-03-08T05:00:00+00:00','2026-03-09T04:00:00+00:00','web')"
    )
    db.commit()
    return db


def test_daylight_saving_and_overlap_union(app):
    db = seed(app)
    report = work_summary(db, date(2026, 3, 8), date(2026, 3, 8), "America/New_York")
    assert next(row for row in report if row["name"] == "Worker")["worked_seconds"] == 23 * 3600
    db.execute(
        "INSERT INTO time_entries(user_id,clock_in,clock_out,source) VALUES(2,'2026-03-08T05:00:00+00:00','2026-03-09T04:00:00+00:00','web')"
    )
    assert (
        next(
            row
            for row in work_summary(
                db, date(2026, 3, 8), date(2026, 3, 8), "America/New_York", "weekly"
            )
            if row["name"] == "Worker"
        )["worked_seconds"]
        == 23 * 3600
    )
    db.execute("DELETE FROM time_entries WHERE id=2")
    db.execute(
        "INSERT INTO breaks(entry_id,started_at,ended_at) VALUES(1,'2026-03-08T06:00:00+00:00','2026-03-08T07:00:00+00:00')"
    )
    assert (
        next(
            row
            for row in work_summary(db, date(2026, 3, 8), date(2026, 3, 8), "America/New_York")
            if row["name"] == "Worker"
        )["hours"]
        == 22
    )
    with pytest.raises(ValueError, match="overlaps"):
        validate_shift(db, 2, 9, "2026-03-08T05:00:00+00:00", None)
    with pytest.raises(ValueError, match="later"):
        validate_shift(db, 2, 1, "2026-03-08T05:00:00+00:00", "2026-03-07T00:00:00+00:00")
    validate_shift(db, 2, 1, "2026-03-08T05:00:00+00:00", None)
    with pytest.raises(ValueError):
        work_summary(db, date(2026, 3, 8), date(2026, 3, 7), "UTC")
    with pytest.raises(ValueError):
        work_summary(db, date(2026, 3, 8), date(2026, 3, 8), "UTC", "monthly")
    db.close()


def test_wall_times_and_open_shift(app):
    assert parse_wall_time("2026-11-01T01:30:00-04:00", "America/New_York").startswith(
        "2026-11-01T05:30"
    )
    assert parse_wall_time("2026-01-01T09:00", "America/New_York").startswith("2026-01-01T14:00")
    for value in ["2026-03-08T02:30", "2026-11-01T01:30"]:
        with pytest.raises(ValueError, match="ambiguous or nonexistent"):
            parse_wall_time(value, "America/New_York")
    with pytest.raises(ValueError, match="offset"):
        instant("2026-01-01")
    db = seed(app)
    db.execute("UPDATE time_entries SET clock_out=NULL")
    rows = work_summary(
        db, date(2026, 3, 8), date(2026, 3, 8), "UTC", now=datetime(2026, 3, 8, 6, tzinfo=UTC)
    )
    assert next(row for row in rows if row["name"] == "Worker")["worked_seconds"] == 3600
    a = datetime(2026, 1, 1, tzinfo=UTC)
    assert merge_intervals([(a, a)]) == []
    db.close()


def test_report_routes_and_sessions(client, app):
    db = seed(app)
    db.close()
    assert client.get("/admin/reports").status_code == 403
    login(client, "admin@example.test", "long-test-password")
    assert b"Work summaries" in client.get("/admin/reports").data
    response = client.get(
        "/admin/reports?start=2026-03-08&end=2026-03-08&group=weekly&format=csv&columns=name&columns=hours&delimiter=semicolon"
    )
    assert response.status_code == 200 and b"name;hours" in response.data
    assert client.get("/admin/reports?columns=secret").status_code == 400
    assert client.get("/admin/reports?start=bad").status_code == 400
    assert (
        client.post(
            "/admin/users/999/revoke-sessions", data={"csrf_token": csrf(client, "/admin")}
        ).status_code
        == 404
    )
    worker = app.test_client()
    login(worker)
    assert worker.get("/").status_code == 200
    client.post("/admin/users/2/revoke-sessions", data={"csrf_token": csrf(client, "/admin")})
    assert worker.get("/").status_code == 302
    with client.session_transaction() as session:
        session["last_seen"] = 0
    assert client.get("/admin").status_code == 403


def test_duplicate_and_invalid_corrections(client, app):
    db = seed(app)
    db.close()
    login(client)
    data = {"clock_in": "2026-03-08T05:00", "clock_out": "2026-03-09T04:00", "reason": "fix"}
    data["csrf_token"] = csrf(client, "/corrections/new/1")
    assert client.post("/corrections/new/1", data=data).status_code == 302
    data["csrf_token"] = csrf(client, "/corrections/new/1")
    assert b"already pending" in client.post("/corrections/new/1", data=data).data
    data["clock_in"] = "bad"
    assert b"Invalid isoformat" in client.post("/corrections/new/1", data=data).data
