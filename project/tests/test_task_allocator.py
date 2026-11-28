from itertools import combinations

from simulator.simulation_engine import Simulation
from task_manager.task_allocator import best_candidate, certified_owner


def test_deterministic_tiebreak():
    assert best_candidate({"002": 0.8, "003": 0.7, "001": 0.8}) == "001"


def test_majority_votes_required_and_intersect():
    members = range(6)
    majorities = [set(group) for group in combinations(members, 4)]
    assert all(first & second for first in majorities for second in majorities)
    assert certified_owner(dict(zip(range(6), ["a"] * 3 + ["b"] * 3)), 6) is None
    assert certified_owner(dict(zip(range(6), ["a"] * 4 + ["b"] * 2)), 6) == "a"


def test_completion_syncs_to_peer_that_missed_original_result():
    sim = Simulation()
    sim.publish("006", "t", (0, 0), frozenset({"COMM"}))
    sim.advance(7)
    sim.power("002", False)
    sim.nodes["001"].tasks.finish("t", sim.now)
    sim.advance(2)
    assert sim.nodes["003"].local_task_table["t"].status == "COMPLETED"
    sim.power("001", False)
    sim.power("002", True)
    sim.advance(3)
    assert sim.nodes["002"].local_task_table["t"].status == "COMPLETED"


def test_no_eligible_node_never_claims():
    sim = Simulation()
    sim.publish("006", "t", (0, 0), frozenset({"UNAVAILABLE"}))
    sim.advance(20)
    assert all(node.local_task_table["t"].owner is None for node in sim.nodes.values())
