import argparse
import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path


PORT_TO_PORT_DIR = Path(__file__).resolve().parents[1]
if str(PORT_TO_PORT_DIR) not in sys.path:
    sys.path.insert(0, str(PORT_TO_PORT_DIR))

import llm_factory  # noqa: E402


def _load_module(name: str, relative_path: str):
    path = PORT_TO_PORT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mini_rl_env = _load_module("mini_rl_env_inkling_test", "mini-rl-env.py")


class CapturingArgumentParser(argparse.ArgumentParser):
    def error(self, message):  # type: ignore[override]
        raise ValueError(message)


class CapturingCompletions:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    async def create(self, **params):
        self.requests.append(params)

        async def _stream():
            yield types.SimpleNamespace(choices=[], usage=None)

        return _stream()


class InklingHarnessTests(unittest.TestCase):
    BASETEN_URL = "https://inference.baseten.co/v1"

    def test_inkling_model_predicate_is_exact_and_normalized(self) -> None:
        for model in (
            "inkling",
            " thinkingmachines/INKLING ",
            "inkling-small",
            " thinkingmachines/INKLING-SMALL ",
        ):
            with self.subTest(model=model):
                self.assertTrue(mini_rl_env._is_baseten_inkling_model(model))

        for model in (
            "thinkingmachines/inkling-preview",
            "thinkingmachines/inkling-small-preview",
            "my-inkling",
            "glm-5.2",
        ):
            with self.subTest(model=model):
                self.assertFalse(mini_rl_env._is_baseten_inkling_model(model))

    def test_apply_inkling_thinking_mode_maps_all_levels_to_native_effort(self) -> None:
        expected_by_level = {
            "none": "none",
            "minimal": "minimal",
            "low": "low",
            "medium": "medium",
            "high": "high",
            "xhigh": "max",
        }
        for thinking, expected_effort in expected_by_level.items():
            with self.subTest(thinking=thinking):
                service = types.SimpleNamespace(
                    _settings={
                        "temperature": 0.2,
                        "extra": {
                            "request_label": "preserve-me",
                            "extra_body": {
                                "reasoning": {"effort": "stale"},
                                "reasoning_effort": "none",
                                "chat_template_kwargs": {"reasoning_effort": "stale"},
                                "vllm_xargs": {"thinking_budget": 128},
                                "top_k": 40,
                            },
                        },
                    }
                )

                policy = mini_rl_env._apply_benchmark_thinking_mode(
                    llm_service=service,
                    provider=mini_rl_env.LLMProvider.OPENAI,
                    model="thinkingmachines/inkling",
                    thinking=thinking,
                    thinking_budget=None,
                    openai_base_url=self.BASETEN_URL,
                )

                extra = service._settings["extra"]
                self.assertEqual(extra["reasoning_effort"], expected_effort)
                self.assertEqual(service._settings["temperature"], 1.0)
                self.assertEqual(extra["request_label"], "preserve-me")
                self.assertEqual(extra["extra_body"], {"top_k": 40})
                self.assertNotIn("reasoning", extra["extra_body"])
                self.assertEqual(
                    policy,
                    "openai-compatible:baseten-inkling "
                    f"reasoning_effort={expected_effort} T=1.0",
                )

    def test_inkling_effort_mapper_rejects_unknown_level(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Inkling models on Baseten support benchmark thinking",
        ):
            mini_rl_env._baseten_inkling_reasoning_effort("unknown")

    def test_inkling_small_uses_same_native_effort_policy(self) -> None:
        service = types.SimpleNamespace(_settings={"temperature": 0.2})
        policy = mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=service,
            provider=mini_rl_env.LLMProvider.OPENAI,
            model="thinkingmachines/inkling-small",
            thinking="xhigh",
            thinking_budget=None,
            openai_base_url=self.BASETEN_URL,
        )
        self.assertEqual(service._settings["temperature"], 1.0)
        self.assertEqual(service._settings["extra"]["reasoning_effort"], "max")
        self.assertEqual(
            policy,
            "openai-compatible:baseten-inkling reasoning_effort=max T=1.0",
        )

    def test_inkling_temperature_override_is_endpoint_and_model_gated(self) -> None:
        inkling = types.SimpleNamespace(_settings={"temperature": 0.2})
        mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=inkling,
            provider=mini_rl_env.LLMProvider.OPENAI,
            model="thinkingmachines/inkling",
            thinking="low",
            thinking_budget=None,
            openai_base_url=self.BASETEN_URL,
        )
        self.assertEqual(inkling._settings["temperature"], 1.0)

        other_baseten = types.SimpleNamespace(_settings={"temperature": 0.2})
        mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=other_baseten,
            provider=mini_rl_env.LLMProvider.OPENAI,
            model="some-other-model",
            thinking="low",
            thinking_budget=None,
            openai_base_url=self.BASETEN_URL,
        )
        self.assertEqual(other_baseten._settings["temperature"], 0.2)
        self.assertEqual(
            other_baseten._settings["extra"]["extra_body"]["reasoning"],
            {"effort": "low"},
        )

    def test_request_boundary_uses_native_effort_temperature_and_max_tokens(self) -> None:
        async def _run(thinking: str, expected_effort: str) -> None:
            args = argparse.Namespace(
                model="thinkingmachines/inkling",
                thinking=thinking,
                thinking_budget=None,
                max_tokens=16384,
                openai_base_url=self.BASETEN_URL,
            )
            service = llm_factory.create_llm_service(
                llm_factory.LLMServiceConfig(
                    provider=llm_factory.LLMProvider.OPENAI,
                    model=args.model,
                    api_key="offline-test-key",
                    thinking=None,
                    max_tokens=args.max_tokens,
                    openai_base_url=args.openai_base_url,
                    openai_params={
                        "temperature": 0.2,
                        "extra": {
                            "extra_body": {
                                "reasoning": {"effort": "stale"},
                                "reasoning_effort": "none",
                                "chat_template_kwargs": {"reasoning_effort": "stale"},
                                "vllm_xargs": {"thinking_budget": 128},
                            }
                        },
                    },
                )
            )
            mini_rl_env._apply_benchmark_thinking_mode(
                llm_service=service,
                provider=mini_rl_env.LLMProvider.OPENAI,
                model=args.model,
                thinking=args.thinking,
                thinking_budget=args.thinking_budget,
                openai_base_url=args.openai_base_url,
            )

            completions = CapturingCompletions()
            service._client = types.SimpleNamespace(
                chat=types.SimpleNamespace(completions=completions)
            )
            chunks = await service.get_chat_completions(
                {"messages": [{"role": "user", "content": "offline boundary test"}]}
            )
            self.assertEqual(len([chunk async for chunk in chunks]), 1)

            self.assertEqual(len(completions.requests), 1)
            request = completions.requests[0]
            self.assertEqual(request["reasoning_effort"], expected_effort)
            self.assertEqual(request["temperature"], 1.0)
            self.assertEqual(request["max_tokens"], 16384)
            self.assertNotIn("extra_body", request)

        expected_by_level = {
            "none": "none",
            "minimal": "minimal",
            "low": "low",
            "medium": "medium",
            "high": "high",
            "xhigh": "max",
        }
        for thinking, expected_effort in expected_by_level.items():
            with self.subTest(thinking=thinking):
                asyncio.run(_run(thinking, expected_effort))

    def test_inkling_validation_accepts_full_range_and_rejects_budget(self) -> None:
        parser = CapturingArgumentParser()
        for thinking in mini_rl_env.THINKING_LEVELS:
            with self.subTest(thinking=thinking):
                args = types.SimpleNamespace(
                    provider="openai",
                    model="thinkingmachines/inkling",
                    openai_base_url=self.BASETEN_URL,
                    thinking=thinking,
                    thinking_budget=None,
                    max_tokens=16384,
                )
                mini_rl_env._validate_generation_controls(args, parser)

        args.thinking_budget = 2048
        with self.assertRaisesRegex(
            ValueError,
            "Baseten endpoints control reasoning via reasoning.effort levels",
        ):
            mini_rl_env._validate_generation_controls(args, parser)

    def test_non_inkling_reasoning_paths_are_unchanged(self) -> None:
        glm = types.SimpleNamespace(_settings={"temperature": 0.2})
        glm_policy = mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=glm,
            provider=mini_rl_env.LLMProvider.OPENAI,
            model="zai-org/GLM-5.2",
            thinking="xhigh",
            thinking_budget=None,
            openai_base_url=self.BASETEN_URL,
        )
        self.assertEqual(glm_policy, "openai-compatible:baseten reasoning.effort=max")
        self.assertEqual(glm._settings["temperature"], 0.2)
        self.assertNotIn("reasoning_effort", glm._settings["extra"])
        self.assertEqual(
            glm._settings["extra"]["extra_body"]["reasoning"],
            {"effort": "max"},
        )

        nemotron = types.SimpleNamespace(_settings={"temperature": 0.3})
        nemotron_policy = mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=nemotron,
            provider=mini_rl_env.LLMProvider.OPENAI,
            model="nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B",
            thinking="high",
            thinking_budget=None,
            openai_base_url=self.BASETEN_URL,
        )
        self.assertEqual(nemotron_policy, "openai-compatible:baseten reasoning.effort=high")
        self.assertEqual(nemotron._settings["temperature"], 0.3)
        self.assertEqual(
            nemotron._settings["extra"]["extra_body"]["reasoning"],
            {"effort": "high"},
        )

        non_baseten_inkling = types.SimpleNamespace(_settings={"temperature": 0.4})
        non_baseten_policy = mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=non_baseten_inkling,
            provider=mini_rl_env.LLMProvider.OPENAI,
            model="thinkingmachines/inkling",
            thinking="low",
            thinking_budget=None,
            openai_base_url="https://api.openai.com/v1",
        )
        self.assertFalse(
            mini_rl_env._is_baseten_endpoint("https://api.openai.com/v1")
        )
        self.assertEqual(non_baseten_policy, "openai-compatible:vllm thinking_budget=128")
        self.assertEqual(non_baseten_inkling._settings["temperature"], 0.4)
        self.assertEqual(
            non_baseten_inkling._settings["extra"],
            {"extra_body": {"vllm_xargs": {"thinking_budget": 128}}},
        )

        non_openai_inkling = types.SimpleNamespace(
            _settings={
                "temperature": 0.5,
                "thinking": None,
                "extra": {"request_label": "preserve-me"},
            }
        )
        expected_settings = {
            "temperature": 0.5,
            "thinking": None,
            "extra": {"request_label": "preserve-me"},
        }
        non_openai_policy = mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=non_openai_inkling,
            provider=mini_rl_env.LLMProvider.ANTHROPIC,
            model="thinkingmachines/inkling",
            thinking="none",
            thinking_budget=None,
            openai_base_url=self.BASETEN_URL,
        )
        self.assertEqual(non_openai_policy, "anthropic:default thinking=disabled")
        self.assertEqual(non_openai_inkling._settings, expected_settings)


if __name__ == "__main__":
    unittest.main()
