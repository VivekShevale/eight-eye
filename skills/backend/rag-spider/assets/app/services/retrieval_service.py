from app.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.vectorstore_service import VectorStoreService


class RetrievalService:
    """Semantic search over the user's own chunks (sync; call through asyncio.to_thread)."""

    @staticmethod
    def build_where_filter(user_id: str, document_ids: list[str] | None) -> dict:
        """Always scope by user; narrow to selected documents only when some are given."""
        if not document_ids:
            return {"user_id": user_id}
        return {"$and": [{"user_id": user_id}, {"document_id": {"$in": document_ids}}]}

    @classmethod
    def search_chunks(cls, user_id: str, query: str, top_k: int | None = None, document_ids: list[str] | None = None) -> list[dict]:
        """Top-k chunks, dropping ones beyond RETRIEVAL_MAX_DISTANCE when that is configured."""
        if not query.strip():
            raise ValueError("Search query cannot be empty.")
        top_k = settings.retrieval_top_k if top_k is None else top_k
        query_embedding = EmbeddingService.generate_embeddings([query])[0]
        results = VectorStoreService.get_collection().query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=cls.build_where_filter(user_id, document_ids),
            include=["documents", "metadatas", "distances"],
        )
        chunks = [
            {"chunk_id": chunk_id, "content": results["documents"][0][index], "metadata": results["metadatas"][0][index], "distance": results["distances"][0][index]}
            for index, chunk_id in enumerate(results["ids"][0])
        ]
        if settings.retrieval_max_distance is None:
            return chunks
        return [chunk for chunk in chunks if chunk["distance"] <= settings.retrieval_max_distance]
