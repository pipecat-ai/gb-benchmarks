#!/usr/bin/env python3
"""Build the primary 9x leaderboard table with custom columns.

Inputs:
- Raw run JSONs (for timing/turn/error metrics)
- Enriched eval JSONL (for LLM-judged strict_success)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any

RUN_SCHEMA_VERSION = "mini_rl_run.v3"

KNOWN_ACTIONS = {
    "my_status",
    "plot_course",
    "local_map_region",
    "list_known_ports",
    "move",
    "trade",
    "salvage_collect",
    "send_message",
    "recharge_warp_power",
    "transfer_warp_power",
    "place_fighters",
    "collect_fighters",
    "event_query",
    "purchase_fighters",
    "create_corporation",
    "join_corporation",
    "leave_corporation",
    "kick_corporation_member",
    "corporation_info",
    "purchase_ship",
    "rename_ship",
    "bank_deposit",
    "bank_withdraw",
    "transfer_credits",
    "dump_cargo",
    "combat_initiate",
    "combat_action",
    "load_game_info",
    "wait_in_idle_state",
    "finished",
}

ERROR_RESULT_STATUSES = {"error", "post_finished_call_rejected"}


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


def _normalize_openai_base_url(base_url: Any) -> str | None:
    if not isinstance(base_url, str):
        return None
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        return None
    if normalized.endswith("/chat/completions"):
        normalized = normalized[: -len("/chat/completions")]
    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return normalized


def _display_base_url(base_url: Any) -> str | None:
    normalized = _normalize_openai_base_url(base_url)
    if normalized is None:
        return None
    text = normalized
    if not text:
        return None
    text = re.sub(r"^https?://", "", text)
    if text.endswith("/v1"):
        text = text[:-3]
    return text or None


def _build_model_label(row: dict[str, Any]) -> str:
    base_label = row["display_model"]
    if row["display_model"] != row["model"]:
        base_label = f"{base_label} [{row['model']}]"

    details: list[str] = []
    thinking = row.get("thinking")
    if thinking not in {None, ""}:
        details.append(f"th={thinking}")

    thinking_budget = row.get("thinking_budget")
    if thinking_budget is not None:
        details.append(f"tb={thinking_budget}")

    max_tokens = row.get("max_tokens")
    if max_tokens is not None:
        details.append(f"mt={max_tokens}")

    prompt_label = row.get("prompt_label") or ""
    if prompt_label:
        details.append(prompt_label)

    base_url = _display_base_url(row.get("openai_base_url"))
    if base_url:
        details.append(f"base={base_url}")

    if not details:
        return base_label
    return f"{base_label} ({', '.join(details)})"


def _is_v3_partial_success(summary: dict[str, Any]) -> bool:
    return bool(
        summary.get("finished_called")
        and summary.get("final_sector_matches_start")
        and summary.get("reached_mega_anytime")
        and summary.get("recharge_to_full_at_mega")
    )


def _load_strict_success_map(enriched_jsonl: Path) -> dict[str, bool]:
    strict_by_file: dict[str, bool] = {}
    with enriched_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            strict_by_file[str(Path(row["file"]).resolve())] = bool(row.get("strict_success"))
    return strict_by_file


def _load_optional_json_map(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return {str(key): str(value) for key, value in payload.items()}


def _build_rows(
    run_files: list[Path],
    strict_by_file: dict[str, bool],
    *,
    model_name_aliases: dict[str, str],
    prompt_hash_labels: dict[str, str],
) -> list[dict[str, Any]]:
    by_group: dict[tuple[str, Any, Any, Any, Any, Any], dict[str, Any]] = {}

    for file_path in sorted(run_files):
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != RUN_SCHEMA_VERSION:
            raise ValueError(
                f"{file_path}: unsupported schema_version={payload.get('schema_version')} "
                f"(expected {RUN_SCHEMA_VERSION})"
            )
        summary = payload.get("summary") or {}
        config = payload.get("config") or {}
        turns = payload.get("turns") or []
        metadata = payload.get("metadata") or {}
        model = summary.get("model") or "UNKNOWN"
        thinking = summary.get("thinking", summary.get("thinking_budget"))
        thinking_budget = summary.get("thinking_budget", config.get("thinking_budget"))
        max_tokens = summary.get("max_tokens")
        openai_base_url = _normalize_openai_base_url(
            config.get("openai_base_url") or summary.get("openai_base_url")
        )
        prompt_hash = metadata.get("task_prompt_hash")
        raw_prompt_hash = str(prompt_hash or "")
        display_model = model_name_aliases.get(model, model)
        prompt_group = prompt_hash_labels.get(raw_prompt_hash, raw_prompt_hash)
        prompt_label = prompt_group if len(prompt_group) < 24 else f"prompt={prompt_group[:8]}"
        group_key = (model, thinking, thinking_budget, max_tokens, openai_base_url, raw_prompt_hash)

        rec = by_group.setdefault(
            group_key,
            {
                "model": model,
                "display_model": display_model,
                "thinking": thinking,
                "thinking_budget": thinking_budget,
                "max_tokens": max_tokens,
                "openai_base_url": openai_base_url,
                "prompt_hash": prompt_hash,
                "prompt_group": prompt_group,
                "prompt_label": prompt_label,
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
                "no_tool_call": 0,
                "inference_failure": 0,
            },
        )

        rec["n"] += 1
        if strict_by_file.get(str(file_path.resolve()), False):
            rec["strict_success_count"] += 1
        if _is_v3_partial_success(summary):
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

            failure_class = str(turn.get("failure_class") or "")
            if failure_class == "inference_failure":
                rec["inference_failure"] += 1
            elif failure_class == "no_tool_call":
                rec["no_tool_call"] += 1

            bad_inc = turn.get("bad_action_increment")
            if isinstance(bad_inc, int):
                bad = bad_inc
            else:
                try:
                    bad = int(bad_inc or 0)
                except Exception:
                    bad = 0
            tool_calls = turn.get("tool_calls")
            if not isinstance(tool_calls, list):
                tool_calls = []

            bad_move_turn = False
            bad_trade_turn = False
            unknown_action_turn = False
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                action = call.get("name")
                result_status = str(call.get("result_status") or "")
                if result_status not in ERROR_RESULT_STATUSES:
                    continue
                if action == "move":
                    bad_move_turn = True
                elif action == "trade":
                    bad_trade_turn = True
                elif isinstance(action, str) and action not in KNOWN_ACTIONS:
                    unknown_action_turn = True

            if bad > 0 and bad_move_turn:
                rec["bad_move"] += 1
            if bad > 0 and bad_trade_turn:
                rec["bad_trade"] += 1
            if bad > 0 and unknown_action_turn:
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
                "display_model": rec["display_model"],
                "thinking": rec["thinking"],
                "thinking_budget": rec["thinking_budget"],
                "max_tokens": rec["max_tokens"],
                "openai_base_url": rec["openai_base_url"],
                "prompt_hash": rec["prompt_hash"],
                "prompt_group": rec["prompt_group"],
                "prompt_label": rec["prompt_label"],
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
                "no_tool_call_rate": _pct(rec["no_tool_call"], total_turns),
                "inference_failure_rate": _pct(rec["inference_failure"], total_turns),
            }
        )

    for row in rows:
        row["model_label"] = _build_model_label(row)

    rows.sort(key=lambda row: (-row["strict_success_rate"], row["avg_time_s"], row["model_label"]))
    return rows


def _write_table(
    out_path: Path,
    rows: list[dict[str, Any]],
    runs_glob: str,
    enriched_jsonl: Path,
) -> None:
    lines: list[str] = []
    lines.append("# Primary Leaderboard (9x Matrix, All Runs, Canonical v3 Columns)")
    lines.append("")
    lines.append(f"- Source runs: `{runs_glob}`")
    lines.append(f"- Strict success source: LLM-judged eval `{enriched_jsonl}`")
    lines.append(
        "- Partial success definition: finished + returned to start + reached mega-port + fully recharged "
        "(`finished_called && final_sector_matches_start && reached_mega_anytime && recharge_to_full_at_mega`)"
    )
    lines.append("- All error rates below use denominator = total turns for that model")
    lines.append("- Sort: strict success rate desc, avg time asc")
    lines.append("")
    lines.append(
        "| Model | N | Strict Success | Partial Success | Avg Time (s) | Avg Turns | "
        "Turn P50 (ms) | Turn P95 (ms) | Bad Move Rate | Bad Trade Rate | "
        "Unknown Tool/Action Rate | No Tool Call Rate | Inference Failure Rate |"
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
            f"{row['unknown_action_rate']:.2f}% | {row['no_tool_call_rate']:.2f}% | "
            f"{row['inference_failure_rate']:.2f}% |"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build primary leaderboard table from benchmark runs.")
    parser.add_argument("--runs-glob", required=True, help="Glob for run JSON files.")
    parser.add_argument("--enriched-jsonl", required=True, help="Path to evaluate_runs.py enriched JSONL.")
    parser.add_argument("--out", required=True, help="Output markdown table path.")
    parser.add_argument(
        "--model-name-aliases-json",
        help="Optional JSON object mapping raw model names to display aliases.",
    )
    parser.add_argument(
        "--prompt-hash-labels-json",
        help="Optional JSON object mapping task prompt hashes to display suffixes (for example \"prompt2\").",
    )
    args = parser.parse_args()

    try:
        run_files = [Path(p) for p in sorted(Path().glob(args.runs_glob))]
    except NotImplementedError:
        run_files = []
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
    rows = _build_rows(
        run_files,
        strict_by_file,
        model_name_aliases=_load_optional_json_map(args.model_name_aliases_json),
        prompt_hash_labels=_load_optional_json_map(args.prompt_hash_labels_json),
    )
    _write_table(Path(args.out), rows, args.runs_glob, enriched_jsonl)
    print(Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
