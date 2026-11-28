from collections.abc import Callable
from itertools import count

from communication.message import Message, MessageType as Kind
from communication.protocol import Inbox
from config.settings import Settings
from node_manager.heartbeat_manager import check_timeouts
from node_manager.node_registry import NodeRegistry
from node_manager.node_state import NodeStatus, Profile
from task_manager.task import Task, TaskStatus
from task_manager.task_coordinator import TaskCoordinator
from task_manager.task_recovery import epoch_at


class Node:
    def __init__(self, node_id: str, profile: Profile, members: frozenset[str],
                 settings: Settings, transport: Callable, record: Callable) -> None:
        self.node_id = node_id
        self.profile = profile
        self.members = members
        self.settings = settings
        self.transport = transport
        self.record = record
        self.registry = NodeRegistry(set(members) - {node_id}, record)
        self.known_nodes = self.registry.peers
        self.tasks = TaskCoordinator(self, members, settings, record)
        self.local_task_table = self.tasks.views
        self.node_status = NodeStatus.JOINING
        self.last_heartbeat_time: float | None = None
        self.inbox = Inbox()
        self.sequences = count(1)
        self.next_heartbeat = 0.0

    def load_at(self, now: float) -> int:
        return sum(
            view.status == TaskStatus.EXECUTING and
            view.epoch == epoch_at(view.task, now, self.settings)
            for view in self.local_task_table.values()
        )

    @property
    def current_task(self) -> str | None:
        return next((key for key, view in self.local_task_table.items()
                     if self.node_status == NodeStatus.ONLINE and view.status == TaskStatus.EXECUTING), None)

    def send(self, kind: Kind, now: float, payload: dict, dst: str = "ALL") -> None:
        self.transport(Message(kind, self.node_id, dst, next(self.sequences), now, payload,
                               self.settings.ttl))

    def publish(self, task: Task, now: float) -> None:
        if task.publisher != self.node_id or task.task_id in self.local_task_table:
            raise ValueError("Invalid task publication")
        self.tasks.register(task, now)
        self.record(now, "task_published", task.payload())
        self.send(Kind.TASK_ANNOUNCE, now, task.payload())

    def receive(self, raw: str, now: float) -> None:
        try:
            msg = self.inbox.accept(raw, self.node_id, now)
            if msg.src not in self.known_nodes:
                raise ValueError("Unknown sender")
            if msg.msg_type in (Kind.NODE_JOIN, Kind.NODE_LEAVE, Kind.HEARTBEAT, Kind.NODE_STATUS):
                self.registry.receive(msg, now, self.settings.suspect, self.settings.offline)
            elif msg.msg_type in (Kind.SENSOR_DATA, Kind.LINK_STATUS):
                if msg.msg_type == Kind.SENSOR_DATA and (
                    msg.payload.get("origin") != "SIMULATION" or msg.payload.get("source_node") != msg.src
                ):
                    raise ValueError("Expected a simulated sensor payload for the sending node")
                self.record(now, msg.msg_type.lower(), msg.payload)
            else:
                self.tasks.receive(msg, now)
        except (ValueError, RecursionError) as exc:
            self.record(now, "message_rejected", {"reason": str(exc)})

    def set_status(self, status: NodeStatus, now: float) -> None:
        if status != self.node_status:
            self.record(now, "node_state", dict(peer=self.node_id, before=self.node_status, after=status))
            self.node_status = status

    def step(self, now: float) -> None:
        if self.node_status == NodeStatus.OFFLINE:
            return
        if self.node_status == NodeStatus.JOINING:
            self.send(Kind.NODE_JOIN, now, self.profile.payload())
            self.set_status(NodeStatus.ONLINE, now)
        pulse = now >= self.next_heartbeat
        if pulse:
            self.send(Kind.HEARTBEAT, now, self.profile.payload())
            self.last_heartbeat_time = now
            self.next_heartbeat = now + self.settings.heartbeat
        check_timeouts(self.registry, self.settings, now)
        self.tasks.step(now, pulse)
