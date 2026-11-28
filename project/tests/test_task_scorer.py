import pytest

from node_manager.node_state import Profile
from task_manager.task import Task
from task_manager.task_scorer import score_task


def test_all_scoring_terms_and_required_capabilities():
    profile = Profile("SIM", frozenset({"COMM"}), 0.5, (50, 0))
    task = Task("demo", "006", (0, 0), frozenset({"COMM"}), frozenset({"VISION"}), 0)
    assert score_task(profile, task, 1, 100) == pytest.approx(0.5)
    impossible = Task("missing", "006", (0, 0), frozenset({"RADAR"}), frozenset(), 0)
    assert score_task(profile, impossible, 0, 100) is None
