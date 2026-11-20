from datetime import datetime, timezone
from functools import lru_cache
from time import perf_counter

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_groq import ChatGroq

from app.config import settings
from app.prompts.rag_prompt import RAG_PROMPT
from app.prompts.summary_prompt import SUMMARY_PROMPT


class LLMService:
    """Chat model calls; every call records provider-reported tokens and duration in usage_context."""

    @staticmethod
    @lru_cache(maxsize=1)
    def get_model() -> ChatGroq:
        """Create the chat model once; model and temperature come from .env (restart after changing)."""
        return ChatGroq(model=settings.groq_model, temperature=settings.llm_temperature, api_key=settings.groq_api_key, max_retries=2)

    @classmethod
    async def invoke_model(cls, messages: list[BaseMessage], operation: str, usage_context: list[dict] | None = None, tools: list[dict] | None = None):
        """Call the model and append one usage entry (no estimates: tokens come from the provider)."""
        started_at = perf_counter()
        model = cls.get_model().bind_tools(tools) if tools else cls.get_model()
        response = await model.ainvoke(messages)
        usage = response.usage_metadata or {}
        if usage_context is not None:
            usage_context.append({
                "operation": operation,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "created_at": datetime.now(timezone.utc),
            })
        return response

    @staticmethod
    def build_history_messages(chat_history: list[dict] | None) -> list[BaseMessage]:
        """Convert stored {"role", "content"} messages into LangChain messages."""
        message_types = {"user": HumanMessage, "assistant": AIMessage}
        return [message_types[message["role"]](content=message["content"]) for message in chat_history or [] if message["role"] in message_types]

    @classmethod
    async def generate_answer(cls, question: str, context: str, summary: str = "", chat_history: list[dict] | None = None, usage_context: list[dict] | None = None) -> str:
        """Answer from the retrieved context only; Markdown is kept as-is."""
        messages = RAG_PROMPT.format_messages(
            context=context,
            question=question,
            summary=summary or "No previous conversation.",
            chat_history=cls.build_history_messages(chat_history),
        )
        response = await cls.invoke_model(messages, "generate_answer", usage_context)
        return str(response.content)

    @classmethod
    async def generate_summary(cls, summary: str, messages: list[dict], usage_context: list[dict] | None = None) -> str:
        """Fold older messages into the rolling conversation summary."""
        if not messages:
            return summary
        message_text = "\n\n".join(f'{message["role"].capitalize()}: {message["content"]}' for message in messages)
        prompt_messages = SUMMARY_PROMPT.format_messages(summary=summary or "No previous summary.", messages=message_text)
        response = await cls.invoke_model(prompt_messages, "generate_summary", usage_context)
        return str(response.content).strip()
