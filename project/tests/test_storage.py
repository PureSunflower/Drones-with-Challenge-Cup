import csv
import json
import sqlite3
import subprocess
import sys

from config.settings import ROOT


def test_cli_persists_and_exports(tmp_path):
    db, log, exported = (tmp_path / filename for filename in ("run.db", "run.log", "run.csv"))
    completed = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--scenario", "single-outage",
         "--db", str(db), "--log", str(log), "--csv", str(exported)],
        check=True, capture_output=True, text=True,
    )
    result = json.loads(completed.stdout)
    connection = sqlite3.connect(db)
    try:
        row = connection.execute("SELECT origin, result FROM experiments WHERE run_id = ?",
                                 (result["run_id"],)).fetchone()
        assert row[0] == "SIMULATION"
        assert json.loads(row[1])["nodes"]["002"]["executing"] == ["survey"]
    finally:
        connection.close()
    with exported.open(encoding="utf-8-sig", newline="") as stream:
        events = list(csv.DictReader(stream))
    assert all(event["origin"] == "SIMULATION" for event in events)
    assert {"task_reassigned", "task_outcome_unknown", "scenario_finished"} <= {
        event["event"] for event in events
    }
    assert "SIMULATION" in log.read_text(encoding="utf-8")
