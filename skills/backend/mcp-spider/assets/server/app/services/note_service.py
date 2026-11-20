from datetime import datetime, timezone
from uuid import uuid4

from fastmcp.exceptions import ToolError

from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


class NoteService:
    """Example integration behind the tools. Replace the in-memory dict with the real system
    (MongoDB via mongodb-silk, Google APIs, ...); tools and their contract stay the same.
    """

    MAX_RESULTS = 50

    def __init__(self) -> None:
        self.notes: dict[str, dict[str, dict]] = {}

    def create_note(self, user_id: str, title: str, content: str) -> dict:
        """Store a note for the user and return its id and title."""
        if not title.strip():
            raise ToolError("INVALID_ARGUMENT: Title cannot be empty.")
        note = {"id": str(uuid4()), "title": title.strip(), "content": content, "created_at": datetime.now(timezone.utc).isoformat()}
        self.notes.setdefault(user_id, {})[note["id"]] = note
        logger.info("Note created | note_id=%s | user_id=%s", note["id"], user_id)
        return {"id": note["id"], "title": note["title"]}

    def search_notes(self, user_id: str, query: str, max_results: int) -> list[dict]:
        """Ids and titles of the user's notes whose title or content contains the query."""
        term = query.lower().strip()
        matches = [note for note in self.notes.get(user_id, {}).values() if term in note["title"].lower() or term in note["content"].lower()]
        return [{"id": note["id"], "title": note["title"]} for note in matches[: min(max_results, self.MAX_RESULTS)]]

    def read_note(self, user_id: str, note_id: str) -> dict:
        """One note of the user; another user's note is reported as missing."""
        note = self.notes.get(user_id, {}).get(note_id)
        if note is None:
            raise ToolError("NOT_FOUND: Note not found.")
        return note
