"""Context override tool scaffold.

Intended to apply temporary context constraints or overrides for planning.
Future implementation should validate override provenance and expiration.
"""

from .base_tool import BaseTool


class ContextOverrideTool(BaseTool):
    """Tool for applying context overrides."""

    name = "context_override_tool"
    description = "Apply and normalize temporary context overrides."
    input_schema = {"base_context": "dict", "overrides": "dict"}

    def run(self, base_context: dict, overrides: dict) -> dict:
        """Return placeholder merged context.

        TODO: Replace with schema-aware conflict resolution.
        """
        merged_context = dict(base_context)
        merged_context.update(overrides)
        return self.todo_result(context=merged_context)
