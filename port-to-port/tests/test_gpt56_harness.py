import argparse
import asyncio
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import httpx
import openai
from openai.types import responses as response_types
from openai.types.responses.response_input_item_param import ResponseInputItemParam
from pipecat.processors.aggregators.llm_context import LLMContext
from pydantic import TypeAdapter


PORT_TO_PORT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = PORT_TO_PORT_DIR / "proj-2026-07-16-1632"
if str(PORT_TO_PORT_DIR) not in sys.path:
    sys.path.insert(0, str(PORT_TO_PORT_DIR))

import llm_factory  # noqa: E402
import openai_responses_service  # noqa: E402


def _load_module(name: str, relative_path: str):
    path = PORT_TO_PORT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mini_rl_env = _load_module("mini_rl_env_gpt56_test", "mini-rl-env.py")


class CapturingArgumentParser(argparse.ArgumentParser):
    def error(self, message):  # type: ignore[override]
        raise ValueError(message)


class _EventStream:
    def __init__(self, events, *, enter_delay: float = 0.0, event_delay: float = 0.0):
        self._events = iter(events)
        self._enter_delay = enter_delay
        self._event_delay = event_delay

    async def __aenter__(self):
        if self._enter_delay:
            await asyncio.sleep(self._enter_delay)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._event_delay:
            await asyncio.sleep(self._event_delay)
        try:
            return next(self._events)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def _configured_service(model: str, *, max_tokens: int = 16384):
    service = llm_factory.create_llm_service(
        llm_factory.LLMServiceConfig(
            provider=llm_factory.LLMProvider.OPENAI,
            model=model,
            api_key="offline-test-key",
            thinking=None,
            max_tokens=max_tokens,
            function_call_timeout_secs=20,
            llm_request_timeout_secs=90,
            llm_stream_idle_timeout_secs=30,
        )
    )
    return service


def _apply_gpt56(service, model: str, *, thinking: str, override: str | None = None):
    return mini_rl_env._apply_benchmark_thinking_mode(
        llm_service=service,
        provider=llm_factory.LLMProvider.OPENAI,
        model=model,
        thinking=thinking,
        thinking_budget=None,
        openai_base_url=None,
        reasoning_effort=override,
    )


def _completed_response(model: str = "gpt-5.6-luna") -> dict:
    return {
        "id": "resp_boundary_test",
        "object": "response",
        "created_at": 0,
        "model": model,
        "status": "completed",
        "output": [
            {
                "id": "msg_boundary_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": "ok",
                        "annotations": [],
                    }
                ],
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "service_tier": "default",
        "usage": {
            "input_tokens": 1,
            "input_tokens_details": {
                "cached_tokens": 0,
                "cache_write_tokens": 1,
            },
            "output_tokens": 1,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 2,
        },
    }


def _bare_stream_service(events, *, request_timeout: float = 5, idle_timeout: float = 5):
    service = object.__new__(openai_responses_service.OpenAIResponsesLLMService)
    service._request_timeout_secs = request_timeout
    service._stream_idle_timeout_secs = idle_timeout
    service._responses_traces = []
    service._benchmark_observability_enabled = True
    service._benchmark_outcome_callback = None
    service.start_ttfb_metrics = mock.AsyncMock()
    service.stop_ttfb_metrics = mock.AsyncMock()
    service.start_llm_usage_metrics = mock.AsyncMock()
    service.run_function_calls = mock.AsyncMock()
    service._responses_request_params = lambda context: {
        "model": "gpt-5.6-luna",
        "reasoning": {"effort": "low"},
        "max_output_tokens": 16384,
        "tools": [{"type": "function", "name": "lookup_probe"}],
        "store": False,
    }
    service.get_full_model_name = lambda: None
    service.set_full_model_name = mock.Mock()
    service._client = types.SimpleNamespace(
        responses=types.SimpleNamespace(stream=lambda **kwargs: _EventStream(events))
    )
    return service


class Gpt56RoutingAndIdentityTests(unittest.TestCase):
    MODELS = ("gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra")

    def test_exact_hosted_gate_and_near_miss_negatives(self) -> None:
        for model in self.MODELS:
            with self.subTest(model=model):
                self.assertTrue(llm_factory._is_gpt56_responses_model(model.upper(), None))
                self.assertTrue(llm_factory._is_openai_responses_model(model, None))

        for model, base_url in (
            ("gpt-5.6-lunatic", None),
            ("gpt-5.6-luna-2026-07-16", None),
            ("openai/gpt-5.6-luna", None),
            ("gpt-5.6-luna", "https://example.test/v1"),
            ("gpt-5.6", None),
        ):
            with self.subTest(model=model, base_url=base_url):
                self.assertFalse(llm_factory._is_gpt56_responses_model(model, base_url))

    def test_factory_routes_every_exact_version_to_responses(self) -> None:
        for model in self.MODELS:
            with self.subTest(model=model):
                service = _configured_service(model)
                self.assertIsInstance(
                    service, openai_responses_service.OpenAIResponsesLLMService
                )
                self.assertEqual(service._request_timeout_secs, 90)
                self.assertEqual(service._stream_idle_timeout_secs, 30)
                self.assertTrue(service._benchmark_observability_enabled)
                self.assertFalse(hasattr(service, "_encrypted_reasoning_replay_enabled"))
                self.assertEqual(openai.DEFAULT_MAX_RETRIES, 2)
                self.assertEqual(service._client.max_retries, 0)
                self.assertEqual(service._benchmark_sdk_max_retries, 0)

    def test_native_xhigh_and_override_max_have_distinct_serialized_identity(self) -> None:
        identities = []
        for override, expected in ((None, "xhigh"), ("max", "max")):
            service = _configured_service("gpt-5.6-luna")
            _apply_gpt56(service, "gpt-5.6-luna", thinking="xhigh", override=override)
            params = service._responses_request_params(
                LLMContext(messages=[{"role": "user", "content": "identity"}])
            )
            effective = mini_rl_env._resolve_gpt56_effective_effort(
                model="gpt-5.6-luna",
                openai_base_url=None,
                thinking="xhigh",
                reasoning_effort=override,
            )
            identities.append(
                {
                    "thinking": "xhigh",
                    "reasoning_effort": override,
                    "effective_effort": effective,
                    "round_id": "r01",
                }
            )
            self.assertEqual(params["reasoning"], {"effort": expected})
            self.assertNotIn("reasoning_effort", params)

        self.assertEqual([row["effective_effort"] for row in identities], ["xhigh", "max"])
        self.assertNotEqual(json.dumps(identities[0], sort_keys=True), json.dumps(identities[1], sort_keys=True))

    def test_identity_and_timeouts_propagate_to_config_summary_and_metadata(self) -> None:
        args = argparse.Namespace(
            provider="openai",
            model="gpt-5.6-luna",
            openai_base_url=None,
            openai_params=None,
            openai_no_budget_thinking_toggle=False,
            thinking="xhigh",
            thinking_budget=None,
            reasoning_effort="max",
            effective_effort="max",
            round_id="r07",
            max_tokens=16384,
            max_turns=50,
            function_call_timeout_secs=20,
            llm_request_timeout_secs=900,
            llm_stream_idle_timeout_secs=600,
            pipeline_idle_timeout_secs=930,
            capture_inference_inputs=True,
            task=mini_rl_env.DEFAULT_BENCHMARK_TASK,
            task_variant="natural",
            task_prompt_version="v1",
            log_json="runs/test.json",
            replay_stream_jsonl=None,
        )
        runtime = mini_rl_env._BenchmarkRuntime(
            args=args,
            llm_service=types.SimpleNamespace(),
            world=mini_rl_env.SyntheticWorld(),
            system_instruction="test",
            system_instruction_path=PORT_TO_PORT_DIR / "system_instruction.txt",
        )
        snapshots = (
            runtime.build_config_snapshot(),
            runtime.build_summary(),
            runtime.build_metadata_snapshot(),
        )
        for snapshot in snapshots:
            self.assertEqual(snapshot["thinking"], "xhigh")
            self.assertEqual(snapshot["reasoning_effort"], "max")
            self.assertEqual(snapshot["effective_effort"], "max")
            self.assertEqual(snapshot["round_id"], "r07")
            self.assertEqual(snapshot["llm_request_timeout_secs"], 900)
            self.assertEqual(snapshot["llm_stream_idle_timeout_secs"], 600)
            self.assertEqual(snapshot["pipeline_idle_timeout_secs"], 930)
        self.assertEqual(
            snapshots[2]["runner_version"], "2026-07-17-gpt56-aiewf-responses-v3"
        )

    def test_pipeline_idle_fallback_is_after_provider_timeouts(self) -> None:
        args = types.SimpleNamespace(
            model="gpt-5.6-luna",
            openai_base_url=None,
            llm_request_timeout_secs=900,
            llm_stream_idle_timeout_secs=600,
        )
        self.assertEqual(
            mini_rl_env._resolve_gpt56_pipeline_idle_timeout_secs(args),
            930,
        )
        args.model = "gpt-5.4"
        self.assertIsNone(mini_rl_env._resolve_gpt56_pipeline_idle_timeout_secs(args))

    def test_partial_checkpoint_is_atomic_and_final_payload_removes_marker(self) -> None:
        args = argparse.Namespace(
            provider="openai",
            model="gpt-5.6-luna",
            openai_base_url=None,
            openai_params=None,
            openai_no_budget_thinking_toggle=False,
            thinking="xhigh",
            thinking_budget=None,
            reasoning_effort=None,
            effective_effort="xhigh",
            round_id="smoke-core",
            max_tokens=50000,
            max_turns=50,
            function_call_timeout_secs=20,
            llm_request_timeout_secs=900,
            llm_stream_idle_timeout_secs=600,
            pipeline_idle_timeout_secs=930,
            capture_inference_inputs=True,
            task=mini_rl_env.DEFAULT_BENCHMARK_TASK,
            task_variant="natural",
            task_prompt_version="v1",
            replay_stream_jsonl=None,
        )
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "attempt.json"
            args.log_json = str(output)
            runtime = mini_rl_env._BenchmarkRuntime(
                args=args,
                llm_service=types.SimpleNamespace(),
                world=mini_rl_env.SyntheticWorld(),
                system_instruction="test",
                system_instruction_path=PORT_TO_PORT_DIR / "system_instruction.txt",
            )
            runtime.turn_logs.append({"llm_turn": 1})
            runtime.responses_traces.append({"trace_index": 1})
            runtime.write_partial_checkpoint(reason="turn_complete")
            checkpoint = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(checkpoint["checkpoint"]["partial"])
            self.assertEqual(checkpoint["checkpoint"]["reason"], "turn_complete")
            self.assertNotIn("inference_inputs", checkpoint)
            self.assertFalse(list(output.parent.glob(".*.tmp")))

            mini_rl_env._atomic_write_json(output, runtime.build_output_payload())
            final = json.loads(output.read_text(encoding="utf-8"))
            self.assertNotIn("checkpoint", final)

    def test_stream_idle_timeout_finishes_before_pipeline_fallback_and_writes_json(self) -> None:
        import tempfile

        async def exercise(output: Path) -> tuple[int, dict]:
            parser = mini_rl_env._build_parser()
            args = parser.parse_args(
                [
                    "--provider",
                    "openai",
                    "--model",
                    "gpt-5.6-luna",
                    "--thinking",
                    "xhigh",
                    "--max-tokens",
                    "50000",
                    "--max-turns",
                    "1",
                    "--round-id",
                    "offline-timeout",
                    "--llm-request-timeout-secs",
                    "0.2",
                    "--llm-stream-idle-timeout-secs",
                    "0.02",
                    "--log-json",
                    str(output),
                    "--no-capture-inference-inputs",
                ]
            )
            args.thinking_budget = None
            args.openai_params = None
            args.task, args.task_variant, args.task_prompt_version = (
                mini_rl_env._resolve_task_prompt(task=None, task_variant="natural")
            )
            mini_rl_env._validate_generation_controls(args, parser)

            service = _configured_service("gpt-5.6-luna", max_tokens=50000)
            service._request_timeout_secs = 0.2
            service._stream_idle_timeout_secs = 0.02
            service._client = types.SimpleNamespace(
                responses=types.SimpleNamespace(
                    stream=lambda **kwargs: _EventStream(
                        [types.SimpleNamespace(type="response.created")],
                        event_delay=0.1,
                    )
                )
            )
            with mock.patch.object(mini_rl_env, "create_llm_service", return_value=service):
                rc = await asyncio.wait_for(mini_rl_env._run_benchmark(args), timeout=2)
            return rc, json.loads(output.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            rc, payload = asyncio.run(exercise(Path(tmp) / "timeout.json"))
        self.assertEqual(rc, 1)
        self.assertNotIn("checkpoint", payload)
        self.assertEqual(payload["config"]["pipeline_idle_timeout_secs"], 30.2)
        self.assertEqual(payload["termination"]["reason"], "inference_error")
        self.assertEqual(payload["responses_traces"][0]["response_status"], "error")
        self.assertEqual(
            payload["responses_traces"][0]["error"]["type"],
            "ResponsesStreamIdleTimeout",
        )

    def test_override_validation_rejects_every_non_exact_route(self) -> None:
        parser = CapturingArgumentParser()
        for provider, model, base_url in (
            ("anthropic", "gpt-5.6-luna", None),
            ("openai", "gpt-5.6-lunatic", None),
            ("openai", "gpt-5.6-luna", "https://example.test/v1"),
            ("openai", "gpt-5.4", None),
        ):
            args = types.SimpleNamespace(
                provider=provider,
                model=model,
                openai_base_url=base_url,
                thinking="xhigh",
                thinking_budget=None,
                reasoning_effort="max",
                round_id="r01",
                max_tokens=None,
                llm_request_timeout_secs=90,
                llm_stream_idle_timeout_secs=30,
                openai_no_budget_thinking_toggle=False,
            )
            with self.subTest(provider=provider, model=model, base_url=base_url):
                with self.assertRaisesRegex(ValueError, "exact hosted GPT-5.6"):
                    mini_rl_env._validate_generation_controls(args, parser)

    def test_validation_rejects_priority_and_invalid_identity_controls(self) -> None:
        parser = CapturingArgumentParser()
        base = dict(
            provider="openai",
            model="gpt-5.6-luna",
            openai_base_url=None,
            thinking="xhigh",
            thinking_budget=None,
            reasoning_effort="max",
            round_id="r01",
            max_tokens=16384,
            llm_request_timeout_secs=90,
            llm_stream_idle_timeout_secs=30,
            openai_no_budget_thinking_toggle=False,
            openai_params={"service_tier": "priority"},
        )
        with self.assertRaisesRegex(ValueError, "omit service_tier"):
            mini_rl_env._validate_generation_controls(types.SimpleNamespace(**base), parser)

        base["openai_params"] = None
        base["round_id"] = "bad round"
        with self.assertRaisesRegex(ValueError, "--round-id"):
            mini_rl_env._validate_generation_controls(types.SimpleNamespace(**base), parser)

        base["round_id"] = "r01"
        base["llm_stream_idle_timeout_secs"] = 0
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            mini_rl_env._validate_generation_controls(types.SimpleNamespace(**base), parser)

        base["llm_stream_idle_timeout_secs"] = 30
        base["reasoning_effort"] = "xhigh"
        with self.assertRaisesRegex(ValueError, "duplicates the native"):
            mini_rl_env._validate_generation_controls(types.SimpleNamespace(**base), parser)

        legacy = types.SimpleNamespace(
            provider="openai",
            model="gpt-5.4",
            openai_base_url=None,
            thinking="low",
            thinking_budget=None,
            reasoning_effort=None,
            round_id=None,
            max_tokens=4096,
            llm_request_timeout_secs=90,
            llm_stream_idle_timeout_secs=None,
            openai_no_budget_thinking_toggle=False,
        )
        with self.assertRaisesRegex(ValueError, "only for the exact hosted GPT-5.6"):
            mini_rl_env._validate_generation_controls(legacy, parser)


class Gpt56HttpBoundaryTests(unittest.TestCase):
    def test_real_factory_serializes_only_responses_for_every_version(self) -> None:
        async def run_one(model: str) -> None:
            service = _configured_service(model)
            policy = _apply_gpt56(service, model, thinking="xhigh")
            self.assertIn("responses", policy)
            self.assertNotIn("reasoning_effort", service._settings["extra"])
            self.assertEqual(service._settings["extra"]["reasoning"], {"effort": "xhigh"})
            self.assertFalse(service._settings["extra"]["store"])

            captured: list[dict] = []

            def handler(request: httpx.Request) -> httpx.Response:
                if request.url.path.endswith("/chat/completions"):
                    self.fail("GPT-5.6 hit Chat Completions")
                self.assertEqual(request.url.path, "/v1/responses")
                captured.append(json.loads(request.content))
                return httpx.Response(
                    200,
                    json=_completed_response(model),
                    headers={"x-request-id": "req_boundary_test"},
                )

            http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            service._client = openai.AsyncOpenAI(
                api_key="offline-test-key",
                base_url="https://api.openai.com/v1",
                http_client=http_client,
            )
            context = LLMContext(
                messages=[{"role": "user", "content": "boundary test"}],
                tools=mini_rl_env.build_tools_schema(),
            )
            try:
                self.assertEqual(await service.run_inference(context), "ok")
            finally:
                await service._client.close()

            self.assertEqual(len(captured), 1)
            body = captured[0]
            self.assertEqual(body["model"], model)
            self.assertEqual(body["reasoning"], {"effort": "xhigh"})
            self.assertFalse(body["store"])
            self.assertNotIn("include", body)
            self.assertEqual(body["max_output_tokens"], 16384)
            self.assertTrue(body["tools"])
            self.assertTrue(
                all(
                    "strict" not in tool or isinstance(tool["strict"], bool)
                    for tool in body["tools"]
                )
            )
            self.assertNotIn("reasoning_effort", body)
            self.assertNotIn("service_tier", body)

        for model in Gpt56RoutingAndIdentityTests.MODELS:
            with self.subTest(model=model):
                asyncio.run(run_one(model))

    def test_real_factory_streaming_path_serializes_and_captures_request_id(self) -> None:
        async def run() -> None:
            service = _configured_service("gpt-5.6-luna")
            _apply_gpt56(service, "gpt-5.6-luna", thinking="low")
            call_item = {
                "type": "function_call",
                "id": "fc_stream_boundary",
                "call_id": "call_stream_boundary",
                "name": "lookup_probe",
                "arguments": "{}",
                "status": "completed",
            }
            base_response = {
                "id": "resp_stream_boundary",
                "object": "response",
                "created_at": 0,
                "model": "gpt-5.6-luna",
                "output": [],
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "service_tier": "default",
            }
            completed = {
                **base_response,
                "status": "completed",
                "output": [call_item],
                "usage": {
                    "input_tokens": 10,
                    "input_tokens_details": {"cached_tokens": 2},
                    "output_tokens": 4,
                    "output_tokens_details": {"reasoning_tokens": 1},
                    "total_tokens": 14,
                },
            }
            events = [
                {
                    "type": "response.created",
                    "sequence_number": 0,
                    "response": {**base_response, "status": "in_progress"},
                },
                {
                    "type": "response.output_item.added",
                    "sequence_number": 1,
                    "output_index": 0,
                    "item": {**call_item, "arguments": "", "status": "in_progress"},
                },
                {
                    "type": "response.function_call_arguments.done",
                    "sequence_number": 2,
                    "output_index": 0,
                    "item_id": call_item["id"],
                    "name": call_item["name"],
                    "arguments": "{}",
                },
                {
                    "type": "response.output_item.done",
                    "sequence_number": 3,
                    "output_index": 0,
                    "item": call_item,
                },
                {
                    "type": "response.completed",
                    "sequence_number": 4,
                    "response": completed,
                },
            ]
            sse = "".join(
                f"data: {json.dumps(event)}\n\n" for event in events
            ) + "data: [DONE]\n\n"
            captured: list[dict] = []

            def handler(request: httpx.Request) -> httpx.Response:
                if request.url.path == "/v1/chat/completions":
                    self.fail("GPT-5.6 production stream hit Chat Completions")
                self.assertEqual(request.url.path, "/v1/responses")
                captured.append(json.loads(request.content))
                return httpx.Response(
                    200,
                    content=sse,
                    headers={
                        "content-type": "text/event-stream",
                        "x-request-id": "req_stream_boundary",
                    },
                )

            http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            service._client = openai.AsyncOpenAI(
                api_key="offline-test-key",
                base_url="https://api.openai.com/v1",
                http_client=http_client,
            )
            service.start_ttfb_metrics = mock.AsyncMock()
            service.stop_ttfb_metrics = mock.AsyncMock()
            service.start_llm_usage_metrics = mock.AsyncMock()
            service.run_function_calls = mock.AsyncMock()
            context = LLMContext(
                messages=[{"role": "user", "content": "stream boundary"}],
                tools=mini_rl_env.build_tools_schema(),
            )
            try:
                await service._process_context(context)
            finally:
                await service._client.close()

            self.assertEqual(len(captured), 1)
            body = captured[0]
            self.assertTrue(body["stream"])
            self.assertEqual(body["reasoning"], {"effort": "low"})
            self.assertFalse(body["store"])
            self.assertEqual(body["max_output_tokens"], 16384)
            self.assertNotIn("include", body)
            self.assertNotIn("reasoning_effort", body)
            service.run_function_calls.assert_awaited_once()
            trace = service.get_responses_traces()[0]
            self.assertEqual(trace["request_id"], "req_stream_boundary")
            self.assertEqual(trace["usage"]["cached_tokens"], 2)
            self.assertIsNone(trace["usage"]["cache_write_tokens"])
            self.assertEqual(trace["sdk_max_retries"], 0)
            self.assertEqual(trace["openai_sdk_version"], "2.21.0")

        asyncio.run(run())

    def test_standard_history_reconstructs_parallel_calls_without_provider_state(self) -> None:
        service = object.__new__(openai_responses_service.OpenAIResponsesLLMService)
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_a",
                        "type": "function",
                        "function": {"name": "lookup_probe", "arguments": "{\\\"slot\\\":1}"},
                    }
                ],
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_b",
                        "type": "function",
                        "function": {"name": "lookup_probe", "arguments": "{\\\"slot\\\":2}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_b", "content": "result-b"},
            {"role": "tool", "tool_call_id": "call_a", "content": "result-a"},
            {"role": "user", "content": "continue"},
        ]

        items = service._messages_to_responses_input(messages)

        self.assertEqual(
            [item["type"] for item in items],
            [
                "function_call",
                "function_call",
                "function_call_output",
                "function_call_output",
                "message",
            ],
        )
        self.assertEqual([items[0]["call_id"], items[1]["call_id"]], ["call_a", "call_b"])
        self.assertEqual([items[2]["call_id"], items[3]["call_id"]], ["call_b", "call_a"])
        self.assertEqual(items[-1]["content"], [{"type": "input_text", "text": "continue"}])
        TypeAdapter(list[ResponseInputItemParam]).validate_python(items)
        self.assertFalse(hasattr(service, "_response_output_groups"))
        self.assertFalse(hasattr(service, "_encrypted_reasoning_replay_enabled"))

    def test_assistant_text_uses_the_aiewf_easy_input_contract(self) -> None:
        service = object.__new__(openai_responses_service.OpenAIResponsesLLMService)
        items = service._messages_to_responses_input(
            [
                {"role": "assistant", "content": "prior answer"},
                {"role": "user", "content": "next question"},
            ]
        )

        self.assertEqual(
            items,
            [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "input_text", "text": "prior answer"}],
                },
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "next question"}],
                },
            ],
        )
        TypeAdapter(list[ResponseInputItemParam]).validate_python(items)

    def test_parallel_function_calls_are_dispatched_as_one_completed_batch(self) -> None:
        calls = [
            types.SimpleNamespace(
                type="function_call",
                id=f"fc_{slot}",
                call_id=f"call_{slot}",
                name="lookup_probe",
                arguments=json.dumps({"slot": slot}),
            )
            for slot in (1, 2, 3)
        ]
        events = []
        for call in calls:
            events.extend(
                [
                    types.SimpleNamespace(type="response.output_item.added", item=call),
                    types.SimpleNamespace(
                        type="response.function_call_arguments.done",
                        item_id=call.id,
                        name=call.name,
                        arguments=call.arguments,
                    ),
                    types.SimpleNamespace(type="response.output_item.done", item=call),
                ]
            )
        events.append(
            types.SimpleNamespace(
                type="response.completed",
                response=types.SimpleNamespace(
                    id="resp_parallel",
                    model="gpt-5.6-luna",
                    status="completed",
                    service_tier="default",
                    incomplete_details=None,
                    error=None,
                    output=calls,
                    usage=None,
                ),
            )
        )
        service = _bare_stream_service(events)

        asyncio.run(service._process_context(types.SimpleNamespace()))

        service.run_function_calls.assert_awaited_once()
        dispatched = service.run_function_calls.await_args.args[0]
        self.assertEqual([call.tool_call_id for call in dispatched], ["call_1", "call_2", "call_3"])
        self.assertEqual([call.arguments for call in dispatched], [{"slot": 1}, {"slot": 2}, {"slot": 3}])
        trace = service.get_responses_traces()[0]
        self.assertEqual(trace["response_status"], "completed")
        self.assertNotIn("reasoning_replay_miss_count", trace)


class Gpt56ResponsesOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (PROJECT_DIR / "step1-gpt56-event-fixtures.json").read_text(encoding="utf-8")
        )

    def test_captured_success_event_sequence_dispatches_and_traces_usage(self) -> None:
        raw_events = self.fixture["captured_success"]["events"]
        events = []
        final_call = None
        for raw in raw_events:
            event_type = raw["type"]
            if event_type in {"response.output_item.added", "response.output_item.done"}:
                item = types.SimpleNamespace(**raw["item"])
                if event_type == "response.output_item.done":
                    final_call = raw["item"]
                events.append(types.SimpleNamespace(**{**raw, "item": item}))
            elif event_type == "response.completed":
                captured_response = raw["response"]
                usage = captured_response["usage"]
                response = types.SimpleNamespace(
                    id=captured_response["id"],
                    model=captured_response["model"],
                    status="completed",
                    service_tier=captured_response["service_tier"],
                    incomplete_details=None,
                    error=None,
                    output=[types.SimpleNamespace(**final_call)] if final_call else [],
                    usage=types.SimpleNamespace(
                        input_tokens=usage["input_tokens"],
                        input_tokens_details=types.SimpleNamespace(
                            cached_tokens=usage["cached_tokens"]
                        ),
                        output_tokens=usage["output_tokens"],
                        output_tokens_details=types.SimpleNamespace(
                            reasoning_tokens=usage["reasoning_tokens"]
                        ),
                        total_tokens=usage["total_tokens"],
                    ),
                )
                events.append(types.SimpleNamespace(type=event_type, response=response))
            else:
                events.append(types.SimpleNamespace(**raw))

        service = _bare_stream_service(events)
        asyncio.run(service._process_context(types.SimpleNamespace()))

        service.run_function_calls.assert_awaited_once()
        call = service.run_function_calls.await_args.args[0][0]
        self.assertEqual(call.function_name, "lookup_probe")
        self.assertEqual(call.arguments, {"code": "gpt56-contract-v1"})
        trace = service.get_responses_traces()[0]
        self.assertEqual(trace["response_status"], "completed")
        self.assertEqual(trace["returned_service_tier"], "default")
        self.assertEqual(trace["usage"]["total_tokens"], 135)
        self.assertEqual(trace["event_types"], self.fixture["captured_success"]["expected_event_types"])
        self.assertNotIn("input", trace)

    def test_usage_trace_captures_prompt_cache_writes(self) -> None:
        response = types.SimpleNamespace(
            usage=types.SimpleNamespace(
                input_tokens=100,
                input_tokens_details=types.SimpleNamespace(
                    cached_tokens=60,
                    cache_write_tokens=25,
                ),
                output_tokens=12,
                output_tokens_details=types.SimpleNamespace(reasoning_tokens=7),
                total_tokens=112,
            )
        )

        usage = openai_responses_service.OpenAIResponsesLLMService._usage_trace(response)

        self.assertEqual(
            usage,
            {
                "input_tokens": 100,
                "cached_tokens": 60,
                "cache_write_tokens": 25,
                "output_tokens": 12,
                "reasoning_tokens": 7,
                "total_tokens": 112,
            },
        )

    def test_sdk_validated_incomplete_and_failed_events_map_explicitly(self) -> None:
        typed_events = {
            "incomplete": response_types.ResponseIncompleteEvent.model_validate(
                self.fixture["synthetic_sdk_schema_events"]["incomplete"]
            ),
            "failed": response_types.ResponseFailedEvent.model_validate(
                self.fixture["synthetic_sdk_schema_events"]["failed"]
            ),
        }
        for label, event in typed_events.items():
            with self.subTest(label=label):
                service = _bare_stream_service([event])
                runtime = object.__new__(mini_rl_env._BenchmarkRuntime)
                runtime.responses_traces = []
                runtime._pending_responses_trace_indexes = mini_rl_env.deque()
                runtime.responses_incomplete_pending = False
                runtime.responses_incomplete_event = None
                runtime.rate_limit_exhausted_pending = False
                runtime.rate_limit_exhausted_event = None
                runtime.api_error_pending = False
                runtime.api_error_event = None
                service.set_benchmark_outcome_callback(runtime.record_responses_trace)

                asyncio.run(service._process_context(types.SimpleNamespace()))
                trace = runtime.responses_traces[0]
                self.assertEqual(trace["response_status"], label)
                self.assertEqual(trace["returned_service_tier"], "default")
                self.assertIsInstance(trace["usage"]["reasoning_tokens"], int)
                if label == "incomplete":
                    self.assertTrue(runtime.responses_incomplete_pending)
                    self.assertEqual(runtime.responses_incomplete_event["reason"], "max_output_tokens")
                    self.assertFalse(runtime.api_error_pending)
                else:
                    self.assertTrue(runtime.api_error_pending)
                    self.assertEqual(runtime.api_error_event["code"], "server_error")
                    self.assertFalse(runtime.responses_incomplete_pending)

    def test_response_error_event_preserves_sdk_error_fields(self) -> None:
        event = response_types.ResponseErrorEvent.model_validate(
            {
                "type": "error",
                "sequence_number": 1,
                "code": "server_error",
                "message": "synthetic response error",
                "param": None,
            }
        )
        service = _bare_stream_service([event])
        asyncio.run(service._process_context(types.SimpleNamespace()))
        trace = service.get_responses_traces()[0]
        self.assertEqual(trace["response_status"], "failed")
        self.assertEqual(trace["error"]["code"], "server_error")
        self.assertEqual(trace["error"]["message"], "synthetic response error")

    def test_incomplete_and_failed_markers_finalize_to_locked_terminal_reasons(self) -> None:
        class Controller:
            @staticmethod
            def has_pending_async_completions() -> bool:
                return False

        async def finalize(trace: dict) -> tuple[types.SimpleNamespace, dict]:
            runtime = types.SimpleNamespace(
                responses_traces=[],
                _pending_responses_trace_indexes=mini_rl_env.deque(),
                responses_incomplete_pending=False,
                responses_incomplete_event=None,
                rate_limit_exhausted_pending=False,
                rate_limit_exhausted_event=None,
                api_error_pending=False,
                api_error_event=None,
                transport_empty_retry_enabled=False,
                empty_response_count=0,
                empty_response_retry_success_count=0,
                no_tool_call_count=0,
                world=mini_rl_env.SyntheticWorld(),
                turn_logs=[],
                turn_count=0,
                stop_requested=False,
                terminal_reason="max_turns_exhausted",
                max_turns=50,
                last_error_event=None,
            )
            runtime.record_responses_trace = types.MethodType(
                mini_rl_env._BenchmarkRuntime.record_responses_trace, runtime
            )
            runtime._responses_trace_is_rate_limit = (
                mini_rl_env._BenchmarkRuntime._responses_trace_is_rate_limit
            )
            runtime.claim_responses_trace_index = types.MethodType(
                mini_rl_env._BenchmarkRuntime.claim_responses_trace_index, runtime
            )
            runtime.attach_active_inference_capture = lambda turn: None
            runtime._append_replay_stream_event = lambda *args, **kwargs: None

            def request_stop(reason: str, **kwargs) -> None:
                runtime.stop_requested = True
                runtime.terminal_reason = reason

            runtime.request_stop = request_stop
            runtime.record_responses_trace(trace)

            tracker = mini_rl_env._BenchmarkResponseTracker(runtime, Controller())
            tracker._response_started = True
            tracker._response_end_seen = True
            tracker._pending_tool_results = 0
            tracker._has_function_calls = False
            tracker._response_text = ""
            tracker._response_text_raw = ""
            tracker._response_thought = ""
            tracker._usage_metrics = None
            tracker._ttfb_metrics = None
            tracker._response_state_before = runtime.world.state_snapshot()
            tracker._bad_before = runtime.world.bad_actions_count
            tracker._decision_ms = 1.0
            tracker._tool_calls = []
            tracker._transport_empty_retries = 0
            await tracker._finalize_if_ready()
            return runtime, runtime.turn_logs[0]

        incomplete_trace = {
            "trace_index": 1,
            "response_status": "incomplete",
            "response_id": "resp_incomplete",
            "request_id": "req_incomplete",
            "incomplete_reason": "max_output_tokens",
            "error": None,
        }
        incomplete_runtime, incomplete_turn = asyncio.run(finalize(incomplete_trace))
        self.assertEqual(incomplete_runtime.terminal_reason, "response_incomplete")
        self.assertEqual(incomplete_turn["failure_class"], "response_incomplete")
        self.assertEqual(incomplete_turn["responses_trace_index"], 1)
        self.assertEqual(incomplete_turn["bad_action_increment"], 0)

        failed_trace = {
            "trace_index": 1,
            "response_status": "failed",
            "response_id": "resp_failed",
            "request_id": "req_failed",
            "incomplete_reason": None,
            "error": {"code": "server_error", "status_code": 503},
        }
        failed_runtime, failed_turn = asyncio.run(finalize(failed_trace))
        self.assertEqual(failed_runtime.terminal_reason, "inference_error")
        self.assertEqual(failed_turn["failure_class"], "inference_failure")
        self.assertEqual(failed_turn["responses_trace_index"], 1)
        self.assertEqual(failed_turn["bad_action_increment"], 0)

    def test_timeout_injection_distinguishes_total_request_and_stream_idle(self) -> None:
        async def consume(service):
            return [event async for event in service._iter_response_events({}, {})]

        request_service = _bare_stream_service([], request_timeout=0.01, idle_timeout=1)
        request_service._client.responses.stream = lambda **kwargs: _EventStream(
            [], enter_delay=0.05
        )
        with self.assertRaises(openai_responses_service.ResponsesRequestTimeout):
            asyncio.run(consume(request_service))

        idle_service = _bare_stream_service([], request_timeout=1, idle_timeout=0.01)
        idle_service._client.responses.stream = lambda **kwargs: _EventStream(
            [types.SimpleNamespace(type="response.created")], event_delay=0.05
        )
        with self.assertRaises(openai_responses_service.ResponsesStreamIdleTimeout):
            asyncio.run(consume(idle_service))

    def test_provider_request_timeout_does_not_bound_tool_execution(self) -> None:
        call_item = types.SimpleNamespace(
            type="function_call",
            id="fc_timeout_boundary",
            call_id="call_timeout_boundary",
            name="lookup_probe",
            arguments="{}",
        )
        response = types.SimpleNamespace(
            id="resp_timeout_boundary",
            model="gpt-5.6-luna",
            status="completed",
            service_tier="default",
            incomplete_details=None,
            error=None,
            output=[call_item],
            usage=None,
        )
        events = [
            types.SimpleNamespace(type="response.output_item.added", item=call_item),
            types.SimpleNamespace(
                type="response.function_call_arguments.done",
                item_id=call_item.id,
                name=call_item.name,
                arguments="{}",
            ),
            types.SimpleNamespace(type="response.completed", response=response),
        ]
        service = _bare_stream_service(events, request_timeout=0.02, idle_timeout=0.02)

        async def slow_tool_dispatch(calls) -> None:
            await asyncio.sleep(0.05)

        service.run_function_calls = mock.AsyncMock(side_effect=slow_tool_dispatch)
        asyncio.run(service._process_context(types.SimpleNamespace()))
        service.run_function_calls.assert_awaited_once()

    def test_429_and_5xx_faults_are_sanitized_and_classified(self) -> None:
        class RaisingStream:
            def __init__(self, exc):
                self.exc = exc

            async def __aenter__(self):
                raise self.exc

            async def __aexit__(self, exc_type, exc, tb):
                return False

        for status, error_cls, expected_rate_limit in (
            (429, openai.RateLimitError, True),
            (503, openai.APIStatusError, False),
        ):
            request = httpx.Request("POST", "https://api.openai.com/v1/responses")
            response = httpx.Response(
                status,
                request=request,
                headers={"x-request-id": f"req_fault_{status}"},
            )
            body = {
                "error": {
                    "code": "rate_limit_exceeded" if status == 429 else "server_error",
                    "message": "synthetic fault",
                    "type": "server_error",
                }
            }
            exc = error_cls("synthetic fault", response=response, body=body)
            service = _bare_stream_service([])
            service._client.responses.stream = lambda _exc=exc, **kwargs: RaisingStream(_exc)
            runtime = object.__new__(mini_rl_env._BenchmarkRuntime)
            runtime.responses_traces = []
            runtime._pending_responses_trace_indexes = mini_rl_env.deque()
            runtime.responses_incomplete_pending = False
            runtime.responses_incomplete_event = None
            runtime.rate_limit_exhausted_pending = False
            runtime.rate_limit_exhausted_event = None
            runtime.api_error_pending = False
            runtime.api_error_event = None
            service.set_benchmark_outcome_callback(runtime.record_responses_trace)

            with self.subTest(status=status):
                with self.assertRaises(error_cls):
                    asyncio.run(service._process_context(types.SimpleNamespace()))
                trace = runtime.responses_traces[0]
                self.assertEqual(trace["error"]["status_code"], status)
                self.assertEqual(trace["request_id"], f"req_fault_{status}")
                self.assertEqual(runtime.rate_limit_exhausted_pending, expected_rate_limit)
                self.assertEqual(runtime.api_error_pending, not expected_rate_limit)


class Gpt56NonInterferenceTests(unittest.TestCase):
    def test_legacy_factory_endpoint_class_and_max_token_mapping(self) -> None:
        cases = (
            ("gpt-5.2", None),
            ("gpt-5.1", None),
            ("gpt-4.1", None),
            ("gpt-5.6-luna", "https://example.test/v1"),
        )
        for model, base_url in cases:
            service = llm_factory.create_llm_service(
                llm_factory.LLMServiceConfig(
                    provider=llm_factory.LLMProvider.OPENAI,
                    model=model,
                    api_key="offline-test-key",
                    max_tokens=4096,
                    openai_base_url=base_url,
                )
            )
            with self.subTest(model=model, base_url=base_url):
                self.assertNotIsInstance(
                    service, openai_responses_service.OpenAIResponsesLLMService
                )
                self.assertEqual(service._settings["max_tokens"], 4096)

    def test_gpt54_shared_service_retains_legacy_runtime_scope_and_wire_shape(self) -> None:
        service = _configured_service("gpt-5.4", max_tokens=4096)
        policy = mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=service,
            provider=llm_factory.LLMProvider.OPENAI,
            model="gpt-5.4",
            thinking="minimal",
            thinking_budget=None,
            openai_base_url=None,
        )
        params = service._responses_request_params(
            LLMContext(messages=[{"role": "user", "content": "legacy snapshot"}])
        )
        self.assertIsInstance(
            service, openai_responses_service.OpenAIResponsesLLMService
        )
        self.assertFalse(service._benchmark_observability_enabled)
        self.assertFalse(hasattr(service, "_encrypted_reasoning_replay_enabled"))
        self.assertIsNone(service._request_timeout_secs)
        self.assertIsNone(service._stream_idle_timeout_secs)
        self.assertEqual(params["reasoning"], {"effort": "low"})
        self.assertEqual(params["max_output_tokens"], 4096)
        self.assertNotIn("store", params)
        self.assertNotIn("include", params)
        self.assertEqual(policy, "openai:gpt-5.4 responses reasoning.effort=low")

        call_item = types.SimpleNamespace(
            type="function_call",
            id="fc_gpt54_legacy",
            call_id="call_gpt54_legacy",
            name="lookup_probe",
            arguments="{}",
        )
        events = [
            types.SimpleNamespace(type="response.output_item.added", item=call_item),
            types.SimpleNamespace(
                type="response.function_call_arguments.done",
                item_id=call_item.id,
                name=call_item.name,
                arguments="{}",
            ),
            types.SimpleNamespace(
                type="response.completed",
                response=types.SimpleNamespace(
                    id="resp_gpt54_legacy",
                    model="gpt-5.4",
                    status="completed",
                    output=[call_item],
                    usage=None,
                ),
            ),
        ]
        service.start_ttfb_metrics = mock.AsyncMock()
        service.stop_ttfb_metrics = mock.AsyncMock()
        service.start_llm_usage_metrics = mock.AsyncMock()
        service.run_function_calls = mock.AsyncMock()
        service._responses_request_params = lambda context: {}
        service._client = types.SimpleNamespace(
            responses=types.SimpleNamespace(stream=lambda **kwargs: _EventStream(events))
        )
        asyncio.run(service._process_context(types.SimpleNamespace()))
        service.run_function_calls.assert_awaited_once()
        self.assertEqual(service.get_responses_traces(), [])
        self.assertFalse(hasattr(service, "_response_output_groups"))

    def test_thinking_behavior_snapshots_for_legacy_routes(self) -> None:
        cases = (
            ("gpt-5.4", None, "minimal", {"reasoning": {"effort": "low"}}, "openai:gpt-5.4 responses reasoning.effort=low"),
            ("gpt-5.2", None, "none", {"reasoning_effort": "minimal"}, "openai:gpt-5 reasoning_effort=minimal"),
            ("gpt-5.1", None, "medium", {"reasoning_effort": "medium"}, "openai:gpt-5 reasoning_effort=medium"),
            ("gpt-4.1", None, "high", {}, "openai:gpt-4.1 reasoning_n/a"),
            ("gpt-5.6-luna", "https://example.test/v1", "xhigh", {"reasoning_effort": "xhigh"}, "openai:gpt-5 reasoning_effort=xhigh"),
        )
        for model, base_url, thinking, expected_extra, expected_policy in cases:
            service = types.SimpleNamespace(_settings={"extra": {}})
            policy = mini_rl_env._apply_benchmark_thinking_mode(
                llm_service=service,
                provider=llm_factory.LLMProvider.OPENAI,
                model=model,
                thinking=thinking,
                thinking_budget=None,
                openai_base_url=base_url,
            )
            with self.subTest(model=model, base_url=base_url):
                self.assertEqual(service._settings["extra"], expected_extra)
                self.assertEqual(policy, expected_policy)

    def test_non_openai_provider_snapshot_is_unchanged(self) -> None:
        service = types.SimpleNamespace(_settings={"extra": {"keep": True}})
        policy = mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=service,
            provider=llm_factory.LLMProvider.GOOGLE,
            model="gemini-3.1-pro-preview",
            thinking="medium",
            thinking_budget=None,
            openai_base_url=None,
        )
        self.assertEqual(policy, "google:gemini-3-family thinking_level=medium")
        self.assertEqual(service._settings["extra"], {"keep": True})


if __name__ == "__main__":
    unittest.main()
