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

    def test_current_readme_has_three_row_frontier(self):
        points = pareto.load_points(
            pareto.DEFAULT_README,
            pareto.DEFAULT_COSTS,
        )
        self.assertEqual(
            [point.label for point in pareto.pareto_frontier(points)],
            [
                "poolside/laguna-s-2.1 (none)",
                "deepseek-v4-flash-0731 (low)",
                "grok-4.6 (high)",
            ],
        )

    def test_current_readme_has_four_row_time_frontier(self):
        points = pareto.load_points(
            pareto.DEFAULT_README,
            pareto.DEFAULT_COSTS,
        )
        self.assertEqual(
            [point.label for point in score_time.time_frontier(points)],
            [
                "inkling (low)",
                "gemini-3.5-flash-lite (high)",
                "deepseek-v4-flash-0731 (low)",
                "grok-4.6 (high)",
            ],
        )

    def test_readme_publishes_both_current_frontier_tables_and_charts(self):
        readme = pareto.DEFAULT_README.read_text(encoding="utf-8")
        cost_section = readme.split("### Score–cost frontier", 1)[1].split(
            "### Score–turn-time frontier", 1
        )[0]
        time_section = readme.split("### Score–turn-time frontier", 1)[1].split(
            "### Score and completion reliability", 1
        )[0]
        points = pareto.load_points(pareto.DEFAULT_README, pareto.DEFAULT_COSTS)

        self.assertIn("score-cost-pareto.svg", cost_section)
        self.assertIn("score-time-frontier.svg", time_section)
        for point in pareto.pareto_frontier(points):
            self.assertIn(f"| {point.label}", cost_section)
        for point in score_time.time_frontier(points):
            self.assertIn(f"| {point.label}", time_section)
        self.assertNotIn("gemini-3.1-flash-lite-preview", cost_section + time_section)

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

    def test_hairline_intersection_detector_includes_crossing_and_touching(self):
        self.assertTrue(
            pareto._segments_intersect(
                pareto.Segment(0, 0, 10, 10),
                pareto.Segment(0, 10, 10, 0),
            )
        )
        self.assertTrue(
            pareto._segments_intersect(
                pareto.Segment(0, 0, 10, 0),
                pareto.Segment(10, 0, 20, 0),
            )
        )
        self.assertFalse(
            pareto._segments_intersect(
                pareto.Segment(0, 0, 10, 0),
                pareto.Segment(0, 2, 10, 2),
            )
        )

    def test_packing_cost_softly_prefers_twelve_pixel_hairlines(self):
        def geometry(length):
            return pareto.LabelGeometry(
                "sample",
                pareto.Rect(0, 0, 1, 1),
                pareto.Segment(0, 0, length, 0),
            )

        preferred = pareto._hairline_packing_cost(geometry(12))
        self.assertLess(preferred, pareto._hairline_packing_cost(geometry(2)))
        self.assertLess(preferred, pareto._hairline_packing_cost(geometry(20)))
        diagonal = pareto.LabelGeometry(
            "sample",
            pareto.Rect(0, 0, 1, 1),
            pareto.Segment(0, 0, 11.31, 4),
        )
        self.assertLess(
            pareto._hairline_packing_cost(diagonal),
            pareto._hairline_packing_cost(geometry(12)),
        )
        self.assertEqual(pareto.MIN_LABEL_PADDING, 10.0)
        self.assertEqual(pareto.MIN_LABEL_DOT_PADDING, 8.0)

    def test_cost_chart_labels_prominent_non_frontier_families(self):
        points = pareto.load_points(
            pareto.DEFAULT_README,
            pareto.DEFAULT_COSTS,
        )
        svg = pareto.render_svg(points)
        self.assertIn("Gemini 3.7 Flash · high", svg)
        self.assertIn("GLM 5.2 · max", svg)
        self.assertIn("97 · $0.174 · 1.19s", svg)
        self.assertEqual(svg.count('class="label-hairline"'), 7)
        self.assertNotIn("Gemini 3.6 Flash · high", svg)
        self.assertIn("Claude Sonnet 5 · xhigh", svg)
        self.assertIn("GPT-5.6 Terra · xhigh", svg)
        time_svg = score_time.render_svg(points)
        self.assertIn("Score versus turn completion time", time_svg)
        self.assertIn("Turn P50: full response or tool call", time_svg)
        self.assertIn("Turn P50 completion time", time_svg)
        self.assertIn("97 · 0.86s · $0.033", time_svg)
        self.assertIn("Gemini 3.7 Flash · high", time_svg)
        self.assertIn("Claude Sonnet 5 · xhigh", time_svg)
        self.assertIn("GPT-5.6 Terra · xhigh", time_svg)
        self.assertEqual(time_svg.count('class="label-hairline"'), 8)
        for point in pareto.pareto_frontier(points):
            self.assertIn(score_time._short_label(point.label), time_svg)
        self.assertIn(">1s</text>", time_svg)
        self.assertIn(">$1</text>", svg)
        self.assertNotIn(">$3</text>", svg)


if __name__ == "__main__":
    unittest.main()
