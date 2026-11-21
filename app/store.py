import json
import sqlite3
from contextlib import closing, contextmanager

from app.errors import ReviewError
from app.manifest import canonical


class RunStore:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as connection, connection:
            yield connection

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS wafer_runs (
                    run_id TEXT PRIMARY KEY,
                    manifest TEXT NOT NULL,
                    snapshot TEXT NOT NULL,
                    pinned TEXT NOT NULL
                )
            """)

    def put(self, manifest, snapshot, pinned):
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO wafer_runs VALUES (?, ?, ?, ?) ON CONFLICT(run_id) DO NOTHING",
                (manifest["run_id"], canonical(manifest), canonical(snapshot), canonical(pinned)),
            )
            created = cursor.rowcount == 1
            row = connection.execute("SELECT manifest FROM wafer_runs WHERE run_id = ?",
                                     (manifest["run_id"],)).fetchone()
        return json.loads(row[0]), created

    def get(self, run_id):
        with self.connect() as connection:
            row = connection.execute("SELECT manifest, snapshot, pinned FROM wafer_runs WHERE run_id = ?",
                                     (run_id,)).fetchone()
        if row is None:
            raise ReviewError("RUN_NOT_FOUND", "图批未找到", 404)
        return tuple(json.loads(part) for part in row)

    def list(self):
        with self.connect() as connection:
            rows = connection.execute("SELECT manifest FROM wafer_runs ORDER BY rowid DESC").fetchall()
        return [json.loads(row[0]) for row in rows]
