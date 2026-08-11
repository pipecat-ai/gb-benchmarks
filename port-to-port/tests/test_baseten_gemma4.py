"""Dedicated Baseten Gemma 4 routing and generation-control tests."""

import argparse
import importlib.util
import sys
import types
import unittest
from pathlib import Path


PORT_TO_PORT_DIR = Path(__file__).resolve().parents[1]
if str(PORT_TO_PORT_DIR) not in sys.path:
    sys.path.insert(0, str(PORT_TO_PORT_DIR))

import llm_factory  # noqa: E402
from openrouter_reasoning_service import OpenRouterReasoningLLMService  # noqa: E402


def _load_module(name: str, relative_path: str):
    path = PORT_TO_PORT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mini_rl_env = _load_module("mini_rl_env_baseten_gemma4_test", "mini-rl-env.py")


class CapturingArgumentParser(argparse.ArgumentParser):
    def error(self, message):  # type: ignore[override]
        raise ValueError(message)


class BasetenGemma4Tests(unittest.TestCase):
    BASE_URL = "https://model-example.api.baseten.co/deployment/example/sync/v1"
    MODEL = "google/gemma-4-26B-A4B-it"

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

    def test_routes_through_reasoning_aware_service(self) -> None:
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

    def test_route_predicates_are_endpoint_and_model_exact(self) -> None:
        self.assertTrue(
            mini_rl_env._is_baseten_gemma4_model(self.BASE_URL, self.MODEL)
        )
        self.assertTrue(
            llm_factory._is_baseten_gemma4_model(self.MODEL, self.BASE_URL)
        )
        for base_url, model in (
            ("https://openrouter.ai/api/v1", self.MODEL),
            (self.BASE_URL, "google/gemma-4-31b-it"),
            (self.BASE_URL, f"{self.MODEL}-extra"),
        ):
            with self.subTest(base_url=base_url, model=model):
                self.assertFalse(
                    mini_rl_env._is_baseten_gemma4_model(base_url, model)
                )
                self.assertFalse(
                    llm_factory._is_baseten_gemma4_model(model, base_url)
                )

    def test_thinking_policy_uses_binary_template_controls(self) -> None:
        for thinking, enabled in (("none", False), ("high", True)):
            with self.subTest(thinking=thinking):
                service = types.SimpleNamespace(
                    _settings={
                        "extra": {
                            "extra_body": {
                                "vllm_xargs": {"thinking_budget": 2048},
                                "reasoning": {"effort": "high"},
                                "unrelated": "preserved",
                            }
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
                self.assertEqual(service._settings["temperature"], 1.0)
                self.assertEqual(service._settings["top_p"], 0.95)
                self.assertEqual(
                    service._settings["extra"]["extra_body"],
                    {
                        "unrelated": "preserved",
                        "chat_template_kwargs": {
                            "enable_thinking": enabled,
                            "preserve_thinking": enabled,
                        },
                        "top_k": 64,
                    },
                )
                self.assertEqual(
                    policy,
                    "openai-compatible:baseten-gemma4 "
                    f"enable_thinking={enabled} T=1.0 top_p=0.95 top_k=64",
                )

    def test_validation_accepts_only_none_and_high(self) -> None:
        parser = CapturingArgumentParser()
        for thinking in ("none", "high"):
            mini_rl_env._validate_generation_controls(self._args(thinking), parser)
        with self.assertRaisesRegex(ValueError, r"none\|high"):
            mini_rl_env._validate_generation_controls(self._args("medium"), parser)
        with self.assertRaisesRegex(ValueError, "binary reasoning toggle"):
            mini_rl_env._validate_generation_controls(
                self._args("high", thinking_budget=512), parser
            )


if __name__ == "__main__":
    unittest.main()
