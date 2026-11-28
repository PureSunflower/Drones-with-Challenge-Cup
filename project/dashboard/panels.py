from collections.abc import Iterable

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox, QFormLayout,
                               QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

STATUS = dict(JOINING="加入中", ONLINE="在线", SUSPECT="疑似失联", OFFLINE="离线",
              WAITING="等待", BIDDING="竞标", ASSIGNED="已分配", EXECUTING="执行中",
              COMPLETED="完成", FAILED="失败", REASSIGNING="重新评估",
              CANCELLED="已取消", EXPIRED="已到期")
TYPES = dict(MULTIROTOR="多旋翼", FIXED_WING="固定翼", GROUND="地面节点")
EVENTS = dict(node_state="节点状态变化", power_off="节点掉电", power_on="节点恢复",
              task_published="任务发布", task_bid="独立评分", task_claim="正式认领",
              task_vote="认领投票", claim_conflict="认领竞争", task_reassigned="任务重新分配", task_state="任务状态变化",
              task_outcome_unknown="失联，任务结果未知", packet_loss="消息丢失",
              packet_duplicated="消息重复", message_rejected="消息被拒绝",
              link_blocked="链路阻断", link_restored="链路恢复", partition="网络分区",
              scenario_started="实验启动", scenario_finished="实验结束")


def table(headers: Iterable[str]) -> QTableWidget:
    headers = list(headers)
    result = QTableWidget(0, len(headers))
    result.setHorizontalHeaderLabels(headers)
    result.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    result.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    result.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    result.setAlternatingRowColors(True)
    result.verticalHeader().hide()
    return result


def rows(widget: QTableWidget, data: list, key: str = "") -> None:
    selected = next((index for index, row in enumerate(data) if str(row[0]) == key), None)
    widget.blockSignals(True)
    widget.setRowCount(len(data))
    for row_index, row in enumerate(data):
        for index, value in enumerate(row):
            item = widget.item(row_index, index)
            if item is None:
                item = QTableWidgetItem()
                widget.setItem(row_index, index, item)
            item.setText("—" if value is None else str(value))
    if selected is not None:
        widget.selectRow(selected)
    else:
        widget.clearSelection()
    widget.blockSignals(False)


def selected(widget: QTableWidget) -> str:
    row = widget.currentRow()
    item = widget.item(row, 0) if widget.selectedItems() else None
    return item.text() if item else ""


def number(low: float, high: float, value: float = 0) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


class TaskForm(QWidget):
    def __init__(self) -> None:
        super().__init__()
        form = QFormLayout(self)
        self.task_id = QLineEdit()
        self.kind = QLineEdit("协同任务")
        self.priority = QSpinBox()
        self.priority.setRange(1, 5)
        self.priority.setValue(3)
        self.x = number(-100000, 100000)
        self.y = number(-100000, 100000)
        self.capabilities = QLineEdit("COMM")
        self.duration = number(0, 86400)
        self.duration.setSpecialValueText("不限")
        self.description = QLineEdit()
        for name, field in [
            ("任务 ID", self.task_id), ("任务类型", self.kind), ("优先级", self.priority),
            ("目标 X", self.x), ("目标 Y", self.y), ("必要能力（逗号分隔）", self.capabilities),
            ("截止时间（发布后仿真秒）", self.duration), ("任务说明", self.description),
        ]:
            form.addRow(name, field)
        self.publish = QPushButton("创建并发布")
        form.addRow(self.publish)

    def values(self) -> dict:
        return dict(task_id=self.task_id.text().strip(), task_type=self.kind.text().strip(),
                    priority=self.priority.value(), position=(self.x.value(), self.y.value()),
                    required=frozenset(word.strip().upper() for word in
                                       self.capabilities.text().replace("，", ",").split(",")
                                       if word.strip()),
                    duration=self.duration.value(), task_description=self.description.text())


class StatsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.metrics = QLabel()
        self.runs = QComboBox()
        self.save = QPushButton("保存当前实验")
        self.export = QPushButton("导出所选实验 CSV")
        figure = Figure(figsize=(6, 3), layout="tight")
        self.canvas = FigureCanvasQTAgg(figure)
        self.axes = figure.subplots()
        font = dict(fontfamily=["Microsoft YaHei", "SimHei", "DejaVu Sans"])
        self.axes.set(title="SIMULATION")
        self.axes.set_xlabel("仿真时间（秒）", **font)
        self.axes.set_ylabel("在线节点（个）", **font)
        self.axes.set_title("在线节点数量变化 · SIMULATION", **font)
        self.axes.set_ylim(-0.1, 6.5)
        self.axes.grid(alpha=0.2)
        self.line, = self.axes.plot([], [], color="#146b70", drawstyle="steps-post")
        for element in (self.metrics, self.canvas, self.runs, self.save, self.export):
            layout.addWidget(element)
        self.last_history = None

    def update_snapshot(self, snapshot: dict) -> None:
        m = snapshot["metrics"]

        def percentage(key: str) -> str:
            value = m[key]
            return "尚无样本" if value is None else f"{value:.1%}"

        def duration(key: str) -> str:
            values = m[key]
            return "尚无样本" if not values else f"{sum(values) / len(values):.2f} 秒（{len(values)} 次）"

        self.metrics.setText(
            f"节点变更 {m.get('node_state', 0)}    心跳超时 {m.get('heartbeat_timeout', 0)}\n"
            f"发送 {m.get('message_sent', 0)}    接收 {m.get('message_received', 0)}    "
            f"随机丢包率 {percentage('loss_rate')}\n认领成功率 {percentage('claim_success')}    "
            f"额外认领 {m['duplicate_claims']}\n"
            f"平均故障检测 {duration('detection')}    平均重新分配 {duration('reassignment')} "
        )
        history = snapshot["history"]
        if history != self.last_history:
            self.last_history = history
            x, y = zip(*history) if history else ([], [])
            self.line.set_data(x, y)
            self.axes.set_xlim(x[0] - 1 if x else 0, max(10, x[-1] + 1) if x else 10)
            self.canvas.draw_idle()
