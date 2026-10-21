"""Install a wheel outside the checkout and verify its documented bootstrap path."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import venv
from pathlib import Path

CHECK = r"""
import importlib.metadata
import importlib.resources
import json
from pathlib import Path
from plainpunch import create_app
from plainpunch.cli import parser
from plainpunch.db import connect

app = create_app()
assert Path(parser().parse_args(["init-db"]).database).resolve() == Path(app.config["DATABASE"]).resolve()
db = connect(app.config["DATABASE"])
assert db.execute("SELECT email FROM users").fetchone()[0] == "setup@example.test"
assert db.execute("SELECT count(*) FROM audit_events WHERE action='bootstrap_admin_created'").fetchone()[0] == 1
db.close()
client = app.test_client()
assert client.get("/health").json == {"status": "ok"}
assert client.post("/login", data={"email":"setup@example.test","password":"synthetic-long-password"}).status_code == 400
client.get("/login")
with client.session_transaction() as session:
    token = session["csrf_token"]
response = client.post("/login", data={"csrf_token":token,"email":"setup@example.test","password":"synthetic-long-password"})
assert response.status_code == 302
assert "HttpOnly" in response.headers["Set-Cookie"]
assert "SameSite=Lax" in response.headers["Set-Cookie"]
assert client.get("/admin").status_code == 200
assert client.get("/admin/export.csv").status_code == 200
client.get("/admin")
with client.session_transaction() as session:
    token = session["csrf_token"]
assert client.post("/admin/users/1/revoke-sessions", data={"csrf_token":token}).status_code == 302
assert client.get("/admin/export.csv").status_code == 403
docs = importlib.resources.files("plainpunch").joinpath("docs")
assert docs.joinpath("docs", "backup-recovery.md").is_file()
assert docs.joinpath("docs", "deployment-controls.md").is_file()
print(json.dumps({"passed":True,"version":importlib.metadata.version("plainpunch"),"checks":["installed console bootstrap","CLI/web default database parity","health","CSRF","login","cookie attributes","CSV access","session revocation","packaged recovery/deployment guides"]}))
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    report = args.report.resolve()
    with tempfile.TemporaryDirectory(prefix="plainpunch-installed-") as name:
        root = Path(name)
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        scripts = root / "venv" / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        cli = scripts / ("plainpunch.exe" if os.name == "nt" else "plainpunch")
        subprocess.run([str(python), "-m", "pip", "install", str(wheel)], check=True, timeout=240)
        env = dict(os.environ)
        env.pop("PLAINPUNCH_DATABASE", None)
        env.pop("PYTHONPATH", None)
        env["PLAINPUNCH_SECRET_KEY"] = "isolated-synthetic-acceptance-key"
        env["PLAINPUNCH_SECURE_COOKIES"] = "0"
        subprocess.run(
            [
                str(cli),
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
            ],
            cwd=root,
            env=env,
            check=True,
            timeout=60,
        )
        completed = subprocess.run(
            [str(python), "-c", CHECK],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        result = json.loads(completed.stdout)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))


if __name__ == "__main__":
    main()
