from collections.abc import Callable
from dataclasses import dataclass

from communication.message import Message


@dataclass(frozen=True)
class FrameRules:
    # Extractor returns validated frame bodies and an unconsumed suffix.
    extract: Callable[[bytes], tuple[list[bytes], bytes]]
    decode: Callable[[bytes], Message]
    encode: Callable[[Message], bytes]


class SerialProtocol:
    def __init__(self, rules: FrameRules, max_pending: int = 65536) -> None:
        self.rules = rules
        self.pending = b""
        self.max_pending = max_pending

    def feed(self, chunk: bytes) -> list[Message]:
        frames, self.pending = self.rules.extract(self.pending + chunk)
        if len(self.pending) > self.max_pending:
            self.pending = b""
            raise ValueError("未完成帧超过缓存上限")
        return [self.rules.decode(frame) for frame in frames]

    def reset(self) -> None:
        self.pending = b""
