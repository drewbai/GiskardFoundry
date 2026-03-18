"""Job search agent scaffold.

Defines the initial class interface for job discovery and relevance scoring.
Future versions should orchestrate search and semantic-evaluation tools.
"""


class JobSearchAgent:
    """Domain agent for job search workflows."""

    def __init__(self) -> None:
        """Initialize default job search agent state."""
        self.name = "jobsearch_agent"

    def plan(self, objective: str) -> dict:
        """Create a placeholder job search plan.

        TODO: Add query strategies, filters, and ranking criteria.
        """
        return {"objective": objective, "search_plan": []}

    def run(self, objective: str) -> dict:
        """Execute placeholder job search workflow.

        TODO: Connect job search and semantic scoring tools.
        """
        return {"status": "todo", "objective": objective}
