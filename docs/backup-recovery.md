# Backup and recovery

The SQLite database holds accounts, credential hashes, shifts, breaks, corrections, audit events and session revisions. CSV files cannot restore these records.

Set `PLAINPUNCH_DATABASE` to an absolute path, and use the same environment for the CLI and web process. Docker already supplies `/data/plainpunch.sqlite3`. Keep your stable private secret and deployment configuration separately protected.

## Existing local installations before 1.1.2

The bootstrap CLI formerly defaulted to `./instance/plainpunch.sqlite3`, while Flask could use a different instance directory, particularly inside an installed virtual environment. Version 1.1.2 makes the CLI follow the web app's existing default; it does not move, merge or delete databases. Before upgrading, identify the authoritative database and set its absolute path explicitly. If bootstrap created an unused database, do not overwrite an active database with it. Preserve any records until you have reconciled them.

## Create a consistent snapshot

Use Python's SQLite online backup API while the service is running, or stop every writer before copying the file. Do not copy an active database file alone, especially when journal/WAL files exist. For a snapshot into a new protected file:

```python
import sqlite3
from pathlib import Path

source_path = Path("/absolute/path/plainpunch.sqlite3")
backup_path = Path("/absolute/protected/path/new-snapshot.sqlite3")
# Fail if the source is missing or the destination already exists.
with backup_path.open("xb"):
    pass
with sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True) as source:
    with sqlite3.connect(backup_path) as target:
        source.backup(target)
        assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
```

Restrict access to snapshots as tightly as the live database. Test your retention and recovery procedure; the application does not schedule backups.

## Rehearse a restore without touching production

1. Restore the snapshot to a new isolated path. Never overwrite the live database during a rehearsal.
2. Set `PLAINPUNCH_DATABASE` to that path and start a separate local instance bound to loopback, with a distinct test secret. A distinct secret prevents production session cookies from being accepted in the rehearsal.
3. Verify `/health`, administrator sign-in, employee history, break totals, correction decisions and their before/after audit evidence. Compare both CSV exports with known synthetic results.
4. For a real recovery, stop every writer before changing the configured database. Preserve the prior database until the recovered instance is verified.

Restoring a snapshot also restores credentials and session revisions to the snapshot date. Use a new private session secret on an actual rollback to invalidate previously issued cookies, and review access changes made since the snapshot. Kiosk PINs are stored credentials and are not revoked by changing the session secret.

The automated rehearsal uses only synthetic data and an isolated SQLite copy. It does not establish an operator's backup storage, retention, reverse proxy or production recovery process.
