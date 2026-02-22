#!/usr/bin/env python3
"""Post-process mini-RL benchmark run JSON files.

This evaluator is intentionally where scoring policy lives.
The runner should remain a thin emitter of raw run data.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Optional

MEGA_PORT_SECTOR = 1611

GRAPH: dict[int, list[int]] = {
    0: [4874],
    172: [220],
    200: [2469],
    220: [172],
    916: [3885, 4884],
    1344: [2469, 3900, 4874],
    1487: [1928],
    1611: [1928, 2058],
    1928: [1487, 1611, 4382],
    2058: [1611, 2831],
    2217: [2266],
    2266: [3080, 3313, 3885],
    2469: [200, 1344, 4884],
    2766: [3494],
    2831: [2058, 3494, 4822],
    3080: [2266, 3313],
    3313: [2266, 3080],
    3494: [2766, 2831, 4874],
    3871: [3885],
    3885: [916, 2266, 3871],
    3900: [1344],
    4382: [1928],
    4822: [2831],
    4874: [0, 1344, 3494],
    4884: [916, 2469, 2833],
}

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

PORT_MARKETS: dict[int, dict[str, dict[str, int]]] = {
    3080: {
        "buys": {"quantum_foam": 33, "neuro_symbolics": 52},
        "sells": {"retro_organics": 8},
    },
    1611: {
        "buys": {},
        "sells": {"quantum_foam": 19, "retro_organics": 8, "neuro_symbolics": 30},
    },
    1928: {
        "buys": {"quantum_foam": 32, "retro_organics": 13},
        "sells": {"neuro_symbolics": 30},
    },
    2831: {
        "buys": {"neuro_symbolics": 52},
        "sells": {"quantum_foam": 19, "retro_organics": 8},
    },
    4874: {
        "buys": {},
        "sells": {"quantum_foam": 19, "retro_organics": 8, "neuro_symbolics": 30},
    },
}


@dataclass
class RateCI:
    rate: float
    low: float
    high: float


@dataclass
class ReportJudgeConfig:
    model: str
    api_key: str
    timeout_secs: float
    base_url: str = "https://api.anthropic.com"


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expand_paths(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        matches = glob.glob(p, recursive=True)
        if matches:
            out.extend(Path(m) for m in matches if m.endswith(".json"))
        else:
            candidate = Path(p)
            if candidate.exists() and candidate.suffix == ".json":
                out.append(candidate)
    deduped = sorted({str(p.resolve()): p.resolve() for p in out}.values())
    return deduped


def _to_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _percentile(values: list[float], p: float) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * p
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[low]
    frac = rank - low
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * frac


def _median_iqr(values: list[float]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if not values:
        return None, None, None
    sorted_values = sorted(values)
    med = median(sorted_values)
    q1 = _percentile(sorted_values, 0.25)
    q3 = _percentile(sorted_values, 0.75)
    return med, q1, q3


def _format_median_iqr(values: list[float], digits: int = 2) -> str:
    med, q1, q3 = _median_iqr(values)
    if med is None or q1 is None or q3 is None:
        return ""
    return f"{med:.{digits}f} [{q1:.{digits}f}, {q3:.{digits}f}]"


def _wilson_interval(successes: int, n: int, z: float = 1.96) -> RateCI:
    if n <= 0:
        return RateCI(rate=0.0, low=0.0, high=0.0)
    phat = successes / n
    denom = 1.0 + (z * z / n)
    center = (phat + (z * z / (2.0 * n))) / denom
    margin = (
        z
        * math.sqrt((phat * (1.0 - phat) / n) + (z * z / (4.0 * n * n)))
        / denom
    )
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return RateCI(rate=phat, low=low, high=high)


def _rate(num: int, den: int) -> Optional[float]:
    if den <= 0:
        return None
    return num / den


def _bfs_hops(start: int, target: int) -> Optional[int]:
    if start == target:
        return 0
    frontier = [start]
    visited = {start}
    hops = 0
    while frontier:
        hops += 1
        nxt_frontier: list[int] = []
        for node in frontier:
            for nbr in GRAPH.get(node, []):
                if nbr in visited:
                    continue
                if nbr == target:
                    return hops
                visited.add(nbr)
                nxt_frontier.append(nbr)
        frontier = nxt_frontier
    return None


def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    text = text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = text[start : end + 1]
    try:
        parsed = json.loads(snippet)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_commodity(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    key = value.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "qf": "quantum_foam",
        "quantumfoam": "quantum_foam",
        "ro": "retro_organics",
        "retroorganics": "retro_organics",
        "ns": "neuro_symbolics",
        "neurosymbolics": "neuro_symbolics",
    }
    if key in aliases:
        return aliases[key]
    if key in {"quantum_foam", "retro_organics", "neuro_symbolics"}:
        return key
    return None


def _deterministic_report_completeness(
    *,
    finished_called: bool,
    claimed_trades: Optional[int],
    claimed_profit: Optional[int],
) -> Optional[bool]:
    if not finished_called:
        return None
    return claimed_trades is not None and claimed_profit is not None


def _compute_trade_pnl_from_actions(turns: list[dict[str, Any]]) -> Optional[float]:
    pnl = 0.0
    saw_successful_trade = False
    for turn in turns:
        if turn.get("action") != "trade":
            continue
        if (turn.get("bad_inc") or 0) > 0:
            continue
        saw_successful_trade = True
        args = turn.get("args") if isinstance(turn.get("args"), dict) else {}
        trade_type = str(args.get("trade_type", "")).strip().lower()
        commodity = _normalize_commodity(args.get("commodity"))
        quantity = _to_int(args.get("quantity"))
        sector = _to_int(turn.get("sector_after"))
        if trade_type not in {"buy", "sell"} or commodity is None or quantity is None or sector is None:
            return None
        if quantity < 0:
            return None
        market = PORT_MARKETS.get(sector)
        if market is None:
            return None
        if trade_type == "buy":
            price = market["sells"].get(commodity)
            if price is None:
                return None
            pnl -= price * quantity
        else:
            price = market["buys"].get(commodity)
            if price is None:
                return None
            pnl += price * quantity
    if not saw_successful_trade:
        return 0.0
    return pnl


class AnthropicReportJudge:
    def __init__(self, config: ReportJudgeConfig) -> None:
        self._config = config

    def _request_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> tuple[Optional[str], Optional[str]]:
        payload = {
            "model": self._config.model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        body = json.dumps(payload).encode("utf-8")
        base = self._config.base_url.rstrip("/")
        req = urllib.request.Request(
            f"{base}/v1/messages",
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": self._config.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._config.timeout_secs) as resp:
                response_payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = ""
            try:
                details = exc.read().decode("utf-8")
            except Exception:  # noqa: BLE001
                details = str(exc)
            return None, f"http_error_{exc.code}: {details[:300]}"
        except Exception as exc:  # noqa: BLE001
            return None, f"request_error: {exc}"

        content_blocks = response_payload.get("content")
        text = ""
        if isinstance(content_blocks, list):
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += str(block.get("text") or "")
        return text, None

    @staticmethod
    def _parse_verdict(text: str) -> Optional[bool]:
        verdict_match = re.search(r"\b(PASS|FAIL)\b", text.upper())
        if not verdict_match:
            return None
        return verdict_match.group(1) == "PASS"

    def judge(
        self,
        *,
        finished_message: str,
    ) -> tuple[Optional[bool], Optional[bool], Optional[bool], str]:
        if not finished_message.strip():
            return None, None, None, "empty finish message"

        system_prompt = (
            "You are a strict evaluator for benchmark final reports. "
            "You MUST output exactly one token: PASS or FAIL. "
            "Do not output anything else."
        )
        user_prompt = (
            "Evaluate whether the final report satisfies both requirements:\n"
            "1) The report explicitly states how many ports were traded at.\n"
            "2) The report explicitly states total profit in credits.\n\n"
            "Final report text:\n"
            "---\n"
            f"{finished_message}\n"
            "---\n\n"
            "Output rule (MANDATORY):\n"
            "- Your FIRST word must be PASS or FAIL.\n"
            "- Output exactly PASS if and only if both requirements are satisfied.\n"
            "- Output exactly FAIL otherwise.\n"
            "- Output only PASS or FAIL."
        )
        text, err = self._request_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=64,
        )
        if err is not None:
            return None, None, None, err
        verdict = self._parse_verdict(text or "")
        if verdict is True:
            return True, True, True, "PASS"
        if verdict is False:
            return False, False, False, "FAIL"

        retry_prompt = (
            user_prompt
            + "\n\nYour previous response was invalid. Reply with exactly one word: PASS or FAIL."
        )
        retry_text, retry_err = self._request_text(
            system_prompt=system_prompt,
            user_prompt=retry_prompt,
            max_tokens=8,
        )
        if retry_err is not None:
            return None, None, None, retry_err
        retry_verdict = self._parse_verdict(retry_text or "")
        if retry_verdict is True:
            return True, True, True, "PASS(retry)"
        if retry_verdict is False:
            return False, False, False, "FAIL(retry)"

        return None, None, None, f"could not parse PASS/FAIL: {(retry_text or text or '')[:300]}"


def _parse_report_claims(message: str) -> tuple[Optional[int], Optional[int]]:
    if not message:
        return None, None
    trades_match = re.search(r"traded\s+at\s+(\d+)\s+port", message, flags=re.IGNORECASE)
    profit_match = re.search(
        r"profit\s*[:=]?\s*(-?[0-9][0-9,]*)\s*credits", message, flags=re.IGNORECASE
    )
    claimed_trades = int(trades_match.group(1)) if trades_match else None
    claimed_profit = int(profit_match.group(1).replace(",", "")) if profit_match else None
    return claimed_trades, claimed_profit


def _normalize_turns(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    last_bad = 0
    for idx, turn in enumerate(turns, start=1):
        turn_num = _to_int(turn.get("turn")) or idx
        bad_before = _to_int(turn.get("bad_actions_before"))
        bad_after = _to_int(turn.get("bad_actions_after"))
        bad_inc = _to_int(turn.get("bad_action_increment"))

        legacy_bad = _to_int(turn.get("bad_actions_count"))
        if bad_after is None and legacy_bad is not None:
            bad_after = legacy_bad
        if bad_before is None:
            bad_before = last_bad
        if bad_after is None and bad_inc is not None:
            bad_after = bad_before + bad_inc
        if bad_after is None:
            bad_after = bad_before
        if bad_inc is None:
            bad_inc = max(0, bad_after - bad_before)

        state_before = turn.get("state_before") if isinstance(turn.get("state_before"), dict) else {}
        state_after = turn.get("state_after") if isinstance(turn.get("state_after"), dict) else {}

        sector_after = _to_int(state_after.get("sector"))
        if sector_after is None:
            sector_after = _to_int(turn.get("sector"))

        norm = {
            "turn": turn_num,
            "decision_ms": _to_float(turn.get("decision_ms")),
            "action": turn.get("action"),
            "args": turn.get("args") if isinstance(turn.get("args"), dict) else {},
            "parse_error": turn.get("parse_error"),
            "raw_response": turn.get("raw_response") or "",
            "bad_before": bad_before,
            "bad_after": bad_after,
            "bad_inc": bad_inc,
            "state_before": state_before,
            "state_after": state_after,
            "sector_after": sector_after,
            "error_event": turn.get("error_event") if isinstance(turn.get("error_event"), dict) else None,
        }
        normalized.append(norm)
        last_bad = bad_after
    return normalized


def _derive_run_metrics(
    path: Path,
    payload: dict[str, Any],
    report_judge: Optional[AnthropicReportJudge],
) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    termination = payload.get("termination") if isinstance(payload.get("termination"), dict) else {}
    turns_raw = payload.get("turns") if isinstance(payload.get("turns"), list) else []

    turns = _normalize_turns([t for t in turns_raw if isinstance(t, dict)])

    provider = str(config.get("provider") or summary.get("provider") or "")
    model = str(config.get("model") or summary.get("model") or "")
    thinking_budget = config.get("thinking_budget", summary.get("thinking_budget"))
    max_tokens = config.get("max_tokens", summary.get("max_tokens"))
    openai_base_url = config.get("openai_base_url")

    final_sector = _to_int(summary.get("final_sector"))
    if final_sector is None:
        for turn in reversed(turns):
            if turn["sector_after"] is not None:
                final_sector = turn["sector_after"]
                break

    finished_called = bool(
        termination.get("finished_called")
        if "finished_called" in termination
        else summary.get("finished_called")
    )
    if not finished_called:
        finished_called = any(turn.get("action") == "finished" for turn in turns)

    finished_message = str(
        termination.get("finished_message")
        or summary.get("finished_message")
        or ""
    )

    terminal_reason = str(termination.get("reason") or summary.get("terminal_reason") or "")
    if not terminal_reason:
        terminal_reason = "finished_action" if finished_called else "max_turns_exhausted"

    reached_mega_anytime = bool(summary.get("reached_mega_anytime"))
    if not reached_mega_anytime:
        reached_mega_anytime = final_sector == MEGA_PORT_SECTOR or any(
            turn.get("sector_after") == MEGA_PORT_SECTOR for turn in turns
        )

    final_sector_is_mega = final_sector == MEGA_PORT_SECTOR

    coherent_report = bool(summary.get("coherent_report"))
    if not coherent_report and finished_message:
        lowered = finished_message.lower()
        coherent_report = "profit" in lowered and (
            "trade" in lowered or "traded" in lowered or "ports" in lowered
        )

    decision_values = [v for v in (turn.get("decision_ms") for turn in turns) if isinstance(v, float)]
    first_turn_latency_ms = decision_values[0] if decision_values else None
    warm_values = decision_values[1:] if len(decision_values) > 1 else []
    warm_p50_ms = _percentile(warm_values, 0.5)
    warm_p90_ms = _percentile(warm_values, 0.9)
    decision_max_ms = max(decision_values) if decision_values else None

    parse_error_count = sum(1 for turn in turns if turn.get("parse_error"))
    empty_response_count = sum(
        1
        for turn in turns
        if isinstance(turn.get("parse_error"), str)
        and turn.get("parse_error") == "empty model response"
    )

    invalid_move_count = sum(
        1 for turn in turns if turn.get("action") == "move" and (turn.get("bad_inc") or 0) > 0
    )
    invalid_trade_count = sum(
        1 for turn in turns if turn.get("action") == "trade" and (turn.get("bad_inc") or 0) > 0
    )
    unknown_action_count = sum(
        1
        for turn in turns
        if isinstance(turn.get("action"), str)
        and turn.get("action") not in KNOWN_ACTIONS
        and (turn.get("bad_inc") or 0) > 0
    )

    turns_executed = _to_int(summary.get("turns_executed")) or len(turns)
    elapsed_ms = _to_float(summary.get("elapsed_ms"))
    bad_actions_count = _to_int(summary.get("bad_actions_count"))
    if bad_actions_count is None:
        bad_actions_count = max((turn.get("bad_after") or 0 for turn in turns), default=0)

    bad_action_rate = _rate(bad_actions_count, turns_executed)
    parse_error_rate = _rate(parse_error_count, turns_executed)
    empty_response_rate = _rate(empty_response_count, turns_executed)

    move_attempts = sum(1 for turn in turns if turn.get("action") == "move")
    trade_attempts = sum(1 for turn in turns if turn.get("action") == "trade")
    invalid_move_rate = _rate(invalid_move_count, move_attempts)
    invalid_trade_rate = _rate(invalid_trade_count, trade_attempts)
    unknown_action_rate = _rate(unknown_action_count, turns_executed)

    # Streaks / recovery.
    max_consecutive_bad = 0
    current_bad = 0
    bad_indices: list[int] = []
    for idx, turn in enumerate(turns):
        if (turn.get("bad_inc") or 0) > 0:
            current_bad += 1
            bad_indices.append(idx)
            max_consecutive_bad = max(max_consecutive_bad, current_bad)
        else:
            current_bad = 0

    recovery_den = 0
    recovery_num = 0
    for idx in bad_indices:
        if idx + 1 >= len(turns):
            continue
        recovery_den += 1
        if (turns[idx + 1].get("bad_inc") or 0) == 0:
            recovery_num += 1
    error_recovery_rate = _rate(recovery_num, recovery_den)

    # Trading metrics from state deltas where available.
    successful_trade_count = 0
    successful_trade_ports: set[int] = set()
    realized_pnl_state: Optional[float] = 0.0
    for turn in turns:
        if turn.get("action") != "trade":
            continue
        if (turn.get("bad_inc") or 0) > 0:
            continue
        successful_trade_count += 1
        sector_for_trade = _to_int(turn.get("sector_after"))
        if sector_for_trade is not None:
            successful_trade_ports.add(sector_for_trade)
        before_credits = _to_float((turn.get("state_before") or {}).get("credits"))
        after_credits = _to_float((turn.get("state_after") or {}).get("credits"))
        if before_credits is None or after_credits is None:
            realized_pnl_state = None
            continue
        if realized_pnl_state is not None:
            realized_pnl_state += after_credits - before_credits

    realized_pnl_action = _compute_trade_pnl_from_actions(turns)
    if realized_pnl_state is not None:
        realized_pnl: Optional[float] = realized_pnl_state
        realized_pnl_source = "state_delta"
    else:
        realized_pnl = realized_pnl_action
        realized_pnl_source = "trade_action_replay" if realized_pnl_action is not None else "unavailable"

    claimed_trades, claimed_profit = _parse_report_claims(finished_message)
    deterministic_report_accuracy = _deterministic_report_completeness(
        finished_called=finished_called,
        claimed_trades=claimed_trades,
        claimed_profit=claimed_profit,
    )
    report_accuracy = deterministic_report_accuracy
    report_accuracy_method = "deterministic"
    report_judge_has_all_info: Optional[bool] = None
    report_judge_numbers_match: Optional[bool] = None
    report_judge_reason: Optional[str] = None

    if report_judge is not None and finished_called:
        judged_accuracy, has_all_info, numbers_match, judge_reason = report_judge.judge(
            finished_message=finished_message,
        )
        report_judge_has_all_info = has_all_info
        report_judge_numbers_match = numbers_match
        report_judge_reason = judge_reason
        if judged_accuracy is not None:
            report_accuracy = judged_accuracy
            report_accuracy_method = "llm"
        else:
            report_accuracy_method = "llm_fallback_deterministic"

    # Navigation quality metrics.
    start_sector = _to_int((metadata.get("initial_state") or {}).get("sector"))
    if start_sector is None:
        first_before = turns[0].get("state_before") if turns else {}
        start_sector = _to_int((first_before or {}).get("sector"))
    if start_sector is None:
        start_sector = 3080

    total_moves = 0
    backtracking_count = 0
    visited = {start_sector}
    reached_first_mega = start_sector == MEGA_PORT_SECTOR
    moves_to_first_mega = 0 if reached_first_mega else None
    post_goal_moves = 0

    for turn in turns:
        if turn.get("action") != "move":
            continue
        if (turn.get("bad_inc") or 0) > 0:
            continue
        sector_after = _to_int(turn.get("sector_after"))
        if sector_after is None:
            continue

        total_moves += 1
        if sector_after in visited:
            backtracking_count += 1
        visited.add(sector_after)

        if reached_first_mega:
            post_goal_moves += 1
        elif sector_after == MEGA_PORT_SECTOR:
            reached_first_mega = True
            moves_to_first_mega = total_moves

    if reached_first_mega and moves_to_first_mega is None:
        moves_to_first_mega = 0

    optimal_hops = _bfs_hops(start_sector, MEGA_PORT_SECTOR)
    path_efficiency_ratio: Optional[float] = None
    if optimal_hops is not None and moves_to_first_mega is not None:
        if moves_to_first_mega == 0 and optimal_hops == 0:
            path_efficiency_ratio = 1.0
        elif moves_to_first_mega > 0:
            path_efficiency_ratio = optimal_hops / moves_to_first_mega

    backtracking_rate = _rate(backtracking_count, total_moves)
    reached_mega_but_left = bool(reached_mega_anytime and not final_sector_is_mega)

    # Success classes.
    strict_success = bool(
        finished_called
        and final_sector_is_mega
        and coherent_report
        and report_accuracy is True
    )
    lenient_success = bool(finished_called and reached_mega_anytime and coherent_report)
    clean_finish = terminal_reason == "finished_action"

    if strict_success:
        terminal_class = "strict_success"
    elif lenient_success:
        terminal_class = "lenient_success_not_strict"
    elif terminal_reason == "watchdog_stop":
        terminal_class = "watchdog_stop"
    elif terminal_reason == "idle_timeout":
        terminal_class = "idle_timeout"
    elif terminal_reason == "max_turns_exhausted":
        if parse_error_count >= 3 and (parse_error_rate or 0.0) >= 0.5:
            terminal_class = "parse_stall"
        else:
            terminal_class = "max_turns_exhausted"
    else:
        terminal_class = "other_failure"

    group_key = (
        f"{provider}|{model}|tb={thinking_budget}|mt={max_tokens}|"
        f"base={openai_base_url or 'default'}"
    )

    return {
        "file": str(path),
        "group_key": group_key,
        "provider": provider,
        "model": model,
        "thinking_budget": thinking_budget,
        "max_tokens": max_tokens,
        "openai_base_url": openai_base_url,
        "turns_executed": turns_executed,
        "elapsed_ms": elapsed_ms,
        "strict_success": strict_success,
        "lenient_success": lenient_success,
        "clean_finish": clean_finish,
        "terminal_reason": terminal_reason,
        "terminal_class": terminal_class,
        "finished_called": finished_called,
        "finished_message": finished_message,
        "coherent_report": coherent_report,
        "final_sector": final_sector,
        "final_sector_is_mega": final_sector_is_mega,
        "reached_mega_anytime": reached_mega_anytime,
        "reached_mega_but_left": reached_mega_but_left,
        "bad_actions_count": bad_actions_count,
        "bad_action_rate": bad_action_rate,
        "parse_error_count": parse_error_count,
        "parse_error_rate": parse_error_rate,
        "empty_response_count": empty_response_count,
        "empty_response_rate": empty_response_rate,
        "invalid_move_count": invalid_move_count,
        "invalid_move_rate": invalid_move_rate,
        "invalid_trade_count": invalid_trade_count,
        "invalid_trade_rate": invalid_trade_rate,
        "unknown_action_count": unknown_action_count,
        "unknown_action_rate": unknown_action_rate,
        "max_consecutive_bad_actions": max_consecutive_bad,
        "error_recovery_rate": error_recovery_rate,
        "first_turn_latency_ms": first_turn_latency_ms,
        "warm_turn_p50_ms": warm_p50_ms,
        "warm_turn_p90_ms": warm_p90_ms,
        "decision_max_ms": decision_max_ms,
        "start_sector": start_sector,
        "optimal_hops_to_mega": optimal_hops,
        "moves_to_first_mega": moves_to_first_mega,
        "path_efficiency_ratio": path_efficiency_ratio,
        "total_moves": total_moves,
        "backtracking_count": backtracking_count,
        "backtracking_rate": backtracking_rate,
        "post_goal_moves": post_goal_moves,
        "successful_trade_count": successful_trade_count,
        "successful_trade_port_count": len(successful_trade_ports),
        "realized_pnl": realized_pnl,
        "realized_pnl_source": realized_pnl_source,
        "claimed_trade_count": claimed_trades,
        "claimed_profit": claimed_profit,
        "report_accuracy": report_accuracy,
        "report_accuracy_method": report_accuracy_method,
        "deterministic_report_accuracy": deterministic_report_accuracy,
        "report_judge_has_all_info": report_judge_has_all_info,
        "report_judge_numbers_match": report_judge_numbers_match,
        "report_judge_reason": report_judge_reason,
        "schema_version": payload.get("schema_version"),
        "run_id": metadata.get("run_id"),
        "git_sha": metadata.get("git_sha"),
        "prompt_hash": metadata.get("task_prompt_hash"),
        "started_at_utc": metadata.get("started_at_utc"),
        "ended_at_utc": metadata.get("ended_at_utc"),
    }


def _aggregate_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    strict_count = sum(1 for r in rows if r["strict_success"])
    lenient_count = sum(1 for r in rows if r["lenient_success"])
    clean_count = sum(1 for r in rows if r["clean_finish"])
    left_count = sum(1 for r in rows if r["reached_mega_but_left"])

    strict_ci = _wilson_interval(strict_count, n)
    lenient_ci = _wilson_interval(lenient_count, n)
    clean_ci = _wilson_interval(clean_count, n)
    left_ci = _wilson_interval(left_count, n)

    terminal_counts = Counter(r["terminal_class"] for r in rows)

    def vals(key: str) -> list[float]:
        out: list[float] = []
        for row in rows:
            value = row.get(key)
            if isinstance(value, (int, float)):
                out.append(float(value))
        return out

    return {
        "n": n,
        "strict_success": {"count": strict_count, **strict_ci.__dict__},
        "lenient_success": {"count": lenient_count, **lenient_ci.__dict__},
        "clean_finish": {"count": clean_count, **clean_ci.__dict__},
        "reached_mega_but_left": {"count": left_count, **left_ci.__dict__},
        "terminal_counts": dict(terminal_counts),
        "turns_median_iqr": _format_median_iqr(vals("turns_executed"), digits=1),
        "bad_action_rate_median_iqr": _format_median_iqr(vals("bad_action_rate"), digits=3),
        "first_turn_latency_median_iqr_ms": _format_median_iqr(vals("first_turn_latency_ms"), digits=1),
        "warm_turn_p50_median_iqr_ms": _format_median_iqr(vals("warm_turn_p50_ms"), digits=1),
        "warm_turn_p90_median_iqr_ms": _format_median_iqr(vals("warm_turn_p90_ms"), digits=1),
        "decision_max_median_iqr_ms": _format_median_iqr(vals("decision_max_ms"), digits=1),
        "path_efficiency_median_iqr": _format_median_iqr(vals("path_efficiency_ratio"), digits=3),
        "realized_pnl_median_iqr": _format_median_iqr(vals("realized_pnl"), digits=1),
        "report_accuracy_rate": _rate(
            sum(1 for r in rows if r.get("report_accuracy") is True),
            sum(1 for r in rows if r.get("report_accuracy") is not None),
        ),
        "error_recovery_rate_median_iqr": _format_median_iqr(vals("error_recovery_rate"), digits=3),
        "parse_error_rate_median_iqr": _format_median_iqr(vals("parse_error_rate"), digits=3),
        "invalid_move_rate_median_iqr": _format_median_iqr(vals("invalid_move_rate"), digits=3),
        "invalid_trade_rate_median_iqr": _format_median_iqr(vals("invalid_trade_rate"), digits=3),
        "post_goal_moves_median_iqr": _format_median_iqr(vals("post_goal_moves"), digits=1),
    }


def _write_markdown_table(out_path: Path, rows: list[dict[str, Any]], agg: dict[str, Any]) -> None:
    lines = [
        "| Model | Config | N | Strict Success | Lenient Success | Clean Finish | Bad Action Rate (med [Q1,Q3]) | Warm P50 ms (med [Q1,Q3]) | Warm P90 ms (med [Q1,Q3]) | Path Eff (med [Q1,Q3]) | P&L (med [Q1,Q3]) | Reached Mega But Left |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for group_key in sorted(agg.keys()):
        group_rows = [r for r in rows if r["group_key"] == group_key]
        first = group_rows[0]
        data = agg[group_key]

        strict = data["strict_success"]
        lenient = data["lenient_success"]
        clean = data["clean_finish"]
        left = data["reached_mega_but_left"]

        config_str = (
            f"tb={first.get('thinking_budget')} mt={first.get('max_tokens')} "
            f"base={first.get('openai_base_url') or 'default'}"
        )

        lines.append(
            "| "
            + f"{first.get('provider')}/{first.get('model')} | {config_str} | {data['n']} | "
            + f"{strict['rate']:.2%} [{strict['low']:.2%}, {strict['high']:.2%}] | "
            + f"{lenient['rate']:.2%} [{lenient['low']:.2%}, {lenient['high']:.2%}] | "
            + f"{clean['rate']:.2%} [{clean['low']:.2%}, {clean['high']:.2%}] | "
            + f"{data['bad_action_rate_median_iqr']} | "
            + f"{data['warm_turn_p50_median_iqr_ms']} | "
            + f"{data['warm_turn_p90_median_iqr_ms']} | "
            + f"{data['path_efficiency_median_iqr']} | "
            + f"{data['realized_pnl_median_iqr']} | "
            + f"{left['rate']:.2%} [{left['low']:.2%}, {left['high']:.2%}] |"
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate mini-RL benchmark run JSON files")
    parser.add_argument(
        "paths",
        nargs="+",
        help="Input JSON paths or glob patterns (e.g. runs/matrix-*/**/*.json)",
    )
    parser.add_argument(
        "--out-dir",
        default=f"runs/eval-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        help="Output directory for evaluation artifacts",
    )
    parser.add_argument(
        "--report-accuracy-judge",
        choices=["llm", "deterministic"],
        default="llm",
        help="How to evaluate report_accuracy used by strict_success",
    )
    parser.add_argument(
        "--judge-model",
        default="claude-sonnet-4-6",
        help="Anthropic model used when --report-accuracy-judge=llm",
    )
    parser.add_argument(
        "--judge-api-key-env",
        default="ANTHROPIC_API_KEY",
        help="Env var containing Anthropic API key",
    )
    parser.add_argument(
        "--judge-base-url",
        default=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        help="Anthropic API base URL",
    )
    parser.add_argument(
        "--judge-timeout-secs",
        type=float,
        default=30.0,
        help="Timeout for per-run LLM judge request",
    )
    args = parser.parse_args()

    input_paths = _expand_paths(args.paths)
    if not input_paths:
        raise SystemExit("No input JSON files found.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_judge: Optional[AnthropicReportJudge] = None
    if args.report_accuracy_judge == "llm":
        judge_api_key = os.getenv(args.judge_api_key_env)
        if not judge_api_key:
            raise SystemExit(
                f"Missing judge API key: set env var {args.judge_api_key_env} "
                "or use --report-accuracy-judge deterministic."
            )
        report_judge = AnthropicReportJudge(
            ReportJudgeConfig(
                model=args.judge_model,
                api_key=judge_api_key,
                timeout_secs=args.judge_timeout_secs,
                base_url=args.judge_base_url,
            )
        )

    derived_rows: list[dict[str, Any]] = []
    for path in input_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            derived_rows.append(
                {
                    "file": str(path),
                    "group_key": "invalid",
                    "provider": "",
                    "model": "",
                    "terminal_class": "other_failure",
                    "strict_success": False,
                    "lenient_success": False,
                    "clean_finish": False,
                    "error": f"failed_to_load_json: {exc}",
                }
            )
            continue
        derived_rows.append(_derive_run_metrics(path, payload, report_judge))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in derived_rows:
        grouped[row["group_key"]].append(row)

    aggregate = {group_key: _aggregate_group(rows) for group_key, rows in grouped.items()}

    enriched_path = out_dir / "enriched_runs.jsonl"
    with enriched_path.open("w", encoding="utf-8") as handle:
        for row in derived_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    aggregate_path = out_dir / "aggregate.json"
    aggregate_payload = {
        "generated_at_utc": _iso_utc_now(),
        "input_count": len(input_paths),
        "report_accuracy_judge": args.report_accuracy_judge,
        "judge_model": args.judge_model if args.report_accuracy_judge == "llm" else None,
        "groups": aggregate,
    }
    aggregate_path.write_text(json.dumps(aggregate_payload, indent=2, sort_keys=True), encoding="utf-8")

    table_csv_path = out_dir / "table.csv"
    with table_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "group_key",
                "model",
                "config",
                "n",
                "strict_success_rate",
                "strict_ci_low",
                "strict_ci_high",
                "lenient_success_rate",
                "lenient_ci_low",
                "lenient_ci_high",
                "clean_finish_rate",
                "clean_ci_low",
                "clean_ci_high",
                "bad_action_rate_median_iqr",
                "warm_turn_p50_median_iqr_ms",
                "warm_turn_p90_median_iqr_ms",
                "path_efficiency_median_iqr",
                "realized_pnl_median_iqr",
                "reached_mega_but_left_rate",
                "reached_mega_but_left_ci_low",
                "reached_mega_but_left_ci_high",
                "terminal_counts",
            ]
        )

        for group_key in sorted(aggregate.keys()):
            group_rows = grouped[group_key]
            first = group_rows[0]
            data = aggregate[group_key]
            strict = data["strict_success"]
            lenient = data["lenient_success"]
            clean = data["clean_finish"]
            left = data["reached_mega_but_left"]
            cfg = (
                f"tb={first.get('thinking_budget')} mt={first.get('max_tokens')} "
                f"base={first.get('openai_base_url') or 'default'}"
            )
            writer.writerow(
                [
                    group_key,
                    f"{first.get('provider')}/{first.get('model')}",
                    cfg,
                    data["n"],
                    strict["rate"],
                    strict["low"],
                    strict["high"],
                    lenient["rate"],
                    lenient["low"],
                    lenient["high"],
                    clean["rate"],
                    clean["low"],
                    clean["high"],
                    data["bad_action_rate_median_iqr"],
                    data["warm_turn_p50_median_iqr_ms"],
                    data["warm_turn_p90_median_iqr_ms"],
                    data["path_efficiency_median_iqr"],
                    data["realized_pnl_median_iqr"],
                    left["rate"],
                    left["low"],
                    left["high"],
                    json.dumps(data["terminal_counts"], sort_keys=True),
                ]
            )

    table_md_path = out_dir / "table.md"
    _write_markdown_table(table_md_path, derived_rows, aggregate)

    print(f"INPUT_FILES={len(input_paths)}")
    print(f"OUT_DIR={out_dir}")
    print(f"ENRICHED={enriched_path}")
    print(f"AGGREGATE={aggregate_path}")
    print(f"TABLE_CSV={table_csv_path}")
    print(f"TABLE_MD={table_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
