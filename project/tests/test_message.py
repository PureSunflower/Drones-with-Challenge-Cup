import json

import pytest

from communication.message import Message, MessageType, SensorData, SensorType
from communication.protocol import Inbox, decode, encode


def packet() -> Message:
    return Message(MessageType.HEARTBEAT, "001", "002", 1, 0, {})


def test_round_trip():
    assert decode(encode(packet())) == packet()


@pytest.mark.parametrize("change", [
    {"protocol_version": 2}, {"protocol_version": True}, {"seq": True},
    {"src": "ALL"}, {"msg_type": "UNKNOWN"}, {"payload": []}, {"ttl": 0},
    {"timestamp": float("nan")}, {"timestamp": 10**100},
])
def test_malformed(change):
    fields = json.loads(encode(packet()))
    with pytest.raises(ValueError):
        decode(json.dumps(fields | change))


def test_nonobject_and_malformed_json():
    for raw in ("[]", "{"):
        with pytest.raises(ValueError):
            decode(raw)


def test_duplicate_expired_future_and_destination():
    inbox = Inbox()
    raw = encode(packet())
    with pytest.raises(ValueError, match="destination"):
        inbox.accept(raw, "003", 0)
    with pytest.raises(ValueError, match="future"):
        inbox.accept(raw, "002", -1)
    inbox.accept(raw, "002", 0)
    with pytest.raises(ValueError, match="duplicate"):
        inbox.accept(raw, "002", 1)
    with pytest.raises(ValueError, match="expired"):
        inbox.accept(raw, "002", 8)
    assert not inbox.seen


@pytest.mark.parametrize("kind", list(SensorType))
def test_simulated_sensor_envelope(kind):
    payload = SensorData("demo", kind, "001", 0, "LOCAL_SIM", {"value": 2}, 0.5).simulation_payload()
    msg = Message(MessageType.SENSOR_DATA, "001", "ALL", 2, 0, payload)
    assert decode(encode(msg)).payload["origin"] == "SIMULATION"
