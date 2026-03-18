"""Tool registry scaffold for GiskardFoundry.

Provides a minimal mapping from manifest tool names to tool classes.
Future expansion should support lazy loading and dependency injection.
"""

from __future__ import annotations

from typing import Type

from .base_tool import BaseTool
from .context_override_tool import ContextOverrideTool
from .job_search_tool import JobSearchTool
from .onedrive_list_tool import OneDriveListTool
from .onenote_read_tool import OneNoteReadTool
from .onenote_write_tool import OneNoteWriteTool
from .score_tool import ScoreTool
from .semantic_description_tool import SemanticDescriptionTool
from .task_planner_tool import TaskPlannerTool

TOOL_REGISTRY: dict[str, Type[BaseTool]] = {
    "onedrive_list_tool": OneDriveListTool,
    "onenote_read_tool": OneNoteReadTool,
    "onenote_write_tool": OneNoteWriteTool,
    "semantic_description_tool": SemanticDescriptionTool,
    "task_planner_tool": TaskPlannerTool,
    "context_override_tool": ContextOverrideTool,
    "score_tool": ScoreTool,
    "job_search_tool": JobSearchTool,
}


def create_tool(tool_name: str) -> BaseTool | None:
    """Instantiate a tool by name from the registry.

    TODO: Add constructor dependency handling and better error reporting.
    """
    tool_class = TOOL_REGISTRY.get(tool_name)
    if tool_class is None:
        return None
    return tool_class()
