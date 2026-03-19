"""GTD domain agent scaffold.

This agent represents Getting Things Done (GTD) planning workflows such as task
capture, decomposition, and prioritization.
"""


class GTDAgent:
    """Domain agent for GTD planning workflows."""

    def __init__(self) -> None:
        """Initialize default GTD agent state."""
        self.name = "gtd_agent"

    def run(self, request: str) -> dict:
        """Process a GTD request using placeholder logic.

        TODO: Implement GTD planning and prioritization behavior.
        """
        return {
            "status": "todo",
            "agent": self.name,
            "request": request,
            "message": "GTD workflow is not implemented yet.",
        }
