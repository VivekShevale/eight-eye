# Pipeline

## Contents
1. Config fields
2. Upload
3. Delete
4. Ask
5. Routes

## 1. Config fields

Add to the project's `AppConfig` (`backend-silk/assets/config.py` pattern) and `.env.example`:

```python
embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"),
chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "5")),
retrieval_max_distance=float(os.getenv("RETRIEVAL_MAX_DISTANCE")) if os.getenv("RETRIEVAL_MAX_DISTANCE") else None,
groq_api_key=os.getenv("GROQ_API_KEY", ""),
groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
chat_history_messages=int(os.getenv("CHAT_HISTORY_MESSAGES", "3")),
max_upload_size_mb=int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")),
chroma_persist_directory=os.getenv("CHROMA_PERSIST_DIRECTORY", "chroma_data"),
chroma_collection_name=os.getenv("CHROMA_COLLECTION_NAME", "documents"),
api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
```

`validate()` checks: `chunk_size > 0`, `0 <= chunk_overlap < chunk_size`, `retrieval_top_k >= 1`, `0 <= llm_temperature <= 2`, `max_upload_size_mb > 0`, `GROQ_API_KEY` set. `uploads/` and `chroma_data/` are gitignored.

## 2. Upload

```python
class DocumentHelper:
    """Upload, list and delete the user's documents."""

    @classmethod
    async def upload_document(cls, file: UploadFile, user_id: str) -> DocumentResponse:
        """Validate, store, index and record a PDF; undo everything written if a step fails."""
        content = await cls.read_valid_pdf(file)
        document_id = str(uuid4())
        file_path = settings.upload_directory / f"{document_id}.pdf"
        await asyncio.to_thread(file_path.write_bytes, content)
        try:
            extracted = await asyncio.to_thread(PDFService.extract_document, file_path)
            chunks = ChunkingService.split_pages(extracted["pages"])
            embeddings = await asyncio.to_thread(EmbeddingService.generate_embeddings, [chunk.page_content for chunk in chunks])
            await asyncio.to_thread(VectorStoreService.store_chunks, user_id, document_id, file.filename, chunks, embeddings)
            record = cls.build_document_record(document_id, user_id, file, content, extracted, len(chunks))
            documents = await MongoDBService.get_collection("documents")
            await documents.insert_one(record)
        except ValueError as exc:
            await cls.remove_partial_upload(user_id, document_id, file_path)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception:
            await cls.remove_partial_upload(user_id, document_id, file_path)
            raise
        logger.info("Document indexed | document_id=%s | user_id=%s | pages=%s | chunks=%s", document_id, user_id, extracted["total_pages"], len(chunks))
        return DocumentResponse.from_document(record)
```

- `read_valid_pdf`: extension `.pdf`, read at most `max_bytes + 1` (more → 413), starts with `b"%PDF-"` (else 400), not empty.
- `remove_partial_upload`: delete chunks (scoped), the file, and the record if it was inserted; log failures of the cleanup itself without hiding the original error.
- The original filename is metadata only; the stored file name is always the UUID.
- Response: `document_id`, `filename`, `file_size`, `total_pages`, `total_chunks`, `status: "indexed"`, `uploaded_at`.

## 3. Delete

1. Find the record by `{"_id": document_id, "user_id": user_id}` → 404 if missing.
2. Delete the chunks (`VectorStoreService.delete_document_chunks`), then the file, then the record.
3. Return 204.

## 4. Ask

```python
@classmethod
async def send_message(cls, user_id: str, chat_id: str, payload: ChatMessageRequest) -> ChatMessageResponse:
    """Answer a question inside a chat, with memory, sources and usage tracking."""
    chat = await cls.get_owned_chat(user_id, chat_id)
    await ChatUtils.validate_documents(user_id, payload.document_ids)
    recent_messages = await cls.get_recent_messages(chat_id, settings.chat_history_messages)
    usage_context: list[dict] = []
    started_at = datetime.now(timezone.utc)
    status = "failed"
    try:
        result = await RAGService.ask_question(user_id, payload.question, payload.top_k, payload.document_ids, chat.get("summary", ""), recent_messages, usage_context)
        messages = await cls.save_exchange(user_id, chat_id, payload, result)
        await cls.update_summary(chat, usage_context)
        status = "completed"
        return ChatMessageResponse.from_messages(messages)
    finally:
        await ChatUtils.save_usage_log(user_id, chat_id, started_at, status, usage_context)
```

- `top_k` in the request is optional (`None` → `RETRIEVAL_TOP_K`), bounded `1..20`.
- `document_ids` empty means "all of the user's documents".
- The user message stores its `document_ids`; the assistant message stores its `sources`.

## 5. Routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/documents` | upload (201) |
| GET | `/api/v1/documents` | list the user's documents (paginated) |
| GET | `/api/v1/documents/{document_id}` | one document's metadata |
| DELETE | `/api/v1/documents/{document_id}` | delete file, chunks, record (204) |
| POST | `/api/v1/chats` | new chat (201) |
| GET | `/api/v1/chats` | list chats |
| GET | `/api/v1/chats/{chat_id}` | chat with messages (paginated) |
| PATCH | `/api/v1/chats/{chat_id}` | rename |
| DELETE | `/api/v1/chats/{chat_id}` | delete chat and its messages (204) |
| POST | `/api/v1/chats/{chat_id}/messages` | ask (201) |

Only build the routes the requirement needs (a download endpoint or filename search only when asked).
