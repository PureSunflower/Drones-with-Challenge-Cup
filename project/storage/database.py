import csv
import json
import sqlite3
from pathlib import Path
from uuid import uuid4


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path.resolve()
        self.connection = sqlite3.connect(self.path)
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (
                run_id TEXT PRIMARY KEY, started_utc TEXT DEFAULT CURRENT_TIMESTAMP,
                scenario TEXT NOT NULL, origin TEXT NOT NULL, result TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES experiments(run_id),
                sim_time REAL NOT NULL, event TEXT NOT NULL, node_id TEXT NOT NULL,
                details TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_by_run ON events(run_id, id);
        """)

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            self.connection.__exit__(exc_type, exc, traceback)
        finally:
            self.connection.close()

    def start(self, scenario: str) -> str:
        run_id = uuid4().hex
        self.connection.execute("INSERT INTO experiments(run_id, scenario, origin) VALUES (?, ?, 'SIMULATION')",
                                (run_id, scenario))
        self.connection.commit()
        return run_id

    def event(self, run_id: str, now: float, event: str, node_id: str, details: dict) -> None:
        self.connection.execute(
            "INSERT INTO events(run_id, sim_time, event, node_id, details) VALUES (?, ?, ?, ?, ?)",
            (run_id, now, event, node_id, json.dumps(details, ensure_ascii=False)),
        )

    def finish(self, run_id: str, result: dict) -> None:
        self.connection.execute("UPDATE experiments SET result = ? WHERE run_id = ?",
                                (json.dumps(result, ensure_ascii=False), run_id))
        self.connection.commit()

    def export(self, path: Path, run_id: str) -> None:
        if path.resolve() == self.path or (path.exists() and path.samefile(self.path)):
            raise ValueError("CSV destination is the experiment database")
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.connection.execute("""
            SELECT e.run_id, x.scenario, x.origin, x.started_utc, e.sim_time, e.event, e.node_id, e.details
            FROM events e JOIN experiments x ON x.run_id = e.run_id
            WHERE e.run_id = ? ORDER BY e.id
        """, (run_id,))
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(column[0] for column in rows.description)
            writer.writerows(rows)
