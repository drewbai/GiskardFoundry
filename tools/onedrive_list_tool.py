"""OneDrive list tool scaffold.

Intended to list files and folders from configured OneDrive scopes.
Future implementation should include pagination and filtering.
"""

from .base_tool import BaseTool


class OneDriveListTool(BaseTool):
    """Tool for listing OneDrive items."""

    name = "onedrive_list_tool"
    description = "List files and folders from configured OneDrive scopes."
    input_schema = {"path": "str"}

    def run(self, path: str = "/") -> dict:
        """Return placeholder OneDrive listing data.

        TODO: Replace with OneDrive API integration and normalized item schema.
        """
        return self.todo_result(path=path, items=[])
