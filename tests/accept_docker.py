"""Exercise the documented Docker image with disposable synthetic data only."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

HTTP_CHECK = r"""
import csv, http.cookiejar, io, json, re, urllib.parse, urllib.request
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
base = "http://127.0.0.1:8080"
page = client.open(base + "/login", timeout=5).read().decode()
token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
body = urllib.parse.urlencode({"csrf_token": token, "email": "docker@example.test", "password": "synthetic-long-password"}).encode()
assert client.open(base + "/login", data=body, timeout=5).status == 200
for _ in range(20):
    assert client.open(base + "/admin", timeout=5).status == 200
rows = list(csv.reader(io.StringIO(client.open(base + "/admin/export.csv", timeout=5).read().decode())))
assert rows == [["employee_code","name","clock_in_utc","clock_out_utc","worked_seconds","source"]]
assert json.load(client.open(base + "/health", timeout=5)) == {"status":"ok"}
print(json.dumps({"passed":True,"checks":["real Gunicorn HTTP health","console bootstrap","CSRF login","20 authenticated multi-worker requests","administrator CSV"]}))
"""


def run(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), check=True, text=True, capture_output=capture, timeout=600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="forge-plainpunch-acceptance:1.1.2")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    run("docker", "build", "--tag", args.image, str(repository))
    container = run(
        "docker",
        "run",
        "--detach",
        "--rm",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/data:uid=10001,gid=10001,mode=0700",
        "--env",
        "PLAINPUNCH_DATABASE=/data/plainpunch.sqlite3",
        "--env",
        "PLAINPUNCH_SECRET_KEY=isolated-synthetic-container-secret",
        args.image,
        capture=True,
    ).stdout.strip()
    try:
        ready = False
        for _ in range(40):
            probe = subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "python",
                    "-c",
                    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=2)",
                ],
                capture_output=True,
                timeout=5,
            )
            if probe.returncode == 0:
                ready = True
                break
            time.sleep(0.25)
        if not ready:
            raise RuntimeError("Docker health did not become ready")
        run(
            "docker",
            "exec",
            container,
            "plainpunch",
            "create-admin",
            "--name",
            "Synthetic Admin",
            "--email",
            "docker@example.test",
            "--employee-code",
            "DOCKER",
            "--password",
            "synthetic-long-password",
            "--pin",
            "1234",
        )
        check = run("docker", "exec", container, "python", "-c", HTTP_CHECK, capture=True)
        result = json.loads(check.stdout)
        result["image"] = args.image
        result["image_id"] = run(
            "docker", "image", "inspect", "--format", "{{.Id}}", args.image, capture=True
        ).stdout.strip()
        result["isolation"] = (
            "No host ports, no network, disposable tmpfs SQLite data; no production paths"
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        # Stop only the disposable container whose ID was returned by this invocation.
        subprocess.run(["docker", "logs", container], check=False, timeout=30)
        subprocess.run(["docker", "stop", container], check=False, timeout=30)


if __name__ == "__main__":
    main()
