from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from random import Random


@dataclass(frozen=True)
class NetworkSettings:
    min_delay: float = 0.05
    max_delay: float = 0.20
    loss: float = 0
    duplicate: float = 0

    def __post_init__(self) -> None:
        if not (0 <= self.min_delay <= self.max_delay < float("inf")
                and 0 <= self.loss <= 1 and 0 <= self.duplicate <= 1):
            raise ValueError("Invalid simulated network settings")


class NetworkSimulator:
    def __init__(self, settings: NetworkSettings, seed: int) -> None:
        self.settings = settings
        self.rng = Random(seed)
        self.queue: list[tuple[float, int, str, str, str]] = []
        self.order = count()
        self.down: set[str] = set()
        self.blocked: set[tuple[str, str]] = set()

    def reachable(self, src: str, dst: str) -> bool:
        return src not in self.down and dst not in self.down and (src, dst) not in self.blocked

    def enqueue(self, now: float, src: str, dst: str, raw: str) -> str:
        if not self.reachable(src, dst):
            return "link_unavailable"
        if self.rng.random() < self.settings.loss:
            return "packet_loss"
        copies = 2 if self.rng.random() < self.settings.duplicate else 1
        for _ in range(copies):
            delay = self.rng.uniform(self.settings.min_delay, self.settings.max_delay)
            heappush(self.queue, (now + delay, next(self.order), src, dst, raw))
        return "packet_duplicated" if copies == 2 else "queued"

    def due(self, now: float):
        while self.queue and self.queue[0][0] <= now:
            _, _, src, dst, raw = heappop(self.queue)
            yield src, dst, raw, self.reachable(src, dst)
