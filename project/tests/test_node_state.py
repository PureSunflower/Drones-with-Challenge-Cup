from communication.message import Message, MessageType
from node_manager.node_state import NodeStatus
from simulator.simulation_engine import Simulation


def test_six_independent_registries_and_task_tables():
    sim = Simulation()
    assert set(sim.nodes) == {f"{i:03}" for i in range(1, 7)}
    assert len({id(node.local_task_table) for node in sim.nodes.values()}) == 6
    assert len({id(node.known_nodes) for node in sim.nodes.values()}) == 6
    sim.advance(2)
    for key, node in sim.nodes.items():
        assert node.node_status == NodeStatus.ONLINE
        assert set(node.known_nodes) == sim.nodes.keys() - {key}
        assert all(peer.status == NodeStatus.ONLINE and peer.profile
                   for peer in node.known_nodes.values())


def test_out_of_order_profile_preserves_newest():
    sim = Simulation()
    node = sim.nodes["002"]
    payload = sim.nodes["001"].profile.payload()
    for seq, battery in [(10, 0.75), (9, 0.25)]:
        msg = Message(MessageType.NODE_STATUS, "001", "ALL", seq, 0, dict(payload, battery=battery))
        from communication.protocol import encode
        node.receive(encode(msg), 0)
    assert node.known_nodes["001"].profile.battery == 0.75
