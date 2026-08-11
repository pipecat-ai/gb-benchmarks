#!/usr/bin/env python3
"""Baseten empty-turn diagnostics for GLM-5.2 and Nemotron-3-Ultra.

Diagnostic-only script. It drives Baseten directly through the OpenAI Python
client and writes markdown findings for operator review. It does not import or
modify the benchmark harness, does not write run JSONs, and must not be used as
leaderboard data.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import datetime as dt
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from openai import OpenAI


BASE_URL = "https://inference.baseten.co/v1"
GLM_MODEL = "zai-org/GLM-5.2"
NEMOTRON_MODEL = "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B"
MODEL_ALIASES = {
    "glm": GLM_MODEL,
    "glm-5.2": GLM_MODEL,
    "zai-org/glm-5.2": GLM_MODEL,
    "nemotron": NEMOTRON_MODEL,
    "nemotron-ultra": NEMOTRON_MODEL,
    "nvidia/nvidia-nemotron-3-ultra-550b-a55b": NEMOTRON_MODEL,
}

REPO_ROOT = Path("/home/khkramer/src/gb-benchmarks")
PORT_DIR = REPO_ROOT / "port-to-port"
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
DEFAULT_OUTPUT = PORT_DIR / "proj-2026-06-30-0924" / "step1-diagnostic-findings.md"

DEFAULT_MAX_TOKENS = 4096
REQUEST_TIMEOUT_SECS = 120.0
MAX_RAW_DUMP_CHARS = 120_000
MAX_CONCURRENCY_SAMPLES = 500
MAX_REASONING_SHAPE_SAMPLES = 50
MAX_FORCE_NONEMPTY_SAMPLES = 50


class DiagnosticError(RuntimeError):
    """User-facing diagnostic setup or invocation error."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_env_key(env_file: Path, key_name: str = "BASETEN_API_KEY") -> str:
    """Read exactly one key from a dotenv-style file without sourcing it."""

    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise DiagnosticError(f"Env file not found: {env_file}") from exc

    prefix = f"{key_name}="
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ("'", '"')
        ):
            value = value[1:-1]
        if not value:
            raise DiagnosticError(f"{key_name} is present but empty in {env_file}")
        return value

    raise DiagnosticError(f"{key_name} not found in {env_file}")


def make_client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=BASE_URL, timeout=REQUEST_TIMEOUT_SECS)


def canonical_model(name: str) -> str:
    lowered = name.lower()
    return MODEL_ALIASES.get(lowered, name)


def selected_models(selector: str) -> list[str]:
    if selector == "all":
        return [GLM_MODEL, NEMOTRON_MODEL]
    return [canonical_model(selector)]


def to_plain(value: Any) -> Any:
    """Convert OpenAI/Pydantic response objects to JSON-like stdlib values."""

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=False)
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def truncate_text(text: str, max_chars: int = MAX_RAW_DUMP_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return f"{text[:max_chars]}\n\n... truncated {omitted} chars ..."


def get_path(value: Any, path: Iterable[Any], default: Any = None) -> Any:
    cur = value
    for item in path:
        if isinstance(cur, dict):
            if item not in cur:
                return default
            cur = cur[item]
        elif isinstance(cur, list) and isinstance(item, int):
            if item < 0 or item >= len(cur):
                return default
            cur = cur[item]
        else:
            return default
    return cur


def strip_not_given(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            cleaned = strip_not_given(item)
            if cleaned == "NOT_GIVEN":
                continue
            out[key] = cleaned
        return out
    if isinstance(value, list):
        return [strip_not_given(item) for item in value if item != "NOT_GIVEN"]
    return value


def normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clean captured messages enough for direct Chat Completions replay."""

    cleaned: list[dict[str, Any]] = []
    for message in copy.deepcopy(messages):
        if not isinstance(message, dict):
            continue
        message = strip_not_given(message)
        if message.get("content") == "NOT_GIVEN":
            message.pop("content", None)
        if "tool_calls" in message and message["tool_calls"] == "NOT_GIVEN":
            message.pop("tool_calls", None)
        cleaned.append(message)
    return cleaned


def usage_completion_tokens(usage: Any) -> int | None:
    if not isinstance(usage, dict):
        return None
    value = usage.get("completion_tokens")
    if isinstance(value, int):
        return value
    return None


def usage_is_missing_or_zero(usage: Any) -> bool:
    completion_tokens = usage_completion_tokens(usage)
    return usage is None or completion_tokens is None or completion_tokens == 0


def has_payload(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def parse_positive_int_list(raw: str, flag_name: str) -> list[int]:
    values: list[int] = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        try:
            value = int(text)
        except ValueError as exc:
            raise DiagnosticError(
                f"{flag_name} must contain positive integers; got {text!r}"
            ) from exc
        if value < 1:
            raise DiagnosticError(f"{flag_name} must contain positive integers")
        values.append(value)
    if not values:
        raise DiagnosticError(f"{flag_name} must contain positive integers")
    return values


def build_extra_body(
    reasoning_effort: str | None = None,
    *,
    captured_extra_body: dict[str, Any] | None = None,
    force_nonempty_content: bool | None = None,
) -> dict[str, Any] | None:
    extra_body = copy.deepcopy(captured_extra_body or {})
    if reasoning_effort is not None:
        reasoning = extra_body.get("reasoning")
        if not isinstance(reasoning, dict):
            reasoning = {}
        reasoning["effort"] = reasoning_effort
        extra_body["reasoning"] = reasoning
    if force_nonempty_content is not None:
        ctk = extra_body.get("chat_template_kwargs")
        if not isinstance(ctk, dict):
            ctk = {}
        ctk["force_nonempty_content"] = force_nonempty_content
        extra_body["chat_template_kwargs"] = ctk
    return extra_body or None


def request_kwargs(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
    max_tokens: int,
    reasoning_effort: str | None,
    captured_extra_body: dict[str, Any] | None = None,
    force_nonempty_content: bool | None = None,
    stream: bool,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": normalize_messages(messages),
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if tools:
        kwargs["tools"] = strip_not_given(copy.deepcopy(tools))
    if tool_choice and tool_choice != "NOT_GIVEN":
        kwargs["tool_choice"] = tool_choice
    extra_body = build_extra_body(
        reasoning_effort,
        captured_extra_body=captured_extra_body,
        force_nonempty_content=force_nonempty_content,
    )
    if extra_body:
        kwargs["extra_body"] = extra_body
    if stream:
        kwargs["stream_options"] = {"include_usage": True}
    return kwargs


def diagnostic_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "my_status",
                "description": "Get current ship status.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "plot_course",
                "description": "Calculate a shortest known path to a sector.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to_sector": {"type": "integer", "minimum": 0},
                        "from_sector": {"type": "integer", "minimum": 0},
                    },
                    "required": ["to_sector"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_known_ports",
                "description": "List known ports, optionally filtered by route or commodity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_sector": {"type": "integer", "minimum": 0},
                        "max_hops": {"type": "integer", "minimum": 1, "maximum": 50},
                        "mega": {"type": "boolean"},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "move",
                "description": "Move one hop to an adjacent sector.",
                "parameters": {
                    "type": "object",
                    "properties": {"to_sector": {"type": "integer", "minimum": 0}},
                    "required": ["to_sector"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "trade",
                "description": "Execute a buy or sell at the current port.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trade_type": {"type": "string", "enum": ["buy", "sell"]},
                        "commodity": {
                            "type": "string",
                            "enum": [
                                "quantum_foam",
                                "retro_organics",
                                "neuro_symbolics",
                            ],
                        },
                        "quantity": {"type": "integer", "minimum": 1},
                    },
                    "required": ["trade_type", "commodity", "quantity"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "recharge_warp_power",
                "description": "Recharge warp power at a mega-port.",
                "parameters": {
                    "type": "object",
                    "properties": {"units": {"type": "integer", "minimum": 1}},
                    "required": ["units"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "finished",
                "description": "Signal that the task is complete.",
                "parameters": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            },
        },
    ]


def diagnostic_messages() -> list[dict[str, Any]]:
    """Representative compact multi-turn tool-use context."""

    return [
        {
            "role": "system",
            "content": (
                "Diagnostic-only Gradient Bang tool-use context. You control a "
                "ship. Use exactly one tool call for the next concrete action. "
                "Move only to adjacent sectors. Port code B means the port buys "
                "from you; S means the port sells to you."
            ),
        },
        {
            "role": "user",
            "content": (
                "Go round-trip to the nearest mega-port, recharge there, and make "
                "profitable trades without going off-course."
            ),
        },
        {
            "role": "user",
            "content": (
                "<event name=status.snapshot>\n"
                "In sector 3080. Adjacent sectors: [2266, 3313]. Warp: 500/500. "
                "Credits: 16564. Cargo: 10 QF, 0 RO, 0 NS. Empty holds: 20. "
                "Port: BSB buys QF@33,NS@52 sells RO@8.\n"
                "</event>"
            ),
        },
        {
            "role": "assistant",
            "content": "I will sell the starting QF and locate the nearest mega-port.",
            "tool_calls": [
                {
                    "id": "call_diag_1",
                    "type": "function",
                    "function": {
                        "name": "trade",
                        "arguments": json.dumps(
                            {
                                "trade_type": "sell",
                                "commodity": "quantum_foam",
                                "quantity": 10,
                            }
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_diag_1",
            "content": "Executed.",
        },
        {
            "role": "user",
            "content": (
                "<event name=trade.executed>\n"
                "Sold 10 quantum_foam for 330 credits. Credits: 16894. "
                "Cargo: 0 QF, 0 RO, 0 NS. Empty holds: 30.\n"
                "</event>"
            ),
        },
        {
            "role": "assistant",
            "content": "I need the nearest mega-port.",
            "tool_calls": [
                {
                    "id": "call_diag_2",
                    "type": "function",
                    "function": {
                        "name": "list_known_ports",
                        "arguments": json.dumps({"mega": True}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_diag_2",
            "content": "Executed.",
        },
        {
            "role": "user",
            "content": (
                "<event name=ports.list>\n"
                "Nearest mega-port: sector 1611, MEGA SSS, distance 11 hops. "
                "It sells QF@10, RO@6, NS@30 and recharges warp at 2 credits/unit.\n"
                "</event>"
            ),
        },
        {
            "role": "assistant",
            "content": "I will plot the course to sector 1611.",
            "tool_calls": [
                {
                    "id": "call_diag_3",
                    "type": "function",
                    "function": {
                        "name": "plot_course",
                        "arguments": json.dumps({"to_sector": 1611}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_diag_3",
            "content": "Executed.",
        },
        {
            "role": "user",
            "content": (
                "<event name=course.plot>\n"
                "Route: 3080 -> 2266 -> 3885 -> 916 -> 4884 -> 2469 -> 1344 -> "
                "4874 -> 3494 -> 2831 -> 2058 -> 1611. Profitable known trade: "
                "buy NS at 4874 or 1611 (SSS), sell NS at 2831 or 3080 (BSB).\n"
                "</event>"
            ),
        },
        {
            "role": "user",
            "content": (
                "Continue. Choose the next concrete tool call now. If starting the "
                "route, move to the next adjacent sector."
            ),
        },
    ]


def fixed_request() -> tuple[list[dict[str, Any]], list[dict[str, Any]], Any, dict[str, Any] | None, int]:
    return diagnostic_messages(), diagnostic_tools(), None, None, DEFAULT_MAX_TOKENS


def turn_is_empty_no_tool_no_usage(turn: dict[str, Any]) -> bool:
    if turn.get("tool_calls") or []:
        return False
    if (turn.get("raw_response_text") or "").strip():
        return False
    if (turn.get("raw_response_text_raw") or "").strip():
        return False
    if (turn.get("raw_thought_text") or "").strip():
        return False
    if not usage_is_missing_or_zero(turn.get("usage")):
        return False
    if turn.get("error_event"):
        return False
    return True


def auto_select_empty_replay_input(
    payload: dict[str, Any],
    inputs: list[dict[str, Any]],
) -> tuple[dict[str, Any], str] | None:
    by_inference_index = {
        item.get("inference_index"): item
        for item in inputs
        if isinstance(item.get("inference_index"), int)
    }
    turns = payload.get("turns")
    if not isinstance(turns, list):
        return None
    for turn in turns:
        if not isinstance(turn, dict) or not turn_is_empty_no_tool_no_usage(turn):
            continue
        inference_index = turn.get("inference_index")
        selected = by_inference_index.get(inference_index)
        if selected is not None:
            return (
                selected,
                "auto-selected first turn with no tool calls, empty text/thought, "
                "and missing/zero usage",
            )
    return None


def load_replay_request(
    run_json: Path,
    *,
    entry_index: int | None,
    inference_index: int | None,
    auto_select_empty: bool = False,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]] | None,
    Any,
    dict[str, Any] | None,
    int,
    dict[str, Any],
]:
    try:
        payload = json.loads(run_json.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DiagnosticError(f"Run JSON not found: {run_json}") from exc
    except json.JSONDecodeError as exc:
        raise DiagnosticError(f"Run JSON is not valid JSON: {run_json}: {exc}") from exc

    inputs = payload.get("inference_inputs")
    if not isinstance(inputs, list) or not inputs:
        raise DiagnosticError(f"No inference_inputs list found in {run_json}")

    selected = None
    selection_mode = None
    if inference_index is not None:
        for item in inputs:
            if item.get("inference_index") == inference_index:
                selected = item
                break
        if selected is None:
            raise DiagnosticError(
                f"inference_index={inference_index} not found in {run_json}"
            )
    else:
        if entry_index is None and auto_select_empty:
            auto_selected = auto_select_empty_replay_input(payload, inputs)
            if auto_selected is None:
                raise DiagnosticError(
                    "--run-json without --entry-index/--inference-index could not "
                    "auto-select a no-tool/empty-text/empty-thought/no-usage "
                    "inference; pass an explicit index"
                )
            selected, selection_mode = auto_selected
        else:
            idx = 0 if entry_index is None else entry_index
            if idx < 0 or idx >= len(inputs):
                raise DiagnosticError(
                    f"entry_index={idx} out of range; run has {len(inputs)} inputs"
                )
            selected = inputs[idx]
            selection_mode = (
                "defaulted to entry_index=0"
                if entry_index is None
                else f"selected entry_index={entry_index}"
            )

    provider_params = selected.get("provider_invocation_params") or {}
    messages = (
        selected.get("messages_for_llm")
        or selected.get("messages")
        or provider_params.get("messages")
    )
    if not isinstance(messages, list) or not messages:
        raise DiagnosticError("Selected inference input does not contain messages")

    tools = (
        selected.get("tools_for_llm")
        or selected.get("tools")
        or provider_params.get("tools")
    )
    if tools == "NOT_GIVEN":
        tools = None
    if tools is not None and not isinstance(tools, list):
        raise DiagnosticError("Selected inference input tools are not a list")

    tool_choice = (
        selected.get("tool_choice")
        or provider_params.get("tool_choice")
        or None
    )
    if tool_choice == "NOT_GIVEN":
        tool_choice = None

    captured_extra_body = get_path(
        selected, ["llm_settings", "extra", "extra_body"], default=None
    )
    if captured_extra_body == "NOT_GIVEN":
        captured_extra_body = None
    if captured_extra_body is not None and not isinstance(captured_extra_body, dict):
        captured_extra_body = None

    captured_max_tokens = get_path(selected, ["llm_settings", "max_tokens"], default=None)
    max_tokens = (
        captured_max_tokens
        if isinstance(captured_max_tokens, int) and captured_max_tokens > 0
        else DEFAULT_MAX_TOKENS
    )

    metadata = {
        "run_json": str(run_json),
        "entry_inference_index": selected.get("inference_index"),
        "entry_llm_turn": selected.get("llm_turn"),
        "entry_reasons": selected.get("reasons"),
        "message_count": len(messages),
        "tool_count": len(tools or []),
        "captured_extra_body": captured_extra_body,
        "captured_max_tokens": max_tokens,
    }
    if selection_mode is not None:
        metadata["selection_mode"] = selection_mode
    return messages, tools, tool_choice, captured_extra_body, max_tokens, metadata


def extract_nonstream_shape(response_plain: dict[str, Any]) -> dict[str, Any]:
    choices = response_plain.get("choices") or []
    first_choice = choices[0] if choices else {}
    message = first_choice.get("message") or {}
    content = message.get("content")
    tool_calls = message.get("tool_calls") or []
    usage = response_plain.get("usage")
    reasoning_content = message.get("reasoning_content")
    if reasoning_content is None:
        reasoning_content = message.get("reasoning")
    content_present = has_payload(content)
    reasoning_present = has_payload(reasoning_content)
    tool_present = bool(tool_calls)
    return {
        "content": content,
        "content_len": len(content or ""),
        "tool_calls": tool_calls,
        "tool_call_count": len(tool_calls),
        "finish_reason": first_choice.get("finish_reason"),
        "usage": usage,
        "completion_tokens": usage_completion_tokens(usage),
        "reasoning_content": reasoning_content,
        "reasoning_content_len": len(reasoning_content or "")
        if isinstance(reasoning_content, str)
        else None,
        "message_keys": list(message.keys()),
        "empty_no_usage": (
            not content_present
            and not tool_present
            and not reasoning_present
            and usage_is_missing_or_zero(usage)
        ),
        "reasoning_only_no_tool": (
            reasoning_present
            and not content_present
            and not tool_present
        ),
    }


def extract_stream_shape(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    deltas: list[dict[str, Any]] = []
    usage = None
    tool_delta_count = 0
    finish_reasons: list[Any] = []
    events: list[dict[str, Any]] = []

    for chunk_index, chunk in enumerate(chunks):
        if chunk.get("usage") is not None:
            usage = chunk.get("usage")
        for choice_index, choice in enumerate(chunk.get("choices") or []):
            delta = choice.get("delta") or {}
            finish_reason = choice.get("finish_reason")
            if finish_reason is not None:
                finish_reasons.append(finish_reason)
            deltas.append(
                {
                    "chunk_index": chunk_index,
                    "choice_index": choice_index,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            )
            content = delta.get("content")
            if content:
                content_parts.append(content)
                events.append(
                    {
                        "chunk_index": chunk_index,
                        "choice_index": choice_index,
                        "kind": "content",
                        "length": len(content),
                    }
                )
            reasoning = delta.get("reasoning_content")
            if reasoning is None:
                reasoning = delta.get("reasoning")
            if reasoning:
                reasoning_parts.append(reasoning)
                events.append(
                    {
                        "chunk_index": chunk_index,
                        "choice_index": choice_index,
                        "kind": "reasoning_content",
                        "length": len(reasoning),
                    }
                )
            tool_calls = delta.get("tool_calls")
            if tool_calls:
                tool_delta_count += len(tool_calls)
                events.append(
                    {
                        "chunk_index": chunk_index,
                        "choice_index": choice_index,
                        "kind": "tool_calls",
                        "count": len(tool_calls),
                    }
                )

    content_text = "".join(content_parts)
    reasoning_text = "".join(reasoning_parts)
    content_present = bool(content_text)
    reasoning_present = bool(reasoning_text)
    tool_present = tool_delta_count > 0
    return {
        "content": content_text,
        "content_len": len(content_text),
        "reasoning_content": reasoning_text,
        "reasoning_content_len": len(reasoning_text),
        "tool_delta_count": tool_delta_count,
        "finish_reasons": finish_reasons,
        "usage": usage,
        "completion_tokens": usage_completion_tokens(usage),
        "deltas": deltas,
        "event_order": events,
        "empty_no_usage": (
            not content_present
            and not tool_present
            and not reasoning_present
            and usage_is_missing_or_zero(usage)
        ),
        "reasoning_only_no_tool": (
            reasoning_present
            and not content_present
            and not tool_present
        ),
    }


def describe_exception(exc: BaseException) -> dict[str, Any]:
    details: dict[str, Any] = {
        "exception_type": type(exc).__name__,
        "message": str(exc),
    }
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if value is not None and value != details.get(attr):
            details[attr] = value
    api_type = getattr(exc, "type", None)
    if api_type is not None:
        details["api_type"] = api_type
    body = getattr(exc, "body", None)
    if body is not None:
        details["body"] = to_plain(body)
    response = getattr(exc, "response", None)
    if response is not None:
        details["response_status_code"] = getattr(response, "status_code", None)
        try:
            details["response_text"] = response.text
        except Exception:
            pass
    return details


def call_nonstream(client: OpenAI, kwargs: dict[str, Any]) -> dict[str, Any]:
    call_kwargs = dict(kwargs)
    call_kwargs["stream"] = False
    call_kwargs.pop("stream_options", None)
    started = time.monotonic()
    response = client.chat.completions.create(**call_kwargs)
    latency_ms = (time.monotonic() - started) * 1000.0
    response_plain = to_plain(response)
    shape = extract_nonstream_shape(response_plain)
    return {
        "mode": "nonstream",
        "latency_ms": round(latency_ms, 2),
        "response": response_plain,
        "shape": shape,
    }


def call_stream(client: OpenAI, kwargs: dict[str, Any]) -> dict[str, Any]:
    call_kwargs = dict(kwargs)
    call_kwargs["stream"] = True
    call_kwargs["stream_options"] = {"include_usage": True}
    chunks: list[dict[str, Any]] = []
    started = time.monotonic()
    stream = client.chat.completions.create(**call_kwargs)
    for chunk in stream:
        chunks.append(to_plain(chunk))
    latency_ms = (time.monotonic() - started) * 1000.0
    shape = extract_stream_shape(chunks)
    return {
        "mode": "stream",
        "latency_ms": round(latency_ms, 2),
        "chunks": chunks,
        "shape": shape,
    }


def append_markdown(
    output: Path,
    heading: str,
    body_lines: list[str],
    *,
    overwrite: bool,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    preamble = [
        "# Baseten Empty-Turn Diagnostic Findings",
        "",
        "> Diagnostic-only evidence for `proj-2026-06-30-0924` step 1. "
        "This file is not a benchmark run, not eval input, and not leaderboard data.",
        "",
    ]
    section = [
        f"## {heading}",
        "",
        f"- Timestamp UTC: `{utc_now()}`",
        f"- Base URL: `{BASE_URL}`",
        "- Diagnostic-only: yes; no harness files or run artifacts are written.",
        "",
        *body_lines,
        "",
    ]
    if overwrite or not output.exists():
        output.write_text("\n".join([*preamble, *section]), encoding="utf-8")
    else:
        with output.open("a", encoding="utf-8") as handle:
            handle.write("\n" + "\n".join(section))


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return lines


def output_target(args: argparse.Namespace) -> Path:
    return Path(args.output).expanduser().resolve()


def base_cli_notes(args: argparse.Namespace) -> list[str]:
    return [
        f"- Command: `{Path(sys.argv[0]).name} {' '.join(sys.argv[1:])}`",
        f"- Output file: `{output_target(args)}`",
        "",
    ]


def run_single_sample(
    *,
    api_key: str,
    model: str,
    mode: str,
    sample_id: int,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
    max_tokens: int,
    reasoning_effort: str | None,
) -> dict[str, Any]:
    client = make_client(api_key)
    kwargs = request_kwargs(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
        stream=(mode == "stream"),
    )
    try:
        result = call_stream(client, kwargs) if mode == "stream" else call_nonstream(client, kwargs)
        shape = result["shape"]
        return {
            "sample_id": sample_id,
            "ok": True,
            "empty_no_usage": bool(shape["empty_no_usage"]),
            "reasoning_only_no_tool": bool(shape["reasoning_only_no_tool"]),
            "content_len": shape.get("content_len", 0),
            "reasoning_content_len": shape.get("reasoning_content_len", 0),
            "tool_count": shape.get("tool_delta_count", shape.get("tool_call_count", 0)),
            "completion_tokens": shape.get("completion_tokens"),
            "finish": shape.get("finish_reasons") or shape.get("finish_reason"),
            "latency_ms": result["latency_ms"],
        }
    except Exception as exc:
        return {
            "sample_id": sample_id,
            "ok": False,
            "empty_no_usage": False,
            "reasoning_only_no_tool": False,
            "error": describe_exception(exc),
        }


def command_concurrency(args: argparse.Namespace) -> int:
    api_key = read_env_key(Path(args.env_file))
    messages, tools, tool_choice, _captured_extra, default_max_tokens = fixed_request()
    max_tokens = args.max_tokens or default_max_tokens
    levels = parse_positive_int_list(args.levels, "--levels")
    if args.samples < 1 or args.samples > MAX_CONCURRENCY_SAMPLES:
        raise DiagnosticError(f"--samples must be between 1 and {MAX_CONCURRENCY_SAMPLES}")

    body = base_cli_notes(args)
    body.extend(
        [
            "### Probe",
            "",
            (
                "Bounded diagnostic exception to the sequential-per-endpoint rule. "
                "This fires the same fixed multi-turn tool-use request at the selected "
                "concurrency levels and counts true Mechanism-B empty/no-usage "
                "responses separately from reasoning-only/no-tool responses."
            ),
            "",
            f"- Models: `{', '.join(selected_models(args.model))}`",
            f"- Mode: `{args.mode}`",
            f"- Reasoning effort: `{args.reasoning_effort}`",
            f"- Samples per level/model: `{args.samples}`",
            f"- Max tokens: `{max_tokens}`",
            "",
        ]
    )

    rows: list[list[Any]] = []
    error_blocks: list[str] = []

    for model in selected_models(args.model):
        for level in levels:
            samples: list[dict[str, Any]] = []
            lock = threading.Lock()
            with concurrent.futures.ThreadPoolExecutor(max_workers=level) as executor:
                futures = [
                    executor.submit(
                        run_single_sample,
                        api_key=api_key,
                        model=model,
                        mode=args.mode,
                        sample_id=sample_id,
                        messages=messages,
                        tools=tools,
                        tool_choice=tool_choice,
                        max_tokens=max_tokens,
                        reasoning_effort=args.reasoning_effort,
                    )
                    for sample_id in range(1, args.samples + 1)
                ]
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    with lock:
                        samples.append(result)

            samples.sort(key=lambda item: item["sample_id"])
            ok_count = sum(1 for item in samples if item.get("ok"))
            error_count = len(samples) - ok_count
            empty_count = sum(1 for item in samples if item.get("empty_no_usage"))
            reasoning_only_count = sum(
                1 for item in samples if item.get("reasoning_only_no_tool")
            )
            empty_rate = empty_count / ok_count if ok_count else 0.0
            latencies = [
                item["latency_ms"]
                for item in samples
                if item.get("ok") and isinstance(item.get("latency_ms"), (int, float))
            ]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
            rows.append(
                [
                    model,
                    level,
                    args.samples,
                    ok_count,
                    error_count,
                    empty_count,
                    reasoning_only_count,
                    f"{empty_rate:.1%}",
                    f"{avg_latency:.0f}",
                ]
            )

            errors = [item for item in samples if not item.get("ok")]
            if errors:
                first_error = errors[0].get("error")
                error_blocks.append(
                    f"#### First error for `{model}` concurrency `{level}`\n\n"
                    "```json\n"
                    f"{pretty_json(first_error)}\n"
                    "```"
                )

    body.extend(
        markdown_table(
            [
                "model",
                "concurrency",
                "requested_samples",
                "ok",
                "errors",
                "empty_no_usage",
                "reasoning_only_no_tool",
                "empty_rate_of_ok",
                "avg_latency_ms",
            ],
            rows,
        )
    )
    if error_blocks:
        body.extend(["", *error_blocks])

    append_markdown(
        output_target(args),
        "Concurrency Probe",
        body,
        overwrite=args.overwrite,
    )
    print(f"Wrote concurrency findings to {output_target(args)}")
    return 0


def resolve_request_from_args(
    args: argparse.Namespace,
    *,
    default_reasoning_effort: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None, Any, dict[str, Any] | None, int, dict[str, Any]]:
    if getattr(args, "run_json", None):
        (
            messages,
            tools,
            tool_choice,
            captured_extra_body,
            captured_max_tokens,
            metadata,
        ) = load_replay_request(
            Path(args.run_json),
            entry_index=args.entry_index,
            inference_index=args.inference_index,
            auto_select_empty=getattr(args, "command", None) == "raw-capture",
        )
    else:
        messages, tools, tool_choice, captured_extra_body, captured_max_tokens = fixed_request()
        metadata = {
            "request_source": "built-in compact diagnostic multi-turn context",
            "message_count": len(messages),
            "tool_count": len(tools or []),
            "captured_extra_body": captured_extra_body,
            "captured_max_tokens": captured_max_tokens,
        }

    if args.max_tokens is not None:
        max_tokens = args.max_tokens
    else:
        max_tokens = captured_max_tokens

    reasoning_effort = args.reasoning_effort
    if reasoning_effort is None:
        reasoning_effort = default_reasoning_effort
    if reasoning_effort is None:
        captured_effort = get_path(captured_extra_body or {}, ["reasoning", "effort"])
        if isinstance(captured_effort, str):
            reasoning_effort = captured_effort

    metadata["effective_max_tokens"] = max_tokens
    metadata["effective_reasoning_effort"] = reasoning_effort
    return messages, tools, tool_choice, captured_extra_body, max_tokens, metadata


def dump_raw_capture_result(
    label: str,
    result: dict[str, Any],
    *,
    dump_all: bool,
) -> list[str]:
    shape = result["shape"]
    lines = [
        f"### {label}",
        "",
        f"- Mode: `{result['mode']}`",
        f"- Latency ms: `{result['latency_ms']}`",
        f"- Empty/no-usage (Mechanism B): `{shape['empty_no_usage']}`",
        f"- Reasoning-only/no-tool: `{shape['reasoning_only_no_tool']}`",
        f"- Content length: `{shape.get('content_len')}`",
        f"- Reasoning content length: `{shape.get('reasoning_content_len')}`",
        f"- Tool call/delta count: `{shape.get('tool_delta_count', shape.get('tool_call_count'))}`",
        f"- Completion tokens: `{shape.get('completion_tokens')}`",
        f"- Finish: `{shape.get('finish_reasons') or shape.get('finish_reason')}`",
        "",
    ]

    if result["mode"] == "stream":
        lines.extend(
            [
                "#### Stream summary",
                "",
                "```json",
                pretty_json(
                    {
                        "usage": shape.get("usage"),
                        "event_order": shape.get("event_order"),
                        "deltas": shape.get("deltas"),
                        "empty_no_usage": shape.get("empty_no_usage"),
                        "reasoning_only_no_tool": shape.get("reasoning_only_no_tool"),
                    }
                ),
                "```",
                "",
            ]
        )
        if shape["empty_no_usage"] or shape["reasoning_only_no_tool"] or dump_all:
            lines.extend(
                [
                    "#### Raw streamed chunks",
                    "",
                    "```json",
                    truncate_text(pretty_json(result["chunks"])),
                    "```",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "#### Non-streaming message summary",
                "",
                "```json",
                pretty_json(
                    {
                        "usage": shape.get("usage"),
                        "message_keys": shape.get("message_keys"),
                        "reasoning_content_len": shape.get("reasoning_content_len"),
                        "finish_reason": shape.get("finish_reason"),
                        "content_len": shape.get("content_len"),
                        "tool_call_count": shape.get("tool_call_count"),
                        "empty_no_usage": shape.get("empty_no_usage"),
                        "reasoning_only_no_tool": shape.get("reasoning_only_no_tool"),
                    }
                ),
                "```",
                "",
            ]
        )
        if shape["empty_no_usage"] or shape["reasoning_only_no_tool"] or dump_all:
            lines.extend(
                [
                    "#### Raw non-streaming response",
                    "",
                    "```json",
                    truncate_text(pretty_json(result["response"])),
                    "```",
                    "",
                ]
            )
    return lines


def command_raw_capture(args: argparse.Namespace) -> int:
    api_key = read_env_key(Path(args.env_file))
    client = make_client(api_key)
    (
        messages,
        tools,
        tool_choice,
        captured_extra_body,
        max_tokens,
        metadata,
    ) = resolve_request_from_args(args)
    model = canonical_model(args.model)
    kwargs = request_kwargs(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
        reasoning_effort=metadata.get("effective_reasoning_effort"),
        captured_extra_body=captured_extra_body,
        stream=True,
    )

    body = base_cli_notes(args)
    body.extend(
        [
            "### Probe",
            "",
            (
                "Captures both streaming and non-streaming responses for the same "
                "request. True empty/no-tool/no-usage responses and "
                "reasoning-only/no-tool responses include raw chunks, deltas, "
                "finish reasons, and usage evidence."
            ),
            "",
            f"- Model: `{model}`",
            f"- Request metadata: `{compact_json(metadata)}`",
            "",
        ]
    )

    for mode_label, caller in (("Streaming response", call_stream), ("Non-streaming response", call_nonstream)):
        try:
            result = caller(client, kwargs)
            body.extend(dump_raw_capture_result(mode_label, result, dump_all=args.dump_all))
        except Exception as exc:
            body.extend(
                [
                    f"### {mode_label}",
                    "",
                    "Request failed before a response was captured.",
                    "",
                    "```json",
                    pretty_json(describe_exception(exc)),
                    "```",
                    "",
                ]
            )

    append_markdown(output_target(args), "Raw Capture Probe", body, overwrite=args.overwrite)
    print(f"Wrote raw-capture findings to {output_target(args)}")
    return 0


def first_event_with_index(
    events: list[dict[str, Any]],
    kind: str,
) -> tuple[int | None, dict[str, Any] | None]:
    for index, event in enumerate(events):
        if event.get("kind") == kind:
            return index, event
    return None, None


def event_source_delta(event: dict[str, Any] | None) -> tuple[int, int] | None:
    if event is None:
        return None
    chunk_index = event.get("chunk_index")
    choice_index = event.get("choice_index")
    if isinstance(chunk_index, int) and isinstance(choice_index, int):
        return chunk_index, choice_index
    return None


def streaming_reasoning_shape(result: dict[str, Any]) -> dict[str, Any]:
    shape = result["shape"]
    events = shape.get("event_order") or []
    first_reasoning, first_reasoning_event = first_event_with_index(
        events, "reasoning_content"
    )
    first_tool, first_tool_event = first_event_with_index(events, "tool_calls")
    first_reasoning_source = event_source_delta(first_reasoning_event)
    first_tool_source = event_source_delta(first_tool_event)
    if first_tool is None:
        order = "no_tool_call"
    elif first_reasoning is None:
        order = "tool_call_without_reasoning_content"
    elif first_reasoning_source == first_tool_source:
        order = "reasoning_content_same_delta_as_tool_call"
    elif (
        first_reasoning_source is not None
        and first_tool_source is not None
        and first_reasoning_source < first_tool_source
    ):
        order = "reasoning_content_strictly_before_tool_call"
    elif (
        first_reasoning_source is not None
        and first_tool_source is not None
        and first_reasoning_source > first_tool_source
    ):
        order = "reasoning_content_strictly_after_tool_call"
    elif first_reasoning < first_tool:
        order = "reasoning_content_strictly_before_tool_call"
    else:
        order = "reasoning_content_strictly_after_tool_call"
    return {
        "tool_delta_count": shape.get("tool_delta_count"),
        "reasoning_content_len": shape.get("reasoning_content_len"),
        "content_len": shape.get("content_len"),
        "completion_tokens": shape.get("completion_tokens"),
        "finish_reasons": shape.get("finish_reasons"),
        "first_reasoning_event_index": first_reasoning,
        "first_tool_event_index": first_tool,
        "first_reasoning_source_delta": first_reasoning_source,
        "first_tool_source_delta": first_tool_source,
        "order": order,
        "event_order": events,
    }


def nonstream_reasoning_shape(result: dict[str, Any]) -> dict[str, Any]:
    shape = result["shape"]
    keys = shape.get("message_keys") or []
    try:
        reasoning_key_index = keys.index("reasoning_content")
    except ValueError:
        reasoning_key_index = None
    try:
        tool_calls_key_index = keys.index("tool_calls")
    except ValueError:
        tool_calls_key_index = None
    if not shape.get("tool_call_count"):
        order = "no_tool_call"
    elif reasoning_key_index is None:
        order = "tool_call_without_message_reasoning_content"
    elif tool_calls_key_index is None:
        order = "reasoning_content_without_tool_calls_key"
    elif reasoning_key_index < tool_calls_key_index:
        order = "message_reasoning_content_key_before_tool_calls_key"
    elif reasoning_key_index > tool_calls_key_index:
        order = "message_reasoning_content_key_after_tool_calls_key"
    else:
        order = "message_reasoning_content_key_same_index_as_tool_calls_key"
    return {
        "tool_call_count": shape.get("tool_call_count"),
        "reasoning_content_len": shape.get("reasoning_content_len"),
        "content_len": shape.get("content_len"),
        "completion_tokens": shape.get("completion_tokens"),
        "finish_reason": shape.get("finish_reason"),
        "message_keys": keys,
        "reasoning_key_index": reasoning_key_index,
        "tool_calls_key_index": tool_calls_key_index,
        "order": order,
    }


def command_reasoning_shape(args: argparse.Namespace) -> int:
    api_key = read_env_key(Path(args.env_file))
    client = make_client(api_key)
    (
        messages,
        tools,
        tool_choice,
        captured_extra_body,
        max_tokens,
        metadata,
    ) = resolve_request_from_args(args, default_reasoning_effort="high")
    model = GLM_MODEL

    body = base_cli_notes(args)
    body.extend(
        [
            "### Probe",
            "",
            (
                "GLM-5.2 reasoning-on evidence for step 4. Successful means the "
                "response produced tool-call deltas or a final message.tool_calls list."
            ),
            "",
            f"- Model: `{model}`",
            f"- Request metadata: `{compact_json(metadata)}`",
            f"- Samples per mode: `{args.samples}`",
            "",
        ]
    )

    stream_rows: list[list[Any]] = []
    nonstream_rows: list[list[Any]] = []
    detail_blocks: list[str] = []

    for sample_id in range(1, args.samples + 1):
        kwargs = request_kwargs(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
            reasoning_effort=metadata.get("effective_reasoning_effort"),
            captured_extra_body=captured_extra_body,
            stream=True,
        )

        try:
            stream_result = call_stream(client, kwargs)
            stream_shape = streaming_reasoning_shape(stream_result)
            stream_rows.append(
                [
                    sample_id,
                    stream_shape["tool_delta_count"],
                    stream_shape["reasoning_content_len"],
                    stream_shape["content_len"],
                    stream_shape["completion_tokens"],
                    stream_shape["order"],
                ]
            )
            if stream_shape["tool_delta_count"]:
                detail_blocks.append(
                    f"#### Streaming sample {sample_id} event order\n\n"
                    "```json\n"
                    f"{pretty_json(stream_shape['event_order'])}\n"
                    "```"
                )
        except Exception as exc:
            stream_rows.append([sample_id, "ERROR", "", "", "", type(exc).__name__])
            detail_blocks.append(
                f"#### Streaming sample {sample_id} error\n\n"
                "```json\n"
                f"{pretty_json(describe_exception(exc))}\n"
                "```"
            )

        try:
            nonstream_result = call_nonstream(client, kwargs)
            ns_shape = nonstream_reasoning_shape(nonstream_result)
            nonstream_rows.append(
                [
                    sample_id,
                    ns_shape["tool_call_count"],
                    ns_shape["reasoning_content_len"],
                    ns_shape["content_len"],
                    ns_shape["completion_tokens"],
                    ns_shape["order"],
                ]
            )
            if ns_shape["tool_call_count"]:
                detail_blocks.append(
                    f"#### Non-streaming sample {sample_id} message shape\n\n"
                    "```json\n"
                    f"{pretty_json(ns_shape)}\n"
                    "```"
                )
        except Exception as exc:
            nonstream_rows.append([sample_id, "ERROR", "", "", "", type(exc).__name__])
            detail_blocks.append(
                f"#### Non-streaming sample {sample_id} error\n\n"
                "```json\n"
                f"{pretty_json(describe_exception(exc))}\n"
                "```"
            )

    body.extend(["### Streaming", ""])
    body.extend(
        markdown_table(
            [
                "sample",
                "tool_deltas",
                "reasoning_content_len",
                "content_len",
                "completion_tokens",
                "order",
            ],
            stream_rows,
        )
    )
    body.extend(["", "### Non-streaming", ""])
    body.extend(
        markdown_table(
            [
                "sample",
                "tool_calls",
                "reasoning_content_len",
                "content_len",
                "completion_tokens",
                "order",
            ],
            nonstream_rows,
        )
    )
    if detail_blocks:
        body.extend(["", *detail_blocks])

    append_markdown(
        output_target(args),
        "Reasoning Shape Probe",
        body,
        overwrite=args.overwrite,
    )
    print(f"Wrote reasoning-shape findings to {output_target(args)}")
    return 0


def summarize_force_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [item for item in samples if item.get("ok")]
    errors = [item for item in samples if not item.get("ok")]
    empty = [item for item in ok if item.get("empty_no_usage")]
    reasoning_only = [item for item in ok if item.get("reasoning_only_no_tool")]
    content = [item for item in ok if item.get("content_len", 0) > 0]
    tool = [item for item in ok if item.get("tool_count", 0) > 0]
    error_categories: dict[str, int] = {}
    for item in errors:
        category = classify_force_error(item.get("error") or {})
        error_categories[category] = error_categories.get(category, 0) + 1
    return {
        "requested": len(samples),
        "ok": len(ok),
        "errors": len(errors),
        "empty_no_usage": len(empty),
        "reasoning_only_no_tool": len(reasoning_only),
        "content_present": len(content),
        "tool_call_present": len(tool),
        "first_error": errors[0].get("error") if errors else None,
        "error_categories": error_categories,
        "api_parameter_rejection_errors": error_categories.get(
            "api_parameter_rejection", 0
        ),
    }


def compact_error_text(error: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("message", "code", "api_type", "type", "response_text"):
        value = error.get(key)
        if value is not None:
            parts.append(str(value))
    body = error.get("body")
    if body is not None:
        parts.append(compact_json(body))
    return " ".join(parts).lower()


def error_status_code(error: dict[str, Any]) -> int | None:
    for key in ("status_code", "response_status_code"):
        value = error.get(key)
        if isinstance(value, int):
            return value
    return None


def is_force_parameter_rejection(error: dict[str, Any]) -> bool:
    status_code = error_status_code(error)
    text = compact_error_text(error)
    mentions_parameter = (
        "force_nonempty_content" in text
        or "chat_template_kwargs" in text
    )
    invalid_request = any(
        marker in text
        for marker in (
            "invalid_request",
            "invalid request",
            "invalid",
            "unknown",
            "unrecognized",
            "unexpected",
            "not allowed",
            "not supported",
            "extra_forbidden",
        )
    )
    return status_code == 400 and mentions_parameter and invalid_request


def classify_force_error(error: dict[str, Any]) -> str:
    if is_force_parameter_rejection(error):
        return "api_parameter_rejection"
    status_code = error_status_code(error)
    text = compact_error_text(error)
    exception_type = str(error.get("exception_type") or "").lower()
    if status_code in (401, 403):
        return "auth_failure"
    if "timeout" in exception_type or "timeout" in text:
        return "timeout"
    if "connection" in exception_type or "network" in text:
        return "transport_failure"
    if status_code is not None:
        if status_code >= 500 or status_code in (408, 409, 429):
            return "transport_or_service_failure"
        if status_code >= 400:
            return "api_error_non_parameter"
    return "unknown_error"


def meaningful_rate_change(
    *,
    control_count: int,
    forced_count: int,
    control_ok: int,
    forced_ok: int,
    direction: str,
) -> bool:
    comparable_ok = min(control_ok, forced_ok)
    if comparable_ok <= 0:
        return False
    if direction == "decrease":
        count_delta = control_count - forced_count
        rate_delta = (control_count / control_ok) - (forced_count / forced_ok)
    elif direction == "increase":
        count_delta = forced_count - control_count
        rate_delta = (forced_count / forced_ok) - (control_count / control_ok)
    else:
        raise DiagnosticError(f"unknown force comparison direction: {direction}")
    return count_delta >= 2 and rate_delta >= 0.20


def classify_force_result(control: dict[str, Any], forced: dict[str, Any]) -> str:
    if control["ok"] == 0:
        return "inconclusive_no_successful_control_samples"
    if (
        forced["ok"] == 0
        and forced["errors"] > 0
        and forced["api_parameter_rejection_errors"] == forced["errors"]
    ):
        return "api_parameter_rejected"
    if forced["ok"] == 0:
        return "inconclusive_forced_condition_failed"
    if meaningful_rate_change(
        control_count=control["empty_no_usage"],
        forced_count=forced["empty_no_usage"],
        control_ok=control["ok"],
        forced_ok=forced["ok"],
        direction="decrease",
    ):
        return "weak_observational_evidence_honored_reduced_empty_no_usage"
    if meaningful_rate_change(
        control_count=control["content_present"],
        forced_count=forced["content_present"],
        control_ok=control["ok"],
        forced_ok=forced["ok"],
        direction="increase",
    ):
        return "weak_observational_evidence_honored_more_nonempty_content"
    if (
        forced["empty_no_usage"] < control["empty_no_usage"]
        or forced["content_present"] > control["content_present"]
    ):
        return "accepted_small_difference_inconclusive"
    return "accepted_no_effect_observed"


def command_force_nonempty(args: argparse.Namespace) -> int:
    api_key = read_env_key(Path(args.env_file))
    messages, tools, tool_choice, _captured_extra, default_max_tokens = fixed_request()
    max_tokens = args.max_tokens or default_max_tokens
    body = base_cli_notes(args)
    body.extend(
        [
            "### Probe",
            "",
            (
                "Sends the same tools request as a control and with "
                "`extra_body.chat_template_kwargs.force_nonempty_content=true`. "
                "Classification is based on whether Baseten rejects the parameter "
                "or whether the forced sample changes empty/content behavior. "
                "Positive honored labels are weak observational evidence."
            ),
            "",
            f"- Models: `{', '.join(selected_models(args.model))}`",
            f"- Mode: `{args.mode}`",
            f"- Reasoning effort: `{args.reasoning_effort}`",
            f"- Samples per condition/model: `{args.samples}`",
            f"- Max tokens: `{max_tokens}`",
            "",
        ]
    )

    rows: list[list[Any]] = []
    detail_blocks: list[str] = []
    for model in selected_models(args.model):
        condition_samples: dict[str, list[dict[str, Any]]] = {"control": [], "forced": []}
        for condition, force_value in (("control", None), ("forced", True)):
            for sample_id in range(1, args.samples + 1):
                client = make_client(api_key)
                kwargs = request_kwargs(
                    model=model,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=max_tokens,
                    reasoning_effort=args.reasoning_effort,
                    force_nonempty_content=force_value,
                    stream=(args.mode == "stream"),
                )
                try:
                    result = call_stream(client, kwargs) if args.mode == "stream" else call_nonstream(client, kwargs)
                    shape = result["shape"]
                    condition_samples[condition].append(
                        {
                            "sample_id": sample_id,
                            "ok": True,
                            "empty_no_usage": bool(shape["empty_no_usage"]),
                            "reasoning_only_no_tool": bool(
                                shape["reasoning_only_no_tool"]
                            ),
                            "content_len": shape.get("content_len", 0),
                            "tool_count": shape.get(
                                "tool_delta_count", shape.get("tool_call_count", 0)
                            ),
                            "completion_tokens": shape.get("completion_tokens"),
                            "finish": shape.get("finish_reasons")
                            or shape.get("finish_reason"),
                        }
                    )
                except Exception as exc:
                    condition_samples[condition].append(
                        {
                            "sample_id": sample_id,
                            "ok": False,
                            "empty_no_usage": False,
                            "reasoning_only_no_tool": False,
                            "error": describe_exception(exc),
                        }
                    )

        control_summary = summarize_force_samples(condition_samples["control"])
        forced_summary = summarize_force_samples(condition_samples["forced"])
        classification = classify_force_result(control_summary, forced_summary)
        rows.append(
            [
                model,
                classification,
                control_summary["ok"],
                control_summary["errors"],
                control_summary["empty_no_usage"],
                control_summary["reasoning_only_no_tool"],
                control_summary["content_present"],
                forced_summary["ok"],
                forced_summary["errors"],
                forced_summary["empty_no_usage"],
                forced_summary["reasoning_only_no_tool"],
                forced_summary["content_present"],
            ]
        )
        if control_summary.get("first_error") or forced_summary.get("first_error"):
            detail_blocks.append(
                f"#### First force-nonempty errors for `{model}`\n\n"
                "```json\n"
                + pretty_json(
                    {
                        "control_first_error": control_summary.get("first_error"),
                        "forced_first_error": forced_summary.get("first_error"),
                        "control_error_categories": control_summary.get(
                            "error_categories"
                        ),
                        "forced_error_categories": forced_summary.get(
                            "error_categories"
                        ),
                    }
                )
                + "\n```"
            )

    body.extend(
        markdown_table(
            [
                "model",
                "classification",
                "control_ok",
                "control_errors",
                "control_empty",
                "control_reasoning_only",
                "control_content",
                "forced_ok",
                "forced_errors",
                "forced_empty",
                "forced_reasoning_only",
                "forced_content",
            ],
            rows,
        )
    )
    if detail_blocks:
        body.extend(["", *detail_blocks])

    append_markdown(
        output_target(args),
        "force_nonempty_content Probe",
        body,
        overwrite=args.overwrite,
    )
    print(f"Wrote force_nonempty_content findings to {output_target(args)}")
    return 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help=f"dotenv file containing BASETEN_API_KEY (default: {DEFAULT_ENV_FILE})",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"markdown findings path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite the markdown file instead of appending a section",
    )


def add_request_replay_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--run-json",
        help=(
            "Optional captured run JSON. The script reads inference_inputs[]."
            "messages_for_llm and provider_invocation_params.tools."
        ),
    )
    parser.add_argument(
        "--entry-index",
        type=int,
        default=None,
        help="0-based inference_inputs entry to replay when --run-json is set",
    )
    parser.add_argument(
        "--inference-index",
        type=int,
        default=None,
        help="inference_inputs[].inference_index value to replay",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnostic-only Baseten empty-turn probe for GLM-5.2 and "
            "Nemotron-3-Ultra. Writes markdown findings; never produces "
            "leaderboard data."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    concurrency = subparsers.add_parser(
        "concurrency",
        help="run bounded empty/no-usage rate tests at concurrency levels",
    )
    add_common_args(concurrency)
    concurrency.add_argument(
        "--model",
        default="all",
        help="all, glm, nemotron, or an exact model name (default: all)",
    )
    concurrency.add_argument(
        "--levels",
        default="1,2,6",
        help="comma-separated concurrency levels (default: 1,2,6)",
    )
    concurrency.add_argument(
        "--samples",
        type=int,
        default=30,
        help=(
            "bounded samples per model and level "
            f"(default: 30, max: {MAX_CONCURRENCY_SAMPLES})"
        ),
    )
    concurrency.add_argument(
        "--mode",
        choices=["stream", "nonstream"],
        default="stream",
        help="request mode for the concurrency probe (default: stream)",
    )
    concurrency.add_argument(
        "--reasoning-effort",
        choices=["none", "minimal", "low", "medium", "high"],
        default="none",
        help="Baseten reasoning.effort for this probe (default: none)",
    )
    concurrency.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"max_tokens for each request (default: {DEFAULT_MAX_TOKENS})",
    )
    concurrency.set_defaults(func=command_concurrency)

    raw = subparsers.add_parser(
        "raw-capture",
        help="capture streaming and non-streaming raw responses for one request",
    )
    add_common_args(raw)
    add_request_replay_args(raw)
    raw.add_argument(
        "--model",
        default="glm",
        help="glm, nemotron, or an exact model name (default: glm)",
    )
    raw.add_argument(
        "--reasoning-effort",
        choices=["none", "minimal", "low", "medium", "high"],
        default=None,
        help="override Baseten reasoning.effort; replay defaults to captured setting",
    )
    raw.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="override max_tokens; replay defaults to captured setting",
    )
    raw.add_argument(
        "--dump-all",
        action="store_true",
        help="dump raw responses even when they are not empty/no-usage",
    )
    raw.set_defaults(func=command_raw_capture)

    reasoning = subparsers.add_parser(
        "reasoning-shape",
        help="inspect GLM-5.2 reasoning_content shape around tool calls",
    )
    add_common_args(reasoning)
    add_request_replay_args(reasoning)
    reasoning.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        default="high",
        help="GLM reasoning-on effort (default: high)",
    )
    reasoning.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="override max_tokens; replay defaults to captured setting",
    )
    reasoning.add_argument(
        "--samples",
        type=int,
        default=3,
        help=(
            "bounded samples per streaming and non-streaming mode "
            f"(default: 3, max: {MAX_REASONING_SHAPE_SAMPLES})"
        ),
    )
    reasoning.set_defaults(func=command_reasoning_shape)

    force = subparsers.add_parser(
        "force-nonempty",
        help="test chat_template_kwargs.force_nonempty_content control vs forced",
    )
    add_common_args(force)
    force.add_argument(
        "--model",
        default="all",
        help="all, glm, nemotron, or an exact model name (default: all)",
    )
    force.add_argument(
        "--mode",
        choices=["stream", "nonstream"],
        default="stream",
        help="request mode for the force probe (default: stream)",
    )
    force.add_argument(
        "--reasoning-effort",
        choices=["none", "minimal", "low", "medium", "high"],
        default="high",
        help="Baseten reasoning.effort for this probe (default: high)",
    )
    force.add_argument(
        "--samples",
        type=int,
        default=5,
        help=(
            "bounded samples per model and condition "
            f"(default: 5, max: {MAX_FORCE_NONEMPTY_SAMPLES})"
        ),
    )
    force.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"max_tokens for each request (default: {DEFAULT_MAX_TOKENS})",
    )
    force.set_defaults(func=command_force_nonempty)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if getattr(args, "samples", 1) < 1:
            raise DiagnosticError("--samples must be positive")
        sample_caps = {
            "concurrency": MAX_CONCURRENCY_SAMPLES,
            "reasoning-shape": MAX_REASONING_SHAPE_SAMPLES,
            "force-nonempty": MAX_FORCE_NONEMPTY_SAMPLES,
        }
        sample_cap = sample_caps.get(getattr(args, "command", ""))
        if sample_cap is not None and args.samples > sample_cap:
            raise DiagnosticError(
                f"--samples for {args.command} must be between 1 and {sample_cap}"
            )
        if getattr(args, "max_tokens", None) is not None and args.max_tokens < 1:
            raise DiagnosticError("--max-tokens must be positive")
        return args.func(args)
    except DiagnosticError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
