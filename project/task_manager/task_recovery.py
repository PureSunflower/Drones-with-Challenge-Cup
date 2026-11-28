from config.settings import Settings
from task_manager.task import Task


def epoch_at(task: Task, now: float, settings: Settings) -> int:
    return int((now - task.starts_at) // settings.lease_period)


def epoch_start(task: Task, epoch: int, settings: Settings) -> float:
    return task.starts_at + epoch * settings.lease_period
