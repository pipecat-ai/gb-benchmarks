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

DEFAULT_START_SECTOR = 3080
MEGA_PORT_SECTOR = 1611
MEGA_PORT_NAME = "MEGA SSS"
RUN_SCHEMA_VERSION = "mini_rl_run.v3"

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

TOOL_FAMILIES: dict[str, set[str]] = {
    "navigation": {"move", "plot_course", "local_map_region", "list_known_ports"},
    "trade": {"trade", "dump_cargo", "salvage_collect", "purchase_fighters"},
    "combat": {"combat_initiate", "combat_action"},
    "corporation": {
        "create_corporation",
        "join_corporation",
        "leave_corporation",
        "kick_corporation_member",
        "corporation_info",
    },
    "economy": {"bank_deposit", "bank_withdraw", "transfer_credits", "recharge_warp_power", "transfer_warp_power"},
    "info": {"my_status", "event_query", "load_game_info", "wait_in_idle_state"},
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


def _normalize_openai_base_url(base_url: Any) -> Optional[str]:
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


def _display_base_url(base_url: Any) -> Optional[str]:
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


def _variant_display_label(row: dict[str, Any]) -> str:
    model = str(row.get("model") or "UNKNOWN")
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

    prompt_hash = str(row.get("prompt_hash") or "").strip()
    if prompt_hash:
        details.append(f"prompt={prompt_hash[:8]}")

    base_label = _display_base_url(row.get("openai_base_url"))
    if base_label:
        details.append(f"base={base_label}")

    if not details:
        return model
    return f"{model} ({', '.join(details)})"


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


def _is_coherent_finished_report(message: str) -> bool:
    lowered = message.lower()
    recharge_like = (
        "recharg" in lowered
        or "refill" in lowered
        or (
            "warp" in lowered
            and any(
                phrase in lowered
                for phrase in (
                    "topped off",
                    "topped up",
                    "top off",
                    "top up",
                    "filled up",
                    "fill up",
                    "full warp",
                    "restored",
                )
            )
        )
    )
    return (
        any(
            token in lowered
            for token in ("profit", "net change", "net result", "overall gain", "overall loss", "overall net")
        )
        and ("trade" in lowered or "traded" in lowered or "ports" in lowered)
        and recharge_like
        and (
            "mega" in lowered
            or "mega sss" in lowered
            or re.search(rf"\b{MEGA_PORT_SECTOR}\b", lowered) is not None
        )
    )


def _iter_turn_tool_call_contexts(
    turn: dict[str, Any],
    *,
    resolved_sector_after: Optional[int] = None,
) -> list[dict[str, Any]]:
    tool_calls = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
    state_before = turn.get("state_before") if isinstance(turn.get("state_before"), dict) else {}
    current_sector = _to_int(state_before.get("sector"))
    turn_sector_after = (
        resolved_sector_after if resolved_sector_after is not None else _to_int(turn.get("sector_after"))
    )

    successful_move_indexes = [
        idx
        for idx, call in enumerate(tool_calls)
        if isinstance(call, dict)
        and call.get("name") == "move"
        and str(call.get("result_status") or "") in {"acknowledged", "success"}
    ]
    last_successful_move_index = successful_move_indexes[-1] if successful_move_indexes else None

    contexts: list[dict[str, Any]] = []
    for idx, call in enumerate(tool_calls):
        if not isinstance(call, dict):
            continue
        name = call.get("name")
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        result_status = str(call.get("result_status") or "unknown")
        sector_before = current_sector
        sector_after = current_sector

        if name == "move" and result_status in {"acknowledged", "success"}:
            if idx == last_successful_move_index and turn_sector_after is not None:
                sector_after = turn_sector_after
            else:
                to_sector = _to_int(args.get("to_sector"))
                if to_sector is not None:
                    sector_after = to_sector
            if sector_after is not None:
                current_sector = sector_after

        contexts.append(
            {
                "name": name,
                "args": args,
                "result_status": result_status,
                "sector_before": sector_before,
                "sector_after": sector_after,
            }
        )

    return contexts


def _compute_trade_pnl_from_actions(
    turns: list[dict[str, Any]],
    *,
    resolved_sector_after_by_turn: Optional[list[Optional[int]]] = None,
) -> Optional[float]:
    pnl = 0.0
    saw_successful_trade = False
    for idx, turn in enumerate(turns):
        resolved_sector_after = None
        if resolved_sector_after_by_turn is not None and idx < len(resolved_sector_after_by_turn):
            resolved_sector_after = resolved_sector_after_by_turn[idx]
        for call in _iter_turn_tool_call_contexts(turn, resolved_sector_after=resolved_sector_after):
            if call.get("name") != "trade":
                continue
            result_status = str(call.get("result_status") or "")
            if result_status not in {"acknowledged", "success"}:
                continue

            saw_successful_trade = True
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            trade_type = str(args.get("trade_type", "")).strip().lower()
            commodity = _normalize_commodity(args.get("commodity"))
            quantity = _to_int(args.get("quantity"))
            sector = _to_int(call.get("sector_before"))
            if (
                trade_type not in {"buy", "sell"}
                or commodity is None
                or quantity is None
                or sector is None
            ):
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
        expected_finish_sector: int,
        report_truth: dict[str, Any],
    ) -> tuple[Optional[bool], str]:
        if not finished_message.strip():
            return None, "empty finish message"

        system_prompt = (
            "You are a strict evaluator for benchmark final reports. "
            "You MUST output exactly one token: PASS or FAIL. "
            "Do not output anything else."
        )
        truth_payload = json.dumps(report_truth, sort_keys=True)
        user_prompt = (
            "Evaluate whether the final report satisfies ALL requirements for this round-trip benchmark:\n"
            "1) It identifies which mega-port was used (name or sector).\n"
            "2) It states how much warp was recharged and the recharge cost in credits.\n"
            "3) It states how many ports were traded at.\n"
            "4) It states total profit in credits for the whole trip.\n"
            "5) Judge by semantic meaning, not exact field labels.\n"
            "6) Accept equivalent wording. For example, whole-trip profit may be expressed as "
            "'net change', 'net result', 'overall gain/loss', or an equivalent whole-trip metric.\n"
            "7) If the report includes both a trade-only profit metric and a whole-trip net metric, "
            "use the whole-trip net metric for requirement 4. Do not fail merely because a trade-only "
            "profit number differs from the whole-trip total.\n"
            "8) A trade-only profit line is allowed as extra detail. Do NOT treat it as the required "
            "whole-trip profit answer if the report separately states the overall trip net result.\n"
            "9) Example: if a report says 'Total profit from trades: 0 credits' and also says "
            "'Net change: -66 credits (warp recharge cost only)', then the required whole-trip profit "
            "claim is -66 credits, not 0 credits.\n"
            "10) Example: 'Warp power recharged: 33 units for 66 credits' DOES satisfy the recharge "
            "amount and recharge cost requirement.\n"
            "11) Accept recharge cost phrased in equivalent ways such as 'cost 66 credits', "
            "'spent 66 credits', or 'for 66 credits'.\n"
            "12) Extra details are allowed and should not cause failure.\n"
            "13) Any numeric claims that semantically correspond to the required items must exactly match ground truth.\n"
            f"14) Do NOT require an explicit finish-sector claim; objective completion is checked separately (expected finish sector is {expected_finish_sector}).\n\n"
            "Ground truth JSON:\n"
            f"{truth_payload}\n\n"
            "Final report text:\n"
            "---\n"
            f"{finished_message}\n"
            "---\n\n"
            "Output rule (MANDATORY):\n"
            "- Your FIRST word must be PASS or FAIL.\n"
            "- Output exactly PASS if and only if all requirements are satisfied.\n"
            "- Output exactly FAIL otherwise.\n"
            "- Output only PASS or FAIL."
        )
        text, err = self._request_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=64,
        )
        if err is not None:
            return None, err
        verdict = self._parse_verdict(text or "")
        if verdict is True:
            return True, "PASS"
        if verdict is False:
            return False, "FAIL"

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
            return None, retry_err
        retry_verdict = self._parse_verdict(retry_text or "")
        if retry_verdict is True:
            return True, "PASS(retry)"
        if retry_verdict is False:
            return False, "FAIL(retry)"

        return None, f"could not parse PASS/FAIL: {(retry_text or text or '')[:300]}"


def _normalize_turns(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    last_bad = 0
    for idx, turn in enumerate(turns, start=1):
        turn_num = _to_int(turn.get("llm_turn")) or idx
        bad_before = _to_int(turn.get("bad_actions_before"))
        bad_after = _to_int(turn.get("bad_actions_after"))
        bad_inc = _to_int(turn.get("bad_action_increment"))

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

        tool_calls_raw = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
        tool_calls: list[dict[str, Any]] = []
        for call in tool_calls_raw:
            if not isinstance(call, dict):
                continue
            name = call.get("name")
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            result_status = str(call.get("result_status") or "unknown")
            tool_calls.append(
                {
                    "name": str(name) if isinstance(name, str) else None,
                    "args": args,
                    "result_status": result_status,
                }
            )

        norm = {
            "turn": turn_num,
            "decision_ms": _to_float(turn.get("decision_ms")),
            "tool_calls": tool_calls,
            "failure_class": str(turn.get("failure_class") or "none"),
            "raw_response": turn.get("raw_response_text") or "",
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


def _actual_sector_after_turn(
    turns: list[dict[str, Any]],
    index: int,
    *,
    final_sector: Optional[int],
) -> Optional[int]:
    if index + 1 < len(turns):
        next_before = _to_int((turns[index + 1].get("state_before") or {}).get("sector"))
        if next_before is not None:
            return next_before

    if index == len(turns) - 1 and final_sector is not None:
        return final_sector

    state_after = turns[index].get("state_after") if isinstance(turns[index].get("state_after"), dict) else {}
    sector_after = _to_int(state_after.get("sector"))
    if sector_after is not None:
        return sector_after

    return _to_int(turns[index].get("sector_after"))


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
    thinking = config.get(
        "thinking",
        summary.get("thinking", config.get("thinking_budget", summary.get("thinking_budget"))),
    )
    thinking_budget = config.get("thinking_budget", summary.get("thinking_budget"))
    max_tokens = config.get("max_tokens", summary.get("max_tokens"))
    openai_base_url = _normalize_openai_base_url(
        config.get("openai_base_url", summary.get("openai_base_url"))
    )
    prompt_hash = str(metadata.get("task_prompt_hash") or "")

    initial_state = metadata.get("initial_state") if isinstance(metadata.get("initial_state"), dict) else {}
    start_sector = _to_int(summary.get("start_sector"))
    if start_sector is None:
        start_sector = _to_int(initial_state.get("sector"))
    if start_sector is None:
        first_before = turns[0].get("state_before") if turns else {}
        start_sector = _to_int((first_before or {}).get("sector"))
    if start_sector is None:
        start_sector = DEFAULT_START_SECTOR

    expected_finish_sector = _to_int(summary.get("expected_finish_sector"))
    if expected_finish_sector is None:
        expected_finish_sector = start_sector

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
        finished_called = any(
            isinstance(call.get("name"), str) and call.get("name") == "finished"
            for turn in turns
            for call in (turn.get("tool_calls") or [])
            if isinstance(call, dict)
        )

    finished_message = str(
        termination.get("finished_message")
        or summary.get("finished_message")
        or ""
    )

    terminal_reason = str(termination.get("reason") or summary.get("terminal_reason") or "")
    if not terminal_reason:
        terminal_reason = "finished_tool" if finished_called else "max_turns_exhausted"

    reached_mega_anytime = bool(summary.get("reached_mega_anytime"))
    if not reached_mega_anytime:
        reached_mega_anytime = final_sector == MEGA_PORT_SECTOR or any(
            _actual_sector_after_turn(turns, idx, final_sector=final_sector) == MEGA_PORT_SECTOR
            for idx, _turn in enumerate(turns)
        )

    final_sector_is_mega = final_sector == MEGA_PORT_SECTOR
    final_sector_matches_start = (
        final_sector == expected_finish_sector if final_sector is not None else False
    )

    coherent_report = bool(summary.get("coherent_report"))
    if not coherent_report and finished_message:
        coherent_report = _is_coherent_finished_report(finished_message)

    decision_values = [v for v in (turn.get("decision_ms") for turn in turns) if isinstance(v, float)]
    first_turn_latency_ms = decision_values[0] if decision_values else None
    warm_values = decision_values[1:] if len(decision_values) > 1 else []
    warm_p50_ms = _percentile(warm_values, 0.5)
    warm_p90_ms = _percentile(warm_values, 0.9)
    decision_max_ms = max(decision_values) if decision_values else None

    resolved_sector_after_by_turn = [
        _actual_sector_after_turn(turns, idx, final_sector=final_sector) for idx, _turn in enumerate(turns)
    ]

    all_calls: list[dict[str, Any]] = []
    turn_call_contexts: list[list[dict[str, Any]]] = []
    for turn, resolved_sector_after in zip(turns, resolved_sector_after_by_turn):
        call_contexts = _iter_turn_tool_call_contexts(
            turn,
            resolved_sector_after=resolved_sector_after,
        )
        turn_call_contexts.append(call_contexts)
        for call in call_contexts:
            all_calls.append(
                {
                    "name": call.get("name"),
                    "args": call.get("args") if isinstance(call.get("args"), dict) else {},
                    "result_status": str(call.get("result_status") or "unknown"),
                    "sector_before": _to_int(call.get("sector_before")),
                    "sector_after": _to_int(call.get("sector_after")),
                    "turn": turn,
                }
            )

    if not reached_mega_anytime:
        reached_mega_anytime = final_sector == MEGA_PORT_SECTOR or any(
            call.get("sector_before") == MEGA_PORT_SECTOR or call.get("sector_after") == MEGA_PORT_SECTOR
            for call in all_calls
        )

    inference_failure_count = sum(
        1 for turn in turns if str(turn.get("failure_class") or "") == "inference_failure"
    )
    no_tool_call_count = _to_int(summary.get("no_tool_call_count"))
    if no_tool_call_count is None:
        no_tool_call_count = sum(
            1 for turn in turns if str(turn.get("failure_class") or "") == "no_tool_call"
        )

    invalid_move_count = sum(
        1
        for call in all_calls
        if call.get("name") == "move"
        and call.get("result_status") in {"error", "post_finished_call_rejected"}
    )
    invalid_trade_count = sum(
        1
        for call in all_calls
        if call.get("name") == "trade"
        and call.get("result_status") in {"error", "post_finished_call_rejected"}
    )
    unknown_action_count = sum(
        1
        for call in all_calls
        if isinstance(call.get("name"), str)
        and call.get("name") not in KNOWN_ACTIONS
        and call.get("result_status") in {"error", "post_finished_call_rejected"}
    )

    turns_executed = _to_int(summary.get("turns_executed")) or len(turns)
    elapsed_ms = _to_float(summary.get("elapsed_ms"))
    bad_actions_count = _to_int(summary.get("bad_actions_count"))
    if bad_actions_count is None:
        bad_actions_count = max((turn.get("bad_after") or 0 for turn in turns), default=0)

    post_finished_call_count = _to_int(summary.get("post_finished_call_count"))
    if post_finished_call_count is None:
        post_finished_call_count = sum(
            1
            for call in all_calls
            if call.get("result_status") == "post_finished_call_rejected"
        )
    async_completion_timeout_count = _to_int(summary.get("async_completion_timeout_count"))
    if async_completion_timeout_count is None:
        async_completion_timeout_count = 0

    multi_call_turn_count = _to_int(summary.get("multi_call_turn_count"))
    if multi_call_turn_count is None:
        multi_call_turn_count = sum(
            1 for turn in turns if len(turn.get("tool_calls") or []) > 1
        )
    avg_tool_calls_per_turn = summary.get("avg_tool_calls_per_turn")
    if not isinstance(avg_tool_calls_per_turn, (int, float)):
        avg_tool_calls_per_turn = (len(all_calls) / turns_executed) if turns_executed > 0 else 0.0
    max_tool_calls_per_turn = _to_int(summary.get("max_tool_calls_per_turn"))
    if max_tool_calls_per_turn is None:
        max_tool_calls_per_turn = max((len(turn.get("tool_calls") or []) for turn in turns), default=0)

    bad_action_rate = _rate(bad_actions_count, turns_executed)
    no_tool_call_rate = _rate(no_tool_call_count, turns_executed)
    inference_failure_rate = _rate(inference_failure_count, turns_executed)

    move_attempts = sum(1 for call in all_calls if call.get("name") == "move")
    trade_attempts = sum(1 for call in all_calls if call.get("name") == "trade")
    invalid_move_rate = _rate(invalid_move_count, move_attempts)
    invalid_trade_rate = _rate(invalid_trade_count, trade_attempts)
    unknown_action_rate = _rate(unknown_action_count, max(1, len(all_calls)))

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
    for turn, call_contexts in zip(turns, turn_call_contexts):
        trade_calls = [
            call
            for call in call_contexts
            if call.get("name") == "trade"
            and str(call.get("result_status") or "") in {"acknowledged", "success"}
        ]
        if not trade_calls:
            continue
        successful_trade_count += len(trade_calls)
        for call in trade_calls:
            sector_for_trade = _to_int(call.get("sector_before"))
            if sector_for_trade is not None:
                successful_trade_ports.add(sector_for_trade)
        # Mixed trade+recharge turns combine distinct credit effects, so trade P&L
        # must be reconstructed from the actions instead of the turn-level delta.
        if any(
            call.get("name") == "recharge_warp_power"
            and str(call.get("result_status") or "") in {"acknowledged", "success"}
            for call in call_contexts
        ):
            realized_pnl_state = None
            continue
        before_credits = _to_float((turn.get("state_before") or {}).get("credits"))
        after_credits = _to_float((turn.get("state_after") or {}).get("credits"))
        if before_credits is None or after_credits is None:
            realized_pnl_state = None
            continue
        if realized_pnl_state is not None:
            realized_pnl_state += after_credits - before_credits

    realized_pnl_action = _compute_trade_pnl_from_actions(
        turns,
        resolved_sector_after_by_turn=resolved_sector_after_by_turn,
    )
    if realized_pnl_state is not None:
        realized_pnl: Optional[float] = realized_pnl_state
        realized_pnl_source = "state_delta"
    else:
        realized_pnl = realized_pnl_action
        realized_pnl_source = "trade_action_replay" if realized_pnl_action is not None else "unavailable"

    recharge_units = 0
    recharge_cost = 0
    recharge_to_full_at_mega = False
    mega_port_used_sector: Optional[int] = None
    for turn in turns:
        recharge_calls = [
            call
            for call in (turn.get("tool_calls") or [])
            if isinstance(call, dict)
            and call.get("name") == "recharge_warp_power"
            and str(call.get("result_status") or "") in {"acknowledged", "success"}
        ]
        if not recharge_calls:
            continue

        state_before = turn.get("state_before") if isinstance(turn.get("state_before"), dict) else {}
        state_after = turn.get("state_after") if isinstance(turn.get("state_after"), dict) else {}

        turn_recharge_units = 0
        before_warp = _to_int(state_before.get("warp"))
        after_warp = _to_int(state_after.get("warp"))
        if before_warp is not None and after_warp is not None and after_warp > before_warp:
            turn_recharge_units = after_warp - before_warp
            recharge_units += turn_recharge_units

        if turn_recharge_units > 0:
            recharge_cost += turn_recharge_units * 2
        else:
            before_credits = _to_float(state_before.get("credits"))
            after_credits = _to_float(state_after.get("credits"))
            if before_credits is not None and after_credits is not None and before_credits > after_credits:
                recharge_cost += int(round(before_credits - after_credits))

        sector_after = _to_int(state_after.get("sector"))
        sector_before = _to_int(state_before.get("sector"))
        sector = sector_after if sector_after is not None else sector_before
        if sector == MEGA_PORT_SECTOR:
            mega_port_used_sector = sector
            max_warp = _to_int(state_after.get("max_warp"))
            if (
                before_warp is not None
                and after_warp is not None
                and max_warp is not None
                and after_warp > before_warp
                and after_warp >= max_warp
            ):
                recharge_to_full_at_mega = True

    summary_recharge_units = _to_int(summary.get("recharge_units_total"))
    summary_recharge_cost = _to_int(summary.get("recharge_cost_total"))
    summary_recharge_sector = _to_int(summary.get("recharge_sector"))
    recharge_units = max(recharge_units, summary_recharge_units or 0)
    recharge_cost = max(recharge_cost, summary_recharge_cost or 0)
    if summary_recharge_sector is not None:
        mega_port_used_sector = summary_recharge_sector
    recharge_to_full_at_mega = bool(summary.get("recharge_to_full_at_mega")) or recharge_to_full_at_mega

    initial_credits = _to_float(initial_state.get("credits"))
    if initial_credits is None:
        first_before = turns[0].get("state_before") if turns else {}
        initial_credits = _to_float((first_before or {}).get("credits"))
    final_credits = _to_float(summary.get("final_credits"))
    if final_credits is None and initial_credits is not None and realized_pnl is not None:
        final_credits = initial_credits + realized_pnl - recharge_cost
    if final_credits is None and turns:
        final_credits = _to_float((turns[-1].get("state_after") or {}).get("credits"))
    if final_credits is None:
        final_credits = initial_credits

    total_profit_credits: Optional[int] = None
    if initial_credits is not None and final_credits is not None:
        total_profit_credits = int(round(final_credits - initial_credits))

    report_truth: dict[str, Any] = {
        "start_sector": start_sector,
        "expected_finish_sector": expected_finish_sector,
        "actual_finish_sector": final_sector,
        "mega_port_sector": MEGA_PORT_SECTOR,
        "mega_port_name": MEGA_PORT_NAME,
        "mega_port_used_sector": mega_port_used_sector,
        "recharge_units": recharge_units,
        "recharge_cost": recharge_cost,
        "trade_port_count": len(successful_trade_ports),
        "total_profit_credits": total_profit_credits,
        "initial_credits": int(round(initial_credits)) if initial_credits is not None else None,
        "final_credits": int(round(final_credits)) if final_credits is not None else None,
    }
    report_accuracy: Optional[bool] = None
    report_accuracy_method = "llm_not_run"
    report_judge_reason: Optional[str] = None

    if report_judge is not None and finished_called:
        judged_accuracy, judge_reason = report_judge.judge(
            finished_message=finished_message,
            expected_finish_sector=expected_finish_sector,
            report_truth=report_truth,
        )
        report_judge_reason = judge_reason
        if judged_accuracy is not None:
            report_accuracy = judged_accuracy
            report_accuracy_method = "llm"
        else:
            report_accuracy_method = "llm_unparseable"
    elif finished_called:
        report_accuracy_method = "llm_unavailable"

    # Navigation quality metrics.
    total_moves = 0
    backtracking_count = 0
    visited = {start_sector}
    reached_first_mega = start_sector == MEGA_PORT_SECTOR
    moves_to_first_mega = 0 if reached_first_mega else None
    post_goal_moves = 0

    for call in all_calls:
        if call.get("name") != "move":
            continue
        if call.get("result_status") not in {"acknowledged", "success"}:
            continue
        sector_after = _to_int(call.get("sector_after"))
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
    reached_mega_but_left = bool(reached_mega_anytime and not final_sector_matches_start)

    round_trip_complete = bool(
        reached_mega_anytime and final_sector_matches_start and recharge_to_full_at_mega
    )
    at_least_one_trade = successful_trade_count >= 1
    objective_success = bool(
        finished_called
        and final_sector_matches_start
        and recharge_to_full_at_mega
    )

    # Success classes.
    strict_success = bool(
        objective_success
        and report_accuracy is True
    )
    lenient_success = bool(finished_called and round_trip_complete and coherent_report)
    clean_finish = terminal_reason == "finished_tool"

    if strict_success:
        terminal_class = "strict_success"
    elif lenient_success:
        terminal_class = "lenient_success_not_strict"
    elif terminal_reason == "no_tool_call_stall":
        terminal_class = "no_tool_stall"
    elif terminal_reason == "inference_failure":
        terminal_class = "inference_failure"
    elif terminal_reason == "watchdog_stop":
        terminal_class = "watchdog_stop"
    elif terminal_reason == "idle_timeout":
        terminal_class = "idle_timeout"
    elif terminal_reason == "max_turns_exhausted":
        terminal_class = "max_turns_exhausted"
    else:
        terminal_class = "other_failure"

    group_key = (
        f"{provider}|{model}|th={thinking}|tb={thinking_budget}|mt={max_tokens}|"
        f"base={openai_base_url or 'default'}|prompt={prompt_hash or 'unknown'}"
    )

    total_tool_calls = len(all_calls)
    tool_usage_counts = Counter(
        str(call.get("name"))
        for call in all_calls
        if isinstance(call.get("name"), str) and call.get("name")
    )
    family_counts: dict[str, int] = {}
    family_rates: dict[str, Optional[float]] = {}
    for family, tools in TOOL_FAMILIES.items():
        count = sum(tool_usage_counts.get(tool_name, 0) for tool_name in tools)
        family_counts[family] = count
        family_rates[family] = _rate(count, turns_executed)

    return {
        "file": str(path),
        "group_key": group_key,
        "provider": provider,
        "model": model,
        "thinking": thinking,
        "thinking_budget": thinking_budget,
        "max_tokens": max_tokens,
        "openai_base_url": openai_base_url,
        "turns_executed": turns_executed,
        "elapsed_ms": elapsed_ms,
        "strict_success": strict_success,
        "lenient_success": lenient_success,
        "objective_success": objective_success,
        "clean_finish": clean_finish,
        "terminal_reason": terminal_reason,
        "terminal_class": terminal_class,
        "finished_called": finished_called,
        "finished_message": finished_message,
        "coherent_report": coherent_report,
        "round_trip_complete": round_trip_complete,
        "expected_finish_sector": expected_finish_sector,
        "final_sector": final_sector,
        "final_sector_matches_start": final_sector_matches_start,
        "final_sector_is_mega": final_sector_is_mega,
        "reached_mega_anytime": reached_mega_anytime,
        "reached_mega_but_left": reached_mega_but_left,
        "reached_mega_but_not_back_to_start": reached_mega_but_left,
        "mega_port_used_sector": mega_port_used_sector,
        "recharge_units": recharge_units,
        "recharge_cost": recharge_cost,
        "recharge_to_full_at_mega": recharge_to_full_at_mega,
        "at_least_one_trade": at_least_one_trade,
        "bad_actions_count": bad_actions_count,
        "bad_action_rate": bad_action_rate,
        "no_tool_call_count": no_tool_call_count,
        "no_tool_call_rate": no_tool_call_rate,
        "post_finished_call_count": post_finished_call_count,
        "async_completion_timeout_count": async_completion_timeout_count,
        "multi_call_turn_count": multi_call_turn_count,
        "multi_call_turn_rate": _rate(multi_call_turn_count, turns_executed),
        "avg_tool_calls_per_turn": avg_tool_calls_per_turn,
        "max_tool_calls_per_turn": max_tool_calls_per_turn,
        "total_tool_calls": total_tool_calls,
        "inference_failure_count": inference_failure_count,
        "inference_failure_rate": inference_failure_rate,
        "invalid_move_count": invalid_move_count,
        "invalid_move_rate": invalid_move_rate,
        "invalid_trade_count": invalid_trade_count,
        "invalid_trade_rate": invalid_trade_rate,
        "unknown_action_count": unknown_action_count,
        "unknown_action_rate": unknown_action_rate,
        "tool_usage_counts": dict(tool_usage_counts),
        "tool_family_counts": family_counts,
        "tool_family_rates": family_rates,
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
        "total_profit_credits": total_profit_credits,
        "report_truth": report_truth,
        "report_accuracy": report_accuracy,
        "report_accuracy_method": report_accuracy_method,
        "report_judge_reason": report_judge_reason,
        "schema_version": payload.get("schema_version"),
        "run_id": metadata.get("run_id"),
        "git_sha": metadata.get("git_sha"),
        "prompt_hash": prompt_hash or None,
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

    def med(key: str) -> Optional[float]:
        metric_vals = vals(key)
        if not metric_vals:
            return None
        return float(median(metric_vals))

    return {
        "n": n,
        "strict_success": {"count": strict_count, **strict_ci.__dict__},
        "lenient_success": {"count": lenient_count, **lenient_ci.__dict__},
        "clean_finish": {"count": clean_count, **clean_ci.__dict__},
        "reached_mega_but_left": {"count": left_count, **left_ci.__dict__},
        "terminal_counts": dict(terminal_counts),
        "turns_median_iqr": _format_median_iqr(vals("turns_executed"), digits=1),
        "turns_median": med("turns_executed"),
        "bad_action_rate_median_iqr": _format_median_iqr(vals("bad_action_rate"), digits=3),
        "bad_action_rate_median": med("bad_action_rate"),
        "first_turn_latency_median_iqr_ms": _format_median_iqr(vals("first_turn_latency_ms"), digits=1),
        "warm_turn_p50_median_iqr_ms": _format_median_iqr(vals("warm_turn_p50_ms"), digits=1),
        "warm_turn_p90_median_iqr_ms": _format_median_iqr(vals("warm_turn_p90_ms"), digits=1),
        "warm_turn_p50_median_ms": med("warm_turn_p50_ms"),
        "warm_turn_p90_median_ms": med("warm_turn_p90_ms"),
        "decision_max_median_iqr_ms": _format_median_iqr(vals("decision_max_ms"), digits=1),
        "path_efficiency_median_iqr": _format_median_iqr(vals("path_efficiency_ratio"), digits=3),
        "realized_pnl_median_iqr": _format_median_iqr(vals("realized_pnl"), digits=1),
        "realized_pnl_median": med("realized_pnl"),
        "report_accuracy_rate": _rate(
            sum(1 for r in rows if r.get("report_accuracy") is True),
            sum(1 for r in rows if r.get("report_accuracy") is not None),
        ),
        "no_tool_call_rate_median_iqr": _format_median_iqr(vals("no_tool_call_rate"), digits=3),
        "inference_failure_rate_median_iqr": _format_median_iqr(vals("inference_failure_rate"), digits=3),
        "multi_call_turn_rate_median_iqr": _format_median_iqr(vals("multi_call_turn_rate"), digits=3),
        "avg_tool_calls_per_turn_median_iqr": _format_median_iqr(vals("avg_tool_calls_per_turn"), digits=3),
        "error_recovery_rate_median_iqr": _format_median_iqr(vals("error_recovery_rate"), digits=3),
        "invalid_move_rate_median_iqr": _format_median_iqr(vals("invalid_move_rate"), digits=3),
        "invalid_trade_rate_median_iqr": _format_median_iqr(vals("invalid_trade_rate"), digits=3),
        "post_goal_moves_median_iqr": _format_median_iqr(vals("post_goal_moves"), digits=1),
    }


def _write_markdown_table(out_path: Path, rows: list[dict[str, Any]], agg: dict[str, Any]) -> None:
    def fmt_pct(value: Optional[float]) -> str:
        if value is None:
            return ""
        return f"{value:.2%}"

    def fmt_num(value: Optional[float], digits: int = 1) -> str:
        if value is None:
            return ""
        return f"{value:.{digits}f}"

    lines = [
        "| Model | N | Turns (Median) | Strict Success | Lenient Success | Clean Finish | Bad Action Rate (Median) | Warm P50 ms (Median) | Warm P90 ms (Median) | P&L (Median) | Reached Mega But Not Back At Start |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def sort_key(group_key: str) -> tuple[float, float, float, str]:
        data = agg[group_key]
        strict_rate = data["strict_success"].get("rate")
        lenient_rate = data["lenient_success"].get("rate")
        p90_ms = data.get("warm_turn_p90_median_ms")

        strict_rank = float(strict_rate) if isinstance(strict_rate, (int, float)) else -1.0
        lenient_rank = float(lenient_rate) if isinstance(lenient_rate, (int, float)) else -1.0
        p90_rank = float(p90_ms) if isinstance(p90_ms, (int, float)) else float("inf")
        return (-strict_rank, -lenient_rank, p90_rank, group_key)

    for group_key in sorted(agg.keys(), key=sort_key):
        group_rows = [r for r in rows if r["group_key"] == group_key]
        first = group_rows[0]
        data = agg[group_key]

        strict = data["strict_success"]
        lenient = data["lenient_success"]
        clean = data["clean_finish"]
        left = data["reached_mega_but_left"]

        model_display = _variant_display_label(first)

        lines.append(
            "| "
            + f"{model_display} | {data['n']} | "
            + f"{fmt_num(data.get('turns_median'))} | "
            + f"{fmt_pct(strict['rate'])} | "
            + f"{fmt_pct(lenient['rate'])} | "
            + f"{fmt_pct(clean['rate'])} | "
            + f"{fmt_pct(data.get('bad_action_rate_median'))} | "
            + f"{fmt_num(data.get('warm_turn_p50_median_ms'))} | "
            + f"{fmt_num(data.get('warm_turn_p90_median_ms'))} | "
            + f"{fmt_num(data.get('realized_pnl_median'))} | "
            + f"{fmt_pct(left['rate'])} |"
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
        choices=["llm"],
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
                f"Missing judge API key: set env var {args.judge_api_key_env}."
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
        if payload.get("schema_version") != RUN_SCHEMA_VERSION:
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
                    "error": (
                        f"unsupported_schema_version: {payload.get('schema_version')} "
                        f"(expected {RUN_SCHEMA_VERSION})"
                    ),
                }
            )
            continue
        derived_rows.append(_derive_run_metrics(path, payload, report_judge))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in derived_rows:
        group_key = row.get("group_key")
        if group_key == "invalid":
            continue
        grouped[str(group_key)].append(row)

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
                "n",
                "turns_median",
                "strict_success_rate",
                "lenient_success_rate",
                "clean_finish_rate",
                "bad_action_rate_median",
                "warm_turn_p50_median_ms",
                "warm_turn_p90_median_ms",
                "realized_pnl_median",
                "reached_mega_but_left_rate",
                "terminal_counts",
            ]
        )

        def sort_key(group_key: str) -> tuple[float, float, float, str]:
            data = aggregate[group_key]
            strict_rate = data["strict_success"].get("rate")
            lenient_rate = data["lenient_success"].get("rate")
            p90_ms = data.get("warm_turn_p90_median_ms")

            strict_rank = float(strict_rate) if isinstance(strict_rate, (int, float)) else -1.0
            lenient_rank = float(lenient_rate) if isinstance(lenient_rate, (int, float)) else -1.0
            p90_rank = float(p90_ms) if isinstance(p90_ms, (int, float)) else float("inf")
            return (-strict_rank, -lenient_rank, p90_rank, group_key)

        for group_key in sorted(aggregate.keys(), key=sort_key):
            group_rows = grouped[group_key]
            first = group_rows[0]
            data = aggregate[group_key]
            strict = data["strict_success"]
            lenient = data["lenient_success"]
            clean = data["clean_finish"]
            left = data["reached_mega_but_left"]
            writer.writerow(
                [
                    group_key,
                    _variant_display_label(first),
                    data["n"],
                    data.get("turns_median"),
                    strict["rate"],
                    lenient["rate"],
                    clean["rate"],
                    data.get("bad_action_rate_median"),
                    data.get("warm_turn_p50_median_ms"),
                    data.get("warm_turn_p90_median_ms"),
                    data.get("realized_pnl_median"),
                    left["rate"],
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
