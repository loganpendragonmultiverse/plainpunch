"""Explicit local-date work summaries; no wage or overtime rules."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp requires an explicit UTC offset.")
    return parsed.astimezone(UTC)


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    result: list[tuple[datetime, datetime]] = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def work_summary(
    db: sqlite3.Connection,
    start: date,
    end: date,
    timezone: str,
    group: str = "daily",
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if end < start or (end - start).days > 365:
        raise ValueError("Choose an inclusive range of at most 366 days.")
    if group not in {"daily", "weekly"}:
        raise ValueError("Choose daily or weekly grouping.")
    tz = ZoneInfo(timezone)
    as_of = now or datetime.now(UTC)
    output: list[dict[str, Any]] = []
    for user in db.execute("SELECT id,name,employee_code FROM users ORDER BY name"):
        spans: list[tuple[datetime, datetime]] = []
        for entry in db.execute("SELECT * FROM time_entries WHERE user_id=?", (user["id"],)):
            left, right = (
                instant(entry["clock_in"]),
                instant(entry["clock_out"]) if entry["clock_out"] else as_of,
            )
            cursor = left
            breaks = merge_intervals(
                [
                    (
                        max(left, instant(b["started_at"])),
                        min(right, instant(b["ended_at"]) if b["ended_at"] else right),
                    )
                    for b in db.execute("SELECT * FROM breaks WHERE entry_id=?", (entry["id"],))
                ]
            )
            for a, b in breaks:
                if a > cursor:
                    spans.append((cursor, a))
                cursor = max(cursor, b)
            if right > cursor:
                spans.append((cursor, right))
        spans = merge_intervals(spans)  # Duplicate/overlapping entries never double-count time.
        buckets: dict[str, int] = {}
        day = start
        while day <= end:
            a = datetime.combine(day, time.min, tz).astimezone(UTC)
            b = datetime.combine(day + timedelta(days=1), time.min, tz).astimezone(UTC)
            seconds = sum(max(0, int((min(y, b) - max(x, a)).total_seconds())) for x, y in spans)
            period = (
                (day - timedelta(days=day.weekday())).isoformat()
                if group == "weekly"
                else day.isoformat()
            )
            buckets[period] = buckets.get(period, 0) + seconds
            day += timedelta(days=1)
        output.extend(
            {
                "employee_code": user["employee_code"],
                "name": user["name"],
                "period": period,
                "worked_seconds": seconds,
                "hours": round(seconds / 3600, 4),
            }
            for period, seconds in buckets.items()
        )
    return output


def validate_shift(
    db: sqlite3.Connection, user_id: int, entry_id: int, start: str, end: str | None
) -> None:
    left = instant(start)
    right = instant(end) if end else datetime.max.replace(tzinfo=UTC)
    if right <= left:
        raise ValueError("Clock-out must be later than clock-in.")
    for row in db.execute(
        "SELECT id,clock_in,clock_out FROM time_entries WHERE user_id=? AND id!=?",
        (user_id, entry_id),
    ):
        a = instant(row["clock_in"])
        b = instant(row["clock_out"]) if row["clock_out"] else datetime.max.replace(tzinfo=UTC)
        if left < b and a < right:
            raise ValueError("This correction overlaps another shift; review that entry first.")


def parse_wall_time(value: str, timezone: str) -> str:
    parsed = datetime.fromisoformat(value)
    tz = ZoneInfo(timezone)
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).isoformat(timespec="seconds")
    possibilities = {
        candidate.astimezone(UTC)
        for fold in [0, 1]
        if (candidate := parsed.replace(tzinfo=tz, fold=fold))
        .astimezone(UTC)
        .astimezone(tz)
        .replace(tzinfo=None)
        == parsed
    }
    if len(possibilities) != 1:
        raise ValueError(
            "This local time is ambiguous or nonexistent at a daylight-saving transition. Supply an explicit UTC offset."
        )
    return possibilities.pop().isoformat(timespec="seconds")
