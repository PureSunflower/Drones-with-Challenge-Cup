from collections import Counter, defaultdict, deque
from dataclasses import asdict
from pathlib import Path

from communication.network_simulator import NetworkSettings
from simulator.scenario_runner import SCENARIOS, scenario_steps
from simulator.simulation_engine import Simulation
from storage.database import Database
from storage.experiment_logger import ExperimentLogger


class Session:
    def __init__(self, db: Database, scenario: str) -> None:
        self.db = db
        self.run_id = db.start(scenario)
        self.logger = ExperimentLogger(db, self.run_id)
        self.events = deque(maxlen=350)
        self.counts = Counter()
        self.claims = defaultdict(set)
        self.awarded = set()
        self.powered_off = {}
        self.detected = {}
        self.reassigned = {}
        self.transfers = defaultdict(set)
        self.history = deque(maxlen=900)
        self.sim = Simulation(network=SCENARIOS.get(scenario, NetworkSettings()), record=self.record)
        self.steps = None if scenario == "manual" else scenario_steps(scenario, self.sim)
        self.next_step = 0
        self.record(0, "scenario_started", "SIMULATOR",
                    dict(name=scenario, origin="SIMULATION", network=asdict(self.sim.network.settings)))

    def record(self, now: float, kind: str, node: str, data: dict) -> None:
        self.logger(now, kind, node, data)
        self.counts[kind] += 1
        if kind not in {"message_sent", "message_received", "heartbeat", "link_unavailable", "delivery_attempt"}:
            self.events.append((now, kind, node, data))
        if kind == "power_off":
            self.powered_off[node] = now
        if kind == "node_state" and data["after"] == "OFFLINE" and data["peer"] != node:
            self.counts["heartbeat_timeout"] += 1
            peer = data["peer"]
            if peer in self.powered_off:
                started = self.powered_off[peer]
                self.detected.setdefault((peer, started), now - started)
        if kind == "task_claim":
            candidates = self.claims[data["task_id"], data["epoch"]]
            candidates.add(node)
            if len(candidates) > 1:
                details = dict(task_id=data["task_id"], epoch=data["epoch"], candidates=sorted(candidates))
                self.logger(now, "claim_conflict", node, details)
                self.events.append((now, "claim_conflict", node, details))
        if kind == "task_state" and data["after"] == "EXECUTING":
            self.awarded.add((data["task_id"], data["epoch"]))
        if kind == "task_reassigned":
            peer = data["previous_owner"]
            self.transfers[data["task_id"]].add((data["epoch"], peer, data["owner"]))
            if peer in self.powered_off:
                self.reassigned.setdefault((data["task_id"], data["epoch"]), now - self.powered_off[peer])

    def tick(self) -> None:
        if self.steps is not None and self.sim.now >= self.next_step:
            duration = next(self.steps, None)
            if duration is None:
                self.steps = None
                self.record(self.sim.now, "scenario_actions_finished", "SIMULATOR", {})
            else:
                self.next_step = self.sim.now + duration
        self.sim.advance(self.sim.settings.tick)
        if int(self.sim.now) != int(self.sim.now - self.sim.settings.tick):
            self.history.append((self.sim.now, sum(
                node.node_status == "ONLINE" for node in self.sim.nodes.values()
            )))

    def snapshot(self) -> dict:
        sim = self.sim
        observers = sim.nodes["006"].known_nodes
        nodes = {}
        for key, node in sim.nodes.items():
            peer = observers.get(key)
            profile = peer.profile if peer else node.profile
            nodes[key] = dict(status=peer.status if peer else node.node_status,
                              profile=profile.payload() if profile else {},
                              heartbeat=peer.last_heartbeat_time if peer else node.last_heartbeat_time,
                              task=node.current_task, actual=node.node_status,
                              peers={key: value.status for key, value in node.known_nodes.items()})
        tasks = {}
        for key, node in sim.nodes.items():
            for task_id, view in node.local_task_table.items():
                entry = tasks.setdefault(task_id, dict(definition=view.task.payload(), views={}))
                current = view.rounds.get(view.epoch)
                entry["views"][key] = dict(status=view.status, owner=view.owner,
                                          epoch=view.epoch, unknown=view.outcome_unknown,
                                          bids=dict(current.bids) if current else {},
                                          claims=dict(current.claims) if current else {},
                                          votes=dict(current.votes) if current else {})
        attempts = self.counts["delivery_attempt"] - self.counts["link_unavailable"]
        return dict(origin="SIMULATION", run_id=self.run_id, now=sim.now, nodes=nodes,
                    tasks=tasks, transfers={key: sorted(values) for key, values in self.transfers.items()},
                    network=asdict(sim.network.settings), blocked=sorted(sim.network.blocked), events=list(self.events),
                    history=list(self.history), metrics=dict(self.counts) | {
                        "loss_rate": self.counts["packet_loss"] / attempts if attempts else None,
                        "claim_success": len(self.awarded) / len(self.claims) if self.claims else None,
                        "duplicate_claims": sum(len(nodes) - 1 for nodes in self.claims.values()),
                        "detection": list(self.detected.values()),
                        "reassignment": list(self.reassigned.values()),
                    })

    def save(self) -> None:
        result = self.snapshot()
        result.pop("events")
        self.db.finish(self.run_id, result)

    def finish(self) -> None:
        self.record(self.sim.now, "scenario_finished", "SIMULATOR", {})
        self.save()

    def export(self, path: Path, run_id: str | None = None) -> None:
        if run_id is None or run_id == self.run_id:
            self.save()
        self.db.export(path, run_id or self.run_id)
