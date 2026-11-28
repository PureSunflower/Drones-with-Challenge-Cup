from communication.message import Message, MessageType
from node_manager.node_state import NodeStatus, Peer, Profile


class NodeRegistry:
    def __init__(self, known_ids: set[str], record) -> None:
        self.peers = {node_id: Peer() for node_id in sorted(known_ids)}
        self.record = record

    def transition(self, node_id: str, status: NodeStatus, now: float) -> None:
        peer = self.peers[node_id]
        if status != peer.status:
            self.record(now, "node_state", {"peer": node_id, "before": peer.status, "after": status})
            peer.status = status
            peer.changed_at = now

    def receive(self, message: Message, now: float, suspect_after: float, offline_after: float) -> None:
        peer = self.peers[message.src]
        kind = message.msg_type
        if kind == MessageType.NODE_LEAVE:
            if message.seq > max(peer.status_seq, peer.heartbeat_seq):
                peer.status_seq = peer.heartbeat_seq = message.seq
                self.transition(message.src, NodeStatus.OFFLINE, now)
            return
        heartbeat = kind in (MessageType.HEARTBEAT, MessageType.NODE_JOIN)
        age = now - message.timestamp
        if heartbeat and (message.seq <= peer.heartbeat_seq or age >= offline_after):
            return
        profile = Profile.from_payload(message.payload)
        if message.seq > peer.status_seq:
            peer.profile = profile
            peer.status_seq = message.seq
        if heartbeat:
            peer.heartbeat_seq = message.seq
            peer.last_heartbeat_time = message.timestamp
            self.transition(message.src, NodeStatus.SUSPECT if age >= suspect_after else NodeStatus.ONLINE, now)
            self.record(now, "heartbeat", {"peer": message.src, "sent_at": message.timestamp})
