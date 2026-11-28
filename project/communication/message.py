from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class MessageType(StrEnum):
    HEARTBEAT = "HEARTBEAT"
    NODE_STATUS = "NODE_STATUS"
    NODE_JOIN = "NODE_JOIN"
    NODE_LEAVE = "NODE_LEAVE"
    TASK_ANNOUNCE = "TASK_ANNOUNCE"
    TASK_BID = "TASK_BID"
    TASK_CLAIM = "TASK_CLAIM"
    TASK_ACK = "TASK_ACK"
    TASK_RELEASE = "TASK_RELEASE"
    TASK_UPDATE = "TASK_UPDATE"
    TASK_COMPLETE = "TASK_COMPLETE"
    SENSOR_DATA = "SENSOR_DATA"
    LINK_STATUS = "LINK_STATUS"


@dataclass(frozen=True)
class Message:
    msg_type: MessageType
    src: str
    dst: str
    seq: int
    timestamp: float
    payload: dict[str, Any]
    ttl: float = 8
    protocol_version: int = 1


class SensorType(StrEnum):
    RADAR = "RADAR"
    VISION = "VISION"
    GNSS = "GNSS"
    IMU = "IMU"


@dataclass(frozen=True)
class SensorData:
    sensor_id: str
    sensor_type: SensorType
    source_node: str
    timestamp: float
    coordinate_frame: str
    measurement: dict[str, Any]
    confidence: float

    def simulation_payload(self) -> dict[str, Any]:
        return {**asdict(self), "origin": "SIMULATION"}
