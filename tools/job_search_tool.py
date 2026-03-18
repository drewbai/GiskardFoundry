"""Job search tool scaffold.

Intended to search job opportunities from configured sources.
Future implementation should include provider adapters and retry handling.
"""

from .base_tool import BaseTool


class JobSearchTool(BaseTool):
    """Tool for searching jobs from external providers."""

    name = "job_search_tool"
    description = "Search configured job providers and normalize matches."
    input_schema = {"query": "str"}

    def run(self, query: str) -> dict:
        """Return placeholder job search results.

        TODO: Replace with provider integrations and result normalization.
        """
        return self.todo_result(query=query, results=[])
