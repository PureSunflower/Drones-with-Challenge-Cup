from node_manager.node_state import NodeStatus
from simulator.simulation_engine import Simulation


def test_heartbeat_timeout_and_power_recovery():
    sim = Simulation()
    sim.advance(2)
    peer = sim.nodes["002"].known_nodes["001"]
    sim.power("001", False)
    sim.advance(2.75)
    assert peer.status == NodeStatus.SUSPECT
    assert peer.changed_at == peer.last_heartbeat_time + sim.settings.suspect
    sim.advance(2)
    assert peer.status == NodeStatus.OFFLINE
    assert peer.changed_at == peer.last_heartbeat_time + sim.settings.offline
    sim.power("001", True)
    sim.advance(1)
    assert peer.status == NodeStatus.ONLINE
    assert peer.changed_at > 6
