import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PORT_TO_PORT_DIR = Path(__file__).resolve().parents[1]
SWEEP_SCRIPT = PORT_TO_PORT_DIR / "run_baseten_sweep.sh"


class BasetenSweepConfigTests(unittest.TestCase):
    def _run_print_configs(self, specs=(), config_filter=None, run_dir=None):
        env = os.environ.copy()
        env["PRINT_CONFIGS"] = "1"
        env["MAX_TOKENS"] = "8192"
        if config_filter is None:
            env.pop("CONFIG_FILTER", None)
        else:
            env["CONFIG_FILTER"] = config_filter
        if run_dir is not None:
            env["RUN_DIR"] = str(run_dir)

        result = subprocess.run(
            ["bash", str(SWEEP_SCRIPT), *specs],
            cwd=PORT_TO_PORT_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return result

    def _print_configs(self, config_filter=None, run_dir=None):
        result = self._run_print_configs(
            config_filter=config_filter,
            run_dir=run_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout.splitlines()

    def test_script_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SWEEP_SCRIPT)],
            cwd=PORT_TO_PORT_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_print_configs_resolves_all_caps_without_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir) / "must-not-be-created"
            lines = self._print_configs(run_dir=run_dir)
            self.assertFalse(run_dir.exists())

        expected = [
            "CONFIG_PLAN slug=glm52-none model=zai-org/GLM-5.2 thinking=none max_tokens=8192",
            "CONFIG_PLAN slug=glm52-high model=zai-org/GLM-5.2 thinking=high max_tokens=8192",
            "CONFIG_PLAN slug=glm52-xhigh model=zai-org/GLM-5.2 thinking=xhigh max_tokens=8192",
            (
                "CONFIG_PLAN slug=nemotron-ultra-none "
                "model=nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B "
                "thinking=none max_tokens=8192"
            ),
            (
                "CONFIG_PLAN slug=nemotron-ultra-high "
                "model=nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B "
                "thinking=high max_tokens=8192"
            ),
            "CONFIG_PLAN slug=inkling-low model=thinkingmachines/inkling thinking=low max_tokens=16384",
            "CONFIG_PLAN slug=inkling-high model=thinkingmachines/inkling thinking=high max_tokens=16384",
            "CONFIG_PLAN slug=inkling-max model=thinkingmachines/inkling thinking=xhigh max_tokens=16384",
        ]
        self.assertEqual(lines, expected)
        self.assertEqual(len(lines), 8)
        self.assertFalse(any("inkling-none" in line for line in lines))

    def test_print_configs_honors_exact_inkling_filter(self):
        lines = self._print_configs("inkling-low,inkling-high,inkling-max")
        self.assertEqual(
            lines,
            [
                "CONFIG_PLAN slug=inkling-low model=thinkingmachines/inkling thinking=low max_tokens=16384",
                "CONFIG_PLAN slug=inkling-high model=thinkingmachines/inkling thinking=high max_tokens=16384",
                "CONFIG_PLAN slug=inkling-max model=thinkingmachines/inkling thinking=xhigh max_tokens=16384",
            ],
        )

    def test_print_configs_parses_positional_specs(self):
        result = self._run_print_configs(["s|m|t", "s|m|t|16384"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "CONFIG_PLAN slug=s model=m thinking=t max_tokens=8192",
                "CONFIG_PLAN slug=s model=m thinking=t max_tokens=16384",
            ],
        )

    def test_print_configs_rejects_malformed_positional_specs(self):
        malformed_specs = [
            "s|m",
            "s||t|16384",
            "s|m|t|16384|",
            "s|m|t|16384||",
            "s|m|t|16384|extra",
        ]
        for spec in malformed_specs:
            with self.subTest(spec=spec):
                result = self._run_print_configs([spec])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("malformed config", result.stderr)

    def test_live_command_uses_resolved_per_config_cap(self):
        source = SWEEP_SCRIPT.read_text()
        self.assertIn('--max-tokens "$mt"', source)
        self.assertNotIn('--max-tokens "$MAX_TOKENS"', source)


if __name__ == "__main__":
    unittest.main()
