"""Tests for concrete TaskPlannerTool behavior."""

from tools.task_planner_tool import TaskPlannerTool


def test_task_planner_decomposes_objective_into_tasks() -> None:
    """Planner should split an objective into multiple pending tasks."""
    tool = TaskPlannerTool()

    result = tool.run("Review backlog, prioritize tasks, and send updates")

    assert result["status"] == "ok"
    payload = result["payload"]
    assert payload["task_count"] >= 2
    assert all(task["status"] == "pending" for task in payload["tasks"])


def test_task_planner_handles_empty_objective() -> None:
    """Planner should return a structured error for empty objective input."""
    tool = TaskPlannerTool()

    result = tool.run("   ")

    assert result["status"] == "error"
    assert result["payload"]["error"] == "Objective is empty."
