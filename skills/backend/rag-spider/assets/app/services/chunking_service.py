from functools import lru_cache

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


class ChunkingService:
    """Split page text into overlapping chunks that keep their page number."""

    @staticmethod
    @lru_cache(maxsize=1)
    def get_splitter() -> RecursiveCharacterTextSplitter:
        """Create the splitter once from CHUNK_SIZE and CHUNK_OVERLAP."""
        return RecursiveCharacterTextSplitter(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap, separators=["\n\n", "\n", " ", ""])

    @classmethod
    def split_pages(cls, pages: list[dict]) -> list[Document]:
        """Split pages; every chunk carries metadata {"page": n} for citations."""
        documents = [Document(page_content=page["text"], metadata={"page": page["page_number"]}) for page in pages]
        return cls.get_splitter().split_documents(documents)
