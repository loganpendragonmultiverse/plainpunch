from datetime import UTC, datetime, timedelta

import pytest

from plainpunch.db import connect, init_db
from plainpunch.domain import active_break, active_entry, punch, seconds_worked


def test_full_punch_cycle(tmp_path):
    path = str(tmp_path / "db.sqlite3")
    init_db(path)
    db = connect(path)
    db.execute(
        "INSERT INTO users(name,email,employee_code,password_hash,pin_hash,created_at) VALUES('A','a@b.c','A','x','y',?)",
        (datetime.now(UTC).isoformat(),),
    )
    db.commit()
    assert punch(db, 1, "clock-in") == "Clocked in."
    assert active_entry(db, 1)
    with pytest.raises(ValueError, match="already"):
        punch(db, 1, "clock-in")
    assert punch(db, 1, "break-start") == "Break started."
    assert active_break(db, 1)
    with pytest.raises(ValueError, match="already"):
        punch(db, 1, "break-start")
    assert punch(db, 1, "break-end") == "Break ended."
    assert punch(db, 1, "clock-out") == "Clocked out."
    assert active_entry(db, 1) is None
    assert db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 4


def test_clock_out_ends_break(tmp_path):
    path = str(tmp_path / "db.sqlite3")
    init_db(path)
    db = connect(path)
    db.execute(
        "INSERT INTO users(name,email,employee_code,password_hash,pin_hash,created_at) VALUES('A','a@b.c','A','x','y',?)",
        (datetime.now(UTC).isoformat(),),
    )
    db.commit()
    punch(db, 1, "clock-in")
    punch(db, 1, "break-start")
    punch(db, 1, "clock-out")
    assert db.execute("SELECT ended_at FROM breaks").fetchone()[0]


def test_invalid_actions(tmp_path):
    path = str(tmp_path / "db.sqlite3")
    init_db(path)
    db = connect(path)
    for action, message in [
        ("clock-out", "not clocked"),
        ("break-start", "Clock in"),
        ("break-end", "no active shift"),
        ("what", "Unknown"),
    ]:
        with pytest.raises(ValueError, match=message):
            punch(db, 1, action)


def test_seconds_worked_subtracts_breaks():
    start = datetime(2026, 1, 1, tzinfo=UTC)

    class Row(dict):
        pass

    breaks = [
        Row(
            started_at=(start + timedelta(hours=1)).isoformat(),
            ended_at=(start + timedelta(hours=1, minutes=15)).isoformat(),
        )
    ]
    assert (
        seconds_worked(start.isoformat(), (start + timedelta(hours=2)).isoformat(), breaks) == 6300
    )
