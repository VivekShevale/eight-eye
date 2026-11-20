from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from langchain_core.documents import Document

from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class VectorStoreService:
    """Store and delete chunk embeddings in ChromaDB (sync; call through asyncio.to_thread)."""

    @staticmethod
    @lru_cache(maxsize=1)
    def get_collection() -> Collection:
        """Open the persistent collection once; embeddings are always supplied by EmbeddingService."""
        persist_directory = Path(settings.chroma_persist_directory)
        if not persist_directory.is_absolute():
            persist_directory = PROJECT_ROOT / persist_directory
        client = chromadb.PersistentClient(path=str(persist_directory))
        return client.get_or_create_collection(name=settings.chroma_collection_name, embedding_function=None, configuration={"hnsw": {"space": "cosine"}})

    @classmethod
    def store_chunks(cls, user_id: str, document_id: str, filename: str, chunks: list[Document], embeddings: list[list[float]]) -> int:
        """Upsert chunks with the metadata every query and citation needs."""
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match.")
        if not chunks:
            return 0
        cls.get_collection().upsert(
            ids=[f"{document_id}_{index}" for index in range(len(chunks))],
            documents=[chunk.page_content for chunk in chunks],
            embeddings=embeddings,
            metadatas=[{"user_id": user_id, "document_id": document_id, "filename": filename, "page_number": chunk.metadata["page"]} for chunk in chunks],
        )
        return len(chunks)

    @classmethod
    def delete_document_chunks(cls, user_id: str, document_id: str) -> int:
        """Delete one document's chunks, scoped to its owner; returns how many were removed."""
        collection = cls.get_collection()
        chunk_ids = collection.get(where={"$and": [{"user_id": user_id}, {"document_id": document_id}]}, include=[])["ids"]
        if chunk_ids:
            collection.delete(ids=chunk_ids)
        return len(chunk_ids)

    @classmethod
    def delete_user_chunks(cls, user_id: str) -> None:
        """Delete every chunk of a user (account deletion)."""
        cls.get_collection().delete(where={"user_id": user_id})
