from fastmcp import FastMCP
from fastmcp.tools import tool

from app.services.note_service import NoteService
from app.utils.auth_utils import AuthUtils


class NoteTools:
    """MCP tools for notes: thin like routes, the user comes from the token, the service does the work."""

    def __init__(self, note_service: NoteService) -> None:
        self.note_service = note_service

    @tool()
    def create_note(self, title: str, content: str) -> dict:
        """Create a note. Returns its id and title."""
        return self.note_service.create_note(AuthUtils.get_user_id(), title, content)

    @tool()
    def search_notes(self, query: str, max_results: int = 10) -> list[dict]:
        """Search notes by text. Returns ids and titles, not full content."""
        return self.note_service.search_notes(AuthUtils.get_user_id(), query, max_results)

    @tool()
    def read_note(self, note_id: str) -> dict:
        """Read one note's full content by id."""
        return self.note_service.read_note(AuthUtils.get_user_id(), note_id)

    def register_tools(self, mcp: FastMCP) -> None:
        """Expose these tools on the server."""
        mcp.add_tool(self.create_note)
        mcp.add_tool(self.search_notes)
        mcp.add_tool(self.read_note)
