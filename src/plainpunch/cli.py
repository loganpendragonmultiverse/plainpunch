"""Command-line administration for PlainPunch."""

from __future__ import annotations

import argparse
import os
import sys
from getpass import getpass

from werkzeug.security import generate_password_hash

from plainpunch.db import connect, init_db
from plainpunch.domain import audit, utc_now


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="plainpunch")
    result.add_argument(
        "--database",
        default=os.environ.get("PLAINPUNCH_DATABASE", "instance/plainpunch.sqlite3"),
        help="SQLite database path",
    )
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Create or upgrade the database schema")
    admin = commands.add_parser("create-admin", help="Create the first administrator")
    admin.add_argument("--name", required=True)
    admin.add_argument("--email", required=True)
    admin.add_argument("--employee-code", required=True)
    admin.add_argument("--password")
    admin.add_argument("--pin")
    return result


def main(arguments: list[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    init_db(options.database)
    if options.command == "init-db":
        print(f"Initialized {options.database}")
        return 0
    password = options.password or getpass("Password: ")
    pin = options.pin or getpass("Kiosk PIN: ")
    if len(password) < 12:
        print("Password must be at least 12 characters.", file=sys.stderr)
        return 2
    if not (4 <= len(pin) <= 12 and pin.isdigit()):
        print("PIN must contain 4 to 12 digits.", file=sys.stderr)
        return 2
    db = connect(options.database)
    try:
        cursor = db.execute(
            "INSERT INTO users(name, email, employee_code, password_hash, pin_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (
                options.name.strip(),
                options.email.strip(),
                options.employee_code.strip(),
                generate_password_hash(password, method="scrypt"),
                generate_password_hash(pin, method="scrypt"),
                utc_now(),
            ),
        )
        audit(
            db,
            None,
            "bootstrap_admin_created",
            "user",
            cursor.lastrowid,
            {"email": options.email.strip()},
        )
        db.commit()
    finally:
        db.close()
    print(f"Created administrator {options.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
