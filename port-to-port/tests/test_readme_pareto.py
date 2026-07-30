import importlib.util
import sys
import unittest
from pathlib import Path


PORT_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "render_readme_pareto", PORT_DIR / "render_readme_pareto.py"
)
assert SPEC and SPEC.loader
pareto = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pareto
SPEC.loader.exec_module(pareto)

SCORE_TIME_SPEC = importlib.util.spec_from_file_location(
    "render_readme_score_time", PORT_DIR / "render_readme_score_time.py"
)
score_time = importlib.util.module_from_spec(SCORE_TIME_SPEC)
sys.modules[SCORE_TIME_SPEC.name] = score_time
SCORE_TIME_SPEC.loader.exec_module(score_time)


class ParetoTests(unittest.TestCase):
    def test_frontier_rejects_dominated_and_equal_score_rows(self):
        points = [
            pareto.Point("cheap", 80, 1.0, 0.01),
            pareto.Point("same-score-expensive", 80, 1.0, 0.02),
            pareto.Point("middle", 90, 1.0, 0.03),
            pareto.Point("dominated", 85, 1.0, 0.04),
            pareto.Point("best", 95, 1.0, 0.10),
        ]
        self.assertEqual(
            [point.label for point in pareto.pareto_frontier(points)],
            ["cheap", "middle", "best"],
        )

    def test_current_readme_has_four_row_frontier(self):
        points = pareto.load_points(
            pareto.DEFAULT_README,
            pareto.DEFAULT_COSTS,
        )
        self.assertEqual(
            [point.label for point in pareto.pareto_frontier(points)],
            [
                "poolside/laguna-s-2.1 (none)",
                "gemma-4-31b (thinking)",
                "kimi-2.6 Cerebras (thinking)",
                "glm-5.2 (max)",
            ],
        )

    def test_current_readme_has_two_row_time_frontier(self):
        points = pareto.load_points(
            pareto.DEFAULT_README,
            pareto.DEFAULT_COSTS,
        )
        self.assertEqual(
            [point.label for point in score_time.time_frontier(points)],
            [
                "kimi-2.6 Cerebras (thinking)",
                "gemini-3.6-flash (high)",
            ],
        )

    def test_time_frontier_rejects_slower_equal_score(self):
        points = [
            pareto.Point("fast", 80, 1.0, 0.1, 500),
            pareto.Point("slower-equal", 80, 1.0, 0.1, 700),
            pareto.Point("slow-better", 90, 1.0, 0.1, 900),
        ]
        self.assertEqual(
            [point.label for point in score_time.time_frontier(points)],
            ["fast", "slow-better"],
        )

    def test_cost_chart_labels_prominent_non_frontier_families(self):
        points = pareto.load_points(
            pareto.DEFAULT_README,
            pareto.DEFAULT_COSTS,
        )
        svg = pareto.render_svg(points)
        self.assertIn("Gemini 3.6 Flash · high", svg)
        self.assertIn("Claude Sonnet 5 · xhigh", svg)
        self.assertIn("GPT-5.6 Terra · xhigh", svg)
        time_svg = score_time.render_svg(points)
        self.assertIn("Gemini 3.6 Flash · high", time_svg)
        self.assertIn("Claude Sonnet 5 · xhigh", time_svg)
        self.assertIn("GPT-5.6 Terra · xhigh", time_svg)
        for point in pareto.pareto_frontier(points):
            self.assertIn(score_time._short_label(point.label), time_svg)
        self.assertIn(">1s</text>", time_svg)
        self.assertIn(">$1</text>", svg)
        self.assertNotIn(">$3</text>", svg)


if __name__ == "__main__":
    unittest.main()
