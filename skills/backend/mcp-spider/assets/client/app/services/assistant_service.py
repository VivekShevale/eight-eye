from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from app.config import settings
from app.services.llm_service import LLMService
from app.services.mcp_client_service import MCPClientService
from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


class AssistantService:
    """LLM answers with MCP tools: discover, call one by one, stop at the first failure, cap the rounds."""

    # Fixed replies for known tool error codes; the LLM never writes these, so it can't invent results.
    FAILURE_MESSAGES = {
        "GOOGLE_ACCOUNT_NOT_CONNECTED": "Your Google account is not connected. Connect it first, then try again.",
        "NOT_FOUND": "I couldn't find what you asked for.",
        "TOOL_NOT_AVAILABLE": "That action isn't available right now.",
    }
    DEFAULT_FAILURE_MESSAGE = "The requested action couldn't be completed. Please try again."

    @staticmethod
    def convert_mcp_tools(mcp_tools: list) -> list[dict]:
        """MCP tool definitions to the OpenAI-style schemas bind_tools expects (exposing, not executing)."""
        return [
            {"type": "function", "function": {"name": tool.name, "description": tool.description or tool.name, "parameters": tool.inputSchema}}
            for tool in mcp_tools
        ]

    @classmethod
    def failure_message(cls, error_code: str) -> str:
        """User-facing text for a failed tool call."""
        return cls.FAILURE_MESSAGES.get(error_code, cls.DEFAULT_FAILURE_MESSAGE)

    @staticmethod
    def build_final_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
        """After the round limit: drop tool-call messages and hand the tool results over as plain text."""
        final_messages = [message for message in messages if not isinstance(message, ToolMessage) and not (isinstance(message, AIMessage) and message.tool_calls)]
        tool_results = [f"{message.name}: {message.content}" for message in messages if isinstance(message, ToolMessage)]
        if tool_results:
            final_messages.append(HumanMessage(content="Don't call more tools. Answer using only these tool results:\n\n" + "\n\n".join(tool_results)))
        return final_messages

    @classmethod
    async def run_tool_calls(cls, response: AIMessage, messages: list[BaseMessage], access_token: str, allowed_tools: set[str]) -> str | None:
        """Run the model's tool calls in order; return a fixed reply as soon as one fails, else None."""
        for tool_call in response.tool_calls:
            if tool_call["name"] not in allowed_tools:
                logger.warning("Tool call rejected | tool=%s | reason=not_available", tool_call["name"])
                return cls.failure_message("TOOL_NOT_AVAILABLE")
            result = await MCPClientService.call_tool(access_token, tool_call["name"], tool_call["args"])
            if not result["ok"]:
                logger.warning("Tool failed | tool=%s | error_code=%s", tool_call["name"], result["error_code"])
                return cls.failure_message(result["error_code"])
            messages.append(ToolMessage(content=result["content"], tool_call_id=tool_call["id"], name=tool_call["name"]))
        return None

    @classmethod
    async def generate_response(cls, messages: list[BaseMessage], access_token: str, usage_context: list[dict] | None = None) -> str:
        """Let the model use tools for up to MCP_MAX_TOOL_ROUNDS rounds, then force a final answer."""
        tools = cls.convert_mcp_tools(await MCPClientService.list_tools(access_token))
        allowed_tools = {tool["function"]["name"] for tool in tools}
        for _ in range(settings.mcp_max_tool_rounds):
            response = await LLMService.invoke_model(messages, "assistant_response", usage_context, tools)
            if not response.tool_calls:
                return str(response.content)
            messages.append(response)
            failure = await cls.run_tool_calls(response, messages, access_token, allowed_tools)
            if failure:
                return failure
        final = await LLMService.invoke_model(cls.build_final_messages(messages), "assistant_final_response", usage_context)
        return str(final.content)
