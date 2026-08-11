"""OpenRouter chat-completions service with reasoning-aware tool history.

OpenRouter exposes reasoning-model output in streaming ``delta.reasoning``
fields. Pipecat 0.0.102 records the corresponding token count but otherwise
ignores those deltas, so a later tool-result request loses the reasoning that
led to the tool call. OpenRouter and Poolside both recommend returning that
reasoning with the assistant tool-call message.

This module keeps the compatibility change local to reasoning-enabled
OpenRouter routes. It also emits Pipecat thought frames so benchmark artifacts
retain the reasoning trace separately from user-visible answer text.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    FunctionCallInProgressFrame,
    LLMTextFrame,
    LLMThoughtEndFrame,
    LLMThoughtStartFrame,
    LLMThoughtTextFrame,
)
from pipecat.metrics.metrics import LLMTokenUsage
from pipecat.processors.aggregators.llm_context import LLMContext, LLMSpecificMessage
from pipecat.processors.aggregators.llm_response_universal import (
    LLMAssistantAggregator,
    LLMUserAggregator,
)
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.llm_service import FunctionCallFromLLM
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.utils.tracing.service_decorators import traced_llm


_PENDING_REASONING_ATTR = "_openrouter_reasoning_by_tool_call"


def _reasoning_delta_text(delta: Any) -> str:
    """Return OpenRouter's plaintext reasoning delta, if present."""

    for key in ("reasoning", "reasoning_content"):
        value = getattr(delta, key, None)
        if isinstance(value, str) and value:
            return value
    return ""


def _pending_reasoning(context: LLMContext) -> dict[str, str]:
    pending = getattr(context, _PENDING_REASONING_ATTR, None)
    if not isinstance(pending, dict):
        pending = {}
        setattr(context, _PENDING_REASONING_ATTR, pending)
    return pending


def _attach_pending_reasoning(context: LLMContext, tool_call_id: str) -> bool:
    """Attach saved reasoning to the matching assistant tool-call message."""

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
            # OpenRouter accepts plaintext assistant reasoning as either
            # `reasoning` or `reasoning_content`; `reasoning` is canonical.
            message["reasoning"] = reasoning
            return True
    return False


class OpenRouterReasoningAssistantAggregator(LLMAssistantAggregator):
    """Universal assistant aggregator that restores reasoning on tool calls."""

    async def _handle_function_call_in_progress(self, frame: FunctionCallInProgressFrame):
        await super()._handle_function_call_in_progress(frame)
        if not _attach_pending_reasoning(self._context, frame.tool_call_id):
            logger.debug("No pending OpenRouter reasoning for tool call {}", frame.tool_call_id)


class OpenRouterReasoningContextAggregatorPair:
    """Pair the stock user aggregator with the reasoning-aware assistant."""

    def __init__(self, context: LLMContext):
        self._user = LLMUserAggregator(context)
        self._assistant = OpenRouterReasoningAssistantAggregator(context)

    def user(self) -> LLMUserAggregator:
        return self._user

    def assistant(self) -> OpenRouterReasoningAssistantAggregator:
        return self._assistant


class OpenRouterReasoningLLMService(OpenAILLMService):
    """OpenAI-compatible service preserving OpenRouter reasoning through tools."""

    def create_reasoning_context_aggregator_pair(
        self, context: LLMContext
    ) -> OpenRouterReasoningContextAggregatorPair:
        return OpenRouterReasoningContextAggregatorPair(context)

    @traced_llm
    async def _process_context(self, context: OpenAILLMContext | LLMContext):
        functions_list: list[str] = []
        arguments_list: list[str] = []
        tool_id_list: list[str] = []
        reasoning_parts: list[str] = []
        func_idx = 0
        function_name = ""
        arguments = ""
        tool_call_id = ""
        thought_open = False

        await self.start_ttfb_metrics()

        chunk_stream = await (
            self._stream_chat_completions_specific_context(context)
            if isinstance(context, OpenAILLMContext)
            else self._stream_chat_completions_universal_context(context)
        )

        @asynccontextmanager
        async def _closing(stream):
            try:
                yield stream
            finally:
                if hasattr(stream, "aclose"):
                    await stream.aclose()
                elif hasattr(stream, "close"):
                    await stream.close()

        async def close_thought() -> None:
            nonlocal thought_open
            if thought_open:
                await self.push_frame(LLMThoughtEndFrame())
                thought_open = False

        async with _closing(chunk_stream):
            async for chunk in chunk_stream:
                if chunk.usage:
                    prompt_details = getattr(chunk.usage, "prompt_tokens_details", None)
                    completion_details = getattr(
                        chunk.usage, "completion_tokens_details", None
                    )
                    tokens = LLMTokenUsage(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                        total_tokens=chunk.usage.total_tokens,
                        cache_read_input_tokens=getattr(prompt_details, "cached_tokens", None),
                        reasoning_tokens=getattr(completion_details, "reasoning_tokens", None),
                    )
                    await self.start_llm_usage_metrics(tokens)

                if chunk.model and self.get_full_model_name() != chunk.model:
                    self.set_full_model_name(chunk.model)

                if not chunk.choices:
                    continue

                await self.stop_ttfb_metrics()
                delta = chunk.choices[0].delta
                if not delta:
                    continue

                reasoning_text = _reasoning_delta_text(delta)
                if reasoning_text:
                    if not thought_open:
                        await self.push_frame(LLMThoughtStartFrame(append_to_context=False))
                        thought_open = True
                    reasoning_parts.append(reasoning_text)
                    await self.push_frame(LLMThoughtTextFrame(reasoning_text))
                elif thought_open:
                    await close_thought()

                if delta.tool_calls:
                    tool_call = delta.tool_calls[0]
                    if tool_call.index != func_idx:
                        functions_list.append(function_name)
                        arguments_list.append(arguments or "{}")
                        tool_id_list.append(tool_call_id)
                        function_name = ""
                        arguments = ""
                        tool_call_id = ""
                        func_idx += 1
                    if tool_call.function and tool_call.function.name:
                        function_name += tool_call.function.name
                        tool_call_id = tool_call.id or tool_call_id
                    if tool_call.function and tool_call.function.arguments:
                        arguments += tool_call.function.arguments
                elif delta.content:
                    await self._push_llm_text(delta.content)
                elif (
                    hasattr(delta, "audio")
                    and delta.audio
                    and delta.audio.get("transcript")
                ):
                    await self.push_frame(LLMTextFrame(delta.audio["transcript"]))

        await close_thought()

        if function_name:
            functions_list.append(function_name)
            arguments_list.append(arguments or "{}")
            tool_id_list.append(tool_call_id)

        if functions_list:
            reasoning = "".join(reasoning_parts)
            if reasoning and isinstance(context, LLMContext):
                pending = _pending_reasoning(context)
                for current_tool_id in tool_id_list:
                    if current_tool_id:
                        pending[current_tool_id] = reasoning

            function_calls = []
            for current_name, current_arguments, current_tool_id in zip(
                functions_list,
                arguments_list,
                tool_id_list,
            ):
                try:
                    parsed_arguments = json.loads(current_arguments)
                except json.JSONDecodeError:
                    logger.warning(
                        "{}: Failed to parse function call arguments: {}",
                        self,
                        current_arguments,
                    )
                    continue
                function_calls.append(
                    FunctionCallFromLLM(
                        context=context,
                        tool_call_id=current_tool_id,
                        function_name=current_name,
                        arguments=parsed_arguments,
                    )
                )

            await self.run_function_calls(function_calls)
