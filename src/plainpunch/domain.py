"""Time-clock domain operations."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any, cast


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def audit(
    db: sqlite3.Connection,
    actor_id: int | None,
    action: str,
    subject_type: str,
    subject_id: int | None,
    detail: dict[str, Any],
) -> None:
    db.execute(
        "INSERT INTO audit_events(actor_id, action, subject_type, subject_id, detail_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (actor_id, action, subject_type, subject_id, json.dumps(detail, sort_keys=True), utc_now()),
    )


def active_entry(db: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return cast(
        sqlite3.Row | None,
        db.execute(
            "SELECT * FROM time_entries WHERE user_id = ? AND clock_out IS NULL ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone(),
    )


def active_break(db: sqlite3.Connection, entry_id: int) -> sqlite3.Row | None:
    return cast(
        sqlite3.Row | None,
        db.execute(
            "SELECT * FROM breaks WHERE entry_id = ? AND ended_at IS NULL ORDER BY id DESC LIMIT 1",
            (entry_id,),
        ).fetchone(),
    )


def punch(db: sqlite3.Connection, user_id: int, action: str, source: str = "web") -> str:
    now = utc_now()
    entry = active_entry(db, user_id)
    if action == "clock-in":
        if entry:
            raise ValueError("You are already clocked in.")
        cursor = db.execute(
            "INSERT INTO time_entries(user_id, clock_in, source) VALUES (?, ?, ?)",
            (user_id, now, source),
        )
        audit(db, user_id, "clock_in", "time_entry", cursor.lastrowid, {"source": source})
        message = "Clocked in."
    elif action == "clock-out":
        if not entry:
            raise ValueError("You are not clocked in.")
        current_break = active_break(db, int(entry["id"]))
        if current_break:
            db.execute("UPDATE breaks SET ended_at = ? WHERE id = ?", (now, current_break["id"]))
            audit(db, user_id, "break_end", "break", int(current_break["id"]), {"automatic": True})
        db.execute("UPDATE time_entries SET clock_out = ? WHERE id = ?", (now, entry["id"]))
        audit(db, user_id, "clock_out", "time_entry", int(entry["id"]), {"source": source})
        message = "Clocked out."
    elif action == "break-start":
        if not entry:
            raise ValueError("Clock in before starting a break.")
        if active_break(db, int(entry["id"])):
            raise ValueError("A break is already active.")
        cursor = db.execute(
            "INSERT INTO breaks(entry_id, started_at) VALUES (?, ?)", (entry["id"], now)
        )
        audit(db, user_id, "break_start", "break", cursor.lastrowid, {})
        message = "Break started."
    elif action == "break-end":
        if not entry:
            raise ValueError("There is no active shift.")
        current_break = active_break(db, int(entry["id"]))
        if not current_break:
            raise ValueError("There is no active break.")
        db.execute("UPDATE breaks SET ended_at = ? WHERE id = ?", (now, current_break["id"]))
        audit(db, user_id, "break_end", "break", int(current_break["id"]), {})
        message = "Break ended."
    else:
        raise ValueError("Unknown punch action.")
    db.commit()
    return message


def seconds_worked(clock_in: str, clock_out: str | None, breaks: list[sqlite3.Row]) -> int:
    start = datetime.fromisoformat(clock_in)
    end = datetime.fromisoformat(clock_out) if clock_out else datetime.now(UTC)
    duration = (end - start).total_seconds()
    for item in breaks:
        break_start = datetime.fromisoformat(str(item["started_at"]))
        break_end = datetime.fromisoformat(str(item["ended_at"])) if item["ended_at"] else end
        duration -= max(0, (break_end - break_start).total_seconds())
    return max(0, int(duration))
