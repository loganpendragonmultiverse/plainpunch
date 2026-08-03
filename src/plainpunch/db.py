"""SQLite access and schema management."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

from flask import current_app, g

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  employee_code TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  pin_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS time_entries (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  clock_in TEXT NOT NULL,
  clock_out TEXT,
  source TEXT NOT NULL CHECK(source IN ('web', 'kiosk'))
);
CREATE TABLE IF NOT EXISTS breaks (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES time_entries(id),
  started_at TEXT NOT NULL,
  ended_at TEXT
);
CREATE TABLE IF NOT EXISTS correction_requests (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES time_entries(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  proposed_clock_in TEXT NOT NULL,
  proposed_clock_out TEXT,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
  reviewer_id INTEGER REFERENCES users(id),
  reviewer_note TEXT,
  created_at TEXT NOT NULL,
  reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY,
  actor_id INTEGER REFERENCES users(id),
  action TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  subject_id INTEGER,
  detail_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_user_clock ON time_entries(user_id, clock_in);
CREATE INDEX IF NOT EXISTS idx_corrections_status ON correction_requests(status, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at);
"""


def connect(path: str) -> sqlite3.Connection:
    database = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys = ON")
    return database


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return cast(sqlite3.Connection, g.db)


def close_db(_error: BaseException | None = None) -> None:
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_db(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    database = connect(path)
    try:
        database.executescript(SCHEMA)
        database.commit()
    finally:
        database.close()


def query_one(sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return cast(sqlite3.Row | None, get_db().execute(sql, parameters).fetchone())


def query_all(sql: str, parameters: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return list(get_db().execute(sql, parameters).fetchall())
