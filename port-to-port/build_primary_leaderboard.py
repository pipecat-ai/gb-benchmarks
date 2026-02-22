#!/usr/bin/env python3
"""Build the primary 9x leaderboard table with custom columns.

Inputs:
- Raw run JSONs (for timing/turn/error metrics)
- Enriched eval JSONL (for LLM-judged strict_success)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

KNOWN_ACTIONS = {
    "list_known_ports",
    "plot_course",
    "move",
    "trade",
    "my_status",
    "local_map_region",
    "wait_in_idle_state",
    "load_game_info",
    "dump_cargo",
    "salvage_collect",
    "finished",
}


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return 100.0 * (numerator / denominator)


def _load_strict_success_map(enriched_jsonl: Path) -> dict[str, bool]:
    strict_by_file: dict[str, bool] = {}
    with enriched_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            strict_by_file[str(Path(row["file"]).resolve())] = bool(row.get("strict_success"))
    return strict_by_file


def _build_rows(run_files: list[Path], strict_by_file: dict[str, bool]) -> list[dict[str, Any]]:
    by_group: dict[tuple[str, Any, Any, Any], dict[str, Any]] = {}

    for file_path in sorted(run_files):
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        summary = payload.get("summary") or {}
        config = payload.get("config") or {}
        turns = payload.get("turns") or []
        model = summary.get("model") or "UNKNOWN"
        thinking_budget = summary.get("thinking_budget")
        max_tokens = summary.get("max_tokens")
        openai_base_url = config.get("openai_base_url") or summary.get("openai_base_url")
        group_key = (model, thinking_budget, max_tokens, openai_base_url)

        rec = by_group.setdefault(
            group_key,
            {
                "model": model,
                "thinking_budget": thinking_budget,
                "max_tokens": max_tokens,
                "openai_base_url": openai_base_url,
                "n": 0,
                "strict_success_count": 0,
                "partial_success_count": 0,
                "elapsed_s": [],
                "turn_counts": [],
                "turn_decisions_ms": [],
                "total_turns": 0,
                "bad_move": 0,
                "bad_trade": 0,
                "unknown_action": 0,
                "parse_format": 0,
                "inference_failure": 0,
            },
        )

        rec["n"] += 1
        if strict_by_file.get(str(file_path.resolve()), False):
            rec["strict_success_count"] += 1
        if bool(summary.get("final_sector_is_mega")):
            rec["partial_success_count"] += 1

        elapsed_ms = summary.get("elapsed_ms")
        if isinstance(elapsed_ms, (int, float)):
            rec["elapsed_s"].append(float(elapsed_ms) / 1000.0)

        turns_executed = summary.get("turns_executed")
        rec["turn_counts"].append(turns_executed if isinstance(turns_executed, int) else len(turns))

        for turn in turns:
            rec["total_turns"] += 1

            decision_ms = turn.get("decision_ms")
            if isinstance(decision_ms, (int, float)):
                rec["turn_decisions_ms"].append(float(decision_ms))

            parse_error = turn.get("parse_error")
            if parse_error is not None:
                if isinstance(parse_error, str) and parse_error == "inference failure":
                    rec["inference_failure"] += 1
                else:
                    rec["parse_format"] += 1
                continue

            bad_inc = turn.get("bad_action_increment")
            if isinstance(bad_inc, int):
                bad = bad_inc
            else:
                try:
                    bad = int(bad_inc or 0)
                except Exception:
                    bad = 0
            if bad <= 0:
                continue

            action = turn.get("action")
            if action == "move":
                rec["bad_move"] += 1
            elif action == "trade":
                rec["bad_trade"] += 1
            elif isinstance(action, str) and action not in KNOWN_ACTIONS:
                rec["unknown_action"] += 1

    rows: list[dict[str, Any]] = []
    for rec in by_group.values():
        n = rec["n"]
        total_turns = rec["total_turns"]
        strict_rate = _pct(rec["strict_success_count"], n)
        avg_time_s = mean(rec["elapsed_s"]) if rec["elapsed_s"] else 0.0
        avg_turns = mean(rec["turn_counts"]) if rec["turn_counts"] else 0.0
        rows.append(
            {
                "model": rec["model"],
                "thinking_budget": rec["thinking_budget"],
                "max_tokens": rec["max_tokens"],
                "openai_base_url": rec["openai_base_url"],
                "n": n,
                "strict_success_count": rec["strict_success_count"],
                "strict_success_rate": strict_rate,
                "partial_success_count": rec["partial_success_count"],
                "partial_success_rate": _pct(rec["partial_success_count"], n),
                "avg_time_s": avg_time_s,
                "avg_turns": avg_turns,
                "turn_p50_ms": _percentile(rec["turn_decisions_ms"], 0.50),
                "turn_p95_ms": _percentile(rec["turn_decisions_ms"], 0.95),
                "bad_move_rate": _pct(rec["bad_move"], total_turns),
                "bad_trade_rate": _pct(rec["bad_trade"], total_turns),
                "unknown_action_rate": _pct(rec["unknown_action"], total_turns),
                "parse_format_rate": _pct(rec["parse_format"], total_turns),
                "inference_failure_rate": _pct(rec["inference_failure"], total_turns),
            }
        )

    model_row_counts: dict[str, int] = {}
    for row in rows:
        model_row_counts[row["model"]] = model_row_counts.get(row["model"], 0) + 1
    for row in rows:
        if model_row_counts[row["model"]] > 1:
            row["model_label"] = f"{row['model']} (tb={row['thinking_budget']})"
        else:
            row["model_label"] = row["model"]

    rows.sort(key=lambda row: (-row["strict_success_rate"], row["avg_time_s"], row["model_label"]))
    return rows


def _write_table(
    out_path: Path,
    rows: list[dict[str, Any]],
    runs_glob: str,
    enriched_jsonl: Path,
) -> None:
    lines: list[str] = []
    lines.append("# Primary Leaderboard (9x Matrix, All Runs, Revised Columns)")
    lines.append("")
    lines.append(f"- Source runs: `{runs_glob}`")
    lines.append(f"- Strict success source: LLM-judged eval `{enriched_jsonl}`")
    lines.append("- Partial success definition: final sector is target mega-port (`summary.final_sector_is_mega == true`)")
    lines.append("- All error rates below use denominator = total turns for that model")
    lines.append("- Sort: strict success rate desc, avg time asc")
    lines.append("")
    lines.append(
        "| Model | N | Strict Success | Partial Success | Avg Time (s) | Avg Turns | "
        "Turn P50 (ms) | Turn P95 (ms) | Bad Move Rate | Bad Trade Rate | "
        "Unknown Tool/Action Rate | Parse/Format Error Rate | Inference Failure Rate |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for row in rows:
        lines.append(
            f"| {row['model_label']} | {row['n']} | "
            f"{row['strict_success_count']}/{row['n']} ({row['strict_success_rate']:.1f}%) | "
            f"{row['partial_success_count']}/{row['n']} ({row['partial_success_rate']:.1f}%) | "
            f"{row['avg_time_s']:.2f} | {row['avg_turns']:.2f} | "
            f"{(row['turn_p50_ms'] or 0.0):.1f} | {(row['turn_p95_ms'] or 0.0):.1f} | "
            f"{row['bad_move_rate']:.2f}% | {row['bad_trade_rate']:.2f}% | "
            f"{row['unknown_action_rate']:.2f}% | {row['parse_format_rate']:.2f}% | "
            f"{row['inference_failure_rate']:.2f}% |"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build primary leaderboard table from benchmark runs.")
    parser.add_argument("--runs-glob", required=True, help="Glob for run JSON files.")
    parser.add_argument("--enriched-jsonl", required=True, help="Path to evaluate_runs.py enriched JSONL.")
    parser.add_argument("--out", required=True, help="Output markdown table path.")
    args = parser.parse_args()

    run_files = [Path(p) for p in sorted(Path().glob(args.runs_glob))]
    # Path().glob does not support absolute patterns.
    if not run_files:
        from glob import glob

        run_files = [Path(p) for p in sorted(glob(args.runs_glob))]
    if not run_files:
        raise SystemExit(f"No run JSON files matched: {args.runs_glob}")

    enriched_jsonl = Path(args.enriched_jsonl)
    if not enriched_jsonl.exists():
        raise SystemExit(f"Missing enriched JSONL: {enriched_jsonl}")

    strict_by_file = _load_strict_success_map(enriched_jsonl)
    rows = _build_rows(run_files, strict_by_file)
    _write_table(Path(args.out), rows, args.runs_glob, enriched_jsonl)
    print(Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
