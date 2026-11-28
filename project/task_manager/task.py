from dataclasses import dataclass, field
from enum import StrEnum

from communication.protocol import finite


class TaskStatus(StrEnum):
    WAITING = "WAITING"
    BIDDING = "BIDDING"
    ASSIGNED = "ASSIGNED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REASSIGNING = "REASSIGNING"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class Task:
    task_id: str
    publisher: str
    position: tuple[float, float]
    required: frozenset[str]
    preferred: frozenset[str]
    starts_at: float
    task_type: str = "协同任务"
    priority: int = 3
    deadline: float | None = None
    task_description: str = ""

    def payload(self) -> dict:
        return dict(task_id=self.task_id, publisher=self.publisher, position=list(self.position),
                    required=sorted(self.required), preferred=sorted(self.preferred),
                    starts_at=self.starts_at, task_type=self.task_type, priority=self.priority,
                    deadline=self.deadline, task_description=self.task_description)

    @classmethod
    def parse(cls, data: dict) -> "Task":
        task_id, publisher, pos, req, pref, start = (
            data.get(key) for key in ("task_id", "publisher", "position", "required", "preferred", "starts_at")
        )
        if (not all(isinstance(item, str) and item for item in (task_id, publisher))
                or not isinstance(pos, list) or len(pos) != 2 or not all(finite(v) for v in pos)
                or not all(isinstance(group, list) and all(isinstance(v, str) for v in group)
                           for group in (req, pref))
                or not finite(start) or start < 0):
            raise ValueError("Invalid task definition")
        kind = data.get("task_type", "协同任务")
        priority = data.get("priority", 3)
        deadline = data.get("deadline")
        description = data.get("task_description", "")
        if (not isinstance(kind, str) or not kind.strip() or type(priority) is not int
                or not 1 <= priority <= 5 or not isinstance(description, str)
                or (deadline is not None and (not finite(deadline) or deadline <= start))):
            raise ValueError("Invalid task metadata")
        return cls(task_id, publisher, tuple(pos), frozenset(req), frozenset(pref),
                   start, kind, priority, deadline, description)


@dataclass
class Round:
    bids: dict[str, float] = field(default_factory=dict)
    claims: dict[str, float] = field(default_factory=dict)
    votes: dict[str, str] = field(default_factory=dict)


@dataclass
class TaskView:
    task: Task
    status: TaskStatus = TaskStatus.WAITING
    epoch: int = -1
    owner: str | None = None
    previous_owner: str | None = None
    rounds: dict[int, Round] = field(default_factory=dict)
    result: str | None = None
    completion: tuple[int, float, str, str] | None = None
    outcome_unknown: bool = False
