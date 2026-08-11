"""Dedicated Baseten Qwen3.6 routing and reasoning-history tests."""

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
from baseten_qwen_reasoning_service import (  # noqa: E402
    BasetenQwenReasoningAssistantAggregator,
    BasetenQwenReasoningLLMService,
)
from openrouter_reasoning_service import _pending_reasoning  # noqa: E402


def _load_module(name: str, relative_path: str):
    path = PORT_TO_PORT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mini_rl_env = _load_module("mini_rl_env_baseten_qwen36_test", "mini-rl-env.py")


class CapturingArgumentParser(argparse.ArgumentParser):
    def error(self, message):  # type: ignore[override]
        raise ValueError(message)


class BasetenQwen36Tests(unittest.TestCase):
    BASE_URL = "https://model-example.api.baseten.co/deployment/example/sync/v1"
    MODEL = "Qwen/Qwen3.6-27B"
    MODELS = (
        "Qwen/Qwen3.6-27B",
        "Qwen/Qwen3.6-35B-A3B-FP8",
    )

    def _args(self, thinking: str, thinking_budget=None, model=None):
        return argparse.Namespace(
            provider="openai",
            model=model or self.MODEL,
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

    def test_routes_through_baseten_reasoning_service(self) -> None:
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
                self.assertIsInstance(service, BasetenQwenReasoningLLMService)

    def test_route_predicate_is_endpoint_and_model_exact(self) -> None:
        for model in self.MODELS:
            with self.subTest(model=model):
                self.assertTrue(
                    mini_rl_env._is_baseten_qwen36_model(self.BASE_URL, model)
                )
                self.assertFalse(
                    mini_rl_env._is_baseten_qwen36_model(
                        "https://openrouter.ai/api/v1", model
                    )
                )
        for unsupported in (
            "Qwen/Qwen3.5-27B",
            "Qwen/Qwen3.6-35B-A3B",
            "Qwen/Qwen3.6-35B-A3B-FP8-extra",
        ):
            with self.subTest(unsupported=unsupported):
                self.assertFalse(
                    mini_rl_env._is_baseten_qwen36_model(
                        self.BASE_URL, unsupported
                    )
                )

    def test_factory_route_predicate_is_endpoint_and_model_exact(self) -> None:
        for model in self.MODELS:
            with self.subTest(model=model):
                self.assertTrue(
                    llm_factory._is_baseten_qwen36_model(model, self.BASE_URL)
                )
                self.assertFalse(
                    llm_factory._is_baseten_qwen36_model(
                        model, "https://openrouter.ai/api/v1"
                    )
                )
        self.assertFalse(
            llm_factory._is_baseten_qwen36_model(
                "Qwen/Qwen3.6-35B-A3B", self.BASE_URL
            )
        )

    def test_thinking_policy_uses_chat_template_kwargs(self) -> None:
        for model in self.MODELS:
            for thinking, enabled in (("none", False), ("high", True)):
                with self.subTest(model=model, thinking=thinking):
                    service = types.SimpleNamespace(
                        _settings={
                            "extra": {
                                "extra_body": {
                                    "vllm_xargs": {"thinking_budget": 2048},
                                    "reasoning": {"effort": "high"},
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
                            "chat_template_kwargs": {
                                "enable_thinking": enabled,
                                "preserve_thinking": enabled,
                            },
                        },
                    )
                    self.assertEqual(
                        policy,
                        f"openai-compatible:baseten-qwen3.6 enable_thinking={enabled}",
                    )

    def test_validation_accepts_only_none_and_high(self) -> None:
        parser = CapturingArgumentParser()
        for model in self.MODELS:
            for thinking in ("none", "high"):
                mini_rl_env._validate_generation_controls(
                    self._args(thinking, model=model), parser
                )
            with self.assertRaisesRegex(ValueError, r"none\|high"):
                mini_rl_env._validate_generation_controls(
                    self._args("medium", model=model), parser
                )
            with self.assertRaisesRegex(ValueError, "binary reasoning toggle"):
                mini_rl_env._validate_generation_controls(
                    self._args("high", thinking_budget=512, model=model), parser
                )

    def test_reasoning_content_is_attached_to_assistant_tool_call(self) -> None:
        async def run() -> None:
            context = LLMContext(messages=[])
            _pending_reasoning(context)["tool-1"] = "preserve this reasoning"
            aggregator = BasetenQwenReasoningAssistantAggregator(context)
            frame = FunctionCallInProgressFrame(
                function_name="move",
                tool_call_id="tool-1",
                arguments={"sector": 1611},
                cancel_on_interruption=True,
            )
            await aggregator._handle_function_call_in_progress(frame)

            assistant = context.get_messages()[0]
            self.assertEqual(assistant["role"], "assistant")
            self.assertEqual(
                assistant["reasoning_content"], "preserve this reasoning"
            )
            self.assertNotIn("reasoning", assistant)
            self.assertEqual(assistant["tool_calls"][0]["id"], "tool-1")
            self.assertEqual(_pending_reasoning(context), {})

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
