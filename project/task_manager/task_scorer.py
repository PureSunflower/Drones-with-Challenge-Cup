from math import dist

from node_manager.node_state import Profile
from task_manager.task import Task


def score_task(profile: Profile, task: Task, load: int, distance_scale: float) -> float | None:
    if not task.required <= profile.capabilities:
        return None
    desired = task.required | task.preferred
    capability = len(desired & profile.capabilities) / len(desired) if desired else 1
    distance = max(0, 1 - dist(task.position, profile.position) / distance_scale)
    return round(0.4 * distance + 0.3 * profile.battery
                 + 0.2 * capability + 0.1 / (1 + load), 9)
