import pytest

from communication.message import Message, MessageType
from communication.protocol import encode
from simulator.simulation_engine import Simulation


def running_task():
    sim = Simulation()
    sim.publish("006", "t", (0, 0), frozenset({"COMM"}))
    sim.advance(7)
    assert sim.nodes["001"].current_task == "t"
    return sim


def test_recovery_waits_for_lease_and_filters_old_claim():
    sim = running_task()
    sim.power("001", False)
    sim.advance(5)
    peer = sim.nodes["002"].local_task_table["t"]
    assert peer.outcome_unknown and peer.status == "REASSIGNING" and peer.owner == "001"
    sim.advance(8)
    assert peer.epoch == 1 and peer.owner == "002"
    stale = Message(MessageType.TASK_CLAIM, "001", "ALL", 99999, sim.now,
                    dict(task_id="t", epoch=0, score=1))
    sim.nodes["002"].receive(encode(stale), sim.now)
    assert peer.owner == "002"
    sim.power("001", True)
    sim.advance(2)
    assert sim.nodes["001"].local_task_table["t"].owner == "002"
    assert [key for key, node in sim.nodes.items() if node.current_task] == ["002"]


def test_partition_does_not_extend_isolated_old_lease():
    sim = running_task()
    sim.partition({"001", "003"})
    for _ in range(72):
        sim.advance(0.25)
        assert sum(node.current_task == "t" for node in sim.nodes.values()) <= 1
    assert sim.nodes["001"].current_task is None
    assert sim.nodes["002"].current_task == "t"
    sim.heal()
    sim.advance(2)
    assert sim.nodes["001"].local_task_table["t"].owner == "002"


def test_expired_lease_cannot_submit_result():
    sim = running_task()
    sim.advance(7)
    with pytest.raises(ValueError, match="active lease"):
        sim.nodes["001"].tasks.finish("t", sim.now)
