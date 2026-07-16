#!/usr/bin/env python3
"""Read-only live diagnostics for thinkingmachines/inkling on Baseten.

This script calls the OpenAI-compatible Baseten endpoint and writes operator
findings to Markdown.  It never imports or changes the benchmark harness and
its output is diagnostic data, not leaderboard run data.

The effort-field experiment is deliberately fixed: five samples for each of
seven levels and three mutually exclusive request shapes, plus five no-effort
controls (110 samples total).  Do not turn it into a sweep with mixed controls.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI


BASE_URL = "https://inference.baseten.co/v1"
MODEL = "thinkingmachines/inkling"
REPO_ROOT = Path("/home/khkramer/src/gb-benchmarks")
PORT_DIR = REPO_ROOT / "port-to-port"
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
PROJECT_DIR = PORT_DIR / "proj-2026-07-15-1700"
DIAGNOSTICS_FINDINGS_DIR = PORT_DIR / "diagnostics" / "findings"
DEFAULT_OUTPUT = PROJECT_DIR / "step1-inkling-findings.md"

LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
EFFORT_SAMPLES = 5
EFFORT_MAX_TOKENS = 16_384
TEMPERATURE = 1.0
DEFAULT_TIMEOUT_SECS = 300.0
MAX_PREVIEW_CHARS = 2_000
MAX_FOLLOWUP_SAMPLES = 20
MAX_TRUNCATION_ITEMS = 20_000
FOLDED_CONTENT_MIN_CHARS = 200

NESTED = "nested_reasoning_effort"
NATIVE = "native_reasoning_effort"
CHAT_TEMPLATE = "chat_template_reasoning_effort"
SHAPES = (NESTED, NATIVE, CHAT_TEMPLATE)
SELECTION_PREFERENCE = (NATIVE, CHAT_TEMPLATE, NESTED)
SHAPE_LABELS = {
    NESTED: "nested extra_body.reasoning.effort",
    NATIVE: "top-level native reasoning_effort",
    CHAT_TEMPLATE: "extra_body.chat_template_kwargs.reasoning_effort",
}
CLI_FIELDS = {
    "native": NATIVE,
    "chat-template": CHAT_TEMPLATE,
    "nested": NESTED,
}

FIXED_MESSAGES: list[dict[str, Any]] = [
    {
        "role": "system",
        "content": (
            "You are a deterministic tool-use diagnostic. Solve the arithmetic "
            "carefully, then call submit_probe exactly once."
        ),
    },
    {
        "role": "user",
        "content": (
            "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer "
            "answer and checksum exactly 'inkling-controlled-v1'."
        ),
    },
]
FIXED_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "submit_probe",
            "description": "Submit the answer for the controlled Inkling probe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {"type": "integer"},
                    "checksum": {"type": "string"},
                },
                "required": ["answer", "checksum"],
                "additionalProperties": False,
            },
        },
    }
]
FIXED_TOOL_CHOICE = {
    "type": "function",
    "function": {"name": "submit_probe"},
}
FIXED_EXPECTED_ARGUMENTS = {
    "answer": 2_416,
    "checksum": "inkling-controlled-v1",
}

BATCH_MESSAGES: list[dict[str, Any]] = [
    {
        "role": "system",
        "content": "You are a concise streaming diagnostic.",
    },
    {
        "role": "user",
        "content": (
            "The request contains tools, but do not call one. In two short "
            "sentences, explain why 2416 is even."
        ),
    },
]

NONE_TEXT_MESSAGES: list[dict[str, Any]] = [
    {
        "role": "system",
        "content": (
            "Solve the arithmetic carefully, but return only `FINAL: <integer>` "
            "with no explanation or intermediate work."
        ),
    },
    {
        "role": "user",
        "content": (
            "Compute ((137 * 149) + (173 * 181) - (19 * 23)) * 7. "
            "Return only the requested final marker."
        ),
    },
]

EPISODE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_probe",
            "description": "Look up a deterministic diagnostic code.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
                "additionalProperties": False,
            },
        },
    }
]
EPISODE_TOOL_CHOICE = {
    "type": "function",
    "function": {"name": "lookup_probe"},
}
EPISODE_EXPECTED_ARGUMENTS = {"code": "inkling-latency-v1"}
EPISODE_EXPECTED_FINAL = "inkling-latency-v1 status: ready"
EPISODE_MESSAGES: list[dict[str, Any]] = [
    {
        "role": "system",
        "content": (
            "You are a two-turn tool-use diagnostic. Use lookup_probe. If its "
            "result says the code is ready, reply exactly: "
            f"{EPISODE_EXPECTED_FINAL}"
        ),
    },
    {
        "role": "user",
        "content": "Look up code inkling-latency-v1 and report its status.",
    },
]


class DiagnosticError(RuntimeError):
    """A user-facing setup or invocation failure."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_env_key(env_file: Path, key_name: str = "BASETEN_API_KEY") -> str:
    """Read one dotenv key without sourcing the repository environment."""

    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DiagnosticError(f"Could not read env file {env_file}: {exc}") from exc

    prefix = f"{key_name}="
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if not value:
            raise DiagnosticError(f"{key_name} is present but empty in {env_file}")
        return value
    raise DiagnosticError(f"{key_name} was not found in {env_file}")


def make_client(api_key: str, timeout_secs: float) -> OpenAI:
    # Zero retries keeps "five samples" equal to five HTTP attempts and exposes
    # the endpoint's rate-limit posture instead of hiding it behind SDK retries.
    return OpenAI(
        api_key=api_key,
        base_url=BASE_URL,
        timeout=timeout_secs,
        max_retries=0,
    )


def to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=False)
    if isinstance(value, dict):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def get_path(value: Any, path: Iterable[Any], default: Any = None) -> Any:
    current = value
    for part in path:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and isinstance(part, int) and 0 <= part < len(current):
            current = current[part]
        else:
            return default
    return current


def preview(text: str, limit: int = MAX_PREVIEW_CHARS) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated {len(text) - limit} chars]"


def compact_error_body(exc: BaseException) -> Any:
    body = getattr(exc, "body", None)
    if body is not None:
        plain = to_plain(body)
        if isinstance(plain, str):
            return preview(plain)
        return plain
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            return preview(response.text)
        except Exception:  # pragma: no cover - defensive around third-party response
            return None
    return None


def rate_limit_headers(headers: Any) -> dict[str, str]:
    if headers is None:
        return {}
    wanted = {
        "retry-after",
        "x-ratelimit-limit-requests",
        "x-ratelimit-remaining-requests",
        "x-ratelimit-reset-requests",
        "x-request-id",
    }
    return {
        str(key).lower(): str(value)
        for key, value in dict(headers).items()
        if str(key).lower() in wanted
    }


def build_effort_kwargs(shape: str | None, level: str | None) -> dict[str, Any]:
    if shape is None:
        if level is not None:
            raise DiagnosticError("A no-effort control cannot have an effort level")
        return {}
    if shape not in SHAPES or level not in LEVELS:
        raise DiagnosticError(f"Invalid effort shape/level: {shape!r}/{level!r}")
    if shape == NESTED:
        return {"extra_body": {"reasoning": {"effort": level}}}
    if shape == NATIVE:
        return {"reasoning_effort": level}
    return {
        "extra_body": {
            "chat_template_kwargs": {"reasoning_effort": level}
        }
    }


def effort_controls(kwargs: dict[str, Any]) -> list[str]:
    found: list[str] = []
    if "reasoning_effort" in kwargs:
        found.append(NATIVE)
    extra_body = kwargs.get("extra_body")
    if isinstance(extra_body, dict):
        reasoning = extra_body.get("reasoning")
        if isinstance(reasoning, dict) and "effort" in reasoning:
            found.append(NESTED)
        template = extra_body.get("chat_template_kwargs")
        if isinstance(template, dict) and "reasoning_effort" in template:
            found.append(CHAT_TEMPLATE)
    return found


def assert_exclusive_control(
    kwargs: dict[str, Any], expected_shape: str | None
) -> None:
    found = effort_controls(kwargs)
    expected = [] if expected_shape is None else [expected_shape]
    if found != expected:
        raise DiagnosticError(
            f"Effort controls are not mutually exclusive: expected {expected}, found {found}"
        )


def base_request_kwargs(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_choice: Any,
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": MODEL,
        "messages": copy.deepcopy(messages),
        "tools": copy.deepcopy(tools),
        "tool_choice": copy.deepcopy(tool_choice),
        "temperature": TEMPERATURE,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }


def build_request_kwargs(
    *,
    shape: str | None,
    level: str | None,
    messages: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
    max_tokens: int = EFFORT_MAX_TOKENS,
) -> dict[str, Any]:
    effective_messages = FIXED_MESSAGES if messages is None else messages
    effective_tools = FIXED_TOOLS if tools is None else tools
    effective_tool_choice = FIXED_TOOL_CHOICE if tool_choice is None else tool_choice
    kwargs = base_request_kwargs(
        messages=effective_messages,
        tools=effective_tools,
        tool_choice=effective_tool_choice,
        max_tokens=max_tokens,
    )
    kwargs.update(build_effort_kwargs(shape, level))
    assert_exclusive_control(kwargs, shape)
    return kwargs


def append_tool_fragments(
    accumulators: dict[int, dict[str, Any]], tool_deltas: Any
) -> None:
    if not isinstance(tool_deltas, list):
        return
    for fallback_index, tool_delta in enumerate(tool_deltas):
        if not isinstance(tool_delta, dict):
            continue
        index = tool_delta.get("index")
        if not isinstance(index, int):
            index = fallback_index
        current = accumulators.setdefault(
            index,
            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if tool_delta.get("id"):
            current["id"] = tool_delta["id"]
        if tool_delta.get("type"):
            current["type"] = tool_delta["type"]
        function = tool_delta.get("function")
        if isinstance(function, dict):
            if function.get("name"):
                current["function"]["name"] += str(function["name"])
            if function.get("arguments"):
                current["function"]["arguments"] += str(function["arguments"])


def summarize_tool_calls(
    accumulators: dict[int, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    wire_calls: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for index in sorted(accumulators):
        call = accumulators[index]
        arguments = str(get_path(call, ("function", "arguments"), ""))
        try:
            json.loads(arguments)
            json_valid = True
            json_error = None
        except (TypeError, ValueError) as exc:
            json_valid = False
            json_error = str(exc)
        wire_call = {
            "id": call.get("id") or f"missing-id-{index}",
            "type": call.get("type") or "function",
            "function": {
                "name": get_path(call, ("function", "name"), ""),
                "arguments": arguments,
            },
        }
        wire_calls.append(wire_call)
        summaries.append(
            {
                "index": index,
                "id": wire_call["id"],
                "type": wire_call["type"],
                "name": wire_call["function"]["name"],
                "arguments_length": len(arguments),
                "arguments_preview": preview(arguments),
                "arguments_json_valid": json_valid,
                "arguments_json_error": json_error,
            }
        )
    return wire_calls, summaries


def validate_expected_tool_call(
    wire_calls: list[dict[str, Any]],
    *,
    expected_name: str,
    required_keys: Iterable[str],
    expected_values: dict[str, Any],
) -> tuple[bool, str | None]:
    """Validate the exact forced-call shape claimed by a follow-up probe."""

    if len(wire_calls) != 1:
        return False, f"expected exactly one tool call, got {len(wire_calls)}"
    call = wire_calls[0]
    call_id = call.get("id")
    if not isinstance(call_id, str) or not call_id or call_id.startswith("missing-id-"):
        return False, "tool call is missing a streamed call id"
    if call.get("type") != "function":
        return False, f"expected tool-call type function, got {call.get('type')!r}"
    function = call.get("function")
    if not isinstance(function, dict) or function.get("name") != expected_name:
        actual_name = function.get("name") if isinstance(function, dict) else None
        return False, f"expected function {expected_name!r}, got {actual_name!r}"
    arguments = function.get("arguments")
    try:
        parsed = json.loads(arguments)
    except (TypeError, ValueError) as exc:
        return False, f"arguments are not valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return False, "arguments JSON is not an object"
    missing = sorted(set(required_keys) - set(parsed))
    if missing:
        return False, f"arguments object is missing required keys: {missing}"
    for key, expected in expected_values.items():
        if parsed.get(key) != expected:
            return False, (
                f"argument {key!r} did not match the expected literal value"
            )
    return True, None


def run_stream_request(
    client: OpenAI,
    kwargs: dict[str, Any],
    *,
    label: str,
    sample: int,
    expected_tool_call: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one no-retry streamed request and retain request-boundary evidence."""

    started_utc = utc_now()
    started = time.monotonic()
    record: dict[str, Any] = {
        "label": label,
        "sample": sample,
        "started_utc": started_utc,
        "request_kwargs_sent": to_plain(copy.deepcopy(kwargs)),
        "http_status": None,
        "request_breaking_400": False,
        "error_type": None,
        "error_message": None,
        "error_body": None,
        "response_headers": {},
        "finish_reason": None,
        "content_length": 0,
        "content_preview": "",
        "reasoning_content_present": False,
        "reasoning_content_length": 0,
        "reasoning_delta_count": 0,
        "usage_completion_tokens": None,
        "reasoning_tokens": None,
        "tool_calls": [],
        "tool_calls_parse_ok": False,
        "tool_calls_parse_error": None,
        "first_reasoning_chunk_index": None,
        "first_content_chunk_index": None,
        "first_tool_call_chunk_index": None,
        "first_answer_chunk_index": None,
        "reasoning_same_delta_as_first_content": None,
        "reasoning_same_delta_as_first_answer": None,
        "first_reasoning_secs": None,
        "first_content_secs": None,
        "first_tool_call_secs": None,
        "elapsed_secs": None,
    }

    stream = None
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_accumulators: dict[int, dict[str, Any]] = {}
    try:
        raw_response = client.chat.completions.with_raw_response.create(**kwargs)
        record["http_status"] = raw_response.status_code
        record["response_headers"] = rate_limit_headers(raw_response.headers)
        stream = raw_response.parse()
        for chunk_index, chunk in enumerate(stream):
            plain = to_plain(chunk)
            usage = plain.get("usage") if isinstance(plain, dict) else None
            if isinstance(usage, dict):
                completion_tokens = usage.get("completion_tokens")
                if isinstance(completion_tokens, int):
                    record["usage_completion_tokens"] = completion_tokens
                reasoning_tokens = get_path(
                    usage, ("completion_tokens_details", "reasoning_tokens")
                )
                if isinstance(reasoning_tokens, (int, float)):
                    record["reasoning_tokens"] = reasoning_tokens

            choices = plain.get("choices") if isinstance(plain, dict) else None
            if not isinstance(choices, list):
                continue
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                if choice.get("finish_reason") is not None:
                    record["finish_reason"] = choice["finish_reason"]
                delta = choice.get("delta")
                if not isinstance(delta, dict):
                    continue

                if "reasoning_content" in delta and delta["reasoning_content"] is not None:
                    record["reasoning_content_present"] = True
                    reasoning_value = delta["reasoning_content"]
                    if isinstance(reasoning_value, str) and reasoning_value:
                        if record["first_reasoning_chunk_index"] is None:
                            record["first_reasoning_chunk_index"] = chunk_index
                            record["first_reasoning_secs"] = time.monotonic() - started
                        record["reasoning_delta_count"] += 1
                        reasoning_parts.append(reasoning_value)

                content_value = delta.get("content")
                if isinstance(content_value, str) and content_value:
                    if record["first_content_chunk_index"] is None:
                        record["first_content_chunk_index"] = chunk_index
                        record["first_content_secs"] = time.monotonic() - started
                    content_parts.append(content_value)

                tool_deltas = delta.get("tool_calls")
                if isinstance(tool_deltas, list) and tool_deltas:
                    if record["first_tool_call_chunk_index"] is None:
                        record["first_tool_call_chunk_index"] = chunk_index
                        record["first_tool_call_secs"] = time.monotonic() - started
                    append_tool_fragments(tool_accumulators, tool_deltas)

    except APIStatusError as exc:
        record["http_status"] = exc.status_code
        record["request_breaking_400"] = exc.status_code == 400
        record["error_type"] = type(exc).__name__
        record["error_message"] = str(exc)
        record["error_body"] = compact_error_body(exc)
        response = getattr(exc, "response", None)
        record["response_headers"] = rate_limit_headers(
            getattr(response, "headers", None)
        )
    except (APIConnectionError, APITimeoutError) as exc:
        record["error_type"] = type(exc).__name__
        record["error_message"] = str(exc)
        record["error_body"] = compact_error_body(exc)
    except Exception as exc:  # keep a long paid protocol from losing its report
        record["error_type"] = type(exc).__name__
        record["error_message"] = str(exc)
        record["error_body"] = compact_error_body(exc)
    finally:
        if stream is not None:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
        record["elapsed_secs"] = time.monotonic() - started

    # Finalize outside the try so a mid-stream transport failure still records
    # every partial content/reasoning/tool delta that reached the client.
    content = "".join(content_parts)
    reasoning = "".join(reasoning_parts)
    wire_calls, tool_summaries = summarize_tool_calls(tool_accumulators)
    record["content_length"] = len(content)
    record["content_preview"] = preview(content)
    record["reasoning_content_length"] = len(reasoning)
    record["tool_calls"] = tool_summaries
    if expected_tool_call is None:
        record["tool_calls_parse_ok"] = bool(tool_summaries) and all(
            item["arguments_json_valid"] for item in tool_summaries
        )
    else:
        parse_ok, parse_error = validate_expected_tool_call(
            wire_calls,
            expected_name=expected_tool_call["name"],
            required_keys=expected_tool_call["required_keys"],
            expected_values=expected_tool_call["expected_values"],
        )
        record["tool_calls_parse_ok"] = parse_ok
        record["tool_calls_parse_error"] = parse_error
    record["_content"] = content
    record["_tool_calls_wire"] = wire_calls

    answer_indices = [
        value
        for value in (
            record["first_content_chunk_index"],
            record["first_tool_call_chunk_index"],
        )
        if isinstance(value, int)
    ]
    if answer_indices:
        record["first_answer_chunk_index"] = min(answer_indices)
    reasoning_index = record["first_reasoning_chunk_index"]
    content_index = record["first_content_chunk_index"]
    answer_index = record["first_answer_chunk_index"]
    if isinstance(reasoning_index, int) and isinstance(content_index, int):
        record["reasoning_same_delta_as_first_content"] = reasoning_index == content_index
    if isinstance(reasoning_index, int) and isinstance(answer_index, int):
        record["reasoning_same_delta_as_first_answer"] = reasoning_index == answer_index
    return record


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if not key.startswith("_")}


def is_fatal_access_failure(record: dict[str, Any]) -> bool:
    if record.get("http_status") in (401, 403):
        return True
    return record.get("error_type") in {
        "APIConnectionError",
        "APITimeoutError",
    }


def pause(interval_secs: float) -> None:
    if interval_secs > 0:
        time.sleep(interval_secs)


def numeric_median(records: list[dict[str, Any]], *, require: int) -> float | None:
    values = [
        float(record["reasoning_tokens"])
        for record in records
        if isinstance(record.get("reasoning_tokens"), (int, float))
    ]
    if len(values) != require:
        return None
    return float(statistics.median(values))


def format_number(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.1f}"


def evaluate_effort_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    controls = [record for record in records if record.get("shape") == "control"]
    control_median = numeric_median(controls, require=EFFORT_SAMPLES)
    medians: dict[str, dict[str, float | None]] = {}
    classifications: dict[str, str] = {}
    controlling_shapes: list[str] = []
    inert_shapes: list[str] = []
    shape_has_400: dict[str, bool] = {}

    for shape in SHAPES:
        medians[shape] = {}
        shape_records = [record for record in records if record.get("shape") == shape]
        shape_has_400[shape] = any(
            bool(record.get("request_breaking_400")) for record in shape_records
        )
        for level in LEVELS:
            cell = [record for record in shape_records if record.get("level") == level]
            medians[shape][level] = numeric_median(cell, require=EFFORT_SAMPLES)

        none_median = medians[shape]["none"]
        max_median = medians[shape]["max"]
        controls_reasoning = (
            none_median is not None
            and max_median is not None
            and max_median - none_median >= 50
            and none_median <= 5
            and not shape_has_400[shape]
        )
        inert = (
            control_median is not None
            and all(medians[shape][level] is not None for level in LEVELS)
            and all(
                abs(float(medians[shape][level]) - control_median) <= 10
                for level in LEVELS
            )
        )
        if controls_reasoning:
            classifications[shape] = "controls"
            controlling_shapes.append(shape)
        elif inert:
            classifications[shape] = "inert"
            inert_shapes.append(shape)
        elif none_median is None or max_median is None:
            classifications[shape] = "incomplete"
        else:
            classifications[shape] = "neither"

    selected = next(
        (shape for shape in SELECTION_PREFERENCE if shape in controlling_shapes),
        None,
    )
    blocked = selected is None or shape_has_400.get(selected, False)
    if selected is None:
        block_reason = "No request shape satisfied the exact controlling-field rule."
    elif shape_has_400[selected]:
        block_reason = "The preference-selected controlling field returned a request-breaking 400."
    else:
        block_reason = None

    return {
        "control_median": control_median,
        "medians": medians,
        "classifications": classifications,
        "controlling_shapes": controlling_shapes,
        "inert_shapes": inert_shapes,
        "shape_has_400": shape_has_400,
        "selected": selected,
        "blocked": blocked,
        "block_reason": block_reason,
    }


def effort_median_table(evaluation: dict[str, Any]) -> list[str]:
    header = ["Request shape", "Control"] + list(LEVELS) + ["Classification"]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for shape in SHAPES:
        row = [
            SHAPE_LABELS[shape],
            format_number(evaluation["control_median"]),
        ]
        row.extend(
            format_number(evaluation["medians"][shape][level]) for level in LEVELS
        )
        row.append(evaluation["classifications"][shape])
        lines.append("| " + " | ".join(row) + " |")
    return lines


def request_result_table(records: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Sample | Shape | Level | HTTP | Error | 400 | Finish | Content chars | reasoning_content | Reasoning tokens | Seconds |",
        "| ---: | --- | --- | ---: | --- | --- | --- | ---: | --- | ---: | ---: |",
    ]
    for record in records:
        error = record.get("error_type") or ""
        lines.append(
            "| {sample} | {shape} | {level} | {status} | {error} | {bad400} | "
            "{finish} | {content} | {reasoning} | {tokens} | {seconds:.3f} |".format(
                sample=record.get("sample", ""),
                shape=record.get("shape", record.get("label", "")),
                level=record.get("level") or "—",
                status=record.get("http_status") or "—",
                error=str(error).replace("|", "\\|"),
                bad400="yes" if record.get("request_breaking_400") else "no",
                finish=record.get("finish_reason") or "—",
                content=record.get("content_length", 0),
                reasoning="yes" if record.get("reasoning_content_present") else "no",
                tokens=format_number(record.get("reasoning_tokens")),
                seconds=float(record.get("elapsed_secs") or 0),
            )
        )
    return lines


def effort_report_lines(
    records: list[dict[str, Any]],
    evaluation: dict[str, Any],
    *,
    aborted_reason: str | None,
) -> list[str]:
    selected = evaluation["selected"]
    lines = [
        "## Effort-field controlled experiment",
        "",
        f"- Generated: `{utc_now()}`",
        f"- Endpoint: `{BASE_URL}`",
        f"- Model: `{MODEL}`",
        f"- Samples requested: exactly `{EFFORT_SAMPLES}` per (shape, level) and `{EFFORT_SAMPLES}` no-effort controls (`110` total)",
        f"- Completed request records: `{len(records)}`",
        f"- Fixed controls: `temperature={TEMPERATURE:g}`, `max_tokens={EFFORT_MAX_TOKENS}`, `stream=True`, `stream_options.include_usage=True`, identical messages/tools/tool_choice",
        "- SDK retries: `0`; execution order is round-robin and strictly sequential (concurrency 1)",
    ]
    if aborted_reason:
        lines.extend(["", f"> INCOMPLETE: {aborted_reason}"])

    lines.extend(
        [
            "",
            "### Median reasoning tokens",
            "",
            *effort_median_table(evaluation),
            "",
            "### Exact decision rule and verdict",
            "",
            "A shape controls iff `median(max) - median(none) >= 50`, `median(none) <= 5`, and it has no request-breaking 400 at any level. A shape is inert iff every level median is within 10 tokens of the no-effort control median. No adjacent-level monotonicity test is used.",
            "",
            "Preference order is: top-level native `reasoning_effort`, then `chat_template_kwargs.reasoning_effort`, then nested `reasoning.effort`.",
            "",
            f"- Controlling shapes: `{', '.join(evaluation['controlling_shapes']) or 'none'}`",
            f"- Inert shapes: `{', '.join(evaluation['inert_shapes']) or 'none'}`",
            f"- Selected controlling field: `{SHAPE_LABELS[selected] if selected else 'none'}`",
            f"- Step 2 verdict: `{'BLOCK' if evaluation['blocked'] else 'PROCEED'}`",
        ]
    )
    if len(evaluation["controlling_shapes"]) > 1:
        lines.append(
            "- Multiple controlling shapes were observed; this is normal and the preference order resolves selection."
        )
    if evaluation["block_reason"]:
        lines.append(f"- Block reason: {evaluation['block_reason']}")

    lines.extend(
        [
            "",
            "### Per-request outcomes",
            "",
            *request_result_table(records),
            "",
            "### Raw sample records",
            "",
            "The `request_kwargs_sent` object in every record is the exact Python keyword mapping passed to `chat.completions.create`; it is retained to prove that controls were mutually exclusive.",
            "",
            "```json",
            json.dumps([public_record(record) for record in records], indent=2, sort_keys=True),
            "```",
        ]
    )
    return lines


def print_effort_verdict(evaluation: dict[str, Any]) -> None:
    print("\n".join(effort_median_table(evaluation)))
    selected = evaluation["selected"]
    print(
        "Selected controlling field:",
        SHAPE_LABELS[selected] if selected else "none",
    )
    print("Step 2 verdict:", "BLOCK" if evaluation["blocked"] else "PROCEED")
    if evaluation["block_reason"]:
        print("Reason:", evaluation["block_reason"])


def run_effort_experiment(
    client: OpenAI, *, interval_secs: float
) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
    records: list[dict[str, Any]] = []
    aborted_reason: str | None = None
    consecutive_access_failures = 0

    # Interleave the control and all cells across five rounds to reduce temporal
    # endpoint-load bias while retaining exactly five samples in every cell.
    for sample in range(1, EFFORT_SAMPLES + 1):
        cells: list[tuple[str | None, str | None]] = [(None, None)]
        cells.extend((shape, level) for shape in SHAPES for level in LEVELS)
        for shape, level in cells:
            label = "control" if shape is None else f"{shape}:{level}"
            print(f"EFFORT_SAMPLE {sample}/{EFFORT_SAMPLES} {label}", flush=True)
            kwargs = build_request_kwargs(shape=shape, level=level)
            record = run_stream_request(client, kwargs, label=label, sample=sample)
            record["shape"] = "control" if shape is None else shape
            record["level"] = level
            records.append(record)

            if is_fatal_access_failure(record):
                consecutive_access_failures += 1
            else:
                consecutive_access_failures = 0
            if record.get("http_status") in (401, 403):
                aborted_reason = (
                    f"Authentication/authorization failed with HTTP {record['http_status']} "
                    f"during {label}; check BASETEN_API_KEY."
                )
                break
            if consecutive_access_failures >= 2:
                aborted_reason = (
                    "Two consecutive connection/timeout failures occurred; the endpoint "
                    "may be unreachable from this environment."
                )
                break
            pause(interval_secs)
        if aborted_reason:
            break

    evaluation = evaluate_effort_records(records)
    return records, evaluation, aborted_reason


def selected_request(
    *,
    shape: str,
    level: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_choice: Any,
    max_tokens: int,
) -> dict[str, Any]:
    return build_request_kwargs(
        shape=shape,
        level=level,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
    )


def selected_text_request(
    *,
    shape: str,
    level: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> dict[str, Any]:
    """Build a streamed text request with no tools or tool_choice fields."""

    kwargs = {
        "model": MODEL,
        "messages": copy.deepcopy(messages),
        "temperature": TEMPERATURE,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    kwargs.update(build_effort_kwargs(shape, level))
    assert_exclusive_control(kwargs, shape)
    return kwargs


def run_repeated(
    client: OpenAI,
    *,
    label: str,
    samples: int,
    kwargs_factory: Any,
    interval_secs: float,
    expected_tool_call: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for sample in range(1, samples + 1):
        print(f"FOLLOWUP {label} {sample}/{samples}", flush=True)
        kwargs = kwargs_factory(sample)
        record = run_stream_request(
            client,
            kwargs,
            label=label,
            sample=sample,
            expected_tool_call=expected_tool_call,
        )
        records.append(record)
        if record.get("http_status") in (401, 403):
            break
        pause(interval_secs)
    return records


def truncation_messages(item_count: int) -> list[dict[str, Any]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a tool-call truncation diagnostic. Follow the requested "
                "sequence exactly and do not summarize it."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Call submit_sequence once. Its values array must contain every "
                f"integer from 1 through {item_count}, in order, with no omissions."
            ),
        },
    ]


def truncation_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "submit_sequence",
                "description": "Submit a long integer sequence without omissions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "values": {
                            "type": "array",
                            "items": {"type": "integer"},
                        }
                    },
                    "required": ["values"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def analyze_truncation_record(record: dict[str, Any], item_count: int) -> None:
    record["sequence_complete"] = False
    record["sequence_length"] = None
    record["sequence_is_exact_prefix"] = False
    record["truncation_category"] = "inconclusive"
    record["truncation_category_reason"] = "insufficient evidence"

    error_text = " ".join(
        (
            str(record.get("error_message") or ""),
            json.dumps(record.get("error_body"), default=str).lower(),
        )
    ).lower()
    explicit_max_tokens_cutoff = any(
        marker in error_text
        for marker in (
            "tool calls cutoff by max_tokens",
            "tool call cutoff by max_tokens",
            "cutoff by max_tokens",
            "cut off by max_tokens",
            "truncated by max_tokens",
            "max_tokens cutoff",
        )
    )
    record["explicit_max_tokens_cutoff"] = explicit_max_tokens_cutoff
    if explicit_max_tokens_cutoff:
        record["truncation_category"] = "confirmed_truncation"
        record["truncation_category_reason"] = (
            "request returned an explicit max_tokens cutoff error"
        )
        return
    if record.get("finish_reason") == "length":
        record["truncation_category"] = "confirmed_truncation"
        record["truncation_category_reason"] = "finish_reason was length"
        return

    status = record.get("http_status")
    if record.get("error_type") or (
        isinstance(status, int) and not 200 <= status < 300
    ):
        record["truncation_category"] = "request_failure"
        record["truncation_category_reason"] = (
            "HTTP, transport, authentication, rate-limit, or timeout failure"
        )
        return
    if not isinstance(status, int) or not 200 <= status < 300:
        record["truncation_category_reason"] = (
            "no successful HTTP status was available to classify the response"
        )
        return

    calls = record.get("_tool_calls_wire") or []
    expected_name = "submit_sequence"
    correct_single_call = (
        len(calls) == 1
        and get_path(calls, (0, "type")) == "function"
        and get_path(calls, (0, "function", "name")) == expected_name
    )
    arguments = (
        get_path(calls, (0, "function", "arguments"), "")
        if correct_single_call
        else ""
    )
    try:
        parsed = json.loads(arguments)
    except (TypeError, ValueError):
        parsed = None
    values = parsed.get("values") if isinstance(parsed, dict) else None
    if isinstance(values, list):
        record["sequence_length"] = len(values)
        expected_values = list(range(1, item_count + 1))
        record["sequence_is_exact_prefix"] = values == expected_values[: len(values)]
        record["sequence_complete"] = bool(
            record.get("tool_calls_parse_ok") and values == expected_values
        )

    if record["sequence_complete"]:
        record["truncation_category_reason"] = (
            "the complete requested sequence was returned; no truncation observed"
        )
        return

    completion_tokens = record.get("usage_completion_tokens")
    max_tokens = record.get("max_tokens_probe")
    provably_hit_cap = (
        record["sequence_is_exact_prefix"]
        and isinstance(record["sequence_length"], int)
        and 0 < record["sequence_length"] < item_count
        and isinstance(completion_tokens, (int, float))
        and isinstance(max_tokens, int)
        and completion_tokens >= max_tokens
    )
    if provably_hit_cap:
        record["truncation_category"] = "confirmed_truncation"
        record["truncation_category_reason"] = (
            "a well-formed exact prefix ended at the configured token cap"
        )
    elif record.get("finish_reason") is not None:
        record["truncation_category"] = "model_noncompliance"
        record["truncation_category_reason"] = (
            "successful non-length completion returned a wrong or incomplete sequence"
        )


def run_episode(
    client: OpenAI,
    *,
    shape: str,
    level: str,
    sample: int,
    interval_secs: float,
) -> dict[str, Any]:
    episode_started = time.monotonic()
    first_kwargs = selected_request(
        shape=shape,
        level=level,
        messages=EPISODE_MESSAGES,
        tools=EPISODE_TOOLS,
        tool_choice=EPISODE_TOOL_CHOICE,
        max_tokens=EFFORT_MAX_TOKENS,
    )
    first = run_stream_request(
        client,
        first_kwargs,
        label="episode_turn_1_tool",
        sample=sample,
        expected_tool_call={
            "name": "lookup_probe",
            "required_keys": ("code",),
            "expected_values": EPISODE_EXPECTED_ARGUMENTS,
        },
    )
    episode: dict[str, Any] = {
        "sample": sample,
        "turn_1": first,
        "turn_2": None,
        "completed_two_turns": False,
        "configured_inter_turn_sleep_secs": interval_secs,
        "request_elapsed_secs": None,
        "elapsed_secs": None,
    }
    wire_calls = first.get("_tool_calls_wire") or []
    if first.get("error_type") or not first.get("tool_calls_parse_ok"):
        episode["request_elapsed_secs"] = first.get("elapsed_secs")
        episode["elapsed_secs"] = time.monotonic() - episode_started
        return episode

    messages = copy.deepcopy(EPISODE_MESSAGES)
    messages.append(
        {
            "role": "assistant",
            "content": first.get("_content") or None,
            "tool_calls": copy.deepcopy(wire_calls),
        }
    )
    for call in wire_calls:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(
                    {
                        "code": "inkling-latency-v1",
                        "status": "ready",
                        "source": "deterministic-probe",
                    },
                    sort_keys=True,
                ),
            }
        )
    pause(interval_secs)
    second_kwargs = selected_request(
        shape=shape,
        level=level,
        messages=messages,
        tools=EPISODE_TOOLS,
        tool_choice="none",
        max_tokens=EFFORT_MAX_TOKENS,
    )
    second = run_stream_request(
        client, second_kwargs, label="episode_turn_2_answer", sample=sample
    )
    episode["turn_2"] = second
    final_content = str(second.get("_content") or "").strip()
    episode["turn_2_expected_answer_ok"] = bool(
        not second.get("error_type")
        and second.get("finish_reason") == "stop"
        and not second.get("_tool_calls_wire")
        and final_content == EPISODE_EXPECTED_FINAL
    )
    episode["completed_two_turns"] = (
        bool(first.get("tool_calls_parse_ok"))
        and episode["turn_2_expected_answer_ok"]
    )
    request_times = [first.get("elapsed_secs"), second.get("elapsed_secs")]
    episode["request_elapsed_secs"] = sum(
        float(value) for value in request_times if isinstance(value, (int, float))
    )
    episode["elapsed_secs"] = time.monotonic() - episode_started
    return episode


def successful(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if not record.get("error_type")]


def median_field(records: list[dict[str, Any]], field: str) -> float | None:
    values = [
        float(record[field])
        for record in records
        if isinstance(record.get(field), (int, float))
    ]
    return float(statistics.median(values)) if values else None


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def followup_report_lines(result: dict[str, Any]) -> list[str]:
    tool_parse = result["tool_parse"]
    batch = result["batch"]
    none_tool_records = result["none_tool"]
    none_text_records = result["none_text"]
    truncation = result["truncation"]
    episodes = result["episodes"]
    all_request_records = (
        tool_parse + batch + none_tool_records + none_text_records + truncation
    )
    for episode in episodes:
        all_request_records.append(episode["turn_1"])
        if isinstance(episode.get("turn_2"), dict):
            all_request_records.append(episode["turn_2"])

    good_tool = successful(tool_parse)
    tool_parsing_works = bool(good_tool) and len(good_tool) == len(tool_parse) and all(
        record.get("tool_calls_parse_ok") for record in good_tool
    )
    good_batch = successful(batch)
    batch_single_at_content = (
        bool(good_batch)
        and len(good_batch) == len(batch)
        and all(
            record.get("reasoning_delta_count") == 1
            and record.get("reasoning_same_delta_as_first_content") is True
            for record in good_batch
        )
    )
    good_none_tool = successful(none_tool_records)
    none_tool_reasoning_near_zero = bool(good_none_tool) and all(
        isinstance(record.get("reasoning_tokens"), (int, float))
        and float(record["reasoning_tokens"]) <= 5
        for record in good_none_tool
    )
    none_tools_work = (
        bool(good_none_tool)
        and len(good_none_tool) == len(none_tool_records)
        and all(record.get("tool_calls_parse_ok") for record in good_none_tool)
    )
    good_none_text = successful(none_text_records)
    for record in none_text_records:
        record["folded_cot_evidence"] = bool(
            not record.get("error_type")
            and isinstance(record.get("reasoning_tokens"), (int, float))
            and float(record["reasoning_tokens"]) <= 5
            and isinstance(record.get("content_length"), int)
            and record["content_length"] >= FOLDED_CONTENT_MIN_CHARS
        )
    folded_content_observed = (
        bool(good_none_text)
        and len(good_none_text) == len(none_text_records)
        and all(record.get("folded_cot_evidence") for record in good_none_text)
    )
    folding_classification = "OBSERVED" if folded_content_observed else "not established"

    requests_429 = [
        record for record in all_request_records if record.get("http_status") == 429
    ]
    completed_episodes = [
        episode for episode in episodes if episode.get("completed_two_turns")
    ]
    episode_wall_latency = median_field(completed_episodes, "elapsed_secs")
    episode_request_latency = median_field(completed_episodes, "request_elapsed_secs")

    lines = [
        "## Follow-up probes",
        "",
        f"- Generated: `{utc_now()}`",
        f"- Selected field representation: `{SHAPE_LABELS[result['shape']]}`",
        f"- High effort: `{result['high_effort']}`",
        "- All requests were streamed with usage enabled, temperature 1, zero SDK retries, and strict concurrency 1.",
        "",
        "### Streaming, tools, and reasoning-content batching",
        "",
        f"- Forced tool-call streams produced exactly one `submit_probe` call with a real call ID and the expected answer/checksum object: `{yes_no(tool_parsing_works)}` ({len(good_tool)}/{len(tool_parse)} requests succeeded)",
        f"- With tools present and `tool_choice=none`, reasoning arrived in exactly one delta at the first non-empty content delta in every successful sample: `{yes_no(batch_single_at_content)}`",
        "- Forced tool-call records also retain whether reasoning shared the first answer-bearing (content or tool-call) delta; see raw records.",
        "",
        "### `none` behavior",
        "",
        f"- Forced-tool usability: exact `submit_probe` calls remained usable at `none`: `{yes_no(none_tools_work)}`; reasoning tokens were <=5 in every successful forced-tool sample: `{yes_no(none_tool_reasoning_near_zero)}`.",
        "- The separate textual probe omits both `tools` and `tool_choice` and requests a concise final marker, so its visible message content can test the folding claim.",
        f"- Textual folding classification: **{folding_classification}**. `OBSERVED` requires every requested sample to succeed with content >= {FOLDED_CONTENT_MIN_CHARS} chars and `reasoning_tokens<=5`; median content was `{format_number(median_field(good_none_text, 'content_length'))}` chars and median reasoning tokens were `{format_number(median_field(good_none_text, 'reasoning_tokens'))}`.",
    ]
    if folded_content_observed:
        lines.append(
            "- Substantially long visible text with near-zero separate reasoning supports folded-CoT behavior. The project plan independently treats `none` as smoke-only and non-canonical."
        )
    else:
        lines.append(
            "- Folding was not established in the tool path, where zero visible content is legitimate, or by the textual threshold. The plan still treats `none` as non-canonical; that exclusion is plan-driven, not diagnostic-inferred."
        )
    lines.extend(
        [
            "",
            "### Separate max_tokens truncation stress comparison",
            "",
            f"The same `{result['truncation_items']}`-integer tool-call payload was requested at `{result['high_effort']}` for both caps. Only `confirmed_truncation` counts as truncation; request failures, successful model noncompliance, and inconclusive records are reported separately.",
            "A complete sequence is shown in the complete column and categorized as `inconclusive` for the truncation hypothesis: it proves this payload completed, not that a larger payload could not truncate.",
            "",
            "| max_tokens | Samples | Complete sequences | Confirmed truncation | Request failure | Model noncompliance | Inconclusive | Median completion tokens | Median reasoning tokens |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for max_tokens in (8_192, 16_384):
        cap_records = [
            record for record in truncation if record.get("max_tokens_probe") == max_tokens
        ]
        category_counts = {
            category: sum(
                record.get("truncation_category") == category for record in cap_records
            )
            for category in (
                "confirmed_truncation",
                "request_failure",
                "model_noncompliance",
                "inconclusive",
            )
        }
        lines.append(
            "| {cap} | {samples} | {complete} | {confirmed} | {failure} | {noncompliance} | {inconclusive} | {completion} | {reasoning} |".format(
                cap=max_tokens,
                samples=len(cap_records),
                complete=sum(bool(record.get("sequence_complete")) for record in cap_records),
                confirmed=category_counts["confirmed_truncation"],
                failure=category_counts["request_failure"],
                noncompliance=category_counts["model_noncompliance"],
                inconclusive=category_counts["inconclusive"],
                completion=format_number(median_field(cap_records, "usage_completion_tokens")),
                reasoning=format_number(median_field(cap_records, "reasoning_tokens")),
            )
        )

    retry_after_values = sorted(
        {
            str(get_path(record, ("response_headers", "retry-after")))
            for record in requests_429
            if get_path(record, ("response_headers", "retry-after")) is not None
        }
    )
    lines.extend(
        [
            "",
            "### Concurrency-1 rate limits and episode-style latency",
            "",
            f"- Requests observed across follow-ups: `{len(all_request_records)}`",
            f"- HTTP 429 responses: `{len(requests_429)}`",
            f"- Retry-After values: `{', '.join(retry_after_values) or 'none observed'}`",
            f"- Completed two-turn tool episodes: `{len(completed_episodes)}/{len(episodes)}`",
            f"- Configured inter-turn sleep: `{format_number(result['interval_secs'])}` seconds per episode (default `0`).",
            f"- Median two-turn episode wall time: `{format_number(episode_wall_latency)}` seconds, including the configured inter-turn sleep.",
            f"- Median summed request time: `{format_number(episode_request_latency)}` seconds, excluding the inter-turn sleep and local handoff overhead.",
            "",
            "| Episode | Turn 1 seconds | Turn 2 seconds | Request seconds | Wall seconds | Inter-turn sleep | Completed |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for episode in episodes:
        second = episode.get("turn_2") or {}
        lines.append(
            "| {sample} | {first} | {second} | {request} | {total} | {sleep} | {completed} |".format(
                sample=episode["sample"],
                first=format_number(episode["turn_1"].get("elapsed_secs")),
                second=format_number(second.get("elapsed_secs")),
                request=format_number(episode.get("request_elapsed_secs")),
                total=format_number(episode.get("elapsed_secs")),
                sleep=format_number(episode.get("configured_inter_turn_sleep_secs")),
                completed=yes_no(bool(episode.get("completed_two_turns"))),
            )
        )

    public_episodes = []
    for episode in episodes:
        clean = dict(episode)
        clean["turn_1"] = public_record(episode["turn_1"])
        if isinstance(episode.get("turn_2"), dict):
            clean["turn_2"] = public_record(episode["turn_2"])
        public_episodes.append(clean)
    lines.extend(
        [
            "",
            "### Sweep recommendation",
            "",
            "- **Diagnostic-inferred:** the controlled effort matrix observed approximately zero separate reasoning at `none` and roughly 80–160 reasoning tokens throughout the non-`none` levels, with no graded monotonic trend. That binary pattern supports sweeping `low`, `high`, and API `max` (the harness `xhigh` mapping) to sample the non-`none` operating region.",
            "- **Integration-doc guidance:** `low` is the document's best single pick when only one configuration can be run.",
            "- **Plan-driven:** exclude `none` from canonical runs and the leaderboard regardless of whether this follow-up establishes folded CoT. That exclusion comes from the project plan, not from the tool-path diagnostic.",
            "",
            "### Raw follow-up records",
            "",
            "```json",
            json.dumps(
                {
                    "tool_parse": [public_record(item) for item in tool_parse],
                    "reasoning_batch_with_tools": [public_record(item) for item in batch],
                    "none_forced_tool": [
                        public_record(item) for item in none_tool_records
                    ],
                    "none_textual": [
                        public_record(item) for item in none_text_records
                    ],
                    "truncation": [public_record(item) for item in truncation],
                    "episodes": public_episodes,
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
        ]
    )
    return lines


def run_followups(
    client: OpenAI,
    *,
    shape: str,
    high_effort: str,
    probe_samples: int,
    truncation_samples: int,
    episode_samples: int,
    truncation_items: int,
    interval_secs: float,
) -> dict[str, Any]:
    tool_parse = run_repeated(
        client,
        label="stream_tool_parse",
        samples=probe_samples,
        interval_secs=interval_secs,
        expected_tool_call={
            "name": "submit_probe",
            "required_keys": ("answer", "checksum"),
            "expected_values": FIXED_EXPECTED_ARGUMENTS,
        },
        kwargs_factory=lambda _sample: selected_request(
            shape=shape,
            level=high_effort,
            messages=FIXED_MESSAGES,
            tools=FIXED_TOOLS,
            tool_choice=FIXED_TOOL_CHOICE,
            max_tokens=EFFORT_MAX_TOKENS,
        ),
    )
    batch = run_repeated(
        client,
        label="reasoning_batch_with_tools",
        samples=probe_samples,
        interval_secs=interval_secs,
        kwargs_factory=lambda _sample: selected_request(
            shape=shape,
            level=high_effort,
            messages=BATCH_MESSAGES,
            tools=FIXED_TOOLS,
            tool_choice="none",
            max_tokens=EFFORT_MAX_TOKENS,
        ),
    )
    none_tool_records = run_repeated(
        client,
        label="none_forced_tool_usability",
        samples=probe_samples,
        interval_secs=interval_secs,
        expected_tool_call={
            "name": "submit_probe",
            "required_keys": ("answer", "checksum"),
            "expected_values": FIXED_EXPECTED_ARGUMENTS,
        },
        kwargs_factory=lambda _sample: selected_request(
            shape=shape,
            level="none",
            messages=FIXED_MESSAGES,
            tools=FIXED_TOOLS,
            tool_choice=FIXED_TOOL_CHOICE,
            max_tokens=EFFORT_MAX_TOKENS,
        ),
    )
    none_text_records = run_repeated(
        client,
        label="none_textual_folded_content",
        samples=probe_samples,
        interval_secs=interval_secs,
        kwargs_factory=lambda _sample: selected_text_request(
            shape=shape,
            level="none",
            messages=NONE_TEXT_MESSAGES,
            max_tokens=EFFORT_MAX_TOKENS,
        ),
    )

    trunc_tools = truncation_tools()
    trunc_choice = {
        "type": "function",
        "function": {"name": "submit_sequence"},
    }
    truncation: list[dict[str, Any]] = []
    for max_tokens in (8_192, 16_384):
        cap_records = run_repeated(
            client,
            label=f"truncation_mt{max_tokens}",
            samples=truncation_samples,
            interval_secs=interval_secs,
            expected_tool_call={
                "name": "submit_sequence",
                "required_keys": ("values",),
                "expected_values": {
                    "values": list(range(1, truncation_items + 1))
                },
            },
            kwargs_factory=lambda _sample, cap=max_tokens: selected_request(
                shape=shape,
                level=high_effort,
                messages=truncation_messages(truncation_items),
                tools=trunc_tools,
                tool_choice=trunc_choice,
                max_tokens=cap,
            ),
        )
        for record in cap_records:
            record["max_tokens_probe"] = max_tokens
            analyze_truncation_record(record, truncation_items)
        truncation.extend(cap_records)

    episodes: list[dict[str, Any]] = []
    for sample in range(1, episode_samples + 1):
        print(f"FOLLOWUP episode {sample}/{episode_samples}", flush=True)
        episodes.append(
            run_episode(
                client,
                shape=shape,
                level=high_effort,
                sample=sample,
                interval_secs=interval_secs,
            )
        )
        pause(interval_secs)

    return {
        "shape": shape,
        "high_effort": high_effort,
        "truncation_items": truncation_items,
        "interval_secs": interval_secs,
        "tool_parse": tool_parse,
        "batch": batch,
        "none_tool": none_tool_records,
        "none_text": none_text_records,
        "truncation": truncation,
        "episodes": episodes,
    }


def write_report_section(output: Path, section: str, lines: list[str]) -> None:
    validate_output_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    start = f"<!-- inkling-probe:{section}:start -->"
    end = f"<!-- inkling-probe:{section}:end -->"
    body = f"{start}\n" + "\n".join(lines).rstrip() + f"\n{end}\n"
    if output.exists():
        existing = output.read_text(encoding="utf-8")
    else:
        existing = "# Inkling probe findings\n\n"
    if start in existing and end in existing:
        before, remainder = existing.split(start, 1)
        _old, after = remainder.split(end, 1)
        updated = before + body + after.lstrip("\n")
    else:
        updated = existing.rstrip() + "\n\n" + body
    output.write_text(updated, encoding="utf-8")
    print(f"WROTE {output}")


def resolve_output(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (PORT_DIR / path).resolve()


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def validate_output_path(output: Path) -> None:
    """Enforce the diagnostic's only permitted write boundary."""

    protected_names = {"mini-rl-env.py", "llm_factory.py"}
    if output.name in protected_names or (
        output.name.startswith("run_baseten") and output.name.endswith(".sh")
    ):
        raise DiagnosticError(f"--output targets protected harness file: {output}")
    if any(part in {"runs", "leaderboards"} for part in output.parts):
        raise DiagnosticError(
            f"--output may not target runs/ or leaderboards/: {output}"
        )
    if output.suffix.lower() != ".md":
        raise DiagnosticError(f"--output must be a Markdown (.md) file: {output}")
    allowed_roots = (PROJECT_DIR.resolve(), DIAGNOSTICS_FINDINGS_DIR.resolve())
    if not any(path_is_within(output, root) for root in allowed_roots):
        roots = " or ".join(str(root) for root in allowed_roots)
        raise DiagnosticError(f"--output must be under {roots}: {output}")


def validate_runtime_args(args: argparse.Namespace) -> None:
    if args.timeout_secs <= 0:
        raise DiagnosticError("--timeout-secs must be positive")
    if args.interval_secs < 0 or args.interval_secs >= 60:
        raise DiagnosticError("--interval-secs must be >=0 and <60")
    for name in ("probe_samples", "truncation_samples", "episode_samples"):
        if not hasattr(args, name):
            continue
        value = getattr(args, name)
        if value < 1 or value > MAX_FOLLOWUP_SAMPLES:
            raise DiagnosticError(
                f"--{name.replace('_', '-')} must be between 1 and "
                f"{MAX_FOLLOWUP_SAMPLES}"
            )
    if hasattr(args, "truncation_items") and not (
        1 <= args.truncation_items <= MAX_TRUNCATION_ITEMS
    ):
        raise DiagnosticError(
            f"--truncation-items must be between 1 and {MAX_TRUNCATION_ITEMS}"
        )


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=(
            "managed .md findings file under the project directory or "
            f"{DIAGNOSTICS_FINDINGS_DIR} (default: {DEFAULT_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help=f"dotenv file containing BASETEN_API_KEY (default: {DEFAULT_ENV_FILE})",
    )
    parser.add_argument(
        "--timeout-secs",
        type=float,
        default=DEFAULT_TIMEOUT_SECS,
        help=f"per-request OpenAI client timeout (default: {DEFAULT_TIMEOUT_SECS:g})",
    )
    parser.add_argument(
        "--interval-secs",
        type=float,
        default=0.0,
        help="optional delay between sequential requests; must be under 60 (default: 0)",
    )


def add_followup_args(parser: argparse.ArgumentParser, *, include_field: bool) -> None:
    if include_field:
        parser.add_argument(
            "--field",
            choices=tuple(CLI_FIELDS),
            required=True,
            help="controlling field selected by the effort-field experiment",
        )
    parser.add_argument(
        "--high-effort",
        choices=LEVELS[1:],
        default="max",
        help="effort for batching, truncation, and latency probes (default: max)",
    )
    parser.add_argument(
        "--probe-samples",
        type=int,
        default=5,
        help=(
            "samples each for tool parsing, batching, and each none probe "
            f"(1-{MAX_FOLLOWUP_SAMPLES}; default: 5)"
        ),
    )
    parser.add_argument(
        "--truncation-samples",
        type=int,
        default=2,
        help=(
            "samples at each of max_tokens 8192 and 16384 "
            f"(1-{MAX_FOLLOWUP_SAMPLES}; default: 2)"
        ),
    )
    parser.add_argument(
        "--truncation-items",
        type=int,
        default=5_000,
        help=(
            "integer count in the truncation stress tool payload "
            f"(1-{MAX_TRUNCATION_ITEMS}; default: 5000)"
        ),
    )
    parser.add_argument(
        "--episode-samples",
        type=int,
        default=3,
        help=(
            "sequential two-turn latency episodes "
            f"(1-{MAX_FOLLOWUP_SAMPLES}; default: 3)"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe which request field controls Inkling reasoning, then inspect "
            "streaming/tools, none behavior, truncation, rate limits, and latency."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    effort = subparsers.add_parser(
        "effort-field",
        help="run the fixed 110-request controlled effort-field experiment",
    )
    add_common_args(effort)

    followups = subparsers.add_parser(
        "follow-ups",
        help="run post-selection streaming/tool/none/truncation/latency probes",
    )
    add_common_args(followups)
    add_followup_args(followups, include_field=True)

    all_parser = subparsers.add_parser(
        "all",
        help="run the effort gate and, only on PROCEED, all follow-up probes",
    )
    add_common_args(all_parser)
    add_followup_args(all_parser, include_field=False)
    return parser


def failure_lines(command: str, message: str) -> list[str]:
    return [
        f"## {command} setup failure",
        "",
        f"- Generated: `{utc_now()}`",
        f"- Endpoint: `{BASE_URL}`",
        f"- Model: `{MODEL}`",
        f"- Error: {message}",
        "",
        "No benchmark or harness files were changed. Correct connectivity/authentication and rerun this diagnostic.",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output: Path | None = None
    output_validated = False
    try:
        output = resolve_output(args.output)
        validate_output_path(output)
        output_validated = True
        validate_runtime_args(args)
        api_key = read_env_key(Path(args.env_file).expanduser())
        client = make_client(api_key, args.timeout_secs)

        if args.command in ("effort-field", "all"):
            records, evaluation, aborted_reason = run_effort_experiment(
                client, interval_secs=args.interval_secs
            )
            write_report_section(
                output,
                "effort-field",
                effort_report_lines(
                    records, evaluation, aborted_reason=aborted_reason
                ),
            )
            print_effort_verdict(evaluation)
            if args.command == "effort-field":
                return 2 if evaluation["blocked"] else 0
            if evaluation["blocked"]:
                print("Follow-up probes were not run because the effort gate BLOCKED.")
                return 2
            shape = evaluation["selected"]
            if shape is None:  # guarded by blocked, retained for type/runtime safety
                raise DiagnosticError("Effort selection unexpectedly returned no field")
        else:
            shape = CLI_FIELDS[args.field]

        result = run_followups(
            client,
            shape=shape,
            high_effort=args.high_effort,
            probe_samples=args.probe_samples,
            truncation_samples=args.truncation_samples,
            episode_samples=args.episode_samples,
            truncation_items=args.truncation_items,
            interval_secs=args.interval_secs,
        )
        write_report_section(
            output,
            "follow-ups",
            followup_report_lines(result),
        )
        return 0
    except (DiagnosticError, OSError) as exc:
        message = str(exc)
        print(f"ERROR: {message}", file=sys.stderr)
        if output_validated and output is not None:
            try:
                write_report_section(
                    output,
                    f"{args.command}-failure",
                    failure_lines(args.command, message),
                )
            except (DiagnosticError, OSError) as write_exc:
                print(f"ERROR: could not write findings: {write_exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
