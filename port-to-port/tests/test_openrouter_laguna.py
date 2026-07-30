"""Laguna S 2.1 OpenRouter routing and reasoning-history tests."""

import argparse
import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path

from pipecat.frames.frames import FunctionCallInProgressFrame
from pipecat.processors.aggregators.llm_context import LLMContext


PORT_TO_PORT_DIR = Path(__file__).resolve().parents[1]
if str(PORT_TO_PORT_DIR) not in sys.path:
    sys.path.insert(0, str(PORT_TO_PORT_DIR))

import llm_factory  # noqa: E402
from openrouter_reasoning_service import (  # noqa: E402
    OpenRouterReasoningAssistantAggregator,
    OpenRouterReasoningLLMService,
    _pending_reasoning,
    _reasoning_delta_text,
)


def _load_module(name: str, relative_path: str):
    path = PORT_TO_PORT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mini_rl_env = _load_module("mini_rl_env_openrouter_laguna_test", "mini-rl-env.py")


class CapturingArgumentParser(argparse.ArgumentParser):
    def error(self, message):  # type: ignore[override]
        raise ValueError(message)


class OpenRouterLagunaTests(unittest.TestCase):
    BASE_URL = "https://openrouter.ai/api/v1"
    MODEL = "poolside/laguna-s-2.1"

    def test_exact_route_selects_reasoning_service(self) -> None:
        service = llm_factory.create_llm_service(
            llm_factory.LLMServiceConfig(
                provider=llm_factory.LLMProvider.OPENAI,
                model=self.MODEL,
                api_key="offline-test-key",
                openai_base_url=self.BASE_URL,
                max_tokens=4096,
            )
        )
        self.assertIsInstance(service, OpenRouterReasoningLLMService)

    def test_route_predicate_is_endpoint_and_model_exact(self) -> None:
        self.assertTrue(mini_rl_env._is_openrouter_laguna_model(self.BASE_URL, self.MODEL))
        self.assertTrue(
            mini_rl_env._is_openrouter_laguna_model(
                self.BASE_URL, " poolside/LAGUNA-S-2.1-20260720 "
            )
        )
        self.assertFalse(
            mini_rl_env._is_openrouter_laguna_model("https://example.com/v1", self.MODEL)
        )
        self.assertFalse(
            mini_rl_env._is_openrouter_laguna_model(
                self.BASE_URL, "poolside/laguna-xs-2.1"
            )
        )

    def test_thinking_policy_uses_openrouter_binary_reasoning_control(self) -> None:
        for thinking, enabled in (("none", False), ("high", True)):
            with self.subTest(thinking=thinking):
                service = types.SimpleNamespace(
                    _settings={
                        "extra": {
                            "keep": "value",
                            "extra_body": {
                                "vllm_xargs": {"thinking_budget": 512},
                                "chat_template_kwargs": {"enable_thinking": False},
                                "top_k": 40,
                            },
                        }
                    }
                )
                policy = mini_rl_env._apply_benchmark_thinking_mode(
                    llm_service=service,
                    provider=mini_rl_env.LLMProvider.OPENAI,
                    model=self.MODEL,
                    thinking=thinking,
                    thinking_budget=None,
                    openai_base_url=self.BASE_URL,
                )
                self.assertEqual(service._settings["extra"]["keep"], "value")
                self.assertEqual(
                    service._settings["extra"]["extra_body"],
                    {
                        "top_k": 40,
                        "reasoning": {"enabled": enabled, "exclude": False},
                    },
                )
                self.assertEqual(
                    policy,
                    f"openrouter:poolside-laguna-s-2.1 reasoning.enabled={enabled}",
                )

    def _args(self, thinking: str, thinking_budget=None):
        return argparse.Namespace(
            provider="openai",
            model=self.MODEL,
            openai_base_url=self.BASE_URL,
            thinking=thinking,
            thinking_budget=thinking_budget,
            max_tokens=4096,
            openai_no_budget_thinking_toggle=False,
            llm_request_timeout_secs=None,
            llm_stream_idle_timeout_secs=None,
            reasoning_effort=None,
            round_id=None,
            openai_params=None,
        )

    def test_validation_accepts_only_none_and_high(self) -> None:
        parser = CapturingArgumentParser()
        for thinking in ("none", "high"):
            mini_rl_env._validate_generation_controls(self._args(thinking), parser)

        with self.assertRaisesRegex(ValueError, r"none\|high"):
            mini_rl_env._validate_generation_controls(self._args("medium"), parser)

        with self.assertRaisesRegex(ValueError, "binary reasoning toggle"):
            mini_rl_env._validate_generation_controls(self._args("high", 512), parser)

    def test_reasoning_delta_aliases(self) -> None:
        self.assertEqual(_reasoning_delta_text(types.SimpleNamespace(reasoning="abc")), "abc")
        self.assertEqual(
            _reasoning_delta_text(types.SimpleNamespace(reasoning_content="def")), "def"
        )
        self.assertEqual(_reasoning_delta_text(types.SimpleNamespace(content="answer")), "")

    def test_reasoning_is_attached_to_assistant_tool_call(self) -> None:
        async def run() -> None:
            context = LLMContext(messages=[])
            _pending_reasoning(context)["tool-1"] = "preserve this reasoning"
            aggregator = OpenRouterReasoningAssistantAggregator(context)
            frame = FunctionCallInProgressFrame(
                function_name="move",
                tool_call_id="tool-1",
                arguments={"sector": 1611},
                cancel_on_interruption=True,
            )
            await aggregator._handle_function_call_in_progress(frame)

            assistant = context.get_messages()[0]
            self.assertEqual(assistant["role"], "assistant")
            self.assertEqual(assistant["reasoning"], "preserve this reasoning")
            self.assertEqual(assistant["tool_calls"][0]["id"], "tool-1")
            self.assertEqual(_pending_reasoning(context), {})

        asyncio.run(run())


class OpenRouterQwen36Tests(unittest.TestCase):
    BASE_URL = "https://openrouter.ai/api/v1"
    MODELS = ("qwen/qwen3.6-27b", "qwen/qwen3.6-35b-a3b")

    def _args(self, model: str, thinking: str, thinking_budget=None):
        return argparse.Namespace(
            provider="openai",
            model=model,
            openai_base_url=self.BASE_URL,
            thinking=thinking,
            thinking_budget=thinking_budget,
            max_tokens=4096,
            openai_no_budget_thinking_toggle=False,
            llm_request_timeout_secs=None,
            llm_stream_idle_timeout_secs=None,
            reasoning_effort=None,
            round_id=None,
            openai_params=None,
        )

    def test_routes_through_reasoning_aware_service(self) -> None:
        for model in self.MODELS:
            with self.subTest(model=model):
                service = llm_factory.create_llm_service(
                    llm_factory.LLMServiceConfig(
                        provider=llm_factory.LLMProvider.OPENAI,
                        model=model,
                        api_key="offline-test-key",
                        openai_base_url=self.BASE_URL,
                        max_tokens=4096,
                    )
                )
                self.assertIsInstance(service, OpenRouterReasoningLLMService)

    def test_route_predicate_is_endpoint_and_family_exact(self) -> None:
        for model in self.MODELS:
            self.assertTrue(
                mini_rl_env._is_openrouter_qwen36_model(self.BASE_URL, model)
            )
        self.assertFalse(
            mini_rl_env._is_openrouter_qwen36_model(
                "https://example.com/v1", self.MODELS[0]
            )
        )
        self.assertFalse(
            mini_rl_env._is_openrouter_qwen36_model(
                self.BASE_URL, "qwen/qwen3.5-27b"
            )
        )

    def test_thinking_policy_uses_binary_reasoning_control(self) -> None:
        for model in self.MODELS:
            for thinking, enabled in (("none", False), ("high", True)):
                with self.subTest(model=model, thinking=thinking):
                    service = types.SimpleNamespace(
                        _settings={
                            "extra": {
                                "extra_body": {
                                    "vllm_xargs": {"thinking_budget": 2048},
                                    "chat_template_kwargs": {"enable_thinking": False},
                                    "top_k": 20,
                                }
                            }
                        }
                    )
                    policy = mini_rl_env._apply_benchmark_thinking_mode(
                        llm_service=service,
                        provider=mini_rl_env.LLMProvider.OPENAI,
                        model=model,
                        thinking=thinking,
                        thinking_budget=None,
                        openai_base_url=self.BASE_URL,
                    )
                    self.assertEqual(
                        service._settings["extra"]["extra_body"],
                        {
                            "top_k": 20,
                            "reasoning": {"enabled": enabled, "exclude": False},
                        },
                    )
                    self.assertEqual(
                        policy,
                        f"openrouter:qwen3.6 reasoning.enabled={enabled}",
                    )

    def test_validation_accepts_only_none_and_high(self) -> None:
        parser = CapturingArgumentParser()
        for model in self.MODELS:
            for thinking in ("none", "high"):
                mini_rl_env._validate_generation_controls(
                    self._args(model, thinking), parser
                )
            with self.assertRaisesRegex(ValueError, r"none\|high"):
                mini_rl_env._validate_generation_controls(
                    self._args(model, "medium"), parser
                )
            with self.assertRaisesRegex(ValueError, "binary reasoning toggle"):
                mini_rl_env._validate_generation_controls(
                    self._args(model, "high", 512), parser
                )


if __name__ == "__main__":
    unittest.main()
