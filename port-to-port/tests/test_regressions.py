import argparse
import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
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


evaluate_runs = _load_module("evaluate_runs_test", "evaluate_runs.py")
llm_factory = _load_module("llm_factory_test", "llm_factory.py")
mini_rl_env = _load_module("mini_rl_env_test", "mini-rl-env.py")
build_primary_leaderboard = _load_module("build_primary_leaderboard_test", "build_primary_leaderboard.py")
tool_catalog = _load_module("tool_catalog_test", "tool_catalog.py")
synthetic_world = _load_module("synthetic_world_test", "synthetic_world.py")


class EvaluateRunsRegressionTests(unittest.TestCase):
    def test_summary_fallback_accepts_sector_only_mega_reference(self) -> None:
        payload = {
            "metadata": {
                "initial_state": {
                    "sector": 3080,
                    "credits": 1000,
                }
            },
            "summary": {
                "final_sector": 3080,
                "reached_mega_anytime": True,
                "recharge_to_full_at_mega": True,
                "recharge_units_total": 33,
                "recharge_cost_total": 66,
                "recharge_sector": 1611,
            },
            "termination": {
                "finished_called": True,
                "finished_message": (
                    "Used sector 1611, recharged 33 units for 66 credits, "
                    "traded at 3 ports, total profit 120 credits."
                ),
            },
            "turns": [],
        }

        metrics = evaluate_runs._derive_run_metrics(Path("synthetic.json"), payload, report_judge=None)

        self.assertTrue(metrics["coherent_report"])
        self.assertTrue(metrics["objective_success"])
        self.assertTrue(metrics["lenient_success"])
        self.assertEqual(metrics["mega_port_used_sector"], 1611)
        self.assertEqual(metrics["recharge_units"], 33)
        self.assertEqual(metrics["recharge_cost"], 66)

    def test_objective_success_does_not_require_trade(self) -> None:
        payload = {
            "metadata": {
                "initial_state": {
                    "sector": 3080,
                    "warp": 10,
                    "max_warp": 20,
                    "credits": 1000,
                }
            },
            "summary": {
                "reached_mega_anytime": True,
            },
            "termination": {
                "finished_called": True,
                "finished_message": (
                    "Back in sector 3080. Used mega-port sector 1611, "
                    "recharged 10 warp units, cost 20 credits, traded at 0 ports, "
                    "total profit -20 credits."
                ),
            },
            "turns": [
                {
                    "llm_turn": 1,
                    "decision_ms": 1.0,
                    "tool_calls": [{"name": "move", "args": {}, "result_status": "acknowledged"}],
                    "state_before": {"sector": 3080, "warp": 10, "max_warp": 20, "credits": 1000},
                    "state_after": {"sector": 1611, "warp": 10, "max_warp": 20, "credits": 1000},
                },
                {
                    "llm_turn": 2,
                    "decision_ms": 1.0,
                    "tool_calls": [
                        {
                            "name": "recharge_warp_power",
                            "args": {},
                            "result_status": "success",
                        }
                    ],
                    "state_before": {"sector": 1611, "warp": 10, "max_warp": 20, "credits": 1000},
                    "state_after": {"sector": 1611, "warp": 20, "max_warp": 20, "credits": 980},
                },
                {
                    "llm_turn": 3,
                    "decision_ms": 1.0,
                    "tool_calls": [{"name": "move", "args": {}, "result_status": "acknowledged"}],
                    "state_before": {"sector": 1611, "warp": 20, "max_warp": 20, "credits": 980},
                    "state_after": {"sector": 3080, "warp": 20, "max_warp": 20, "credits": 980},
                },
            ],
        }

        metrics = evaluate_runs._derive_run_metrics(Path("synthetic.json"), payload, report_judge=None)

        self.assertFalse(metrics["at_least_one_trade"])
        self.assertTrue(metrics["objective_success"])
        self.assertNotIn("deterministic_report_accuracy", metrics)
        self.assertNotIn("claimed_total_profit_credits", metrics)

    def test_navigation_metrics_use_actual_post_move_sector(self) -> None:
        payload = {
            "metadata": {
                "initial_state": {
                    "sector": 3080,
                    "warp": 10,
                    "max_warp": 20,
                    "credits": 1000,
                }
            },
            "summary": {
                "final_sector": 3080,
                "reached_mega_anytime": True,
                "recharge_to_full_at_mega": True,
            },
            "termination": {
                "finished_called": True,
                "finished_message": (
                    "Used mega-port sector 1611, recharged 10 units for 20 credits, "
                    "traded at 1 ports, total profit -20 credits."
                ),
            },
            "turns": [
                {
                    "llm_turn": 1,
                    "decision_ms": 1.0,
                    "tool_calls": [{"name": "move", "args": {"to_sector": 2266}, "result_status": "acknowledged"}],
                    "state_before": {"sector": 3080, "warp": 10, "max_warp": 20, "credits": 1000},
                    "state_after": {"sector": 3080, "warp": 10, "max_warp": 20, "credits": 1000},
                },
                {
                    "llm_turn": 2,
                    "decision_ms": 1.0,
                    "tool_calls": [{"name": "move", "args": {"to_sector": 1611}, "result_status": "acknowledged"}],
                    "state_before": {"sector": 2266, "warp": 7, "max_warp": 20, "credits": 1000},
                    "state_after": {"sector": 2266, "warp": 7, "max_warp": 20, "credits": 1000},
                },
                {
                    "llm_turn": 3,
                    "decision_ms": 1.0,
                    "tool_calls": [
                        {
                            "name": "recharge_warp_power",
                            "args": {"units": 10},
                            "result_status": "success",
                        }
                    ],
                    "state_before": {"sector": 1611, "warp": 10, "max_warp": 20, "credits": 1000},
                    "state_after": {"sector": 1611, "warp": 20, "max_warp": 20, "credits": 980},
                },
                {
                    "llm_turn": 4,
                    "decision_ms": 1.0,
                    "tool_calls": [{"name": "move", "args": {"to_sector": 2266}, "result_status": "acknowledged"}],
                    "state_before": {"sector": 1611, "warp": 20, "max_warp": 20, "credits": 980},
                    "state_after": {"sector": 1611, "warp": 20, "max_warp": 20, "credits": 980},
                },
                {
                    "llm_turn": 5,
                    "decision_ms": 1.0,
                    "tool_calls": [{"name": "move", "args": {"to_sector": 3080}, "result_status": "acknowledged"}],
                    "state_before": {"sector": 2266, "warp": 17, "max_warp": 20, "credits": 980},
                    "state_after": {"sector": 2266, "warp": 17, "max_warp": 20, "credits": 980},
                },
            ],
        }

        metrics = evaluate_runs._derive_run_metrics(Path("synthetic.json"), payload, report_judge=None)

        self.assertEqual(metrics["moves_to_first_mega"], 2)
        self.assertEqual(metrics["post_goal_moves"], 2)

    def test_canonical_required_course_turnaround_does_not_count_as_backtrack(self) -> None:
        route = evaluate_runs._canonical_required_course_sectors(evaluate_runs.DEFAULT_START_SECTOR)
        turns = []
        credits = 1000
        warp = 500
        max_warp = 500
        llm_turn = 1

        for idx, next_sector in enumerate(route[1:], start=1):
            current_sector = route[idx - 1]
            turns.append(
                {
                    "llm_turn": llm_turn,
                    "decision_ms": 1.0,
                    "tool_calls": [{"name": "move", "args": {"to_sector": next_sector}, "result_status": "acknowledged"}],
                    "state_before": {
                        "sector": current_sector,
                        "warp": warp,
                        "max_warp": max_warp,
                        "credits": credits,
                        "cargo": {},
                        "empty_holds": 30,
                        "used_holds": 0,
                    },
                    "state_after": {
                        "sector": next_sector,
                        "warp": max(0, warp - 3),
                        "max_warp": max_warp,
                        "credits": credits,
                        "cargo": {},
                        "empty_holds": 30,
                        "used_holds": 0,
                    },
                }
            )
            warp = max(0, warp - 3)
            llm_turn += 1

            if next_sector == evaluate_runs.MEGA_PORT_SECTOR:
                turns.append(
                    {
                        "llm_turn": llm_turn,
                        "decision_ms": 1.0,
                        "tool_calls": [
                            {
                                "name": "recharge_warp_power",
                                "args": {"units": max_warp - warp},
                                "result_status": "success",
                            }
                        ],
                        "state_before": {
                            "sector": next_sector,
                            "warp": warp,
                            "max_warp": max_warp,
                            "credits": credits,
                            "cargo": {},
                            "empty_holds": 30,
                            "used_holds": 0,
                        },
                        "state_after": {
                            "sector": next_sector,
                            "warp": max_warp,
                            "max_warp": max_warp,
                            "credits": credits - 66,
                            "cargo": {},
                            "empty_holds": 30,
                            "used_holds": 0,
                        },
                    }
                )
                credits -= 66
                warp = max_warp
                llm_turn += 1

        turns.append(
            {
                "llm_turn": llm_turn,
                "decision_ms": 1.0,
                "tool_calls": [
                    {
                        "name": "finished",
                        "args": {
                            "message": (
                                "Used mega-port sector 1611, recharged 33 units for 66 credits, "
                                "traded at 0 ports, total profit -66 credits."
                            )
                        },
                        "result_status": "success",
                    }
                ],
                "state_before": {
                    "sector": evaluate_runs.DEFAULT_START_SECTOR,
                    "warp": warp,
                    "max_warp": max_warp,
                    "credits": credits,
                    "cargo": {},
                    "empty_holds": 30,
                    "used_holds": 0,
                },
                "state_after": {
                    "sector": evaluate_runs.DEFAULT_START_SECTOR,
                    "warp": warp,
                    "max_warp": max_warp,
                    "credits": credits,
                    "cargo": {},
                    "empty_holds": 30,
                    "used_holds": 0,
                },
            }
        )

        payload = {
            "metadata": {
                "initial_state": {
                    "sector": evaluate_runs.DEFAULT_START_SECTOR,
                    "warp": 500,
                    "max_warp": 500,
                    "credits": 1000,
                    "cargo": {},
                    "empty_holds": 30,
                    "used_holds": 0,
                }
            },
            "summary": {
                "final_sector": evaluate_runs.DEFAULT_START_SECTOR,
                "reached_mega_anytime": True,
                "recharge_to_full_at_mega": True,
            },
            "termination": {
                "finished_called": True,
                "finished_message": (
                    "Used mega-port sector 1611, recharged 33 units for 66 credits, "
                    "traded at 0 ports, total profit -66 credits."
                ),
            },
            "turns": turns,
        }

        metrics = evaluate_runs._derive_run_metrics(Path("synthetic.json"), payload, report_judge=None)

        self.assertEqual(metrics["extra_moves_count"], 0)
        self.assertEqual(metrics["avoidable_backtrack_count"], 0)
        self.assertEqual(metrics["path_efficiency_score"], 15)

    def test_mixed_trade_and_recharge_turn_uses_action_replay_for_trade_pnl(self) -> None:
        payload = {
            "metadata": {
                "initial_state": {
                    "sector": 1611,
                    "warp": 490,
                    "max_warp": 500,
                    "credits": 1000,
                }
            },
            "summary": {
                "final_sector": 1611,
            },
            "turns": [
                {
                    "llm_turn": 1,
                    "decision_ms": 1.0,
                    "tool_calls": [
                        {
                            "name": "trade",
                            "args": {
                                "trade_type": "buy",
                                "commodity": "quantum_foam",
                                "quantity": 1,
                            },
                            "result_status": "success",
                        },
                        {
                            "name": "recharge_warp_power",
                            "args": {"units": 10},
                            "result_status": "success",
                        },
                    ],
                    "state_before": {"sector": 1611, "warp": 490, "max_warp": 500, "credits": 1000},
                    "state_after": {"sector": 1611, "warp": 500, "max_warp": 500, "credits": 961},
                }
            ],
        }

        metrics = evaluate_runs._derive_run_metrics(Path("synthetic.json"), payload, report_judge=None)

        self.assertEqual(metrics["realized_pnl"], -19.0)
        self.assertEqual(metrics["realized_pnl_source"], "trade_action_replay")
        self.assertEqual(metrics["report_truth"]["final_credits"], 961)
        self.assertEqual(metrics["total_profit_credits"], -39)

    def test_multi_call_turn_tracks_trade_ports_by_call_order(self) -> None:
        payload = {
            "metadata": {
                "initial_state": {
                    "sector": 1611,
                    "credits": 1000,
                }
            },
            "summary": {
                "final_sector": 1928,
                "final_credits": 1013,
            },
            "termination": {
                "finished_called": True,
                "finished_message": (
                    "Used MEGA SSS, recharged 0 warp for 0 credits, traded at 2 ports, overall gain 13 credits."
                ),
            },
            "turns": [
                {
                    "llm_turn": 1,
                    "decision_ms": 1.0,
                    "tool_calls": [
                        {
                            "name": "trade",
                            "args": {"trade_type": "buy", "commodity": "quantum_foam", "quantity": 1},
                            "result_status": "acknowledged",
                        },
                        {
                            "name": "move",
                            "args": {"to_sector": 1928},
                            "result_status": "acknowledged",
                        },
                        {
                            "name": "trade",
                            "args": {"trade_type": "sell", "commodity": "quantum_foam", "quantity": 1},
                            "result_status": "acknowledged",
                        },
                    ],
                    "state_before": {"sector": 1611, "credits": 1000},
                    "state_after": {"sector": 1928, "credits": 1013},
                }
            ],
        }

        metrics = evaluate_runs._derive_run_metrics(Path("synthetic.json"), payload, report_judge=None)

        self.assertEqual(metrics["successful_trade_port_count"], 2)
        self.assertEqual(metrics["report_truth"]["trade_port_count"], 2)
        self.assertEqual(metrics["realized_pnl"], 13.0)

    def test_multi_move_turn_counts_intermediate_sectors(self) -> None:
        payload = {
            "metadata": {
                "initial_state": {
                    "sector": 3080,
                    "credits": 1000,
                }
            },
            "summary": {
                "final_sector": 2266,
            },
            "turns": [
                {
                    "llm_turn": 1,
                    "decision_ms": 1.0,
                    "tool_calls": [
                        {"name": "move", "args": {"to_sector": 2266}, "result_status": "acknowledged"},
                        {"name": "move", "args": {"to_sector": 3313}, "result_status": "acknowledged"},
                    ],
                    "state_before": {"sector": 3080},
                    "state_after": {"sector": 3313},
                },
                {
                    "llm_turn": 2,
                    "decision_ms": 1.0,
                    "tool_calls": [
                        {"name": "move", "args": {"to_sector": 2266}, "result_status": "acknowledged"},
                    ],
                    "state_before": {"sector": 3313},
                    "state_after": {"sector": 2266},
                },
            ],
        }

        metrics = evaluate_runs._derive_run_metrics(Path("synthetic.json"), payload, report_judge=None)

        self.assertEqual(metrics["total_moves"], 3)
        self.assertEqual(metrics["backtracking_count"], 1)

    def test_multi_move_turn_detects_pass_through_mega(self) -> None:
        payload = {
            "metadata": {
                "initial_state": {
                    "sector": 1928,
                    "credits": 1000,
                }
            },
            "summary": {
                "final_sector": 2058,
            },
            "turns": [
                {
                    "llm_turn": 1,
                    "decision_ms": 1.0,
                    "tool_calls": [
                        {"name": "move", "args": {"to_sector": 1611}, "result_status": "acknowledged"},
                        {"name": "move", "args": {"to_sector": 2058}, "result_status": "acknowledged"},
                    ],
                    "state_before": {"sector": 1928},
                    "state_after": {"sector": 2058},
                },
            ],
        }

        metrics = evaluate_runs._derive_run_metrics(Path("synthetic.json"), payload, report_judge=None)

        self.assertTrue(metrics["reached_mega_anytime"])
        self.assertEqual(metrics["moves_to_first_mega"], 1)
        self.assertEqual(metrics["post_goal_moves"], 1)

    def test_final_credits_prefer_summary_after_async_completion(self) -> None:
        payload = {
            "metadata": {
                "initial_state": {
                    "sector": 3080,
                    "credits": 1000,
                },
                "task_prompt_hash": "prompt-a",
            },
            "summary": {
                "final_sector": 3080,
                "final_credits": 980,
                "reached_mega_anytime": True,
                "recharge_to_full_at_mega": True,
                "recharge_units_total": 10,
                "recharge_cost_total": 20,
                "recharge_sector": 1611,
            },
            "termination": {
                "finished_called": True,
                "finished_message": (
                    "Used sector 1611, recharged 10 units for 20 credits, "
                    "traded at 0 ports, total profit -20 credits."
                ),
            },
            "turns": [
                {
                    "llm_turn": 1,
                    "decision_ms": 1.0,
                    "tool_calls": [
                        {
                            "name": "recharge_warp_power",
                            "args": {"units": 10},
                            "result_status": "acknowledged",
                        }
                    ],
                    "state_before": {"sector": 1611, "warp": 10, "max_warp": 20, "credits": 1000},
                    "state_after": {"sector": 1611, "warp": 10, "max_warp": 20, "credits": 1000},
                }
            ],
        }

        metrics = evaluate_runs._derive_run_metrics(Path("synthetic.json"), payload, report_judge=None)

        self.assertEqual(metrics["total_profit_credits"], -20)
        self.assertEqual(metrics["report_truth"]["final_credits"], 980)
        self.assertEqual(metrics["report_truth"]["total_profit_credits"], -20)

    def test_required_course_trade_oracle_matches_current_world(self) -> None:
        oracle = evaluate_runs._compute_required_course_trade_oracle(
            start_sector=3080,
            initial_state={
                "sector": 3080,
                "credits": 16564,
                "cargo": {"quantum_foam": 10, "retro_organics": 0, "neuro_symbolics": 0},
                "empty_holds": 20,
                "used_holds": 10,
                "warp": 500,
                "max_warp": 500,
            },
            turns=[],
        )

        self.assertEqual(oracle["required_course_port_visits"], [3080, 4874, 2831, 1611, 2831, 4874, 3080])
        self.assertEqual(oracle["required_course_optimal_trade_value"], 2310)
        self.assertEqual(oracle["beneficial_visit_indexes"], [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(oracle["required_course_recharge_cost"], 66)

    def test_derive_run_metrics_stamps_prompt_scope_and_primary_score(self) -> None:
        payload = {
            "metadata": {
                "initial_state": {
                    "sector": 3080,
                    "credits": 16564,
                    "cargo": {"quantum_foam": 10, "retro_organics": 0, "neuro_symbolics": 0},
                    "empty_holds": 20,
                    "used_holds": 10,
                    "warp": 500,
                    "max_warp": 500,
                },
                "task_variant": "natural",
                "task_prompt_version": "v1",
                "task_prompt_hash": "prompt-a",
            },
            "summary": {
                "final_sector": 3080,
                "final_credits": 17000,
                "reached_mega_anytime": True,
                "recharge_to_full_at_mega": True,
                "recharge_units_total": 33,
                "recharge_cost_total": 66,
                "recharge_sector": 1611,
                "finished_called": True,
                "coherent_report": True,
                "elapsed_ms": 1000,
            },
            "termination": {
                "finished_called": True,
                "finished_message": (
                    "Used MEGA SSS, recharged 33 units for 66 credits, "
                    "traded at 3 ports, total profit 436 credits."
                ),
                "reason": "finished_tool",
            },
            "config": {
                "provider": "openai",
                "model": "demo",
                "thinking": "medium",
                "task_variant": "natural",
                "task_prompt_version": "v1",
            },
            "turns": [],
        }

        metrics = evaluate_runs._derive_run_metrics(Path("synthetic.json"), payload, report_judge=None)

        self.assertEqual(metrics["leaderboard_prompt_id"], "natural")
        self.assertEqual(metrics["task_variant"], "natural")
        self.assertEqual(metrics["task_prompt_version"], "v1")
        self.assertEqual(metrics["score_rubric_version"], "port_to_port_primary_v1")
        self.assertIn("primary_score_100", metrics)
        self.assertIn("trade_quality_score", metrics)
        self.assertIn("report_quality_score", metrics)

    def test_aggregate_group_uses_primary_summary_metrics(self) -> None:
        agg = evaluate_runs._aggregate_group(
            [
                {
                    "leaderboard_prompt_id": "natural",
                    "task_variant": "natural",
                    "task_prompt_version": "v1",
                    "prompt_hash": "prompt-a",
                    "score_rubric_version": "port_to_port_primary_v1",
                    "task_complete": True,
                    "primary_score_100": 80,
                    "mission_completion_score": 40,
                    "trade_quality_score": 10,
                    "path_efficiency_score": 12,
                    "tool_discipline_score": 13,
                    "report_quality_score": 5,
                    "elapsed_ms": 1000,
                    "turn_decision_ms_values": [100.0, 200.0],
                    "terminal_class": "strict_success",
                    "report_accuracy": True,
                },
                {
                    "leaderboard_prompt_id": "natural",
                    "task_variant": "natural",
                    "task_prompt_version": "v1",
                    "prompt_hash": "prompt-a",
                    "score_rubric_version": "port_to_port_primary_v1",
                    "task_complete": False,
                    "primary_score_100": 90,
                    "mission_completion_score": 35,
                    "trade_quality_score": 12,
                    "path_efficiency_score": 14,
                    "tool_discipline_score": 15,
                    "report_quality_score": 14,
                    "elapsed_ms": 2000,
                    "turn_decision_ms_values": [300.0],
                    "terminal_class": "other_failure",
                    "report_accuracy": False,
                },
            ]
        )

        self.assertEqual(agg["leaderboard_prompt_id"], "natural")
        self.assertEqual(agg["score_rubric_versions"], ["port_to_port_primary_v1"])
        self.assertEqual(agg["primary_score_100_median"], 85.0)
        self.assertEqual(agg["task_complete"]["count"], 1)
        self.assertAlmostEqual(agg["task_complete"]["rate"], 0.5)
        self.assertEqual(agg["turn_p50_ms"], 200.0)
        self.assertEqual(agg["total_time_p50_s"], 1.5)

    def test_group_key_includes_prompt_hash(self) -> None:
        payload_a = {
            "metadata": {
                "initial_state": {"sector": 3080, "credits": 1000},
                "task_prompt_hash": "prompt-a",
            },
            "summary": {"final_sector": 3080},
            "config": {"provider": "openai", "model": "demo", "thinking": "medium"},
            "turns": [],
        }
        payload_b = {
            "metadata": {
                "initial_state": {"sector": 3080, "credits": 1000},
                "task_prompt_hash": "prompt-b",
            },
            "summary": {"final_sector": 3080},
            "config": {"provider": "openai", "model": "demo", "thinking": "medium"},
            "turns": [],
        }

        row_a = evaluate_runs._derive_run_metrics(Path("a.json"), payload_a, report_judge=None)
        row_b = evaluate_runs._derive_run_metrics(Path("b.json"), payload_b, report_judge=None)

        self.assertNotEqual(row_a["group_key"], row_b["group_key"])

    def test_group_key_separates_builtin_prompt_revisions(self) -> None:
        def payload_for(version: str, prompt_hash: str) -> dict[str, object]:
            return {
                "metadata": {
                    "initial_state": {"sector": 3080, "credits": 1000},
                    "task_variant": "natural",
                    "task_prompt_version": version,
                    "task_prompt_hash": prompt_hash,
                    "leaderboard_prompt_id": "natural",
                },
                "summary": {"final_sector": 3080},
                "config": {
                    "provider": "openai",
                    "model": "demo",
                    "thinking": "medium",
                    "task_variant": "natural",
                    "task_prompt_version": version,
                },
                "turns": [],
            }

        row_v1 = evaluate_runs._derive_run_metrics(
            Path("v1.json"),
            payload_for("v1", "prompt-a"),
            report_judge=None,
        )
        row_v2 = evaluate_runs._derive_run_metrics(
            Path("v2.json"),
            payload_for("v2", "prompt-b"),
            report_judge=None,
        )

        self.assertNotEqual(row_v1["group_key"], row_v2["group_key"])

    def test_group_key_normalizes_equivalent_openai_base_urls(self) -> None:
        def payload_for(base_url: str) -> dict[str, object]:
            return {
                "metadata": {
                    "initial_state": {"sector": 3080, "credits": 1000},
                    "task_prompt_hash": "prompt-a",
                },
                "summary": {"final_sector": 3080},
                "config": {
                    "provider": "openai",
                    "model": "demo",
                    "thinking": "medium",
                    "openai_base_url": base_url,
                },
                "turns": [],
            }

        row_a = evaluate_runs._derive_run_metrics(
            Path("a.json"),
            payload_for("http://host:8000"),
            report_judge=None,
        )
        row_b = evaluate_runs._derive_run_metrics(
            Path("b.json"),
            payload_for("http://host:8000/v1"),
            report_judge=None,
        )
        row_c = evaluate_runs._derive_run_metrics(
            Path("c.json"),
            payload_for("http://host:8000/chat/completions"),
            report_judge=None,
        )

        self.assertEqual(row_a["group_key"], row_b["group_key"])
        self.assertEqual(row_b["group_key"], row_c["group_key"])
        self.assertEqual(row_c["openai_base_url"], "http://host:8000/v1")

    def test_variant_display_label_includes_budget_tokens_prompt_and_base(self) -> None:
        label = evaluate_runs._variant_display_label(
            {
                "model": "demo",
                "thinking": "medium",
                "thinking_budget": 1536,
                "max_tokens": 4608,
                "prompt_hash": "0123456789abcdef",
                "openai_base_url": "https://spark-18e9:8000/v1",
            }
        )

        self.assertEqual(
            label,
            "demo (th=medium, tb=1536, mt=4608, prompt=01234567, base=spark-18e9:8000)",
        )

    def test_coherent_report_accepts_semantic_recharge_wording(self) -> None:
        message = (
            "Used MEGA SSS, topped off 33 warp for 66 credits, visited 3 ports, overall gain 120 credits."
        )

        self.assertTrue(evaluate_runs._is_coherent_finished_report(message))

    def test_report_element_verdicts_require_recharge_context_for_recharge_cost(self) -> None:
        verdicts = evaluate_runs._compute_report_element_verdicts(
            finished_message=(
                "Used MEGA SSS, recharged 33 units, traded at 3 ports, total profit 66 credits."
            ),
            report_truth={
                "mega_port_sector": 1611,
                "recharge_units": 33,
                "recharge_cost": 66,
                "trade_port_count": 3,
                "total_profit_credits": 66,
            },
        )

        self.assertTrue(verdicts["recharge_amount"]["present"])
        self.assertTrue(verdicts["recharge_amount"]["accurate"])
        self.assertFalse(verdicts["recharge_cost"]["present"])
        self.assertFalse(verdicts["recharge_cost"]["accurate"])
        self.assertTrue(verdicts["total_profit"]["present"])
        self.assertTrue(verdicts["total_profit"]["accurate"])

    def test_report_judge_prompt_accepts_semantic_whole_trip_profit(self) -> None:
        judge = evaluate_runs.AnthropicReportJudge(
            evaluate_runs.ReportJudgeConfig(
                model="dummy",
                api_key="dummy",
                timeout_secs=1.0,
            )
        )

        with mock.patch.object(judge, "_request_text", return_value=("PASS", None)) as request_mock:
            verdict, reason = judge.judge(
                finished_message=(
                    "Total profit from trades: 0 credits. "
                    "Net change: -66 credits. "
                    "Warp power recharged: 33 units for 66 credits."
                ),
                expected_finish_sector=3080,
                report_truth={
                    "mega_port_sector": 1611,
                    "recharge_units": 33,
                    "recharge_cost": 66,
                    "trade_port_count": 0,
                    "total_profit_credits": -66,
                },
            )

        self.assertTrue(verdict)
        self.assertEqual(reason, "PASS")
        prompt = request_mock.call_args.kwargs["user_prompt"]
        self.assertIn("Judge by semantic meaning, not exact field labels.", prompt)
        self.assertIn("'net change', 'net result', 'overall gain/loss'", prompt)
        self.assertIn("trade-only profit metric and a whole-trip net metric", prompt)
        self.assertIn("Total profit from trades: 0 credits", prompt)
        self.assertIn("Net change: -66 credits (warp recharge cost only)", prompt)
        self.assertIn("'for 66 credits'", prompt)


class MiniRLEnvRegressionTests(unittest.TestCase):
    def test_serialize_llm_usage_metrics_includes_reasoning_and_cached_tokens(self) -> None:
        metric = mini_rl_env.LLMUsageMetricsData(
            processor="llm",
            model="demo-model",
            value=mini_rl_env.LLMTokenUsage(
                prompt_tokens=120,
                completion_tokens=45,
                total_tokens=165,
                cache_read_input_tokens=32,
                reasoning_tokens=17,
            ),
        )

        usage = mini_rl_env._serialize_llm_usage_metrics(metric)

        self.assertEqual(usage["prompt_tokens"], 120)
        self.assertEqual(usage["completion_tokens"], 45)
        self.assertEqual(usage["total_tokens"], 165)
        self.assertEqual(usage["cache_read_input_tokens"], 32)
        self.assertEqual(usage["reasoning_tokens"], 17)

    def test_coherent_report_accepts_semantic_recharge_wording(self) -> None:
        message = (
            "Used MEGA SSS, topped off 33 warp for 66 credits, visited 3 ports, overall gain 120 credits."
        )

        self.assertTrue(mini_rl_env._is_coherent_finished_report(message))

    def test_finished_waits_for_pending_async_completion_before_stop(self) -> None:
        async def _run() -> None:
            runtime = mini_rl_env._BenchmarkRuntime.__new__(mini_rl_env._BenchmarkRuntime)
            runtime.stop_requested = False
            runtime.inference_suppressed = False
            runtime.terminal_reason = "max_turns_exhausted"
            runtime._deferred_stop_reason = None
            runtime.done_event = asyncio.Event()
            runtime.pipeline_task = None
            runtime.async_completion_timeout_count = 0
            runtime._async_dependency_waiters = []
            runtime.controller = mini_rl_env._BenchmarkInferenceController(runtime)
            runtime.response_tracker = types.SimpleNamespace(
                finalize_pending_response=mock.AsyncMock(),
            )

            timeout_handle = mock.Mock()
            runtime.controller._pending_async = {
                "move-1": {
                    "expected_event": "movement.complete",
                    "timeout_handle": timeout_handle,
                }
            }

            runtime.request_stop("finished_tool", wait_for_pending_async=True)

            self.assertFalse(runtime.stop_requested)
            self.assertTrue(runtime.inference_suppressed)
            self.assertFalse(runtime.done_event.is_set())

            await runtime.controller.on_event("movement.complete")
            await asyncio.sleep(0)

            self.assertTrue(runtime.stop_requested)
            self.assertTrue(runtime.done_event.is_set())
            self.assertEqual(runtime.terminal_reason, "finished_tool")
            timeout_handle.cancel.assert_called_once_with()
            runtime.response_tracker.finalize_pending_response.assert_awaited_once()

        asyncio.run(_run())

    def test_clear_pending_for_event_clears_only_one(self) -> None:
        controller = mini_rl_env._BenchmarkInferenceController(
            types.SimpleNamespace(async_completion_timeout_count=0)
        )

        first_handle = mock.Mock()
        second_handle = mock.Mock()
        controller._pending_async = {
            "first": {"expected_event": "trade", "timeout_handle": first_handle},
            "second": {"expected_event": "trade", "timeout_handle": second_handle},
        }

        cleared = controller._clear_pending_for_event("trade")

        self.assertEqual(cleared, 1)
        self.assertNotIn("first", controller._pending_async)
        self.assertIn("second", controller._pending_async)
        first_handle.cancel.assert_called_once_with()
        second_handle.cancel.assert_not_called()

    def test_response_tracker_logs_turn_usage_from_metrics_frame(self) -> None:
        async def _run() -> None:
            world = types.SimpleNamespace(
                bad_actions_count=0,
                state_snapshot=lambda: {"sector": 3080, "credits": 1000},
                increment_bad_action=mock.Mock(),
            )
            runtime = types.SimpleNamespace(
                stop_requested=False,
                inference_suppressed=False,
                no_tool_call_count=0,
                last_error_event=None,
                turn_logs=[],
                turn_count=0,
                max_turns=50,
                request_stop=mock.Mock(),
                world=world,
            )
            controller = mini_rl_env._BenchmarkInferenceController(runtime)
            tracker = mini_rl_env._BenchmarkResponseTracker(runtime, controller)
            clock = SystemClock()
            clock.start()
            task_manager = TaskManager()
            task_manager.setup(TaskManagerParams(loop=asyncio.get_running_loop()))
            await tracker.setup(FrameProcessorSetup(clock=clock, task_manager=task_manager))
            await asyncio.sleep(0)
            function_call = FunctionCallFromLLM(
                function_name="move",
                tool_call_id="move-1",
                arguments={"to_sector": 1611},
                context=None,
            )

            await tracker.process_frame(
                StartFrame(enable_metrics=True, enable_usage_metrics=True),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )
            await tracker.process_frame(
                mini_rl_env.LLMFullResponseStartFrame(),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )
            await tracker.process_frame(
                mini_rl_env.MetricsFrame(
                    data=[
                        mini_rl_env.LLMUsageMetricsData(
                            processor="llm",
                            model="demo-model",
                            value=mini_rl_env.LLMTokenUsage(
                                prompt_tokens=120,
                                completion_tokens=45,
                                total_tokens=165,
                                cache_read_input_tokens=32,
                                reasoning_tokens=17,
                            ),
                        )
                    ]
                ),
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
                    result={"ok": True},
                ),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )

            self.assertEqual(len(runtime.turn_logs), 1)
            usage = runtime.turn_logs[0]["usage"]
            self.assertEqual(usage["prompt_tokens"], 120)
            self.assertEqual(usage["completion_tokens"], 45)
            self.assertEqual(usage["total_tokens"], 165)
            self.assertEqual(usage["cache_read_input_tokens"], 32)
            self.assertEqual(usage["reasoning_tokens"], 17)
            self.assertEqual(usage["processor"], "llm")
            self.assertEqual(usage["model"], "demo-model")
            await tracker.cleanup()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_response_tracker_waits_for_async_completion_before_finalizing_turn(self) -> None:
        async def _run() -> None:
            state = {"sector": 4874, "credits": 1000}
            world = types.SimpleNamespace(
                bad_actions_count=0,
                state_snapshot=lambda: dict(state),
                increment_bad_action=mock.Mock(),
            )
            runtime = types.SimpleNamespace(
                stop_requested=False,
                inference_suppressed=False,
                no_tool_call_count=0,
                last_error_event=None,
                turn_logs=[],
                turn_count=0,
                max_turns=50,
                request_stop=mock.Mock(),
                world=world,
                async_completion_timeout_count=0,
                has_async_dependency_waiters=lambda: False,
                resolve_async_dependency_waiters=mock.Mock(),
                maybe_finalize_deferred_stop=mock.Mock(),
            )
            controller = mini_rl_env._BenchmarkInferenceController(runtime)
            tracker = mini_rl_env._BenchmarkResponseTracker(runtime, controller)
            runtime.controller = controller
            runtime.response_tracker = tracker

            clock = SystemClock()
            clock.start()
            task_manager = TaskManager()
            task_manager.setup(TaskManagerParams(loop=asyncio.get_running_loop()))
            await tracker.setup(FrameProcessorSetup(clock=clock, task_manager=task_manager))
            await asyncio.sleep(0)

            function_call = FunctionCallFromLLM(
                function_name="trade",
                tool_call_id="trade-1",
                arguments={"trade_type": "sell", "commodity": "quantum_foam", "quantity": 1},
                context=None,
            )

            controller.register_async_completion(
                tool_call_id="trade-1",
                expected_event="trade.executed",
                tool_name="trade",
            )

            await tracker.process_frame(
                StartFrame(enable_metrics=True, enable_usage_metrics=True),
                mini_rl_env.FrameDirection.DOWNSTREAM,
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
                    function_name="trade",
                    tool_call_id="trade-1",
                    arguments={"trade_type": "sell", "commodity": "quantum_foam", "quantity": 1},
                    result={"status": "Executed."},
                ),
                mini_rl_env.FrameDirection.DOWNSTREAM,
            )

            self.assertEqual(runtime.turn_logs, [])

            state["credits"] = 1033
            await controller.on_event("trade.executed")

            self.assertEqual(len(runtime.turn_logs), 1)
            self.assertEqual(runtime.turn_logs[0]["state_after"]["credits"], 1033)
            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_last_turn_async_completion_waits_before_requesting_stop(self) -> None:
        async def _run() -> None:
            state = {"sector": 3080, "credits": 1000}
            world = types.SimpleNamespace(
                bad_actions_count=0,
                state_snapshot=lambda: dict(state),
                increment_bad_action=mock.Mock(),
            )
            runtime = types.SimpleNamespace(
                stop_requested=False,
                inference_suppressed=False,
                no_tool_call_count=0,
                last_error_event=None,
                turn_logs=[],
                turn_count=0,
                max_turns=1,
                request_stop=mock.Mock(),
                world=world,
                async_completion_timeout_count=0,
                has_async_dependency_waiters=lambda: False,
                resolve_async_dependency_waiters=mock.Mock(),
                maybe_finalize_deferred_stop=mock.Mock(),
            )
            controller = mini_rl_env._BenchmarkInferenceController(runtime)
            tracker = mini_rl_env._BenchmarkResponseTracker(runtime, controller)
            runtime.controller = controller
            runtime.response_tracker = tracker

            clock = SystemClock()
            clock.start()
            task_manager = TaskManager()
            task_manager.setup(TaskManagerParams(loop=asyncio.get_running_loop()))
            await tracker.setup(FrameProcessorSetup(clock=clock, task_manager=task_manager))
            await asyncio.sleep(0)

            function_call = FunctionCallFromLLM(
                function_name="move",
                tool_call_id="move-1",
                arguments={"to_sector": 1611},
                context=None,
            )

            controller.register_async_completion(
                tool_call_id="move-1",
                expected_event="movement.complete",
                tool_name="move",
            )

            await tracker.process_frame(
                StartFrame(enable_metrics=True, enable_usage_metrics=True),
                mini_rl_env.FrameDirection.DOWNSTREAM,
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

            runtime.request_stop.assert_not_called()
            self.assertEqual(runtime.turn_logs, [])

            state["sector"] = 1611
            await controller.on_event("movement.complete")

            runtime.request_stop.assert_called_once_with("max_turns_exhausted", wait_for_pending_async=True)
            self.assertEqual(len(runtime.turn_logs), 1)
            self.assertEqual(runtime.turn_logs[0]["state_after"]["sector"], 1611)
            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_response_tracker_logs_turn_progress(self) -> None:
        async def _run() -> None:
            state = {"sector": 3080, "credits": 1000, "warp": 20, "max_warp": 20}
            world = types.SimpleNamespace(
                bad_actions_count=0,
                state_snapshot=lambda: dict(state),
                increment_bad_action=mock.Mock(),
            )
            runtime = types.SimpleNamespace(
                stop_requested=False,
                inference_suppressed=False,
                no_tool_call_count=0,
                last_error_event=None,
                turn_logs=[],
                turn_count=0,
                max_turns=50,
                request_stop=mock.Mock(),
                world=world,
                async_completion_timeout_count=0,
                has_async_dependency_waiters=lambda: False,
                resolve_async_dependency_waiters=mock.Mock(),
                maybe_finalize_deferred_stop=mock.Mock(),
            )
            controller = mini_rl_env._BenchmarkInferenceController(runtime)
            tracker = mini_rl_env._BenchmarkResponseTracker(runtime, controller)
            runtime.controller = controller
            runtime.response_tracker = tracker

            clock = SystemClock()
            clock.start()
            task_manager = TaskManager()
            task_manager.setup(TaskManagerParams(loop=asyncio.get_running_loop()))
            await tracker.setup(FrameProcessorSetup(clock=clock, task_manager=task_manager))
            await asyncio.sleep(0)

            function_call = FunctionCallFromLLM(
                function_name="my_status",
                tool_call_id="status-1",
                arguments={},
                context=None,
            )

            with mock.patch.object(mini_rl_env.logger, "info") as info_mock:
                await tracker.process_frame(
                    StartFrame(enable_metrics=True, enable_usage_metrics=True),
                    mini_rl_env.FrameDirection.DOWNSTREAM,
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
                        function_name="my_status",
                        tool_call_id="status-1",
                        arguments={},
                        result={"status": "success"},
                    ),
                    mini_rl_env.FrameDirection.DOWNSTREAM,
                )

            log_messages = [call.args[0] for call in info_mock.call_args_list]
            self.assertTrue(any("LLM_RESPONSE_START" in message for message in log_messages))
            self.assertTrue(any("TURN_TOOL_CALLS" in message for message in log_messages))
            self.assertTrue(any("TURN_COMPLETE" in message for message in log_messages))
            await tracker.cleanup()
            controller.close()
            await asyncio.sleep(0)

        asyncio.run(_run())

    def test_apply_benchmark_thinking_mode_prefers_exact_budget_on_vllm(self) -> None:
        llm_service = types.SimpleNamespace(_settings={})

        policy = mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=llm_service,
            provider=mini_rl_env.LLMProvider.OPENAI,
            model="demo-vllm",
            thinking="low",
            thinking_budget=1536,
            openai_base_url="http://localhost:8000",
        )

        extra = llm_service._settings["extra"]
        self.assertEqual(extra["extra_body"]["vllm_xargs"]["thinking_budget"], 1536)
        self.assertEqual(policy, "openai-compatible:vllm thinking_budget=1536")

    def test_apply_benchmark_thinking_mode_disables_adaptive_claude_when_none(self) -> None:
        llm_service = types.SimpleNamespace(_settings={})

        policy = mini_rl_env._apply_benchmark_thinking_mode(
            llm_service=llm_service,
            provider=mini_rl_env.LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            thinking="none",
            thinking_budget=None,
            openai_base_url=None,
        )

        self.assertEqual(policy, "anthropic:adaptive disabled")
        self.assertEqual(llm_service._settings["extra"], {})

    def test_validate_generation_controls_rejects_max_tokens_for_non_openai(self) -> None:
        parser = argparse.ArgumentParser()
        args = types.SimpleNamespace(
            provider="google",
            model="gemini-2.5-flash",
            openai_base_url=None,
            thinking="medium",
            thinking_budget=None,
            max_tokens=1024,
        )

        with self.assertRaises(SystemExit):
            mini_rl_env._validate_generation_controls(args, parser)

    def test_later_batched_call_waits_for_async_completion(self) -> None:
        async def _run() -> None:
            async def result_callback(payload: dict[str, object], properties=None) -> None:
                payloads.append(payload)

            payloads: list[dict[str, object]] = []
            world = types.SimpleNamespace(
                increment_bad_action=mock.Mock(),
                execute_tool=mock.Mock(
                    return_value=synthetic_world.ToolExecution(
                        payload={"status": "success"},
                        events=[],
                        ok=True,
                    )
                ),
                _error=mock.Mock(),
            )

            runtime = mini_rl_env._BenchmarkRuntime.__new__(mini_rl_env._BenchmarkRuntime)
            runtime.stop_requested = False
            runtime.inference_suppressed = False
            runtime.finished_called = False
            runtime.finished_message = None
            runtime.terminal_reason = "max_turns_exhausted"
            runtime._deferred_stop_reason = None
            runtime.done_event = asyncio.Event()
            runtime.pipeline_task = None
            runtime.world = world
            runtime.last_error_event = None
            runtime.post_finished_call_count = 0
            runtime._skip_context_events = {}
            runtime._event_tasks = set()
            runtime._async_dependency_waiters = []
            runtime.async_completion_timeout_count = 0
            runtime.controller = mini_rl_env._BenchmarkInferenceController(runtime)
            runtime.response_tracker = types.SimpleNamespace(
                finalize_pending_response=mock.AsyncMock(),
            )

            timeout_handle = mock.Mock()
            runtime.controller._pending_async = {
                "move-1": {
                    "expected_event": "movement.complete",
                    "timeout_handle": timeout_handle,
                }
            }

            params = types.SimpleNamespace(
                function_name="recharge_warp_power",
                arguments={},
                tool_call_id="recharge-1",
                result_callback=result_callback,
            )

            task = asyncio.create_task(runtime.handle_function_call(params))
            await asyncio.sleep(0)

            world.execute_tool.assert_not_called()
            self.assertEqual(payloads, [])

            await runtime.controller.on_event("movement.complete")
            await task

            world.execute_tool.assert_called_once_with("recharge_warp_power", {})
            self.assertEqual(payloads, [{"status": "Executed."}])
            timeout_handle.cancel.assert_called_once_with()
            runtime.response_tracker.finalize_pending_response.assert_awaited_once()
            runtime.controller.close()

        asyncio.run(_run())

    def test_build_summary_uses_event_history_for_async_recharge_and_sector_only_report(self) -> None:
        runtime = mini_rl_env._BenchmarkRuntime.__new__(mini_rl_env._BenchmarkRuntime)
        runtime.args = types.SimpleNamespace(
            provider="openai",
            model="dummy",
            thinking="none",
            thinking_budget=None,
            max_tokens=None,
        )
        runtime.world = types.SimpleNamespace(
            state=types.SimpleNamespace(sector=3080, credits=16684),
            bad_actions_count=0,
            event_history=[
                {"event_name": "movement.complete", "source_tool": "move", "sector": 1611},
                {
                    "event_name": "warp.purchase",
                    "source_tool": "recharge_warp_power",
                    "sector": 1611,
                    "event_payload": {
                        "units": 33,
                        "total_cost": 66,
                        "new_warp_power": 500,
                        "warp_power_capacity": 500,
                    },
                },
            ],
        )
        runtime.started_monotonic = time.perf_counter() - 0.01
        runtime.initial_state_snapshot = {"sector": 3080}
        runtime.turn_logs = []
        runtime.finished_called = True
        runtime.finished_message = (
            "Used sector 1611, recharged 33 units for 66 credits, "
            "traded at 3 ports, total profit 120 credits."
        )
        runtime.no_tool_call_count = 0
        runtime.post_finished_call_count = 0
        runtime.async_completion_timeout_count = 0
        runtime.terminal_reason = "finished_tool"

        summary = mini_rl_env._BenchmarkRuntime.build_summary(runtime)

        self.assertTrue(summary["coherent_report"])
        self.assertTrue(summary["reached_mega_anytime"])
        self.assertTrue(summary["recharge_to_full_at_mega"])
        self.assertEqual(summary["recharge_units_total"], 33)
        self.assertEqual(summary["recharge_cost_total"], 66)
        self.assertTrue(summary["success"])


class LeaderboardRegressionTests(unittest.TestCase):
    def test_resolve_leaderboard_prompt_id_requires_explicit_scope_for_hash_only_runs(self) -> None:
        payload = {
            "schema_version": "mini_rl_run.v3",
            "summary": {"model": "demo"},
            "config": {},
            "turns": [],
            "metadata": {"task_prompt_hash": "prompt-a"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            run_path = Path(tmpdir) / "run.json"
            run_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Pass --leaderboard-prompt-id explicitly"):
                build_primary_leaderboard._resolve_leaderboard_prompt_id(
                    [run_path],
                    explicit_prompt_id=None,
                )

            prompt_id, prompt_hash = build_primary_leaderboard._resolve_leaderboard_prompt_id(
                [run_path],
                explicit_prompt_id="natural",
            )

        self.assertEqual(prompt_id, "natural")
        self.assertEqual(prompt_hash, "prompt-a")

    def test_resolve_leaderboard_prompt_id_rejects_mixed_prompt_hashes(self) -> None:
        payload_a = {
            "schema_version": "mini_rl_run.v3",
            "summary": {"model": "demo"},
            "config": {},
            "turns": [],
            "metadata": {"task_prompt_hash": "prompt-a"},
        }
        payload_b = {
            "schema_version": "mini_rl_run.v3",
            "summary": {"model": "demo"},
            "config": {},
            "turns": [],
            "metadata": {"task_prompt_hash": "prompt-b"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            run_a = Path(tmpdir) / "a.json"
            run_b = Path(tmpdir) / "b.json"
            run_a.write_text(json.dumps(payload_a), encoding="utf-8")
            run_b.write_text(json.dumps(payload_b), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Mixed prompt hashes"):
                build_primary_leaderboard._resolve_leaderboard_prompt_id(
                    [run_a, run_b],
                    explicit_prompt_id="natural",
                )

    def test_resolve_leaderboard_prompt_id_rejects_conflicting_explicit_variant(self) -> None:
        payload = {
            "schema_version": "mini_rl_run.v3",
            "summary": {"model": "demo"},
            "config": {},
            "turns": [],
            "metadata": {
                "task_prompt_hash": "prompt-a",
                "task_variant": "literal",
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            run_path = Path(tmpdir) / "run.json"
            run_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "does not match metadata.task_variant"):
                build_primary_leaderboard._resolve_leaderboard_prompt_id(
                    [run_path],
                    explicit_prompt_id="natural",
                )

    def test_default_output_path_uses_canonical_built_in_files(self) -> None:
        natural_path = build_primary_leaderboard._default_output_path("natural", "hash-a")
        literal_path = build_primary_leaderboard._default_output_path("literal", "hash-b")
        custom_path = build_primary_leaderboard._default_output_path("custom:abcdef1234567890", "abcdef1234567890")

        self.assertEqual(natural_path, PORT_TO_PORT_DIR / "leaderboards" / "leaderboard-natural.md")
        self.assertEqual(literal_path, PORT_TO_PORT_DIR / "leaderboards" / "leaderboard-literal.md")
        self.assertEqual(custom_path, PORT_TO_PORT_DIR / "leaderboards" / "leaderboard-custom-abcdef1234567890.md")

    def test_build_rows_aggregates_primary_and_task_complete(self) -> None:
        payload = {
            "schema_version": "mini_rl_run.v3",
            "summary": {
                "model": "demo",
                "thinking": "medium",
                "max_tokens": None,
                "elapsed_ms": 1000,
                "turns_executed": 2,
            },
            "config": {"openai_base_url": "http://host:8000"},
            "turns": [{"decision_ms": 100.0}, {"decision_ms": 200.0}],
            "metadata": {"task_prompt_hash": "prompt-a"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            run_path = Path(tmpdir) / "run.json"
            run_path.write_text(json.dumps(payload), encoding="utf-8")

            rows, rubric_versions = build_primary_leaderboard._build_rows(
                [run_path],
                enriched_by_file={
                    str(run_path.resolve()): {
                        "file": str(run_path),
                        "score_rubric_version": "port_to_port_primary_v1",
                        "primary_score_100": 87,
                        "task_complete": True,
                        "trade_quality_score": 14,
                        "path_efficiency_score": 13,
                        "tool_discipline_score": 15,
                        "report_quality_score": 12,
                    }
                },
                model_name_aliases={},
            )

        self.assertEqual(rubric_versions, {"port_to_port_primary_v1"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["primary_score_100_median"], 87.0)
        self.assertEqual(rows[0]["task_complete_rate"], 100.0)
        self.assertEqual(rows[0]["turn_p50_ms"], 150.0)
        self.assertEqual(rows[0]["turn_p90_ms"], 190.0)
        self.assertEqual(rows[0]["total_time_p50_s"], 1.0)

    def test_aliases_do_not_merge_distinct_raw_models(self) -> None:
        payload_a = {
            "schema_version": "mini_rl_run.v3",
            "summary": {
                "model": "raw-a",
                "thinking": "medium",
                "thinking_budget": 1536,
                "max_tokens": 4608,
                "elapsed_ms": 1000,
                "turns_executed": 1,
            },
            "config": {"openai_base_url": "http://one.example/v1"},
            "turns": [],
            "metadata": {"task_prompt_hash": "prompt-a"},
        }
        payload_b = {
            "schema_version": "mini_rl_run.v3",
            "summary": {
                "model": "raw-b",
                "thinking": "medium",
                "thinking_budget": 1536,
                "max_tokens": 4608,
                "elapsed_ms": 1000,
                "turns_executed": 1,
            },
            "config": {"openai_base_url": "http://two.example/v1"},
            "turns": [],
            "metadata": {"task_prompt_hash": "prompt-b"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            run_a = Path(tmpdir) / "a.json"
            run_b = Path(tmpdir) / "b.json"
            run_a.write_text(json.dumps(payload_a), encoding="utf-8")
            run_b.write_text(json.dumps(payload_b), encoding="utf-8")

            rows, _rubric_versions = build_primary_leaderboard._build_rows(
                [run_a, run_b],
                enriched_by_file={
                    str(run_a.resolve()): {
                        "file": str(run_a),
                        "score_rubric_version": "port_to_port_primary_v1",
                        "primary_score_100": 80,
                        "task_complete": True,
                        "trade_quality_score": 12,
                        "path_efficiency_score": 13,
                        "tool_discipline_score": 14,
                        "report_quality_score": 11,
                    },
                    str(run_b.resolve()): {
                        "file": str(run_b),
                        "score_rubric_version": "port_to_port_primary_v1",
                        "primary_score_100": 82,
                        "task_complete": True,
                        "trade_quality_score": 12,
                        "path_efficiency_score": 13,
                        "tool_discipline_score": 14,
                        "report_quality_score": 11,
                    },
                },
                model_name_aliases={"raw-a": "Alias", "raw-b": "Alias"},
            )

        self.assertEqual(len(rows), 2)
        labels = {row["model_label"] for row in rows}
        self.assertIn("Alias [raw-a] (th=medium, tb=1536, mt=4608, base=one.example)", labels)
        self.assertIn("Alias [raw-b] (th=medium, tb=1536, mt=4608, base=two.example)", labels)

    def test_equivalent_openai_base_urls_merge_into_one_leaderboard_row(self) -> None:
        payload_a = {
            "schema_version": "mini_rl_run.v3",
            "summary": {
                "model": "demo",
                "thinking": "medium",
                "elapsed_ms": 1000,
                "turns_executed": 1,
            },
            "config": {"openai_base_url": "http://host:8000"},
            "turns": [],
            "metadata": {"task_prompt_hash": "prompt-a"},
        }
        payload_b = {
            "schema_version": "mini_rl_run.v3",
            "summary": {
                "model": "demo",
                "thinking": "medium",
                "elapsed_ms": 1200,
                "turns_executed": 2,
            },
            "config": {"openai_base_url": "http://host:8000/chat/completions"},
            "turns": [],
            "metadata": {"task_prompt_hash": "prompt-a"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            run_a = Path(tmpdir) / "a.json"
            run_b = Path(tmpdir) / "b.json"
            run_a.write_text(json.dumps(payload_a), encoding="utf-8")
            run_b.write_text(json.dumps(payload_b), encoding="utf-8")

            rows, _rubric_versions = build_primary_leaderboard._build_rows(
                [run_a, run_b],
                enriched_by_file={
                    str(run_a.resolve()): {
                        "file": str(run_a),
                        "score_rubric_version": "port_to_port_primary_v1",
                        "primary_score_100": 80,
                        "task_complete": True,
                        "trade_quality_score": 12,
                        "path_efficiency_score": 13,
                        "tool_discipline_score": 14,
                        "report_quality_score": 11,
                    },
                    str(run_b.resolve()): {
                        "file": str(run_b),
                        "score_rubric_version": "port_to_port_primary_v1",
                        "primary_score_100": 82,
                        "task_complete": False,
                        "trade_quality_score": 11,
                        "path_efficiency_score": 12,
                        "tool_discipline_score": 14,
                        "report_quality_score": 10,
                    },
                },
                model_name_aliases={},
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["n"], 2)
        self.assertEqual(rows[0]["openai_base_url"], "http://host:8000/v1")


class ScriptRegressionTests(unittest.TestCase):
    def test_run_model_matrix_fails_fast_without_judge_key(self) -> None:
        script_path = PORT_TO_PORT_DIR / "run_model_matrix.sh"
        runs_dir = PORT_TO_PORT_DIR / "runs"
        before = {p.resolve() for p in runs_dir.glob("matrix-*")}

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_uv = Path(tmpdir) / "fake_uv"
            fake_uv_marker = Path(tmpdir) / "fake_uv.invoked"
            fake_uv.write_text(
                "#!/usr/bin/env bash\n"
                f"echo invoked > {json.dumps(str(fake_uv_marker))}\n"
                "exit 99\n",
                encoding="utf-8",
            )
            fake_uv.chmod(0o755)

            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            env["UV_BIN"] = str(fake_uv)

            completed = subprocess.run(
                ["bash", str(script_path)],
                cwd=PORT_TO_PORT_DIR,
                env=env,
                capture_output=True,
                text=True,
            )

            after = {p.resolve() for p in runs_dir.glob("matrix-*")}
            new_dirs = sorted(after - before)
            try:
                self.assertEqual(completed.returncode, 2)
                self.assertFalse(fake_uv_marker.exists())
                self.assertEqual(len(new_dirs), 1)

                run_dir = new_dirs[0]
                done_path = run_dir / "DONE"
                self.assertTrue(done_path.exists())
                self.assertEqual(done_path.read_text(encoding="utf-8").splitlines(), ["DONE", "PRECHECK_FAILED"])
            finally:
                for run_dir in new_dirs:
                    if run_dir.exists():
                        shutil.rmtree(run_dir)
                latest_run = runs_dir / "LATEST_MATRIX_RUN"
                if latest_run.exists():
                    latest_text = latest_run.read_text(encoding="utf-8").strip()
                    if any(str(run_dir) == latest_text for run_dir in new_dirs):
                        latest_run.unlink()


class ToolCatalogRegressionTests(unittest.TestCase):
    def test_wait_in_idle_state_is_async_completion_tool(self) -> None:
        self.assertEqual(
            tool_catalog.BENCHMARK_ASYNC_TOOL_COMPLETIONS["wait_in_idle_state"],
            "idle.complete",
        )


class SyntheticWorldRegressionTests(unittest.TestCase):
    def test_local_map_region_defaults_to_three_hops(self) -> None:
        world = synthetic_world.SyntheticWorld()

        result = world._handle_local_map_region({})

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["center_sector"], 3080)
        self.assertEqual(result.payload["max_hops"], 3)
        self.assertEqual(result.payload["total_sectors"], 6)

    def test_plot_course_respects_from_sector(self) -> None:
        world = synthetic_world.SyntheticWorld()

        result = world._handle_plot_course({"from_sector": 1928, "to_sector": 1611})

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["from_sector"], 1928)
        self.assertEqual(result.payload["to_sector"], 1611)
        self.assertEqual(result.payload["distance"], 1)
        self.assertEqual(result.payload["path"], [1928, 1611])

    def test_list_known_ports_applies_filters(self) -> None:
        world = synthetic_world.SyntheticWorld()

        result = world._handle_list_known_ports(
            {"from_sector": 3080, "max_hops": 1, "port_type": "BBS", "mega": False}
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["from_sector"], 3080)
        self.assertEqual(result.payload["max_hops"], 1)
        self.assertEqual(result.payload["port_type"], "BBS")
        self.assertFalse(result.payload["mega"])
        self.assertEqual(result.payload["count"], 0)
        self.assertEqual(result.payload["ports"], [])

    def test_port_markets_are_isolated_per_instance(self) -> None:
        world_a = synthetic_world.SyntheticWorld()
        world_b = synthetic_world.SyntheticWorld()

        world_a.ports[4874].stock["quantum_foam"] -= 5

        self.assertEqual(world_a.ports[4874].stock["quantum_foam"], 1195)
        self.assertEqual(world_b.ports[4874].stock["quantum_foam"], 1200)
        self.assertNotEqual(
            world_a.ports[4874].stock["quantum_foam"],
            world_b.ports[4874].stock["quantum_foam"],
        )

    def test_event_query_filters_by_time_window(self) -> None:
        world = synthetic_world.SyntheticWorld()
        world.event_history = [
            {
                "timestamp": "2026-03-06T00:00:00+00:00",
                "event_name": "task.start",
                "response_data": {"idx": 0},
                "event_payload": {"idx": 0},
                "source_tool": "my_status",
                "sector": 3080,
                "task_id": "task-a",
            },
            {
                "timestamp": "2026-03-06T01:00:00+00:00",
                "event_name": "movement.complete",
                "response_data": {"idx": 1},
                "event_payload": {"idx": 1},
                "source_tool": "move",
                "sector": 2266,
                "task_id": "task-a",
            },
            {
                "timestamp": "2026-03-06T02:00:00+00:00",
                "event_name": "trade.executed",
                "response_data": {"idx": 2},
                "event_payload": {"idx": 2},
                "source_tool": "trade",
                "sector": 4874,
                "task_id": "task-a",
            },
        ]

        result = world._handle_event_query(
            {
                "start": "2026-03-06T00:30:00Z",
                "end": "2026-03-06T02:00:00Z",
            }
        )

        self.assertTrue(result.ok)
        payload = result.events[0].payload
        self.assertEqual(payload["count"], 1)
        self.assertEqual([event["event"] for event in payload["events"]], ["movement.complete"])
        self.assertEqual(payload["events"][0]["timestamp"], "2026-03-06T01:00:00+00:00")

    def test_event_query_honors_max_rows_alias(self) -> None:
        world = synthetic_world.SyntheticWorld()
        world.event_history = [
            {
                "timestamp": f"2026-03-06T00:{minute:02d}:00+00:00",
                "event_name": f"event-{minute}",
                "response_data": {"idx": minute},
                "event_payload": {"idx": minute},
                "source_tool": "my_status",
                "sector": 3080,
                "task_id": "task-a",
            }
            for minute in range(25)
        ]

        result = world._handle_event_query(
            {
                "start": "2026-03-06T00:00:00Z",
                "end": "2026-03-06T01:00:00Z",
                "max_rows": 7,
            }
        )

        self.assertTrue(result.ok)
        payload = result.events[0].payload
        self.assertEqual(payload["count"], 7)
        self.assertTrue(payload["has_more"])
        self.assertEqual(payload["next_cursor"], 7)
        self.assertEqual(payload["events"][0]["event"], "event-0")
        self.assertEqual(payload["events"][-1]["event"], "event-6")

    def test_purchase_fighters_requires_mega_port(self) -> None:
        world = synthetic_world.SyntheticWorld()

        result = world._handle_purchase_fighters({"units": 1})

        self.assertFalse(result.ok)
        self.assertIn("mega-port", result.payload["error"])

    def test_purchase_fighters_uses_mega_port_pricing(self) -> None:
        world = synthetic_world.SyntheticWorld()
        world.state.sector = 1611
        world.state.credits = 200
        world.state.fighters = 300

        result = world._handle_purchase_fighters({"units": 3})

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["cost"], 150)
        self.assertEqual(len(result.events), 1)

        event = result.events[0]
        assert event.mutation is not None
        event.mutation()
        payload = event.payload_factory() if event.payload_factory is not None else {}

        self.assertEqual(world.state.credits, 50)
        self.assertEqual(world.state.fighters, 303)
        self.assertEqual(payload["total_cost"], 150)
        self.assertEqual(payload["fighters_after"], 303)
        self.assertEqual(payload["ship_credits_after"], 50)


class LlmFactoryRegressionTests(unittest.TestCase):
    def test_openai_thinking_budget_preserves_existing_extra_body(self) -> None:
        fake_openai_module = types.ModuleType("pipecat.services.openai.llm")

        class FakeOpenAILLMService:
            class InputParams:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            def __init__(self, **kwargs):
                self.kwargs = kwargs

        fake_openai_module.OpenAILLMService = FakeOpenAILLMService

        openai_params = {
            "temperature": 0.2,
            "extra": {
                "request_label": "keep-me",
                "extra_body": {
                    "top_k": 40,
                    "vllm_xargs": {"other_flag": 7},
                },
            },
        }
        thinking = llm_factory.UnifiedThinkingConfig(
            enabled=True,
            budget_tokens=512,
            include_thoughts=True,
        )

        with mock.patch.dict(sys.modules, {"pipecat.services.openai.llm": fake_openai_module}):
            service = llm_factory._create_openai_service(
                api_key="dummy",
                model="qwen3.5-35b",
                thinking=thinking,
                max_tokens=None,
                function_call_timeout_secs=None,
                openai_base_url="http://localhost:8000",
                openai_params=openai_params,
            )

        params = service.kwargs["params"]
        extra = params.kwargs["extra"]

        self.assertEqual(service.kwargs["base_url"], "http://localhost:8000/v1")
        self.assertEqual(extra["request_label"], "keep-me")
        self.assertEqual(extra["extra_body"]["top_k"], 40)
        self.assertEqual(extra["extra_body"]["vllm_xargs"]["other_flag"], 7)
        self.assertEqual(extra["extra_body"]["vllm_xargs"]["thinking_budget"], 512)

    def test_openai_max_tokens_flag_overrides_raw_openai_params(self) -> None:
        fake_openai_module = types.ModuleType("pipecat.services.openai.llm")

        class FakeOpenAILLMService:
            class InputParams:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            def __init__(self, **kwargs):
                self.kwargs = kwargs

        fake_openai_module.OpenAILLMService = FakeOpenAILLMService

        with mock.patch.dict(sys.modules, {"pipecat.services.openai.llm": fake_openai_module}):
            service = llm_factory._create_openai_service(
                api_key="dummy",
                model="gpt-4.1",
                thinking=None,
                max_tokens=2048,
                function_call_timeout_secs=None,
                openai_base_url=None,
                openai_params={"max_tokens": 128, "max_completion_tokens": 256, "temperature": 0.2},
            )

        params = service.kwargs["params"]
        self.assertEqual(params.kwargs["max_tokens"], 2048)
        self.assertNotIn("max_completion_tokens", params.kwargs)
        self.assertEqual(params.kwargs["temperature"], 0.2)


if __name__ == "__main__":
    unittest.main()
