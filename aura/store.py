"""Local SQLite foundation. Production PostgreSQL migration is a release gate."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES (1);
CREATE TABLE IF NOT EXISTS records (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL,
 payload TEXT NOT NULL, created REAL NOT NULL);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
 BEGIN SELECT RAISE(ABORT, 'append only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
 BEGIN SELECT RAISE(ABORT, 'append only'); END;
CREATE TABLE IF NOT EXISTS controls (
 name TEXT PRIMARY KEY, value INTEGER NOT NULL CHECK(value IN (0,1)));
INSERT OR IGNORE INTO controls VALUES ('kill_switch', 1);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, dedupe_key TEXT UNIQUE NOT NULL, topic TEXT NOT NULL,
 payload TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 available REAL NOT NULL, lease_until REAL, lease_token TEXT);
"""


class Store:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        for environment in ("historical", "virtual", "demo"):
            with self.connect(environment) as db:
                db.executescript(SCHEMA)

    @contextmanager
    def connect(self, environment="historical"):
        if environment not in {"historical", "virtual", "demo"}:
            raise ValueError("Invalid or disabled memory environment")
        db = sqlite3.connect(self.directory / f"{environment}.db", timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def record(self, environment, kind, payload):
        identifier = str(uuid.uuid4())
        with self.connect(environment) as db:
            db.execute(
                "INSERT INTO records VALUES (?,?,?,?)",
                (identifier, kind, json.dumps(payload, allow_nan=False), time.time()),
            )
        return identifier

    def records(self, environment, limit=100):
        with self.connect(environment) as db:
            rows = db.execute("SELECT * FROM records ORDER BY created DESC LIMIT ?", (limit,))
            return [dict(r) | {"payload": json.loads(r["payload"])} for r in rows]

    def audit(self, actor, action, payload):
        with self.connect() as db:
            db.execute(
                "INSERT INTO audit(actor,action,payload,created) VALUES (?,?,?,?)",
                (actor, action, json.dumps(payload, allow_nan=False), time.time()),
            )

    def set_kill(self, enabled, actor="local-operator"):
        with self.connect() as db:
            db.execute("UPDATE controls SET value=? WHERE name='kill_switch'", (int(enabled),))
            db.execute(
                "INSERT INTO audit(actor,action,payload,created) VALUES (?,?,?,?)",
                (actor, "kill_switch", json.dumps({"enabled": enabled}), time.time()),
            )

    def killed(self):
        with self.connect() as db:
            row = db.execute("SELECT value FROM controls WHERE name='kill_switch'").fetchone()
            if row is None:
                raise RuntimeError("Missing safety control")
            return bool(row[0])

    def enqueue(self, key, topic, payload):
        encoded = json.dumps(payload, sort_keys=True, allow_nan=False)
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO jobs VALUES (?,?,?,?,?,0,?,NULL,NULL)",
                (str(uuid.uuid4()), key, topic, encoded, "pending", time.time()),
            )
            row = db.execute("SELECT * FROM jobs WHERE dedupe_key=?", (key,)).fetchone()
            if row["topic"] != topic or row["payload"] != encoded:
                raise ValueError("Idempotency key reused with different payload")
            return row["id"]

    def claim(self, now=None, lease_seconds=30):
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT * FROM jobs WHERE
              (state='pending' AND available<=?) OR (state='running' AND lease_until<=?)
              ORDER BY available LIMIT 1""",
                (now, now),
            ).fetchone()
            if row is None:
                return None
            token = str(uuid.uuid4())
            db.execute(
                "UPDATE jobs SET state='running',attempts=attempts+1,"
                "lease_until=?,lease_token=? WHERE id=?",
                (now + lease_seconds, token, row["id"]),
            )
            return dict(row) | {
                "payload": json.loads(row["payload"]),
                "attempts": row["attempts"] + 1,
                "lease_token": token,
            }

    def finish(self, identifier, lease_token, success=True, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE id=? AND state='running' AND "
                "lease_token=? AND lease_until>?",
                (identifier, lease_token, now),
            ).fetchone()
            if row is None:
                raise ValueError("Expired or stale worker lease")
            state = "done" if success else ("dead" if row["attempts"] >= 3 else "pending")
            db.execute(
                "UPDATE jobs SET state=?,available=?,lease_until=NULL,lease_token=NULL WHERE id=?",
                (state, now + 2 ** row["attempts"], identifier),
            )
