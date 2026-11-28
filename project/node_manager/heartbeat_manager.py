from config.settings import Settings
from node_manager.node_registry import NodeRegistry
from node_manager.node_state import NodeStatus


def check_timeouts(registry: NodeRegistry, settings: Settings, now: float) -> None:
    for node_id, peer in registry.peers.items():
        last = peer.last_heartbeat_time
        age = now - (last if last is not None else 0)
        if age >= settings.offline:
            registry.transition(node_id, NodeStatus.OFFLINE, now)
        elif age >= settings.suspect and peer.status != NodeStatus.OFFLINE:
            registry.transition(node_id, NodeStatus.SUSPECT, now)
