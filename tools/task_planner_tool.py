"""Task planner tool scaffold.

Intended to decompose high-level objectives into executable task steps.
Future implementation should support priorities and dependencies.
"""

from __future__ import annotations

import re

from .base_tool import BaseTool


class TaskPlannerTool(BaseTool):
    """Tool for building task plans."""

    name = "task_planner_tool"
    description = "Decompose high-level objectives into executable tasks."
    input_schema = {"objective": "str"}

    _SEPARATORS = re.compile(r"\s*(?:,|;|\band\b|\bthen\b|\bafter\b)\s*", re.IGNORECASE)

    def _priority_for(self, text: str) -> str:
        """Infer a simple priority marker from language cues."""
        lowered = text.lower()
        if any(keyword in lowered for keyword in {"urgent", "asap", "immediately", "today"}):
            return "high"
        if any(keyword in lowered for keyword in {"soon", "this week", "next"}):
            return "medium"
        return "normal"

    def _normalize_steps(self, objective: str) -> list[str]:
        """Split objective text into deterministic candidate steps."""
        chunks = [chunk.strip(" .") for chunk in self._SEPARATORS.split(objective) if chunk.strip()]
        if not chunks:
            return [objective.strip()]
        return chunks

    def run(self, objective: str) -> dict:
        """Generate a lightweight executable plan from an objective string."""
        normalized_objective = objective.strip()
        if not normalized_objective:
            return {
                "status": "error",
                "tool": self.name,
                "payload": {
                    "objective": objective,
                    "error": "Objective is empty.",
                    "tasks": [],
                },
            }

        steps = self._normalize_steps(normalized_objective)
        tasks = [
            {
                "id": index,
                "title": step,
                "priority": self._priority_for(step),
                "status": "pending",
            }
            for index, step in enumerate(steps, start=1)
        ]

        return {
            "status": "ok",
            "tool": self.name,
            "payload": {
                "objective": normalized_objective,
                "task_count": len(tasks),
                "tasks": tasks,
            },
        }
