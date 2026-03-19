"""Job search domain agent scaffold.

This agent represents job discovery and opportunity-evaluation workflows.
"""


class JobSearchAgent:
    """Domain agent for job search workflows."""

    def __init__(self) -> None:
        """Initialize default job search agent state."""
        self.name = "jobsearch_agent"

    def run(self, request: str) -> dict:
        """Process a job search request using placeholder logic.

        TODO: Implement search provider integration and ranking.
        """
        return {
            "status": "todo",
            "agent": self.name,
            "request": request,
            "message": "Job search workflow is not implemented yet.",
        }
