#!/usr/bin/env python3
"""Bounded GPT-5.6/GPT-5.5 Responses API contract probe.

The default mode is a no-network dry run. Live execution requires both
``--execute`` and the exact acknowledgement token printed by ``--dry-run``.
The probe uses fixed prompts, ``store=False``, zero SDK retries, sequential
requests, and a hard request/token/cost/wall-time ledger.

It writes only a sanitized, machine-readable checkpoint under the project
directory. Prompts, API keys, headers, encrypted reasoning content, and raw
response bodies are never persisted.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)


REPO_ROOT = Path("/home/khkramer/src/gb-benchmarks")
PORT_DIR = REPO_ROOT / "port-to-port"
PROJECT_DIR = PORT_DIR / "proj-2026-07-16-1632"
ENV_FILE = REPO_ROOT / ".env"
OUTPUT_JSON = PROJECT_DIR / "step1-gpt56-probe.json"

EXPECTED_OPENAI_SDK = "2.21.0"

GPT56_MODELS = (
    "gpt-5.6-luna",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
)
GPT55_MODEL = "gpt-5.5"

INITIAL_MAX_OUTPUT_TOKENS = 16_384
ESCALATED_MAX_OUTPUT_TOKENS = 32_768
INPUT_TOKEN_RESERVATION = 4_096
REQUEST_TIMEOUT_SECS = 600.0
MAX_REQUESTS = 24
MAX_RETRY_REQUESTS = 8
MAX_ACCOUNTED_TOKENS = 999_424
MAX_ACCOUNTED_USD = 15.00
MAX_WALL_SECS = 14_400.0

PROBE_CODE = "gpt56-contract-v1"
EXPECTED_FINAL = f"{PROBE_CODE} status: ready"
INSTRUCTIONS = (
    "You are a deterministic two-turn API contract diagnostic. On the first "
    "turn, call lookup_probe exactly once with code gpt56-contract-v1. After "
    "the tool result says the code is ready, respond exactly: "
    f"{EXPECTED_FINAL}"
)
FIRST_INPUT = [
    {
        "role": "user",
        "content": [
            {
                "type": "input_text",
                "text": "Look up code gpt56-contract-v1 and report its status.",
            }
        ],
    }
]
RESPONSES_TOOL = {
    "type": "function",
    "name": "lookup_probe",
    "description": "Look up a fixed diagnostic code.",
    "parameters": {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
        "additionalProperties": False,
    },
    "strict": True,
}
CHAT_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup_probe",
        "description": "Look up a fixed diagnostic code.",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


@dataclass(frozen=True)
class Price:
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float


PRICES = {
    "gpt-5.6-luna": Price(1.00, 0.10, 6.00),
    "gpt-5.6-terra": Price(2.50, 0.25, 15.00),
    "gpt-5.6-sol": Price(5.00, 0.50, 30.00),
    "gpt-5.5": Price(5.00, 0.50, 30.00),
}


@dataclass(frozen=True)
class PhysicalCall:
    api: str
    model: str
    effort: str
    turn: int


@dataclass
class Reservation:
    model: str
    max_output_tokens: int
    tokens: int
    usd: float
    wall_secs: float


class ProbeError(RuntimeError):
    """User-facing probe setup or safety failure."""


class BudgetExceeded(ProbeError):
    """Raised before a request when its reservation does not fit."""


class PlannedBudgetStop(ProbeError):
    """Raised after checkpointing when a planned request cannot fit."""


class RequestWallTimeout(TimeoutError):
    """Raised by the process-level total request deadline."""


class SystemicProbeStop(ProbeError):
    """Raised after two consecutive identical systemic client/access errors."""


class PartialStreamError(Exception):
    """Carry sanitized partial events while preserving the original exception."""

    def __init__(
        self,
        original: Exception,
        events: list[dict[str, Any]],
        request_id: str | None,
    ) -> None:
        super().__init__(str(original))
        self.original = original
        self.events = events
        self.request_id = request_id


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_env_key(path: Path = ENV_FILE, key: str = "OPENAI_API_KEY") -> str:
    """Read one dotenv key without sourcing or logging the file."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ProbeError(f"Could not read {path}: {exc}") from exc
    prefix = f"{key}="
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            return value
    raise ProbeError(f"{key} was not found or was empty in {path}")


def installed_sdk_version() -> str:
    return importlib.metadata.version("openai")


def planned_calls() -> list[PhysicalCall]:
    calls: list[PhysicalCall] = []
    for model in GPT56_MODELS:
        for effort in ("low", "max"):
            calls.extend(
                [
                    PhysicalCall("responses", model, effort, 1),
                    PhysicalCall("responses", model, effort, 2),
                ]
            )
    calls.extend(
        [
            PhysicalCall("responses", GPT55_MODEL, "medium", 1),
            PhysicalCall("responses", GPT55_MODEL, "medium", 2),
            PhysicalCall("chat", "gpt-5.6-luna", "low", 1),
            PhysicalCall("chat", GPT55_MODEL, "medium", 1),
        ]
    )
    return calls


def reservation_for(
    model: str,
    max_output_tokens: int,
    input_tokens: int = INPUT_TOKEN_RESERVATION,
) -> Reservation:
    price = PRICES[model]
    tokens = input_tokens + max_output_tokens
    usd = (
        input_tokens * price.input_per_million
        + max_output_tokens * price.output_per_million
    ) / 1_000_000
    return Reservation(model, max_output_tokens, tokens, usd, REQUEST_TIMEOUT_SECS)


def planned_worst_case() -> dict[str, Any]:
    initial = [
        reservation_for(
            call.model,
            INITIAL_MAX_OUTPUT_TOKENS,
            INPUT_TOKEN_RESERVATION
            + (INITIAL_MAX_OUTPUT_TOKENS if call.api == "responses" and call.turn == 2 else 0),
        )
        for call in planned_calls()
    ]
    retry = reservation_for(
        "gpt-5.6-sol",
        ESCALATED_MAX_OUTPUT_TOKENS,
        INPUT_TOKEN_RESERVATION + ESCALATED_MAX_OUTPUT_TOKENS,
    )
    return {
        "planned_requests": len(initial),
        "retry_requests_reserved": MAX_RETRY_REQUESTS,
        "requests_total": len(initial) + MAX_RETRY_REQUESTS,
        "tokens": sum(item.tokens for item in initial) + MAX_RETRY_REQUESTS * retry.tokens,
        "usd": round(sum(item.usd for item in initial) + MAX_RETRY_REQUESTS * retry.usd, 6),
        "wall_secs": (len(initial) + MAX_RETRY_REQUESTS) * REQUEST_TIMEOUT_SECS,
    }


def budget_fingerprint() -> str:
    encoded = json.dumps(
        {"limits": limits_payload(), "worst": planned_worst_case()},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12].upper()


def approval_token() -> str:
    return f"I_APPROVE_GPT56_RESPONSES_PROBE_{budget_fingerprint()}"


@contextlib.contextmanager
def total_request_deadline(seconds: float):
    """Enforce a process-level total deadline, including streaming reads."""

    if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
        raise ProbeError("hard request deadlines require POSIX setitimer support")
    previous_handler = signal.getsignal(signal.SIGALRM)

    def on_alarm(_signum: int, _frame: Any) -> None:
        raise RequestWallTimeout(f"total request wall timeout exceeded {seconds}s")

    signal.signal(signal.SIGALRM, on_alarm)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


class BudgetLedger:
    def __init__(self) -> None:
        self.started_monotonic = time.monotonic()
        self.requests = 0
        self.retry_requests = 0
        self.accounted_tokens = 0
        self.accounted_usd = 0.0

    @property
    def elapsed_wall_secs(self) -> float:
        return time.monotonic() - self.started_monotonic

    def preflight(self, reservation: Reservation, *, retry: bool) -> None:
        if self.requests + 1 > MAX_REQUESTS:
            raise BudgetExceeded(f"request ceiling would exceed {MAX_REQUESTS}")
        if retry and self.retry_requests + 1 > MAX_RETRY_REQUESTS:
            raise BudgetExceeded(f"retry ceiling would exceed {MAX_RETRY_REQUESTS}")
        if self.accounted_tokens + reservation.tokens > MAX_ACCOUNTED_TOKENS:
            raise BudgetExceeded("token reservation would exceed hard ceiling")
        if self.accounted_usd + reservation.usd > MAX_ACCOUNTED_USD + 1e-12:
            raise BudgetExceeded("cost reservation would exceed hard ceiling")
        if self.elapsed_wall_secs + reservation.wall_secs > MAX_WALL_SECS:
            raise BudgetExceeded("wall-time reservation would exceed hard ceiling")
        self.requests += 1
        if retry:
            self.retry_requests += 1

    def account(
        self,
        reservation: Reservation,
        usage: dict[str, int | None] | None,
        *,
        unknown_may_be_billable: bool,
    ) -> None:
        if not usage:
            if unknown_may_be_billable:
                self.accounted_tokens += reservation.tokens
                self.accounted_usd += reservation.usd
            return
        input_tokens = int(usage.get("input_tokens") or 0)
        cached_tokens = min(input_tokens, int(usage.get("cached_tokens") or 0))
        output_tokens = int(usage.get("output_tokens") or 0)
        price = PRICES[reservation.model]
        self.accounted_tokens += input_tokens + output_tokens
        self.accounted_usd += (
            (input_tokens - cached_tokens) * price.input_per_million
            + cached_tokens * price.cached_input_per_million
            + output_tokens * price.output_per_million
        ) / 1_000_000

    def snapshot(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "retry_requests": self.retry_requests,
            "accounted_tokens": self.accounted_tokens,
            "accounted_usd": round(self.accounted_usd, 6),
            "elapsed_wall_secs": round(self.elapsed_wall_secs, 3),
        }


def to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        # responses.stream() returns ParsedResponseFunctionToolCall objects in
        # SDK 2.21.0.  ``parsed_arguments`` is an SDK convenience field, not a
        # Responses API input field; replaying the unfiltered dump produces a
        # provider 400.  Keep the API item and drop that client-only field.
        return value.model_dump(
            mode="json",
            exclude_none=True,
            exclude={"parsed_arguments"},
        )
    if isinstance(value, dict):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def get_attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def usage_summary(response: Any) -> dict[str, int | None] | None:
    usage = get_attr(response, "usage")
    if usage is None:
        return None
    input_details = get_attr(usage, "input_tokens_details") or get_attr(
        usage, "prompt_tokens_details"
    )
    output_details = get_attr(usage, "output_tokens_details") or get_attr(
        usage, "completion_tokens_details"
    )
    return {
        "input_tokens": get_attr(usage, "input_tokens", get_attr(usage, "prompt_tokens")),
        "cached_tokens": get_attr(input_details, "cached_tokens"),
        "output_tokens": get_attr(usage, "output_tokens", get_attr(usage, "completion_tokens")),
        "reasoning_tokens": get_attr(output_details, "reasoning_tokens"),
        "total_tokens": get_attr(usage, "total_tokens"),
    }


def sanitize_error(error: Any) -> dict[str, Any] | None:
    if error is None:
        return None
    if isinstance(error, dict):
        return {key: error.get(key) for key in ("code", "message") if error.get(key) is not None}
    return {
        key: get_attr(error, key)
        for key in ("code", "message")
        if get_attr(error, key) is not None
    }


def sanitize_response(response: Any) -> dict[str, Any]:
    incomplete = get_attr(response, "incomplete_details")
    return {
        "id": get_attr(response, "id"),
        "model": get_attr(response, "model"),
        "status": get_attr(response, "status"),
        "service_tier": get_attr(response, "service_tier"),
        "incomplete_reason": get_attr(incomplete, "reason"),
        "error": sanitize_error(get_attr(response, "error")),
        "usage": usage_summary(response),
        "output_types": [get_attr(item, "type") for item in (get_attr(response, "output") or [])],
    }


def sanitize_event(event: Any) -> dict[str, Any]:
    event_type = get_attr(event, "type")
    result: dict[str, Any] = {"type": event_type}
    for key in ("sequence_number", "output_index", "item_id"):
        value = get_attr(event, key)
        if value is not None:
            result[key] = value
    if event_type == "response.function_call_arguments.delta":
        result["delta"] = get_attr(event, "delta", "")
    elif event_type == "response.function_call_arguments.done":
        result["arguments"] = get_attr(event, "arguments", "")
        result["name"] = get_attr(event, "name")
    elif event_type in {"response.output_text.delta", "response.reasoning_text.delta"}:
        result["delta_length"] = len(get_attr(event, "delta", "") or "")
    item = get_attr(event, "item")
    if item is not None:
        item_type = get_attr(item, "type")
        result["item"] = {
            key: get_attr(item, key)
            for key in ("type", "id", "status", "call_id", "name", "arguments")
            if get_attr(item, key) is not None
        }
        if item_type == "message":
            result["item"]["content_types"] = [
                get_attr(part, "type") for part in (get_attr(item, "content") or [])
            ]
    if event_type in {"response.completed", "response.incomplete", "response.failed"}:
        result["response"] = sanitize_response(get_attr(event, "response"))
    return result


def build_responses_request(
    *,
    model: str,
    effort: str,
    input_items: list[Any],
    tool_choice: Any,
    max_output_tokens: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "instructions": INSTRUCTIONS,
        "input": input_items,
        "tools": [RESPONSES_TOOL],
        "tool_choice": tool_choice,
        "reasoning": {"effort": effort},
        "max_output_tokens": max_output_tokens,
        "store": False,
        "include": ["reasoning.encrypted_content"],
        "timeout": REQUEST_TIMEOUT_SECS,
    }


def build_chat_request(*, model: str, effort: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": "Look up code gpt56-contract-v1."},
        ],
        "tools": [CHAT_TOOL],
        "tool_choice": {"type": "function", "function": {"name": "lookup_probe"}},
        "reasoning_effort": effort,
        "max_completion_tokens": INITIAL_MAX_OUTPUT_TOKENS,
        "store": False,
        "timeout": REQUEST_TIMEOUT_SECS,
    }


def sanitized_request_shape(
    request: dict[str, Any],
    *,
    api: str,
    turn: int,
    input_token_reservation: int,
) -> dict[str, Any]:
    """Validate and sanitize the exact request dict passed to the SDK."""

    if request.get("store") is not False:
        raise ProbeError("live request must contain store=False")
    if "service_tier" in request:
        raise ProbeError("live request must omit service_tier")
    if api == "responses":
        reasoning = request.get("reasoning")
        if not isinstance(reasoning, dict) or not reasoning.get("effort"):
            raise ProbeError("Responses request must contain reasoning.effort")
        if "reasoning_effort" in request:
            raise ProbeError("Responses request must not contain reasoning_effort")
        max_output_tokens = request.get("max_output_tokens")
        input_items = request.get("input") or []
        tool_names = [tool.get("name") for tool in request.get("tools") or []]
        effort_shape: dict[str, Any] = {"reasoning": {"effort": reasoning["effort"]}}
    elif api == "chat":
        if not request.get("reasoning_effort"):
            raise ProbeError("Chat contract request must contain reasoning_effort")
        max_output_tokens = request.get("max_completion_tokens")
        input_items = request.get("messages") or []
        tool_names = [
            get_attr(tool.get("function") or {}, "name") for tool in request.get("tools") or []
        ]
        effort_shape = {"reasoning_effort": request["reasoning_effort"]}
    else:
        raise ProbeError(f"unsupported probe API surface {api!r}")
    return {
        "api": api,
        "model": request.get("model"),
        **effort_shape,
        "store": request["store"],
        "service_tier_present": "service_tier" in request,
        "max_output_tokens": max_output_tokens,
        "input_token_reservation": input_token_reservation,
        "tool_names": tool_names,
        "tool_choice": to_plain(request.get("tool_choice")),
        "turn": turn,
        "input_item_types": [
            get_attr(item, "type", get_attr(item, "role")) for item in input_items
        ],
    }


def classify_exception(exc: BaseException) -> tuple[str, bool, bool]:
    """Return (classification, transient_retry, unknown_may_be_billable)."""

    target = exc.original if isinstance(exc, PartialStreamError) else exc
    if isinstance(target, RequestWallTimeout):
        return "request_wall_timeout", True, True
    if isinstance(target, RateLimitError):
        return "rate_limit", True, False
    if isinstance(target, (APITimeoutError, APIConnectionError)):
        return "transport_timeout_or_connection", True, True
    if isinstance(target, BadRequestError):
        return "unsupported_or_invalid_request", False, False
    if isinstance(target, APIStatusError):
        status = getattr(target, "status_code", None)
        if isinstance(status, int) and status >= 500:
            return "provider_5xx", True, True
        if status in {401, 403, 404, 422}:
            return "access_or_request_error", False, False
        return "api_status_error", False, False
    return "unexpected_client_error", False, True


def public_exception(exc: BaseException) -> dict[str, Any]:
    target = exc.original if isinstance(exc, PartialStreamError) else exc
    message = str(getattr(target, "message", "") or target)
    body = getattr(target, "body", None)
    result = {
        "type": type(target).__name__,
        "status_code": getattr(target, "status_code", None),
        "message": message[:500],
    }
    if isinstance(body, dict):
        provider_error = body.get("error")
        if isinstance(provider_error, dict):
            body = provider_error
        for source, destination in (("code", "provider_code"), ("param", "provider_param")):
            value = body.get(source)
            if isinstance(value, (str, int, float, bool)):
                result[destination] = value
    return result


def transient_failed_response(trace: dict[str, Any]) -> bool:
    error = trace.get("error") or {}
    return error.get("code") in {
        "server_error",
        "internal_error",
        "rate_limit_exceeded",
        "temporarily_unavailable",
    }


def response_function_call(response: Any) -> tuple[Any | None, str | None]:
    calls = [item for item in (get_attr(response, "output") or []) if get_attr(item, "type") == "function_call"]
    if len(calls) != 1:
        return None, f"expected exactly one function_call, got {len(calls)}"
    call = calls[0]
    if get_attr(call, "name") != "lookup_probe":
        return None, f"unexpected function name {get_attr(call, 'name')!r}"
    call_id = get_attr(call, "call_id")
    if not call_id:
        return None, "function call has no call_id"
    try:
        arguments = json.loads(get_attr(call, "arguments", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        return None, f"invalid function arguments: {exc}"
    if arguments != {"code": PROBE_CODE}:
        return None, f"unexpected function arguments {arguments!r}"
    return call, None


def response_text(response: Any) -> str:
    direct = get_attr(response, "output_text")
    if isinstance(direct, str):
        return direct
    parts: list[str] = []
    for item in get_attr(response, "output") or []:
        if get_attr(item, "type") != "message":
            continue
        for content in get_attr(item, "content") or []:
            if get_attr(content, "type") in {"output_text", "text"}:
                text = get_attr(content, "text")
                if text:
                    parts.append(text)
    return "".join(parts)


class ProbeRunner:
    def __init__(self, client: OpenAI) -> None:
        self.client = client
        self.ledger = BudgetLedger()
        self.records: list[dict[str, Any]] = []
        self.started_at = utc_now()
        self.stop_reason: str | None = None
        self.recovery_of_stop_reason: str | None = None
        self.last_systemic_signature: tuple[Any, ...] | None = None
        self.consecutive_systemic_errors = 0

    @classmethod
    def from_checkpoint(cls, client: OpenAI) -> "ProbeRunner":
        """Restore the original hard-budget ledger for a bounded recovery."""

        try:
            payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProbeError(f"Could not load recovery checkpoint {OUTPUT_JSON}: {exc}") from exc
        if payload.get("schema_version") != 1:
            raise ProbeError("Recovery checkpoint has an unsupported schema version")
        if payload.get("limits") != limits_payload():
            raise ProbeError("Recovery checkpoint limits differ from the approved limits")
        if payload.get("planned_worst_case") != planned_worst_case():
            raise ProbeError("Recovery checkpoint plan differs from the approved plan")
        records = payload.get("records")
        snapshot = payload.get("ledger")
        if not isinstance(records, list) or not isinstance(snapshot, dict):
            raise ProbeError("Recovery checkpoint is missing records or ledger state")
        attempted_records = sum(record.get("attempt_number") is not None for record in records)
        if int(snapshot.get("requests") or 0) != attempted_records:
            raise ProbeError("Recovery checkpoint ledger does not match attempted records")

        runner = cls(client)
        runner.records = records
        runner.started_at = str(payload.get("started_at") or runner.started_at)
        runner.ledger.requests = int(snapshot.get("requests") or 0)
        runner.ledger.retry_requests = int(snapshot.get("retry_requests") or 0)
        runner.ledger.accounted_tokens = int(snapshot.get("accounted_tokens") or 0)
        runner.ledger.accounted_usd = float(snapshot.get("accounted_usd") or 0.0)
        prior_elapsed = float(snapshot.get("elapsed_wall_secs") or 0.0)
        runner.ledger.started_monotonic = time.monotonic() - prior_elapsed
        runner.recovery_of_stop_reason = payload.get("recovery_of_stop_reason") or payload.get(
            "stop_reason"
        )
        runner.stop_reason = None
        return runner

    def checkpoint(self) -> None:
        payload = {
            "schema_version": 1,
            "started_at": self.started_at,
            "updated_at": utc_now(),
            "openai_sdk_version": installed_sdk_version(),
            "limits": limits_payload(),
            "planned_worst_case": planned_worst_case(),
            "ledger": self.ledger.snapshot(),
            "stop_reason": self.stop_reason,
            "recovery_of_stop_reason": self.recovery_of_stop_reason,
            "records": self.records,
        }
        PROJECT_DIR.mkdir(parents=True, exist_ok=True)
        temp = OUTPUT_JSON.with_suffix(".json.tmp")
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, OUTPUT_JSON)

    def _stream_responses(self, request: dict[str, Any]) -> tuple[Any, str | None, list[dict[str, Any]]]:
        terminal = None
        fixtures: list[dict[str, Any]] = []
        request_id: str | None = None
        try:
            with self.client.responses.stream(**request) as stream:
                raw_response = getattr(stream, "_response", None)
                headers = getattr(raw_response, "headers", None)
                if headers is not None:
                    request_id = headers.get("x-request-id")
                for event in stream:
                    fixtures.append(sanitize_event(event))
                    if get_attr(event, "type") in {
                        "response.completed",
                        "response.incomplete",
                        "response.failed",
                    }:
                        terminal = get_attr(event, "response")
        except Exception as exc:
            raise PartialStreamError(exc, fixtures, request_id) from exc
        if terminal is None:
            error = ProbeError("stream ended without completed/incomplete/failed terminal event")
            raise PartialStreamError(error, fixtures, request_id)
        return terminal, request_id, fixtures

    def _attempt(
        self,
        *,
        api: str,
        model: str,
        effort: str,
        turn: int,
        max_output_tokens: int,
        input_token_reservation: int,
        retry: bool,
        operation: Callable[[], tuple[Any, str | None, list[dict[str, Any]]]],
        request_shape: dict[str, Any],
        success_status: str | None = None,
        allow_missing_reasoning_rejection: bool = False,
    ) -> tuple[Any | None, dict[str, Any]]:
        reservation = reservation_for(model, max_output_tokens, input_token_reservation)
        self.ledger.preflight(reservation, retry=retry)
        started = time.monotonic()
        record: dict[str, Any] = {
            "attempt_number": len(self.records) + 1,
            "retry": retry,
            "request": request_shape,
            "reservation": asdict(reservation),
        }
        try:
            with total_request_deadline(reservation.wall_secs):
                response, request_id, fixtures = operation()
            elapsed = time.monotonic() - started
            trace = sanitize_response(response)
            if trace.get("status") is None and success_status is not None:
                trace["status"] = success_status
            usage = trace.get("usage")
            self.ledger.account(reservation, usage, unknown_may_be_billable=True)
            record.update(
                {
                    "classification": f"response_{trace.get('status')}",
                    "elapsed_secs": round(elapsed, 3),
                    "request_id": request_id,
                    "response": trace,
                    "events": fixtures,
                }
            )
            if trace.get("status") == "failed":
                record["transient_retry_eligible"] = transient_failed_response(trace)
            result = response
        except (KeyboardInterrupt, SystemExit, GeneratorExit) as exc:
            elapsed = time.monotonic() - started
            self.ledger.account(reservation, None, unknown_may_be_billable=True)
            record.update(
                {
                    "classification": "operator_interrupt",
                    "elapsed_secs": round(elapsed, 3),
                    "error": {"type": type(exc).__name__},
                    "events": [],
                }
            )
            self.records.append(record)
            self.stop_reason = "operator_interrupt"
            self.checkpoint()
            raise
        except Exception as exc:
            elapsed = time.monotonic() - started
            classification, transient, unknown_billable = classify_exception(exc)
            self.ledger.account(reservation, None, unknown_may_be_billable=unknown_billable)
            record.update(
                {
                    "classification": classification,
                    "transient_retry_eligible": transient,
                    "elapsed_secs": round(elapsed, 3),
                    "error": public_exception(exc),
                    "request_id": exc.request_id if isinstance(exc, PartialStreamError) else None,
                    "events": exc.events if isinstance(exc, PartialStreamError) else [],
                }
            )
            result = None
        self.records.append(record)
        self.checkpoint()
        print(
            f"ATTEMPT={record['attempt_number']} API={api} MODEL={model} "
            f"EFFORT={effort} TURN={turn} RETRY={int(retry)} "
            f"CLASS={record['classification']} ELAPSED={record['elapsed_secs']}s",
            flush=True,
        )
        systemic_classes = {
            "unexpected_client_error",
            "access_or_request_error",
            "unsupported_or_invalid_request",
        }
        if record["classification"] in systemic_classes:
            error = record.get("error") or {}
            message = str(error.get("message") or "").lower()
            expected_missing_reasoning = (
                allow_missing_reasoning_rejection
                and record["classification"] == "unsupported_or_invalid_request"
                and "reasoning" in message
                and ("required" in message or "without" in message)
            )
            if expected_missing_reasoning:
                record["systemic_halt_exempt"] = "sanitized_checkpoint_omitted_reasoning"
                self.last_systemic_signature = None
                self.consecutive_systemic_errors = 0
                self.checkpoint()
                return result, record
            signature = (
                record["classification"],
                error.get("type"),
                error.get("status_code"),
                error.get("provider_code"),
                error.get("provider_param"),
            )
            if signature == self.last_systemic_signature:
                self.consecutive_systemic_errors += 1
            else:
                self.last_systemic_signature = signature
                self.consecutive_systemic_errors = 1
            if self.consecutive_systemic_errors >= 2:
                self.stop_reason = f"repeated_systemic_error:{':'.join(str(x) for x in signature)}"
                self.checkpoint()
                raise SystemicProbeStop(self.stop_reason)
        else:
            self.last_systemic_signature = None
            self.consecutive_systemic_errors = 0
        return result, record

    def budget_blocked_record(
        self,
        *,
        api: str,
        model: str,
        effort: str,
        turn: int,
        max_output_tokens: int,
        input_token_reservation: int,
        retry: bool,
        allow_missing_reasoning_rejection: bool = False,
        error: BudgetExceeded,
    ) -> dict[str, Any]:
        reservation = reservation_for(model, max_output_tokens, input_token_reservation)
        record = {
            "attempt_number": None,
            "retry": retry,
            "request": {
                "api": api,
                "model": model,
                "turn": turn,
                "effective_effort": effort,
                "max_output_tokens": max_output_tokens,
                "input_token_reservation": input_token_reservation,
            },
            "reservation": asdict(reservation),
            "classification": "budget_blocked",
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        self.records.append(record)
        self.checkpoint()
        return record

    def responses_attempt(
        self,
        *,
        model: str,
        effort: str,
        turn: int,
        input_items: list[Any],
        tool_choice: Any,
        max_output_tokens: int,
        input_token_reservation: int,
        retry: bool,
        allow_missing_reasoning_rejection: bool = False,
    ) -> tuple[Any | None, dict[str, Any]]:
        request = build_responses_request(
            model=model,
            effort=effort,
            input_items=input_items,
            tool_choice=tool_choice,
            max_output_tokens=max_output_tokens,
        )
        return self._attempt(
            api="responses",
            model=model,
            effort=effort,
            turn=turn,
            max_output_tokens=max_output_tokens,
            input_token_reservation=input_token_reservation,
            retry=retry,
            operation=lambda: self._stream_responses(request),
            request_shape=sanitized_request_shape(
                request,
                api="responses",
                turn=turn,
                input_token_reservation=input_token_reservation,
            ),
            allow_missing_reasoning_rejection=allow_missing_reasoning_rejection,
        )

    def chat_attempt(self, *, model: str, effort: str, retry: bool) -> tuple[Any | None, dict[str, Any]]:
        request = build_chat_request(model=model, effort=effort)

        def operation() -> tuple[Any, str | None, list[dict[str, Any]]]:
            response = self.client.chat.completions.create(**request)
            return response, getattr(response, "_request_id", None), []

        return self._attempt(
            api="chat",
            model=model,
            effort=effort,
            turn=1,
            max_output_tokens=INITIAL_MAX_OUTPUT_TOKENS,
            input_token_reservation=INPUT_TOKEN_RESERVATION,
            retry=retry,
            operation=operation,
            request_shape=sanitized_request_shape(
                request,
                api="chat",
                turn=1,
                input_token_reservation=INPUT_TOKEN_RESERVATION,
            ),
            success_status="completed",
        )

    @staticmethod
    def _needs_cap_retry(record: dict[str, Any], max_output_tokens: int) -> bool:
        response = record.get("response") or {}
        reason = response.get("incomplete_reason")
        return (
            response.get("status") == "incomplete"
            and reason in {"max_tokens", "max_output_tokens"}
            and max_output_tokens < ESCALATED_MAX_OUTPUT_TOKENS
        )

    @staticmethod
    def _needs_transient_retry(record: dict[str, Any]) -> bool:
        return bool(record.get("transient_retry_eligible"))

    def responses_with_retry(
        self,
        *,
        model: str,
        effort: str,
        turn: int,
        input_items: list[Any],
        tool_choice: Any,
        input_token_reservation: int,
        allow_missing_reasoning_rejection: bool = False,
    ) -> tuple[Any | None, dict[str, Any]]:
        cap = INITIAL_MAX_OUTPUT_TOKENS
        try:
            response, record = self.responses_attempt(
                model=model,
                effort=effort,
                turn=turn,
                input_items=input_items,
                tool_choice=tool_choice,
                max_output_tokens=cap,
                input_token_reservation=input_token_reservation,
                retry=False,
                allow_missing_reasoning_rejection=allow_missing_reasoning_rejection,
            )
        except BudgetExceeded as exc:
            record = self.budget_blocked_record(
                api="responses",
                model=model,
                effort=effort,
                turn=turn,
                max_output_tokens=cap,
                input_token_reservation=input_token_reservation,
                retry=False,
                error=exc,
            )
            self.stop_reason = f"planned_request_budget_blocked:{model}:{effort}:turn{turn}"
            self.checkpoint()
            raise PlannedBudgetStop(self.stop_reason) from exc
        if self._needs_cap_retry(record, cap):
            cap = ESCALATED_MAX_OUTPUT_TOKENS
            try:
                return self.responses_attempt(
                    model=model,
                    effort=effort,
                    turn=turn,
                    input_items=input_items,
                    tool_choice=tool_choice,
                    max_output_tokens=cap,
                    input_token_reservation=input_token_reservation,
                    retry=True,
                    allow_missing_reasoning_rejection=allow_missing_reasoning_rejection,
                )
            except BudgetExceeded as exc:
                return None, self.budget_blocked_record(
                    api="responses",
                    model=model,
                    effort=effort,
                    turn=turn,
                    max_output_tokens=cap,
                    input_token_reservation=input_token_reservation,
                    retry=True,
                    error=exc,
                )
        if self._needs_transient_retry(record):
            time.sleep(2.0)
            try:
                return self.responses_attempt(
                    model=model,
                    effort=effort,
                    turn=turn,
                    input_items=input_items,
                    tool_choice=tool_choice,
                    max_output_tokens=cap,
                    input_token_reservation=input_token_reservation,
                    retry=True,
                    allow_missing_reasoning_rejection=allow_missing_reasoning_rejection,
                )
            except BudgetExceeded as exc:
                return None, self.budget_blocked_record(
                    api="responses",
                    model=model,
                    effort=effort,
                    turn=turn,
                    max_output_tokens=cap,
                    input_token_reservation=input_token_reservation,
                    retry=True,
                    error=exc,
                )
        return response, record

    def run_round_trip(self, model: str, effort: str) -> None:
        first, first_record = self.responses_with_retry(
            model=model,
            effort=effort,
            turn=1,
            input_items=list(FIRST_INPUT),
            tool_choice={"type": "function", "name": "lookup_probe"},
            input_token_reservation=INPUT_TOKEN_RESERVATION,
        )
        if first is None or get_attr(first, "status") != "completed":
            first_record["round_trip_result"] = "turn_1_not_completed"
            self.checkpoint()
            return
        call, error = response_function_call(first)
        if error:
            first_record["round_trip_result"] = "invalid_turn_1_function_call"
            first_record["validation_error"] = error
            self.checkpoint()
            return
        replay_items = list(FIRST_INPUT)
        replay_items.extend(to_plain(item) for item in (get_attr(first, "output") or []))
        replay_items.append(
            {
                "type": "function_call_output",
                "call_id": get_attr(call, "call_id"),
                "output": json.dumps(
                    {"code": PROBE_CODE, "source": "deterministic-probe", "status": "ready"},
                    sort_keys=True,
                ),
            }
        )
        second, second_record = self.responses_with_retry(
            model=model,
            effort=effort,
            turn=2,
            input_items=replay_items,
            tool_choice="none",
            input_token_reservation=(
                INPUT_TOKEN_RESERVATION + int(first_record["request"]["max_output_tokens"])
            ),
        )
        if second is None or get_attr(second, "status") != "completed":
            second_record["round_trip_result"] = "turn_2_not_completed"
        elif response_text(second).strip() != EXPECTED_FINAL:
            second_record["round_trip_result"] = "wrong_final_text"
            second_record["visible_output_length"] = len(response_text(second))
        else:
            second_record["round_trip_result"] = "success"
        self.checkpoint()

    @staticmethod
    def _checkpoint_function_call(record: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Recover one sanitized function call without persisted reasoning text."""

        items = [
            event.get("item")
            for event in record.get("events") or []
            if event.get("type") == "response.output_item.done"
            and isinstance(event.get("item"), dict)
        ]
        calls = [item for item in items if item.get("type") == "function_call"]
        if len(calls) != 1:
            raise ProbeError("Recovery checkpoint does not contain exactly one function call")
        call, error = response_function_call({"output": calls})
        if error or call is None:
            raise ProbeError(f"Recovery checkpoint function call is invalid: {error}")
        reasoning_count = sum(item.get("type") == "reasoning" for item in items)
        return dict(call), reasoning_count

    def resume_round_trip(self, source_record: dict[str, Any]) -> None:
        """Finish a turn-two replay from a sanitized successful turn-one record."""

        request = source_record.get("request") or {}
        model = request.get("model")
        reasoning = request.get("reasoning") or {}
        effort = reasoning.get("effort")
        if model not in {*GPT56_MODELS, GPT55_MODEL} or not isinstance(effort, str):
            raise ProbeError("Recovery checkpoint has an unexpected model/effort identity")
        call, omitted_reasoning_items = self._checkpoint_function_call(source_record)
        replay_items = list(FIRST_INPUT)
        replay_items.append(call)
        replay_items.append(
            {
                "type": "function_call_output",
                "call_id": call["call_id"],
                "output": json.dumps(
                    {"code": PROBE_CODE, "source": "deterministic-probe", "status": "ready"},
                    sort_keys=True,
                ),
            }
        )
        second, second_record = self.responses_with_retry(
            model=model,
            effort=effort,
            turn=2,
            input_items=replay_items,
            tool_choice="none",
            input_token_reservation=(
                INPUT_TOKEN_RESERVATION + int(request["max_output_tokens"])
            ),
            allow_missing_reasoning_rejection=omitted_reasoning_items > 0,
        )
        second_record["recovery"] = {
            "source_attempt_number": source_record.get("attempt_number"),
            "omitted_sanitized_reasoning_items": omitted_reasoning_items,
            "reason": "sdk_2.21.0_parsed_arguments_is_not_an_api_input_field",
        }
        if second is None or get_attr(second, "status") != "completed":
            second_record["round_trip_result"] = "turn_2_not_completed"
        elif response_text(second).strip() != EXPECTED_FINAL:
            second_record["round_trip_result"] = "wrong_final_text"
            second_record["visible_output_length"] = len(response_text(second))
        elif omitted_reasoning_items:
            second_record["round_trip_result"] = "success_reasoning_omitted"
        else:
            second_record["round_trip_result"] = "success_sanitized_replay"
        self.checkpoint()

    def resume_after_contract_fix(self) -> None:
        """Finish missing calls, including retries only within the original ceiling."""

        expected = [
            (model, effort)
            for model in GPT56_MODELS
            for effort in ("low", "max")
        ] + [(GPT55_MODEL, "medium")]
        sources: dict[tuple[str, str], dict[str, Any]] = {}
        for record in self.records:
            request = record.get("request") or {}
            reasoning = request.get("reasoning") or {}
            key = (request.get("model"), reasoning.get("effort"))
            if (
                request.get("api") == "responses"
                and request.get("turn") == 1
                and record.get("classification") == "response_completed"
                and key in expected
            ):
                sources[key] = record
        missing_sources = [key for key in expected if key not in sources]
        if missing_sources:
            raise ProbeError(
                f"Recovery checkpoint is missing successful turn ones: {missing_sources}"
            )
        completed_sources = {
            record.get("recovery", {}).get("source_attempt_number")
            for record in self.records
            if isinstance(record.get("recovery"), dict)
            and record.get("round_trip_result") is not None
        }
        remaining = [
            key
            for key in expected
            if sources[key].get("attempt_number") not in completed_sources
        ]
        chat_done = any(
            (record.get("request") or {}).get("api") == "chat"
            and (record.get("request") or {}).get("model") == GPT55_MODEL
            and record.get("chat_contract_result") is not None
            for record in self.records
        )
        planned_remaining = len(remaining) + int(not chat_done)
        if self.ledger.requests + planned_remaining > MAX_REQUESTS:
            raise ProbeError("Recovery plan would exceed the original request ceiling")

        try:
            # Preserve mandatory GPT-5.5 Responses evidence first, then run
            # reasoning-bearing replays. A known missing-reasoning rejection
            # is recorded but does not masquerade as a new systemic failure.
            remaining.sort(
                key=lambda key: (
                    self._checkpoint_function_call(sources[key])[1] > 0,
                    expected.index(key),
                )
            )
            for key in remaining:
                self.resume_round_trip(sources[key])
            # The GPT-5.6 Chat check is already conclusive. Keep the remaining
            # Chat family diagnostic last so its expected 400 cannot prime a
            # Responses continuation.
            if not chat_done:
                self.run_chat_check(GPT55_MODEL, "medium")
        except (PlannedBudgetStop, SystemicProbeStop):
            return

    def run_chat_check(self, model: str, effort: str) -> None:
        try:
            response, record = self.chat_attempt(model=model, effort=effort, retry=False)
        except BudgetExceeded as exc:
            self.budget_blocked_record(
                api="chat",
                model=model,
                effort=effort,
                turn=1,
                max_output_tokens=INITIAL_MAX_OUTPUT_TOKENS,
                input_token_reservation=INPUT_TOKEN_RESERVATION,
                retry=False,
                error=exc,
            )
            self.stop_reason = f"planned_request_budget_blocked:{model}:{effort}:chat"
            self.checkpoint()
            raise PlannedBudgetStop(self.stop_reason) from exc
        if response is None and self._needs_transient_retry(record):
            time.sleep(2.0)
            try:
                response, record = self.chat_attempt(model=model, effort=effort, retry=True)
            except BudgetExceeded as exc:
                response = None
                record = self.budget_blocked_record(
                    api="chat",
                    model=model,
                    effort=effort,
                    turn=1,
                    max_output_tokens=INITIAL_MAX_OUTPUT_TOKENS,
                    input_token_reservation=INPUT_TOKEN_RESERVATION,
                    retry=True,
                    error=exc,
                )
        if response is None:
            record["chat_contract_result"] = record["classification"]
            self.checkpoint()
            return
        choices = get_attr(response, "choices") or []
        tool_calls = get_attr(get_attr(choices[0], "message"), "tool_calls") if choices else []
        record["chat_contract_result"] = "accepted_with_tool_call" if tool_calls else "accepted_without_tool_call"
        self.checkpoint()

    def run(self) -> None:
        try:
            for model in GPT56_MODELS:
                for effort in ("low", "max"):
                    self.run_round_trip(model, effort)
            self.run_round_trip(GPT55_MODEL, "medium")
            self.run_chat_check("gpt-5.6-luna", "low")
            self.run_chat_check(GPT55_MODEL, "medium")
        except (PlannedBudgetStop, SystemicProbeStop):
            return


def limits_payload() -> dict[str, Any]:
    return {
        "initial_max_output_tokens": INITIAL_MAX_OUTPUT_TOKENS,
        "escalated_max_output_tokens": ESCALATED_MAX_OUTPUT_TOKENS,
        "input_token_reservation_per_request": INPUT_TOKEN_RESERVATION,
        "request_timeout_secs": REQUEST_TIMEOUT_SECS,
        "max_requests": MAX_REQUESTS,
        "max_retry_requests": MAX_RETRY_REQUESTS,
        "max_accounted_tokens": MAX_ACCOUNTED_TOKENS,
        "max_accounted_usd": MAX_ACCOUNTED_USD,
        "max_wall_secs": MAX_WALL_SECS,
    }


def dry_run_payload() -> dict[str, Any]:
    return {
        "network": False,
        "openai_sdk_expected": EXPECTED_OPENAI_SDK,
        "openai_sdk_installed": installed_sdk_version(),
        "approval_token": approval_token(),
        "budget_fingerprint": budget_fingerprint(),
        "limits": limits_payload(),
        "planned_worst_case": planned_worst_case(),
        "planned_calls": [asdict(call) for call in planned_calls()],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Perform the bounded live probe")
    parser.add_argument(
        "--approval-token",
        default="",
        help="Required exact acknowledgement token for live execution",
    )
    parser.add_argument(
        "--resume-after-contract-fix",
        action="store_true",
        help="Resume the sanitized checkpoint within the original hard ceilings",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sdk_version = installed_sdk_version()
    if sdk_version != EXPECTED_OPENAI_SDK:
        raise ProbeError(
            f"OpenAI SDK mismatch: expected {EXPECTED_OPENAI_SDK}, installed {sdk_version}"
        )
    if not args.execute:
        print(json.dumps(dry_run_payload(), indent=2, sort_keys=True))
        return 0
    if args.approval_token != approval_token():
        raise ProbeError(
            "Live execution requires the exact approval token printed by the dry run"
        )
    worst = planned_worst_case()
    if worst["requests_total"] > MAX_REQUESTS:
        raise ProbeError("internal request plan exceeds hard request ceiling")
    if worst["tokens"] > MAX_ACCOUNTED_TOKENS:
        raise ProbeError("internal request plan exceeds hard token ceiling")
    if worst["usd"] > MAX_ACCOUNTED_USD:
        raise ProbeError("internal request plan exceeds hard cost ceiling")
    if worst["wall_secs"] > MAX_WALL_SECS:
        raise ProbeError("internal request plan exceeds hard wall-time ceiling")
    client = OpenAI(
        api_key=read_env_key(),
        timeout=REQUEST_TIMEOUT_SECS,
        max_retries=0,
    )
    if args.resume_after_contract_fix:
        runner = ProbeRunner.from_checkpoint(client)
        runner.checkpoint()
        runner.resume_after_contract_fix()
    else:
        if OUTPUT_JSON.exists():
            raise ProbeError(
                "Live checkpoint already exists; use --resume-after-contract-fix instead of overwriting it"
            )
        runner = ProbeRunner(client)
        runner.checkpoint()
        runner.run()
    runner.checkpoint()
    print(f"WROTE {OUTPUT_JSON}")
    print(f"LEDGER {json.dumps(runner.ledger.snapshot(), sort_keys=True)}")
    if runner.stop_reason:
        print(f"STOP_REASON={runner.stop_reason}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeError as exc:
        print(f"PROBE_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
