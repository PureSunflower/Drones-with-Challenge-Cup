from dataclasses import dataclass
from enum import StrEnum

from communication.protocol import finite


class NodeStatus(StrEnum):
    JOINING = "JOINING"
    ONLINE = "ONLINE"
    SUSPECT = "SUSPECT"
    OFFLINE = "OFFLINE"


@dataclass(frozen=True)
class Profile:
    node_type: str
    capabilities: frozenset[str]
    battery: float
    position: tuple[float, float]

    @classmethod
    def from_payload(cls, payload: dict) -> "Profile":
        kind = payload.get("node_type")
        capabilities = payload.get("capabilities")
        battery = payload.get("battery")
        position = payload.get("position")
        if (not isinstance(kind, str) or not isinstance(capabilities, list)
                or not all(isinstance(item, str) for item in capabilities)
                or not finite(battery) or not 0 <= battery <= 1
                or not isinstance(position, list) or len(position) != 2
                or not all(finite(item) for item in position)):
            raise ValueError("Invalid node profile")
        return cls(kind, frozenset(capabilities), battery, tuple(position))

    def payload(self) -> dict:
        return dict(node_type=self.node_type, capabilities=sorted(self.capabilities),
                    battery=self.battery, position=list(self.position))


@dataclass
class Peer:
    status: NodeStatus = NodeStatus.JOINING
    profile: Profile | None = None
    last_heartbeat_time: float | None = None
    changed_at: float = 0
    status_seq: int = 0
    heartbeat_seq: int = 0
