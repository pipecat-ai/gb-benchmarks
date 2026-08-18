import importlib.util
import sys
import unittest
from pathlib import Path


PORT_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "render_under_four_reliability", PORT_DIR / "render_under_four_reliability.py"
)
assert SPEC and SPEC.loader
chart = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = chart
SPEC.loader.exec_module(chart)


class UnderFourReliabilityTests(unittest.TestCase):
    def test_current_readme_renders_every_curated_row(self):
        rows = chart.load_rows(chart.DEFAULT_README)
        self.assertEqual(len(rows), 26)
        self.assertEqual(rows[0].label, "grok-4.6 (high)")
        self.assertEqual(rows[-1].label, "nemotron-3-super-120b (tb=512)")

    def test_completion_tails_are_sparse_and_directly_labeled(self):
        svg = chart.render_svg(chart.load_rows(chart.DEFAULT_README))
        self.assertEqual(svg.count('class="tail"'), 5)
        self.assertIn(">96% complete</text>", svg)
        self.assertIn(">84% complete</text>", svg)
        self.assertIn(">92% complete</text>", svg)
        self.assertIn(">68% complete</text>", svg)
        self.assertIn("Muse Glimmer 30B · high, GGUF", svg)
        self.assertIn("Qwen 3.8 27B · low, NVFP4", svg)
        self.assertIn("Gemini 3.7 Flash · high", svg)
        self.assertIn("Gemini 3.5 Flash Lite · high", svg)
        self.assertIn("Grok 4.6 · high", svg)
        self.assertIn("$0.406 / completion · xAI", svg)
        self.assertIn("Port-to-port benchmark: rankings", svg)
        self.assertIn("$0.261 / completion", svg)
        self.assertNotIn(" / turn", svg)
        self.assertIn("no API price · Local RTX 5090", svg)

    def test_score_axis_keeps_the_requested_sixty_to_one_hundred_range(self):
        svg = chart.render_svg(chart.load_rows(chart.DEFAULT_README))
        self.assertIn(">60</text>", svg)
        self.assertIn(">100</text>", svg)
        self.assertIn("Tail length = unfinished share", svg)


if __name__ == "__main__":
    unittest.main()
