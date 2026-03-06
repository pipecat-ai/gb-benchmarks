"""Minimal local LLM service factory used by the standalone benchmark harness."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from loguru import logger
from pipecat.services.llm_service import LLMService


class LLMProvider(Enum):
    GOOGLE = "google"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


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


def _create_anthropic_service(
    *,
    api_key: str,
    model: str,
    thinking: Optional[UnifiedThinkingConfig],
    function_call_timeout_secs: Optional[float],
) -> LLMService:
    from pipecat.services.anthropic.llm import AnthropicLLMService

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
) -> LLMService:
    from pipecat.services.openai.llm import OpenAILLMService

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

    params = OpenAILLMService.InputParams(**params_kwargs) if params_kwargs else None

    kwargs: dict[str, object] = {}
    if function_call_timeout_secs is not None:
        kwargs["function_call_timeout_secs"] = function_call_timeout_secs
    if normalized_base_url:
        kwargs["base_url"] = normalized_base_url
    if params is not None:
        kwargs["params"] = params

    return OpenAILLMService(
        api_key=api_key,
        model=model,
        **kwargs,
    )
