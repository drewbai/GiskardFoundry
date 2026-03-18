"""Shared base class for GiskardFoundry tools.

Defines a minimal contract for tool metadata and result formatting.
Concrete tools should implement ``run`` with domain-specific inputs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Base class that standardizes tool shape and placeholder responses."""

    name: str = "base_tool"
    description: str = "Base tool template"

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute tool logic and return a normalized payload."""

    def todo_result(self, **payload: Any) -> dict[str, Any]:
        """Return a consistent placeholder result for scaffolded tools."""
        return {
            "status": "todo",
            "tool": self.name,
            "payload": payload,
        }
