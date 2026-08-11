#!/usr/bin/env python3
"""Probe streamed Qwen3.6 text, tool calls, and tool-result continuation."""

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
            "description": "Look up the current temperature for a city.",
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
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning is None:
                reasoning = getattr(delta, "reasoning", None)
            if reasoning:
                if first_payload_seconds is None:
                    first_payload_seconds = elapsed
                reasoning_parts.append(str(reasoning))
            if delta.content:
                if first_payload_seconds is None:
                    first_payload_seconds = elapsed
                if first_content_seconds is None:
                    first_content_seconds = elapsed
                content_parts.append(delta.content)
            for tool_call in delta.tool_calls or []:
                if first_payload_seconds is None:
                    first_payload_seconds = elapsed
                if first_tool_seconds is None:
                    first_tool_seconds = elapsed
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
        "reasoning_content": "".join(reasoning_parts),
        "tool_calls": [tool_parts[index] for index in sorted(tool_parts)],
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
        "reasoning_chars": len(raw["reasoning_content"]),
        "tool_calls": raw["tool_calls"],
        "usage": usage,
    }
    return raw, summary


def _parse_first_tool(raw: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    calls = raw["tool_calls"]
    if len(calls) != 1:
        raise ValueError(f"expected exactly one tool call, got {len(calls)}")
    call = calls[0]
    return call["id"], call["name"], json.loads(call["arguments"])


def _assistant_tool_message(raw: dict[str, Any]) -> dict[str, Any]:
    calls = raw["tool_calls"]
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
            for call in calls
        ],
    }
    if raw["reasoning_content"]:
        message["reasoning_content"] = raw["reasoning_content"]
    return message


def _thinking_kwargs() -> dict[str, Any]:
    return {
        "temperature": 1.0,
        "top_p": 0.95,
        "presence_penalty": 0.0,
        "extra_body": {
            "top_k": 20,
            "chat_template_kwargs": {
                "enable_thinking": True,
                "preserve_thinking": True,
            },
        },
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", default="Qwen/Qwen3.6-27B")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--prefix-repetitions",
        type=int,
        default=0,
        help=(
            "Prepend a shared synthetic system prefix to every request. "
            "Use a value such as 2048 to exercise hybrid prefix-cache hits."
        ),
    )
    args = parser.parse_args(argv)
    if args.prefix_repetitions < 0:
        parser.error("--prefix-repetitions must be non-negative")

    prefix_content = ""
    if args.prefix_repetitions:
        prefix_content = (
            "The repeated padding below is inert benchmark data. Ignore it and "
            "follow the user request after it.\n"
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

    text_raw, text_summary = _stream_request(
        client,
        model=args.model,
        messages=with_prefix([
            {
                "role": "user",
                "content": "Reply with exactly STREAM_OK and nothing else.",
            }
        ]),
        max_tokens=32,
        temperature=0.0,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    text_summary["passed"] = text_raw["content"].strip() == "STREAM_OK"
    result["checks"]["streamed_text"] = text_summary

    forced_raw, forced_summary = _stream_request(
        client,
        model=args.model,
        messages=with_prefix([
            {
                "role": "user",
                "content": "Use lookup_temperature to look up Oslo. Do not answer directly.",
            }
        ]),
        tools=TOOLS,
        tool_choice={
            "type": "function",
            "function": {"name": "lookup_temperature"},
        },
        max_tokens=1024,
        **_thinking_kwargs(),
    )
    try:
        _, forced_name, forced_arguments = _parse_first_tool(forced_raw)
        forced_summary["parsed_arguments"] = forced_arguments
        forced_summary["passed"] = (
            forced_name == "lookup_temperature"
            and forced_arguments.get("city", "").strip().lower() == "oslo"
        )
    except (ValueError, json.JSONDecodeError) as exc:
        forced_summary["passed"] = False
        forced_summary["parse_error"] = str(exc)
    result["checks"]["forced_streamed_tool"] = forced_summary

    auto_raw, auto_summary = _stream_request(
        client,
        model=args.model,
        messages=with_prefix([
            {
                "role": "user",
                "content": "What is the current temperature in Oslo? Use the available tool.",
            }
        ]),
        tools=TOOLS,
        tool_choice="auto",
        max_tokens=1024,
        **_thinking_kwargs(),
    )
    try:
        auto_id, auto_name, auto_arguments = _parse_first_tool(auto_raw)
        auto_summary["parsed_arguments"] = auto_arguments
        auto_summary["passed"] = (
            bool(auto_id)
            and auto_name == "lookup_temperature"
            and auto_arguments.get("city", "").strip().lower() == "oslo"
        )
    except (ValueError, json.JSONDecodeError) as exc:
        auto_id = ""
        auto_summary["passed"] = False
        auto_summary["parse_error"] = str(exc)
    result["checks"]["automatic_streamed_tool"] = auto_summary

    if auto_summary["passed"]:
        continuation_messages = with_prefix([
            {
                "role": "user",
                "content": "What is the current temperature in Oslo? Use the available tool.",
            },
            _assistant_tool_message(auto_raw),
            {
                "role": "tool",
                "tool_call_id": auto_id,
                "content": json.dumps({"city": "Oslo", "temperature_c": 7}),
            },
            {
                "role": "user",
                "content": "Using the tool result, reply with exactly TEMP_OK.",
            },
        ])
        continuation_raw, continuation_summary = _stream_request(
            client,
            model=args.model,
            messages=continuation_messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=1024,
            **_thinking_kwargs(),
        )
        continuation_summary["passed"] = (
            continuation_raw["content"].strip() == "TEMP_OK"
            and not continuation_raw["tool_calls"]
        )
    else:
        continuation_summary = {
            "passed": False,
            "skipped": True,
            "reason": "automatic tool call did not parse",
        }
    result["checks"]["tool_result_continuation"] = continuation_summary

    result["passed"] = all(
        check.get("passed") is True for check in result["checks"].values()
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
