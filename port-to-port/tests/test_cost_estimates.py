import importlib.util
import unittest
from pathlib import Path


PORT_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "estimate_leaderboard_costs", PORT_DIR / "estimate_leaderboard_costs.py"
)
assert SPEC and SPEC.loader
costs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(costs)


def _run(usage, *, trace_usage=None, decision_ms=1000):
    turn = {"usage": usage, "decision_ms": decision_ms}
    run = {"config": {"model": "test"}, "summary": {"turns_executed": 1}, "turns": [turn]}
    if trace_usage is not None:
        turn["responses_trace_index"] = 0
        run["responses_traces"] = [{"trace_index": 0, "usage": trace_usage}]
    return run


class TokenCostTests(unittest.TestCase):
    def test_openai_separates_cached_input_without_double_counting_reasoning(self):
        run = _run(
            {
                "prompt_tokens": 100,
                "cache_read_input_tokens": 40,
                "completion_tokens": 20,
                "reasoning_tokens": 15,
            }
        )
        cost, buckets = costs.token_cost(
            run,
            {"input": 2, "cached_input": 0.5, "output": 8, "usage_semantics": "openai"},
        )
        self.assertEqual(
            buckets,
            {"uncached_input": 60, "cached_input": 40, "cache_write": 0, "output": 20},
        )
        self.assertAlmostEqual(cost, (60 * 2 + 40 * 0.5 + 20 * 8) / 1_000_000)

    def test_google_adds_reasoning_to_billable_output(self):
        run = _run(
            {
                "prompt_tokens": 100,
                "cache_read_input_tokens": 25,
                "completion_tokens": 10,
                "reasoning_tokens": 30,
            }
        )
        _, buckets = costs.token_cost(
            run,
            {"input": 1, "cached_input": 0.1, "output": 5, "usage_semantics": "google"},
        )
        self.assertEqual(buckets["uncached_input"], 75)
        self.assertEqual(buckets["output"], 40)

    def test_anthropic_prices_base_cache_write_and_cache_read_as_disjoint(self):
        run = _run(
            {
                "prompt_tokens": 5,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 15,
                "completion_tokens": 10,
            }
        )
        _, buckets = costs.token_cost(
            run,
            {
                "input": 3,
                "cached_input": 0.3,
                "cache_write": 3.75,
                "output": 15,
                "usage_semantics": "anthropic",
            },
        )
        self.assertEqual(
            buckets,
            {"uncached_input": 5, "cached_input": 80, "cache_write": 15, "output": 10},
        )

    def test_responses_trace_supplies_cache_write_tokens(self):
        run = _run(
            {"prompt_tokens": 100, "cache_read_input_tokens": 50, "completion_tokens": 10},
            trace_usage={"cache_write_tokens": 30},
        )
        _, buckets = costs.token_cost(
            run,
            {
                "input": 1,
                "cached_input": 0.1,
                "cache_write": 1.25,
                "output": 6,
                "usage_semantics": "openai_responses",
            },
        )
        self.assertEqual(
            buckets,
            {"uncached_input": 20, "cached_input": 50, "cache_write": 30, "output": 10},
        )

    def test_modal_cost_uses_active_request_seconds_and_gpu_count(self):
        run = _run({}, decision_ms=2000)
        primary, fallback = costs.modal_cost(
            run,
            {"gpu": "b200", "count": 2},
            {"b200": 0.001736},
        )
        self.assertAlmostEqual(primary, 2 * 2 * 0.001736)
        self.assertIsNone(fallback)


if __name__ == "__main__":
    unittest.main()
