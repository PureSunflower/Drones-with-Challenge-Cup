from collections.abc import Callable

from communication.message import Message
from communication.network_simulator import NetworkSimulator
from communication.protocol import encode


class MessageBus:
    def __init__(self, network: NetworkSimulator, record: Callable) -> None:
        self.network = network
        self.record = record
        self.receivers: dict[str, Callable[[str, float], None]] = {}

    def send(self, message: Message) -> None:
        now = message.timestamp
        raw = encode(message)
        self.record(now, "message_sent", message.src, {"message": raw})
        for dst in self.receivers:
            if dst == message.src or message.dst not in ("ALL", dst):
                continue
            result = self.network.enqueue(now, message.src, dst, raw)
            if result != "queued":
                self.record(now, result, message.src, {"dst": dst, "seq": message.seq})

    def deliver(self, now: float) -> None:
        for src, dst, raw, reachable in self.network.due(now):
            if reachable:
                self.record(now, "message_received", dst, {"message": raw})
                self.receivers[dst](raw, now)
            else:
                self.record(now, "link_unavailable_at_delivery", src, {"dst": dst})
