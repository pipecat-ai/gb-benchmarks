"""Minimal local LLM service factory used by the standalone benchmark harness."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

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
    function_call_timeout_secs: Optional[float] = None
    run_in_parallel: Optional[bool] = None
    openai_base_url: Optional[str] = None


def _normalize_openai_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


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
            function_call_timeout_secs=config.function_call_timeout_secs,
            openai_base_url=config.openai_base_url,
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
    function_call_timeout_secs: Optional[float],
    openai_base_url: Optional[str],
) -> LLMService:
    from pipecat.services.openai.llm import OpenAILLMService

    normalized_base_url = _normalize_openai_base_url(openai_base_url) if openai_base_url else None

    params = None
    if thinking and thinking.enabled and normalized_base_url:
        params = OpenAILLMService.InputParams(
            extra={"extra_body": {"vllm_xargs": {"thinking_budget": int(thinking.budget_tokens)}}}
        )
    elif thinking and thinking.enabled:
        logger.warning(
            "OpenAI thinking budget requested for model {} without custom base URL; "
            "continuing without thinking extras.",
            model,
        )

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
