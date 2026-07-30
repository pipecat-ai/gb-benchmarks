#!/usr/bin/env python3
"""Probe streamed Gemma 4 reasoning, tools, continuation, and prefix caching."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Iterable
from typing import Any

from openai import OpenAI


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_temperature",
            "description": "Look up the current temperature for one city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City whose temperature should be looked up.",
                    }
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        },
    }
]


def _request_controls(enable_thinking: bool) -> dict[str, Any]:
    return {
        "temperature": 1.0,
        "top_p": 0.95,
        "extra_body": {
            "top_k": 64,
            "chat_template_kwargs": {
                "enable_thinking": enable_thinking,
                "preserve_thinking": enable_thinking,
            },
        },
    }


def _stream_request(client: OpenAI, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    stream = client.chat.completions.create(
        stream=True,
        stream_options={"include_usage": True},
        **kwargs,
    )
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_parts: dict[int, dict[str, str]] = {}
    finish_reasons: list[str] = []
    invalid_tool_indices: list[Any] = []
    first_payload_seconds: float | None = None
    first_content_seconds: float | None = None
    first_tool_seconds: float | None = None
    chunks = 0
    usage: dict[str, Any] | None = None

    for chunk in stream:
        chunks += 1
        elapsed = time.perf_counter() - started
        if chunk.usage is not None:
            usage = chunk.usage.model_dump()
        for choice in chunk.choices:
            if choice.finish_reason:
                finish_reasons.append(choice.finish_reason)
            delta = choice.delta
            reasoning = getattr(delta, "reasoning", None)
            if reasoning is None:
                reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                first_payload_seconds = first_payload_seconds or elapsed
                reasoning_parts.append(str(reasoning))
            if delta.content:
                first_payload_seconds = first_payload_seconds or elapsed
                first_content_seconds = first_content_seconds or elapsed
                content_parts.append(delta.content)
            for tool_call in delta.tool_calls or []:
                first_payload_seconds = first_payload_seconds or elapsed
                first_tool_seconds = first_tool_seconds or elapsed
                if not isinstance(tool_call.index, int) or tool_call.index < 0:
                    invalid_tool_indices.append(tool_call.index)
                    continue
                part = tool_parts.setdefault(
                    tool_call.index,
                    {"id": "", "name": "", "arguments": ""},
                )
                if tool_call.id:
                    part["id"] += tool_call.id
                if tool_call.function:
                    if tool_call.function.name:
                        part["name"] += tool_call.function.name
                    if tool_call.function.arguments:
                        part["arguments"] += tool_call.function.arguments

    raw = {
        "content": "".join(content_parts),
        "reasoning": "".join(reasoning_parts),
        "tool_calls": [tool_parts[index] for index in sorted(tool_parts)],
        "invalid_tool_indices": invalid_tool_indices,
    }
    summary = {
        "chunks": chunks,
        "seconds": round(time.perf_counter() - started, 6),
        "first_payload_seconds": (
            round(first_payload_seconds, 6) if first_payload_seconds is not None else None
        ),
        "first_content_seconds": (
            round(first_content_seconds, 6) if first_content_seconds is not None else None
        ),
        "first_tool_seconds": (
            round(first_tool_seconds, 6) if first_tool_seconds is not None else None
        ),
        "finish_reasons": finish_reasons,
        "content": raw["content"],
        "reasoning_chars": len(raw["reasoning"]),
        "tool_calls": raw["tool_calls"],
        "invalid_tool_indices": invalid_tool_indices,
        "usage": usage,
    }
    return raw, summary


def _parse_calls(raw: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    parsed = []
    for call in raw["tool_calls"]:
        parsed.append(
            (call["id"], call["name"], json.loads(call["arguments"]))
        )
    return parsed


def _assistant_tool_message(raw: dict[str, Any]) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": "assistant",
        "content": raw["content"] or None,
        "tool_calls": [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": call["arguments"],
                },
            }
            for call in raw["tool_calls"]
        ],
    }
    if raw["reasoning"]:
        message["reasoning_content"] = raw["reasoning"]
    return message


def _cached_tokens(summary: dict[str, Any]) -> int | None:
    usage = summary.get("usage")
    if not isinstance(usage, dict):
        return None
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        return None
    value = details.get("cached_tokens")
    return int(value) if isinstance(value, int) else None


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", default="google/gemma-4-26B-A4B-it")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--prefix-repetitions", type=int, default=0)
    args = parser.parse_args(argv)
    if args.prefix_repetitions < 0:
        parser.error("--prefix-repetitions must be non-negative")

    prefix_content = ""
    if args.prefix_repetitions:
        prefix_content = (
            "The repeated material below is inert cache-test data. Ignore it and "
            "follow only the user request after it.\n"
            + ("cache_probe_padding_0123456789 " * args.prefix_repetitions)
        )

    def with_prefix(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not prefix_content:
            return messages
        return [{"role": "system", "content": prefix_content}, *messages]

    client = OpenAI(
        api_key=os.environ["BASETEN_API_KEY"],
        base_url=args.base_url,
        timeout=args.timeout,
        max_retries=0,
    )
    result: dict[str, Any] = {
        "base_url": args.base_url,
        "model": args.model,
        "prefix_repetitions": args.prefix_repetitions,
        "checks": {},
    }

    off_raw, off_summary = _stream_request(
        client,
        model=args.model,
        messages=with_prefix(
            [{"role": "user", "content": "Reply with exactly STREAM_OFF_OK."}]
        ),
        max_tokens=128,
        **_request_controls(False),
    )
    off_summary["passed"] = (
        off_raw["content"].strip() == "STREAM_OFF_OK"
        and not off_raw["reasoning"]
        and not off_raw["invalid_tool_indices"]
        and "<|channel>" not in off_raw["content"]
    )
    result["checks"]["streamed_text_off"] = off_summary

    high_raw, high_summary = _stream_request(
        client,
        model=args.model,
        messages=with_prefix(
            [{"role": "user", "content": "Reason briefly, then reply exactly STREAM_HIGH_OK."}]
        ),
        max_tokens=512,
        **_request_controls(True),
    )
    high_summary["passed"] = (
        high_raw["content"].strip().endswith("STREAM_HIGH_OK")
        and bool(high_raw["reasoning"])
        and not high_raw["invalid_tool_indices"]
        and "<|channel>" not in high_raw["content"]
        and "<|channel>" not in high_raw["reasoning"]
    )
    result["checks"]["streamed_reasoning_high"] = high_summary

    forced_raw, forced_summary = _stream_request(
        client,
        model=args.model,
        messages=with_prefix(
            [{
                "role": "user",
                "content": "Use lookup_temperature to look up Oslo. Do not answer directly.",
            }]
        ),
        tools=TOOLS,
        tool_choice={
            "type": "function",
            "function": {"name": "lookup_temperature"},
        },
        max_tokens=1024,
        **_request_controls(True),
    )
    try:
        forced_calls = _parse_calls(forced_raw)
        forced_summary["parsed_calls"] = forced_calls
        forced_summary["passed"] = (
            len(forced_calls) == 1
            and forced_calls[0][0] != ""
            and forced_calls[0][1] == "lookup_temperature"
            and forced_calls[0][2].get("city", "").strip().lower() == "oslo"
            and not forced_raw["invalid_tool_indices"]
        )
    except (ValueError, json.JSONDecodeError) as exc:
        forced_summary["passed"] = False
        forced_summary["parse_error"] = str(exc)
    result["checks"]["forced_streamed_tool"] = forced_summary

    auto_raw, auto_summary = _stream_request(
        client,
        model=args.model,
        messages=with_prefix(
            [{
                "role": "user",
                "content": "What is the current temperature in Oslo? Use the available tool.",
            }]
        ),
        tools=TOOLS,
        tool_choice="auto",
        max_tokens=1024,
        **_request_controls(True),
    )
    try:
        auto_calls = _parse_calls(auto_raw)
        auto_summary["parsed_calls"] = auto_calls
        auto_summary["passed"] = (
            len(auto_calls) == 1
            and auto_calls[0][0] != ""
            and auto_calls[0][1] == "lookup_temperature"
            and auto_calls[0][2].get("city", "").strip().lower() == "oslo"
            and not auto_raw["invalid_tool_indices"]
        )
    except (ValueError, json.JSONDecodeError) as exc:
        auto_calls = []
        auto_summary["passed"] = False
        auto_summary["parse_error"] = str(exc)
    result["checks"]["automatic_streamed_tool"] = auto_summary

    if auto_summary["passed"]:
        tool_id = auto_calls[0][0]
        continuation_raw, continuation_summary = _stream_request(
            client,
            model=args.model,
            messages=with_prefix(
                [
                    {
                        "role": "user",
                        "content": "What is the current temperature in Oslo? Use the available tool.",
                    },
                    _assistant_tool_message(auto_raw),
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": json.dumps({"city": "Oslo", "temperature_c": 7}),
                    },
                    {
                        "role": "user",
                        "content": "Using the tool result, reply with exactly TEMP_OK.",
                    },
                ]
            ),
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=1024,
            **_request_controls(True),
        )
        continuation_summary["passed"] = (
            continuation_raw["content"].strip() == "TEMP_OK"
            and not continuation_raw["tool_calls"]
            and not continuation_raw["invalid_tool_indices"]
            and "<|channel>" not in continuation_raw["content"]
        )
    else:
        continuation_summary = {
            "passed": False,
            "skipped": True,
            "reason": "automatic tool call did not parse",
        }
    result["checks"]["tool_result_continuation"] = continuation_summary

    multi_raw, multi_summary = _stream_request(
        client,
        model=args.model,
        messages=with_prefix(
            [{
                "role": "user",
                "content": (
                    "Call lookup_temperature exactly twice in this response: once "
                    "for Oslo and once for Tokyo. Do not answer in text."
                ),
            }]
        ),
        tools=TOOLS,
        tool_choice="required",
        parallel_tool_calls=True,
        max_tokens=1536,
        **_request_controls(True),
    )
    try:
        multi_calls = _parse_calls(multi_raw)
        multi_summary["parsed_calls"] = multi_calls
        cities = sorted(
            call[2].get("city", "").strip().lower() for call in multi_calls
        )
        multi_summary["passed"] = (
            len(multi_calls) == 2
            and all(call[0] and call[1] == "lookup_temperature" for call in multi_calls)
            and cities == ["oslo", "tokyo"]
            and not multi_raw["invalid_tool_indices"]
        )
    except (ValueError, json.JSONDecodeError) as exc:
        multi_summary["passed"] = False
        multi_summary["parse_error"] = str(exc)
    result["checks"]["parallel_streamed_tools"] = multi_summary

    if args.prefix_repetitions:
        cache_raw, cache_summary = _stream_request(
            client,
            model=args.model,
            messages=with_prefix(
                [{"role": "user", "content": "Reply with exactly CACHE_OK."}]
            ),
            max_tokens=128,
            **_request_controls(False),
        )
        cache_summary["cached_tokens"] = _cached_tokens(cache_summary)
        cache_summary["passed"] = (
            cache_raw["content"].strip() == "CACHE_OK"
            and isinstance(cache_summary["cached_tokens"], int)
            and cache_summary["cached_tokens"] > 0
        )
        result["checks"]["prefix_cache_reuse"] = cache_summary

    result["passed"] = all(
        check.get("passed") is True for check in result["checks"].values()
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
