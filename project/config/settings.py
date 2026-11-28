from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    tick: float = 0.25
    heartbeat: float = 1
    suspect: float = 3
    offline: float = 5
    ttl: float = 8
    bid_window: float = 3
    claim_window: float = 2
    lease_period: float = 14
    distance_scale: float = 100
    seed: int = 42
