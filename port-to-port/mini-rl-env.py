#!/usr/bin/env python3
"""Standalone mini RL benchmark harness using native Pipecat function calling."""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.parse
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any, Optional

from loguru import logger
import openai
from pipecat.frames.frames import (
    EndFrame,
    FunctionCallResultFrame,
    FunctionCallResultProperties,
    FunctionCallsStartedFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMMessagesAppendFrame,
    LLMRunFrame,
    LLMTextFrame,
    LLMThoughtTextFrame,
    MetricsFrame,
)
from pipecat.metrics.metrics import LLMTokenUsage, LLMUsageMetricsData, TTFBMetricsData
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext, LLMSpecificMessage
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.llm_service import FunctionCallParams, LLMService


def _find_repo_root(start_dir: Path) -> Path:
    for candidate in [start_dir, *start_dir.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start_dir


HARNESS_DIR = Path(__file__).resolve().parent
REPO_ROOT = _find_repo_root(HARNESS_DIR)

from llm_factory import (  # noqa: E402
    LLMProvider,
    LLMServiceConfig,
    _is_gpt56_responses_model,
    create_llm_service,
)
from report_contract import (  # noqa: E402
    MEGA_PORT_NAME,
    is_coherent_finished_report as _is_coherent_finished_report,
)

from synthetic_world import (  # noqa: E402
    MEGA_PORT_SECTOR,
    EventPlan,
    SyntheticWorld,
    classify_result_status,
    serialize_response_data,
)
from taskagent_event_summaries import TaskAgentEventSummaries  # noqa: E402
from tool_catalog import (  # noqa: E402
    BENCHMARK_ASYNC_TOOL_COMPLETIONS,
    BENCHMARK_SYNC_TOOL_EVENTS,
    assert_catalog_parity,
    build_tools_schema,
)


DEFAULT_TASK_VARIANT = "natural"
TASK_PROMPTS: dict[str, dict[str, str]] = {
    "natural": {
        "version": "v1",
        "text": (
            "Go round-trip from our current location to the nearest mega-port. "
            "At the mega-port, recharge to full warp power. "
            "While traveling there and back, make as much money as possible by trading optimally "
            "at profitable ports on your route without going off-course. "
            "When you're back where you started, give me a quick summary with the mega-port you used, "
            "how much warp you recharged and what it cost, how many distinct ports you traded at, "
            "and total profit or loss from the whole trip."
        ),
    },
    "literal": {
        "version": "v7",
        "text": (
            "Use this procedure exactly.\n"
            "1. Mission priority:\n"
            "   - reach the nearest mega-port that is not your current sector\n"
            "   - recharge to full there\n"
            "   - return to your starting sector\n"
            "   - only then call `finished`\n"
            "2. Response rule:\n"
            "   - every response must contain exactly one tool call\n"
            "   - do not output explanation text, JSON snippets, pseudo-calls, or thoughts\n"
            "   - if you know the next action, call the tool immediately\n"
            "3. Trading rule:\n"
            "   - a profitable sale means the current port pays more credits than you paid for that cargo\n"
            "   - a profitable buy means the current port sells a commodity for fewer credits than a later port on your already plotted route pays for it\n"
            "   - treat cargo already in your hold at the start of the run as having cost 0, so any positive sale price is profitable\n"
            "   - only free hold space by making profitable sales\n"
            "   - do not make an unprofitable sale and do not use `dump_cargo` just to create empty holds for a later buy\n"
            "   - if your holds are empty and the current port has a profitable buy on the plotted route, take that buy before moving\n"
            "   - do not skip an available profitable buy just because moving is also allowed\n"
            "   - if a port is both a profitable sell and a profitable buy, do the profitable sell first, then use the next turn for the profitable buy if hold space is available\n"
            "4. Outbound setup:\n"
            "   - identify the nearest mega-port that is not your current sector\n"
            "   - plot a route to it\n"
            "5. Outbound policy: repeat until you arrive at the mega-port:\n"
            "   - if the current sector has no port, move to the next sector on the plotted route\n"
            "   - otherwise, if the port pays more for cargo you carry than you paid for it, sell that cargo\n"
            "   - otherwise, if this port sells a commodity and a later port on the already plotted route pays more for that commodity, buy that commodity\n"
            "   - otherwise, move to the next sector on the plotted route\n"
            "   - if you were already at this same port on the previous turn and no successful trade happened there, move to the next sector on the plotted route\n"
            "6. Mega-port policy:\n"
            "   - recharge to full immediately when you arrive\n"
            "   - then plot a route back to your starting sector\n"
            "   - if you already have empty holds and the plotted return route has a later buyer that pays more, take exactly one profitable buy turn at the mega-port before leaving\n"
            "   - after that one trade turn, leave the mega-port by moving to the next sector on the plotted return route\n"
            "7. Return policy:\n"
            "   - if the current sector is not your starting sector, do not call `finished`\n"
            "   - if the current sector has no profitable sale or profitable buy on the plotted return route right now, move to the next sector on the plotted return route\n"
            "   - if a trade attempt failed on the previous turn at this port, move on this turn\n"
            "   - otherwise, repeat the same sell/buy/move policy on the plotted return route until you reach your starting sector\n"
            "8. Starting-sector finish rule:\n"
            "   - when you are back at your starting sector, first sell any profitable cargo there\n"
            "   - do not buy new cargo at your starting sector on the return leg\n"
            "   - when no profitable sale remains at your starting sector, call `finished` immediately\n"
            "9. `finished` message requirements:\n"
            "   - which mega-port you used\n"
            "   - how much warp you recharged\n"
            "   - the recharge cost\n"
            "   - how many distinct ports you traded at\n"
            "   - the total profit or loss from the whole trip"
        ),
    },
}
DEFAULT_BENCHMARK_TASK = TASK_PROMPTS[DEFAULT_TASK_VARIANT]["text"]

RUN_SCHEMA_VERSION = "mini_rl_run.v3"
REPLAY_STREAM_SCHEMA_VERSION = "mini_rl_replay_stream.v1"
RUNNER_VERSION = "2026-07-17-gpt56-aiewf-responses-v3"
ASYNC_COMPLETION_TIMEOUT = 5.0
MAX_NO_TOOL_NUDGES = 3
NO_TOOL_WATCHDOG_DELAY = 5.0
EVENT_BATCH_INFERENCE_DELAY = 1.0
MAX_TRANSPORT_EMPTY_RETRIES = 2
BASETEN_RATE_LIMIT_MAX_ATTEMPTS = 5
BASETEN_RATE_LIMIT_BACKOFF_BASE_SECS = 2.0
BASETEN_RATE_LIMIT_BACKOFF_FACTOR = 2.0
BASETEN_RATE_LIMIT_BACKOFF_MAX_SECS = 30.0
PIPELINE_GRACEFUL_SHUTDOWN_TIMEOUT = 3.0
GPT56_PIPELINE_IDLE_GRACE_SECS = 30.0
THINKING_LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh")
GPT56_REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
THINKING_BUDGET_MAP = {"minimal": 0, "low": 128, "medium": 512, "high": 2048}
ANTHROPIC_HAIKU_THINKING_BUDGET_MAP = {"low": 1024, "medium": 2048, "high": 4096}
GEMINI_25_FLASH_THINKING_BUDGET_MAP = {"low": 1024, "medium": 2048, "high": 4096}
GOOGLE_THINKING_LEVEL_MODEL_PREFIXES = ("gemini-3", "supernova")
CONTROL_TOKEN_REPLAY_PATTERNS = (
    re.compile(r"<\|start\|>assistant<\|channel\|>[A-Za-z_]+"),
    re.compile(r"<\|start\|>assistant"),
    re.compile(r"<\|channel\|>[A-Za-z_]+"),
    re.compile(r"<\|(?:start|end|channel)\|>"),
)


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_task_prompt(
    *,
    task: Optional[str],
    task_variant: str,
) -> tuple[str, str, Optional[str]]:
    if task:
        return task, "custom", None
    prompt = TASK_PROMPTS.get(task_variant)
    if prompt is None:
        raise ValueError(f"Unsupported task variant: {task_variant}")
    return prompt["text"], task_variant, prompt["version"]


def _leaderboard_prompt_id_for_task(*, task_variant: str, task: str) -> str:
    if task_variant in TASK_PROMPTS:
        return task_variant
    return f"custom:{_sha256_text(task)}"


def _git_sha(repo_root: Path) -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _provider_from_str(provider: str) -> LLMProvider:
    normalized = provider.strip().lower()
    if normalized == "openai":
        return LLMProvider.OPENAI
    if normalized == "google":
        return LLMProvider.GOOGLE
    if normalized == "anthropic":
        return LLMProvider.ANTHROPIC
    if normalized == "cerebras":
        return LLMProvider.CEREBRAS
    raise ValueError(f"Unsupported provider: {provider}")


def _is_google_thinking_level_model(model_lower: str) -> bool:
    normalized = model_lower.strip().lower()
    return any(normalized.startswith(prefix) for prefix in GOOGLE_THINKING_LEVEL_MODEL_PREFIXES)


def _is_nemotron_model(model_lower: str) -> bool:
    normalized = model_lower.strip().lower()
    return normalized.startswith("nemotron") or normalized.startswith("nvidia/nemotron")


def _is_qwen35_model(model_lower: str) -> bool:
    normalized = model_lower.strip().lower()
    return "qwen3.5" in normalized or "qwen-3.5" in normalized


def _is_glm_sglang_binary_reasoning_model(model_lower: str) -> bool:
    normalized = model_lower.strip().lower()
    return (
        normalized.startswith("glm-4.7")
        or normalized.startswith("glm4.7")
        or normalized.startswith("glm-5")
        or normalized.startswith("glm5")
    )


QWEN35_BINARY_REASONING_HOSTS = {
    "daily--qwen35-4b-b200-sglang-serve.modal.run",
    "daily--qwen35-sglang-serve-4b.modal.run",
    "daily--qwen35-sglang-serve-27b.modal.run",
    "daily--qwen35-sglang-serve-35b.modal.run",
}


def _is_qwen35_default_only_endpoint(openai_base_url: Optional[str]) -> bool:
    if not openai_base_url:
        return False

    parsed = urllib.parse.urlparse(openai_base_url)
    host = parsed.netloc.lower()
    if host in QWEN35_BINARY_REASONING_HOSTS:
        return False
    if host.startswith("daily--qwen35-vllm-017-") and host.endswith(".modal.run"):
        return True
    return host.startswith("daily--qwen35-") and "sglang-serve" in host and host.endswith(".modal.run")


def _is_nemotron_vllm_017_default_only_endpoint(openai_base_url: Optional[str]) -> bool:
    if not openai_base_url:
        return False

    parsed = urllib.parse.urlparse(openai_base_url)
    host = parsed.netloc.lower()
    return (
        "nemotron-vllm-017" in host or ("nemotron" in host and "vllm017" in host)
    ) and host.endswith(".modal.run")


def _is_baseten_endpoint(openai_base_url: Optional[str]) -> bool:
    if not openai_base_url:
        return False

    parsed = urllib.parse.urlparse(openai_base_url)
    host = parsed.netloc.lower()
    return host == "inference.baseten.co" or host.endswith(".baseten.co")


def _is_openrouter_laguna_model(
    openai_base_url: Optional[str], model: str
) -> bool:
    if not openai_base_url:
        return False
    parsed = urllib.parse.urlparse(openai_base_url)
    normalized_model = model.strip().lower()
    return (parsed.hostname or "").lower() in {
        "openrouter.ai",
        "www.openrouter.ai",
    } and normalized_model in {
        "poolside/laguna-s-2.1",
        "poolside/laguna-s-2.1-20260720",
    }


def _is_openrouter_qwen36_model(
    openai_base_url: Optional[str], model: str
) -> bool:
    if not openai_base_url:
        return False
    parsed = urllib.parse.urlparse(openai_base_url)
    normalized_model = model.strip().lower()
    return (parsed.hostname or "").lower() in {
        "openrouter.ai",
        "www.openrouter.ai",
    } and normalized_model.startswith("qwen/qwen3.6-")


def _is_baseten_qwen36_model(
    openai_base_url: Optional[str], model: str
) -> bool:
    if not openai_base_url:
        return False
    parsed = urllib.parse.urlparse(openai_base_url)
    normalized_model = model.strip().lower()
    return (parsed.hostname or "").lower().endswith(
        ".baseten.co"
    ) and normalized_model in {
        "qwen/qwen3.6-27b",
        "qwen/qwen3.6-35b-a3b-fp8",
    }


def _is_baseten_gemma4_model(
    openai_base_url: Optional[str], model: str
) -> bool:
    if not openai_base_url:
        return False
    parsed = urllib.parse.urlparse(openai_base_url)
    normalized_model = model.strip().lower()
    return (parsed.hostname or "").lower().endswith(
        ".baseten.co"
    ) and normalized_model == "google/gemma-4-26b-a4b-it"


def _is_baseten_inkling_model(model_lower: str) -> bool:
    normalized = (model_lower or "").strip().lower()
    return normalized in {"inkling", "thinkingmachines/inkling"}


def _is_baseten_retry_eligible_model(model: str) -> bool:
    normalized = (model or "").strip().lower()
    return (
        "glm-5" in normalized
        or "glm5" in normalized
        or "nemotron-3-ultra" in normalized
        or _is_baseten_inkling_model(normalized)
    )


def _baseten_transport_retry_enabled(
    openai_base_url: Optional[str], model: str
) -> bool:
    return _is_baseten_endpoint(openai_base_url) and _is_baseten_retry_eligible_model(
        model
    )


def _is_baseten_glm_reasoning_model(model_lower: str) -> bool:
    normalized = model_lower.strip().lower()
    return "glm-5" in normalized or "glm5" in normalized


def _baseten_reasoning_effort(thinking: str) -> str:
    # Baseten Model APIs accept OpenAI-style reasoning.effort (none|minimal|low|
    # medium|high). "none" disables reasoning; any other level enables it. Some
    # models are effectively binary on this stack, so minimal..high may behave
    # the same for them. GLM-5.2 on Baseten is handled by the GLM-specific mapper.
    normalized = _normalize_benchmark_thinking_level(thinking)
    if normalized == "none":
        return "none"
    if normalized == "xhigh":
        return "high"
    return normalized


def _baseten_glm_reasoning_effort(thinking: str) -> str:
    normalized = thinking.strip().lower()
    if normalized == "none":
        return "none"
    if normalized == "high":
        return "high"
    if normalized == "xhigh":
        return "max"
    raise ValueError(
        "GLM-5.2 on Baseten supports only benchmark thinking none/high/xhigh "
        "(xhigh maps to reasoning.effort=max)."
    )


def _baseten_inkling_reasoning_effort(thinking: str) -> str:
    requested = thinking.strip().lower()
    normalized = _normalize_benchmark_thinking_level(requested)
    # The generic normalizer aliases minimal to none for budget-based models,
    # while Inkling exposes minimal as a distinct native API value.
    if requested == "minimal":
        normalized = "minimal"
    effort_by_level = {
        "none": "none",
        "minimal": "minimal",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "xhigh": "max",
    }
    try:
        return effort_by_level[normalized]
    except KeyError as exc:
        raise ValueError(
            "Inkling on Baseten supports benchmark thinking "
            "none/minimal/low/medium/high/xhigh "
            "(xhigh maps to reasoning_effort=max)."
        ) from exc


def _sanitize_assistant_replay_text(text: str) -> str:
    sanitized = text
    for pattern in CONTROL_TOKEN_REPLAY_PATTERNS:
        sanitized = pattern.sub(" ", sanitized)
    sanitized = re.sub(r"[ \t]{2,}", " ", sanitized)
    return sanitized


def _is_gpt_oss_model(model_lower: str) -> bool:
    normalized = model_lower.strip().lower()
    return normalized.startswith("gpt-oss")


def _gpt_oss_reasoning_level(thinking: str) -> str:
    # gpt-oss endpoints accept "Reasoning: <level>" style control in system messages.
    # There is no known "none/disabled" mode, so map benchmark none/minimal to low.
    if thinking in {"none", "minimal", "low"}:
        return "low"
    if thinking in {"medium", "high"}:
        return thinking
    raise ValueError(f"Unsupported thinking level for gpt-oss model: {thinking}")


def _system_reasoning_prefix_for_model(
    *,
    provider: LLMProvider,
    model: str,
    thinking: str,
    openai_base_url: Optional[str],
) -> Optional[str]:
    if provider != LLMProvider.OPENAI or not openai_base_url:
        return None

    model_lower = model.strip().lower()
    if _is_gpt_oss_model(model_lower):
        level = _gpt_oss_reasoning_level(thinking)
        return f"Reasoning: {level}"

    return None


def _apply_openai_non_streaming_tool_call_workaround(
    *,
    llm_service: LLMService,
    provider: LLMProvider,
    model: str,
    openai_base_url: Optional[str],
) -> str:
    """Work around streamed tool-call argument loss for some OpenAI-compatible endpoints.

    Some servers emit incomplete/empty function arguments while streaming tool calls.
    We request non-streaming chat completions and adapt them into chunk-like objects so
    Pipecat's function-call pipeline can remain unchanged.
    """
    if provider != LLMProvider.OPENAI or not openai_base_url:
        return "disabled"

    model_lower = model.strip().lower()
    if not _is_gpt_oss_model(model_lower):
        return "disabled"

    original = getattr(llm_service, "get_chat_completions", None)
    if not callable(original):
        logger.warning("OpenAI non-streaming workaround unavailable: get_chat_completions missing.")
        return "unavailable"

    async def _patched_get_chat_completions(self: Any, params_from_context: Any) -> Any:
        params = self.build_chat_completion_params(params_from_context)
        params["stream"] = False
        params.pop("stream_options", None)

        response = await self._client.chat.completions.create(**params)
        choices = getattr(response, "choices", None) or []
        choice0 = choices[0] if choices else None
        message = getattr(choice0, "message", None)
        usage = getattr(response, "usage", None)
        model_name = getattr(response, "model", None)

        async def _iter_chunks() -> Any:
            if message is None:
                return

            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                for fallback_idx, call in enumerate(tool_calls):
                    function = getattr(call, "function", None)
                    index = getattr(call, "index", None)
                    yield SimpleNamespace(
                        usage=usage if fallback_idx == 0 else None,
                        model=model_name if fallback_idx == 0 else None,
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content=None,
                                    tool_calls=[
                                        SimpleNamespace(
                                            index=fallback_idx if index is None else index,
                                            id=getattr(call, "id", ""),
                                            function=SimpleNamespace(
                                                name=getattr(function, "name", "") if function else "",
                                                arguments=getattr(function, "arguments", "")
                                                if function
                                                else "",
                                            ),
                                        )
                                    ]
                                )
                            )
                        ],
                    )

            content = getattr(message, "content", None)
            if content:
                yield SimpleNamespace(
                    usage=None,
                    model=model_name,
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=None))],
                )

        return _iter_chunks()

    llm_service.get_chat_completions = MethodType(_patched_get_chat_completions, llm_service)
    return "enabled"


def _openai_error_status_code(exc: BaseException) -> Optional[int]:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status
    return None


def _is_openai_rate_limit_error(exc: BaseException) -> bool:
    return isinstance(exc, openai.RateLimitError) or (
        isinstance(exc, openai.APIStatusError) and _openai_error_status_code(exc) == 429
    )


def _retry_after_seconds_from_error(exc: BaseException) -> Optional[float]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None

    raw_retry_after = None
    get_header = getattr(headers, "get", None)
    if callable(get_header):
        raw_retry_after = get_header("retry-after")
    if raw_retry_after is None:
        return None

    retry_after_text = str(raw_retry_after).strip()
    if not retry_after_text:
        return None

    try:
        return max(0.0, float(retry_after_text))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(retry_after_text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def _baseten_rate_limit_backoff_seconds(exc: BaseException, *, failed_attempt: int) -> float:
    retry_after = _retry_after_seconds_from_error(exc)
    if retry_after is not None:
        return min(retry_after, BASETEN_RATE_LIMIT_BACKOFF_MAX_SECS)

    exponent = max(0, failed_attempt - 1)
    base_delay = BASETEN_RATE_LIMIT_BACKOFF_BASE_SECS * (
        BASETEN_RATE_LIMIT_BACKOFF_FACTOR**exponent
    )
    capped_delay = min(base_delay, BASETEN_RATE_LIMIT_BACKOFF_MAX_SECS)
    jitter = random.uniform(0.0, min(1.0, capped_delay * 0.25))
    return min(capped_delay + jitter, BASETEN_RATE_LIMIT_BACKOFF_MAX_SECS)


async def _sleep_for_rate_limit_backoff(delay_seconds: float) -> None:
    await asyncio.sleep(delay_seconds)


def _runtime_turn_for_rate_limit_log(runtime: Any) -> int:
    turn_count = getattr(runtime, "turn_count", 0)
    return int(turn_count) + 1 if isinstance(turn_count, int) else 1


def _record_baseten_rate_limit_event(
    runtime: Any,
    *,
    failed_attempt: int,
    backoff_s: float,
    exhausted: bool,
) -> None:
    runtime.rate_limit_count = getattr(runtime, "rate_limit_count", 0) + 1
    logger.warning(
        "RATE_LIMIT_429 ts={} turn={} attempt={} backoff_s={:.3f} max_attempts={} exhausted={}",
        _iso_utc_now(),
        _runtime_turn_for_rate_limit_log(runtime),
        failed_attempt,
        backoff_s,
        BASETEN_RATE_LIMIT_MAX_ATTEMPTS,
        exhausted,
    )


def _record_baseten_rate_limit_retry_success(runtime: Any, *, recovered_attempt: int) -> None:
    runtime.rate_limit_retry_success_count = (
        getattr(runtime, "rate_limit_retry_success_count", 0) + 1
    )
    logger.info(
        "RATE_LIMIT_RETRY_SUCCESS ts={} turn={} attempts={}",
        _iso_utc_now(),
        _runtime_turn_for_rate_limit_log(runtime),
        recovered_attempt,
    )


def _mark_baseten_rate_limit_exhausted(
    runtime: Any,
    *,
    failed_attempt: int,
    exc: BaseException,
) -> None:
    status_code = _openai_error_status_code(exc) or 429
    event = {
        "endpoint": "inference",
        "error_class": "rate_limit_exhausted",
        "error": str(exc),
        "source": {"type": "baseten_rate_limit_retry"},
        "synthesized": True,
        "status": status_code,
        "attempts": failed_attempt,
        "max_attempts": BASETEN_RATE_LIMIT_MAX_ATTEMPTS,
    }
    runtime.rate_limit_exhausted_pending = True
    runtime.rate_limit_exhausted_event = event
    logger.error(
        "RATE_LIMIT_EXHAUSTED ts={} turn={} attempts={} status={}",
        _iso_utc_now(),
        _runtime_turn_for_rate_limit_log(runtime),
        failed_attempt,
        status_code,
    )


def _mark_baseten_api_error(runtime: Any, *, exc: BaseException) -> None:
    status_code = _openai_error_status_code(exc)
    message = str(exc)
    event = {
        "endpoint": "inference",
        "error_class": "api_error",
        "error": message,
        "message": message,
        "source": {"type": "baseten_api_error"},
        "synthesized": True,
        "status": status_code,
        "exception_type": exc.__class__.__name__,
    }
    runtime.api_error_pending = True
    runtime.api_error_event = event
    logger.error(
        "BASETEN_API_ERROR ts={} turn={} status={} exception_type={} message={}",
        _iso_utc_now(),
        _runtime_turn_for_rate_limit_log(runtime),
        status_code if status_code is not None else "(unknown)",
        exc.__class__.__name__,
        message,
    )


def _apply_baseten_rate_limit_retry_wrapper(
    *,
    llm_service: LLMService,
    provider: LLMProvider,
    openai_base_url: Optional[str],
    runtime: Any,
) -> str:
    """Retry Baseten 429s at the OpenAI stream-open boundary before Pipecat sees them."""
    if provider != LLMProvider.OPENAI or not _is_baseten_endpoint(openai_base_url):
        return "disabled"

    if getattr(llm_service, "_baseten_rate_limit_retry_wrapped", False):
        return "already_enabled"

    original = getattr(llm_service, "get_chat_completions", None)
    if not callable(original):
        logger.warning("Baseten rate-limit retry unavailable: get_chat_completions missing.")
        return "unavailable"

    async def _patched_get_chat_completions(self: Any, params_from_context: Any) -> Any:
        attempt = 1
        saw_rate_limit = False
        while True:
            try:
                chunks = await original(params_from_context)
            except openai.APIError as exc:
                if not _is_openai_rate_limit_error(exc):
                    _mark_baseten_api_error(runtime, exc=exc)
                    raise

                saw_rate_limit = True
                exhausted = attempt >= BASETEN_RATE_LIMIT_MAX_ATTEMPTS
                backoff_s = (
                    0.0
                    if exhausted
                    else _baseten_rate_limit_backoff_seconds(exc, failed_attempt=attempt)
                )
                _record_baseten_rate_limit_event(
                    runtime,
                    failed_attempt=attempt,
                    backoff_s=backoff_s,
                    exhausted=exhausted,
                )
                if exhausted:
                    _mark_baseten_rate_limit_exhausted(
                        runtime,
                        failed_attempt=attempt,
                        exc=exc,
                    )
                    raise

                await _sleep_for_rate_limit_backoff(backoff_s)
                attempt += 1
                continue

            if saw_rate_limit:
                _record_baseten_rate_limit_retry_success(runtime, recovered_attempt=attempt)
            return chunks

    llm_service.get_chat_completions = MethodType(_patched_get_chat_completions, llm_service)
    setattr(llm_service, "_baseten_rate_limit_retry_wrapped", True)
    return "enabled"


def _to_json_compatible(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "_type": "bytes_b64",
            "data": base64.b64encode(bytes(value)).decode("ascii"),
        }

    if isinstance(value, dict):
        return {str(key): _to_json_compatible(val) for key, val in value.items()}

    if isinstance(value, (list, tuple)):
        return [_to_json_compatible(item) for item in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _to_json_compatible(model_dump(exclude_none=False))
        except TypeError:
            return _to_json_compatible(model_dump())
        except Exception:  # noqa: BLE001
            pass

    to_dict = getattr(value, "dict", None)
    if callable(to_dict):
        try:
            return _to_json_compatible(to_dict())
        except Exception:  # noqa: BLE001
            pass

    return repr(value)


def _state_log_label(state: Any) -> str:
    if not isinstance(state, dict):
        return "sector=? credits=? warp=?/?"

    sector = state.get("sector", "?")
    credits = state.get("credits", "?")
    warp = state.get("warp", "?")
    max_warp = state.get("max_warp", "?")
    return f"sector={sector} credits={credits} warp={warp}/{max_warp}"


def _tool_calls_log_label(tool_calls: list[dict[str, Any]]) -> str:
    if not tool_calls:
        return "none"

    return ", ".join(
        f"{str(call.get('name') or 'unknown')}:{str(call.get('result_status') or 'unknown')}"
        for call in tool_calls
    )


def _serialize_llm_usage_metrics(metric_data: LLMUsageMetricsData) -> dict[str, Any]:
    value = metric_data.value
    payload: dict[str, Any] = {
        "prompt_tokens": int(value.prompt_tokens),
        "completion_tokens": int(value.completion_tokens),
        "total_tokens": int(value.total_tokens),
    }
    for field in ("cache_read_input_tokens", "cache_creation_input_tokens", "reasoning_tokens"):
        metric_value = getattr(value, field, None)
        if metric_value is not None:
            payload[field] = int(metric_value)
    if metric_data.processor:
        payload["processor"] = metric_data.processor
    if metric_data.model:
        payload["model"] = metric_data.model
    return payload


def _usage_entry_from_metrics_frame(frame: MetricsFrame) -> Optional[dict[str, Any]]:
    usage_entry: Optional[dict[str, Any]] = None
    for metric_data in frame.data:
        if not isinstance(metric_data, LLMUsageMetricsData):
            continue
        serialized = _serialize_llm_usage_metrics(metric_data)
        if usage_entry is None:
            usage_entry = serialized
        else:
            usage_entry.update(serialized)
    return usage_entry


def _ttfb_entry_from_metrics_frame(frame: MetricsFrame) -> Optional[dict[str, Any]]:
    ttfb_entry: Optional[dict[str, Any]] = None
    for metric_data in frame.data:
        if not isinstance(metric_data, TTFBMetricsData):
            continue
        value = float(metric_data.value)
        if value <= 0:
            continue
        serialized: dict[str, Any] = {"ttfb_ms": round(value * 1000.0, 2)}
        if metric_data.processor:
            serialized["processor"] = metric_data.processor
        if metric_data.model:
            serialized["model"] = metric_data.model
        if ttfb_entry is None:
            ttfb_entry = serialized
        else:
            ttfb_entry.update(serialized)
    return ttfb_entry


def _serialize_context_message(message: Any) -> Any:
    if isinstance(message, LLMSpecificMessage):
        return {
            "_type": "llm_specific",
            "llm": message.llm,
            "message": _to_json_compatible(message.message),
        }

    return _to_json_compatible(message)


def _message_content_has_meaningful_payload(content: Any) -> bool:
    if content is None:
        return False
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(_message_content_has_meaningful_payload(item) for item in content)
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            if text.strip():
                return True
            return any(
                _message_content_has_meaningful_payload(value)
                for key, value in content.items()
                if key not in {"type", "text"} and value is not None
            )

        refusal = content.get("refusal")
        if isinstance(refusal, str):
            if refusal.strip():
                return True
            return any(
                _message_content_has_meaningful_payload(value)
                for key, value in content.items()
                if key not in {"type", "refusal"} and value is not None
            )

        return any(
            _message_content_has_meaningful_payload(value)
            for key, value in content.items()
            if key != "type" and value is not None
        )

    return True


def _is_empty_assistant_context_message(message: Any) -> bool:
    payload = message.message if isinstance(message, LLMSpecificMessage) else message
    if not isinstance(payload, dict):
        return False
    if payload.get("role") != "assistant":
        return False
    if payload.get("tool_calls") or payload.get("function_call"):
        return False

    allowed_keys = {"role", "content", "name", "tool_calls", "function_call"}
    if any(key not in allowed_keys for key in payload):
        return False

    return not _message_content_has_meaningful_payload(payload.get("content"))


def _prune_empty_assistant_context_messages(context: Optional[LLMContext]) -> int:
    if context is None:
        return 0

    messages = list(context.get_messages())
    filtered_messages = [
        message for message in messages if not _is_empty_assistant_context_message(message)
    ]
    dropped = len(messages) - len(filtered_messages)
    if dropped:
        context.set_messages(filtered_messages)
    return dropped


def _normalize_benchmark_thinking_level(thinking: str) -> str:
    return "none" if thinking == "minimal" else thinking


def _mapped_budget_for_thinking(
    thinking: str,
    *,
    budget_map: dict[str, int],
) -> int:
    normalized = _normalize_benchmark_thinking_level(thinking)
    if normalized == "none":
        return 0
    return budget_map[normalized]


def _default_thinking_level() -> str:
    explicit = os.getenv("TASK_LLM_THINKING")
    if explicit:
        normalized = explicit.strip().lower()
        if normalized in THINKING_LEVELS:
            return normalized
        logger.warning("Unknown TASK_LLM_THINKING='{}'; falling back to 'high'.", explicit)
        return "high"

    return "high"


def _parse_optional_json_dict(raw: Optional[str], *, label: str) -> Optional[dict[str, Any]]:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return parsed


def _parse_optional_nonnegative_int(raw: Optional[str], *, label: str) -> Optional[int]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be a non-negative integer.") from exc
    if value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return value


def _resolve_gpt56_effective_effort(
    *,
    model: str,
    openai_base_url: Optional[str],
    thinking: str,
    reasoning_effort: Optional[str],
) -> Optional[str]:
    if not _is_gpt56_responses_model(model, openai_base_url):
        return None
    if reasoning_effort is not None:
        return reasoning_effort
    normalized = _normalize_benchmark_thinking_level(thinking)
    return "low" if normalized == "minimal" else normalized


def _resolve_gpt56_pipeline_idle_timeout_secs(args: argparse.Namespace) -> Optional[float]:
    if not _is_gpt56_responses_model(
        str(getattr(args, "model", "")), getattr(args, "openai_base_url", None)
    ):
        return None
    request_timeout = float(getattr(args, "llm_request_timeout_secs", 900.0) or 900.0)
    stream_idle_timeout = float(
        getattr(args, "llm_stream_idle_timeout_secs", 600.0) or 600.0
    )
    # The pipeline watchdog observes emitted Pipecat frames, not raw Responses
    # events. It must remain a fallback after both provider-I/O controls so a
    # long silent reasoning turn cannot cancel the pipeline while the service
    # is still blocked inside the stream iterator.
    return max(request_timeout, stream_idle_timeout) + GPT56_PIPELINE_IDLE_GRACE_SECS


def _validate_generation_controls(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    model = str(getattr(args, "model", ""))
    provider = getattr(args, "provider", None)
    openai_base_url = getattr(args, "openai_base_url", None)
    model_lower = model.strip().lower()
    thinking_budget = getattr(args, "thinking_budget", None)
    openai_no_budget_thinking_toggle = bool(getattr(args, "openai_no_budget_thinking_toggle", False))
    reasoning_effort = getattr(args, "reasoning_effort", None)
    round_id = getattr(args, "round_id", None)
    request_timeout = getattr(args, "llm_request_timeout_secs", None)
    stream_idle_timeout = getattr(args, "llm_stream_idle_timeout_secs", None)

    for label, value in (
        ("--llm-request-timeout-secs", request_timeout),
        ("--llm-stream-idle-timeout-secs", stream_idle_timeout),
    ):
        if value is not None and value <= 0:
            parser.error(f"{label} must be greater than zero.")
    if round_id is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", round_id):
        parser.error(
            "--round-id must be 1-64 characters using only letters, digits, '.', '_', or '-'."
        )

    if reasoning_effort is not None:
        if provider != "openai" or not _is_gpt56_responses_model(model, openai_base_url):
            parser.error(
                "--reasoning-effort is valid only for provider openai, an exact hosted "
                "GPT-5.6 model (luna/sol/terra), and the default OpenAI base URL."
            )
        if reasoning_effort not in GPT56_REASONING_EFFORTS:
            parser.error(
                "--reasoning-effort must be one of: " + ", ".join(GPT56_REASONING_EFFORTS)
            )
        if thinking_budget is not None:
            parser.error("GPT-5.6 --reasoning-effort cannot be combined with --thinking-budget.")
        native_effort = _resolve_gpt56_effective_effort(
            model=model,
            openai_base_url=openai_base_url,
            thinking=getattr(args, "thinking", "high"),
            reasoning_effort=None,
        )
        if reasoning_effort == native_effort:
            parser.error(
                "--reasoning-effort duplicates the native --thinking mapping; "
                "omit the redundant override."
            )

    if _is_gpt56_responses_model(model, openai_base_url):
        openai_params = getattr(args, "openai_params", None)
        if isinstance(openai_params, dict):
            extra = openai_params.get("extra")
            if "service_tier" in openai_params or (
                isinstance(extra, dict) and "service_tier" in extra
            ):
                parser.error(
                    "GPT-5.6 benchmark requests must omit service_tier; Priority is not allowed."
                )
    elif request_timeout is not None or stream_idle_timeout is not None:
        parser.error(
            "--llm-request-timeout-secs and --llm-stream-idle-timeout-secs are valid "
            "only for the exact hosted GPT-5.6 Responses route."
        )

    if getattr(args, "max_tokens", None) is not None and provider != "openai":
        parser.error("--max-tokens is only supported when --provider openai is selected.")

    if args.provider == "cerebras":
        # Kimi K2.6 is a binary-reasoning model: Thinking (default) or Instant
        # (reasoning_effort="none"). It exposes no exact thinking budget.
        if thinking_budget is not None:
            parser.error(
                "Cerebras Kimi supports benchmark --thinking none|high "
                "(Instant vs Thinking), not exact --thinking-budget."
            )
        if args.thinking not in {"none", "high"}:
            parser.error(
                "For Cerebras Kimi, --thinking must be 'none' (Instant) or "
                "'high' (Thinking)."
            )
        return

    if args.provider == "openai":
        if _is_openrouter_laguna_model(args.openai_base_url, model_lower):
            if args.thinking not in {"none", "high"}:
                parser.error(
                    "Laguna S 2.1 on OpenRouter supports benchmark --thinking "
                    "none|high (thinking disabled or default-enabled)."
                )
            if thinking_budget is not None:
                parser.error(
                    "Laguna S 2.1 on OpenRouter exposes a binary reasoning toggle, "
                    "not an exact --thinking-budget control."
                )
            return

        if _is_openrouter_qwen36_model(args.openai_base_url, model_lower):
            if args.thinking not in {"none", "high"}:
                parser.error(
                    "Qwen 3.6 on OpenRouter supports benchmark --thinking "
                    "none|high (thinking disabled or default-enabled)."
                )
            if thinking_budget is not None:
                parser.error(
                    "Qwen 3.6 on OpenRouter exposes a binary reasoning toggle, "
                    "not an exact --thinking-budget control."
                )
            return

        if _is_baseten_qwen36_model(args.openai_base_url, model_lower):
            if args.thinking not in {"none", "high"}:
                parser.error(
                    "Qwen 3.6 on a dedicated Baseten vLLM endpoint supports "
                    "benchmark --thinking none|high."
                )
            if thinking_budget is not None:
                parser.error(
                    "Qwen 3.6 on a dedicated Baseten vLLM endpoint exposes a "
                    "binary reasoning toggle, not an exact --thinking-budget control."
                )
            return

        if _is_baseten_gemma4_model(args.openai_base_url, model_lower):
            if args.thinking not in {"none", "high"}:
                parser.error(
                    "Gemma 4 on a dedicated Baseten vLLM endpoint supports "
                    "benchmark --thinking none|high."
                )
            if thinking_budget is not None:
                parser.error(
                    "Gemma 4 on a dedicated Baseten vLLM endpoint exposes a "
                    "binary reasoning toggle, not an exact --thinking-budget control."
                )
            return

        if openai_no_budget_thinking_toggle:
            if not args.openai_base_url:
                parser.error(
                    "--openai-no-budget-thinking-toggle requires --openai-base-url for an "
                    "OpenAI-compatible endpoint."
                )
            if not _is_nemotron_model(model_lower):
                parser.error(
                    "--openai-no-budget-thinking-toggle is currently supported only for "
                    "OpenAI-compatible Nemotron endpoints."
                )
            if _is_nemotron_vllm_017_default_only_endpoint(args.openai_base_url):
                parser.error(
                    "This Nemotron vLLM 0.17 endpoint only supports its default reasoning mode; "
                    "--openai-no-budget-thinking-toggle is not applicable."
                )
            if args.thinking not in {"none", "high"}:
                parser.error(
                    "For Nemotron with --openai-no-budget-thinking-toggle, --thinking must be "
                    "'none' (thinking disabled) or 'high' (thinking enabled)."
                )
            if thinking_budget is not None:
                parser.error(
                    "--openai-no-budget-thinking-toggle omits exact reasoning budgets; "
                    "do not pass --thinking-budget."
                )
            return

        if args.openai_base_url and _is_baseten_endpoint(args.openai_base_url):
            # Baseten controls reasoning via reasoning.effort (level-based), not an
            # exact token budget. GLM-5.2 currently exposes only none/high/max.
            if thinking_budget is not None:
                parser.error(
                    "Baseten endpoints control reasoning via reasoning.effort levels; "
                    "use --thinking instead of --thinking-budget."
                )
            if _is_baseten_glm_reasoning_model(model_lower) and args.thinking not in {
                "none",
                "high",
                "xhigh",
            }:
                parser.error(
                    "GLM-5.2 on Baseten supports only --thinking none, high, or xhigh "
                    "(xhigh maps to reasoning.effort=max); low, medium, and minimal "
                    "are rejected by the Baseten API."
                )
            # Inkling intentionally accepts none/minimal/low/medium/high/xhigh with no budget.
            return

        if args.openai_base_url and _is_glm_sglang_binary_reasoning_model(model_lower):
            if args.thinking not in {"none", "high"}:
                parser.error(
                    "GLM on OpenAI-compatible SGLang supports only --thinking "
                    "'none' (thinking disabled) or 'high' (thinking enabled)."
                )
            if thinking_budget is not None:
                parser.error(
                    "GLM on OpenAI-compatible SGLang does not expose an exact "
                    "--thinking-budget control; use --thinking none|high instead."
                )
            return

        if (
            args.openai_base_url
            and _is_nemotron_model(model_lower)
            and _is_nemotron_vllm_017_default_only_endpoint(args.openai_base_url)
        ):
            if args.thinking != "high":
                parser.error(
                    "This Nemotron vLLM 0.17 endpoint only supports its default reasoning mode; "
                    "use the default --thinking high and the harness will send no override."
                )
            if thinking_budget is not None:
                parser.error(
                    "This Nemotron vLLM 0.17 endpoint does not expose an exact --thinking-budget control."
                )
            return

        if args.openai_base_url and _is_qwen35_model(model_lower):
            if _is_qwen35_default_only_endpoint(args.openai_base_url):
                if args.thinking != "high":
                    parser.error(
                        "This Qwen 3.5 endpoint only supports its default reasoning mode; "
                        "use the default --thinking high and the harness will send no override."
                    )
                if thinking_budget is not None:
                    parser.error(
                        "This Qwen 3.5 endpoint does not expose an exact --thinking-budget control."
                    )
                return

            if args.thinking not in {"none", "high"}:
                parser.error(
                    "For Qwen 3.5 on OpenAI-compatible SGLang, --thinking must be 'none' "
                    "(thinking disabled) or 'high' (thinking enabled)."
                )
            if thinking_budget is not None:
                parser.error(
                    "Qwen 3.5 on OpenAI-compatible SGLang does not expose an exact "
                    "--thinking-budget control; use --thinking none|high instead."
                )
            return

        if thinking_budget is None:
            return

        if model_lower.startswith("gpt-5"):
            parser.error("GPT-5 models support benchmark --thinking levels, not exact --thinking-budget.")
        if model_lower.startswith("gpt-4.1"):
            parser.error("GPT-4.1 models do not support exact --thinking-budget in this harness.")
        if args.openai_base_url and _is_gpt_oss_model(model_lower):
            parser.error(
                "gpt-oss endpoints support benchmark --thinking levels via system prompting, "
                "not exact --thinking-budget."
            )
        if not args.openai_base_url:
            parser.error(
                "Hosted OpenAI models in this harness do not support exact --thinking-budget; "
                "use --thinking instead."
            )
        return

    if thinking_budget is None:
        return

    if args.provider == "anthropic" and (
        "claude-opus-4-6" in model_lower
        or "claude-sonnet-4-6" in model_lower
        or "claude-sonnet-5" in model_lower
    ):
        parser.error(
            "Claude Sonnet/Opus adaptive reasoning models support benchmark --thinking levels, "
            "not exact --thinking-budget."
        )

    if args.provider == "google" and _is_google_thinking_level_model(model_lower):
        parser.error(
            "Gemini 3 / Supernova models support benchmark --thinking levels, "
            "not exact --thinking-budget."
        )


def _apply_benchmark_thinking_mode(
    *,
    llm_service: LLMService,
    provider: LLMProvider,
    model: str,
    thinking: str,
    thinking_budget: Optional[int],
    openai_base_url: Optional[str],
    openai_no_budget_thinking_toggle: bool = False,
    reasoning_effort: Optional[str] = None,
) -> str:
    model_lower = model.strip().lower()
    normalized_thinking = _normalize_benchmark_thinking_level(thinking)
    settings = getattr(llm_service, "_settings", None)
    if not isinstance(settings, dict):
        logger.warning("LLM service settings are not mutable; skipping thinking-mode override.")
        return "unmodified"

    extra = settings.get("extra")
    if not isinstance(extra, dict):
        extra = {}
        settings["extra"] = extra

    # Clear keys this function owns before applying model-specific config.
    for key in ("thinking", "output_config", "reasoning", "reasoning_effort"):
        extra.pop(key, None)

    if provider == LLMProvider.CEREBRAS:
        # CerebrasLLMService merges extra into the top-level chat request, so
        # reasoning_effort lands as a chat param. Sampling follows Cerebras's
        # per-model guides.
        settings["top_p"] = 0.95
        if model_lower.startswith("gemma-4"):
            # Gemma 4 31B: reasoning OFF by default. low/medium/high are
            # equivalent today; "medium" is Cerebras's agentic-workflow pick.
            # Agentic T=0.8 (thinking), Fast Q&A T=0.6 (no reasoning).
            if normalized_thinking == "none":
                extra["reasoning_effort"] = "none"
                settings["temperature"] = 0.6
                return "cerebras:gemma-4 no-reasoning reasoning_effort=none T=0.6"
            extra["reasoning_effort"] = "medium"
            settings["temperature"] = 0.8
            return "cerebras:gemma-4 reasoning reasoning_effort=medium T=0.8"
        # Default: Kimi K2.6 — Thinking by default, Instant via reasoning_effort=none.
        # Thinking T=1.0, Instant T=0.6.
        if normalized_thinking == "none":
            extra["reasoning_effort"] = "none"
            settings["temperature"] = 0.6
            return "cerebras:kimi instant reasoning_effort=none T=0.6"
        settings["temperature"] = 1.0
        return "cerebras:kimi thinking (default) T=1.0"

    if provider == LLMProvider.OPENAI:
        if _is_gpt56_responses_model(model, openai_base_url):
            effort = _resolve_gpt56_effective_effort(
                model=model,
                openai_base_url=openai_base_url,
                thinking=normalized_thinking,
                reasoning_effort=reasoning_effort,
            )
            assert effort is not None
            extra["reasoning"] = {"effort": effort}
            extra["store"] = False
            return f"openai:gpt-5.6 responses reasoning.effort={effort} store=false"

        if model_lower.startswith("gpt-5.4"):
            effort = "none" if thinking == "none" else ("low" if thinking == "minimal" else thinking)
            extra["reasoning"] = {"effort": effort}
            return f"openai:gpt-5.4 responses reasoning.effort={effort}"

        if model_lower.startswith("gpt-5"):
            effort = "minimal" if thinking in {"none", "minimal"} else thinking
            extra["reasoning_effort"] = effort
            return f"openai:gpt-5 reasoning_effort={effort}"

        if model_lower.startswith("gpt-4.1"):
            return "openai:gpt-4.1 reasoning_n/a"

        if _is_openrouter_laguna_model(openai_base_url, model_lower):
            enabled = normalized_thinking != "none"
            existing_extra_body = extra.get("extra_body")
            extra_body = dict(existing_extra_body) if isinstance(existing_extra_body, dict) else {}
            extra_body.pop("vllm_xargs", None)
            extra_body.pop("chat_template_kwargs", None)
            extra_body.pop("reasoning_effort", None)
            extra_body["reasoning"] = {
                "enabled": enabled,
                "exclude": False,
            }
            extra["extra_body"] = extra_body
            return f"openrouter:poolside-laguna-s-2.1 reasoning.enabled={enabled}"

        if _is_openrouter_qwen36_model(openai_base_url, model_lower):
            enabled = normalized_thinking != "none"
            existing_extra_body = extra.get("extra_body")
            extra_body = dict(existing_extra_body) if isinstance(existing_extra_body, dict) else {}
            extra_body.pop("vllm_xargs", None)
            extra_body.pop("chat_template_kwargs", None)
            extra_body.pop("reasoning_effort", None)
            extra_body["reasoning"] = {
                "enabled": enabled,
                "exclude": False,
            }
            extra["extra_body"] = extra_body
            return f"openrouter:qwen3.6 reasoning.enabled={enabled}"

        if _is_baseten_qwen36_model(openai_base_url, model_lower):
            enabled = normalized_thinking != "none"
            existing_extra_body = extra.get("extra_body")
            extra_body = dict(existing_extra_body) if isinstance(existing_extra_body, dict) else {}
            extra_body.pop("vllm_xargs", None)
            extra_body.pop("reasoning", None)
            extra_body.pop("reasoning_effort", None)
            existing_ctk = extra_body.get("chat_template_kwargs")
            chat_template_kwargs = dict(existing_ctk) if isinstance(existing_ctk, dict) else {}
            chat_template_kwargs["enable_thinking"] = enabled
            chat_template_kwargs["preserve_thinking"] = enabled
            extra_body["chat_template_kwargs"] = chat_template_kwargs
            extra["extra_body"] = extra_body
            return f"openai-compatible:baseten-qwen3.6 enable_thinking={enabled}"

        if _is_baseten_gemma4_model(openai_base_url, model_lower):
            enabled = normalized_thinking != "none"
            settings["temperature"] = 1.0
            settings["top_p"] = 0.95
            existing_extra_body = extra.get("extra_body")
            extra_body = dict(existing_extra_body) if isinstance(existing_extra_body, dict) else {}
            extra_body.pop("vllm_xargs", None)
            extra_body.pop("reasoning", None)
            extra_body.pop("reasoning_effort", None)
            existing_ctk = extra_body.get("chat_template_kwargs")
            chat_template_kwargs = dict(existing_ctk) if isinstance(existing_ctk, dict) else {}
            chat_template_kwargs["enable_thinking"] = enabled
            chat_template_kwargs["preserve_thinking"] = enabled
            extra_body["chat_template_kwargs"] = chat_template_kwargs
            extra_body["top_k"] = 64
            extra["extra_body"] = extra_body
            return (
                "openai-compatible:baseten-gemma4 "
                f"enable_thinking={enabled} T=1.0 top_p=0.95 top_k=64"
            )

        if openai_base_url and _is_baseten_endpoint(openai_base_url):
            if _is_baseten_inkling_model(model_lower):
                effort = _baseten_inkling_reasoning_effort(thinking)
                # Pipecat settings extra -> SDK create() kwarg -> top-level HTTP field.
                extra["reasoning_effort"] = effort
                settings["temperature"] = 1.0
                existing_extra_body = extra.get("extra_body")
                if isinstance(existing_extra_body, dict):
                    extra_body = dict(existing_extra_body)
                    extra_body.pop("reasoning", None)
                    extra_body.pop("reasoning_effort", None)
                    extra_body.pop("chat_template_kwargs", None)
                    extra_body.pop("vllm_xargs", None)
                    if extra_body:
                        extra["extra_body"] = extra_body
                    else:
                        extra.pop("extra_body", None)
                return (
                    "openai-compatible:baseten-inkling "
                    f"reasoning_effort={effort} T=1.0"
                )

            # Baseten ignores vllm_xargs/chat_template_kwargs; thinking is
            # controlled via OpenAI-style reasoning.effort in extra_body.
            if _is_baseten_glm_reasoning_model(model_lower):
                effort = _baseten_glm_reasoning_effort(thinking)
            else:
                effort = _baseten_reasoning_effort(thinking)
            existing_extra_body = extra.get("extra_body")
            extra_body = dict(existing_extra_body) if isinstance(existing_extra_body, dict) else {}
            existing_reasoning = extra_body.get("reasoning")
            reasoning = dict(existing_reasoning) if isinstance(existing_reasoning, dict) else {}
            reasoning["effort"] = effort
            extra_body["reasoning"] = reasoning
            # Drop controls Baseten does not honor so they don't linger in extra_body.
            extra_body.pop("vllm_xargs", None)
            extra_body.pop("chat_template_kwargs", None)
            extra["extra_body"] = extra_body
            return f"openai-compatible:baseten reasoning.effort={effort}"

        if openai_base_url and _is_gpt_oss_model(model_lower):
            level = _gpt_oss_reasoning_level(thinking)
            return f"openai-compatible:gpt-oss reasoning_level={level} (system_message)"

        if openai_base_url and _is_glm_sglang_binary_reasoning_model(model_lower):
            enable_thinking = thinking != "none"
            existing_extra_body = extra.get("extra_body")
            extra_body = dict(existing_extra_body) if isinstance(existing_extra_body, dict) else {}
            existing_ctk = extra_body.get("chat_template_kwargs")
            chat_template_kwargs = dict(existing_ctk) if isinstance(existing_ctk, dict) else {}
            chat_template_kwargs["enable_thinking"] = enable_thinking
            extra_body["chat_template_kwargs"] = chat_template_kwargs
            extra["extra_body"] = extra_body
            return f"openai-compatible:sglang glm enable_thinking={enable_thinking}"

        if openai_base_url and _is_nemotron_model(model_lower) and openai_no_budget_thinking_toggle:
            enable_thinking = thinking != "none"
            existing_extra_body = extra.get("extra_body")
            extra_body = dict(existing_extra_body) if isinstance(existing_extra_body, dict) else {}
            existing_ctk = extra_body.get("chat_template_kwargs")
            chat_template_kwargs = dict(existing_ctk) if isinstance(existing_ctk, dict) else {}
            chat_template_kwargs["enable_thinking"] = enable_thinking
            extra_body["chat_template_kwargs"] = chat_template_kwargs

            existing_xargs = extra_body.get("vllm_xargs")
            if isinstance(existing_xargs, dict):
                xargs = dict(existing_xargs)
                xargs.pop("thinking_budget", None)
                if xargs:
                    extra_body["vllm_xargs"] = xargs
                else:
                    extra_body.pop("vllm_xargs", None)

            extra["extra_body"] = extra_body
            return f"openai-compatible:nemotron enable_thinking={enable_thinking} no_budget"

        if (
            openai_base_url
            and _is_nemotron_model(model_lower)
            and _is_nemotron_vllm_017_default_only_endpoint(openai_base_url)
        ):
            return "openai-compatible:nemotron vllm-017 default reasoning only"

        if openai_base_url and _is_qwen35_model(model_lower):
            if _is_qwen35_default_only_endpoint(openai_base_url):
                return "openai-compatible:qwen3.5 default reasoning only"

            if thinking == "none":
                enable_thinking = False
            elif thinking == "high":
                enable_thinking = True
            else:
                raise ValueError(
                    "Qwen 3.5 on OpenAI-compatible SGLang supports only thinking='none' or 'high'."
                )

            existing_extra_body = extra.get("extra_body")
            extra_body = dict(existing_extra_body) if isinstance(existing_extra_body, dict) else {}
            existing_ctk = extra_body.get("chat_template_kwargs")
            chat_template_kwargs = dict(existing_ctk) if isinstance(existing_ctk, dict) else {}
            chat_template_kwargs["enable_thinking"] = enable_thinking
            extra_body["chat_template_kwargs"] = chat_template_kwargs
            extra["extra_body"] = extra_body
            return f"openai-compatible:sglang qwen3.5 enable_thinking={enable_thinking}"

        if openai_base_url:
            budget = (
                int(thinking_budget)
                if thinking_budget is not None
                else _mapped_budget_for_thinking(thinking, budget_map=THINKING_BUDGET_MAP)
            )
            existing_extra_body = extra.get("extra_body")
            extra_body = dict(existing_extra_body) if isinstance(existing_extra_body, dict) else {}
            existing_xargs = extra_body.get("vllm_xargs")
            xargs = dict(existing_xargs) if isinstance(existing_xargs, dict) else {}
            xargs["thinking_budget"] = budget
            extra_body["vllm_xargs"] = xargs
            extra["extra_body"] = extra_body
            return f"openai-compatible:vllm thinking_budget={budget}"

        return "openai:unknown_model no_reasoning_override"

    if provider == LLMProvider.ANTHROPIC:
        from pipecat.services.anthropic.llm import AnthropicLLMService

        if (
            "claude-opus-4-6" in model_lower
            or "claude-sonnet-4-6" in model_lower
            or "claude-sonnet-5" in model_lower
        ):
            settings["thinking"] = None
            if normalized_thinking == "none":
                return "anthropic:adaptive disabled"
            effort = normalized_thinking
            # display="summarized" keeps thinking-block text non-empty. Newer
            # adaptive models (Sonnet 5, Opus 4.7/4.8, Fable) default to
            # display="omitted" -> empty thinking text, which pipecat's Anthropic
            # adapter cannot round-trip (it returns the raw thought dict without a
            # "role" key, crashing on the next turn). No-op for Opus/Sonnet 4.6,
            # which already default to summarized. Does not change model behavior
            # or billing -- only whether the reasoning summary is returned.
            extra["thinking"] = {"type": "adaptive", "display": "summarized"}
            extra["output_config"] = {"effort": effort}
            return f"anthropic:adaptive effort={effort}"

        if "claude-haiku-4-5" in model_lower:
            if thinking_budget == 0 or (thinking_budget is None and normalized_thinking == "none"):
                settings["thinking"] = None
                return "anthropic:haiku thinking=disabled"
            budget = (
                int(thinking_budget)
                if thinking_budget is not None
                else _mapped_budget_for_thinking(
                    thinking,
                    budget_map=ANTHROPIC_HAIKU_THINKING_BUDGET_MAP,
                )
            )
            settings["thinking"] = AnthropicLLMService.ThinkingConfig(
                type="enabled",
                budget_tokens=budget,
            )
            return f"anthropic:haiku budget_tokens={budget}"

        if thinking_budget == 0 or (thinking_budget is None and normalized_thinking == "none"):
            settings["thinking"] = None
            return "anthropic:default thinking=disabled"
        budget = (
            int(thinking_budget)
            if thinking_budget is not None
            else max(1024, _mapped_budget_for_thinking(thinking, budget_map=THINKING_BUDGET_MAP))
        )
        settings["thinking"] = AnthropicLLMService.ThinkingConfig(
            type="enabled",
            budget_tokens=budget,
        )
        return f"anthropic:default budget_tokens={budget}"

    if provider == LLMProvider.GOOGLE:
        from pipecat.services.google.llm import GoogleLLMService

        if model_lower.startswith("gemini-2.5-flash"):
            budget = (
                int(thinking_budget)
                if thinking_budget is not None
                else _mapped_budget_for_thinking(
                    thinking,
                    budget_map=GEMINI_25_FLASH_THINKING_BUDGET_MAP,
                )
            )
            settings["thinking"] = GoogleLLMService.ThinkingConfig(
                thinking_budget=budget,
                include_thoughts=budget > 0,
            )
            return f"google:gemini-2.5-flash thinking_budget={budget}"

        if _is_google_thinking_level_model(model_lower):
            level = "minimal" if normalized_thinking == "none" else normalized_thinking
            settings["thinking"] = GoogleLLMService.ThinkingConfig(
                thinking_level=level,
                include_thoughts=True,
            )
            return f"google:gemini-3-family thinking_level={level}"

        if normalized_thinking == "none":
            settings["thinking"] = None
            return "google:default thinking=disabled"
        budget = (
            int(thinking_budget)
            if thinking_budget is not None
            else _mapped_budget_for_thinking(thinking, budget_map=THINKING_BUDGET_MAP)
        )
        settings["thinking"] = GoogleLLMService.ThinkingConfig(
            thinking_budget=budget,
            include_thoughts=True,
        )
        return f"google:default thinking_budget={budget}"

    return "unknown_provider"


def _normalize_prompt_text(text: str) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    normalized: list[str] = []
    saw_blank = False
    for line in lines:
        if line == "":
            if saw_blank:
                continue
            normalized.append("")
            saw_blank = True
        else:
            saw_blank = False
            normalized.append(line)
    return "\n".join(normalized)


def _load_system_instruction(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def create_task_instruction_user_message(task: str) -> str:
    """Create the task-specific user message for the benchmark run."""
    prompt_parts = [
        "# Agent Instructions",
        "",
        "You are an autonomous agent. Execute this task step by step. After each step, observe the results and react accordingly. Responses you generate from each inference call will be used only internally to complete the task. The only information that is returned to the user is the final result message that is passed to the `finished` tool call.",
        "",
        "When you have completed the task, call the `finished` tool with a message to be returned to the user who initiated the task.",
        "",
        "# Current time (UTC)",
        f"{datetime.now(timezone.utc).isoformat()}",
        "",
        "# Task Instructions",
        "",
        f"{task}",
        "",
    ]
    return "\n".join(prompt_parts)


def _event_xml_message(event_name: str, response_data: Any) -> dict[str, str]:
    return {
        "role": "user",
        "content": f"<event name={event_name}>\n{serialize_response_data(response_data)}\n</event>",
    }


def _event_payload_as_dict(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("event_payload")
    if isinstance(payload, dict):
        return payload
    response_data = event.get("response_data")
    if isinstance(response_data, dict):
        return response_data
    return {}


class _BenchmarkInferenceController:
    def __init__(self, runtime: "_BenchmarkRuntime") -> None:
        self._runtime = runtime
        self._pipeline_task: Optional[PipelineTask] = None
        self._llm_inflight = False
        self._tool_call_in_progress = False
        self._inference_reasons: list[str] = []
        self._inference_watchdog_handle: Optional[asyncio.TimerHandle] = None
        self._no_tool_watchdog_handle: Optional[asyncio.TimerHandle] = None
        self._no_tool_nudge_count = 0
        self._pending_async: dict[str, dict[str, Any]] = {}

    def bind_pipeline_task(self, pipeline_task: PipelineTask) -> None:
        self._pipeline_task = pipeline_task

    def set_tool_call_in_progress(self, in_progress: bool) -> None:
        self._tool_call_in_progress = in_progress

    def on_response_start(self) -> None:
        self._llm_inflight = True
        if self._no_tool_watchdog_handle:
            self._no_tool_watchdog_handle.cancel()
            self._no_tool_watchdog_handle = None

    async def on_response_end(self, *, has_function_calls: bool) -> None:
        self._llm_inflight = False
        if self._runtime.stop_requested or self._runtime.inference_suppressed:
            return
        if has_function_calls:
            await self._schedule_pending_inference()
            return
        self._start_no_tool_watchdog()

    def register_async_completion(
        self,
        *,
        tool_call_id: str,
        expected_event: str,
        tool_name: str,
    ) -> None:
        existing = self._pending_async.pop(tool_call_id, None)
        if existing and existing.get("timeout_handle"):
            existing["timeout_handle"].cancel()

        loop = asyncio.get_running_loop()
        timeout_handle = loop.call_later(
            ASYNC_COMPLETION_TIMEOUT,
            lambda: asyncio.create_task(self._on_async_timeout(tool_call_id)),
        )
        self._pending_async[tool_call_id] = {
            "expected_event": expected_event,
            "tool_name": tool_name,
            "timeout_handle": timeout_handle,
        }

    def cancel_async_completion(self, tool_call_id: str) -> None:
        pending = self._pending_async.pop(tool_call_id, None)
        if pending is None:
            return
        handle = pending.get("timeout_handle")
        if handle:
            handle.cancel()
        if not self._pending_async:
            self._runtime.resolve_async_dependency_waiters(allow_execution=False)

    def has_pending_async_completions(self) -> bool:
        return bool(self._pending_async)

    async def _on_async_timeout(self, tool_call_id: str) -> None:
        pending = self._pending_async.pop(tool_call_id, None)
        if pending is None:
            return
        handle = pending.get("timeout_handle")
        if handle:
            handle.cancel()
        self._runtime.async_completion_timeout_count += 1
        if not self._pending_async:
            self._runtime.resolve_async_dependency_waiters(allow_execution=False)
        await self._runtime.response_tracker.finalize_pending_response()
        if self._runtime.inference_suppressed:
            self._runtime.maybe_finalize_deferred_stop()
            return
        await self.request_inference(f"async_timeout:{tool_call_id}")

    def _clear_pending_for_event(self, event_name: str) -> int:
        for tool_call_id, payload in list(self._pending_async.items()):
            if payload.get("expected_event") != event_name:
                continue
            matched = self._pending_async.pop(tool_call_id, None)
            if matched and matched.get("timeout_handle"):
                matched["timeout_handle"].cancel()
            return 1
        return 0

    async def on_event(self, event_name: str) -> None:
        matched = self._clear_pending_for_event(event_name)
        had_waiters = self._runtime.has_async_dependency_waiters()
        logger.info(
            "EVENT event={} matched_async={} state={}",
            event_name,
            matched,
            _state_log_label(self._runtime.world.state_snapshot()),
        )
        if matched and not self._pending_async:
            await self._runtime.response_tracker.finalize_pending_response()
            self._runtime.resolve_async_dependency_waiters(allow_execution=True)
        if self._runtime.inference_suppressed:
            if not had_waiters:
                self._runtime.maybe_finalize_deferred_stop()
            return
        await self.request_inference(f"event:{event_name}")

    async def queue_initial_run(self) -> None:
        if self._runtime.stop_requested:
            return
        if not self._pipeline_task or self._pipeline_task.has_finished():
            return
        logger.info(
            "LLM_RUN turn={} reasons={} state={}",
            self._runtime.turn_count + 1,
            ["initial_run"],
            _state_log_label(self._runtime.world.state_snapshot()),
        )
        inference_index = self._runtime.queue_inference_capture(["initial_run"])
        self._llm_inflight = True
        try:
            await self._pipeline_task.queue_frames([LLMRunFrame()])
        except Exception:
            self._llm_inflight = False
            if inference_index is not None:
                self._runtime.discard_pending_inference_capture(inference_index)
            raise

    async def request_inference(self, reason: str) -> None:
        if self._runtime.stop_requested or self._runtime.inference_suppressed:
            return
        self._inference_reasons.append(reason)
        if len(self._inference_reasons) > 50:
            self._inference_reasons = self._inference_reasons[-50:]
        self._start_inference_watchdog()

    def _start_inference_watchdog(self) -> None:
        if self._runtime.stop_requested or self._runtime.inference_suppressed:
            return
        if self._inference_watchdog_handle is not None:
            return
        if self._llm_inflight:
            return
        if self._tool_call_in_progress:
            return
        if not self._inference_reasons:
            return
        if self._pending_async:
            return
        if not self._pipeline_task or self._pipeline_task.has_finished():
            return

        loop = asyncio.get_running_loop()
        self._inference_watchdog_handle = loop.call_later(
            EVENT_BATCH_INFERENCE_DELAY,
            self._inference_watchdog_fire,
        )

    def _inference_watchdog_fire(self) -> None:
        self._inference_watchdog_handle = None

        async def _run() -> None:
            await self._schedule_pending_inference()

        asyncio.create_task(_run())

    async def _schedule_pending_inference(self) -> None:
        if self._runtime.stop_requested or self._runtime.inference_suppressed:
            self._inference_reasons.clear()
            return
        if self._llm_inflight or self._tool_call_in_progress:
            return
        if not self._inference_reasons:
            return
        if self._pending_async:
            return
        if not self._pipeline_task or self._pipeline_task.has_finished():
            return

        reasons_snapshot = list(self._inference_reasons)
        self._inference_reasons.clear()

        if self._no_tool_watchdog_handle:
            self._no_tool_watchdog_handle.cancel()
            self._no_tool_watchdog_handle = None

        if "no_tool_nudge" not in reasons_snapshot:
            self._no_tool_nudge_count = 0

        dropped_empty_messages = _prune_empty_assistant_context_messages(
            getattr(self._runtime, "llm_context", None)
        )
        if dropped_empty_messages:
            logger.info(
                "LLM_CONTEXT_PRUNE turn={} dropped_empty_assistant_messages={}",
                self._runtime.turn_count + 1,
                dropped_empty_messages,
            )

        logger.info(
            "LLM_RUN turn={} reasons={} state={}",
            self._runtime.turn_count + 1,
            reasons_snapshot,
            _state_log_label(self._runtime.world.state_snapshot()),
        )
        inference_index = self._runtime.queue_inference_capture(reasons_snapshot)
        self._llm_inflight = True
        try:
            await self._pipeline_task.queue_frames([LLMRunFrame()])
        except Exception:
            self._llm_inflight = False
            if inference_index is not None:
                self._runtime.discard_pending_inference_capture(inference_index)
            self._inference_reasons = reasons_snapshot + self._inference_reasons
            raise

    def can_retry_transport_empty_response(self) -> bool:
        if self._runtime.stop_requested or self._runtime.inference_suppressed:
            return False
        if self._llm_inflight or self._tool_call_in_progress:
            return False
        if not self._pipeline_task or self._pipeline_task.has_finished():
            return False
        return True

    async def retry_transport_empty_response(self, *, retry_number: int) -> bool:
        if not self.can_retry_transport_empty_response():
            return False

        if self._no_tool_watchdog_handle:
            self._no_tool_watchdog_handle.cancel()
            self._no_tool_watchdog_handle = None
        if self._inference_watchdog_handle:
            self._inference_watchdog_handle.cancel()
            self._inference_watchdog_handle = None

        reasons_snapshot = [f"transport_empty_retry:{retry_number}"]
        dropped_empty_messages = _prune_empty_assistant_context_messages(
            getattr(self._runtime, "llm_context", None)
        )
        if dropped_empty_messages:
            logger.info(
                "LLM_CONTEXT_PRUNE turn={} dropped_empty_assistant_messages={}",
                self._runtime.turn_count + 1,
                dropped_empty_messages,
            )

        logger.info(
            "LLM_RUN turn={} reasons={} state={}",
            self._runtime.turn_count + 1,
            reasons_snapshot,
            _state_log_label(self._runtime.world.state_snapshot()),
        )
        inference_index = self._runtime.queue_inference_capture(reasons_snapshot)
        self._llm_inflight = True
        try:
            await self._pipeline_task.queue_frames([LLMRunFrame()])
        except Exception:
            self._llm_inflight = False
            if inference_index is not None:
                self._runtime.discard_pending_inference_capture(inference_index)
            raise
        return True

    def _start_no_tool_watchdog(self) -> None:
        if self._runtime.stop_requested or self._runtime.inference_suppressed:
            return
        if self._no_tool_watchdog_handle is not None:
            return
        if not self._pipeline_task or self._pipeline_task.has_finished():
            return
        loop = asyncio.get_running_loop()
        self._no_tool_watchdog_handle = loop.call_later(
            NO_TOOL_WATCHDOG_DELAY,
            self._no_tool_watchdog_fire,
        )

    def _no_tool_watchdog_fire(self) -> None:
        self._no_tool_watchdog_handle = None

        async def _run() -> None:
            if self._runtime.stop_requested:
                return
            self._no_tool_nudge_count += 1
            if self._no_tool_nudge_count > MAX_NO_TOOL_NUDGES:
                self._runtime.finished_message = "Task stopped: LLM failed to call required tools"
                self._runtime.request_stop("no_tool_call_stall")
                return

            nudge_message = {
                "role": "user",
                "content": (
                    "You did not call any tools in your last response. "
                    "If the task is complete, call the `finished` tool with a summary message. "
                    "If more work is needed, call the appropriate tool to continue."
                ),
            }
            if self._pipeline_task and not self._pipeline_task.has_finished():
                await self._pipeline_task.queue_frames(
                    [LLMMessagesAppendFrame(messages=[nudge_message], run_llm=False)]
                )
            await self.request_inference("no_tool_nudge")

        asyncio.create_task(_run())

    def close(self) -> None:
        if self._inference_watchdog_handle:
            self._inference_watchdog_handle.cancel()
            self._inference_watchdog_handle = None
        if self._no_tool_watchdog_handle:
            self._no_tool_watchdog_handle.cancel()
            self._no_tool_watchdog_handle = None
        for payload in list(self._pending_async.values()):
            handle = payload.get("timeout_handle")
            if handle:
                handle.cancel()
        self._pending_async.clear()


class _BenchmarkResponseTracker(FrameProcessor):
    def __init__(self, runtime: "_BenchmarkRuntime", controller: _BenchmarkInferenceController):
        super().__init__()
        self._runtime = runtime
        self._controller = controller
        self._transport_empty_retries = 0
        self._reset_response()

    def _reset_response(self) -> None:
        self._response_started = False
        self._response_start_monotonic: Optional[float] = None
        self._response_state_before: dict[str, Any] = {}
        self._bad_before = 0
        self._response_end_seen = False
        self._pending_tool_results = 0
        self._has_function_calls = False
        self._response_text = ""
        self._response_text_raw = ""
        self._response_thought = ""
        self._decision_ms: Optional[float] = None
        self._tool_calls: list[dict[str, Any]] = []
        self._tool_call_by_id: dict[str, int] = {}
        self._usage_metrics: Optional[dict[str, Any]] = None
        self._ttfb_metrics: Optional[dict[str, Any]] = None

    def _transport_empty_retry_enabled(self) -> bool:
        if not getattr(self._runtime, "transport_empty_retry_enabled", False):
            return False
        args = getattr(self._runtime, "args", None)
        return _baseten_transport_retry_enabled(
            getattr(args, "openai_base_url", None), getattr(args, "model", "")
        )

    def _matches_transport_empty_response_signature(self) -> bool:
        return (
            self._transport_empty_retry_enabled()
            and not self._has_function_calls
            and self._response_text == ""
            and self._response_text_raw == ""
            and self._response_thought == ""
            and self._usage_metrics is None
            and getattr(self._runtime, "last_error_event", None) is None
            and not getattr(self._runtime, "rate_limit_exhausted_pending", False)
            and not getattr(self._runtime, "api_error_pending", False)
            and not getattr(self._runtime, "responses_incomplete_pending", False)
        )

    async def process_frame(self, frame: Any, direction: FrameDirection):
        await super().process_frame(frame, direction)
        frame_to_push: Any = frame

        if isinstance(frame, LLMFullResponseStartFrame):
            self._reset_response()
            self._response_started = True
            self._response_start_monotonic = time.perf_counter()
            self._response_state_before = self._runtime.world.state_snapshot()
            self._bad_before = self._runtime.world.bad_actions_count
            self._runtime.activate_next_inference_capture()
            self._controller.on_response_start()
            logger.info(
                "LLM_RESPONSE_START turn={} state={}",
                self._runtime.turn_count + 1,
                _state_log_label(self._response_state_before),
            )

        elif isinstance(frame, LLMTextFrame):
            self._response_text_raw += frame.text
            sanitized_chunk = _sanitize_assistant_replay_text(frame.text)
            if sanitized_chunk:
                self._response_text += sanitized_chunk
                frame_to_push = LLMTextFrame(sanitized_chunk)
            else:
                frame_to_push = None

        elif isinstance(frame, LLMThoughtTextFrame):
            self._response_thought += frame.text

        elif isinstance(frame, FunctionCallsStartedFrame):
            self._has_function_calls = True
            function_calls = list(frame.function_calls)
            self._pending_tool_results = len(function_calls)
            self._tool_calls = []
            self._tool_call_by_id = {}
            for idx, function_call in enumerate(function_calls):
                entry = {
                    "name": function_call.function_name,
                    "args": dict(function_call.arguments or {}),
                    "result_status": "pending",
                    "tool_call_id": function_call.tool_call_id,
                }
                self._tool_calls.append(entry)
                self._tool_call_by_id[function_call.tool_call_id] = idx
            logger.info(
                "TURN_TOOL_CALLS turn={} tools={}",
                self._runtime.turn_count + 1,
                ", ".join(str(function_call.function_name) for function_call in function_calls) or "none",
            )

        elif isinstance(frame, FunctionCallResultFrame):
            index = self._tool_call_by_id.get(frame.tool_call_id)
            if index is None:
                entry = {
                    "name": frame.function_name,
                    "args": frame.arguments if isinstance(frame.arguments, dict) else {},
                    "result_status": classify_result_status(frame.result),
                    "tool_call_id": frame.tool_call_id,
                }
                self._tool_calls.append(entry)
            else:
                self._tool_calls[index]["result_status"] = classify_result_status(frame.result)
            self._pending_tool_results = max(0, self._pending_tool_results - 1)

            if isinstance(frame.result, dict) and frame.result.get("error") is not None:
                self._runtime.last_error_event = dict(frame.result)

        elif isinstance(frame, MetricsFrame):
            usage_entry = _usage_entry_from_metrics_frame(frame)
            if usage_entry is not None:
                self._usage_metrics = usage_entry
            ttfb_entry = _ttfb_entry_from_metrics_frame(frame)
            if ttfb_entry is not None and self._ttfb_metrics is None:
                self._ttfb_metrics = ttfb_entry

        elif isinstance(frame, LLMFullResponseEndFrame):
            self._response_end_seen = True
            if self._response_start_monotonic is not None:
                self._decision_ms = round((time.perf_counter() - self._response_start_monotonic) * 1000, 2)
            await self._controller.on_response_end(has_function_calls=self._has_function_calls)

        await self._finalize_if_ready()
        if frame_to_push is not None:
            await self.push_frame(frame_to_push, direction)

    async def _finalize_if_ready(self) -> None:
        if not self._response_started:
            return
        if not self._response_end_seen:
            return
        if self._pending_tool_results != 0:
            return
        if self._controller.has_pending_async_completions():
            return

        failure_class = "none"
        transport_empty_exhausted = False
        rate_limit_exhausted = bool(
            getattr(self._runtime, "rate_limit_exhausted_pending", False)
        )
        rate_limit_exhausted_event = None
        if rate_limit_exhausted:
            event = getattr(self._runtime, "rate_limit_exhausted_event", None)
            if isinstance(event, dict):
                rate_limit_exhausted_event = dict(event)
        api_error_pending = bool(getattr(self._runtime, "api_error_pending", False))
        api_error_event = None
        if api_error_pending:
            event = getattr(self._runtime, "api_error_event", None)
            if isinstance(event, dict):
                api_error_event = dict(event)
        responses_incomplete = bool(
            getattr(self._runtime, "responses_incomplete_pending", False)
        )
        responses_incomplete_event = None
        if responses_incomplete:
            event = getattr(self._runtime, "responses_incomplete_event", None)
            if isinstance(event, dict):
                responses_incomplete_event = dict(event)

        if (
            not rate_limit_exhausted
            and not api_error_pending
            and not responses_incomplete
            and self._matches_transport_empty_response_signature()
        ):
            self._runtime.empty_response_count = getattr(self._runtime, "empty_response_count", 0) + 1
            if self._transport_empty_retries < MAX_TRANSPORT_EMPTY_RETRIES:
                if self._controller.can_retry_transport_empty_response():
                    self._transport_empty_retries += 1
                    retry_number = self._transport_empty_retries
                    logger.info(
                        "TRANSPORT_EMPTY_RETRY turn={} retry={} max_retries={}",
                        self._runtime.turn_count + 1,
                        retry_number,
                        MAX_TRANSPORT_EMPTY_RETRIES,
                    )
                    retry_queued = await self._controller.retry_transport_empty_response(
                        retry_number=retry_number
                    )
                    if retry_queued:
                        self._runtime.discard_active_inference_capture()
                        self._reset_response()
                        return
                    self._transport_empty_retries -= 1
                    logger.warning(
                        "TRANSPORT_EMPTY_RETRY_UNAVAILABLE turn={} retry={} falling_back_to_no_tool",
                        self._runtime.turn_count + 1,
                        retry_number,
                    )
                else:
                    logger.warning(
                        "TRANSPORT_EMPTY_RETRY_UNAVAILABLE turn={} falling_back_to_no_tool",
                        self._runtime.turn_count + 1,
                    )
                transport_empty_exhausted = True
            else:
                transport_empty_exhausted = True

        if rate_limit_exhausted:
            failure_class = "rate_limit_exhausted"
        elif api_error_pending:
            failure_class = "inference_failure"
        elif responses_incomplete:
            failure_class = "response_incomplete"
        elif not self._has_function_calls:
            failure_class = "no_tool_call"
            self._runtime.no_tool_call_count += 1
            self._runtime.world.increment_bad_action()

        state_after = self._runtime.world.state_snapshot()
        bad_after = self._runtime.world.bad_actions_count

        tool_calls = [
            {
                "name": entry.get("name"),
                "args": entry.get("args") if isinstance(entry.get("args"), dict) else {},
                "result_status": entry.get("result_status", "unknown"),
            }
            for entry in self._tool_calls
        ]

        turn_log: dict[str, Any] = {
            "llm_turn": self._runtime.turn_count + 1,
            "decision_ms": self._decision_ms,
            "tool_calls": tool_calls,
            "raw_response_text": self._response_text.strip(),
            "failure_class": failure_class,
            "bad_actions_before": self._bad_before,
            "bad_actions_after": bad_after,
            "bad_action_increment": bad_after - self._bad_before,
            "state_before": self._response_state_before,
            "state_after": state_after,
        }
        if getattr(self._runtime, "transport_empty_retry_enabled", False):
            turn_log["transport_empty_retries"] = self._transport_empty_retries
            turn_log["transport_empty_attempts"] = self._transport_empty_retries + 1
        if rate_limit_exhausted:
            turn_log["rate_limit_exhausted"] = True
            if rate_limit_exhausted_event is not None:
                turn_log["rate_limit_event"] = rate_limit_exhausted_event
                turn_log["error_event"] = rate_limit_exhausted_event
        if api_error_pending:
            turn_log["api_error"] = True
            if api_error_event is not None:
                turn_log["api_error_event"] = api_error_event
                turn_log["error_event"] = api_error_event
        if responses_incomplete:
            turn_log["response_incomplete"] = True
            if responses_incomplete_event is not None:
                turn_log["response_incomplete_event"] = responses_incomplete_event
                turn_log["error_event"] = responses_incomplete_event
        claim_trace_index = getattr(self._runtime, "claim_responses_trace_index", None)
        responses_trace_index = claim_trace_index() if callable(claim_trace_index) else None
        if responses_trace_index is not None:
            turn_log["responses_trace_index"] = responses_trace_index
        raw_text_raw = self._response_text_raw.strip()
        if raw_text_raw and raw_text_raw != turn_log["raw_response_text"]:
            turn_log["raw_response_text_raw"] = raw_text_raw

        if self._runtime.last_error_event is not None:
            turn_log["error_event"] = self._runtime.last_error_event
            self._runtime.last_error_event = None

        if self._response_thought:
            turn_log["raw_thought_text"] = self._response_thought

        if self._usage_metrics is not None:
            turn_log["usage"] = dict(self._usage_metrics)
        if self._ttfb_metrics is not None:
            turn_log["ttfb"] = dict(self._ttfb_metrics)
            turn_log["ttfb_ms"] = self._ttfb_metrics.get("ttfb_ms")

        self._runtime.attach_active_inference_capture(turn_log)
        self._runtime.turn_logs.append(turn_log)
        self._runtime.turn_count += 1
        if rate_limit_exhausted:
            self._runtime.rate_limit_exhausted_pending = False
            self._runtime.rate_limit_exhausted_event = None
        if api_error_pending:
            self._runtime.api_error_pending = False
            self._runtime.api_error_event = None
        if responses_incomplete:
            self._runtime.responses_incomplete_pending = False
            self._runtime.responses_incomplete_event = None
        if self._transport_empty_retries > 0 and not transport_empty_exhausted:
            self._runtime.empty_response_retry_success_count = (
                getattr(self._runtime, "empty_response_retry_success_count", 0) + 1
            )
        self._transport_empty_retries = 0
        append_replay_stream_event = getattr(self._runtime, "_append_replay_stream_event", None)
        if callable(append_replay_stream_event):
            append_replay_stream_event("turn", turn=turn_log)
        logger.info(
            "TURN_COMPLETE turn={} decision_ms={} tools={} failure={} before={} after={}",
            turn_log["llm_turn"],
            self._decision_ms,
            _tool_calls_log_label(tool_calls),
            failure_class,
            _state_log_label(self._response_state_before),
            _state_log_label(state_after),
        )

        if rate_limit_exhausted and not self._runtime.stop_requested:
            self._runtime.request_stop("rate_limit_exhausted")

        if api_error_pending and not self._runtime.stop_requested:
            self._runtime.request_stop("inference_error")

        if responses_incomplete and not self._runtime.stop_requested:
            self._runtime.request_stop("response_incomplete")

        if self._runtime.turn_count >= self._runtime.max_turns and not self._runtime.stop_requested:
            self._runtime.request_stop("max_turns_exhausted", wait_for_pending_async=True)

        write_partial_checkpoint = getattr(self._runtime, "write_partial_checkpoint", None)
        if callable(write_partial_checkpoint):
            write_partial_checkpoint(reason="turn_complete")

        self._response_started = False

    async def finalize_pending_response(self) -> None:
        await self._finalize_if_ready()


class _BenchmarkRuntime:
    def __init__(
        self,
        *,
        args: argparse.Namespace,
        llm_service: LLMService,
        world: SyntheticWorld,
        system_instruction: str,
        system_instruction_path: Path,
    ) -> None:
        self.args = args
        self.llm_service = llm_service
        self.world = world
        self.system_instruction = system_instruction
        self.system_instruction_path = system_instruction_path

        self.turn_logs: list[dict[str, Any]] = []
        self.turn_count = 0
        self.stop_requested = False
        self.inference_suppressed = False
        self.finished_called = False
        self.finished_message: Optional[str] = None
        self.terminal_reason = "max_turns_exhausted"
        self._deferred_stop_reason: Optional[str] = None
        self.last_error_event: Optional[dict[str, Any]] = None

        self.no_tool_call_count = 0
        self.post_finished_call_count = 0
        self.async_completion_timeout_count = 0
        self.transport_empty_retry_enabled = _baseten_transport_retry_enabled(
            args.openai_base_url, args.model
        )
        self.empty_response_count = 0
        self.empty_response_retry_success_count = 0
        self.rate_limit_retry_enabled = args.provider == "openai" and _is_baseten_endpoint(
            args.openai_base_url
        )
        self.rate_limit_count = 0
        self.rate_limit_retry_success_count = 0
        self.rate_limit_exhausted_pending = False
        self.rate_limit_exhausted_event: Optional[dict[str, Any]] = None
        self.api_error_pending = False
        self.api_error_event: Optional[dict[str, Any]] = None
        self.responses_incomplete_pending = False
        self.responses_incomplete_event: Optional[dict[str, Any]] = None
        self.responses_traces: list[dict[str, Any]] = []
        self._pending_responses_trace_indexes: deque[int] = deque()

        self.run_id = str(uuid.uuid4())
        self.started_at_utc = _iso_utc_now()
        self.started_monotonic = time.perf_counter()
        self.initial_state_snapshot = self.world.state_snapshot()
        self.git_sha = _git_sha(REPO_ROOT)
        self.leaderboard_prompt_id = _leaderboard_prompt_id_for_task(
            task_variant=self.args.task_variant,
            task=self.args.task,
        )
        self.replay_stream_path = (
            Path(self.args.replay_stream_jsonl).expanduser().resolve()
            if getattr(self.args, "replay_stream_jsonl", None)
            else None
        )

        self.max_turns = args.max_turns
        self.done_event = asyncio.Event()

        self.pipeline_task: Optional[PipelineTask] = None
        self.llm_context: Optional[LLMContext] = None
        self.controller = _BenchmarkInferenceController(self)
        self.response_tracker = _BenchmarkResponseTracker(self, self.controller)
        self.event_summaries = TaskAgentEventSummaries()
        self.inference_inputs: list[dict[str, Any]] = []
        self._pending_inference_capture_indexes: deque[int] = deque()
        self._active_inference_capture_index: int | None = None

        self._event_tasks: set[asyncio.Task[Any]] = set()
        self._skip_context_events: dict[str, int] = {}
        self._async_dependency_waiters: list[asyncio.Future[bool]] = []
        self._initialize_replay_stream()

    @staticmethod
    def _responses_trace_is_rate_limit(trace: dict[str, Any]) -> bool:
        error = trace.get("error") if isinstance(trace.get("error"), dict) else {}
        return error.get("status_code") == 429 or error.get("code") in {
            "rate_limit_exceeded",
            "rate_limit_error",
        }

    def record_responses_trace(self, trace: dict[str, Any]) -> None:
        sanitized = _to_json_compatible(trace)
        if not isinstance(sanitized, dict):
            return
        self.responses_traces.append(sanitized)
        trace_index = sanitized.get("trace_index")
        if isinstance(trace_index, int):
            self._pending_responses_trace_indexes.append(trace_index)

        status = sanitized.get("response_status")
        if status == "completed":
            return
        if status == "incomplete":
            self.responses_incomplete_pending = True
            self.responses_incomplete_event = {
                "endpoint": "inference",
                "error_class": "response_incomplete",
                "source": {"type": "openai_responses_terminal"},
                "synthesized": False,
                "response_id": sanitized.get("response_id"),
                "request_id": sanitized.get("request_id"),
                "reason": sanitized.get("incomplete_reason"),
                "trace_index": trace_index,
            }
            return

        error = sanitized.get("error") if isinstance(sanitized.get("error"), dict) else {}
        event = {
            "endpoint": "inference",
            "error_class": "responses_error",
            "source": {"type": "openai_responses_terminal"},
            "synthesized": False,
            "status": error.get("status_code"),
            "code": error.get("code"),
            "exception_type": error.get("type"),
            "message": error.get("message"),
            "request_id": sanitized.get("request_id"),
            "response_id": sanitized.get("response_id"),
            "trace_index": trace_index,
        }
        if self._responses_trace_is_rate_limit(sanitized):
            self.rate_limit_exhausted_pending = True
            self.rate_limit_exhausted_event = event
        else:
            self.api_error_pending = True
            self.api_error_event = event

    def claim_responses_trace_index(self) -> Optional[int]:
        pending = getattr(self, "_pending_responses_trace_indexes", None)
        if not pending:
            return None
        return pending.popleft()

    def build_config_snapshot(self) -> dict[str, Any]:
        snapshot = {
            "provider": self.args.provider,
            "model": self.args.model,
            "openai_base_url": self.args.openai_base_url,
            "openai_params": getattr(self.args, "openai_params", None),
            "openai_no_budget_thinking_toggle": getattr(self.args, "openai_no_budget_thinking_toggle", False),
            "thinking": self.args.thinking,
            "thinking_budget": self.args.thinking_budget,
            "max_tokens": self.args.max_tokens,
            "max_turns": self.args.max_turns,
            "function_call_timeout_secs": self.args.function_call_timeout_secs,
            "llm_request_timeout_secs": getattr(self.args, "llm_request_timeout_secs", None),
            "llm_stream_idle_timeout_secs": getattr(
                self.args, "llm_stream_idle_timeout_secs", None
            ),
            "pipeline_idle_timeout_secs": getattr(
                self.args, "pipeline_idle_timeout_secs", None
            ),
            "capture_inference_inputs": self.args.capture_inference_inputs,
            "task": self.args.task,
            "task_variant": self.args.task_variant,
            "task_prompt_version": self.args.task_prompt_version,
            "leaderboard_prompt_id": self.leaderboard_prompt_id,
        }
        if getattr(self.args, "round_id", None) is not None:
            snapshot["round_id"] = self.args.round_id
        if getattr(self.args, "effective_effort", None) is not None:
            snapshot["reasoning_effort"] = getattr(self.args, "reasoning_effort", None)
            snapshot["effective_effort"] = self.args.effective_effort
        return snapshot

    def build_metadata_snapshot(self, *, ended_at_utc: Optional[str] = None) -> dict[str, Any]:
        snapshot = {
            "run_id": self.run_id,
            "runner_version": RUNNER_VERSION,
            "started_at_utc": self.started_at_utc,
            "ended_at_utc": ended_at_utc,
            "repo_root": str(REPO_ROOT),
            "git_sha": self.git_sha,
            "system_instruction_path": str(self.system_instruction_path),
            "system_instruction_hash": _sha256_text(self.system_instruction),
            "task_variant": self.args.task_variant,
            "task_prompt_version": self.args.task_prompt_version,
            "leaderboard_prompt_id": self.leaderboard_prompt_id,
            "task_prompt_hash": _sha256_text(self.args.task),
            "initial_state": self.initial_state_snapshot,
            "run_file": self.args.log_json,
            "replay_stream_jsonl": self.args.replay_stream_jsonl,
            "llm_request_timeout_secs": getattr(self.args, "llm_request_timeout_secs", None),
            "llm_stream_idle_timeout_secs": getattr(
                self.args, "llm_stream_idle_timeout_secs", None
            ),
            "pipeline_idle_timeout_secs": getattr(
                self.args, "pipeline_idle_timeout_secs", None
            ),
        }
        if getattr(self.args, "round_id", None) is not None:
            snapshot["round_id"] = self.args.round_id
        if getattr(self.args, "effective_effort", None) is not None:
            snapshot["thinking"] = self.args.thinking
            snapshot["reasoning_effort"] = getattr(self.args, "reasoning_effort", None)
            snapshot["effective_effort"] = self.args.effective_effort
        return snapshot

    def build_termination_snapshot(self, *, elapsed_ms: Any) -> dict[str, Any]:
        return {
            "reason": self.terminal_reason,
            "finished_called": self.finished_called,
            "finished_message": self.finished_message,
            "elapsed_ms": elapsed_ms,
        }

    def _append_replay_stream_event(self, event_type: str, **payload: Any) -> None:
        if getattr(self, "replay_stream_path", None) is None:
            return

        event = {
            "schema_version": REPLAY_STREAM_SCHEMA_VERSION,
            "type": event_type,
            "recorded_at_utc": _iso_utc_now(),
            **payload,
        }
        replay_stream_path = self.replay_stream_path
        replay_stream_path.parent.mkdir(parents=True, exist_ok=True)
        with replay_stream_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_to_json_compatible(event), ensure_ascii=False) + "\n")

    def _initialize_replay_stream(self) -> None:
        if self.replay_stream_path is None:
            return
        self.replay_stream_path.parent.mkdir(parents=True, exist_ok=True)
        self.replay_stream_path.write_text("", encoding="utf-8")
        self._append_replay_stream_event(
            "session_start",
            run_schema_version=RUN_SCHEMA_VERSION,
            metadata=self.build_metadata_snapshot(),
            config=self.build_config_snapshot(),
        )

    async def setup_pipeline(self) -> tuple[PipelineTask, asyncio.Task[Any]]:
        self.llm_service.register_function(None, self.handle_function_call)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_instruction},
            {"role": "user", "content": create_task_instruction_user_message(self.args.task)},
        ]

        self.world.current_task_id = self.run_id
        for event_plan in self.world.initial_events():
            event_payload, response_data = self._resolve_event_payload_and_response_data(event_plan)
            self.world.record_event(
                event_name=event_plan.event_name,
                response_data=response_data,
                event_payload=event_payload,
                source_tool=event_plan.source_tool,
            )
            messages.append(_event_xml_message(event_plan.event_name, response_data))

        context = LLMContext(messages=messages, tools=build_tools_schema())
        self.llm_context = context
        create_reasoning_pair = getattr(
            self.llm_service, "create_reasoning_context_aggregator_pair", None
        )
        aggregator_pair = (
            create_reasoning_pair(context)
            if callable(create_reasoning_pair)
            else LLMContextAggregatorPair(context)
        )
        pipeline = Pipeline(
            [
                aggregator_pair.user(),
                self.llm_service,
                self.response_tracker,
                aggregator_pair.assistant(),
            ]
        )

        pipeline_task_kwargs: dict[str, Any] = {}
        pipeline_idle_timeout = getattr(self.args, "pipeline_idle_timeout_secs", None)
        if pipeline_idle_timeout is not None:
            pipeline_task_kwargs["idle_timeout_secs"] = float(pipeline_idle_timeout)

        pipeline_task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=False,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            idle_timeout_frames=(
                LLMTextFrame,
                FunctionCallsStartedFrame,
                LLMFullResponseStartFrame,
            ),
            **pipeline_task_kwargs,
        )

        if pipeline_idle_timeout is not None:

            @pipeline_task.event_handler("on_idle_timeout")
            async def on_idle_timeout(_task: PipelineTask) -> None:
                if not self.stop_requested:
                    self.last_error_event = {
                        "endpoint": "inference",
                        "error_class": "pipeline_idle_timeout",
                        "source": {"type": "pipeline_watchdog"},
                        "synthesized": True,
                        "status": 504,
                    }
                    self.request_stop("inference_error")
                self.write_partial_checkpoint(reason="pipeline_idle_timeout")

        pipeline_runner = PipelineRunner(handle_sigint=False, handle_sigterm=False)
        runner_task = asyncio.create_task(pipeline_runner.run(pipeline_task))

        self.pipeline_task = pipeline_task
        self.controller.bind_pipeline_task(pipeline_task)
        return pipeline_task, runner_task

    def _ensure_inference_capture_state(self) -> None:
        if not hasattr(self, "_pending_inference_capture_indexes"):
            self._pending_inference_capture_indexes = deque()
        if not hasattr(self, "_active_inference_capture_index"):
            self._active_inference_capture_index = None

    def _inference_input_entry(self, inference_index: int) -> dict[str, Any] | None:
        if inference_index <= 0:
            return None
        if inference_index > len(self.inference_inputs):
            return None
        entry = self.inference_inputs[inference_index - 1]
        if not isinstance(entry, dict):
            return None
        return entry

    def capture_inference_input(self, reasons: list[str]) -> int | None:
        if not self.args.capture_inference_inputs:
            return None
        if self.llm_context is None:
            return None

        entry: dict[str, Any] = {
            "inference_index": len(self.inference_inputs) + 1,
            "llm_turn": self.turn_count + 1,
            "reasons": list(reasons),
            "state_before": self.world.state_snapshot(),
            "messages": [
                _serialize_context_message(message) for message in self.llm_context.get_messages()
            ],
        }

        try:
            adapter = self.llm_service.get_llm_adapter()
            llm_filter = getattr(adapter, "id_for_llm_specific_messages", None)
            if isinstance(llm_filter, str) and llm_filter:
                filtered_messages = self.llm_context.get_messages(llm_specific_filter=llm_filter)
                entry["messages_for_llm"] = [
                    _serialize_context_message(message) for message in filtered_messages
                ]
            entry["provider_invocation_params"] = _to_json_compatible(
                adapter.get_llm_invocation_params(self.llm_context)
            )
        except Exception as exc:  # noqa: BLE001
            entry["capture_error"] = str(exc)

        llm_settings = getattr(self.llm_service, "_settings", None)
        if llm_settings is not None:
            entry["llm_settings"] = _to_json_compatible(llm_settings)

        llm_tool_config = getattr(self.llm_service, "_tool_config", None)
        if llm_tool_config is not None:
            entry["llm_tool_config"] = _to_json_compatible(llm_tool_config)

        self.inference_inputs.append(entry)
        self._append_replay_stream_event("inference_input", inference_input=entry)
        return int(entry["inference_index"])

    def queue_inference_capture(self, reasons: list[str]) -> int | None:
        inference_index = self.capture_inference_input(reasons)
        if inference_index is None:
            return None
        self._ensure_inference_capture_state()
        self._pending_inference_capture_indexes.append(inference_index)
        return inference_index

    def activate_next_inference_capture(self) -> int | None:
        self._ensure_inference_capture_state()
        if self._active_inference_capture_index is not None:
            return self._active_inference_capture_index
        if not self._pending_inference_capture_indexes:
            return None

        inference_index = self._pending_inference_capture_indexes.popleft()
        self._active_inference_capture_index = inference_index
        entry = self._inference_input_entry(inference_index)
        if entry is not None:
            entry["response_start_llm_turn"] = self.turn_count + 1
        return inference_index

    def claim_next_inference_capture(self) -> int | None:
        self._ensure_inference_capture_state()
        if self._active_inference_capture_index is not None:
            inference_index = self._active_inference_capture_index
            self._active_inference_capture_index = None
            return inference_index
        if self._pending_inference_capture_indexes:
            return self._pending_inference_capture_indexes.popleft()
        return None

    def attach_active_inference_capture(self, turn_log: dict[str, Any]) -> None:
        inference_index = self.claim_next_inference_capture()
        if inference_index is None:
            return

        turn_log["inference_index"] = inference_index
        entry = self._inference_input_entry(inference_index)
        if entry is not None:
            entry["finalized_llm_turn"] = turn_log.get("llm_turn")

    def discard_pending_inference_capture(self, inference_index: int) -> None:
        self._ensure_inference_capture_state()
        if inference_index <= 0:
            return
        if self._active_inference_capture_index == inference_index:
            self._active_inference_capture_index = None
        else:
            try:
                self._pending_inference_capture_indexes.remove(inference_index)
            except ValueError:
                pass

        if inference_index == len(self.inference_inputs):
            self.inference_inputs.pop()
            return

        entry = self._inference_input_entry(inference_index)
        if entry is not None:
            entry["discarded"] = True

    def discard_active_inference_capture(self) -> int | None:
        self._ensure_inference_capture_state()
        inference_index = self._active_inference_capture_index
        if inference_index is None:
            return None
        self.discard_pending_inference_capture(inference_index)
        return inference_index

    def _resolve_event_payload_and_response_data(self, event_plan: EventPlan) -> tuple[Any, Any]:
        if event_plan.summary_factory is not None:
            summary = event_plan.summary_factory()
        else:
            summary = event_plan.summary

        if event_plan.payload_factory is not None:
            payload = event_plan.payload_factory()
        else:
            payload = event_plan.payload

        if summary is None:
            formatted_summary = self.event_summaries.summarize_event(event_plan.event_name, payload)
            if formatted_summary is not None:
                summary = formatted_summary

        response_data = summary if summary is not None else payload
        return payload, response_data

    def _schedule_event_delivery(self, event_plan: EventPlan) -> None:
        task = asyncio.create_task(self._deliver_event(event_plan))
        self._event_tasks.add(task)

        def _drop(done_task: asyncio.Task[Any]) -> None:
            self._event_tasks.discard(done_task)

        task.add_done_callback(_drop)

    async def _deliver_event(self, event_plan: EventPlan) -> None:
        try:
            if event_plan.delay_s > 0:
                await asyncio.sleep(event_plan.delay_s)

            if self.stop_requested:
                return
            if not self.pipeline_task or self.pipeline_task.has_finished():
                return

            if event_plan.mutation is not None:
                event_plan.mutation()

            event_payload, response_data = self._resolve_event_payload_and_response_data(event_plan)
            self.world.record_event(
                event_name=event_plan.event_name,
                response_data=response_data,
                event_payload=event_payload,
                source_tool=event_plan.source_tool,
            )

            if event_plan.event_name == "error":
                self.last_error_event = (
                    response_data if isinstance(response_data, dict) else {"error": str(response_data)}
                )

            # TaskAgent parity: selected sync tool events are emitted for logs but
            # not injected into LLM context to avoid duplicating sync tool payloads.
            skip_count = self._skip_context_events.get(event_plan.event_name, 0)
            if skip_count > 0:
                self._skip_context_events[event_plan.event_name] = skip_count - 1
                if self._skip_context_events[event_plan.event_name] == 0:
                    del self._skip_context_events[event_plan.event_name]
                return

            await self.pipeline_task.queue_frames(
                [
                    LLMMessagesAppendFrame(
                        messages=[_event_xml_message(event_plan.event_name, response_data)],
                        run_llm=False,
                    )
                ]
            )

            await self.controller.on_event(event_plan.event_name)

        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to deliver synthetic event {}: {}", event_plan.event_name, exc)

    def _complete_stop(self, terminal_reason: str) -> None:
        if self.stop_requested:
            return
        self.stop_requested = True
        self.terminal_reason = terminal_reason
        self.resolve_async_dependency_waiters(allow_execution=False)

        async def _queue_end() -> None:
            if self.pipeline_task and not self.pipeline_task.has_finished():
                try:
                    await self.pipeline_task.queue_frames([EndFrame()])
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to queue EndFrame: {}", exc)

        asyncio.create_task(_queue_end())
        self.done_event.set()

    def maybe_finalize_deferred_stop(self) -> None:
        if self.stop_requested:
            return
        if self._deferred_stop_reason is None:
            return
        if self.controller.has_pending_async_completions():
            return
        if self.has_async_dependency_waiters():
            return

        terminal_reason = self._deferred_stop_reason
        self._deferred_stop_reason = None
        self._complete_stop(terminal_reason)

    def request_stop(self, terminal_reason: str, *, wait_for_pending_async: bool = False) -> None:
        if self.stop_requested:
            return

        if wait_for_pending_async:
            self.inference_suppressed = True
            self.terminal_reason = terminal_reason
            if self.controller.has_pending_async_completions():
                self._deferred_stop_reason = terminal_reason
                return

        self._deferred_stop_reason = None
        self._complete_stop(terminal_reason)

    def has_async_dependency_waiters(self) -> bool:
        return any(not waiter.done() for waiter in self._async_dependency_waiters)

    def resolve_async_dependency_waiters(self, *, allow_execution: bool) -> None:
        if allow_execution and self.controller.has_pending_async_completions():
            return
        waiters = list(self._async_dependency_waiters)
        self._async_dependency_waiters.clear()
        for waiter in waiters:
            if not waiter.done():
                waiter.set_result(allow_execution)

    async def wait_for_async_dependency_resolution(self) -> bool:
        while self.controller.has_pending_async_completions() and not self.stop_requested:
            loop = asyncio.get_running_loop()
            waiter: asyncio.Future[bool] = loop.create_future()
            self._async_dependency_waiters.append(waiter)
            allow_execution = await waiter
            if not allow_execution:
                return False
        return not self.stop_requested

    async def handle_function_call(self, params: FunctionCallParams) -> None:
        tool_name = params.function_name
        arguments = params.arguments or {}
        properties = FunctionCallResultProperties(run_llm=False)

        if self.controller.has_pending_async_completions():
            can_execute = await self.wait_for_async_dependency_resolution()
            if not can_execute:
                payload = {
                    "status": "error",
                    "error_class": "async_dependency_unresolved",
                    "error": "Previous async tool call did not complete before this batched call could run.",
                    "tool": tool_name,
                }
                self.last_error_event = dict(payload)
                await params.result_callback(payload, properties=properties)
                if self.inference_suppressed:
                    self.maybe_finalize_deferred_stop()
                return

        if self.finished_called and tool_name != "finished":
            self.world.increment_bad_action()
            self.post_finished_call_count += 1
            payload = {
                "status": "error",
                "error_class": "post_finished_call",
                "error": "Tool call received after finished() in the same response batch.",
                "tool": tool_name,
            }
            self.last_error_event = dict(payload)
            await params.result_callback(payload, properties=properties)
            return

        if tool_name == "finished":
            self.finished_called = True
            message = str(arguments.get("message") or "Done").strip()
            self.finished_message = message or "Done"
            await params.result_callback(
                {"status": "completed", "message": self.finished_message},
                properties=properties,
            )
            self.request_stop("finished_tool", wait_for_pending_async=True)
            return

        is_async = tool_name in BENCHMARK_ASYNC_TOOL_COMPLETIONS
        expected_event = BENCHMARK_ASYNC_TOOL_COMPLETIONS.get(tool_name)
        sync_event_to_skip = BENCHMARK_SYNC_TOOL_EVENTS.get(tool_name)
        tool_call_id = params.tool_call_id or f"{tool_name}:{uuid.uuid4()}"

        if is_async and expected_event is not None:
            self.controller.register_async_completion(
                tool_call_id=tool_call_id,
                expected_event=expected_event,
                tool_name=tool_name,
            )

        if sync_event_to_skip is not None:
            self._skip_context_events[sync_event_to_skip] = (
                self._skip_context_events.get(sync_event_to_skip, 0) + 1
            )

        self.controller.set_tool_call_in_progress(True)
        try:
            execution = self.world.execute_tool(tool_name, dict(arguments))
        except Exception as exc:  # noqa: BLE001
            execution = self.world._error(tool_name, str(exc))  # type: ignore[attr-defined]
        finally:
            self.controller.set_tool_call_in_progress(False)

        if not execution.ok:
            if is_async:
                self.controller.cancel_async_completion(tool_call_id)
            if sync_event_to_skip is not None:
                remaining = self._skip_context_events.get(sync_event_to_skip, 0)
                if remaining <= 1:
                    self._skip_context_events.pop(sync_event_to_skip, None)
                else:
                    self._skip_context_events[sync_event_to_skip] = remaining - 1
            await params.result_callback(execution.payload, properties=properties)
            self.last_error_event = dict(execution.payload)
            await self.controller.request_inference(f"tool_error:{tool_name}")
            if self.inference_suppressed:
                self.maybe_finalize_deferred_stop()
            return

        if is_async:
            # Async tools mirror TaskAgent behavior: immediate minimal ack and
            # rerun is gated by completion event arrival.
            await params.result_callback({"status": "Executed."}, properties=properties)
            for event_plan in execution.events:
                self._schedule_event_delivery(event_plan)
            if self.inference_suppressed:
                self.maybe_finalize_deferred_stop()
            return

        # Sync tools (including sync tools that also emit events) return full
        # payload immediately and schedule a rerun. Selected duplicate sync
        # events are skipped from context by _deliver_event.
        await params.result_callback(execution.payload, properties=properties)
        for event_plan in execution.events:
            self._schedule_event_delivery(event_plan)
        await self.controller.request_inference(f"tool:{tool_name}")
        if self.inference_suppressed:
            self.maybe_finalize_deferred_stop()

    async def close(self) -> None:
        self.controller.close()
        for event_task in list(self._event_tasks):
            if not event_task.done():
                event_task.cancel()
        if self._event_tasks:
            await asyncio.gather(*self._event_tasks, return_exceptions=True)

    def build_summary(self) -> dict[str, Any]:
        total_ms = round((time.perf_counter() - self.started_monotonic) * 1000, 2)
        final_sector = self.world.state.sector
        final_credits = self.world.state.credits
        start_sector_raw = self.initial_state_snapshot.get("sector")
        start_sector = start_sector_raw if isinstance(start_sector_raw, int) else 3080
        expected_finish_sector = start_sector
        final_sector_matches_start = final_sector == expected_finish_sector
        final_sector_is_mega = final_sector == MEGA_PORT_SECTOR
        event_history = [event for event in self.world.event_history if isinstance(event, dict)]
        reached_mega_anytime = bool(
            final_sector_is_mega
            or any(event.get("sector") == MEGA_PORT_SECTOR for event in event_history)
            or any((turn.get("state_after") or {}).get("sector") == MEGA_PORT_SECTOR for turn in self.turn_logs)
        )

        recharge_units_total = 0
        recharge_cost_total = 0
        recharge_to_full_at_mega = False
        recharge_sector: Optional[int] = None
        recharge_events = [
            event
            for event in event_history
            if event.get("event_name") == "warp.purchase"
            and event.get("source_tool") == "recharge_warp_power"
        ]
        if recharge_events:
            for event in recharge_events:
                payload = _event_payload_as_dict(event)

                units = payload.get("units")
                if isinstance(units, int) and units > 0:
                    recharge_units_total += units

                total_cost = payload.get("total_cost")
                if isinstance(total_cost, (int, float)) and total_cost > 0:
                    recharge_cost_total += int(total_cost)

                sector = event.get("sector")
                if isinstance(sector, int) and sector == MEGA_PORT_SECTOR:
                    recharge_sector = sector
                    new_warp = payload.get("new_warp_power")
                    warp_capacity = payload.get("warp_power_capacity")
                    if (
                        isinstance(new_warp, int)
                        and isinstance(warp_capacity, int)
                        and new_warp >= warp_capacity
                    ):
                        recharge_to_full_at_mega = True
        else:
            for turn in self.turn_logs:
                tool_calls = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
                has_successful_recharge_call = any(
                    isinstance(call, dict)
                    and call.get("name") == "recharge_warp_power"
                    and str(call.get("result_status") or "") in {"acknowledged", "success"}
                    for call in tool_calls
                )
                if not has_successful_recharge_call:
                    continue

                state_before = turn.get("state_before") if isinstance(turn.get("state_before"), dict) else {}
                state_after = turn.get("state_after") if isinstance(turn.get("state_after"), dict) else {}

                before_warp = state_before.get("warp")
                after_warp = state_after.get("warp")
                if isinstance(before_warp, int) and isinstance(after_warp, int) and after_warp > before_warp:
                    recharge_units_total += after_warp - before_warp

                before_credits = state_before.get("credits")
                after_credits = state_after.get("credits")
                if (
                    isinstance(before_credits, (int, float))
                    and isinstance(after_credits, (int, float))
                    and before_credits > after_credits
                ):
                    recharge_cost_total += int(before_credits - after_credits)

                sector_after = state_after.get("sector")
                sector_before = state_before.get("sector")
                sector = sector_after if isinstance(sector_after, int) else sector_before
                if isinstance(sector, int) and sector == MEGA_PORT_SECTOR:
                    recharge_sector = sector
                    max_warp = state_after.get("max_warp")
                    if isinstance(after_warp, int) and isinstance(max_warp, int) and after_warp >= max_warp:
                        recharge_to_full_at_mega = True

        coherent_report = False
        if self.finished_message:
            coherent_report = _is_coherent_finished_report(self.finished_message)

        success = bool(
            self.finished_message
            and final_sector_matches_start
            and reached_mega_anytime
            and recharge_to_full_at_mega
            and coherent_report
        )

        tool_call_counts = [len(turn.get("tool_calls") or []) for turn in self.turn_logs]
        multi_call_turn_count = sum(1 for count in tool_call_counts if count > 1)
        avg_tool_calls = (
            round(sum(tool_call_counts) / len(tool_call_counts), 3) if tool_call_counts else 0.0
        )
        max_tool_calls = max(tool_call_counts) if tool_call_counts else 0

        summary = {
            "schema_version": RUN_SCHEMA_VERSION,
            "success": success,
            "success_legacy": success,
            "bad_actions_count": self.world.bad_actions_count,
            "no_tool_call_count": self.no_tool_call_count,
            "post_finished_call_count": self.post_finished_call_count,
            "async_completion_timeout_count": self.async_completion_timeout_count,
            "multi_call_turn_count": multi_call_turn_count,
            "avg_tool_calls_per_turn": avg_tool_calls,
            "max_tool_calls_per_turn": max_tool_calls,
            "finished_message": self.finished_message,
            "start_sector": start_sector,
            "expected_finish_sector": expected_finish_sector,
            "final_sector": final_sector,
            "final_credits": final_credits,
            "final_sector_matches_start": final_sector_matches_start,
            "reached_mega": reached_mega_anytime,
            "final_sector_is_mega": final_sector_is_mega,
            "reached_mega_anytime": reached_mega_anytime,
            "recharge_sector": recharge_sector,
            "recharge_units_total": recharge_units_total,
            "recharge_cost_total": recharge_cost_total,
            "recharge_to_full_at_mega": recharge_to_full_at_mega,
            "coherent_report": coherent_report,
            "finished_called": self.finished_called,
            "terminal_reason": self.terminal_reason,
            "turns_executed": len(self.turn_logs),
            "elapsed_ms": total_ms,
            "provider": self.args.provider,
            "model": self.args.model,
            "openai_no_budget_thinking_toggle": getattr(self.args, "openai_no_budget_thinking_toggle", False),
            "thinking": self.args.thinking,
            "thinking_budget": self.args.thinking_budget,
            "max_tokens": self.args.max_tokens,
            "llm_request_timeout_secs": getattr(self.args, "llm_request_timeout_secs", None),
            "llm_stream_idle_timeout_secs": getattr(
                self.args, "llm_stream_idle_timeout_secs", None
            ),
            "pipeline_idle_timeout_secs": getattr(
                self.args, "pipeline_idle_timeout_secs", None
            ),
        }
        if getattr(self.args, "round_id", None) is not None:
            summary["round_id"] = self.args.round_id
        if getattr(self.args, "effective_effort", None) is not None:
            summary["reasoning_effort"] = getattr(self.args, "reasoning_effort", None)
            summary["effective_effort"] = self.args.effective_effort
        if getattr(self, "transport_empty_retry_enabled", False):
            summary["empty_response_count"] = getattr(self, "empty_response_count", 0)
            summary["empty_response_retry_success_count"] = getattr(
                self,
                "empty_response_retry_success_count",
                0,
            )
        if getattr(self, "rate_limit_retry_enabled", False):
            summary["rate_limit_count"] = getattr(self, "rate_limit_count", 0)
            summary["rate_limit_retry_success_count"] = getattr(
                self,
                "rate_limit_retry_success_count",
                0,
            )
        return summary

    def build_output_payload(
        self,
        *,
        partial: bool = False,
        checkpoint_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        summary = self.build_summary()
        ended_at_utc = None if partial else _iso_utc_now()
        config_snapshot = self.build_config_snapshot()
        metadata = self.build_metadata_snapshot(ended_at_utc=ended_at_utc)
        termination = self.build_termination_snapshot(elapsed_ms=summary.get("elapsed_ms"))
        if partial:
            termination["reason"] = "checkpoint_partial"
        payload = {
            "schema_version": RUN_SCHEMA_VERSION,
            "metadata": metadata,
            "config": config_snapshot,
            "termination": termination,
            "summary": summary,
            "turns": self.turn_logs,
        }
        if self.args.capture_inference_inputs and not partial:
            payload["inference_inputs"] = self.inference_inputs
        if self.responses_traces:
            payload["responses_traces"] = list(self.responses_traces)
        if partial:
            payload["checkpoint"] = {
                "partial": True,
                "reason": checkpoint_reason or "inference_in_progress",
                "written_at_utc": _iso_utc_now(),
                "omitted_fields": ["inference_inputs"]
                if self.args.capture_inference_inputs
                else [],
            }
        return payload

    def write_partial_checkpoint(self, *, reason: str) -> None:
        log_json = getattr(self.args, "log_json", None)
        if not log_json or getattr(
            self.args, "pipeline_idle_timeout_secs", None
        ) is None:
            return
        payload = self.build_output_payload(partial=True, checkpoint_reason=reason)
        _atomic_write_json(Path(log_json), payload)
        logger.info(
            "CHECKPOINT {} reason={} turns={} traces={}",
            log_json,
            reason,
            len(self.turn_logs),
            len(self.responses_traces),
        )


async def _run_benchmark(args: argparse.Namespace) -> int:
    provider = _provider_from_str(args.provider)

    if provider == LLMProvider.OPENAI and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "dummy"

    assert_catalog_parity()

    if _is_gpt56_responses_model(args.model, args.openai_base_url):
        if getattr(args, "llm_request_timeout_secs", None) is None:
            args.llm_request_timeout_secs = 900.0
        if getattr(args, "llm_stream_idle_timeout_secs", None) is None:
            args.llm_stream_idle_timeout_secs = 600.0
    args.pipeline_idle_timeout_secs = _resolve_gpt56_pipeline_idle_timeout_secs(args)

    args.effective_effort = _resolve_gpt56_effective_effort(
        model=args.model,
        openai_base_url=args.openai_base_url,
        thinking=args.thinking,
        reasoning_effort=getattr(args, "reasoning_effort", None),
    )

    config = LLMServiceConfig(
        provider=provider,
        model=args.model,
        thinking=None,
        max_tokens=args.max_tokens,
        function_call_timeout_secs=args.function_call_timeout_secs,
        run_in_parallel=False,
        openai_base_url=args.openai_base_url,
        openai_params=args.openai_params,
        llm_request_timeout_secs=getattr(args, "llm_request_timeout_secs", None),
        llm_stream_idle_timeout_secs=getattr(args, "llm_stream_idle_timeout_secs", None),
    )
    llm_service = create_llm_service(config)
    tool_call_streaming_workaround = _apply_openai_non_streaming_tool_call_workaround(
        llm_service=llm_service,
        provider=provider,
        model=args.model,
        openai_base_url=args.openai_base_url,
    )
    thinking_policy = _apply_benchmark_thinking_mode(
        llm_service=llm_service,
        provider=provider,
        model=args.model,
        thinking=args.thinking,
        thinking_budget=args.thinking_budget,
        openai_base_url=args.openai_base_url,
        openai_no_budget_thinking_toggle=getattr(args, "openai_no_budget_thinking_toggle", False),
        reasoning_effort=getattr(args, "reasoning_effort", None),
    )

    harness_dir = Path(__file__).resolve().parent
    system_instruction_path = harness_dir / "system_instruction.txt"
    system_instruction = _load_system_instruction(system_instruction_path)
    reasoning_prefix = _system_reasoning_prefix_for_model(
        provider=provider,
        model=args.model,
        thinking=args.thinking,
        openai_base_url=args.openai_base_url,
    )
    if reasoning_prefix:
        system_instruction = f"{reasoning_prefix}\n\n{system_instruction}"

    world = SyntheticWorld()
    runtime = _BenchmarkRuntime(
        args=args,
        llm_service=llm_service,
        world=world,
        system_instruction=system_instruction,
        system_instruction_path=system_instruction_path,
    )
    set_outcome_callback = getattr(llm_service, "set_benchmark_outcome_callback", None)
    if callable(set_outcome_callback):
        set_outcome_callback(runtime.record_responses_trace)
    rate_limit_retry_policy = _apply_baseten_rate_limit_retry_wrapper(
        llm_service=llm_service,
        provider=provider,
        openai_base_url=args.openai_base_url,
        runtime=runtime,
    )

    logger.info(
        "HARNESS_CONFIG provider={} model={} openai_base_url={} thinking={} reasoning_effort={} effective_effort={} round_id={} thinking_budget={} openai_no_budget_thinking_toggle={} thinking_policy={} tool_call_workaround={} rate_limit_retry={} max_tokens={} max_turns={} llm_request_timeout_secs={} llm_stream_idle_timeout_secs={} pipeline_idle_timeout_secs={}",
        provider.value,
        args.model,
        args.openai_base_url or "(default)",
        args.thinking,
        getattr(args, "reasoning_effort", None) or "(mapped)",
        getattr(args, "effective_effort", None) or "(n/a)",
        getattr(args, "round_id", None) or "(none)",
        args.thinking_budget if args.thinking_budget is not None else "(mapped)",
        getattr(args, "openai_no_budget_thinking_toggle", False),
        thinking_policy,
        tool_call_streaming_workaround,
        rate_limit_retry_policy,
        args.max_tokens,
        args.max_turns,
        getattr(args, "llm_request_timeout_secs", None),
        getattr(args, "llm_stream_idle_timeout_secs", None),
        getattr(args, "pipeline_idle_timeout_secs", None),
    )

    pipeline_task: Optional[PipelineTask] = None
    runner_task: Optional[asyncio.Task[Any]] = None
    interrupted = False
    try:
        pipeline_task, runner_task = await runtime.setup_pipeline()
        await runtime.controller.queue_initial_run()

        def _runner_done(task: asyncio.Task[Any]) -> None:
            if task.cancelled():
                if not runtime.stop_requested:
                    runtime.request_stop("inference_failure")
                return
            exc = task.exception()
            if exc is not None and not runtime.stop_requested:
                runtime.world.increment_bad_action()
                runtime.last_error_event = {
                    "endpoint": "inference",
                    "error": str(exc),
                    "source": {"type": "pipeline"},
                    "synthesized": True,
                    "status": 500,
                }
                runtime.turn_logs.append(
                    {
                        "llm_turn": runtime.turn_count + 1,
                        "decision_ms": 0.0,
                        "tool_calls": [],
                        "raw_response_text": "",
                        "failure_class": "inference_failure",
                        "bad_actions_before": runtime.world.bad_actions_count - 1,
                        "bad_actions_after": runtime.world.bad_actions_count,
                        "bad_action_increment": 1,
                        "state_before": runtime.world.state_snapshot(),
                        "state_after": runtime.world.state_snapshot(),
                        "error_event": runtime.last_error_event,
                    }
                )
                runtime.attach_active_inference_capture(runtime.turn_logs[-1])
                runtime.turn_count += 1
                runtime._append_replay_stream_event("turn", turn=runtime.turn_logs[-1])
                runtime.request_stop("inference_failure")
                runtime.write_partial_checkpoint(reason="pipeline_failure")

        runner_task.add_done_callback(_runner_done)

        try:
            await runtime.done_event.wait()
        except asyncio.CancelledError:
            interrupted = True
            if not runtime.stop_requested:
                runtime.request_stop("interrupted")
            logger.warning("Benchmark run interrupted; proceeding with partial summary/output.")

    finally:
        if pipeline_task and not pipeline_task.has_finished():
            try:
                await pipeline_task.queue_frames([EndFrame()])
            except Exception:  # noqa: BLE001
                pass

        if runner_task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(runner_task), timeout=PIPELINE_GRACEFUL_SHUTDOWN_TIMEOUT)
            except asyncio.TimeoutError:
                runner_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await runner_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001
                logger.debug("Runner task ended with error during shutdown: {}", exc)

        await runtime.close()

    summary = runtime.build_summary()

    print(f"SUCCESS={summary['success']}")
    print(f"TERMINAL_REASON={summary['terminal_reason']}")
    print(f"BAD_ACTIONS_COUNT={summary['bad_actions_count']}")
    print(f"NO_TOOL_CALL_COUNT={summary['no_tool_call_count']}")
    print(f"FINAL_SECTOR={summary['final_sector']}")
    print(f"FINAL_SECTOR_MATCHES_START={summary['final_sector_matches_start']}")
    print(f"RECHARGE_TO_FULL_AT_MEGA={summary['recharge_to_full_at_mega']}")
    print(f"COHERENT_REPORT={summary['coherent_report']}")
    print(f"TURNS={summary['turns_executed']}")
    print(f"ELAPSED_MS={summary['elapsed_ms']}")
    if "rate_limit_count" in summary:
        print(f"RATE_LIMIT_COUNT={summary['rate_limit_count']}")
        print(f"RATE_LIMIT_RETRY_SUCCESS_COUNT={summary['rate_limit_retry_success_count']}")
    if summary.get("finished_message"):
        print(f"FINISH_MESSAGE={summary['finished_message']}")

    if args.log_json:
        payload = runtime.build_output_payload()
        runtime._append_replay_stream_event(
            "summary",
            summary=payload.get("summary"),
            termination=payload.get("termination"),
        )
        _atomic_write_json(Path(args.log_json), payload)
        runtime._append_replay_stream_event("output_written", path=args.log_json)
        logger.info("WROTE {}", args.log_json)
    else:
        runtime._append_replay_stream_event(
            "summary",
            summary=summary,
            termination=runtime.build_termination_snapshot(elapsed_ms=summary.get("elapsed_ms")),
        )

    if interrupted:
        return 130
    return 0 if summary.get("success") else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run standalone mini RL benchmark harness")
    parser.add_argument(
        "--task",
        default=None,
        help="Custom task prompt override. If provided, it overrides --task-variant.",
    )
    parser.add_argument(
        "--task-variant",
        default=DEFAULT_TASK_VARIANT,
        choices=sorted(TASK_PROMPTS.keys()),
        help="Built-in task prompt variant to use when --task is not provided.",
    )
    parser.add_argument(
        "--provider",
        default=os.getenv("TASK_LLM_PROVIDER", "openai"),
        choices=["openai", "google", "anthropic", "cerebras"],
        help="LLM provider",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("TASK_LLM_MODEL", "nemotron-3-super-120b"),
        help="Model name",
    )
    parser.add_argument(
        "--openai-base-url",
        default=None,
        help="OpenAI-compatible base URL (with or without /v1)",
    )
    parser.add_argument(
        "--openai-params-json",
        default=os.getenv("TASK_LLM_OPENAI_PARAMS_JSON"),
        help=(
            "Optional JSON object merged into OpenAI InputParams "
            "(example: '{\"temperature\":0.2,\"extra\":{\"extra_body\":{\"top_k\":40}}}')"
        ),
    )
    parser.add_argument(
        "--openai-no-budget-thinking-toggle",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "For supported OpenAI-compatible Nemotron endpoints, send "
            "chat_template_kwargs.enable_thinking and omit thinking_budget. "
            "Supports --thinking none|high only."
        ),
    )
    parser.add_argument(
        "--thinking",
        default=_default_thinking_level(),
        choices=list(THINKING_LEVELS),
        help="Benchmark thinking level: none|minimal|low|medium|high",
    )
    parser.add_argument(
        "--thinking-budget",
        default=os.getenv("TASK_LLM_THINKING_BUDGET"),
        help=(
            "Optional exact numeric thinking budget override. When set, it overrides "
            "the benchmark --thinking mapping on providers/models that expose exact budgets."
        ),
    )
    parser.add_argument(
        "--reasoning-effort",
        default=None,
        choices=list(GPT56_REASONING_EFFORTS),
        help=(
            "Exact GPT-5.6 Responses reasoning effort override. Valid only for hosted "
            "gpt-5.6-luna/sol/terra; distinct from the requested --thinking label."
        ),
    )
    parser.add_argument(
        "--round-id",
        default=None,
        help="Optional deterministic round identity (the GPT-5.6 runner uses r01...r25).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional per-turn max tokens override",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=50,
        help="Max inference turns before hard stop",
    )
    parser.add_argument(
        "--function-call-timeout-secs",
        type=float,
        default=float(os.getenv("TASK_LLM_FUNCTION_CALL_TIMEOUT_SECS", "20")),
        help="LLM function call timeout passed to service config",
    )
    parser.add_argument(
        "--llm-request-timeout-secs",
        type=float,
        default=None,
        help="Total wall timeout for one hosted GPT-5.6 Responses request (default: 900).",
    )
    parser.add_argument(
        "--llm-stream-idle-timeout-secs",
        type=float,
        default=None,
        help="Maximum idle wait between GPT-5.6 Responses events (default: 600).",
    )
    parser.add_argument(
        "--log-json",
        default=None,
        help="Optional output file for structured run logs",
    )
    parser.add_argument(
        "--capture-inference-inputs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include full pre-inference context snapshots in structured outputs and replay streams.",
    )
    parser.add_argument(
        "--replay-stream-jsonl",
        default=None,
        help="Optional append-only JSONL stream for live replay observers.",
    )
    return parser


def main() -> int:
    logger.configure(handlers=[{"sink": sys.stderr, "level": os.getenv("LOGURU_LEVEL", "INFO")}])
    parser = _build_parser()
    args = parser.parse_args()
    try:
        args.thinking_budget = _parse_optional_nonnegative_int(
            args.thinking_budget,
            label="--thinking-budget",
        )
        args.openai_params = _parse_optional_json_dict(
            args.openai_params_json,
            label="--openai-params-json",
        )
    except ValueError as exc:
        parser.error(str(exc))
    _validate_generation_controls(args, parser)
    try:
        resolved_task, resolved_task_variant, resolved_task_prompt_version = _resolve_task_prompt(
            task=args.task,
            task_variant=args.task_variant,
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.task = resolved_task
    args.task_variant = resolved_task_variant
    args.task_prompt_version = resolved_task_prompt_version
    try:
        return asyncio.run(_run_benchmark(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
