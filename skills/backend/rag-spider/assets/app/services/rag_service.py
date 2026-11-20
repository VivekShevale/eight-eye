import asyncio

from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService

NO_ANSWER_MESSAGE = "I couldn't find information about this in your uploaded documents."


class RAGService:
    """Orchestrate retrieval and answer generation; each step lives in its own service."""

    @staticmethod
    def build_context(chunks: list[dict]) -> str:
        """Number each chunk with its file and page so the answer can cite it."""
        return "\n\n".join(
            f"Source {index}\nFilename: {chunk['metadata']['filename']}\nPage: {chunk['metadata']['page_number']}\nContent: {chunk['content']}"
            for index, chunk in enumerate(chunks, start=1)
        )

    @staticmethod
    def build_sources(chunks: list[dict]) -> list[dict]:
        """One source per (document, page), in retrieval order."""
        sources, seen = [], set()
        for chunk in chunks:
            metadata = chunk["metadata"]
            key = (metadata["document_id"], metadata["page_number"])
            if key not in seen:
                seen.add(key)
                sources.append({"document_id": metadata["document_id"], "filename": metadata["filename"], "page_number": metadata["page_number"]})
        return sources

    @classmethod
    async def ask_question(cls, user_id: str, question: str, top_k: int | None = None, document_ids: list[str] | None = None, summary: str = "", chat_history: list[dict] | None = None, usage_context: list[dict] | None = None) -> dict:
        """Retrieve, then answer; with no relevant chunks, answer without calling the LLM."""
        chunks = await asyncio.to_thread(RetrievalService.search_chunks, user_id, question, top_k, document_ids)
        if not chunks:
            return {"answer": NO_ANSWER_MESSAGE, "sources": []}
        answer = await LLMService.generate_answer(question, cls.build_context(chunks), summary, chat_history, usage_context)
        return {"answer": answer, "sources": cls.build_sources(chunks)}
