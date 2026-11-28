import json
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QDateTime, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QPlainTextEdit, QPushButton, QSplitter, QTabWidget,
                               QVBoxLayout, QWidget)

from config.settings import ROOT
from dashboard.panels import EVENTS, STATUS, TYPES, StatsPanel, TaskForm, number, rows, selected, table
from dashboard.worker import Worker

SCENARIO_NAMES = {
    "manual": "手动仿真", "normal": "正常六节点", "single-outage": "单节点失联",
    "double-outage": "双节点失联", "loss": "随机丢包", "duplicate": "消息重复",
    "delay": "消息延迟", "partition": "网络分区", "recovery": "网络恢复",
    "competition": "多节点竞争",
}


class MainWindow(QMainWindow):
    command = Signal(str, object)
    shutdown = Signal()

    def __init__(self, db_path: Path = ROOT / "data/experiments.sqlite3") -> None:
        super().__init__()
        self.setWindowTitle("空地协同上位机")
        self.resize(1440, 900)
        self.snapshot = {}
        self.closing = False
        self.closed = False
        self.running_status = "待启动"

        root = QWidget()
        layout = QVBoxLayout(root)
        self.setCentralWidget(root)
        self.header = QLabel()
        self.header.setObjectName("header")
        layout.addWidget(self.header)

        toolbar = QHBoxLayout()
        self.scenarios = QComboBox()
        for key, label in SCENARIO_NAMES.items():
            self.scenarios.addItem(label, key)
        toolbar.addWidget(self.scenarios)
        self.button(toolbar, "启动新实验", lambda: self.send("start", self.scenarios.currentData()))
        self.button(toolbar, "暂停 / 继续", lambda: self.send("pause"))
        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        workspace = QSplitter(Qt.Orientation.Horizontal)
        left, left_layout = self.panel()
        left_layout.addWidget(QLabel("节点监控 · 006 邻居视角"))
        self.nodes = table(("ID", "类型", "状态", "电量", "任务", "通信"))
        left_layout.addWidget(self.nodes)
        actions = QHBoxLayout()
        self.button(actions, "模拟掉电", lambda: self.power(False))
        self.button(actions, "恢复节点", lambda: self.power(True))
        left_layout.addLayout(actions)
        self.node_detail = self.text(max_height=180)
        left_layout.addWidget(self.node_detail)
        self.nodes.itemSelectionChanged.connect(self.show_node)
        workspace.addWidget(left)

        tabs = QTabWidget()
        overview, central = self.panel()
        central.addWidget(QLabel("模拟链路 · 各观察节点最近心跳状态"))
        self.links = table(("观察者", "001", "002", "003", "004", "005", "006"))
        central.addWidget(self.links)
        self.blocked = QLabel()
        self.blocked.setWordWrap(True)
        central.addWidget(self.blocked)
        tabs.addTab(overview, "协同总览")
        tabs.addTab(self.network_panel(), "网络实验")
        self.stats = StatsPanel()
        tabs.addTab(self.stats, "实验统计")
        self.stats.save.clicked.connect(lambda: self.send("save"))
        self.stats.export.clicked.connect(self.export)
        tabs.addTab(self.hardware_panel(), "硬件与感知")
        workspace.addWidget(tabs)

        right, right_layout = self.panel()
        right_layout.addWidget(QLabel("协同任务"))
        self.tasks = table(("ID", "类型", "优先级", "能力", "状态", "认领者", "发布/秒"))
        right_layout.addWidget(self.tasks)
        self.tasks.itemSelectionChanged.connect(self.show_task)
        self.task_detail = self.text(max_height=190)
        right_layout.addWidget(self.task_detail)
        self.button(right_layout, "取消所选任务", self.cancel)
        self.form = TaskForm()
        self.form.publish.clicked.connect(lambda: self.send("publish", self.form.values()))
        right_layout.addWidget(self.form)
        workspace.addWidget(right)
        workspace.setSizes([350, 490, 530])
        splitter.addWidget(workspace)

        log, log_layout = self.panel()
        filters = QHBoxLayout()
        filters.addWidget(QLabel("运行事件"))
        self.filter = QComboBox()
        self.filter.addItem("所有类型", "")
        for key, label in EVENTS.items():
            self.filter.addItem(label, key)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索节点、任务 ID 或事件内容")
        filters.addWidget(self.filter)
        filters.addWidget(self.search, 1)
        log_layout.addLayout(filters)
        self.log = self.text()
        log_layout.addWidget(self.log)
        self.filter.currentIndexChanged.connect(self.show_log)
        self.search.textChanged.connect(self.show_log)
        splitter.addWidget(log)
        splitter.setSizes([670, 180])
        layout.addWidget(splitter)

        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f5f7fa; color: #15283b; }
            QLabel#header { background: #15283b; color: white; padding: 12px; font-weight: bold; }
            QTableWidget, QPlainTextEdit, QLineEdit { background: white; alternate-background-color: #edf4f8; }
            QHeaderView::section { background: #e3edf3; padding: 4px; }
            QPushButton { padding: 5px 10px; border: 1px solid #a7bcc9; border-radius: 4px; background: white; }
            QPushButton:hover { background: #dceef0; }
        """)
        self.thread = QThread(self)
        self.worker = Worker(db_path)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.initialize)
        self.command.connect(self.worker.command)
        self.shutdown.connect(self.worker.shutdown)
        self.worker.snapshot.connect(self.refresh)
        self.worker.notice.connect(self.notice)
        self.worker.error.connect(self.error)
        self.worker.ports.connect(self.show_ports)
        self.worker.runs.connect(self.show_runs)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.finish_close)
        self.thread.start()
        self.clock = QTimer(self)
        self.clock.timeout.connect(self.show_header)
        self.clock.start(1000)
        self.show_header()

    @staticmethod
    def panel():
        widget = QWidget()
        return widget, QVBoxLayout(widget)

    @staticmethod
    def button(layout, title, callback):
        button = QPushButton(title)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    @staticmethod
    def text(max_height=None):
        widget = QPlainTextEdit()
        widget.setReadOnly(True)
        if max_height:
            widget.setMaximumHeight(max_height)
        return widget

    def network_panel(self):
        widget = QWidget()
        form = QFormLayout(widget)
        self.network_values = {"min_delay": number(0, 60, 0.05), "max_delay": number(0, 60, 0.2),
                               "loss": number(0, 1), "duplicate": number(0, 1)}
        for label, field in zip(("最短延迟（秒）", "最长延迟（秒）", "丢包概率", "重复概率"),
                                self.network_values.values()):
            field.setDecimals(3)
            form.addRow(label, field)
        self.button(form, "应用网络参数", lambda: self.send("network", {
            key: field.value() for key, field in self.network_values.items()
        }))
        self.partition = QLineEdit("001,002,003")
        form.addRow("分区一侧的节点 ID", self.partition)
        self.button(form, "应用双向分区", lambda: self.send("partition", [
            value.strip() for value in self.partition.text().split(",") if value.strip()
        ]))
        self.button(form, "恢复所有链路", lambda: self.send("heal"))
        return widget

    def hardware_panel(self):
        widget, layout = self.panel()
        layout.addWidget(QLabel("HARDWARE · 未连接 · 设备参数和通信验证规则待确认"))
        self.devices = self.text(max_height=130)
        layout.addWidget(self.devices)
        self.button(layout, "扫描串口设备", lambda: self.send("scan"))
        layout.addWidget(QLabel("感知 · 暂无设备数据"))
        layout.addStretch()
        return widget

    @Slot(list)
    def show_ports(self, ports):
        self.devices.setPlainText("\n".join(ports) if ports else "未发现串口设备")

    def send(self, command, arg=None):
        self.command.emit(command, arg)

    def power(self, online):
        key = selected(self.nodes)
        if key:
            self.send("power", (key, online))
        else:
            self.notice("请先选择节点")

    def cancel(self):
        key = selected(self.tasks)
        if key and QMessageBox.question(self, "取消任务", f"向各节点广播取消 {key}？") == QMessageBox.StandardButton.Yes:
            self.send("cancel", key)

    @Slot(str)
    def notice(self, text):
        if text.startswith("仿真已"):
            self.running_status = text
            self.show_header()
        self.statusBar().showMessage(text, 6000)

    @Slot(str)
    def error(self, text):
        if text.startswith("仿真暂停"):
            self.running_status = "异常暂停"
            self.show_header()
        self.statusBar().showMessage(text)
        if not self.closing:
            QMessageBox.warning(self, "操作提示", text)

    @Slot(list)
    def show_runs(self, runs):
        self.stats.runs.clear()
        for key, scenario, started in runs:
            self.stats.runs.addItem(f"{started} UTC · {SCENARIO_NAMES.get(scenario, scenario)} · {key[:8]}", key)

    def export(self):
        run_id = self.stats.runs.currentData()
        if run_id:
            path, _ = QFileDialog.getSaveFileName(self, "导出实验记录", f"{run_id[:8]}.csv", "CSV (*.csv)")
            if path:
                self.send("export", (path, run_id))

    def show_header(self):
        nodes = self.snapshot.get("nodes", {}).values()
        online = sum(node["status"] == "ONLINE" for node in nodes)
        offline = sum(node["status"] == "OFFLINE" for node in nodes)
        time = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.header.setText(f"空地协同上位机  |  SIMULATION 仿真  |  {self.running_status}  |  "
                            f"在线 {online} / 离线 {offline}  |  {self.snapshot.get('now', 0):.2f} 仿真秒  |  {time}")

    @Slot(dict)
    def refresh(self, snapshot):
        if self.snapshot.get("run_id") != snapshot["run_id"]:
            self.running_status = "运行中"
        if self.snapshot.get("network") != snapshot["network"]:
            for key, value in snapshot["network"].items():
                self.network_values[key].setValue(value)
        self.snapshot = snapshot
        nodes = snapshot["nodes"]
        rows(self.nodes, [
            (key, TYPES.get(node["profile"].get("node_type")), STATUS[node["status"]],
             f"{node['profile']['battery']:.0%}" if node["profile"] else None,
             node["task"], {"ONLINE": "正常", "JOINING": "未知"}.get(node["status"], "异常"))
            for key, node in nodes.items()
        ], selected(self.nodes))
        rows(self.links, [(key, *(STATUS[node["peers"][dst]] if dst != key else "本机"
                                 for dst in nodes)) for key, node in nodes.items()])
        self.blocked.setText("模拟阻断链路：" + ("、".join(f"{a}→{b}" for a, b in snapshot["blocked"]) or "无"))
        records = []
        for key, task in snapshot["tasks"].items():
            definition = task["definition"]
            publisher_view = task["views"][definition["publisher"]]
            active = next((view for view in task["views"].values() if view["status"] == "EXECUTING"), None)
            view = active or publisher_view
            state = STATUS[view["status"]]
            if active and publisher_view["status"] == "CANCELLED":
                state += "（取消传播中）"
            records.append((key, definition["task_type"], definition["priority"],
                            ", ".join(definition["required"]), state, view["owner"], definition["starts_at"]))
        rows(self.tasks, records, selected(self.tasks))
        self.show_header()
        self.show_node()
        self.show_task()
        self.show_log()
        self.stats.update_snapshot(snapshot)

    def show_node(self):
        key = selected(self.nodes)
        node = self.snapshot.get("nodes", {}).get(key)
        if node:
            p = node["profile"]
            self.node_detail.setPlainText(
                f"节点 {key}\n能力：{', '.join(p.get('capabilities', [])) or '未知'}\n"
                f"位置：{p.get('position', '未知')}\n"
                f"最后心跳：{node['heartbeat']} 仿真秒\n模拟电源状态：{STATUS[node['actual']]}"
            )
        else:
            self.node_detail.clear()

    def show_task(self):
        key = selected(self.tasks)
        task = self.snapshot.get("tasks", {}).get(key)
        if not task:
            self.task_detail.clear()
            return
        definition = task["definition"]
        lines = [f"截止：{definition['deadline'] if definition['deadline'] is not None else '不限'}",
                 f"说明：{definition['task_description']}"]
        for node, view in task["views"].items():
            bid = view["bids"].get(node)
            lines.append(f"{node} · 第 {view['epoch']} 轮 · {STATUS[view['status']]} · "
                         f"本地评分 {bid if bid is not None else '—'} · "
                         f"认领 {', '.join(view['claims']) or '—'} · 投票 {view['votes']}")
        for epoch, previous, owner in self.snapshot["transfers"].get(key, []):
            lines.append(f"第 {epoch} 轮重新分配：{previous} → {owner}")
        text = "\n".join(lines)
        if text != self.task_detail.toPlainText():
            self.task_detail.setPlainText(text)

    def show_log(self):
        category = self.filter.currentData()
        search = self.search.text().casefold()
        lines = []
        for now, key, node, data in self.snapshot.get("events", []):
            if category and category != key:
                continue
            line = f"{now:8.2f}  {node:9s}  {EVENTS.get(key, key)}  {json.dumps(data, ensure_ascii=False)}"
            if search in line.casefold():
                lines.append(line)
        text = "\n".join(lines)
        if text != self.log.toPlainText():
            bar = self.log.verticalScrollBar()
            at_end = bar.value() == bar.maximum()
            previous = bar.value()
            self.log.setPlainText(text)
            bar.setValue(bar.maximum() if at_end else previous)

    def closeEvent(self, event):
        if self.closed:
            event.accept()
        else:
            event.ignore()
            if not self.closing:
                self.closing = True
                self.centralWidget().setEnabled(False)
                self.shutdown.emit()

    @Slot()
    def finish_close(self):
        self.closed = True
        self.close()


def main():
    log_path = ROOT / "logs/dashboard.log"
    log_path.parent.mkdir(exist_ok=True)
    logging.basicConfig(filename=log_path, encoding="utf-8", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
