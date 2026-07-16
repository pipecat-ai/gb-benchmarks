import asyncio
import importlib.util
import json
import sys
import tempfile
import time
import types
import unittest
from collections import deque
from pathlib import Path
from unittest import mock

from pipecat.clocks.system_clock import SystemClock
from pipecat.frames.frames import FunctionCallFromLLM, StartFrame
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


mini_rl_env = _load_module("mini_rl_env_empty_retry_test", "mini-rl-env.py")
evaluate_runs = _load_module("evaluate_runs_empty_retry_test", "evaluate_runs.py")
build_primary_leaderboard = _load_module(
    "build_primary_leaderboard_empty_retry_test",
    "build_primary_leaderboard.py",
)


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


class FakeContext:
    def __init__(self) -> None:
        self.messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
        ]

    def get_messages(self, llm_specific_filter=None):
        return list(self.messages)

    def set_messages(self, messages) -> None:
        self.messages = list(messages)


class FakeAdapter:
    id_for_llm_specific_messages = None

    def get_llm_invocation_params(self, context):
        return {"messages": context.get_messages()}


class FakePipelineTask:
    def __init__(self, controller) -> None:
        self.controller = controller
        self.queued_frames = []
        self.watchdog_handles_seen_on_queue = []

    def has_finished(self) -> bool:
        return False

    async def queue_frames(self, frames) -> None:
        self.watchdog_handles_seen_on_queue.append(
            self.controller._no_tool_watchdog_handle
        )
        self.queued_frames.extend(frames)


class EmptyRetryTests(unittest.TestCase):
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
        base_url: str = "https://inference.baseten.co/v1",
        model: str = "zai-org/GLM-5.2",
    ):
        args = types.SimpleNamespace(
            capture_inference_inputs=True,
            openai_base_url=base_url,
            provider="openai",
            model=model,
            thinking="high",
            thinking_budget=None,
            max_tokens=8192,
        )
        runtime = types.SimpleNamespace(
            args=args,
            stop_requested=False,
            inference_suppressed=False,
            no_tool_call_count=0,
            last_error_event=None,
            turn_logs=[],
            turn_count=0,
            max_turns=50,
            request_stop=mock.Mock(),
            world=FakeWorld(),
            transport_empty_retry_enabled=mini_rl_env._baseten_transport_retry_enabled(
                base_url, model
            ),
            empty_response_count=0,
            empty_response_retry_success_count=0,
            llm_context=FakeContext(),
            llm_service=types.SimpleNamespace(
                get_llm_adapter=lambda: FakeAdapter(),
                _settings={},
                _tool_config={},
            ),
            inference_inputs=[],
            _pending_inference_capture_indexes=deque(),
            _active_inference_capture_index=None,
            _append_replay_stream_event=mock.Mock(),
            started_monotonic=time.perf_counter() - 0.01,
            initial_state_snapshot={"sector": 3080, "credits": 1000},
            finished_called=False,
            finished_message=None,
            post_finished_call_count=0,
            async_completion_timeout_count=0,
            terminal_reason="max_turns_exhausted",
        )
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

    async def _empty_attempt(self, tracker) -> None:
        await tracker.process_frame(
            mini_rl_env.LLMFullResponseStartFrame(),
            mini_rl_env.FrameDirection.DOWNSTREAM,
        )
        await tracker.process_frame(
            mini_rl_env.LLMFullResponseEndFrame(),
            mini_rl_env.FrameDirection.DOWNSTREAM,
        )

    async def _empty_attempt_with_signature_probe(self, tracker) -> bool:
        await tracker.process_frame(
            mini_rl_env.LLMFullResponseStartFrame(),
            mini_rl_env.FrameDirection.DOWNSTREAM,
        )
        signature_matches = tracker._matches_transport_empty_response_signature()
        await tracker.process_frame(
            mini_rl_env.LLMFullResponseEndFrame(),
            mini_rl_env.FrameDirection.DOWNSTREAM,
        )
        return signature_matches

    async def _successful_tool_attempt(self, tracker) -> None:
        function_call = FunctionCallFromLLM(
            function_name="move",
            tool_call_id="move-1",
            arguments={"to_sector": 1611},
            context=None,
        )
        await tracker.process_frame(
            mini_rl_env.LLMFullResponseStartFrame(),
            mini_rl_env.FrameDirection.DOWNSTREAM,
        )
        await tracker.process_frame(
            mini_rl_env.FunctionCallsStartedFrame([function_call]),
            mini_rl_env.FrameDirection.DOWNSTREAM,
        )
        await tracker.process_frame(
            mini_rl_env.LLMFullResponseEndFrame(),
            mini_rl_env.FrameDirection.DOWNSTREAM,
        )
        await tracker.process_frame(
            mini_rl_env.FunctionCallResultFrame(
                function_name="move",
                tool_call_id="move-1",
                arguments={"to_sector": 1611},
                result={"status": "Executed."},
            ),
            mini_rl_env.FrameDirection.DOWNSTREAM,
        )

    def test_baseten_empty_retry_model_predicate_matches_target_variants(self) -> None:
        for model in (
            "zai-org/GLM-5.2",
            "glm-5.2",
            "glm5.2",
            "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B",
            "nemotron-3-ultra-550b",
            "thinkingmachines/inkling",
            "inkling",
        ):
            with self.subTest(model=model):
                self.assertTrue(mini_rl_env._is_baseten_retry_eligible_model(model))

        for model in (
            "glm-4.7-flash",
            "nemotron-3-super-120b",
            "some-other-model",
            "my-inkling",
            "inkling-v2",
            "thinkingmachines/inkling-preview",
        ):
            with self.subTest(model=model):
                self.assertFalse(mini_rl_env._is_baseten_retry_eligible_model(model))

    def test_baseten_transport_retry_helper_scopes_endpoint_and_model(self) -> None:
        enabled_cases = (
            ("https://inference.baseten.co/v1", "thinkingmachines/inkling"),
            ("https://model-abc.api.baseten.co/v1", "inkling"),
            ("https://inference.baseten.co/v1", "zai-org/GLM-5.2"),
            (
                "https://inference.baseten.co/v1",
                "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B",
            ),
        )
        disabled_cases = (
            ("https://api.openai.com/v1", "thinkingmachines/inkling"),
            ("https://inference.baseten.co/v1", "some-other-model"),
            ("https://inference.baseten.co/v1", "my-inkling"),
            ("https://inference.baseten.co/v1", "inkling-v2"),
            ("https://inference.baseten.co/v1", "thinkingmachines/inkling-preview"),
        )

        for expected, cases in ((True, enabled_cases), (False, disabled_cases)):
            for base_url, model in cases:
                with self.subTest(expected=expected, base_url=base_url, model=model):
                    self.assertEqual(
                        mini_rl_env._baseten_transport_retry_enabled(base_url, model),
                        expected,
                    )
                    runtime = self._make_runtime(base_url=base_url, model=model)
                    tracker = mini_rl_env._BenchmarkResponseTracker.__new__(
                        mini_rl_env._BenchmarkResponseTracker
                    )
                    tracker._runtime = runtime
                    self.assertEqual(runtime.transport_empty_retry_enabled, expected)
                    self.assertEqual(tracker._transport_empty_retry_enabled(), expected)

    def test_empty_retry_success_does_not_count_bad_action_or_append_nudge(self) -> None:
        async def _run() -> None:
            runtime = self._make_runtime()
            tracker, controller, pipeline_task = await self._make_tracker(runtime)
            runtime.queue_inference_capture(["initial_run"])

            await self._empty_attempt(tracker)

            self.assertEqual(runtime.turn_logs, [])
            self.assertEqual(runtime.turn_count, 0)
            self.assertEqual(runtime.no_tool_call_count, 0)
            self.assertEqual(runtime.world.bad_actions_count, 0)
            self.assertIsNone(controller._no_tool_watchdog_handle)
            self.assertEqual(len(pipeline_task.queued_frames), 1)
            self.assertIsInstance(pipeline_task.queued_frames[0], mini_rl_env.LLMRunFrame)
            self.assertEqual(pipeline_task.watchdog_handles_seen_on_queue, [None])
            self.assertFalse(
                any(isinstance(frame, mini_rl_env.LLMMessagesAppendFrame) for frame in pipeline_task.queued_frames)
            )
            self.assertEqual(runtime.empty_response_count, 1)
            self.assertEqual(runtime.empty_response_retry_success_count, 0)
            self.assertTrue(runtime.inference_inputs[0]["discarded"])
            self.assertEqual(runtime.inference_inputs[1]["reasons"], ["transport_empty_retry:1"])

            await self._successful_tool_attempt(tracker)

            self.assertEqual(runtime.turn_count, 1)
            self.assertEqual(runtime.no_tool_call_count, 0)
            self.assertEqual(runtime.world.bad_actions_count, 0)
            self.assertEqual(len(runtime.turn_logs), 1)
            turn = runtime.turn_logs[0]
            self.assertEqual(turn["failure_class"], "none")
            self.assertEqual(turn["transport_empty_retries"], 1)
            self.assertEqual(turn["transport_empty_attempts"], 2)
            self.assertEqual(turn["inference_index"], 2)
            self.assertEqual(runtime.inference_inputs[1]["finalized_llm_turn"], 1)
            self.assertEqual(list(runtime._pending_inference_capture_indexes), [])
            self.assertIsNone(runtime._active_inference_capture_index)
            self.assertEqual(runtime.empty_response_retry_success_count, 1)
            summary = mini_rl_env._BenchmarkRuntime.build_summary(runtime)
            self.assertEqual(summary["empty_response_count"], 1)
            self.assertEqual(summary["empty_response_retry_success_count"], 1)

            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_empty_retries_exhaust_then_existing_no_tool_nudge_path_runs(self) -> None:
        async def _run() -> None:
            runtime = self._make_runtime()
            tracker, controller, pipeline_task = await self._make_tracker(runtime)
            runtime.queue_inference_capture(["initial_run"])

            for _attempt in range(mini_rl_env.MAX_TRANSPORT_EMPTY_RETRIES + 1):
                await self._empty_attempt(tracker)

            self.assertEqual(runtime.turn_count, 1)
            self.assertEqual(runtime.no_tool_call_count, 1)
            self.assertEqual(runtime.world.bad_actions_count, 1)
            self.assertEqual(runtime.empty_response_count, 3)
            self.assertEqual(runtime.empty_response_retry_success_count, 0)
            turn = runtime.turn_logs[0]
            self.assertEqual(turn["failure_class"], "no_tool_call")
            self.assertEqual(turn["bad_action_increment"], 1)
            self.assertEqual(turn["transport_empty_retries"], 2)
            self.assertEqual(turn["transport_empty_attempts"], 3)
            self.assertEqual(
                turn["inference_index"],
                mini_rl_env.MAX_TRANSPORT_EMPTY_RETRIES + 1,
            )
            self.assertEqual(
                len(runtime.inference_inputs),
                mini_rl_env.MAX_TRANSPORT_EMPTY_RETRIES + 1,
            )
            for entry in runtime.inference_inputs[:-1]:
                self.assertTrue(entry["discarded"])
            final_capture = runtime.inference_inputs[-1]
            self.assertNotIn("discarded", final_capture)
            self.assertEqual(final_capture["finalized_llm_turn"], 1)
            self.assertEqual(list(runtime._pending_inference_capture_indexes), [])
            self.assertIsNone(runtime._active_inference_capture_index)
            self.assertIsNotNone(controller._no_tool_watchdog_handle)
            self.assertEqual(
                sum(isinstance(frame, mini_rl_env.LLMRunFrame) for frame in pipeline_task.queued_frames),
                2,
            )

            controller._no_tool_watchdog_fire()
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            self.assertEqual(controller._no_tool_nudge_count, 1)
            self.assertTrue(
                any(isinstance(frame, mini_rl_env.LLMMessagesAppendFrame) for frame in pipeline_task.queued_frames)
            )
            self.assertEqual(controller._inference_reasons, ["no_tool_nudge"])

            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_non_baseten_empty_no_usage_response_uses_normal_no_tool_path(self) -> None:
        async def _run() -> None:
            runtime = self._make_runtime(base_url="https://api.openai.com/v1")
            tracker, controller, pipeline_task = await self._make_tracker(runtime)
            runtime.queue_inference_capture(["initial_run"])

            self.assertFalse(runtime.transport_empty_retry_enabled)
            self.assertFalse(tracker._transport_empty_retry_enabled())

            signature_matches = await self._empty_attempt_with_signature_probe(tracker)

            self.assertFalse(signature_matches)
            self.assertEqual(len(pipeline_task.queued_frames), 0)
            self.assertEqual(runtime.empty_response_count, 0)
            self.assertEqual(runtime.empty_response_retry_success_count, 0)
            self.assertEqual(runtime.no_tool_call_count, 1)
            self.assertEqual(runtime.world.bad_actions_count, 1)
            self.assertEqual(runtime.turn_count, 1)
            turn = runtime.turn_logs[0]
            self.assertEqual(turn["failure_class"], "no_tool_call")
            self.assertNotIn("transport_empty_retries", turn)
            self.assertNotIn("transport_empty_attempts", turn)
            summary = mini_rl_env._BenchmarkRuntime.build_summary(runtime)
            self.assertNotIn("empty_response_count", summary)
            self.assertNotIn("empty_response_retry_success_count", summary)
            self.assertIsNotNone(controller._no_tool_watchdog_handle)

            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_baseten_non_target_empty_no_usage_response_uses_normal_no_tool_path(self) -> None:
        async def _run() -> None:
            runtime = self._make_runtime(model="some-other-model")
            tracker, controller, pipeline_task = await self._make_tracker(runtime)
            runtime.queue_inference_capture(["initial_run"])

            self.assertFalse(runtime.transport_empty_retry_enabled)
            self.assertFalse(tracker._transport_empty_retry_enabled())

            signature_matches = await self._empty_attempt_with_signature_probe(tracker)

            self.assertFalse(signature_matches)
            self.assertEqual(len(pipeline_task.queued_frames), 0)
            self.assertEqual(runtime.empty_response_count, 0)
            self.assertEqual(runtime.empty_response_retry_success_count, 0)
            self.assertEqual(runtime.no_tool_call_count, 1)
            self.assertEqual(runtime.world.bad_actions_count, 1)
            self.assertEqual(runtime.turn_count, 1)
            turn = runtime.turn_logs[0]
            self.assertEqual(turn["failure_class"], "no_tool_call")
            self.assertNotIn("transport_empty_retries", turn)
            self.assertNotIn("transport_empty_attempts", turn)
            summary = mini_rl_env._BenchmarkRuntime.build_summary(runtime)
            self.assertNotIn("empty_response_count", summary)
            self.assertNotIn("empty_response_retry_success_count", summary)
            self.assertIsNotNone(controller._no_tool_watchdog_handle)

            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_text_only_no_tool_without_usage_is_not_retried(self) -> None:
        async def _run() -> None:
            runtime = self._make_runtime()
            tracker, controller, pipeline_task = await self._make_tracker(runtime)
            runtime.queue_inference_capture(["initial_run"])

            await tracker.process_frame(
                mini_rl_env.LLMFullResponseStartFrame(),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )
            await tracker.process_frame(
                mini_rl_env.LLMTextFrame("I should inspect status next."),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )
            await tracker.process_frame(
                mini_rl_env.LLMFullResponseEndFrame(),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )

            self.assertEqual(len(pipeline_task.queued_frames), 0)
            self.assertEqual(runtime.empty_response_count, 0)
            self.assertEqual(runtime.empty_response_retry_success_count, 0)
            self.assertEqual(runtime.no_tool_call_count, 1)
            self.assertEqual(runtime.world.bad_actions_count, 1)
            self.assertEqual(runtime.turn_count, 1)
            self.assertEqual(runtime.turn_logs[0]["failure_class"], "no_tool_call")
            self.assertEqual(runtime.turn_logs[0]["raw_response_text"], "I should inspect status next.")
            self.assertIsNotNone(controller._no_tool_watchdog_handle)

            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_whitespace_only_no_usage_response_is_not_retried(self) -> None:
        async def _run() -> None:
            runtime = self._make_runtime()
            tracker, controller, pipeline_task = await self._make_tracker(runtime)
            runtime.queue_inference_capture(["initial_run"])

            await tracker.process_frame(
                mini_rl_env.LLMFullResponseStartFrame(),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )
            await tracker.process_frame(
                mini_rl_env.LLMTextFrame(" \n\t "),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )
            self.assertFalse(tracker._matches_transport_empty_response_signature())
            await tracker.process_frame(
                mini_rl_env.LLMFullResponseEndFrame(),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )

            self.assertEqual(len(pipeline_task.queued_frames), 0)
            self.assertEqual(runtime.empty_response_count, 0)
            self.assertEqual(runtime.empty_response_retry_success_count, 0)
            self.assertEqual(runtime.no_tool_call_count, 1)
            self.assertEqual(runtime.world.bad_actions_count, 1)
            self.assertEqual(runtime.turn_count, 1)
            turn = runtime.turn_logs[0]
            self.assertEqual(turn["failure_class"], "no_tool_call")
            self.assertEqual(turn["raw_response_text"], "")
            self.assertEqual(turn["transport_empty_retries"], 0)
            self.assertEqual(turn["transport_empty_attempts"], 1)
            self.assertIsNotNone(controller._no_tool_watchdog_handle)

            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_error_event_empty_response_is_not_retried(self) -> None:
        async def _run() -> None:
            runtime = self._make_runtime()
            runtime.last_error_event = {
                "endpoint": "inference",
                "error": "synthetic failure",
                "synthesized": True,
                "status": 500,
            }
            tracker, controller, pipeline_task = await self._make_tracker(runtime)
            runtime.queue_inference_capture(["initial_run"])

            await self._empty_attempt(tracker)

            self.assertEqual(len(pipeline_task.queued_frames), 0)
            self.assertEqual(runtime.empty_response_count, 0)
            self.assertEqual(runtime.no_tool_call_count, 1)
            self.assertEqual(runtime.world.bad_actions_count, 1)
            self.assertEqual(runtime.turn_count, 1)
            self.assertEqual(runtime.turn_logs[0]["failure_class"], "no_tool_call")
            self.assertEqual(runtime.turn_logs[0]["error_event"]["synthesized"], True)

            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_new_telemetry_does_not_change_eval_or_leaderboard_grouping(self) -> None:
        base_payload = {
            "schema_version": "mini_rl_run.v3",
            "metadata": {
                "initial_state": {"sector": 3080, "credits": 1000},
                "task_variant": "natural",
                "task_prompt_version": "v1",
                "task_prompt_hash": "prompt-a",
                "leaderboard_prompt_id": "natural",
            },
            "config": {
                "provider": "openai",
                "model": "zai-org/GLM-5.2",
                "thinking": "high",
                "max_tokens": 8192,
                "openai_base_url": "https://inference.baseten.co/v1",
            },
            "summary": {
                "final_sector": 3080,
                "final_credits": 1000,
                "bad_actions_count": 1,
                "no_tool_call_count": 1,
                "turns_executed": 1,
                "reached_mega_anytime": False,
                "recharge_to_full_at_mega": False,
            },
            "termination": {"reason": "max_turns_exhausted", "finished_called": False},
            "turns": [
                {
                    "llm_turn": 1,
                    "decision_ms": 10.0,
                    "tool_calls": [],
                    "raw_response_text": "",
                    "failure_class": "no_tool_call",
                    "bad_actions_before": 0,
                    "bad_actions_after": 1,
                    "bad_action_increment": 1,
                    "state_before": {"sector": 3080, "credits": 1000},
                    "state_after": {"sector": 3080, "credits": 1000},
                }
            ],
        }
        telemetry_payload = json.loads(json.dumps(base_payload))
        telemetry_payload["summary"]["empty_response_count"] = 2
        telemetry_payload["summary"]["empty_response_retry_success_count"] = 1
        telemetry_payload["turns"][0]["transport_empty_retries"] = 1
        telemetry_payload["turns"][0]["transport_empty_attempts"] = 2

        base_metrics = evaluate_runs._derive_run_metrics(
            Path("base.json"),
            base_payload,
            report_judge=None,
        )
        telemetry_metrics = evaluate_runs._derive_run_metrics(
            Path("telemetry.json"),
            telemetry_payload,
            report_judge=None,
        )

        for key in (
            "no_tool_call_count",
            "bad_actions_count",
            "tool_discipline_score",
            "group_key",
        ):
            self.assertEqual(base_metrics[key], telemetry_metrics[key])

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "base.json"
            telemetry_path = Path(tmpdir) / "telemetry.json"
            base_path.write_text(json.dumps(base_payload), encoding="utf-8")
            telemetry_path.write_text(json.dumps(telemetry_payload), encoding="utf-8")

            prompt_id, prompt_hash = build_primary_leaderboard._resolve_leaderboard_prompt_id(
                [base_path, telemetry_path],
                explicit_prompt_id=None,
            )
            rows, _rubric_versions = build_primary_leaderboard._build_rows(
                [base_path, telemetry_path],
                enriched_by_file={
                    str(base_path.resolve()): base_metrics,
                    str(telemetry_path.resolve()): telemetry_metrics,
                },
                model_name_aliases={},
            )

        self.assertEqual(prompt_id, "natural")
        self.assertEqual(prompt_hash, "prompt-a")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["n"], 2)
        self.assertEqual(rows[0]["tool_discipline_score_mean"], base_metrics["tool_discipline_score"])


if __name__ == "__main__":
    unittest.main()
