"""Baseten/vLLM Qwen service preserving reasoning through tool continuations."""

from __future__ import annotations

from loguru import logger
from pipecat.frames.frames import FunctionCallInProgressFrame
from pipecat.processors.aggregators.llm_context import LLMContext, LLMSpecificMessage
from pipecat.processors.aggregators.llm_response_universal import (
    LLMAssistantAggregator,
    LLMUserAggregator,
)

from openrouter_reasoning_service import (
    OpenRouterReasoningLLMService,
    _pending_reasoning,
)


def _attach_pending_reasoning_content(context: LLMContext, tool_call_id: str) -> bool:
    reasoning = _pending_reasoning(context).pop(tool_call_id, "")
    if not reasoning:
        return False

    for message in reversed(context.get_messages()):
        if isinstance(message, LLMSpecificMessage) or message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        if any(call.get("id") == tool_call_id for call in tool_calls if isinstance(call, dict)):
            message["reasoning_content"] = reasoning
            return True
    return False


class BasetenQwenReasoningAssistantAggregator(LLMAssistantAggregator):
    """Restore Qwen's ``reasoning_content`` on assistant tool-call messages."""

    async def _handle_function_call_in_progress(self, frame: FunctionCallInProgressFrame):
        await super()._handle_function_call_in_progress(frame)
        if not _attach_pending_reasoning_content(self._context, frame.tool_call_id):
            logger.debug("No pending Baseten Qwen reasoning for tool call {}", frame.tool_call_id)


class BasetenQwenReasoningContextAggregatorPair:
    def __init__(self, context: LLMContext):
        self._user = LLMUserAggregator(context)
        self._assistant = BasetenQwenReasoningAssistantAggregator(context)

    def user(self) -> LLMUserAggregator:
        return self._user

    def assistant(self) -> BasetenQwenReasoningAssistantAggregator:
        return self._assistant


class BasetenQwenReasoningLLMService(OpenRouterReasoningLLMService):
    """Reasoning-aware OpenAI-compatible service for dedicated Baseten Qwen."""

    def create_reasoning_context_aggregator_pair(
        self, context: LLMContext
    ) -> BasetenQwenReasoningContextAggregatorPair:
        return BasetenQwenReasoningContextAggregatorPair(context)
