"""Minimal local LLM service factory used by the standalone benchmark harness."""

from __future__ import annotations

import os
import urllib.parse
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from loguru import logger
from pipecat.services.llm_service import LLMService


class LLMProvider(Enum):
    GOOGLE = "google"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    CEREBRAS = "cerebras"


@dataclass
class UnifiedThinkingConfig:
    enabled: bool = True
    budget_tokens: int = 2048
    include_thoughts: bool = True


@dataclass
class LLMServiceConfig:
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    thinking: Optional[UnifiedThinkingConfig] = None
    max_tokens: Optional[int] = None
    function_call_timeout_secs: Optional[float] = None
    run_in_parallel: Optional[bool] = None
    openai_base_url: Optional[str] = None
    openai_params: Optional[dict[str, Any]] = None
    llm_request_timeout_secs: Optional[float] = None
    llm_stream_idle_timeout_secs: Optional[float] = None


def _is_google_thinking_level_model(model: str) -> bool:
    normalized = model.strip().lower()
    return normalized.startswith("gemini-3") or normalized.startswith("supernova")


def _google_budget_to_thinking_level(budget_tokens: int) -> str:
    if budget_tokens <= 0:
        return "minimal"
    if budget_tokens <= 128:
        return "low"
    if budget_tokens <= 512:
        return "medium"
    return "high"


def _normalize_openai_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    # Allow users to pass a full chat completions endpoint for local servers.
    if normalized.endswith("/chat/completions"):
        return normalized[: -len("/chat/completions")]
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


def _is_openrouter_laguna_model(model: str, openai_base_url: Optional[str]) -> bool:
    if not openai_base_url:
        return False
    host = (urllib.parse.urlparse(openai_base_url).hostname or "").lower()
    normalized_model = model.strip().lower()
    return host in {"openrouter.ai", "www.openrouter.ai"} and normalized_model in {
        "poolside/laguna-s-2.1",
        "poolside/laguna-s-2.1-20260720",
    }


def _is_openrouter_qwen36_model(model: str, openai_base_url: Optional[str]) -> bool:
    if not openai_base_url:
        return False
    host = (urllib.parse.urlparse(openai_base_url).hostname or "").lower()
    normalized_model = model.strip().lower()
    return host in {"openrouter.ai", "www.openrouter.ai"} and normalized_model.startswith(
        "qwen/qwen3.6-"
    )


def _is_baseten_qwen36_model(model: str, openai_base_url: Optional[str]) -> bool:
    if not openai_base_url:
        return False
    host = (urllib.parse.urlparse(openai_base_url).hostname or "").lower()
    normalized_model = model.strip().lower()
    return host.endswith(".baseten.co") and normalized_model in {
        "qwen/qwen3.6-27b",
        "qwen/qwen3.6-35b-a3b-fp8",
    }


GPT56_RESPONSES_MODELS = frozenset(
    {
        "gpt-5.6-luna",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
    }
)


def _is_gpt56_responses_model(model: str, openai_base_url: Optional[str]) -> bool:
    """Return the full routing decision for the exact hosted GPT-5.6 set."""

    normalized = (model or "").strip().lower()
    return openai_base_url is None and normalized in GPT56_RESPONSES_MODELS


def _is_openai_responses_model(model: str, openai_base_url: Optional[str]) -> bool:
    normalized = model.strip().lower()
    return (
        openai_base_url is None and normalized.startswith("gpt-5.4")
    ) or _is_gpt56_responses_model(model, openai_base_url)


def _merge_openai_extra(existing_extra: Any, *, thinking_budget: int) -> dict[str, Any]:
    merged_extra = dict(existing_extra) if isinstance(existing_extra, dict) else {}

    extra_body = merged_extra.get("extra_body")
    merged_extra_body = dict(extra_body) if isinstance(extra_body, dict) else {}

    vllm_xargs = merged_extra_body.get("vllm_xargs")
    merged_vllm_xargs = dict(vllm_xargs) if isinstance(vllm_xargs, dict) else {}
    merged_vllm_xargs["thinking_budget"] = int(thinking_budget)

    merged_extra_body["vllm_xargs"] = merged_vllm_xargs
    merged_extra["extra_body"] = merged_extra_body
    return merged_extra


def _get_api_key(provider: LLMProvider, override: Optional[str] = None) -> str:
    if override:
        return override

    env_var_map = {
        LLMProvider.GOOGLE: "GOOGLE_API_KEY",
        LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
        LLMProvider.OPENAI: "OPENAI_API_KEY",
        LLMProvider.CEREBRAS: "CEREBRAS_API_KEY",
    }
    env_var = env_var_map[provider]
    value = os.getenv(env_var)
    if not value:
        raise ValueError(f"{provider.value.capitalize()} API key required. Set {env_var}.")
    return value


def create_llm_service(config: LLMServiceConfig) -> LLMService:
    api_key = _get_api_key(config.provider, config.api_key)

    if config.provider == LLMProvider.GOOGLE:
        service = _create_google_service(
            api_key=api_key,
            model=config.model,
            thinking=config.thinking,
            function_call_timeout_secs=config.function_call_timeout_secs,
        )
    elif config.provider == LLMProvider.ANTHROPIC:
        service = _create_anthropic_service(
            api_key=api_key,
            model=config.model,
            thinking=config.thinking,
            function_call_timeout_secs=config.function_call_timeout_secs,
        )
    elif config.provider == LLMProvider.OPENAI:
        service = _create_openai_service(
            api_key=api_key,
            model=config.model,
            thinking=config.thinking,
            max_tokens=config.max_tokens,
            function_call_timeout_secs=config.function_call_timeout_secs,
            openai_base_url=config.openai_base_url,
            openai_params=config.openai_params,
            llm_request_timeout_secs=config.llm_request_timeout_secs,
            llm_stream_idle_timeout_secs=config.llm_stream_idle_timeout_secs,
        )
    elif config.provider == LLMProvider.CEREBRAS:
        service = _create_cerebras_service(
            api_key=api_key,
            model=config.model,
            function_call_timeout_secs=config.function_call_timeout_secs,
        )
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")

    if config.run_in_parallel is not None:
        service._run_in_parallel = config.run_in_parallel
    return service


def _create_google_service(
    *,
    api_key: str,
    model: str,
    thinking: Optional[UnifiedThinkingConfig],
    function_call_timeout_secs: Optional[float],
) -> LLMService:
    from pipecat.services.google.llm import GoogleLLMService

    params = None
    if thinking and thinking.enabled:
        if _is_google_thinking_level_model(model):
            params = GoogleLLMService.InputParams(
                thinking=GoogleLLMService.ThinkingConfig(
                    thinking_level=_google_budget_to_thinking_level(thinking.budget_tokens),
                    include_thoughts=thinking.include_thoughts,
                )
            )
        else:
            params = GoogleLLMService.InputParams(
                thinking=GoogleLLMService.ThinkingConfig(
                    thinking_budget=thinking.budget_tokens,
                    include_thoughts=thinking.include_thoughts,
                )
            )

    kwargs: dict[str, object] = {}
    if params is not None:
        kwargs["params"] = params
    if function_call_timeout_secs is not None:
        kwargs["function_call_timeout_secs"] = function_call_timeout_secs

    return GoogleLLMService(
        api_key=api_key,
        model=model,
        **kwargs,
    )


def _install_anthropic_thinking_roundtrip_fix() -> None:
    """Runtime monkeypatch: tolerate empty-thinking assistant turns in the Anthropic adapter.

    Newer adaptive Anthropic models (Sonnet 5, Opus 4.7/4.8, Fable) return thinking
    blocks with empty text when thinking is disabled (``--thinking none``) or when the
    model's ``display`` defaults to ``"omitted"``. pipecat stores these as "thought"
    LLMSpecificMessages; on the next turn ``AnthropicLLMAdapter._from_anthropic_specific_message``
    hits its fallthrough and returns the raw thought dict, which has no ``"role"`` key,
    raising ``KeyError: 'role'`` in ``_from_universal_context_messages``. We wrap that
    method so a role-less result becomes a benign empty assistant turn (which pipecat's
    consecutive-message merge folds into the adjacent assistant content). Idempotent;
    patches the in-memory class only -- it does not modify the installed package on disk.
    """
    from pipecat.adapters.services.anthropic_adapter import AnthropicLLMAdapter

    if getattr(AnthropicLLMAdapter, "_gb_thinking_roundtrip_fix", False):
        return

    _orig_from_specific = AnthropicLLMAdapter._from_anthropic_specific_message

    def _from_anthropic_specific_message(self, message):
        result = _orig_from_specific(self, message)
        if not (isinstance(result, dict) and "role" in result):
            # Empty/blank "thought" fallthrough -> emit a benign, role-carrying
            # assistant turn instead of a role-less dict.
            return {"role": "assistant", "content": []}
        return result

    AnthropicLLMAdapter._from_anthropic_specific_message = _from_anthropic_specific_message
    AnthropicLLMAdapter._gb_thinking_roundtrip_fix = True
    logger.info("Installed AnthropicLLMAdapter empty-thinking round-trip monkeypatch")


def _create_anthropic_service(
    *,
    api_key: str,
    model: str,
    thinking: Optional[UnifiedThinkingConfig],
    function_call_timeout_secs: Optional[float],
) -> LLMService:
    from pipecat.services.anthropic.llm import AnthropicLLMService

    _install_anthropic_thinking_roundtrip_fix()

    params_kwargs: dict[str, object] = {"enable_prompt_caching": True}
    if thinking and thinking.enabled:
        params_kwargs["thinking"] = AnthropicLLMService.ThinkingConfig(
            type="enabled",
            budget_tokens=max(1024, thinking.budget_tokens),
        )
    params = AnthropicLLMService.InputParams(**params_kwargs)

    kwargs: dict[str, object] = {"params": params}
    if function_call_timeout_secs is not None:
        kwargs["function_call_timeout_secs"] = function_call_timeout_secs

    return AnthropicLLMService(
        api_key=api_key,
        model=model,
        **kwargs,
    )


def _create_openai_service(
    *,
    api_key: str,
    model: str,
    thinking: Optional[UnifiedThinkingConfig],
    max_tokens: Optional[int],
    function_call_timeout_secs: Optional[float],
    openai_base_url: Optional[str],
    openai_params: Optional[dict[str, Any]],
    llm_request_timeout_secs: Optional[float] = None,
    llm_stream_idle_timeout_secs: Optional[float] = None,
) -> LLMService:
    uses_responses = _is_openai_responses_model(model, openai_base_url)
    is_gpt56_responses = _is_gpt56_responses_model(model, openai_base_url)
    if uses_responses:
        from openai_responses_service import OpenAIResponsesLLMService as OpenAIServiceClass
    elif _is_openrouter_laguna_model(
        model, openai_base_url
    ) or _is_openrouter_qwen36_model(model, openai_base_url):
        from openrouter_reasoning_service import (
            OpenRouterReasoningLLMService as OpenAIServiceClass,
        )
    elif _is_baseten_qwen36_model(model, openai_base_url):
        from baseten_qwen_reasoning_service import (
            BasetenQwenReasoningLLMService as OpenAIServiceClass,
        )
    else:
        from pipecat.services.openai.llm import OpenAILLMService as OpenAIServiceClass

    normalized_base_url = _normalize_openai_base_url(openai_base_url) if openai_base_url else None

    params_kwargs: dict[str, Any] = dict(openai_params or {})
    if max_tokens is not None:
        # The explicit harness flag wins over any raw OpenAI param overrides.
        params_kwargs["max_tokens"] = int(max_tokens)
        params_kwargs.pop("max_completion_tokens", None)

    if thinking and thinking.enabled and normalized_base_url:
        existing_extra = params_kwargs.get("extra")
        params_kwargs["extra"] = _merge_openai_extra(
            existing_extra,
            thinking_budget=thinking.budget_tokens,
        )
    elif thinking and thinking.enabled:
        logger.warning(
            "OpenAI thinking budget requested for model {} without custom base URL; "
            "continuing without thinking extras.",
            model,
        )

    params = OpenAIServiceClass.InputParams(**params_kwargs) if params_kwargs else None

    kwargs: dict[str, object] = {}
    if function_call_timeout_secs is not None:
        kwargs["function_call_timeout_secs"] = function_call_timeout_secs
    if normalized_base_url:
        kwargs["base_url"] = normalized_base_url
    if params is not None:
        kwargs["params"] = params
    if is_gpt56_responses:
        kwargs["benchmark_observability_enabled"] = True
        if llm_request_timeout_secs is not None:
            kwargs["request_timeout_secs"] = float(llm_request_timeout_secs)
        if llm_stream_idle_timeout_secs is not None:
            kwargs["stream_idle_timeout_secs"] = float(llm_stream_idle_timeout_secs)

    return OpenAIServiceClass(
        api_key=api_key,
        model=model,
        **kwargs,
    )


def _create_cerebras_service(
    *,
    api_key: str,
    model: str,
    function_call_timeout_secs: Optional[float],
) -> LLMService:
    from pipecat.services.cerebras.llm import CerebrasLLMService

    # Cerebras Kimi K2.6 guide sampling defaults (Thinking mode). Instant-mode
    # temperature (0.6) and reasoning_effort="none" are applied post-construction
    # in mini-rl-env._apply_benchmark_thinking_mode, which mutates _settings.
    params = CerebrasLLMService.InputParams(temperature=1.0, top_p=0.95)

    kwargs: dict[str, object] = {"params": params}
    if function_call_timeout_secs is not None:
        kwargs["function_call_timeout_secs"] = function_call_timeout_secs

    # CerebrasLLMService defaults base_url to https://api.cerebras.ai/v1.
    return CerebrasLLMService(
        api_key=api_key,
        model=model,
        **kwargs,
    )
