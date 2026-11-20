# Memory and Usage

## Collections

| Collection | Holds | Indexes |
|---|---|---|
| `chats` | `_id` (uuid), `user_id`, `title`, `title_generated`, `summary`, `summarized_message_count`, `created_at`, `updated_at` | `(user_id, updated_at desc)` |
| `chat_messages` | `_id` (uuid), `chat_id`, `user_id`, `role` (`user`/`assistant`), `content`, `document_ids` (user) or `sources` (assistant), `created_at` | `(chat_id, created_at)` |
| `usage_logs` | one document per request: `request_id`, `user_id`, `chat_id`, `provider`, `model`, `status`, `request_started_at`, `duration_ms`, `llm_calls: [{operation, input_tokens, output_tokens, duration_ms, created_at}]` | `(user_id, request_started_at desc)` |

Messages live in their own collection because they grow without limit and are paged; the full history is kept even though the LLM only sees part of it.

## Rolling summary

The LLM receives `summary` (everything older) plus the last `CHAT_HISTORY_MESSAGES` messages verbatim. After saving a new exchange:

```python
@staticmethod
async def update_summary(chat: dict, usage_context: list[dict]) -> None:
    """Fold messages older than the last N into the summary; skip when nothing new fell out of the window."""
    messages = await ChatHelper.get_all_messages(chat["_id"])
    summary_end = max(0, len(messages) - settings.chat_history_messages)
    if summary_end <= chat.get("summarized_message_count", 0):
        return
    new_summary = await LLMService.generate_summary(chat.get("summary", ""), messages[chat.get("summarized_message_count", 0):summary_end], usage_context)
    chats = await MongoDBService.get_collection("chats")
    await chats.update_one({"_id": chat["_id"]}, {"$set": {"summary": new_summary, "summarized_message_count": summary_end, "updated_at": datetime.now(timezone.utc)}})
```

- Only messages that left the window are summarized, once each, so each summary call is small.
- History is re-sent on every request and costs tokens; keep N small (3 is a good default).
- The title is generated once from the first question and answer (`title_generated: true`), and never overwrites a title the user set.

## Usage logging

- `LLMService.invoke_model` appends one entry per call to the `usage_context` list the helper passed in; services never write usage to the database themselves.
- `ChatUtils.save_usage_log` writes one document in the helper's `finally` block with `status` `completed` or `failed`. It catches and logs its own errors (`logger.exception`) so tracking can never break the user's request.
- Tokens are the provider's numbers (`response.usage_metadata`). Totals are computed when reading (aggregation), not stored. Money cost is not tracked unless the requirement asks.
- Memory and title calls are tracked too; leaving them out undercounts usage.
