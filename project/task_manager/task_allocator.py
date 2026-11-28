from collections import Counter
from collections.abc import Mapping


def best_candidate(scores: Mapping[str, float]) -> str | None:
    return min(scores, key=lambda node_id: (-scores[node_id], node_id), default=None)


def certified_owner(votes: Mapping[str, str], membership_size: int) -> str | None:
    return next((candidate for candidate, count in Counter(votes.values()).items()
                 if count > membership_size // 2), None)
