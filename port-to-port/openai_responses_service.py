"""OpenAI Responses API shim for benchmark text-and-tool runs."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
from typing import Any, Callable

from loguru import logger
from openai import NOT_GIVEN
from pipecat.adapters.services.open_ai_adapter import OpenAILLMInvocationParams
from pipecat.metrics.metrics import LLMTokenUsage
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.llm_service import FunctionCallFromLLM
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.utils.tracing.service_decorators import traced_llm


class ResponsesRequestTimeout(TimeoutError):
    """One Responses inference exceeded its total wall deadline."""


class ResponsesStreamIdleTimeout(TimeoutError):
    """A Responses stream produced no event before its idle deadline."""


class ResponsesProtocolError(RuntimeError):
    """A Responses stream ended without a terminal event."""


class OpenAIResponsesLLMService(OpenAILLMService):
    """OpenAI-compatible LLM service backed by the Responses API."""

    def __init__(
        self,
        *,
        request_timeout_secs: float | None = None,
        stream_idle_timeout_secs: float | None = None,
        benchmark_observability_enabled: bool = False,
        **kwargs: Any,
    ) -> None:
        self._request_timeout_secs = (
            float(request_timeout_secs) if request_timeout_secs is not None else None
        )
        self._stream_idle_timeout_secs = (
            float(stream_idle_timeout_secs) if stream_idle_timeout_secs is not None else None
        )
        self._benchmark_observability_enabled = bool(benchmark_observability_enabled)
        self._responses_traces: list[dict[str, Any]] = []
        self._benchmark_outcome_callback: Callable[[dict[str, Any]], None] | None = None
        super().__init__(**kwargs)
        if self._benchmark_observability_enabled:
            # Keep every billable attempt visible to the outer runner. SDK
            # retries can perform provider work that is absent from the final
            # response usage, which would make a hard cumulative budget
            # unauditable. Infrastructure replacement therefore happens only
            # at the episode runner, where it gets its own JSON/log/ledger row.
            self._client.max_retries = 0
            self._benchmark_sdk_max_retries = 0
        else:
            self._benchmark_sdk_max_retries = None

    def set_benchmark_outcome_callback(
        self, callback: Callable[[dict[str, Any]], None] | None
    ) -> None:
        self._benchmark_outcome_callback = callback

    def get_responses_traces(self) -> list[dict[str, Any]]:
        # Round-trip through JSON so callers cannot mutate service-owned state.
        return json.loads(json.dumps(getattr(self, "_responses_traces", [])))

    def _setting(self, key: str, default: Any = NOT_GIVEN) -> Any:
        settings = getattr(self, "_settings", {})
        if isinstance(settings, dict):
            return settings.get(key, default)
        return getattr(settings, key, default)

    def _context_to_openai_params(
        self, context: LLMContext | OpenAILLMContext
    ) -> OpenAILLMInvocationParams:
        if isinstance(context, LLMContext):
            adapter = self.get_llm_adapter()
            return adapter.get_llm_invocation_params(context)

        return OpenAILLMInvocationParams(
            messages=context.messages,
            tools=context.tools,
            tool_choice=context.tool_choice,
        )

    @staticmethod
    def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    @staticmethod
    def _is_not_given(value: Any) -> bool:
        return value is NOT_GIVEN

    @staticmethod
    def _header_request_id(headers: Any) -> str | None:
        getter = getattr(headers, "get", None)
        if not callable(getter):
            return None
        value = getter("x-request-id")
        return str(value) if value else None

    def _stream_request_id(self, stream: Any) -> str | None:
        for response_attr in ("response", "_response"):
            response = getattr(stream, response_attr, None)
            request_id = self._header_request_id(getattr(response, "headers", None))
            if request_id:
                return request_id
        return None

    @classmethod
    def _usage_trace(cls, response: Any) -> dict[str, int | None] | None:
        usage = cls._get_attr(response, "usage")
        if usage is None:
            return None
        input_details = cls._get_attr(usage, "input_tokens_details")
        output_details = cls._get_attr(usage, "output_tokens_details")
        return {
            "input_tokens": cls._get_attr(usage, "input_tokens"),
            "cached_tokens": cls._get_attr(input_details, "cached_tokens"),
            "cache_write_tokens": cls._get_attr(input_details, "cache_write_tokens"),
            "output_tokens": cls._get_attr(usage, "output_tokens"),
            "reasoning_tokens": cls._get_attr(output_details, "reasoning_tokens"),
            "total_tokens": cls._get_attr(usage, "total_tokens"),
        }

    @classmethod
    def _error_trace(cls, error: Any) -> dict[str, Any] | None:
        if error is None:
            return None
        result: dict[str, Any] = {}
        for key in ("code", "message", "type", "param"):
            value = cls._get_attr(error, key)
            if value is not None:
                result[key] = str(value)[:500]
        return result or None

    def _request_trace(self, params: dict[str, Any]) -> dict[str, Any]:
        reasoning = params.get("reasoning")
        return {
            "api_surface": "responses",
            "requested_model": params.get("model"),
            "requested_effective_effort": (
                reasoning.get("effort") if isinstance(reasoning, dict) else None
            ),
            "requested_max_output_tokens": params.get("max_output_tokens"),
            "tools_present": bool(params.get("tools")),
            "store": params.get("store"),
            "service_tier_present": "service_tier" in params,
            "request_timeout_secs": getattr(self, "_request_timeout_secs", None),
            "stream_idle_timeout_secs": getattr(self, "_stream_idle_timeout_secs", None),
            "sdk_max_retries": getattr(self, "_benchmark_sdk_max_retries", None),
            "openai_sdk_version": importlib.metadata.version("openai"),
        }

    def _terminal_trace(
        self,
        *,
        params: dict[str, Any],
        response: Any,
        event_types: list[str],
        request_id: str | None,
    ) -> dict[str, Any]:
        incomplete = self._get_attr(response, "incomplete_details")
        return {
            **self._request_trace(params),
            "request_id": request_id or self._get_attr(response, "_request_id"),
            "response_id": self._get_attr(response, "id"),
            "resolved_model": self._get_attr(response, "model"),
            "response_status": self._get_attr(response, "status"),
            "returned_service_tier": self._get_attr(response, "service_tier"),
            "incomplete_reason": self._get_attr(incomplete, "reason"),
            "error": self._error_trace(self._get_attr(response, "error")),
            "usage": self._usage_trace(response),
            "event_types": list(event_types),
        }

    def _exception_trace(
        self,
        *,
        params: dict[str, Any],
        exc: BaseException,
        event_types: list[str],
        request_id: str | None,
    ) -> dict[str, Any]:
        body = getattr(exc, "body", None)
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            body = body["error"]
        error = self._error_trace(body) or {}
        error.setdefault("type", type(exc).__name__)
        error.setdefault("message", str(exc)[:500])
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            error["status_code"] = status_code
        return {
            **self._request_trace(params),
            "request_id": request_id or getattr(exc, "request_id", None),
            "response_id": None,
            "resolved_model": None,
            "response_status": "error",
            "returned_service_tier": None,
            "incomplete_reason": None,
            "error": error,
            "usage": None,
            "event_types": list(event_types),
        }

    def _record_trace(self, trace: dict[str, Any]) -> None:
        traces = getattr(self, "_responses_traces", None)
        if not isinstance(traces, list):
            traces = []
            self._responses_traces = traces
        trace = dict(trace)
        trace["trace_index"] = len(traces) + 1
        traces.append(trace)
        callback = getattr(self, "_benchmark_outcome_callback", None)
        if callable(callback):
            callback(dict(trace))

    async def _iter_response_events(
        self,
        params: dict[str, Any],
        state: dict[str, Any],
    ):
        request_timeout = getattr(self, "_request_timeout_secs", None)
        idle_timeout = getattr(self, "_stream_idle_timeout_secs", None)
        strict_terminal = bool(
            getattr(self, "_benchmark_observability_enabled", False)
        )
        if request_timeout is None and idle_timeout is None:
            async with self._client.responses.stream(**params) as stream:
                state["request_id"] = self._stream_request_id(stream)
                async for event in stream:
                    yield event
            return

        request_timeout = float(request_timeout) if request_timeout is not None else None
        idle_timeout = float(idle_timeout) if idle_timeout is not None else None
        try:
            async with asyncio.timeout(request_timeout):
                async with self._client.responses.stream(**params) as stream:
                    state["request_id"] = self._stream_request_id(stream)
                    iterator = stream.__aiter__()
                    while True:
                        try:
                            event = await asyncio.wait_for(anext(iterator), timeout=idle_timeout)
                        except StopAsyncIteration:
                            break
                        except asyncio.TimeoutError as exc:
                            raise ResponsesStreamIdleTimeout(
                                f"Responses stream idle for more than {idle_timeout}s"
                            ) from exc
                        yield event
                        if strict_terminal and getattr(event, "type", None) in {
                            "response.completed",
                            "response.incomplete",
                            "response.failed",
                            "response.error",
                            "error",
                        }:
                            break
        except ResponsesStreamIdleTimeout:
            raise
        except asyncio.TimeoutError as exc:
            raise ResponsesRequestTimeout(
                f"Responses request exceeded total timeout {request_timeout}s"
            ) from exc

    @staticmethod
    def _to_json_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    def _message_to_responses_items(self, message: Any) -> list[dict[str, Any]]:
        role = self._get_attr(message, "role")
        content = self._get_attr(message, "content")
        tool_calls = self._get_attr(message, "tool_calls")
        items: list[dict[str, Any]] = []

        if role == "tool":
            tool_call_id = self._get_attr(message, "tool_call_id")
            if tool_call_id:
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": tool_call_id,
                        "output": self._to_json_text(content),
                    }
                )
            return items

        if role == "assistant" and tool_calls:
            for tool_call in tool_calls:
                function = self._get_attr(tool_call, "function") or {}
                function_name = self._get_attr(function, "name")
                arguments = self._get_attr(function, "arguments", "{}")
                call_id = self._get_attr(tool_call, "id")
                if function_name and call_id:
                    items.append(
                        {
                            "type": "function_call",
                            "call_id": call_id,
                            "name": function_name,
                            "arguments": arguments if isinstance(arguments, str) else "{}",
                        }
                    )

        if content is None:
            return items

        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    if part:
                        text_parts.append(part)
                    continue
                part_type = self._get_attr(part, "type")
                if part_type in {"text", "output_text", "input_text"}:
                    text = self._get_attr(part, "text")
                    if text:
                        text_parts.append(text)
            content_text = "\n".join(text_parts).strip()
        else:
            content_text = str(content)

        if role in {"system", "developer", "user", "assistant"} and content_text:
            # This easy-input representation is used for new user/developer
            # messages and as a fallback for assistant history that did not
            # originate from this service. Remembered assistant outputs are
            # replaced with their exact provider output items below.
            items.append(
                {
                    "type": "message",
                    "role": role,
                    "content": [{"type": "input_text", "text": content_text}],
                }
            )

        return items

    def _messages_to_responses_input(self, messages: list[Any]) -> list[dict[str, Any]]:
        """Convert Pipecat history using the proven aiewf-eval wire contract.

        Responses continuations are reconstructed from standard assistant
        function calls plus function-call outputs. Provider-owned reasoning
        payloads are intentionally neither requested nor retained.
        """

        return [
            item
            for message in messages
            for item in self._message_to_responses_items(message)
        ]

    def _tools_to_responses_tools(self, tools: Any) -> Any:
        if self._is_not_given(tools):
            return NOT_GIVEN

        adapter = self.get_llm_adapter()
        chat_tools = adapter.from_standard_tools(tools)
        if self._is_not_given(chat_tools):
            return NOT_GIVEN

        response_tools: list[dict[str, Any]] = []
        for tool in chat_tools:
            if self._get_attr(tool, "type") != "function":
                continue
            fn = self._get_attr(tool, "function") or {}
            name = self._get_attr(fn, "name")
            if not name:
                continue
            resp_tool: dict[str, Any] = {
                "type": "function",
                "name": name,
                "parameters": self._get_attr(fn, "parameters"),
            }
            strict = self._get_attr(fn, "strict")
            if strict is not None and not self._is_not_given(strict):
                resp_tool["strict"] = strict
            description = self._get_attr(fn, "description")
            if description:
                resp_tool["description"] = description
            response_tools.append(resp_tool)
        return response_tools if response_tools else NOT_GIVEN

    def _tool_choice_to_responses_tool_choice(self, tool_choice: Any) -> Any:
        if self._is_not_given(tool_choice):
            return NOT_GIVEN
        if isinstance(tool_choice, str):
            return tool_choice
        if isinstance(tool_choice, dict):
            if (
                tool_choice.get("type") == "function"
                and isinstance(tool_choice.get("function"), dict)
                and tool_choice["function"].get("name")
            ):
                return {"type": "function", "name": tool_choice["function"]["name"]}
            return tool_choice
        return tool_choice

    def _responses_request_params(self, context: LLMContext | OpenAILLMContext) -> dict[str, Any]:
        params_from_context = self._context_to_openai_params(context)
        messages = params_from_context.get("messages") or []
        tools = params_from_context.get("tools", NOT_GIVEN)
        tool_choice = params_from_context.get("tool_choice", NOT_GIVEN)

        request: dict[str, Any] = {
            "model": getattr(self, "model_name", None) or self._setting("model"),
            "tools": self._tools_to_responses_tools(tools),
            "tool_choice": self._tool_choice_to_responses_tool_choice(tool_choice),
            "temperature": self._setting("temperature"),
            "top_p": self._setting("top_p"),
            "service_tier": self._setting("service_tier"),
        }

        max_completion_tokens = self._setting("max_completion_tokens")
        max_tokens = self._setting("max_tokens")
        if not self._is_not_given(max_completion_tokens):
            request["max_output_tokens"] = max_completion_tokens
        elif not self._is_not_given(max_tokens):
            request["max_output_tokens"] = max_tokens

        extra = self._setting("extra", {})
        if not isinstance(extra, dict):
            extra = {}

        # Allow the benchmark to keep using the older reasoning_effort key.
        if "reasoning" not in extra and "reasoning_effort" in extra:
            extra = dict(extra)
            extra["reasoning"] = {"effort": extra.pop("reasoning_effort")}

        request.update(extra)

        request["input"] = self._messages_to_responses_input(messages)

        cleaned: dict[str, Any] = {}
        for key, value in request.items():
            if self._is_not_given(value):
                continue
            cleaned[key] = value
        return cleaned

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        output_items = getattr(response, "output", None) or []
        parts: list[str] = []
        for item in output_items:
            if getattr(item, "type", None) != "message":
                continue
            for part in getattr(item, "content", None) or []:
                if getattr(part, "type", None) in {"output_text", "text", "input_text"}:
                    text = getattr(part, "text", None)
                    if text:
                        parts.append(text)
        return "".join(parts)

    async def run_inference(
        self, context: LLMContext | OpenAILLMContext, max_tokens: int | None = None
    ) -> str | None:
        params = self._responses_request_params(context)
        params["stream"] = False
        if max_tokens is not None:
            params["max_output_tokens"] = max_tokens
        request_timeout = getattr(self, "_request_timeout_secs", None)
        if request_timeout is None:
            response = await self._client.responses.create(**params)
            return self._extract_response_text(response)
        try:
            response = await asyncio.wait_for(
                self._client.responses.create(**params),
                timeout=float(request_timeout),
            )
        except asyncio.TimeoutError as exc:
            raise ResponsesRequestTimeout("Non-streaming Responses request timed out") from exc
        return self._extract_response_text(response)

    @traced_llm
    async def _process_context(self, context: OpenAILLMContext | LLMContext):
        await self.start_ttfb_metrics()
        ttfb_stopped = False
        function_call_map: dict[str, dict[str, str]] = {}
        queued_function_calls: list[FunctionCallFromLLM] = []
        processed_call_ids: set[str] = set()

        async def apply_terminal_metadata(response: Any) -> None:
            model_name = self._get_attr(response, "model")
            if model_name and self.get_full_model_name() != model_name:
                self.set_full_model_name(model_name)
            usage = self._get_attr(response, "usage")
            if usage is None:
                return
            input_details = self._get_attr(usage, "input_tokens_details")
            output_details = self._get_attr(usage, "output_tokens_details")
            tokens = LLMTokenUsage(
                prompt_tokens=self._get_attr(usage, "input_tokens"),
                completion_tokens=self._get_attr(usage, "output_tokens"),
                total_tokens=self._get_attr(usage, "total_tokens"),
                cache_read_input_tokens=self._get_attr(input_details, "cached_tokens"),
                reasoning_tokens=self._get_attr(output_details, "reasoning_tokens"),
            )
            await self.start_llm_usage_metrics(tokens)

        async def queue_function_call(
            *,
            item_id: str | None,
            call_id: str | None,
            function_name: str,
            args_text: Any,
        ) -> None:
            nonlocal ttfb_stopped
            if not call_id or not function_name:
                logger.warning(
                    f"{self}: skipping function call due to missing call_id/name "
                    f"(item_id={item_id}, name={function_name})"
                )
                return
            if call_id in processed_call_ids:
                return
            try:
                arguments = json.loads(args_text) if isinstance(args_text, str) else {}
            except Exception:
                arguments = {"_raw_arguments": args_text}
            if not ttfb_stopped:
                await self.stop_ttfb_metrics()
                ttfb_stopped = True
            processed_call_ids.add(call_id)
            queued_function_calls.append(
                FunctionCallFromLLM(
                    context=context,
                    tool_call_id=call_id,
                    function_name=function_name,
                    arguments=arguments,
                )
            )

        params = self._responses_request_params(context)
        stream_state: dict[str, Any] = {"request_id": None}
        event_types: list[str] = []
        terminal_seen = False
        completed_terminal = False
        strict_outcomes = bool(
            getattr(self, "_benchmark_observability_enabled", False)
        )
        try:
            async for event in self._iter_response_events(params, stream_state):
                event_type = getattr(event, "type", None)
                if event_type and event_type not in event_types:
                    event_types.append(event_type)

                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", "")
                    if delta:
                        if not ttfb_stopped:
                            await self.stop_ttfb_metrics()
                            ttfb_stopped = True
                        await self._push_llm_text(delta)
                    continue

                if event_type == "response.reasoning_text.delta":
                    delta = getattr(event, "delta", "")
                    if delta:
                        if not ttfb_stopped:
                            await self.stop_ttfb_metrics()
                            ttfb_stopped = True
                        await self._push_frame(self._create_text_frame(delta, is_thought=True))
                    continue

                if event_type == "response.output_item.added":
                    item = getattr(event, "item", None)
                    if item is not None and getattr(item, "type", None) == "function_call":
                        item_id = getattr(item, "id", None)
                        call_id = getattr(item, "call_id", None)
                        name = getattr(item, "name", None)
                        if item_id:
                            function_call_map[item_id] = {
                                "call_id": call_id or item_id,
                                "name": name or "",
                            }
                        if not ttfb_stopped:
                            await self.stop_ttfb_metrics()
                            ttfb_stopped = True
                    continue

                if event_type == "response.function_call_arguments.done":
                    item_id = getattr(event, "item_id", None)
                    name = getattr(event, "name", "")
                    args_text = getattr(event, "arguments", "{}")
                    mapping = function_call_map.get(item_id, {}) if item_id else {}
                    call_id = mapping.get("call_id") or item_id
                    function_name = name or mapping.get("name") or ""
                    await queue_function_call(
                        item_id=item_id,
                        call_id=call_id,
                        function_name=function_name,
                        args_text=args_text,
                    )
                    continue

                if event_type == "response.output_item.done":
                    item = getattr(event, "item", None)
                    if item is not None and getattr(item, "type", None) == "function_call":
                        item_id = getattr(item, "id", None)
                        call_id = getattr(item, "call_id", None) or item_id
                        function_name = getattr(item, "name", "")
                        args_text = getattr(item, "arguments", "{}")
                        await queue_function_call(
                            item_id=item_id,
                            call_id=call_id,
                            function_name=function_name,
                            args_text=args_text,
                        )
                    continue

                if event_type == "response.completed":
                    response = getattr(event, "response", None)
                    if response is not None:
                        terminal_seen = True
                        completed_terminal = True
                        await apply_terminal_metadata(response)
                        if strict_outcomes:
                            self._record_trace(
                                self._terminal_trace(
                                    params=params,
                                    response=response,
                                    event_types=event_types,
                                    request_id=stream_state.get("request_id"),
                                )
                            )
                    if not strict_outcomes and queued_function_calls:
                        await self.run_function_calls(list(queued_function_calls))
                        queued_function_calls.clear()
                    continue

                if event_type in {"response.incomplete", "response.failed"}:
                    if not strict_outcomes:
                        if event_type == "response.failed":
                            await self.push_error(
                                error_msg=f"Responses API error event: {event}"
                            )
                        continue
                    response = getattr(event, "response", None)
                    if response is not None:
                        terminal_seen = True
                        await apply_terminal_metadata(response)
                        self._record_trace(
                            self._terminal_trace(
                                params=params,
                                response=response,
                                event_types=event_types,
                                request_id=stream_state.get("request_id"),
                            )
                        )
                    continue

                if event_type in {"response.error", "error"}:
                    if not strict_outcomes:
                        await self.push_error(error_msg=f"Responses API error event: {event}")
                        continue
                    terminal_seen = True
                    trace = {
                        **self._request_trace(params),
                        "request_id": stream_state.get("request_id"),
                        "response_id": None,
                        "resolved_model": None,
                        "response_status": "failed",
                        "returned_service_tier": None,
                        "incomplete_reason": None,
                        "error": self._error_trace(event),
                        "usage": None,
                        "event_types": list(event_types),
                    }
                    self._record_trace(trace)
                    continue

            if strict_outcomes and not terminal_seen:
                raise ResponsesProtocolError("Responses stream ended without a terminal event")
            # The request/idle deadlines protect provider I/O only.  Dispatch
            # tool calls after the stream context has closed so those calls
            # remain governed by the existing function-call timeout instead.
            if strict_outcomes and completed_terminal and queued_function_calls:
                await self.run_function_calls(list(queued_function_calls))
                queued_function_calls.clear()
        except Exception as exc:
            if strict_outcomes and not terminal_seen:
                self._record_trace(
                    self._exception_trace(
                        params=params,
                        exc=exc,
                        event_types=event_types,
                        request_id=stream_state.get("request_id"),
                    )
                )
            if not ttfb_stopped:
                await self.stop_ttfb_metrics()
                ttfb_stopped = True
            raise

        if not ttfb_stopped:
            await self.stop_ttfb_metrics()
