#!/usr/bin/env python3
"""Run a single Google SDK inference call from a reconstructed messages file.

This is intended for sanity-checking one specific turn context (for example,
a premature `finished` call) and quickly testing small system-instruction edits.
"""

from __future__ import annotations

import argparse
import ast
import base64
import json
import os
import runpy
import sys
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from pipecat.processors.aggregators.llm_context import LLMContext, LLMSpecificMessage

DEFAULT_MESSAGES_VAR = "FINAL_INFERENCE_INPUT_MESSAGES"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_data(path: Path) -> Any:
    if path.suffix.lower() == ".py":
        return runpy.run_path(str(path))
    return json.loads(_read_text(path))


def _resolve_dotted_path(obj: Any, dotted_path: str) -> Any:
    current = obj
    for token in dotted_path.split("."):
        key = token.strip()
        if not key:
            raise ValueError(f"Invalid dotted path segment in {dotted_path!r}")
        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"Path {dotted_path!r} not found")
        current = current[key]
    return current


def _decode_json_compatible(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_json_compatible(item) for item in value]

    if isinstance(value, dict):
        marker = value.get("_type")
        if marker == "bytes_b64" and isinstance(value.get("data"), str):
            try:
                return base64.b64decode(value["data"])
            except Exception:  # noqa: BLE001
                return value
        return {str(key): _decode_json_compatible(item) for key, item in value.items()}

    if isinstance(value, str) and (value.startswith("b'") or value.startswith('b"')):
        # Backward compatibility for older captures where bytes were serialized with repr().
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, bytes):
                return parsed
        except Exception:  # noqa: BLE001
            pass
        return value

    return value


def _decode_llm_specific_message(item: dict[str, Any]) -> LLMSpecificMessage | None:
    marker = str(item.get("_type") or "").strip().lower()
    if marker == "llm_specific":
        llm = str(item.get("llm") or "").strip()
        if llm:
            return LLMSpecificMessage(llm=llm, message=_decode_json_compatible(item.get("message")))
    if "role" in item:
        return None
    llm = item.get("llm")
    if isinstance(llm, str) and llm.strip() and "message" in item:
        return LLMSpecificMessage(
            llm=llm.strip(),
            message=_decode_json_compatible(item.get("message")),
        )
    return None


def _load_messages(path: Path, var_name: str) -> list[Any]:
    payload = _load_data(path)
    if isinstance(payload, dict) and var_name in payload:
        messages = payload[var_name]
    elif isinstance(payload, dict) and "messages" in payload:
        messages = payload["messages"]
    else:
        messages = payload

    if not isinstance(messages, list):
        raise ValueError(f"Expected list of messages, got {type(messages).__name__}")

    normalized: list[Any] = []
    for idx, item in enumerate(messages, start=1):
        if isinstance(item, LLMSpecificMessage):
            normalized.append(item)
            continue
        if isinstance(item, dict):
            llm_specific = _decode_llm_specific_message(item)
            if llm_specific is not None:
                normalized.append(llm_specific)
            else:
                normalized.append(_decode_json_compatible(item))
            continue
        raise ValueError(f"Message #{idx} is not an object: {type(item).__name__}")
    return normalized


def _convert_messages_to_google_contents(
    messages: list[Any],
) -> tuple[str, list[types.Content]]:
    from pipecat.adapters.services.gemini_adapter import GeminiLLMAdapter

    adapter = GeminiLLMAdapter()
    context = LLMContext(messages=messages)
    params = adapter.get_llm_invocation_params(context)
    system_instruction = str(params.get("system_instruction") or "")
    contents = list(params.get("messages") or [])
    return system_instruction, contents


def _minimal_function_declarations() -> list[types.FunctionDeclaration]:
    return [
        types.FunctionDeclaration(
            name="move",
            description="Move your ship to an adjacent sector. You can only move one sector at a time.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "to_sector": {
                        "type": "integer",
                        "description": "Adjacent sector ID to move to",
                    }
                },
                "required": ["to_sector"],
            },
        ),
        types.FunctionDeclaration(
            name="finished",
            description="Signal that you have completed the assigned task.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Completion message describing what was accomplished",
                    }
                },
                "required": ["message"],
            },
        ),
    ]


def _build_tools(mode: str) -> list[Any]:
    if mode == "minimal":
        declarations = _minimal_function_declarations()
        return [types.Tool(function_declarations=declarations)]
    if mode == "full":
        # Use the exact adapter conversion path as the harness.
        from pipecat.adapters.services.gemini_adapter import GeminiLLMAdapter
        from tool_catalog import build_tools_schema

        adapter = GeminiLLMAdapter()
        return adapter.to_provider_tools_format(build_tools_schema())
    raise ValueError(f"Unknown tools mode: {mode}")


def _extract_function_calls(response: types.GenerateContentResponse) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    response_calls = getattr(response, "function_calls", None)
    if response_calls:
        for call in response_calls:
            out.append(
                {
                    "name": call.name,
                    "args": dict(call.args or {}),
                    "id": getattr(call, "id", None),
                }
            )
        if out:
            return out

    candidates = response.candidates or []
    for candidate in candidates:
        content = candidate.content
        if content is None:
            continue
        for part in content.parts or []:
            function_call = part.function_call
            if function_call is None:
                continue
            out.append(
                {
                    "name": function_call.name,
                    "args": dict(function_call.args or {}),
                    "id": getattr(function_call, "id", None),
                }
            )
    return out


def _extract_function_calls_from_stream(chunks: list[types.GenerateContentResponse]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for chunk in chunks:
        candidates = chunk.candidates or []
        for candidate in candidates:
            content = candidate.content
            if content is None:
                continue
            for part in content.parts or []:
                function_call = part.function_call
                if function_call is None:
                    continue
                out.append(
                    {
                        "name": function_call.name,
                        "args": dict(function_call.args or {}),
                        "id": getattr(function_call, "id", None),
                    }
                )
    return out


def _primary_decision(function_calls: list[dict[str, Any]]) -> str:
    if not function_calls:
        return "no_tool_call"

    first_name = str(function_calls[0].get("name") or "")
    if first_name == "move":
        return "move"
    if first_name == "finished":
        return "finished"
    return f"other:{first_name}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one Google SDK inference call from a reconstructed messages file.",
    )
    parser.add_argument("messages_file", help="Path to .py or .json file containing messages list")
    parser.add_argument(
        "--messages-var",
        default=DEFAULT_MESSAGES_VAR,
        help=f"Variable name in .py/.json payload (default: {DEFAULT_MESSAGES_VAR})",
    )
    parser.add_argument(
        "--provider-invocation-var",
        default=None,
        help=(
            "Optional dotted path to a captured provider_invocation_params dict "
            "(for exact harness invocation replay)."
        ),
    )
    parser.add_argument("--model", default="supernova", help="Google model name")
    parser.add_argument(
        "--api-mode",
        choices=["sync", "stream"],
        default="sync",
        help="Google API call mode. Harness uses stream.",
    )
    parser.add_argument(
        "--tools",
        choices=["minimal", "full"],
        default="full",
        help="Function declarations to expose to the model",
    )
    parser.add_argument(
        "--api-key-env",
        default="GOOGLE_API_KEY",
        help="Env var containing Google API key",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Google API key override (takes precedence over --api-key-env)",
    )
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-output-tokens", type=int, default=None)
    parser.add_argument(
        "--thinking-level",
        choices=["minimal", "low", "medium", "high"],
        default=None,
        help="Optional Gemini thinking_level override",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=None,
        help="Optional thinking_budget override",
    )
    parser.add_argument(
        "--include-thoughts",
        action="store_true",
        help="Request thoughts in response metadata",
    )
    parser.add_argument(
        "--function-calling-mode",
        choices=["AUTO", "ANY", "NONE", "VALIDATED"],
        default=None,
        help="Optional tool calling mode override. Omit for harness parity.",
    )
    parser.add_argument(
        "--disable-automatic-function-calling",
        action="store_true",
        help="Set automatic_function_calling.disable=true.",
    )
    parser.add_argument(
        "--system-replace-file",
        default=None,
        help="Replace system instruction with contents of this file",
    )
    parser.add_argument(
        "--system-append-file",
        default=None,
        help="Append contents of this file to system instruction",
    )
    parser.add_argument(
        "--system-append-text",
        default=None,
        help="Append inline text to system instruction",
    )
    parser.add_argument(
        "--dump-response-json",
        default=None,
        help="Optional path to write full raw response JSON",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    messages_path = Path(args.messages_file).resolve()
    if not messages_path.exists():
        raise SystemExit(f"messages_file not found: {messages_path}")

    input_mode = "messages"
    messages: list[Any] = []
    payload = _load_data(messages_path)
    if args.provider_invocation_var:
        input_mode = "provider_invocation"
        invocation = _resolve_dotted_path(payload, args.provider_invocation_var)
        if not isinstance(invocation, dict):
            raise ValueError(
                f"Expected dict at provider invocation path, got {type(invocation).__name__}"
            )
        invocation = _decode_json_compatible(invocation)
        system_instruction = str(invocation.get("system_instruction") or "")
        contents = list(invocation.get("messages") or [])
        tools = invocation.get("tools")
        if tools is None:
            tools = _build_tools(args.tools)
    else:
        messages = _load_messages(messages_path, args.messages_var)
        system_instruction, contents = _convert_messages_to_google_contents(messages)
        tools = _build_tools(args.tools)

    if args.system_replace_file:
        system_instruction = _read_text(Path(args.system_replace_file)).strip()
    if args.system_append_file:
        append_block = _read_text(Path(args.system_append_file)).strip()
        if append_block:
            system_instruction = f"{system_instruction}\n\n{append_block}".strip()
    if args.system_append_text:
        system_instruction = f"{system_instruction}\n\n{args.system_append_text}".strip()

    api_key = args.api_key or os.getenv(args.api_key_env)
    if not api_key:
        raise SystemExit(
            f"Missing API key. Provide --api-key or set {args.api_key_env}."
        )

    thinking_cfg: types.ThinkingConfig | None = None
    if args.thinking_level is not None or args.thinking_budget is not None:
        thinking_kwargs: dict[str, Any] = {"include_thoughts": args.include_thoughts}
        if args.thinking_level is not None:
            thinking_kwargs["thinking_level"] = args.thinking_level
        if args.thinking_budget is not None:
            thinking_kwargs["thinking_budget"] = args.thinking_budget
        thinking_cfg = types.ThinkingConfig(**thinking_kwargs)

    config_kwargs: dict[str, Any] = {
        "system_instruction": system_instruction,
        "tools": tools,
    }
    if args.temperature is not None:
        config_kwargs["temperature"] = args.temperature
    if args.max_output_tokens is not None:
        config_kwargs["max_output_tokens"] = args.max_output_tokens
    if thinking_cfg is not None:
        config_kwargs["thinking_config"] = thinking_cfg
    if args.function_calling_mode is not None:
        config_kwargs["tool_config"] = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode=args.function_calling_mode)
        )
    if args.disable_automatic_function_calling:
        config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
            disable=True
        )
    config = types.GenerateContentConfig(**config_kwargs)

    client = genai.Client(api_key=api_key)
    response = None
    streamed_chunks: list[types.GenerateContentResponse] = []
    if args.api_mode == "stream":
        for chunk in client.models.generate_content_stream(
            model=args.model,
            contents=contents,
            config=config,
        ):
            streamed_chunks.append(chunk)
        function_calls = _extract_function_calls_from_stream(streamed_chunks)
    else:
        response = client.models.generate_content(
            model=args.model,
            contents=contents,
            config=config,
        )
        function_calls = _extract_function_calls(response)

    decision = _primary_decision(function_calls)
    first_tool_name = function_calls[0]["name"] if function_calls else None

    text = None
    if response is not None:
        try:
            text = response.text
        except Exception:  # noqa: BLE001
            text = None

    summary = {
        "messages_file": str(messages_path),
        "input_mode": input_mode,
        "model": args.model,
        "api_mode": args.api_mode,
        "tools_mode": args.tools,
        "messages_count": len(messages),
        "contents_count": len(contents),
        "decision": decision,
        "first_tool_call_name": first_tool_name,
        "function_call_count": len(function_calls),
        "function_calls": function_calls,
        "response_text": text,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))

    if args.dump_response_json:
        dump_path = Path(args.dump_response_json).resolve()
        if args.api_mode == "stream":
            payload = {
                "api_mode": "stream",
                "chunk_count": len(streamed_chunks),
                "chunks": [chunk.model_dump(mode="json") for chunk in streamed_chunks],
            }
            dump_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
        else:
            dump_path.write_text(
                json.dumps(response.model_dump(mode="json"), indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
        print(f"WROTE_RESPONSE_JSON={dump_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
