from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from communication.network_simulator import NetworkSettings
from dashboard.session import Session
from hardware.serial_manager import SerialManager
from storage.database import Database


class Worker(QObject):
    snapshot = Signal(dict)
    notice = Signal(str)
    error = Signal(str)
    ports = Signal(list)
    runs = Signal(list)
    finished = Signal()

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.db = None
        self.session = None
        self.timer = None

    @Slot()
    def initialize(self) -> None:
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.tick)
        try:
            self.db = Database(self.db_path)
            self.list_runs()
        except Exception as exc:
            self.error.emit(f"数据库初始化失败：{exc}")

    def list_runs(self) -> None:
        rows = self.db.connection.execute(
            "SELECT run_id, scenario, started_utc FROM experiments ORDER BY rowid DESC"
        )
        self.runs.emit(list(rows))

    @Slot()
    def tick(self) -> None:
        try:
            self.session.tick()
            if self.session.sim.step_number % 4 == 0:
                self.db.connection.commit()
            self.snapshot.emit(self.session.snapshot())
        except Exception as exc:
            self.timer.stop()
            self.error.emit(f"仿真暂停：{exc}")

    @Slot(str, object)
    def command(self, name: str, args: object) -> None:
        try:
            self.dispatch(name, args)
        except Exception as exc:
            self.error.emit(f"操作失败：{exc}")

    def dispatch(self, name: str, args: object) -> None:
        if name == "scan":
            self.ports.emit(SerialManager.scan())
            return
        if self.db is None:
            raise RuntimeError("实验数据库不可用")
        if name == "start":
            if self.session:
                self.session.finish()
            self.session = Session(self.db, args)
            self.timer.start()
            self.list_runs()
        elif name == "export":
            path, run_id = args
            if self.session and run_id == self.session.run_id:
                self.session.export(Path(path), run_id)
            else:
                self.db.export(Path(path), run_id)
            self.notice.emit(f"已导出 {path}")
        elif self.session is None:
            raise ValueError("请先启动仿真")
        else:
            session = self.session
            sim = session.sim
            if name == "pause":
                if self.timer.isActive():
                    self.timer.stop()
                    session.save()
                    self.notice.emit("仿真已暂停")
                else:
                    self.timer.start()
                    self.notice.emit("仿真已继续")
            elif name == "power":
                sim.power(*args)
            elif name == "publish":
                options = dict(args)
                duration = options.pop("duration")
                sim.publish("006", deadline=sim.now + duration if duration else None, **options)
            elif name == "cancel":
                sim.cancel("006", args)
            elif name == "partition":
                sim.partition(set(args))
            elif name == "heal":
                sim.heal()
            elif name == "network":
                sim.configure_network(NetworkSettings(**args))
            elif name == "save":
                session.save()
                self.notice.emit("实验已保存")
            self.snapshot.emit(session.snapshot())

    @Slot()
    def shutdown(self) -> None:
        try:
            if self.timer:
                self.timer.stop()
            if self.db:
                with self.db:
                    if self.session:
                        self.session.finish()
        except Exception as exc:
            self.error.emit(f"关闭时保存失败：{exc}")
        finally:
            self.finished.emit()
