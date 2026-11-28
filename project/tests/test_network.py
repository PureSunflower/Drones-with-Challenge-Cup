import pytest

from communication.network_simulator import NetworkSettings
from simulator.scenario_runner import run_scenario
from simulator.simulation_engine import Simulation


@pytest.mark.parametrize("scenario,expected", [
    ("normal", "001"), ("single-outage", "002"), ("double-outage", "003"),
    ("loss", "001"), ("duplicate", "001"), ("delay", "001"),
    ("partition", None), ("recovery", "001"), ("competition", "001"),
])
def test_scenarios(scenario, expected):
    events = []
    result = run_scenario(scenario, lambda *event: events.append(event), 42)
    executing = [key for key, state in result["nodes"].items() if state["executing"]]
    assert executing == ([expected] if expected else [])
    assert result["origin"] == "SIMULATION"
    if scenario == "competition":
        assert {node for _, kind, node, _ in events if kind == "task_claim"} >= {"001", "002"}
    if scenario == "duplicate":
        assert any(kind == "message_rejected" and item["reason"] == "duplicate message"
                   for _, kind, _, item in events)
    if scenario == "loss":
        assert any(kind == "packet_loss" for _, kind, _, _ in events)


def test_full_loss_never_self_assigns():
    sim = Simulation(network=NetworkSettings(loss=1))
    sim.publish("001", "blocked", (0, 0), frozenset({"COMM"}))
    sim.advance(30)
    assert not any(node.current_task for node in sim.nodes.values())


def test_network_delay_controls_delivery():
    sim = Simulation(network=NetworkSettings(min_delay=2, max_delay=2))
    sim.advance(2)
    assert sim.nodes["002"].known_nodes["001"].last_heartbeat_time is None
    sim.advance(0.25)
    assert sim.nodes["002"].known_nodes["001"].last_heartbeat_time == 0
