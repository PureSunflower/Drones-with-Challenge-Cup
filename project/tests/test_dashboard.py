import csv
import os
import time

from PySide6.QtWidgets import QApplication

from dashboard.main_window import MainWindow
from dashboard.session import Session
from storage.database import Database


def advance(session, seconds):
    for _ in range(seconds * 4):
        session.tick()


def test_live_outage_metrics_and_export(tmp_path):
    with Database(tmp_path / "runs.db") as db:
        session = Session(db, "single-outage")
        advance(session, 25)
        result = session.snapshot()
        assert result["nodes"]["002"]["task"] == "survey"
        assert result["metrics"]["detection"]
        assert result["metrics"]["reassignment"]
        assert result["metrics"]["loss_rate"] == 0
        assert min(count for _, count in result["history"]) == 5
        path = tmp_path / "run.csv"
        session.export(path)
        with path.open(encoding="utf-8-sig", newline="") as stream:
            kinds = {event["event"] for event in csv.DictReader(stream)}
        assert {"task_reassigned", "delivery_attempt", "power_off"} <= kinds


def test_cancel_preserves_partition_observability(tmp_path):
    with Database(tmp_path / "runs.db") as db:
        session = Session(db, "manual")
        sim = session.sim
        sim.publish("006", "a", (0, 0), frozenset({"COMM"}))
        advance(session, 7)
        sim.partition({"001", "002", "003"})
        sim.cancel("006", "a")
        advance(session, 1)
        views = session.snapshot()["tasks"]["a"]["views"]
        assert views["006"]["status"] == "CANCELLED"
        assert views["001"]["status"] == "EXECUTING"
        sim.heal()
        advance(session, 2)
        views = session.snapshot()["tasks"]["a"]["views"]
        assert all(view["status"] == "CANCELLED" for view in views.values())


def test_deadline_stops_execution(tmp_path):
    with Database(tmp_path / "runs.db") as db:
        session = Session(db, "manual")
        session.sim.publish("006", "a", (0, 0), frozenset({"COMM"}), deadline=8, priority=5)
        advance(session, 7)
        assert session.sim.nodes["001"].current_task == "a"
        advance(session, 2)
        task = session.snapshot()["tasks"]["a"]
        assert task["definition"]["priority"] == 5
        assert all(view["status"] == "EXPIRED" for view in task["views"].values())


def test_window_drives_live_worker_and_closes(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    window = MainWindow(tmp_path / "gui.db")

    def wait(predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert predicate()

    window.show()
    try:
        window.send("start", "manual")
        wait(lambda: window.nodes.rowCount() == 6)
        window.form.task_id.setText("from-gui")
        window.form.publish.click()
        wait(lambda: window.tasks.rowCount() == 1)
        window.nodes.selectRow(0)
        window.power(False)
        wait(lambda: window.snapshot["nodes"]["001"]["actual"] == "OFFLINE")
        window.power(True)
        wait(lambda: window.snapshot["nodes"]["001"]["actual"] == "ONLINE")
        pixmap = window.grab()
        assert not pixmap.isNull()
    finally:
        window.close()
        wait(lambda: not window.thread.isRunning())
