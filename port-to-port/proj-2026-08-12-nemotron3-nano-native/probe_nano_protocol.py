#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from openai import OpenAI


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_port",
            "description": "Look up a port by sector.",
            "parameters": {
                "type": "object",
                "properties": {"sector": {"type": "integer"}},
                "required": ["sector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote_trade",
            "description": "Quote a commodity sale at a port.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "integer"},
                    "commodity": {"type": "string"},
                    "quantity": {"type": "integer"},
                },
                "required": ["sector", "commodity", "quantity"],
            },
        },
    },
]


def _delta_reasoning(delta: Any) -> str:
    value = getattr(delta, "reasoning_content", None)
    if isinstance(value, str):
        return value
    extra = getattr(delta, "model_extra", None) or {}
    for key in ("reasoning_content", "reasoning"):
        value = extra.get(key)
        if isinstance(value, str):
            return value
    return ""


def stream_turn(
    client: OpenAI,
    *,
    model: str,
    messages: list[dict[str, Any]],
    mode: str,
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    sampling: dict[str, Any]
    if mode == "none":
        sampling = {"temperature": 0}
    else:
        sampling = {"temperature": 0.6, "top_p": 0.95}
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        stream=True,
        stream_options={"include_usage": True},
        max_tokens=10000,
        extra_body={
            **sampling,
            "chat_template_kwargs": {
                "enable_thinking": mode == "high",
                "force_nonempty_content": True,
            },
        },
    )
    raw_chunks: list[dict[str, Any]] = []
    content: list[str] = []
    reasoning: list[str] = []
    finish_reasons: list[str] = []
    tool_parts: dict[int, dict[str, str]] = {}
    usage: dict[str, Any] | None = None

    for chunk in stream:
        raw_chunks.append(chunk.model_dump(mode="json", exclude_none=False))
        if chunk.usage is not None:
            usage = chunk.usage.model_dump(mode="json", exclude_none=False)
        for choice in chunk.choices:
            if choice.finish_reason:
                finish_reasons.append(choice.finish_reason)
            delta = choice.delta
            if delta.content:
                content.append(delta.content)
            reasoning_text = _delta_reasoning(delta)
            if reasoning_text:
                reasoning.append(reasoning_text)
            for call in delta.tool_calls or []:
                part = tool_parts.setdefault(
                    call.index,
                    {"id": "", "name": "", "arguments": ""},
                )
                if call.id:
                    part["id"] += call.id
                if call.function and call.function.name:
                    part["name"] += call.function.name
                if call.function and call.function.arguments:
                    part["arguments"] += call.function.arguments

    tool_calls = [
        {
            "id": value["id"],
            "type": "function",
            "function": {
                "name": value["name"],
                "arguments": value["arguments"],
            },
        }
        for _, value in sorted(tool_parts.items())
    ]
    return {
        "content": "".join(content),
        "reasoning_content": "".join(reasoning),
        "tool_calls": tool_calls,
        "finish_reasons": finish_reasons,
        "usage": usage,
        "raw_chunks": raw_chunks,
    }


def assistant_message(turn: dict[str, Any]) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": turn["content"] or None}
    if turn["reasoning_content"]:
        message["reasoning_content"] = turn["reasoning_content"]
    if turn["tool_calls"]:
        message["tool_calls"] = turn["tool_calls"]
    return message


def run_mode(client: OpenAI, *, model: str, mode: str) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "Use tools exactly as requested."},
        {
            "role": "user",
            "content": "Think briefly, then call lookup_port exactly once for sector 1611.",
        },
    ]
    first = stream_turn(client, model=model, messages=messages, mode=mode, tools=TOOLS)
    messages.append(assistant_message(first))
    first_call = first["tool_calls"][0] if first["tool_calls"] else None
    if first_call:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": first_call["id"],
                "content": json.dumps({"sector": 1611, "code": "SSS", "mega": True}),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": "Now call quote_trade exactly once for 20 neuro_symbolics at sector 1611.",
        }
    )
    second = stream_turn(client, model=model, messages=messages, mode=mode, tools=TOOLS)
    messages.append(assistant_message(second))
    second_call = second["tool_calls"][0] if second["tool_calls"] else None
    if second_call:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": second_call["id"],
                "content": json.dumps({"unit_price": 52, "quantity": 20, "total": 1040}),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": "Summarize the two tool results in one sentence. Do not call another tool.",
        }
    )
    third = stream_turn(client, model=model, messages=messages, mode=mode, tools=TOOLS)

    errors: list[str] = []
    if not first["tool_calls"] or first["tool_calls"][0]["function"]["name"] != "lookup_port":
        errors.append("first turn did not parse lookup_port")
    if not second["tool_calls"] or second["tool_calls"][0]["function"]["name"] != "quote_trade":
        errors.append("second turn did not parse quote_trade")
    if not third["content"].strip():
        errors.append("third turn had empty final content")
    if third["tool_calls"]:
        errors.append("third turn unexpectedly called a tool")
    if any("length" in turn["finish_reasons"] for turn in (first, second, third)):
        errors.append("a turn stopped at the output ceiling")
    reasoning_chars = sum(len(turn["reasoning_content"]) for turn in (first, second, third))
    if mode == "none" and reasoning_chars:
        errors.append("thinking-off emitted reasoning_content")
    if mode == "high" and not reasoning_chars:
        errors.append("thinking-on emitted no reasoning_content")
    return {
        "mode": mode,
        "turns": [first, second, third],
        "reasoning_chars": reasoning_chars,
        "errors": errors,
        "ok": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="nemotron-3-nano-30b-nvfp4")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    client = OpenAI(base_url=args.base_url, api_key="dummy", timeout=900.0)
    result = {
        "base_url": args.base_url,
        "model": args.model,
        "modes": [
            run_mode(client, model=args.model, mode="none"),
            run_mode(client, model=args.model, mode="high"),
        ],
    }
    result["ok"] = all(mode["ok"] for mode in result["modes"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": result["ok"],
        "modes": [
            {
                "mode": mode["mode"],
                "ok": mode["ok"],
                "reasoning_chars": mode["reasoning_chars"],
                "errors": mode["errors"],
            }
            for mode in result["modes"]
        ],
        "out": str(args.out),
    }, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
