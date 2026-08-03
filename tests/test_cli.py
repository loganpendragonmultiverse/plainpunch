from plainpunch.cli import main
from plainpunch.db import connect


def test_cli_initializes_and_creates_admin(tmp_path):
    path = str(tmp_path / "clock.sqlite3")
    assert main(["--database", path, "init-db"]) == 0
    assert (
        main(
            [
                "--database",
                path,
                "create-admin",
                "--name",
                "Boss",
                "--email",
                "boss@example.test",
                "--employee-code",
                "B1",
                "--password",
                "long-enough-password",
                "--pin",
                "1234",
            ]
        )
        == 0
    )
    db = connect(path)
    assert db.execute("SELECT is_admin FROM users").fetchone()[0] == 1


def test_cli_rejects_weak_credentials(tmp_path):
    path = str(tmp_path / "clock.sqlite3")
    base = [
        "--database",
        path,
        "create-admin",
        "--name",
        "Boss",
        "--email",
        "boss@example.test",
        "--employee-code",
        "B1",
    ]
    assert main(base + ["--password", "short", "--pin", "1234"]) == 2
    assert main(base + ["--password", "long-enough-password", "--pin", "abc"]) == 2
