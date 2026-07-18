from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PORT_TO_PORT_DIR = Path(__file__).resolve().parents[1]
RUNNER = PORT_TO_PORT_DIR / "run_gpt56_sweep.sh"
PYTHON = PORT_TO_PORT_DIR / ".venv" / "bin" / "python"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


evaluate_runs = _load_module("evaluate_runs_gpt56_sweep_test", PORT_TO_PORT_DIR / "evaluate_runs.py")
leaderboard = _load_module(
    "build_primary_leaderboard_gpt56_sweep_test",
    PORT_TO_PORT_DIR / "build_primary_leaderboard.py",
)


def _runner(*, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        [str(RUNNER)],
        cwd=PORT_TO_PORT_DIR,
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    )


def _approval_hashes(phase: str = "full") -> dict[str, str]:
    result = _runner(env={"PRINT_APPROVAL_HASHES": "1", "GPT56_PHASE": phase})
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return dict(line.split("=", 1) for line in result.stdout.splitlines())


def _fixture_payload(terminal_reason: str, *, response_status: str = "failed", code: str = "fixture") -> dict:
    return {
        "schema_version": "mini_rl_run.v3",
        "metadata": {"run_id": "fixture", "round_id": "r01"},
        "config": {
            "provider": "openai",
            "model": "gpt-5.6-luna",
            "thinking": "xhigh",
            "effective_effort": "xhigh",
            "round_id": "r01",
            "max_turns": 50,
        },
        "termination": {"reason": terminal_reason},
        "summary": {"terminal_reason": terminal_reason},
        "turns": [{}],
        "responses_traces": [
            {
                "api_surface": "responses",
                "response_status": response_status,
                "sdk_max_retries": 0,
                "openai_sdk_version": "2.21.0",
                "error": {"code": code, "type": code},
                "usage": {
                    "input_tokens": 100,
                    "cached_tokens": 10,
                    "output_tokens": 20,
                    "reasoning_tokens": 5,
                    "total_tokens": 120,
                },
            }
        ],
    }


class RunnerMatrixTests(unittest.TestCase):
    def test_print_configs_is_exact_round_robin_matrix(self):
        result = _runner(env={"PRINT_CONFIGS": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 226)
        header = lines[0].split("\t")
        rows = [dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]]

        self.assertEqual({row["round_id"] for row in rows}, {f"r{i:02d}" for i in range(1, 26)})
        self.assertEqual(len({row["config_slug"] for row in rows}), 9)
        for round_id in (f"r{i:02d}" for i in range(1, 26)):
            round_rows = [row for row in rows if row["round_id"] == round_id]
            self.assertEqual(len(round_rows), 9)
            self.assertEqual(
                [row["config_slug"] for row in round_rows],
                [row["config_slug"] for row in rows[:9]],
            )

        wire_identities = {(row["model"], row["effective_effort"]) for row in rows}
        self.assertEqual(len(wire_identities), 9)
        max_rows = [row for row in rows if row["effective_effort"] == "max"]
        self.assertEqual(len(max_rows), 75)
        self.assertTrue(all(row["thinking"] == "xhigh" and row["override"] == "max" for row in max_rows))
        self.assertTrue(all(row["max_tokens"] == "50000" for row in rows))
        self.assertTrue(all(row["token_reservation"] == "55000000" for row in rows))
        self.assertEqual({row["usd_reservation"] for row in rows}, {"153.75", "384.375", "768.75"})

    def test_dry_run_has_required_flags_and_no_key_or_writes(self):
        result = _runner(env={"DRY_RUN": "1", "OPENAI_API_KEY": "must-not-be-needed"})
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 225)
        for line in lines:
            self.assertIn("--task-variant natural", line)
            self.assertIn("--max-turns 50", line)
            self.assertIn("--function-call-timeout-secs 20", line)
            self.assertIn("--max-tokens 50000", line)
            self.assertIn("--log-json runs/", line)
            self.assertNotIn("service-tier", line)
            self.assertNotIn("OPENAI_API_KEY", line)

    def test_production_core_phases_are_exact_six_config_round_robin_without_sol(self):
        expected_slugs = [
            "gpt56-luna-low",
            "gpt56-luna-xhigh",
            "gpt56-luna-max",
            "gpt56-terra-low",
            "gpt56-terra-xhigh",
            "gpt56-terra-max",
        ]
        for phase in ("production-core-v1", "production-core-v2", "production-core-v3"):
            with self.subTest(phase=phase):
                result = _runner(env={"PRINT_CONFIGS": "1", "GPT56_PHASE": phase})
                self.assertEqual(result.returncode, 0, result.stderr)
                lines = result.stdout.splitlines()
                self.assertEqual(len(lines), 151)
                header = lines[0].split("\t")
                rows = [dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]]

                self.assertEqual(
                    {row["round_id"] for row in rows},
                    {f"r{i:02d}" for i in range(1, 26)},
                )
                self.assertTrue(all(row["model"] != "gpt-5.6-sol" for row in rows))
                for round_id in (f"r{i:02d}" for i in range(1, 26)):
                    self.assertEqual(
                        [row["config_slug"] for row in rows if row["round_id"] == round_id],
                        expected_slugs,
                    )
                self.assertNotEqual(
                    _approval_hashes(phase)["config_sha256"],
                    _approval_hashes("full")["config_sha256"],
                )
                dry_run = _runner(env={"DRY_RUN": "1", "GPT56_PHASE": phase})
                self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
                self.assertEqual(len(dry_run.stdout.splitlines()), 150)
                self.assertNotIn("gpt-5.6-sol", dry_run.stdout)
                self.assertEqual(dry_run.stdout.count("--log-json runs/"), 150)
                if phase == "production-core-v1":
                    self.assertNotIn("-production-core-v1-", dry_run.stdout)
                else:
                    self.assertEqual(dry_run.stdout.count(f"-{phase}-"), 150)
                    self.assertNotIn("--log-json runs/gpt56-luna-low-r01-aNNN.json", dry_run.stdout)

    def test_parallel_replay_v6_is_one_luna_low_attempt_and_hash_binds_preflight(self):
        phase = "smoke-parallel-replay-v6"
        printed = _runner(env={"PRINT_CONFIGS": "1", "GPT56_PHASE": phase})
        self.assertEqual(printed.returncode, 0, printed.stderr)
        lines = printed.stdout.splitlines()
        self.assertEqual(len(lines), 2)
        header = lines[0].split("\t")
        row = dict(zip(header, lines[1].split("\t"), strict=True))
        self.assertEqual(row["config_slug"], "gpt56-luna-low")
        self.assertEqual(row["model"], "gpt-5.6-luna")
        self.assertEqual(row["effective_effort"], "low")
        self.assertEqual(row["round_id"], phase)
        self.assertNotIn("gpt-5.6-terra", printed.stdout)
        self.assertNotIn("gpt-5.6-sol", printed.stdout)
        dry_run = _runner(env={"DRY_RUN": "1", "GPT56_PHASE": phase})
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertEqual(len(dry_run.stdout.splitlines()), 1)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hashes = _approval_hashes(phase)
            ledger = (
                PORT_TO_PORT_DIR
                / "proj-2026-07-16-1632"
                / "step4-authorization-ledger-parallel-replay-v6.json"
            )
            common = {
                "GPT56_PHASE": phase,
                "GPT56_APPROVAL_ID": "parallel-replay-preflight-gate-test",
                "GPT56_TOKEN_CEILING": "230000000",
                "GPT56_USD_CEILING": "650",
                "GPT56_WALL_SECS_CEILING": "16000",
                "GPT56_MAX_ATTEMPTS": "1",
                "GPT56_EXPECTED_CONFIG_SHA256": hashes["config_sha256"],
                "GPT56_EXPECTED_RUNNER_SHA256": hashes["runner_sha256"],
                "GPT56_EXPECTED_IMPLEMENTATION_SHA256": hashes[
                    "implementation_sha256"
                ],
                "GPT56_BASELINE_LEDGER_PATH": str(
                    ledger.relative_to(PORT_TO_PORT_DIR)
                ),
                "GPT56_EXPECTED_BASELINE_LEDGER_SHA256": hashlib.sha256(
                    ledger.read_bytes()
                ).hexdigest(),
                "GPT56_STATE_PATH": str(root / "state.json"),
                "GPT56_MANIFEST_PATH": str(root / "manifest.json"),
                "GPT56_OFFLINE_TEST": "1",
                "GPT56_OFFLINE_LOCK_PATH": str(root / "runner.lock"),
                "OPENAI_API_KEY": "must-not-be-read",
            }
            missing = _runner(env=common)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("GPT56_PREFLIGHT_PATH", missing.stderr)
            self.assertFalse((root / "state.json").exists())

            preflight = root / "preflight.md"
            preflight.write_text("reviewed content\n", encoding="utf-8")
            mismatch = _runner(
                env={
                    **common,
                    "GPT56_PREFLIGHT_PATH": str(preflight),
                    "GPT56_EXPECTED_PREFLIGHT_SHA256": "0" * 64,
                }
            )
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn("preflight document hash mismatch", mismatch.stderr)
            self.assertFalse((root / "state.json").exists())

            state = root / "state.json"
            state.write_text('{"existing":true}\n', encoding="utf-8")
            no_resume = _runner(
                env={
                    **common,
                    "GPT56_PREFLIGHT_PATH": str(preflight),
                    "GPT56_EXPECTED_PREFLIGHT_SHA256": hashlib.sha256(
                        preflight.read_bytes()
                    ).hexdigest(),
                }
            )
            self.assertEqual(no_resume.returncode, 11, no_resume.stderr)
            self.assertIn("PHASE_RESUME_FORBIDDEN", no_resume.stderr)
            self.assertEqual(state.read_text(encoding="utf-8"), '{"existing":true}\n')

    def test_production_core_v1_requires_baseline_ledger_before_key_or_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hashes = _approval_hashes("production-core-v1")
            result = _runner(env={
                "GPT56_PHASE": "production-core-v1",
                "GPT56_APPROVAL_ID": "production-ledger-gate-test",
                "GPT56_TOKEN_CEILING": "190000000",
                "GPT56_USD_CEILING": "600",
                "GPT56_WALL_SECS_CEILING": "35000",
                "GPT56_MAX_ATTEMPTS": "160",
                "GPT56_EXPECTED_CONFIG_SHA256": hashes["config_sha256"],
                "GPT56_EXPECTED_RUNNER_SHA256": hashes["runner_sha256"],
                "GPT56_EXPECTED_IMPLEMENTATION_SHA256": hashes["implementation_sha256"],
                "GPT56_STATE_PATH": str(root / "state.json"),
                "GPT56_MANIFEST_PATH": str(root / "manifest.json"),
                "OPENAI_API_KEY": "must-not-be-read",
            })
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("GPT56_BASELINE_LEDGER_PATH", result.stderr)
            self.assertFalse((root / "state.json").exists())

    def test_production_core_v1_refuses_resume_before_key_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state.json"
            manifest = root / "manifest.json"
            state.write_text('{"existing": true}\n', encoding="utf-8")
            ledger = (
                PORT_TO_PORT_DIR
                / "proj-2026-07-16-1632"
                / "step4-authorization-ledger-production-core-v1.json"
            )
            hashes = _approval_hashes("production-core-v1")
            result = _runner(env={
                "GPT56_PHASE": "production-core-v1",
                "GPT56_APPROVAL_ID": "production-no-resume-test",
                "GPT56_TOKEN_CEILING": "200000000",
                "GPT56_USD_CEILING": "650",
                "GPT56_WALL_SECS_CEILING": "38000",
                "GPT56_MAX_ATTEMPTS": "160",
                "GPT56_EXPECTED_CONFIG_SHA256": hashes["config_sha256"],
                "GPT56_EXPECTED_RUNNER_SHA256": hashes["runner_sha256"],
                "GPT56_EXPECTED_IMPLEMENTATION_SHA256": hashes["implementation_sha256"],
                "GPT56_BASELINE_LEDGER_PATH": str(ledger.relative_to(PORT_TO_PORT_DIR)),
                "GPT56_EXPECTED_BASELINE_LEDGER_SHA256": hashlib.sha256(
                    ledger.read_bytes()
                ).hexdigest(),
                "GPT56_STATE_PATH": str(state),
                "GPT56_MANIFEST_PATH": str(manifest),
                "OPENAI_API_KEY": "must-not-be-read",
            })
            self.assertEqual(result.returncode, 11, result.stderr)
            self.assertIn("PRODUCTION_RESUME_FORBIDDEN", result.stderr)
            self.assertEqual(state.read_text(encoding="utf-8"), '{"existing": true}\n')
            self.assertFalse(manifest.exists())

    def test_production_core_v2_accepts_rebased_ledger_and_refuses_resume_before_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state.json"
            manifest = root / "manifest.json"
            state.write_text('{"existing": true}\n', encoding="utf-8")
            ledger = (
                PORT_TO_PORT_DIR
                / "proj-2026-07-16-1632"
                / "step4-authorization-ledger-production-core-v2.json"
            )
            hashes = _approval_hashes("production-core-v2")
            result = _runner(env={
                "GPT56_PHASE": "production-core-v2",
                "GPT56_APPROVAL_ID": "standing-production-core-scope",
                "GPT56_TOKEN_CEILING": "200000000",
                "GPT56_USD_CEILING": "650",
                "GPT56_WALL_SECS_CEILING": "38000",
                "GPT56_MAX_ATTEMPTS": "160",
                "GPT56_EXPECTED_CONFIG_SHA256": hashes["config_sha256"],
                "GPT56_EXPECTED_RUNNER_SHA256": hashes["runner_sha256"],
                "GPT56_EXPECTED_IMPLEMENTATION_SHA256": hashes["implementation_sha256"],
                "GPT56_BASELINE_LEDGER_PATH": str(ledger.relative_to(PORT_TO_PORT_DIR)),
                "GPT56_EXPECTED_BASELINE_LEDGER_SHA256": hashlib.sha256(
                    ledger.read_bytes()
                ).hexdigest(),
                "GPT56_STATE_PATH": str(state),
                "GPT56_MANIFEST_PATH": str(manifest),
                "OPENAI_API_KEY": "must-not-be-read",
            })
            self.assertEqual(result.returncode, 11, result.stderr)
            self.assertIn("PRODUCTION_RESUME_FORBIDDEN", result.stderr)
            self.assertEqual(state.read_text(encoding="utf-8"), '{"existing": true}\n')
            self.assertFalse(manifest.exists())

    def test_staged_smoke_phases_are_disjoint_and_sol_is_last(self):
        staged: dict[str, list[dict[str, str]]] = {}
        for phase, expected_count in (
            ("smoke-core", 6),
            ("smoke-sol", 3),
            ("smoke-luna-xhigh-v4", 1),
            ("smoke-core-remainder-v5", 4),
        ):
            result = _runner(env={"PRINT_CONFIGS": "1", "GPT56_PHASE": phase})
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.splitlines()
            self.assertEqual(len(lines), expected_count + 1)
            header = lines[0].split("\t")
            rows = [
                dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]
            ]
            self.assertEqual({row["round_id"] for row in rows}, {phase})
            self.assertEqual(
                len({(row["model"], row["effective_effort"]) for row in rows}),
                expected_count,
            )
            staged[phase] = rows

        self.assertTrue(
            all(row["model"] != "gpt-5.6-sol" for row in staged["smoke-core"])
        )
        self.assertTrue(
            all(row["model"] == "gpt-5.6-sol" for row in staged["smoke-sol"])
        )
        self.assertEqual(
            [row["config_slug"] for row in staged["smoke-luna-xhigh-v4"]],
            ["gpt56-luna-xhigh"],
        )
        self.assertEqual(
            staged["smoke-luna-xhigh-v4"][0]["round_id"],
            "smoke-luna-xhigh-v4",
        )
        self.assertEqual(
            [row["config_slug"] for row in staged["smoke-core-remainder-v5"]],
            [
                "gpt56-luna-max",
                "gpt56-terra-low",
                "gpt56-terra-xhigh",
                "gpt56-terra-max",
            ],
        )
        core_slugs = {row["config_slug"] for row in staged["smoke-core"]}
        sol_slugs = {row["config_slug"] for row in staged["smoke-sol"]}
        self.assertTrue(core_slugs.isdisjoint(sol_slugs))
        self.assertEqual(len(core_slugs | sol_slugs), 9)
        self.assertNotEqual(
            _approval_hashes("smoke-core")["config_sha256"],
            _approval_hashes("smoke-sol")["config_sha256"],
        )
        self.assertNotEqual(
            _approval_hashes("smoke-core")["config_sha256"],
            _approval_hashes("smoke-luna-xhigh-v4")["config_sha256"],
        )
        self.assertNotEqual(
            _approval_hashes("smoke-core")["config_sha256"],
            _approval_hashes("smoke-core-remainder-v5")["config_sha256"],
        )

    def test_execution_is_structurally_sequential(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn(
            'timeout "$episode_timeout" "${cmd[@]}" < /dev/null 2>&1 | tee -a "$raw_log"',
            source,
        )
        self.assertIn("done < <(print_configs)", source)
        self.assertNotIn("xargs -P", source)
        self.assertNotIn("parallel ", source)
        self.assertNotIn("wait -n", source)
        self.assertIn("flock -n 9", source)
        self.assertNotIn("set -e", "\n".join(line for line in source.splitlines() if not line.startswith("#")))

    def test_live_mode_requires_explicit_approval_before_key_access(self):
        result = _runner(env={})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GPT56_APPROVAL_ID", result.stderr)

    def test_live_mode_rejects_unreviewed_hashes_before_key_or_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = _runner(env={
                "GPT56_APPROVAL_ID": "hash-test",
                "GPT56_TOKEN_CEILING": "200000000",
                "GPT56_USD_CEILING": "3000",
                "GPT56_WALL_SECS_CEILING": "40000",
                "GPT56_MAX_ATTEMPTS": "9",
                "GPT56_EXPECTED_CONFIG_SHA256": "0" * 64,
                "GPT56_EXPECTED_RUNNER_SHA256": "0" * 64,
                "GPT56_EXPECTED_IMPLEMENTATION_SHA256": "0" * 64,
                "GPT56_STATE_PATH": str(root / "state.json"),
                "GPT56_MANIFEST_PATH": str(root / "manifest.json"),
                "OPENAI_API_KEY": "must-not-be-read",
            })
            self.assertEqual(result.returncode, 8)
            self.assertIn("APPROVAL_HASH_MISMATCH", result.stderr)
            self.assertFalse((root / "state.json").exists())

    def test_v5_requires_hash_bound_baseline_ledger_before_key_or_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hashes = _approval_hashes("smoke-core-remainder-v5")
            base_env = {
                "GPT56_PHASE": "smoke-core-remainder-v5",
                "GPT56_APPROVAL_ID": "v5-ledger-gate-test",
                "GPT56_TOKEN_CEILING": "282000000",
                "GPT56_USD_CEILING": "1500",
                "GPT56_WALL_SECS_CEILING": "38000",
                "GPT56_MAX_ATTEMPTS": "4",
                "GPT56_EXPECTED_CONFIG_SHA256": hashes["config_sha256"],
                "GPT56_EXPECTED_RUNNER_SHA256": hashes["runner_sha256"],
                "GPT56_EXPECTED_IMPLEMENTATION_SHA256": hashes["implementation_sha256"],
                "GPT56_STATE_PATH": str(root / "state.json"),
                "GPT56_MANIFEST_PATH": str(root / "manifest.json"),
                "OPENAI_API_KEY": "must-not-be-read",
            }
            missing = _runner(env=base_env)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("GPT56_BASELINE_LEDGER_PATH", missing.stderr)
            self.assertFalse((root / "state.json").exists())

            mismatch = _runner(env={
                **base_env,
                "GPT56_BASELINE_LEDGER_PATH": str(root / "missing-ledger.json"),
                "GPT56_EXPECTED_BASELINE_LEDGER_SHA256": "0" * 64,
            })
            self.assertEqual(mismatch.returncode, 10)
            self.assertIn("BASELINE_LEDGER_HASH_MISMATCH", mismatch.stderr)
            self.assertFalse((root / "state.json").exists())

    def test_offline_stub_executes_smoke_reserve_run_record_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stub = root / "stub_benchmark.py"
            stub.write_text(
                """from __future__ import annotations
import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--model', required=True)
p.add_argument('--thinking', required=True)
p.add_argument('--reasoning-effort')
p.add_argument('--round-id', required=True)
p.add_argument('--max-turns', type=int, required=True)
p.add_argument('--log-json', required=True)
args, _ = p.parse_known_args()
effort = args.reasoning_effort or args.thinking
payload = {
    'schema_version': 'mini_rl_run.v3',
    'metadata': {'run_id': f'{args.model}-{effort}-{args.round_id}', 'round_id': args.round_id},
    'config': {
        'provider': 'openai', 'model': args.model, 'thinking': args.thinking,
        'effective_effort': effort, 'round_id': args.round_id, 'max_turns': args.max_turns,
    },
    'termination': {'reason': 'finished_tool'},
    'summary': {'model': args.model, 'terminal_reason': 'finished_tool'},
    'turns': [{}],
    'responses_traces': [{
        'api_surface': 'responses', 'response_status': 'completed', 'sdk_max_retries': 0,
        'openai_sdk_version': '2.21.0',
        'usage': {'input_tokens': 100, 'cached_tokens': 0, 'output_tokens': 20, 'reasoning_tokens': 5, 'total_tokens': 120},
    }],
}
Path(args.log_json).write_text(json.dumps(payload), encoding='utf-8')
print(f'HARNESS_CONFIG model={args.model} effective_effort={effort} round_id={args.round_id}')
print(f'WROTE {args.log_json}')
print('SUCCESS=True')
print('TERMINAL_REASON=finished_tool')
""",
                encoding="utf-8",
            )
            runs = root / "runs"
            state = root / "state.json"
            manifest = root / "manifest.json"
            hashes = _approval_hashes("smoke-core")
            result = _runner(env={
                "GPT56_OFFLINE_TEST": "1",
                "GPT56_OFFLINE_EXECUTOR": str(stub),
                "GPT56_OFFLINE_LOCK_PATH": str(root / "runner.lock"),
                "GPT56_PHASE": "smoke-core",
                "GPT56_RUNS_DIR": str(runs),
                "GPT56_STATE_PATH": str(state),
                "GPT56_MANIFEST_PATH": str(manifest),
                "GPT56_APPROVAL_ID": "offline-loop-test",
                "GPT56_TOKEN_CEILING": "200000000",
                "GPT56_USD_CEILING": "3000",
                "GPT56_WALL_SECS_CEILING": "40000",
                "GPT56_MAX_ATTEMPTS": "6",
                "GPT56_EXPECTED_CONFIG_SHA256": hashes["config_sha256"],
                "GPT56_EXPECTED_RUNNER_SHA256": hashes["runner_sha256"],
                "GPT56_EXPECTED_IMPLEMENTATION_SHA256": hashes["implementation_sha256"],
            })
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(len(data["attempts"]), 6)
            self.assertEqual(len(data["canonical"]), 6)
            self.assertEqual([item["attempt_number"] for item in data["attempts"]], list(range(1, 7)))
            self.assertTrue(all(item["selected"] for item in data["attempts"]))
            self.assertEqual(result.stdout.count("RUN_START"), 6)
            self.assertEqual(result.stdout.count("RUN_EXIT"), 6)
            self.assertEqual(result.stdout.count("APPROVAL_HASH_OK"), 1)
            for item in data["attempts"]:
                log = Path(item["raw_log"]).read_text(encoding="utf-8")
                self.assertIn("RUN_START", log)
                self.assertIn("RUN_EXIT", log)


class ClassifierAndBudgetTests(unittest.TestCase):
    def _classify(self, payload: dict | None, rc: int, log_text: str = "") -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path = root / "attempt.json"
            log_path = root / "attempt.log"
            if payload is not None:
                json_path.write_text(json.dumps(payload), encoding="utf-8")
            log_path.write_text(log_text, encoding="utf-8")
            result = _runner(
                env={
                    "CLASSIFY_ATTEMPT": "1",
                    "CLASSIFY_JSON_PATH": str(json_path),
                    "CLASSIFY_LOG_PATH": str(log_path),
                    "CLASSIFY_EXIT_CODE": str(rc),
                }
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_exact_classifier_fixtures(self):
        cases = [
            ("429", _fixture_payload("rate_limit_exhausted", code="rate_limit"), 1, False, "rate_limit_exhausted"),
            ("retryable 5xx", _fixture_payload("inference_error", code="server_error"), 1, False, "inference_error"),
            ("request timeout", _fixture_payload("inference_error", code="request_timeout"), 1, False, "inference_error"),
            ("stream idle timeout", _fixture_payload("inference_error", code="stream_idle_timeout"), 1, False, "inference_error"),
            ("response.failed", _fixture_payload("inference_error", code="response_failed"), 1, False, "inference_error"),
            ("response.incomplete", _fixture_payload("response_incomplete", response_status="incomplete"), 1, True, "eligible_model_result"),
            ("completed model failure", _fixture_payload("max_turns_exhausted", response_status="completed"), 1, True, "eligible_model_result"),
        ]
        for label, payload, rc, eligible, classification in cases:
            with self.subTest(label=label):
                result = self._classify(payload, rc)
                self.assertEqual(result["eligible"], eligible)
                self.assertEqual(result["classification"], classification)

        self.assertEqual(self._classify(None, 124)["classification"], "exit_124_no_json")
        self.assertEqual(self._classify(None, 1)["classification"], "no_json")

        replay_error = _fixture_payload("inference_error", response_status="completed")
        replay_error["turns"].append({})
        replay_error["responses_traces"].append(
            {
                "api_surface": "responses",
                "response_status": "replay_error",
                "sdk_max_retries": 0,
                "openai_sdk_version": "2.21.0",
                "error": {
                    "type": "ResponsesReplayError",
                    "message": "request not sent",
                },
                "usage": None,
            }
        )
        replay_result = self._classify(replay_error, 1)
        self.assertEqual(replay_result["classification"], "local_replay_error")
        self.assertFalse(replay_result["eligible"])
        self.assertFalse(replay_result["usage_known"])
        self.assertTrue(replay_result["halt_immediately"])
        replay_error["termination"]["reason"] = "unknown"
        replay_error["summary"]["terminal_reason"] = "unknown"
        self.assertEqual(
            self._classify(replay_error, 1)["classification"],
            "local_replay_error",
        )

    def test_missing_or_malformed_json_is_ineligible(self):
        payload = _fixture_payload("finished_tool", response_status="completed")
        payload.pop("responses_traces")
        result = self._classify(payload, 0)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["classification"], "missing_responses_trace")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path = root / "attempt.json"
            log_path = root / "attempt.log"
            json_path.write_text("{broken", encoding="utf-8")
            log_path.write_text("", encoding="utf-8")
            run = _runner(env={
                "CLASSIFY_ATTEMPT": "1",
                "CLASSIFY_JSON_PATH": str(json_path),
                "CLASSIFY_LOG_PATH": str(log_path),
                "CLASSIFY_EXIT_CODE": "1",
            })
            self.assertEqual(json.loads(run.stdout)["classification"], "malformed_json")

    def test_unknown_terminal_reason_is_ineligible(self):
        payload = _fixture_payload("unknown", response_status="completed")
        result = self._classify(payload, 0)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["classification"], "missing_terminal_reason")

        count_mismatch = _fixture_payload("finished_tool", response_status="completed")
        count_mismatch["turns"] = []
        result = self._classify(count_mismatch, 0)
        self.assertEqual(result["classification"], "inference_count_mismatch")

        retry_mismatch = _fixture_payload("finished_tool", response_status="completed")
        retry_mismatch["responses_traces"][0]["sdk_max_retries"] = 2
        result = self._classify(retry_mismatch, 0)
        self.assertEqual(result["classification"], "retry_policy_mismatch")

        sdk_mismatch = _fixture_payload("finished_tool", response_status="completed")
        sdk_mismatch["responses_traces"][0]["openai_sdk_version"] = "changed"
        result = self._classify(sdk_mismatch, 0)
        self.assertEqual(result["classification"], "sdk_version_mismatch")

    def test_partial_checkpoint_is_ineligible_and_cannot_release_reservation(self):
        payload = _fixture_payload("max_turns_exhausted", response_status="completed")
        payload["checkpoint"] = {
            "partial": True,
            "reason": "turn_complete",
            "written_at_utc": "2026-07-17T00:00:00+00:00",
        }
        result = self._classify(payload, 124)
        self.assertFalse(result["eligible"])
        self.assertFalse(result["usage_known"])
        self.assertEqual(result["classification"], "partial_checkpoint")

        empty_usage = _fixture_payload("finished_tool", response_status="completed")
        empty_usage["responses_traces"][0]["usage"] = {}
        result = self._classify(empty_usage, 0)
        self.assertTrue(result["eligible"])
        self.assertFalse(result["usage_known"])

    def test_budget_reservation_requires_strict_headroom_and_stops_each_overage(self):
        base = {
            "BUDGET_FIXTURE": "1",
            "FIXTURE_ACCOUNTED_TOKENS": "100",
            "FIXTURE_ESTIMATED_USD": "2",
            "FIXTURE_WALL_SECS": "3",
            "FIXTURE_TOKEN_CEILING": "151",
            "FIXTURE_USD_CEILING": "7.01",
            "FIXTURE_WALL_CEILING": "9.01",
            "FIXTURE_RESERVE_TOKENS": "50",
            "FIXTURE_RESERVE_USD": "5",
            "FIXTURE_RESERVE_WALL": "6",
        }
        allowed = _runner(env=base)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertTrue(json.loads(allowed.stdout)["allowed"])
        for key, value in (
            ("FIXTURE_TOKEN_CEILING", "150"),
            ("FIXTURE_USD_CEILING", "7"),
            ("FIXTURE_WALL_CEILING", "9"),
        ):
            with self.subTest(key=key):
                denied = _runner(env={**base, key: value})
                self.assertEqual(denied.returncode, 3)
                self.assertFalse(json.loads(denied.stdout)["allowed"])


class AtomicStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = RUNNER.read_text(encoding="utf-8")
        cls.state_source = source.split("<<'PY'\n", 1)[1].split("\nPY\n}", 1)[0]

    def _tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(PYTHON), "-", *args],
            input=self.state_source,
            text=True,
            capture_output=True,
            check=False,
            cwd=PORT_TO_PORT_DIR,
        )

    def test_first_eligible_is_canonical_and_identical_infra_halts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, manifest, runs = root / "state.json", root / "manifest.json", root / "runs"
            runs.mkdir()
            init = self._tool("init", str(state), str(manifest), "full", "approval", "50000000", "500", "100000", "20", "config-hash", "runner-hash", "implementation-hash", "cfg")
            self.assertEqual(init.returncode, 0, init.stderr)

            def reserve(round_id: str) -> tuple[Path, Path]:
                result = self._tool("reserve", str(state), str(manifest), "cfg", "gpt-5.6-luna", "xhigh", round_id, str(runs), "5500000", "18", "7200")
                self.assertEqual(result.returncode, 0, result.stderr)
                _, raw_json, raw_log = result.stdout.strip().split("\t")
                return Path(raw_json), Path(raw_log)

            first_json, first_log = reserve("r01")
            first_json.write_text(json.dumps(_fixture_payload("response_incomplete", response_status="incomplete")), encoding="utf-8")
            first_log.write_text("first", encoding="utf-8")
            recorded = self._tool("record", str(state), str(manifest), "1", "10")
            self.assertTrue(json.loads(recorded.stdout)["selected"])

            second_json, second_log = reserve("r01")
            second_json.write_text(json.dumps(_fixture_payload("finished_tool", response_status="completed")), encoding="utf-8")
            second_log.write_text("second", encoding="utf-8")
            recorded = self._tool("record", str(state), str(manifest), "0", "10")
            self.assertFalse(json.loads(recorded.stdout)["selected"])
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(saved["canonical"]["cfg|r01"], 1)

            for round_id in ("r02", "r03"):
                raw_json, raw_log = reserve(round_id)
                raw_json.write_text(json.dumps(_fixture_payload("inference_error", code="server_error")), encoding="utf-8")
                raw_log.write_text("same server error 500", encoding="utf-8")
                recorded = self._tool("record", str(state), str(manifest), "1", "5")
            self.assertTrue(json.loads(recorded.stdout)["halted"])
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertTrue(saved["config_state"]["cfg"]["halted"])
            self.assertEqual(len(saved["attempts"]), 4)
            self.assertTrue(manifest.is_file())

    def test_local_replay_error_halts_after_first_attempt_and_charges_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state.json"
            manifest = root / "manifest.json"
            runs = root / "runs"
            runs.mkdir()
            init = self._tool(
                "init",
                str(state),
                str(manifest),
                "full",
                "approval",
                "20000000",
                "500",
                "100000",
                "20",
                "config-hash",
                "runner-hash",
                "implementation-hash",
                "cfg",
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            reserved = self._tool(
                "reserve",
                str(state),
                str(manifest),
                "cfg",
                "gpt-5.6-luna",
                "xhigh",
                "r01",
                str(runs),
                "5500000",
                "18",
                "7200",
            )
            self.assertEqual(reserved.returncode, 0, reserved.stderr)
            _, raw_json, raw_log = reserved.stdout.strip().split("\t")
            payload = _fixture_payload("inference_error", response_status="completed")
            payload["responses_traces"].append(
                {
                    "api_surface": "responses",
                    "response_status": "replay_error",
                    "sdk_max_retries": 0,
                    "openai_sdk_version": "2.21.0",
                    "error": {
                        "type": "ResponsesReplayError",
                        "message": "request not sent",
                    },
                    "usage": None,
                }
            )
            payload["turns"].append({})
            Path(raw_json).write_text(json.dumps(payload), encoding="utf-8")
            Path(raw_log).write_text("request not sent", encoding="utf-8")

            recorded = self._tool("record", str(state), str(manifest), "1", "5")
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            output = json.loads(recorded.stdout)
            self.assertTrue(output["halted"])
            self.assertEqual(output["classification"], "local_replay_error")
            saved = json.loads(state.read_text(encoding="utf-8"))
            attempt = saved["attempts"][0]
            self.assertEqual(attempt["accounted_tokens"], 5_500_000)
            self.assertEqual(attempt["estimated_usd"], 18)
            self.assertEqual(
                attempt["accounting_basis"],
                "full_reservation_incomplete_trace_usage",
            )
            self.assertEqual(saved["config_state"]["cfg"]["infra_replacements"], 0)

    def test_baseline_ledger_is_hash_and_evidence_bound_and_enforces_aggregate_budget(self):
        with tempfile.TemporaryDirectory(dir=PORT_TO_PORT_DIR) as tmp:
            root = Path(tmp)
            state, manifest, runs = root / "state.json", root / "manifest.json", root / "runs"
            runs.mkdir()
            evidence = root / "prior.json"
            evidence.write_text('{"prior": true}\n', encoding="utf-8")
            evidence_sha = hashlib.sha256(evidence.read_bytes()).hexdigest()
            ledger = root / "ledger.json"
            ledger_payload = {
                "schema_version": "gpt56_authorization_ledger.v1",
                "entries": [{
                    "entry_id": "prior",
                    "accounted_tokens": 100,
                    "estimated_usd": 2.0,
                    "wall_secs": 3.0,
                    "physical_requests": 4,
                    "known_returned_tokens": 5,
                    "evidence": [{
                        "path": str(evidence.relative_to(PORT_TO_PORT_DIR)),
                        "sha256": evidence_sha,
                    }],
                }],
                "cumulative": {
                    "accounted_tokens": 100,
                    "estimated_usd": 2.0,
                    "wall_secs": 3.0,
                    "physical_requests": 4,
                    "known_returned_tokens": 5,
                },
            }
            ledger.write_text(json.dumps(ledger_payload), encoding="utf-8")
            ledger_sha = hashlib.sha256(ledger.read_bytes()).hexdigest()
            init = self._tool(
                "init", str(state), str(manifest), "smoke-core-remainder-v5",
                "approval", "250", "10", "100", "1", "config-hash",
                "runner-hash", "implementation-hash", "cfg", str(ledger), ledger_sha,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(saved["baseline_cumulative"]["accounted_tokens"], 100)
            self.assertEqual(saved["baseline_ledger"]["physical_requests"], 4)

            rejected = self._tool(
                "reserve", str(state), str(manifest), "cfg", "gpt-5.6-luna",
                "xhigh", "smoke-core-remainder-v5", str(runs), "150", "1", "1",
            )
            self.assertEqual(rejected.returncode, 3)
            self.assertIn("token reservation", rejected.stderr)
            reserved = self._tool(
                "reserve", str(state), str(manifest), "cfg", "gpt-5.6-luna",
                "xhigh", "smoke-core-remainder-v5", str(runs), "100", "1", "1",
            )
            self.assertEqual(reserved.returncode, 0, reserved.stderr)
            _, raw_json, raw_log = reserved.stdout.strip().split("\t")
            payload = _fixture_payload("finished_tool", response_status="completed")
            payload["config"]["round_id"] = "smoke-core-remainder-v5"
            payload["metadata"]["round_id"] = "smoke-core-remainder-v5"
            Path(raw_json).write_text(json.dumps(payload), encoding="utf-8")
            Path(raw_log).write_text("complete", encoding="utf-8")
            recorded = self._tool("record", str(state), str(manifest), "0", "1")
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            record_output = json.loads(recorded.stdout)
            self.assertEqual(record_output["aggregate_cumulative"]["accounted_tokens"], 220)
            self.assertEqual(record_output["aggregate_cumulative"]["wall_secs"], 4.0)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["aggregate_cumulative"]["accounted_tokens"], 220)

            bad_state = root / "bad-state.json"
            bad_manifest = root / "bad-manifest.json"
            evidence.write_text('{"prior": false}\n', encoding="utf-8")
            bad_init = self._tool(
                "init", str(bad_state), str(bad_manifest), "smoke-core-remainder-v5",
                "approval", "250", "10", "100", "1", "config-hash",
                "runner-hash", "implementation-hash", "cfg", str(ledger), ledger_sha,
            )
            self.assertNotEqual(bad_init.returncode, 0)
            self.assertIn("evidence hash mismatch", bad_init.stderr)
            self.assertFalse(bad_state.exists())

    def test_smoke_preserves_one_attempt_per_slot_without_infra_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, manifest, runs = root / "state.json", root / "manifest.json", root / "runs"
            runs.mkdir()
            init = self._tool(
                "init", str(state), str(manifest), "smoke-core", "approval", "50000000",
                "500", "100000", "9", "config-hash", "runner-hash",
                "implementation-hash", "cfg",
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            reserved = self._tool(
                "reserve", str(state), str(manifest), "cfg", "gpt-5.6-luna",
                "xhigh", "smoke-core", str(runs), "5500000", "18", "7200",
            )
            self.assertEqual(reserved.returncode, 0, reserved.stderr)
            recorded = self._tool("record", str(state), str(manifest), "1", "5")
            self.assertFalse(json.loads(recorded.stdout)["eligible"])

            replacement = self._tool(
                "reserve", str(state), str(manifest), "cfg", "gpt-5.6-luna",
                "xhigh", "smoke-core", str(runs), "5500000", "18", "7200",
            )
            self.assertEqual(replacement.returncode, 5)
            self.assertIn("does not replace", replacement.stderr)
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["attempts"]), 1)
            self.assertIsNone(saved["inflight"])
            self.assertTrue(saved["config_state"]["cfg"]["halted"])
            self.assertEqual(saved["config_state"]["cfg"]["infra_replacements"], 0)

    def test_per_config_cap_allows_no_more_than_ten_replacements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, manifest, runs = root / "state.json", root / "manifest.json", root / "runs"
            runs.mkdir()
            init = self._tool(
                "init", str(state), str(manifest), "full", "approval", "100000000",
                "1000", "200000", "20", "config-hash", "runner-hash", "implementation-hash", "cfg",
            )
            self.assertEqual(init.returncode, 0, init.stderr)

            for attempt in range(1, 12):
                reserved = self._tool(
                    "reserve", str(state), str(manifest), "cfg", "gpt-5.6-luna",
                    "xhigh", "r01", str(runs), "5500000", "18", "7200",
                )
                self.assertEqual(reserved.returncode, 0, reserved.stderr)
                _, raw_json, raw_log = reserved.stdout.strip().split("\t")
                payload = _fixture_payload("inference_error", code=f"error-{attempt}")
                Path(raw_json).write_text(json.dumps(payload), encoding="utf-8")
                Path(raw_log).write_text(f"distinct error {attempt}", encoding="utf-8")
                recorded = self._tool("record", str(state), str(manifest), "1", "1")
                self.assertEqual(recorded.returncode, 0, recorded.stderr)

            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["attempts"]), 11)  # original + ten replacements
            self.assertEqual(saved["config_state"]["cfg"]["infra_replacements"], 10)
            self.assertTrue(saved["config_state"]["cfg"]["halted"])

    def test_recovery_charges_full_reservations_and_partial_usage_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, manifest, runs = root / "state.json", root / "manifest.json", root / "runs"
            runs.mkdir()
            init = self._tool(
                "init", str(state), str(manifest), "full", "approval", "50000000",
                "500", "100000", "10", "config-hash", "runner-hash", "implementation-hash", "cfg",
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            reserved = self._tool(
                "reserve", str(state), str(manifest), "cfg", "gpt-5.6-luna",
                "xhigh", "r01", str(runs), "5500000", "18", "7200",
            )
            self.assertEqual(reserved.returncode, 0, reserved.stderr)
            recovered = self._tool("recover", str(state))
            self.assertEqual(recovered.stdout.strip(), "1\t7200.0")
            recorded = self._tool("record", str(state), str(manifest), "125", "7200")
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(saved["cumulative"]["accounted_tokens"], 5_500_000)
            self.assertEqual(saved["cumulative"]["estimated_usd"], 18)
            self.assertEqual(saved["cumulative"]["wall_secs"], 7200)

            reserved = self._tool(
                "reserve", str(state), str(manifest), "cfg", "gpt-5.6-luna",
                "xhigh", "r02", str(runs), "5500000", "18", "7200",
            )
            _, raw_json, raw_log = reserved.stdout.strip().split("\t")
            payload = _fixture_payload("finished_tool", response_status="completed")
            payload["config"]["round_id"] = "r02"
            payload["metadata"]["round_id"] = "r02"
            payload["responses_traces"].append({
                "api_surface": "responses", "response_status": "error",
                "sdk_max_retries": 0, "openai_sdk_version": "2.21.0", "usage": None,
            })
            payload["turns"].append({})
            Path(raw_json).write_text(json.dumps(payload), encoding="utf-8")
            Path(raw_log).write_text("partial usage", encoding="utf-8")
            recorded = self._tool("record", str(state), str(manifest), "0", "2")
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            saved = json.loads(state.read_text(encoding="utf-8"))
            attempt = saved["attempts"][-1]
            self.assertTrue(attempt["selected"])
            self.assertTrue(attempt["usage_estimated"])
            self.assertEqual(attempt["accounted_tokens"], 5_500_000)
            self.assertEqual(attempt["estimated_usd"], 18)

            reserved = self._tool(
                "reserve", str(state), str(manifest), "cfg", "gpt-5.6-luna",
                "xhigh", "r03", str(runs), "5500000", "18", "7200",
            )
            _, raw_json, raw_log = reserved.stdout.strip().split("\t")
            checkpoint = _fixture_payload("max_turns_exhausted", response_status="completed")
            checkpoint["config"]["round_id"] = "r03"
            checkpoint["metadata"]["round_id"] = "r03"
            checkpoint["checkpoint"] = {
                "partial": True,
                "reason": "turn_complete",
                "written_at_utc": "2026-07-17T00:00:00+00:00",
            }
            Path(raw_json).write_text(json.dumps(checkpoint), encoding="utf-8")
            Path(raw_log).write_text("partial checkpoint", encoding="utf-8")
            recorded = self._tool("record", str(state), str(manifest), "124", "3")
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            saved = json.loads(state.read_text(encoding="utf-8"))
            attempt = saved["attempts"][-1]
            self.assertEqual(attempt["classification"], "partial_checkpoint")
            self.assertFalse(attempt["selected"])
            self.assertTrue(attempt["usage_estimated"])
            self.assertEqual(attempt["accounted_tokens"], 5_500_000)
            self.assertEqual(attempt["estimated_usd"], 18)

    def test_identity_mismatch_resume_mismatch_and_artifact_collision_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, manifest, runs = root / "state.json", root / "manifest.json", root / "runs"
            runs.mkdir()
            args = ("init", str(state), str(manifest), "full", "approval", "50000000", "500", "100000", "10", "config-hash", "runner-hash", "implementation-hash", "cfg")
            self.assertEqual(self._tool(*args).returncode, 0)
            mismatch = self._tool(
                "init", str(state), str(manifest), "full", "different-approval", "50000000",
                "500", "100000", "10", "config-hash", "runner-hash", "implementation-hash", "cfg",
            )
            self.assertNotEqual(mismatch.returncode, 0)

            reserved = self._tool(
                "reserve", str(state), str(manifest), "cfg", "gpt-5.6-luna",
                "xhigh", "r01", str(runs), "5500000", "18", "7200",
            )
            _, raw_json, raw_log = reserved.stdout.strip().split("\t")
            payload = _fixture_payload("finished_tool", response_status="completed")
            payload["config"]["round_id"] = "wrong-round"
            payload["metadata"]["round_id"] = "wrong-round"
            Path(raw_json).write_text(json.dumps(payload), encoding="utf-8")
            Path(raw_log).write_text("identity mismatch", encoding="utf-8")
            recorded = self._tool("record", str(state), str(manifest), "0", "1")
            self.assertEqual(json.loads(recorded.stdout)["classification"], "identity_mismatch")

            collision_state = root / "collision-state.json"
            collision_manifest = root / "collision-manifest.json"
            collision_runs = root / "collision-runs"
            collision_runs.mkdir()
            collision_args = (
                "init", str(collision_state), str(collision_manifest), "full", "approval",
                "50000000", "500", "100000", "10", "config-hash", "runner-hash", "implementation-hash", "cfg",
            )
            self.assertEqual(self._tool(*collision_args).returncode, 0)
            (collision_runs / "cfg-r01-a001.log").write_text("existing", encoding="utf-8")
            collision = self._tool(
                "reserve", str(collision_state), str(collision_manifest), "cfg",
                "gpt-5.6-luna", "xhigh", "r01", str(collision_runs), "5500000", "18", "7200",
            )
            self.assertEqual(collision.returncode, 6)
            saved = json.loads(collision_state.read_text(encoding="utf-8"))
            self.assertIsNone(saved["inflight"])
            self.assertEqual(saved["attempts"], [])


class DownstreamIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legacy_source = next((PORT_TO_PORT_DIR / "runs" / "leaderboard-natural-v1-input").glob("*.json"))

    def test_evaluate_rows_copy_identity_and_preserve_legacy_group_key(self):
        payload = json.loads(self.legacy_source.read_text(encoding="utf-8"))
        legacy = evaluate_runs._derive_run_metrics(self.legacy_source, copy.deepcopy(payload), None)
        self.assertNotIn("|eff=", legacy["group_key"])
        self.assertIsNone(legacy["effective_effort"])
        self.assertIsNone(legacy["round_id"])
        expected_legacy_key = (
            f"{legacy['provider']}|{legacy['model']}|th={legacy['thinking']}|"
            f"tb={legacy['thinking_budget']}|mt={legacy['max_tokens']}|"
            f"base={legacy['openai_base_url'] or 'default'}|"
            f"prompt_id={legacy['leaderboard_prompt_id'] or 'unknown'}|"
            f"prompt_version={legacy['task_prompt_version'] or 'none'}|"
            f"prompt_hash={legacy['prompt_hash'] or 'unknown'}"
        )
        self.assertEqual(legacy["group_key"], expected_legacy_key)

        updated = copy.deepcopy(payload)
        updated.setdefault("config", {})["effective_effort"] = "max"
        updated["config"]["round_id"] = "r17"
        row = evaluate_runs._derive_run_metrics(self.legacy_source, updated, None)
        self.assertEqual(row["effective_effort"], "max")
        self.assertEqual(row["round_id"], "r17")
        self.assertIn("|eff=max|", row["group_key"])

    def test_xhigh_and_max_are_two_n25_groups_with_one_to_one_round_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files: list[Path] = []
            enriched: dict[str, dict] = {}
            identities: set[tuple[str, str, str]] = set()
            for effort in ("xhigh", "max"):
                for number in range(1, 26):
                    round_id = f"r{number:02d}"
                    path = root / f"gpt-5.6-luna-{effort}-{round_id}.json"
                    payload = {
                        "schema_version": "mini_rl_run.v3",
                        "metadata": {"task_prompt_hash": "fixture", "round_id": round_id},
                        "config": {
                            "model": "gpt-5.6-luna",
                            "thinking": "xhigh",
                            "max_tokens": 50000,
                            "effective_effort": effort,
                            "round_id": round_id,
                        },
                        "summary": {"model": "gpt-5.6-luna", "thinking": "xhigh", "max_tokens": 50000, "elapsed_ms": 1000},
                        "turns": [],
                    }
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    files.append(path)
                    enriched[str(path.resolve())] = {
                        "score_rubric_version": "fixture",
                        "primary_score_100": 50,
                        "trade_quality_score": 10,
                        "path_efficiency_score": 10,
                        "tool_discipline_score": 10,
                        "report_quality_score": 10,
                        "task_complete": True,
                        "effective_effort": effort,
                        "round_id": round_id,
                    }
                    identity = ("gpt-5.6-luna", effort, round_id)
                    self.assertNotIn(identity, identities)
                    identities.add(identity)

            rows, _ = leaderboard._build_rows(files, enriched, model_name_aliases={})
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["effective_effort"] for row in rows}, {"xhigh", "max"})
            self.assertEqual({row["n"] for row in rows}, {25})
            self.assertEqual(len(identities), 50)
            self.assertEqual({row["model_label"] for row in rows}, {
                "gpt-5.6-luna (eff=xhigh, mt=50000)",
                "gpt-5.6-luna (eff=max, mt=50000)",
            })

    def test_updated_builder_is_byte_identical_for_published_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "leaderboard.md"
            command = [
                str(PYTHON),
                "build_primary_leaderboard.py",
                "--runs-glob",
                "runs/leaderboard-natural-v1-input/*.json",
                "--enriched-jsonl",
                "runs/leaderboard-natural-v1-refresh-20260718.jsonl",
                "--out",
                str(out),
                "--leaderboard-prompt-id",
                "natural",
            ]
            result = subprocess.run(command, cwd=PORT_TO_PORT_DIR, text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(out.read_bytes(), (PORT_TO_PORT_DIR / "leaderboards" / "leaderboard-natural.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
