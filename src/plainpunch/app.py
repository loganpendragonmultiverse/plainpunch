"""Flask application factory and HTTP routes."""

from __future__ import annotations

import csv
import io
import os
import secrets
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask.typing import ResponseReturnValue
from werkzeug.security import check_password_hash, generate_password_hash

from plainpunch import db as database
from plainpunch.domain import active_break, active_entry, audit, punch, seconds_worked, utc_now

View = TypeVar("View", bound=Callable[..., Any])


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    default_database = str(Path(app.instance_path) / "plainpunch.sqlite3")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("PLAINPUNCH_SECRET_KEY", secrets.token_hex(32)),
        DATABASE=os.environ.get("PLAINPUNCH_DATABASE", default_database),
        TIMEZONE=os.environ.get("PLAINPUNCH_TIMEZONE", "UTC"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("PLAINPUNCH_SECURE_COOKIES", "0") == "1",
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    database.init_db(app.config["DATABASE"])
    app.teardown_appcontext(database.close_db)
    register_security(app)
    register_context(app)
    register_routes(app)
    return app


def register_security(app: Flask) -> None:
    @app.before_request
    def load_user_and_check_csrf() -> None:
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            g.user = database.query_one(
                "SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)
            )
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            expected = session.get("csrf_token")
            if not expected or not supplied or not secrets.compare_digest(expected, supplied):
                abort(400, "Invalid CSRF token")

    @app.context_processor
    def csrf_context() -> dict[str, Any]:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return {"csrf_token": session["csrf_token"]}


def register_context(app: Flask) -> None:
    @app.template_filter("localtime")
    def localtime(value: str | None) -> str:
        if not value:
            return "—"
        converted = datetime.fromisoformat(value).astimezone(ZoneInfo(app.config["TIMEZONE"]))
        return converted.strftime("%b %d, %Y %I:%M %p")

    @app.template_filter("duration")
    def duration(seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes:02d}m"


def login_required(view: View) -> View:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return cast(View, wrapped)


def admin_required(view: View) -> View:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if g.user is None or not g.user["is_admin"]:
            abort(403)
        return view(*args, **kwargs)

    return cast(View, wrapped)


def register_routes(app: Flask) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:
        database.query_one("SELECT 1")
        return {"status": "ok"}

    @app.route("/login", methods=["GET", "POST"])
    def login() -> ResponseReturnValue:
        if request.method == "POST":
            user = database.query_one(
                "SELECT * FROM users WHERE email = ? AND is_active = 1",
                (request.form["email"].strip(),),
            )
            if user and check_password_hash(user["password_hash"], request.form["password"]):
                session.clear()
                session["user_id"] = user["id"]
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for("dashboard"))
            flash("Email or password was not recognized.", "error")
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout() -> ResponseReturnValue:
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def dashboard() -> str:
        entry = active_entry(database.get_db(), int(g.user["id"]))
        current_break = active_break(database.get_db(), int(entry["id"])) if entry else None
        rows = database.query_all(
            "SELECT * FROM time_entries WHERE user_id = ? ORDER BY clock_in DESC LIMIT 30",
            (g.user["id"],),
        )
        entries = [entry_view(row) for row in rows]
        return render_template(
            "dashboard.html", active=entry, active_break=current_break, entries=entries
        )

    @app.post("/punch/<action>")
    @login_required
    def do_punch(action: str) -> ResponseReturnValue:
        try:
            flash(punch(database.get_db(), int(g.user["id"]), action), "success")
        except ValueError as error:
            flash(str(error), "error")
        return redirect(url_for("dashboard"))

    @app.route("/kiosk", methods=["GET", "POST"])
    def kiosk() -> str:
        if request.method == "POST":
            user = database.query_one(
                "SELECT * FROM users WHERE employee_code = ? AND is_active = 1",
                (request.form["employee_code"].strip(),),
            )
            if not user or not check_password_hash(user["pin_hash"], request.form["pin"]):
                flash("Employee code or PIN was not recognized.", "error")
            else:
                try:
                    flash(
                        punch(database.get_db(), int(user["id"]), request.form["action"], "kiosk"),
                        "success",
                    )
                except ValueError as error:
                    flash(str(error), "error")
        return render_template("kiosk.html")

    @app.route("/corrections/new/<int:entry_id>", methods=["GET", "POST"])
    @login_required
    def request_correction(entry_id: int) -> ResponseReturnValue:
        entry = database.query_one(
            "SELECT * FROM time_entries WHERE id = ? AND user_id = ?", (entry_id, g.user["id"])
        )
        if entry is None:
            abort(404)
        if request.method == "POST":
            proposed_in = parse_local(request.form["clock_in"], app.config["TIMEZONE"])
            proposed_out = (
                parse_local(request.form["clock_out"], app.config["TIMEZONE"])
                if request.form["clock_out"]
                else None
            )
            if proposed_out and proposed_out <= proposed_in:
                flash("Clock-out must be later than clock-in.", "error")
            elif not request.form["reason"].strip():
                flash("Explain why the correction is needed.", "error")
            else:
                db = database.get_db()
                cursor = db.execute(
                    "INSERT INTO correction_requests(entry_id, user_id, proposed_clock_in, proposed_clock_out, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        entry_id,
                        g.user["id"],
                        proposed_in,
                        proposed_out,
                        request.form["reason"].strip(),
                        utc_now(),
                    ),
                )
                audit(
                    db,
                    int(g.user["id"]),
                    "correction_requested",
                    "correction_request",
                    cursor.lastrowid,
                    {"entry_id": entry_id},
                )
                db.commit()
                flash("Correction submitted for review.", "success")
                return redirect(url_for("dashboard"))
        return render_template("correction.html", entry=entry, local_input=local_input)

    @app.get("/admin")
    @admin_required
    def admin() -> str:
        users = database.query_all("SELECT * FROM users ORDER BY name")
        corrections = database.query_all(
            "SELECT c.*, u.name FROM correction_requests c JOIN users u ON u.id = c.user_id WHERE c.status = 'pending' ORDER BY c.created_at"
        )
        audit_rows = database.query_all(
            "SELECT a.*, u.name AS actor_name FROM audit_events a LEFT JOIN users u ON u.id = a.actor_id ORDER BY a.created_at DESC LIMIT 100"
        )
        return render_template(
            "admin.html", users=users, corrections=corrections, audit_rows=audit_rows
        )

    @app.post("/admin/users")
    @admin_required
    def create_user() -> ResponseReturnValue:
        db = database.get_db()
        try:
            cursor = db.execute(
                "INSERT INTO users(name, email, employee_code, password_hash, pin_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    request.form["name"].strip(),
                    request.form["email"].strip(),
                    request.form["employee_code"].strip(),
                    generate_password_hash(request.form["password"], method="scrypt"),
                    generate_password_hash(request.form["pin"], method="scrypt"),
                    int(request.form.get("is_admin") == "1"),
                    utc_now(),
                ),
            )
            audit(
                db,
                int(g.user["id"]),
                "user_created",
                "user",
                cursor.lastrowid,
                {"email": request.form["email"].strip()},
            )
            db.commit()
            flash("User created.", "success")
        except Exception as error:
            db.rollback()
            if "UNIQUE constraint" in str(error):
                flash("That email or employee code is already in use.", "error")
            else:
                raise
        return redirect(url_for("admin"))

    @app.post("/admin/corrections/<int:correction_id>/<decision>")
    @admin_required
    def review_correction(correction_id: int, decision: str) -> ResponseReturnValue:
        if decision not in {"approved", "rejected"}:
            abort(404)
        db = database.get_db()
        correction = db.execute(
            "SELECT * FROM correction_requests WHERE id = ? AND status = 'pending'",
            (correction_id,),
        ).fetchone()
        if correction is None:
            abort(404)
        if decision == "approved":
            original = db.execute(
                "SELECT clock_in, clock_out FROM time_entries WHERE id = ?",
                (correction["entry_id"],),
            ).fetchone()
            db.execute(
                "UPDATE time_entries SET clock_in = ?, clock_out = ? WHERE id = ?",
                (
                    correction["proposed_clock_in"],
                    correction["proposed_clock_out"],
                    correction["entry_id"],
                ),
            )
            detail = {
                "entry_id": correction["entry_id"],
                "before": dict(original),
                "after": {
                    "clock_in": correction["proposed_clock_in"],
                    "clock_out": correction["proposed_clock_out"],
                },
            }
        else:
            detail = {"entry_id": correction["entry_id"]}
        db.execute(
            "UPDATE correction_requests SET status = ?, reviewer_id = ?, reviewer_note = ?, reviewed_at = ? WHERE id = ?",
            (
                decision,
                g.user["id"],
                request.form.get("reviewer_note", "").strip(),
                utc_now(),
                correction_id,
            ),
        )
        audit(
            db,
            int(g.user["id"]),
            f"correction_{decision}",
            "correction_request",
            correction_id,
            detail,
        )
        db.commit()
        flash(f"Correction {decision}.", "success")
        return redirect(url_for("admin"))

    @app.get("/admin/export.csv")
    @admin_required
    def export_csv() -> ResponseReturnValue:
        rows = database.query_all(
            "SELECT e.*, u.name, u.employee_code FROM time_entries e JOIN users u ON u.id = e.user_id ORDER BY e.clock_in"
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            ["employee_code", "name", "clock_in_utc", "clock_out_utc", "worked_seconds", "source"]
        )
        for row in rows:
            breaks = database.query_all("SELECT * FROM breaks WHERE entry_id = ?", (row["id"],))
            writer.writerow(
                [
                    row["employee_code"],
                    row["name"],
                    row["clock_in"],
                    row["clock_out"] or "",
                    seconds_worked(row["clock_in"], row["clock_out"], breaks),
                    row["source"],
                ]
            )
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=plainpunch-export.csv"},
        )

    def entry_view(row: Any) -> dict[str, Any]:
        breaks = database.query_all("SELECT * FROM breaks WHERE entry_id = ?", (row["id"],))
        return {
            **dict(row),
            "worked_seconds": seconds_worked(row["clock_in"], row["clock_out"], breaks),
        }


def parse_local(value: str, timezone: str) -> str:
    parsed = datetime.fromisoformat(value).replace(tzinfo=ZoneInfo(timezone))
    return parsed.astimezone(ZoneInfo("UTC")).isoformat(timespec="seconds")


def local_input(value: str | None, timezone: str = "UTC") -> str:
    if not value:
        return ""
    return datetime.fromisoformat(value).astimezone(ZoneInfo(timezone)).strftime("%Y-%m-%dT%H:%M")
