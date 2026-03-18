"""OneNote read tool scaffold.

Intended to retrieve note content from a target page or section.
Future implementation should support rich content normalization.
"""

from .base_tool import BaseTool


class OneNoteReadTool(BaseTool):
    """Tool for reading OneNote content."""

    name = "onenote_read_tool"
    description = "Read page or section content from OneNote."
    input_schema = {"note_id": "str"}

    def run(self, note_id: str) -> dict:
        """Return placeholder OneNote read result.

        TODO: Replace with OneNote API read operation.
        """
        return self.todo_result(note_id=note_id, content="")
