import json
from collections.abc import Callable

from communication.message_bus import MessageBus
from communication.network_simulator import NetworkSettings, NetworkSimulator
from config.settings import ROOT, Settings
from node_manager.node_state import Profile
from simulator.simulated_node import SimulatedNode
from task_manager.task import Task


def ignore_event(now: float, event: str, node_id: str, details: dict) -> None:
    pass


class Simulation:
    def __init__(self, settings: Settings = Settings(), network: NetworkSettings = NetworkSettings(),
                 record: Callable = ignore_event) -> None:
        self.settings = settings
        self.record = record
        self.network = NetworkSimulator(network, settings.seed)
        self.bus = MessageBus(self.network, record)
        self.step_number = 0
        config = json.loads((ROOT / "config/node_config.json").read_text(encoding="utf-8"))
        members = frozenset(row["node_id"] for row in config)
        if len(members) != 6 or len(config) != 6:
            raise ValueError("Expected six unique simulation members")
        self.nodes = {}
        for row in config:
            node_id = row["node_id"]
            self.nodes[node_id] = SimulatedNode(
                node_id, Profile.from_payload(row), members, settings, self.bus.send,
                lambda now, event, details, sender=node_id: record(now, event, sender, details),
            )
        self.bus.receivers.update((key, node.receive) for key, node in self.nodes.items())

    @property
    def now(self) -> float:
        return self.step_number * self.settings.tick

    def advance(self, seconds: float) -> None:
        ticks = round(seconds / self.settings.tick)
        if ticks < 0 or abs(ticks * self.settings.tick - seconds) > 1e-9:
            raise ValueError("Duration must be a nonnegative multiple of the simulation tick")
        for _ in range(ticks):
            self.bus.deliver(self.now)
            for node in self.nodes.values():
                node.step(self.now)
            self.step_number += 1

    def publish(self, publisher: str, task_id: str, position: tuple[float, float],
                required: frozenset[str], preferred: frozenset[str] = frozenset(), *,
                task_type: str = "协同任务", priority: int = 3, deadline: float | None = None,
                task_description: str = "") -> None:
        if publisher in self.network.down:
            raise ValueError("Publisher is offline")
        task = Task.parse(Task(task_id, publisher, position, required, preferred, self.now,
                               task_type, priority, deadline, task_description).payload())
        self.nodes[publisher].publish(task, self.now)

    def cancel(self, publisher: str, task_id: str) -> None:
        if publisher in self.network.down:
            raise ValueError("Publisher is offline")
        self.nodes[publisher].tasks.cancel(task_id, self.now)

    def configure_network(self, settings: NetworkSettings) -> None:
        from dataclasses import asdict
        self.network.settings = settings
        self.record(self.now, "network_configured", "NETWORK", asdict(settings))

    def power(self, node_id: str, online: bool) -> None:
        node = self.nodes[node_id]
        if online and node_id in self.network.down:
            self.network.down.remove(node_id)
            node.power_on(self.now)
        elif not online and node_id not in self.network.down:
            self.network.down.add(node_id)
            node.power_off(self.now)
        else:
            return
        self.record(self.now, "power_on" if online else "power_off", node_id, {})

    def set_link(self, src: str, dst: str, enabled: bool) -> None:
        if src not in self.nodes or dst not in self.nodes or src == dst:
            raise ValueError("Expected two distinct member IDs")
        if enabled:
            self.network.blocked.discard((src, dst))
        else:
            self.network.blocked.add((src, dst))
        self.record(self.now, "link_restored" if enabled else "link_blocked", src, dict(dst=dst))

    def partition(self, group: set[str]) -> None:
        if not group or not group < self.nodes.keys():
            raise ValueError("Partition must be a nonempty proper subset of members")
        self.heal()
        for src in sorted(group):
            for dst in sorted(self.nodes.keys() - group):
                self.set_link(src, dst, False)
                self.set_link(dst, src, False)
        self.record(self.now, "partition", "NETWORK", dict(group=sorted(group)))

    def heal(self) -> None:
        for src, dst in sorted(self.network.blocked):
            self.set_link(src, dst, True)
        self.record(self.now, "network_healed", "NETWORK", {})
