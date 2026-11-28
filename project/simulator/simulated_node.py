from node_manager.node import Node
from node_manager.node_state import NodeStatus


class SimulatedNode(Node):
    def power_off(self, now: float) -> None:
        self.set_status(NodeStatus.OFFLINE, now)

    def power_on(self, now: float) -> None:
        # The simulation retains the vote journal and sequence counter across reboot.
        self.set_status(NodeStatus.JOINING, now)
        self.next_heartbeat = now
