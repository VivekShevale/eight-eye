from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings


class EmbeddingService:
    """Local embedding model (separate from the chat LLM). Sync and CPU-heavy: call through asyncio.to_thread."""

    @staticmethod
    @lru_cache(maxsize=1)
    def get_model() -> SentenceTransformer:
        """Load the model named in EMBEDDING_MODEL_NAME once per process."""
        return SentenceTransformer(settings.embedding_model_name)

    @classmethod
    def generate_embeddings(cls, texts: list[str]) -> list[list[float]]:
        """Normalized embeddings, so cosine distance behaves consistently."""
        if not texts:
            return []
        embeddings = cls.get_model().encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
        return embeddings.tolist()
