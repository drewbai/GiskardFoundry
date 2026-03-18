"""GTD agent scaffold.

Defines the baseline class interface for GTD-oriented planning and execution.
Future versions should connect planning tools and context overlays.
"""


class GTDAgent:
    """Domain agent for GTD task planning workflows."""

    def __init__(self) -> None:
        """Initialize default GTD agent state."""
        self.name = "gtd_agent"

    def plan(self, objective: str) -> dict:
        """Return a placeholder GTD plan object.

        TODO: Integrate task decomposition and scoring tools.
        """
        return {"objective": objective, "plan": []}

    def run(self, objective: str) -> dict:
        """Execute placeholder GTD workflow.

        TODO: Run planning pipeline and produce actionable outputs.
        """
        return {"status": "todo", "objective": objective}
