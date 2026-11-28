import json
import math

from communication.message import Message, MessageType


def finite(value: object) -> bool:
    return (type(value) is int and abs(value) <= 2**53
            or type(value) is float and math.isfinite(value))


def encode(message: Message) -> str:
    from dataclasses import asdict
    return json.dumps(asdict(message), allow_nan=False, ensure_ascii=False)


def reject_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def decode(raw: str) -> Message:
    fields = json.loads(raw, parse_constant=reject_constant)
    if not isinstance(fields, dict):
        raise ValueError("Expected a JSON object")
    try:
        message = Message(**fields)
        kind = MessageType(message.msg_type)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid message fields") from exc
    if (
        "protocol_version" not in fields or type(message.protocol_version) is not int
        or message.protocol_version != 1
        or not all(isinstance(value, str) and value.strip() for value in (message.src, message.dst))
        or message.src == "ALL" or type(message.seq) is not int or message.seq < 1
        or not finite(message.timestamp) or message.timestamp < 0
        or not finite(message.ttl) or message.ttl <= 0
        or not isinstance(message.payload, dict)
    ):
        raise ValueError("Invalid envelope")
    return Message(kind, message.src, message.dst, message.seq,
                   message.timestamp, message.payload, message.ttl)


class Inbox:
    def __init__(self) -> None:
        self.seen: dict[tuple[str, int], float] = {}

    def accept(self, raw: str, recipient: str, now: float) -> Message:
        message = decode(raw)
        self.seen = {key: expiry for key, expiry in self.seen.items() if expiry > now}
        expiry = message.timestamp + message.ttl
        if not message.timestamp <= now < expiry:
            raise ValueError("expired or future message")
        if message.dst not in ("ALL", recipient):
            raise ValueError("wrong destination")
        key = (message.src, message.seq)
        if key in self.seen:
            raise ValueError("duplicate message")
        self.seen[key] = expiry
        return message
