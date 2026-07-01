import asyncio
import importlib.util
import sys
import time
import types
import unittest
from collections import deque
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest import mock

import httpx
import openai
from pipecat.clocks.system_clock import SystemClock
from pipecat.frames.frames import StartFrame
from pipecat.processors.frame_processor import FrameProcessorSetup
from pipecat.utils.asyncio.task_manager import TaskManager, TaskManagerParams


PORT_TO_PORT_DIR = Path(__file__).resolve().parents[1]
if str(PORT_TO_PORT_DIR) not in sys.path:
    sys.path.insert(0, str(PORT_TO_PORT_DIR))


def _load_module(name: str, relative_path: str):
    path = PORT_TO_PORT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mini_rl_env = _load_module("mini_rl_env_rate_limit_test", "mini-rl-env.py")


class FakeWorld:
    def __init__(self) -> None:
        self.bad_actions_count = 0
        self.state = types.SimpleNamespace(sector=3080, credits=1000)
        self.event_history = []
        self._snapshot = {"sector": 3080, "credits": 1000}

    def state_snapshot(self) -> dict[str, int]:
        return dict(self._snapshot)

    def increment_bad_action(self) -> None:
        self.bad_actions_count += 1


class FakePipelineTask:
    def __init__(self, controller) -> None:
        self.controller = controller
        self.queued_frames = []

    def has_finished(self) -> bool:
        return False

    async def queue_frames(self, frames) -> None:
        self.queued_frames.extend(frames)


class FakeCompletions:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    async def create(self, **params):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeOpenAIService:
    def __init__(self, outcomes) -> None:
        self.completions = FakeCompletions(outcomes)
        self._client = types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=self.completions)
        )

    async def get_chat_completions(self, params_from_context):
        return await self._client.chat.completions.create(**params_from_context)


def _rate_limit_error(*, retry_after: str | None = None):
    request = httpx.Request("POST", "https://inference.baseten.co/v1/chat/completions")
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    response = httpx.Response(
        429,
        request=request,
        headers=headers,
        json={"error": {"message": "Rate limit exceeded"}},
    )
    return openai.RateLimitError(
        "Rate limit exceeded",
        response=response,
        body={"error": {"message": "Rate limit exceeded"}},
    )


def _api_status_error(status_code: int):
    request = httpx.Request("POST", "https://inference.baseten.co/v1/chat/completions")
    response = httpx.Response(
        status_code,
        request=request,
        json={"error": {"message": "Rate limit exceeded"}},
    )
    return openai.APIStatusError(
        f"HTTP {status_code}",
        response=response,
        body={"error": {"message": "Rate limit exceeded"}},
    )


class BasetenRateLimitRetryTests(unittest.TestCase):
    def _bind_capture_runtime_methods(self, runtime) -> None:
        for name in (
            "_ensure_inference_capture_state",
            "_inference_input_entry",
            "capture_inference_input",
            "queue_inference_capture",
            "activate_next_inference_capture",
            "claim_next_inference_capture",
            "attach_active_inference_capture",
            "discard_pending_inference_capture",
            "discard_active_inference_capture",
        ):
            setattr(
                runtime,
                name,
                types.MethodType(getattr(mini_rl_env._BenchmarkRuntime, name), runtime),
            )

    def _make_runtime(
        self,
        *,
        provider: str = "openai",
        base_url: str = "https://inference.baseten.co/v1",
    ):
        runtime = mini_rl_env._BenchmarkRuntime.__new__(mini_rl_env._BenchmarkRuntime)
        runtime.args = types.SimpleNamespace(
            provider=provider,
            model="zai-org/GLM-5.2",
            openai_base_url=base_url,
            openai_no_budget_thinking_toggle=False,
            thinking="high",
            thinking_budget=None,
            max_tokens=8192,
            capture_inference_inputs=False,
        )
        runtime.world = FakeWorld()
        runtime.turn_logs = []
        runtime.turn_count = 0
        runtime.stop_requested = False
        runtime.inference_suppressed = False
        runtime.started_monotonic = time.perf_counter()
        runtime.initial_state_snapshot = {"sector": 3080}
        runtime.finished_called = False
        runtime.finished_message = None
        runtime.last_error_event = None
        runtime.no_tool_call_count = 0
        runtime.post_finished_call_count = 0
        runtime.async_completion_timeout_count = 0
        runtime.terminal_reason = "max_turns_exhausted"
        runtime.max_turns = 50
        runtime.transport_empty_retry_enabled = mini_rl_env._is_baseten_endpoint(
            base_url
        ) and mini_rl_env._is_baseten_retry_eligible_model(runtime.args.model)
        runtime.empty_response_count = 0
        runtime.empty_response_retry_success_count = 0
        runtime.rate_limit_retry_enabled = provider == "openai" and mini_rl_env._is_baseten_endpoint(
            base_url
        )
        runtime.rate_limit_count = 0
        runtime.rate_limit_retry_success_count = 0
        runtime.rate_limit_exhausted_pending = False
        runtime.rate_limit_exhausted_event = None
        runtime.llm_context = None
        runtime.llm_service = types.SimpleNamespace()
        runtime.inference_inputs = []
        runtime._pending_inference_capture_indexes = deque()
        runtime._active_inference_capture_index = None
        runtime._append_replay_stream_event = mock.Mock()
        runtime._deferred_stop_reason = None
        runtime._async_dependency_waiters = []

        def request_stop(terminal_reason: str, *, wait_for_pending_async: bool = False) -> None:
            runtime.stop_requested = True
            runtime.terminal_reason = terminal_reason
            if wait_for_pending_async:
                runtime.inference_suppressed = True

        runtime.request_stop = request_stop
        self._bind_capture_runtime_methods(runtime)
        return runtime

    async def _make_tracker(self, runtime):
        controller = mini_rl_env._BenchmarkInferenceController(runtime)
        pipeline_task = FakePipelineTask(controller)
        controller.bind_pipeline_task(pipeline_task)
        tracker = mini_rl_env._BenchmarkResponseTracker(runtime, controller)
        tracker._enable_direct_mode = True
        runtime.controller = controller
        runtime.response_tracker = tracker

        clock = SystemClock()
        clock.start()
        task_manager = TaskManager()
        task_manager.setup(TaskManagerParams(loop=asyncio.get_running_loop()))
        await tracker.setup(FrameProcessorSetup(clock=clock, task_manager=task_manager))
        await tracker.process_frame(
            StartFrame(enable_metrics=True, enable_usage_metrics=True),
            mini_rl_env.FrameDirection.DOWNSTREAM,
        )
        return tracker, controller, pipeline_task

    def test_429_then_success_retries_and_records_rate_limit_telemetry(self) -> None:
        async def _run() -> None:
            sentinel = object()
            service = FakeOpenAIService([_rate_limit_error(retry_after="0"), sentinel])
            runtime = self._make_runtime()
            sleeps = []

            async def fake_sleep(delay_seconds: float) -> None:
                sleeps.append(delay_seconds)

            status = mini_rl_env._apply_baseten_rate_limit_retry_wrapper(
                llm_service=service,
                provider=mini_rl_env.LLMProvider.OPENAI,
                openai_base_url=runtime.args.openai_base_url,
                runtime=runtime,
            )

            with mock.patch.object(
                mini_rl_env,
                "_sleep_for_rate_limit_backoff",
                side_effect=fake_sleep,
            ):
                result = await service.get_chat_completions({"stream": True})

            self.assertEqual(status, "enabled")
            self.assertIs(result, sentinel)
            self.assertEqual(service.completions.calls, 2)
            self.assertEqual(sleeps, [0.0])
            self.assertEqual(runtime.rate_limit_count, 1)
            self.assertEqual(runtime.rate_limit_retry_success_count, 1)
            self.assertEqual(runtime.empty_response_count, 0)
            self.assertEqual(runtime.empty_response_retry_success_count, 0)
            self.assertEqual(runtime.no_tool_call_count, 0)
            self.assertEqual(runtime.world.bad_actions_count, 0)
            self.assertEqual(runtime.turn_logs, [])

            summary = mini_rl_env._BenchmarkRuntime.build_summary(runtime)
            self.assertEqual(summary["rate_limit_count"], 1)
            self.assertEqual(summary["rate_limit_retry_success_count"], 1)
            self.assertEqual(summary["empty_response_count"], 0)
            self.assertEqual(summary["no_tool_call_count"], 0)
            self.assertEqual(summary["bad_actions_count"], 0)

        asyncio.run(_run())

    def test_sustained_429_exhaustion_finalizes_as_rate_limit_exhausted(
        self,
    ) -> None:
        async def _run() -> None:
            service = FakeOpenAIService(
                [
                    _api_status_error(429)
                    for _ in range(mini_rl_env.BASETEN_RATE_LIMIT_MAX_ATTEMPTS)
                ]
            )
            runtime = self._make_runtime()
            tracker, controller, pipeline_task = await self._make_tracker(runtime)
            sleeps = []

            async def fake_sleep(delay_seconds: float) -> None:
                sleeps.append(delay_seconds)

            mini_rl_env._apply_baseten_rate_limit_retry_wrapper(
                llm_service=service,
                provider=mini_rl_env.LLMProvider.OPENAI,
                openai_base_url=runtime.args.openai_base_url,
                runtime=runtime,
            )

            with mock.patch.object(
                mini_rl_env,
                "_sleep_for_rate_limit_backoff",
                side_effect=fake_sleep,
            ):
                with self.assertRaises(openai.APIStatusError):
                    await service.get_chat_completions({"stream": True})

            self.assertTrue(runtime.rate_limit_exhausted_pending)

            await tracker.process_frame(
                mini_rl_env.LLMFullResponseStartFrame(),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )
            self.assertFalse(tracker._matches_transport_empty_response_signature())
            await tracker.process_frame(
                mini_rl_env.LLMFullResponseEndFrame(),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )

            self.assertEqual(
                service.completions.calls,
                mini_rl_env.BASETEN_RATE_LIMIT_MAX_ATTEMPTS,
            )
            self.assertEqual(
                len(sleeps),
                mini_rl_env.BASETEN_RATE_LIMIT_MAX_ATTEMPTS - 1,
            )
            self.assertEqual(
                runtime.rate_limit_count,
                mini_rl_env.BASETEN_RATE_LIMIT_MAX_ATTEMPTS,
            )
            self.assertEqual(runtime.rate_limit_retry_success_count, 0)
            self.assertEqual(runtime.empty_response_count, 0)
            self.assertEqual(runtime.empty_response_retry_success_count, 0)
            self.assertEqual(runtime.no_tool_call_count, 0)
            self.assertEqual(runtime.world.bad_actions_count, 0)
            self.assertFalse(runtime.rate_limit_exhausted_pending)
            self.assertIsNone(runtime.rate_limit_exhausted_event)
            self.assertEqual(runtime.turn_count, 1)
            self.assertEqual(len(runtime.turn_logs), 1)
            turn = runtime.turn_logs[0]
            self.assertEqual(turn["failure_class"], "rate_limit_exhausted")
            self.assertTrue(turn["rate_limit_exhausted"])
            self.assertEqual(
                turn["rate_limit_event"]["error_class"],
                "rate_limit_exhausted",
            )
            self.assertEqual(
                turn["rate_limit_event"]["attempts"],
                mini_rl_env.BASETEN_RATE_LIMIT_MAX_ATTEMPTS,
            )
            self.assertEqual(turn["bad_action_increment"], 0)
            self.assertEqual(turn["transport_empty_retries"], 0)
            self.assertEqual(turn["transport_empty_attempts"], 1)
            self.assertEqual(pipeline_task.queued_frames, [])
            self.assertTrue(runtime.stop_requested)
            self.assertEqual(runtime.terminal_reason, "rate_limit_exhausted")

            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_non_429_api_status_error_is_not_retried(self) -> None:
        async def _run() -> None:
            for status_code in (400, 500):
                with self.subTest(status_code=status_code):
                    service = FakeOpenAIService([_api_status_error(status_code), object()])
                    runtime = self._make_runtime()
                    sleeps = []

                    async def fake_sleep(delay_seconds: float) -> None:
                        sleeps.append(delay_seconds)

                    mini_rl_env._apply_baseten_rate_limit_retry_wrapper(
                        llm_service=service,
                        provider=mini_rl_env.LLMProvider.OPENAI,
                        openai_base_url=runtime.args.openai_base_url,
                        runtime=runtime,
                    )

                    with mock.patch.object(
                        mini_rl_env,
                        "_sleep_for_rate_limit_backoff",
                        side_effect=fake_sleep,
                    ):
                        with self.assertRaises(openai.APIStatusError):
                            await service.get_chat_completions({"stream": True})

                    self.assertEqual(service.completions.calls, 1)
                    self.assertEqual(sleeps, [])
                    self.assertEqual(runtime.rate_limit_count, 0)
                    self.assertEqual(runtime.rate_limit_retry_success_count, 0)
                    self.assertFalse(runtime.rate_limit_exhausted_pending)
                    self.assertIsNone(runtime.rate_limit_exhausted_event)

        asyncio.run(_run())

    def test_non_baseten_endpoint_does_not_install_wrapper_or_retry(self) -> None:
        async def _run() -> None:
            first_error = _rate_limit_error(retry_after="0")
            service = FakeOpenAIService([first_error, object()])
            runtime = self._make_runtime(base_url="https://api.openai.com/v1")

            status = mini_rl_env._apply_baseten_rate_limit_retry_wrapper(
                llm_service=service,
                provider=mini_rl_env.LLMProvider.OPENAI,
                openai_base_url=runtime.args.openai_base_url,
                runtime=runtime,
            )

            with self.assertRaises(openai.RateLimitError):
                await service.get_chat_completions({"stream": True})

            self.assertEqual(status, "disabled")
            self.assertFalse(getattr(service, "_baseten_rate_limit_retry_wrapped", False))
            self.assertEqual(service.completions.calls, 1)
            self.assertEqual(runtime.rate_limit_count, 0)
            self.assertEqual(runtime.rate_limit_retry_success_count, 0)
            self.assertEqual(runtime.empty_response_count, 0)
            self.assertEqual(runtime.no_tool_call_count, 0)
            summary = mini_rl_env._BenchmarkRuntime.build_summary(runtime)
            self.assertNotIn("rate_limit_count", summary)
            self.assertNotIn("rate_limit_retry_success_count", summary)

        asyncio.run(_run())

    def test_non_openai_provider_does_not_install_wrapper_or_emit_rate_limit_telemetry(
        self,
    ) -> None:
        async def _run() -> None:
            first_error = _rate_limit_error(retry_after="0")
            service = FakeOpenAIService([first_error, object()])
            runtime = self._make_runtime(provider="anthropic")

            status = mini_rl_env._apply_baseten_rate_limit_retry_wrapper(
                llm_service=service,
                provider=mini_rl_env.LLMProvider.ANTHROPIC,
                openai_base_url=runtime.args.openai_base_url,
                runtime=runtime,
            )

            with self.assertRaises(openai.RateLimitError):
                await service.get_chat_completions({"stream": True})

            self.assertEqual(status, "disabled")
            self.assertFalse(getattr(service, "_baseten_rate_limit_retry_wrapped", False))
            self.assertEqual(service.completions.calls, 1)
            self.assertFalse(runtime.rate_limit_retry_enabled)
            self.assertEqual(runtime.rate_limit_count, 0)
            self.assertEqual(runtime.rate_limit_retry_success_count, 0)
            self.assertFalse(runtime.rate_limit_exhausted_pending)

            summary = mini_rl_env._BenchmarkRuntime.build_summary(runtime)
            self.assertNotIn("rate_limit_count", summary)
            self.assertNotIn("rate_limit_retry_success_count", summary)

        asyncio.run(_run())

    def test_retry_after_numeric_and_http_date_are_bounded(self) -> None:
        numeric_error = _rate_limit_error(retry_after="45")
        self.assertEqual(
            mini_rl_env._baseten_rate_limit_backoff_seconds(
                numeric_error,
                failed_attempt=1,
            ),
            mini_rl_env.BASETEN_RATE_LIMIT_BACKOFF_MAX_SECS,
        )

        retry_at = datetime.now(timezone.utc) + timedelta(seconds=120)
        http_date_error = _rate_limit_error(
            retry_after=format_datetime(retry_at, usegmt=True)
        )
        http_date_backoff = mini_rl_env._baseten_rate_limit_backoff_seconds(
            http_date_error,
            failed_attempt=1,
        )
        self.assertGreater(http_date_backoff, 0)
        self.assertLessEqual(
            http_date_backoff,
            mini_rl_env.BASETEN_RATE_LIMIT_BACKOFF_MAX_SECS,
        )


if __name__ == "__main__":
    unittest.main()
