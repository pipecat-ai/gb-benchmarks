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
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any, Optional

DEFAULT_START_SECTOR = 3080
MEGA_PORT_SECTOR = 1611
MEGA_PORT_NAME = "MEGA SSS"
RUN_SCHEMA_VERSION = "mini_rl_run.v3"
SCORE_RUBRIC_VERSION = "port_to_port_primary_v1"

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
    2833: [4884],
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

# Precomputed correct answers for info-retrieval task
def _bfs_distance(start: int, end: int) -> int | None:
    """BFS shortest path distance."""
    from collections import deque
    if start == end:
        return 0
    visited = {start}
    queue = deque([(start, 0)])
    while queue:
        sector, dist = queue.popleft()
        for neighbor in GRAPH.get(sector, []):
            if neighbor == end:
                return dist + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))
    return None

def _ports_selling_commodity_within_hops(start: int, commodity: str, max_hops: int) -> list[int]:
    """Find ports that sell a commodity within max_hops of start."""
    from collections import deque
    result = []
    visited = {start}
    queue = deque([(start, 0)])
    while queue:
        sector, dist = queue.popleft()
        if dist <= max_hops and sector in PORT_MARKETS:
            if commodity in PORT_MARKETS[sector].get("sells", {}):
                result.append(sector)
        if dist < max_hops:
            for neighbor in GRAPH.get(sector, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
    return result

INFO_RETRIEVAL_ANSWERS = {
    "ports_selling_qf_within_5": len(_ports_selling_commodity_within_hops(3080, "quantum_foam", 5)),
    "shortest_path_to_1928": _bfs_distance(3080, 1928),
    "port_type_2831": "SSB",
    "full_recharge_cost": 1000,  # 500 units * 2 credits
    "empty_holds": 20,  # 30 total - 10 QF starting cargo
}


def _safe_mean(values: list) -> Optional[float]:
    nums = [v for v in values if isinstance(v, (int, float))]
    return sum(nums) / len(nums) if nums else None


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


def _bfs_path(start: int, target: int) -> Optional[list[int]]:
    if start == target:
        return [start]
    frontier = [start]
    parent: dict[int, Optional[int]] = {start: None}
    while frontier:
        nxt_frontier: list[int] = []
        for node in frontier:
            for nbr in GRAPH.get(node, []):
                if nbr in parent:
                    continue
                parent[nbr] = node
                if nbr == target:
                    path = [target]
                    while parent[path[-1]] is not None:
                        path.append(parent[path[-1]])
                    path.reverse()
                    return path
                nxt_frontier.append(nbr)
        frontier = nxt_frontier
    return None


def _canonical_required_course_sectors(start_sector: int) -> list[int]:
    outbound = _bfs_path(start_sector, MEGA_PORT_SECTOR)
    if not outbound:
        return [start_sector]
    return outbound + list(reversed(outbound[:-1]))


def _required_course_port_visits(start_sector: int) -> list[int]:
    return [sector for sector in _canonical_required_course_sectors(start_sector) if sector in PORT_MARKETS]


def _cargo_tuple_from_dict(cargo: dict[str, Any]) -> tuple[int, int, int]:
    return tuple(max(0, _to_int(cargo.get(name)) or 0) for name in ("quantum_foam", "retro_organics", "neuro_symbolics"))


def _cargo_used_holds(cargo: tuple[int, int, int]) -> int:
    return sum(cargo)


@lru_cache(maxsize=None)
def _enumerate_port_trade_outcomes_cached(
    sector: int,
    start_cargo: tuple[int, int, int],
    start_credits: int,
    holds_total: int,
) -> tuple[tuple[tuple[int, int, int], int], ...]:
    market = PORT_MARKETS.get(sector)
    if market is None:
        return ((start_cargo, start_credits),)

    best_by_cargo: dict[tuple[int, int, int], int] = {start_cargo: start_credits}
    queue: list[tuple[int, int, int]] = [start_cargo]

    while queue:
        cargo = queue.pop()
        credits = best_by_cargo[cargo]
        used_holds = _cargo_used_holds(cargo)
        for idx, commodity in enumerate(("quantum_foam", "retro_organics", "neuro_symbolics")):
            qty = cargo[idx]
            buy_price = market["buys"].get(commodity)
            if buy_price is not None and qty > 0:
                for amount in range(1, qty + 1):
                    next_cargo = list(cargo)
                    next_cargo[idx] -= amount
                    next_cargo_key = tuple(next_cargo)
                    next_credits = credits + (buy_price * amount)
                    if next_credits > best_by_cargo.get(next_cargo_key, -1):
                        best_by_cargo[next_cargo_key] = next_credits
                        queue.append(next_cargo_key)

            sell_price = market["sells"].get(commodity)
            if sell_price is not None:
                max_buy_qty = min(holds_total - used_holds, credits // sell_price)
                for amount in range(1, max_buy_qty + 1):
                    next_cargo = list(cargo)
                    next_cargo[idx] += amount
                    next_cargo_key = tuple(next_cargo)
                    next_credits = credits - (sell_price * amount)
                    if next_credits > best_by_cargo.get(next_cargo_key, -1):
                        best_by_cargo[next_cargo_key] = next_credits
                        queue.append(next_cargo_key)

    return tuple(sorted(best_by_cargo.items()))


def _enumerate_port_trade_outcomes(
    *,
    sector: int,
    start_cargo: tuple[int, int, int],
    start_credits: int,
    holds_total: int,
) -> dict[tuple[int, int, int], int]:
    market = PORT_MARKETS.get(sector)
    if market is None:
        return {start_cargo: start_credits}
    max_unit_price = max(market["sells"].values(), default=0)
    if max_unit_price > 0:
        capped_credits = min(start_credits, holds_total * max_unit_price)
    else:
        capped_credits = start_credits
    return dict(
        _enumerate_port_trade_outcomes_cached(
            sector,
            start_cargo,
            capped_credits,
            holds_total,
        )
    )


def _compute_required_course_trade_oracle(
    *,
    start_sector: int,
    initial_state: dict[str, Any],
    turns: list[dict[str, Any]],
) -> dict[str, Any]:
    required_port_visits = _required_course_port_visits(start_sector)
    if not required_port_visits:
        return {
            "required_course_port_visits": [],
            "required_course_optimal_trade_value": 0,
            "beneficial_visit_indexes": [],
            "required_course_recharge_cost": 0,
        }

    first_before = turns[0].get("state_before") if turns else {}
    start_credits = _to_int(initial_state.get("credits"))
    if start_credits is None:
        start_credits = _to_int((first_before or {}).get("credits")) or 0

    initial_cargo = initial_state.get("cargo") if isinstance(initial_state.get("cargo"), dict) else {}
    if not initial_cargo and isinstance(first_before, dict):
        initial_cargo = first_before.get("cargo") if isinstance(first_before.get("cargo"), dict) else {}
    cargo_tuple = _cargo_tuple_from_dict(initial_cargo if isinstance(initial_cargo, dict) else {})

    empty_holds = _to_int(initial_state.get("empty_holds"))
    used_holds = _to_int(initial_state.get("used_holds"))
    holds_total = None
    if empty_holds is not None and used_holds is not None:
        holds_total = empty_holds + used_holds
    if holds_total is None and isinstance(first_before, dict):
        cargo_before = first_before.get("cargo") if isinstance(first_before.get("cargo"), dict) else {}
        empty_before = _to_int(first_before.get("empty_holds"))
        if empty_before is not None:
            holds_total = empty_before + sum(_cargo_tuple_from_dict(cargo_before))
    if holds_total is None:
        holds_total = max(30, _cargo_used_holds(cargo_tuple))

    start_warp = _to_int(initial_state.get("warp"))
    max_warp = _to_int(initial_state.get("max_warp"))
    if start_warp is None and isinstance(first_before, dict):
        start_warp = _to_int(first_before.get("warp"))
    if max_warp is None and isinstance(first_before, dict):
        max_warp = _to_int(first_before.get("max_warp"))
    if start_warp is None:
        start_warp = 500
    if max_warp is None:
        max_warp = max(start_warp, 500)

    outbound = _bfs_path(start_sector, MEGA_PORT_SECTOR) or [start_sector]
    outbound_hops = max(0, len(outbound) - 1)
    warp_at_mega = max(0, start_warp - (3 * outbound_hops))
    required_course_recharge_cost = max(0, max_warp - warp_at_mega) * 2

    # Fast path for the current benchmark world. The required course is fixed and
    # the optimal on-course policy is exact and easy to compute directly:
    # sell starting QF/NS at 3080, then fill holds with NS at 4874/1611 and
    # liquidate at 2831/3080. RO has no profitable on-course exit.
    if required_port_visits == [3080, 4874, 2831, 1611, 2831, 4874, 3080]:
        credits = start_credits
        qf, ro, ns = cargo_tuple
        beneficial_visit_indexes: list[int] = []
        trade_value = 0

        def record_trade(visit_index: int) -> None:
            if visit_index not in beneficial_visit_indexes:
                beneficial_visit_indexes.append(visit_index)

        if qf > 0:
            credits += 33 * qf
            trade_value += 33 * qf
            qf = 0
            record_trade(0)
        if ns > 0:
            credits += 52 * ns
            trade_value += 52 * ns
            ns = 0
            record_trade(0)

        for visit_index, sector in enumerate(required_port_visits[1:], start=1):
            used_holds = qf + ro + ns
            empty_holds_now = max(0, holds_total - used_holds)

            if sector == 1611:
                credits = max(0, credits - required_course_recharge_cost)

            if sector in {4874, 1611}:
                qty = min(empty_holds_now, credits // 30)
                if qty > 0:
                    ns += qty
                    credits -= 30 * qty
                    trade_value -= 30 * qty
                    record_trade(visit_index)
                continue

            if sector == 2831:
                if ns > 0:
                    credits += 52 * ns
                    trade_value += 52 * ns
                    ns = 0
                    record_trade(visit_index)
                continue

            if sector == 3080:
                sold_any = False
                if ns > 0:
                    credits += 52 * ns
                    trade_value += 52 * ns
                    ns = 0
                    sold_any = True
                if qf > 0:
                    credits += 33 * qf
                    trade_value += 33 * qf
                    qf = 0
                    sold_any = True
                if sold_any:
                    record_trade(visit_index)

        return {
            "required_course_port_visits": required_port_visits,
            "required_course_optimal_trade_value": trade_value,
            "beneficial_visit_indexes": beneficial_visit_indexes,
            "required_course_recharge_cost": required_course_recharge_cost,
        }

    states: dict[tuple[int, int, int], tuple[int, int]] = {cargo_tuple: (start_credits, 0)}
    traces: list[dict[tuple[int, int, int], tuple[tuple[int, int, int], bool]]] = []

    for sector in required_port_visits:
        next_states: dict[tuple[int, int, int], tuple[int, int]] = {}
        next_trace: dict[tuple[int, int, int], tuple[tuple[int, int, int], bool]] = {}

        for prior_cargo, (prior_credits, prior_trade_visit_count) in states.items():
            outcomes = _enumerate_port_trade_outcomes(
                sector=sector,
                start_cargo=prior_cargo,
                start_credits=prior_credits,
                holds_total=holds_total,
            )
            for next_cargo, credits_after_trade in outcomes.items():
                used_trade = next_cargo != prior_cargo or credits_after_trade != prior_credits
                next_credits = credits_after_trade
                if sector == MEGA_PORT_SECTOR:
                    if next_credits < required_course_recharge_cost:
                        continue
                    next_credits -= required_course_recharge_cost
                candidate = (next_credits, prior_trade_visit_count + (1 if used_trade else 0))
                best = next_states.get(next_cargo)
                if best is None or candidate[0] > best[0] or (
                    candidate[0] == best[0] and candidate[1] > best[1]
                ):
                    next_states[next_cargo] = candidate
                    next_trace[next_cargo] = (prior_cargo, used_trade)

        states = next_states
        traces.append(next_trace)

    if not states:
        return {
            "required_course_port_visits": required_port_visits,
            "required_course_optimal_trade_value": 0,
            "beneficial_visit_indexes": [],
            "required_course_recharge_cost": required_course_recharge_cost,
        }

    best_cargo, (best_final_credits, _) = max(
        states.items(),
        key=lambda item: (item[1][0], item[1][1], -_cargo_used_holds(item[0])),
    )

    beneficial_visit_indexes: list[int] = []
    current_cargo = best_cargo
    for visit_index in range(len(traces) - 1, -1, -1):
        prior_cargo, used_trade = traces[visit_index][current_cargo]
        if used_trade:
            beneficial_visit_indexes.append(visit_index)
        current_cargo = prior_cargo
    beneficial_visit_indexes.reverse()

    required_course_optimal_trade_value = best_final_credits - start_credits + required_course_recharge_cost
    return {
        "required_course_port_visits": required_port_visits,
        "required_course_optimal_trade_value": required_course_optimal_trade_value,
        "beneficial_visit_indexes": beneficial_visit_indexes,
        "required_course_recharge_cost": required_course_recharge_cost,
    }


def _trade_pnl_for_call(call: dict[str, Any]) -> Optional[int]:
    args = call.get("args") if isinstance(call.get("args"), dict) else {}
    trade_type = str(args.get("trade_type") or "").strip().lower()
    commodity = _normalize_commodity(args.get("commodity"))
    quantity = _to_int(args.get("quantity"))
    sector = _to_int(call.get("sector_before"))
    if trade_type not in {"buy", "sell"} or commodity is None or quantity is None or sector is None:
        return None
    market = PORT_MARKETS.get(sector)
    if market is None:
        return None
    if trade_type == "buy":
        price = market["sells"].get(commodity)
        if price is None:
            return None
        return -(price * quantity)
    price = market["buys"].get(commodity)
    if price is None:
        return None
    return price * quantity


def _compute_actual_trade_value_by_course(
    *,
    start_sector: int,
    turn_call_contexts: list[list[dict[str, Any]]],
    required_port_visits: list[int],
) -> dict[str, Any]:
    active_visit_index = 0 if required_port_visits and required_port_visits[0] == start_sector else None
    final_visit_index = len(required_port_visits) - 1
    course_closed = False
    on_course_realized_trade_value = 0
    off_course_trade_value = 0
    traded_visit_indexes: set[int] = set()

    for call in [call for contexts in turn_call_contexts for call in contexts]:
        if (
            call.get("name") == "move"
            and str(call.get("result_status") or "") in {"acknowledged", "success"}
        ):
            if active_visit_index == final_visit_index and _to_int(call.get("sector_before")) == start_sector:
                course_closed = True
            if not course_closed:
                next_visit_index = 0 if active_visit_index is None else active_visit_index + 1
                sector_after = _to_int(call.get("sector_after"))
                if (
                    sector_after is not None
                    and next_visit_index < len(required_port_visits)
                    and sector_after == required_port_visits[next_visit_index]
                ):
                    active_visit_index = next_visit_index
            continue

        if (
            call.get("name") == "trade"
            and str(call.get("result_status") or "") in {"acknowledged", "success"}
        ):
            pnl = _trade_pnl_for_call(call)
            if pnl is None:
                continue
            is_on_course = bool(
                not course_closed
                and active_visit_index is not None
                and _to_int(call.get("sector_before")) == required_port_visits[active_visit_index]
            )
            if is_on_course:
                traded_visit_indexes.add(active_visit_index)
                on_course_realized_trade_value += pnl
            else:
                off_course_trade_value += pnl

    return {
        "on_course_realized_trade_value": on_course_realized_trade_value,
        "off_course_trade_value": off_course_trade_value,
        "traded_visit_indexes": sorted(traded_visit_indexes),
    }


def _count_avoidable_tool_calls(turn_call_contexts: list[list[dict[str, Any]]]) -> dict[str, int]:
    repeated_query_tools = {"my_status", "local_map_region", "list_known_ports", "load_game_info", "plot_course"}
    state_changing_tools = {
        "move",
        "trade",
        "recharge_warp_power",
        "dump_cargo",
        "salvage_collect",
        "transfer_warp_power",
        "purchase_fighters",
        "place_fighters",
        "collect_fighters",
        "create_corporation",
        "join_corporation",
        "leave_corporation",
        "kick_corporation_member",
        "purchase_ship",
        "rename_ship",
        "bank_deposit",
        "bank_withdraw",
        "transfer_credits",
        "combat_initiate",
        "combat_action",
    }
    redundant_info_call_count = 0
    unnecessary_tool_call_count = 0
    state_revision = 0
    seen_at_revision: dict[tuple[str, str, str], int] = {}

    for call in [call for contexts in turn_call_contexts for call in contexts]:
        name = str(call.get("name") or "")
        result_status = str(call.get("result_status") or "")
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        signature = (
            name,
            str(_to_int(call.get("sector_before")) or ""),
            json.dumps(args, sort_keys=True),
        )
        if name in repeated_query_tools and result_status in {"acknowledged", "success"}:
            if seen_at_revision.get(signature) == state_revision:
                redundant_info_call_count += 1
                unnecessary_tool_call_count += 1
            else:
                seen_at_revision[signature] = state_revision
        if name in state_changing_tools and result_status in {"acknowledged", "success"}:
            state_revision += 1

    return {
        "redundant_info_call_count": redundant_info_call_count,
        "unnecessary_tool_call_count": unnecessary_tool_call_count,
    }


def _message_mentions_number_window(message: str, *, keywords: tuple[str, ...], target: int) -> bool:
    lowered = message.lower()
    for keyword in keywords:
        start = 0
        while True:
            idx = lowered.find(keyword, start)
            if idx == -1:
                break
            window = message[max(0, idx - 32) : idx + len(keyword) + 48]
            numbers = [int(match.group(0)) for match in re.finditer(r"-?\d+", window)]
            if target in numbers:
                return True
            start = idx + len(keyword)
    return False


def _message_mentions_profit_value(message: str, target: Optional[int]) -> tuple[bool, bool]:
    if target is None:
        return False, False
    lowered = message.lower()
    keywords = ("profit", "net", "result", "gain", "loss")
    present = any(keyword in lowered for keyword in keywords)
    if not present:
        return False, False
    if _message_mentions_number_window(message, keywords=keywords, target=target):
        return True, True
    if target < 0 and _message_mentions_number_window(message, keywords=("loss",), target=abs(target)):
        return True, True
    if target > 0 and _message_mentions_number_window(message, keywords=("profit", "gain"), target=target):
        return True, True
    if target == 0 and re.search(r"\b0\b", message):
        return True, True
    return True, False


def _message_mentions_recharge_cost_value(message: str, target: Optional[int]) -> tuple[bool, bool]:
    if target is None:
        return False, False
    lowered = message.lower()
    recharge_keywords = ("recharg", "warp", "topped off", "topped up")
    cost_keywords = ("cost", "spent", "pay", "paid", "price", "for")
    present = False

    for keyword in recharge_keywords:
        start = 0
        while True:
            idx = lowered.find(keyword, start)
            if idx == -1:
                break
            window = message[max(0, idx - 40) : idx + len(keyword) + 80]
            window_lower = window.lower()
            if any(cost_keyword in window_lower for cost_keyword in cost_keywords):
                present = True
                numbers = [int(match.group(0)) for match in re.finditer(r"-?\d+", window)]
                if target in numbers:
                    return True, True
            start = idx + len(keyword)

    return present, False


def _compute_report_element_verdicts(
    *,
    finished_message: str,
    report_truth: dict[str, Any],
) -> dict[str, dict[str, bool]]:
    if not finished_message.strip():
        return {
            "mega_port_used": {"present": False, "accurate": False},
            "recharge_amount": {"present": False, "accurate": False},
            "recharge_cost": {"present": False, "accurate": False},
            "ports_traded": {"present": False, "accurate": False},
            "total_profit": {"present": False, "accurate": False},
        }

    lowered = finished_message.lower()
    mega_present = (
        "mega" in lowered
        or "mega sss" in lowered
        or str(report_truth.get("mega_port_sector") or MEGA_PORT_SECTOR) in lowered
    )
    mega_accurate = mega_present

    recharge_units = _to_int(report_truth.get("recharge_units")) or 0
    recharge_cost = _to_int(report_truth.get("recharge_cost")) or 0
    ports_traded = _to_int(report_truth.get("trade_port_count")) or 0
    total_profit = _to_int(report_truth.get("total_profit_credits"))

    recharge_amount_present = any(token in lowered for token in ("recharg", "warp", "topped off", "topped up"))
    recharge_amount_accurate = recharge_amount_present and _message_mentions_number_window(
        finished_message,
        keywords=("recharg", "warp", "topped off", "topped up"),
        target=recharge_units,
    )

    recharge_cost_present, recharge_cost_accurate = _message_mentions_recharge_cost_value(
        finished_message,
        recharge_cost,
    )

    ports_present = ("port" in lowered or "ports" in lowered) and ("trade" in lowered or "traded" in lowered)
    ports_accurate = ports_present and _message_mentions_number_window(
        finished_message,
        keywords=("port", "ports", "trade", "traded"),
        target=ports_traded,
    )

    profit_present, profit_accurate = _message_mentions_profit_value(finished_message, total_profit)

    return {
        "mega_port_used": {"present": mega_present, "accurate": mega_accurate},
        "recharge_amount": {"present": recharge_amount_present, "accurate": recharge_amount_accurate},
        "recharge_cost": {"present": recharge_cost_present, "accurate": recharge_cost_accurate},
        "ports_traded": {"present": ports_present, "accurate": ports_accurate},
        "total_profit": {"present": profit_present, "accurate": profit_accurate},
    }


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


def _extract_sectors_visited(all_calls: list[dict[str, Any]]) -> list[int]:
    """Extract all sector_after values from successful move calls."""
    sectors = []
    for call in all_calls:
        if call.get("name") != "move":
            continue
        if call.get("result_status") not in {"acknowledged", "success"}:
            continue
        sector_after = _to_int(call.get("sector_after"))
        if sector_after is not None:
            sectors.append(sector_after)
    return sectors


def _base_tool_discipline(
    hallucinated_tool_count: int,
    invalid_move_count: int,
    invalid_trade_count: int,
    no_tool_call_count: int,
    unnecessary_tool_call_count: int,
) -> int:
    return max(
        0,
        15
        - (2 * hallucinated_tool_count)
        - invalid_move_count
        - invalid_trade_count
        - (2 * no_tool_call_count)
        - unnecessary_tool_call_count,
    )


def _score_trade_arbitrage(
    *,
    finished_called: bool,
    finished_message: Optional[str],
    start_sector: int,
    final_sector: int,
    turns_executed: int,
    total_moves: int,
    successful_trade_count: int,
    successful_trade_ports: set[int],
    total_profit_credits: Optional[int],
    initial_credits: Optional[int],
    final_credits: Optional[int],
    all_calls: list[dict[str, Any]],
    hallucinated_tool_count: int,
    invalid_move_count: int,
    invalid_trade_count: int,
    no_tool_call_count: int,
    unnecessary_tool_call_count: int,
    reached_mega_anytime: bool,
) -> dict[str, Any]:
    profit = total_profit_credits or 0
    returned = final_sector == start_sector

    # Mission (40)
    mission_completion_score = (
        15 * int(finished_called)
        + 15 * int(returned)
        + 10 * int(profit > 0)
    )

    # Trade Quality (15)
    if profit >= 2000:
        trade_quality_score = 15
    elif profit >= 1000:
        trade_quality_score = 10
    elif profit >= 500:
        trade_quality_score = 7
    elif profit >= 100:
        trade_quality_score = 4
    elif profit > 0:
        trade_quality_score = 2
    else:
        trade_quality_score = 0

    # Efficiency (15): ratio of productive turns (move/trade/finished) to total turns.
    # Info-gathering (plot_course, list_known_ports, etc.) is sensible planning, not waste.
    productive_actions = sum(
        1 for call in all_calls
        if call.get("result_status") in {"acknowledged", "success"}
        and call.get("name") in {"move", "trade", "finished"}
    )
    ratio = productive_actions / max(turns_executed, 1)
    if ratio >= 0.75:
        path_efficiency_score = 15
    elif ratio >= 0.60:
        path_efficiency_score = 12
    elif ratio >= 0.50:
        path_efficiency_score = 10
    elif ratio >= 0.40:
        path_efficiency_score = 7
    elif ratio >= 0.30:
        path_efficiency_score = 4
    else:
        path_efficiency_score = 0

    # Tool Discipline (15)
    tool_discipline_score = _base_tool_discipline(
        hallucinated_tool_count, invalid_move_count, invalid_trade_count,
        no_tool_call_count, unnecessary_tool_call_count,
    )

    # Report (15)
    report_quality_score = 0
    msg = finished_message or ""
    lowered = msg.lower()
    elements_present = 0
    if re.search(r"start", lowered) and re.search(r"\d+", msg):
        elements_present += 1
    if re.search(r"end", lowered) and re.search(r"\d+", msg):
        elements_present += 1
    if (re.search(r"profit|loss", lowered)) and re.search(r"\d+", msg):
        elements_present += 1
    if re.search(r"port|traded|trade", lowered):
        elements_present += 1
    if elements_present >= 3:
        report_quality_score = 5
    # Check numbers close to actual values
    numbers_close = 0
    if total_profit_credits is not None and _message_mentions_number_window(msg, keywords=("profit", "loss", "net"), target=abs(total_profit_credits)):
        numbers_close += 1
    if initial_credits is not None and _message_mentions_number_window(msg, keywords=("start", "initial"), target=initial_credits):
        numbers_close += 1
    if final_credits is not None and _message_mentions_number_window(msg, keywords=("end", "final"), target=final_credits):
        numbers_close += 1
    if numbers_close >= 2:
        report_quality_score = 15
    elif numbers_close >= 1:
        report_quality_score = max(report_quality_score, 10)

    task_complete = bool(finished_called and returned and profit > 0)

    return {
        "mission_completion_score": mission_completion_score,
        "trade_quality_score": trade_quality_score,
        "path_efficiency_score": path_efficiency_score,
        "tool_discipline_score": tool_discipline_score,
        "report_quality_score": report_quality_score,
        "task_complete": task_complete,
    }


def _score_explore_fuel(
    *,
    finished_called: bool,
    finished_message: Optional[str],
    start_sector: int,
    final_sector: int,
    turns_executed: int,
    total_moves: int,
    successful_trade_count: int,
    successful_trade_ports: set[int],
    total_profit_credits: Optional[int],
    initial_credits: Optional[int],
    final_credits: Optional[int],
    all_calls: list[dict[str, Any]],
    hallucinated_tool_count: int,
    invalid_move_count: int,
    invalid_trade_count: int,
    no_tool_call_count: int,
    unnecessary_tool_call_count: int,
    reached_mega_anytime: bool,
) -> dict[str, Any]:
    move_sectors = _extract_sectors_visited(all_calls)
    sectors_visited_set = set(move_sectors)
    sectors_visited_set.add(start_sector)
    new_sectors_count = len(sectors_visited_set) - 1  # subtract start sector
    total_moves_count = len(move_sectors)
    returned = final_sector == start_sector

    # Mission (40)
    mission_completion_score = (
        15 * int(finished_called)
        + 15 * int(returned)
        + 10 * int(new_sectors_count >= 5)
    )

    # Quality (15): how many new sectors
    if new_sectors_count >= 15:
        trade_quality_score = 15
    elif new_sectors_count >= 12:
        trade_quality_score = 12
    elif new_sectors_count >= 10:
        trade_quality_score = 10
    elif new_sectors_count >= 7:
        trade_quality_score = 7
    elif new_sectors_count >= 5:
        trade_quality_score = 5
    elif new_sectors_count >= 3:
        trade_quality_score = 3
    elif new_sectors_count >= 1:
        trade_quality_score = 1
    else:
        trade_quality_score = 0

    # Efficiency (15): exploration ratio
    ratio = new_sectors_count / max(total_moves_count, 1)
    if ratio >= 0.8:
        path_efficiency_score = 15
    elif ratio >= 0.6:
        path_efficiency_score = 12
    elif ratio >= 0.5:
        path_efficiency_score = 10
    elif ratio >= 0.3:
        path_efficiency_score = 7
    elif ratio >= 0.2:
        path_efficiency_score = 4
    else:
        path_efficiency_score = 2

    # Tool Discipline (15)
    tool_discipline_score = _base_tool_discipline(
        hallucinated_tool_count, invalid_move_count, invalid_trade_count,
        no_tool_call_count, unnecessary_tool_call_count,
    )

    # Report (15)
    report_quality_score = 0
    msg = finished_message or ""
    lowered = msg.lower()
    elements = 0
    if (re.search(r"sector|discover", lowered)) and re.search(r"\d+", msg):
        elements += 1
    if (re.search(r"warp|remaining|fuel", lowered)) and re.search(r"\d+", msg):
        elements += 1
    if re.search(r"visit|explor", lowered):
        elements += 1
    report_quality_score = min(15, elements * 5)

    task_complete = bool(
        finished_called and returned and new_sectors_count >= 5
    )

    return {
        "mission_completion_score": mission_completion_score,
        "trade_quality_score": trade_quality_score,
        "path_efficiency_score": path_efficiency_score,
        "tool_discipline_score": tool_discipline_score,
        "report_quality_score": report_quality_score,
        "task_complete": task_complete,
    }


def _score_info_retrieval(
    *,
    finished_called: bool,
    finished_message: Optional[str],
    start_sector: int,
    final_sector: int,
    turns_executed: int,
    total_moves: int,
    successful_trade_count: int,
    successful_trade_ports: set[int],
    total_profit_credits: Optional[int],
    initial_credits: Optional[int],
    final_credits: Optional[int],
    all_calls: list[dict[str, Any]],
    hallucinated_tool_count: int,
    invalid_move_count: int,
    invalid_trade_count: int,
    no_tool_call_count: int,
    unnecessary_tool_call_count: int,
    reached_mega_anytime: bool,
) -> dict[str, Any]:
    msg = finished_message or ""
    move_sectors = _extract_sectors_visited(all_calls)
    total_moves_count = len(move_sectors)

    # Count correct answers
    correct = 0
    answers_present = 0

    # ports_selling_qf_within_5
    target_count = INFO_RETRIEVAL_ANSWERS["ports_selling_qf_within_5"]
    if _message_mentions_number_window(msg, keywords=("port", "quantum", "sell"), target=target_count):
        correct += 1
        answers_present += 1
    elif re.search(r"quantum|foam|port.*sell", msg.lower()):
        answers_present += 1

    # shortest_path_to_1928
    target_dist = INFO_RETRIEVAL_ANSWERS["shortest_path_to_1928"]
    if target_dist is not None and _message_mentions_number_window(msg, keywords=("shortest", "path", "distance", "hop", "1928"), target=target_dist):
        correct += 1
        answers_present += 1
    elif re.search(r"1928|shortest|path|distance", msg.lower()):
        answers_present += 1

    # port_type_2831
    if re.search(r"SSB", msg, re.IGNORECASE):
        correct += 1
        answers_present += 1
    elif re.search(r"2831|port.*type", msg.lower()):
        answers_present += 1

    # full_recharge_cost
    target_cost = INFO_RETRIEVAL_ANSWERS["full_recharge_cost"]
    if _message_mentions_number_window(msg, keywords=("recharge", "cost", "warp"), target=target_cost):
        correct += 1
        answers_present += 1
    elif re.search(r"recharge|cost|warp", msg.lower()):
        answers_present += 1

    # empty_holds
    target_holds = INFO_RETRIEVAL_ANSWERS["empty_holds"]
    if _message_mentions_number_window(msg, keywords=("hold", "cargo", "empty", "space"), target=target_holds):
        correct += 1
        answers_present += 1
    elif re.search(r"hold|cargo|empty|space", msg.lower()):
        answers_present += 1

    # Mission (40): 8 per correct answer
    mission_completion_score = min(40, correct * 8)

    # Quality (15): questions answered
    if correct >= 5:
        trade_quality_score = 15
    elif correct >= 4:
        trade_quality_score = 12
    elif correct >= 3:
        trade_quality_score = 9
    elif correct >= 2:
        trade_quality_score = 6
    elif correct >= 1:
        trade_quality_score = 3
    else:
        trade_quality_score = 0

    # Efficiency (15): penalize moves
    path_efficiency_score = max(0, 15 - 5 * total_moves_count)

    # Tool Discipline (15)
    tool_discipline_score = _base_tool_discipline(
        hallucinated_tool_count, invalid_move_count, invalid_trade_count,
        no_tool_call_count, unnecessary_tool_call_count,
    )

    # Report (15): 3 per answer present in message
    report_quality_score = min(15, answers_present * 3)

    task_complete = bool(finished_called and total_moves_count == 0 and correct >= 4)

    return {
        "mission_completion_score": mission_completion_score,
        "trade_quality_score": trade_quality_score,
        "path_efficiency_score": path_efficiency_score,
        "tool_discipline_score": tool_discipline_score,
        "report_quality_score": report_quality_score,
        "task_complete": task_complete,
    }


def _score_scavenger_hunt(
    *,
    finished_called: bool,
    finished_message: Optional[str],
    start_sector: int,
    final_sector: int,
    turns_executed: int,
    total_moves: int,
    successful_trade_count: int,
    successful_trade_ports: set[int],
    total_profit_credits: Optional[int],
    initial_credits: Optional[int],
    final_credits: Optional[int],
    all_calls: list[dict[str, Any]],
    hallucinated_tool_count: int,
    invalid_move_count: int,
    invalid_trade_count: int,
    no_tool_call_count: int,
    unnecessary_tool_call_count: int,
    reached_mega_anytime: bool,
) -> dict[str, Any]:
    from itertools import permutations

    required_sectors = {1928, 4874, 2831}
    move_sectors = _extract_sectors_visited(all_calls)
    sectors_visited_set = set(move_sectors)
    returned = final_sector == start_sector

    # Check which required sectors were visited
    visited_required = required_sectors & sectors_visited_set

    # Check which had successful buy trades
    buy_trade_sectors = set()
    for call in all_calls:
        call_args = call.get("args") if isinstance(call.get("args"), dict) else {}
        if (
            call.get("name") == "trade"
            and call.get("result_status") in {"acknowledged", "success"}
            and call_args.get("trade_type") == "buy"
        ):
            sector = _to_int(call.get("sector_before"))
            if sector in required_sectors:
                buy_trade_sectors.add(sector)

    # Compute optimal TSP route
    targets = list(required_sectors)
    best_total = float("inf")
    for perm in permutations(targets):
        total = 0
        current = start_sector
        valid = True
        for t in perm:
            d = _bfs_distance(current, t)
            if d is None:
                valid = False
                break
            total += d
            current = t
        if valid:
            d_back = _bfs_distance(current, start_sector)
            if d_back is not None:
                total += d_back
                best_total = min(best_total, total)
    optimal_moves = best_total if best_total < float("inf") else 20
    total_moves_count = len(move_sectors)

    # Mission (40): 10 per required sector visited + 10 for return
    mission_completion_score = 10 * len(visited_required) + 10 * int(returned)

    # Quality (15): 5 per port with successful buy trade
    trade_quality_score = min(15, 5 * len(buy_trade_sectors))

    # Efficiency (15)
    extra = max(0, total_moves_count - optimal_moves)
    path_efficiency_score = max(0, 15 - extra)

    # Tool Discipline (15)
    tool_discipline_score = _base_tool_discipline(
        hallucinated_tool_count, invalid_move_count, invalid_trade_count,
        no_tool_call_count, unnecessary_tool_call_count,
    )

    # Report (15)
    report_quality_score = 0
    msg = finished_message or ""
    lowered = msg.lower()
    if re.search(r"order|visit|route", lowered):
        report_quality_score += 5
    if re.search(r"purchas|bought|buy|trade", lowered):
        report_quality_score += 5
    if re.search(r"move|warp|hop|step", lowered):
        report_quality_score += 5

    task_complete = bool(
        finished_called
        and len(visited_required) == 3
        and len(buy_trade_sectors) == 3
        and returned
    )

    return {
        "mission_completion_score": mission_completion_score,
        "trade_quality_score": trade_quality_score,
        "path_efficiency_score": path_efficiency_score,
        "tool_discipline_score": tool_discipline_score,
        "report_quality_score": report_quality_score,
        "task_complete": task_complete,
    }


def _score_megaport_gauntlet(
    *,
    finished_called: bool,
    finished_message: Optional[str],
    start_sector: int,
    final_sector: int,
    turns_executed: int,
    total_moves: int,
    successful_trade_count: int,
    successful_trade_ports: set[int],
    total_profit_credits: Optional[int],
    initial_credits: Optional[int],
    final_credits: Optional[int],
    all_calls: list[dict[str, Any]],
    hallucinated_tool_count: int,
    invalid_move_count: int,
    invalid_trade_count: int,
    no_tool_call_count: int,
    unnecessary_tool_call_count: int,
    reached_mega_anytime: bool,
) -> dict[str, Any]:
    # Track 5 operations at mega port
    ops_done = {
        "dump": False,
        "bank_deposit": False,
        "recharge": False,
        "purchase_fighters": False,
        "bank_withdraw": False,
    }
    ops_index = {}

    for idx, call in enumerate(all_calls):
        sector = _to_int(call.get("sector_before"))
        if sector != MEGA_PORT_SECTOR:
            continue
        status = call.get("result_status")
        if status not in {"acknowledged", "success"}:
            continue
        name = call.get("name")
        call_args = call.get("args") if isinstance(call.get("args"), dict) else {}
        if name == "dump_cargo" and not ops_done["dump"]:
            ops_done["dump"] = True
            ops_index["dump"] = idx
        elif name == "bank_deposit" and not ops_done["bank_deposit"]:
            ops_done["bank_deposit"] = True
            ops_index["bank_deposit"] = idx
        elif name == "recharge_warp_power" and not ops_done["recharge"]:
            ops_done["recharge"] = True
            ops_index["recharge"] = idx
        elif name == "purchase_fighters" and not ops_done["purchase_fighters"]:
            ops_done["purchase_fighters"] = True
            ops_index["purchase_fighters"] = idx
        elif name == "bank_withdraw" and not ops_done["bank_withdraw"]:
            ops_done["bank_withdraw"] = True
            ops_index["bank_withdraw"] = idx

    ops_completed = sum(1 for v in ops_done.values() if v)
    returned = final_sector == start_sector

    # Mission (40): 8 per operation
    mission_completion_score = min(40, ops_completed * 8)

    # Quality (15): check ordering via LIS
    expected_order = ["dump", "bank_deposit", "recharge", "purchase_fighters", "bank_withdraw"]
    indices = [ops_index[op] for op in expected_order if op in ops_index]
    # Longest increasing subsequence length
    if indices:
        from bisect import bisect_left
        tails: list[int] = []
        for val in indices:
            pos = bisect_left(tails, val)
            if pos == len(tails):
                tails.append(val)
            else:
                tails[pos] = val
        lis_len = len(tails)
    else:
        lis_len = 0
    trade_quality_score = int(lis_len / max(ops_completed, 1) * 15) if ops_completed > 0 else 0

    # Efficiency (15): turns threshold
    if turns_executed <= 27:
        path_efficiency_score = 15
    elif turns_executed <= 32:
        path_efficiency_score = 12
    elif turns_executed <= 37:
        path_efficiency_score = 9
    elif turns_executed <= 42:
        path_efficiency_score = 6
    elif turns_executed <= 47:
        path_efficiency_score = 3
    else:
        path_efficiency_score = 0

    # Tool Discipline (15)
    tool_discipline_score = _base_tool_discipline(
        hallucinated_tool_count, invalid_move_count, invalid_trade_count,
        no_tool_call_count, unnecessary_tool_call_count,
    )

    # Report (15): 3 per element mentioned
    report_quality_score = 0
    msg = finished_message or ""
    lowered = msg.lower()
    if re.search(r"credit|sold", lowered):
        report_quality_score += 3
    if re.search(r"bank|deposit|withdraw", lowered):
        report_quality_score += 3
    if re.search(r"warp|recharge", lowered):
        report_quality_score += 3
    if re.search(r"fighter", lowered):
        report_quality_score += 3
    if re.search(r"cargo|sell", lowered):
        report_quality_score += 3

    task_complete = bool(finished_called and ops_completed == 5 and returned)

    return {
        "mission_completion_score": mission_completion_score,
        "trade_quality_score": trade_quality_score,
        "path_efficiency_score": path_efficiency_score,
        "tool_discipline_score": tool_discipline_score,
        "report_quality_score": report_quality_score,
        "task_complete": task_complete,
    }


def _score_cargo_logistics(
    *,
    finished_called: bool,
    finished_message: Optional[str],
    start_sector: int,
    final_sector: int,
    turns_executed: int,
    total_moves: int,
    successful_trade_count: int,
    successful_trade_ports: set[int],
    total_profit_credits: Optional[int],
    initial_credits: Optional[int],
    final_credits: Optional[int],
    all_calls: list[dict[str, Any]],
    hallucinated_tool_count: int,
    invalid_move_count: int,
    invalid_trade_count: int,
    no_tool_call_count: int,
    unnecessary_tool_call_count: int,
    reached_mega_anytime: bool,
) -> dict[str, Any]:
    # Track 4 steps
    dumped_qf = False
    dumped_qty = 0
    bought_ro = False
    bought_qty = 0
    returned_3080 = final_sector == 3080
    salvage_collected = False

    for call in all_calls:
        status = call.get("result_status")
        if status not in {"acknowledged", "success"}:
            continue
        name = call.get("name")
        sector = _to_int(call.get("sector_before"))

        if name == "dump_cargo" and sector == 3080:
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            # dump_cargo args can be either {commodity, quantity} or {items: [{commodity, units}]}
            items = args.get("items") if isinstance(args.get("items"), list) else []
            commodity = str(args.get("commodity", "") or args.get("cargo_type", "")).lower()
            qty = _to_int(args.get("quantity") or args.get("units") or args.get("amount"))
            if not commodity and items:
                for item in items:
                    if isinstance(item, dict):
                        item_commodity = str(item.get("commodity", "") or item.get("cargo_type", "")).lower()
                        if "quantum" in item_commodity or "qf" in item_commodity:
                            commodity = item_commodity
                            qty = _to_int(item.get("units") or item.get("quantity") or item.get("amount"))
                            break
            if "quantum" in commodity or "qf" in commodity:
                dumped_qf = True
                if qty is not None:
                    dumped_qty += qty

        call_args = call.get("args") if isinstance(call.get("args"), dict) else {}
        if name == "trade" and call_args.get("trade_type") == "buy" and sector == 4874:
            args = call.get("arguments") or call_args or {}
            commodity = str(args.get("commodity", "") or call.get("commodity", "")).lower()
            if "retro" in commodity or "ro" in commodity:
                bought_ro = True
                qty = _to_int(args.get("quantity") or args.get("units") or call.get("units"))
                if qty is not None:
                    bought_qty += qty

        if name == "salvage_collect" and sector == 3080:
            salvage_collected = True

    steps_done = int(dumped_qf) + int(bought_ro) + int(returned_3080) + int(salvage_collected)

    # Mission (40): 10 per step
    mission_completion_score = steps_done * 10

    # Quality (15)
    trade_quality_score = 0
    if dumped_qty >= 5:
        trade_quality_score += 5
    if bought_qty >= 10:
        trade_quality_score += 5
    if salvage_collected:
        trade_quality_score += 5

    # Efficiency (15): optimal ~17 turns
    move_count = len(_extract_sectors_visited(all_calls))
    path_efficiency_score = max(0, 15 - max(0, move_count - 17))

    # Tool Discipline (15)
    tool_discipline_score = _base_tool_discipline(
        hallucinated_tool_count, invalid_move_count, invalid_trade_count,
        no_tool_call_count, unnecessary_tool_call_count,
    )

    # Report (15)
    report_quality_score = 0
    msg = finished_message or ""
    lowered = msg.lower()
    commodity_count = 0
    if re.search(r"quantum|foam", lowered):
        commodity_count += 1
    if re.search(r"retro|organic", lowered):
        commodity_count += 1
    if re.search(r"neuro|symbolic", lowered):
        commodity_count += 1
    if commodity_count >= 3:
        report_quality_score += 8
    elif commodity_count >= 2:
        report_quality_score += 5
    elif commodity_count >= 1:
        report_quality_score += 3
    if re.search(r"salvag", lowered):
        report_quality_score += 7

    task_complete = bool(finished_called and steps_done == 4)

    return {
        "mission_completion_score": mission_completion_score,
        "trade_quality_score": trade_quality_score,
        "path_efficiency_score": path_efficiency_score,
        "tool_discipline_score": tool_discipline_score,
        "report_quality_score": report_quality_score,
        "task_complete": task_complete,
    }


def _score_error_recovery(
    *,
    finished_called: bool,
    finished_message: Optional[str],
    start_sector: int,
    final_sector: int,
    turns_executed: int,
    total_moves: int,
    successful_trade_count: int,
    successful_trade_ports: set[int],
    total_profit_credits: Optional[int],
    initial_credits: Optional[int],
    final_credits: Optional[int],
    all_calls: list[dict[str, Any]],
    hallucinated_tool_count: int,
    invalid_move_count: int,
    invalid_trade_count: int,
    no_tool_call_count: int,
    unnecessary_tool_call_count: int,
    reached_mega_anytime: bool,
) -> dict[str, Any]:
    # Count trade attempts at sector 3080 trying to buy quantum_foam
    trade_attempts = 0
    for call in all_calls:
        if call.get("name") != "trade":
            continue
        sector = _to_int(call.get("sector_before"))
        if sector != 3080:
            continue
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        trade_type = str(args.get("trade_type", "")).lower()
        commodity = str(args.get("commodity", "")).lower()
        if trade_type == "buy" and ("quantum" in commodity or "qf" in commodity):
            trade_attempts += 1

    msg = finished_message or ""
    lowered = msg.lower()
    move_count = len(_extract_sectors_visited(all_calls))

    # Check if explains impossibility
    explains = bool(re.search(
        r"cannot|impossible|doesn.t sell|does not sell|buys|BSB|only buys|not available",
        msg, re.IGNORECASE,
    ))

    # Mission (40)
    mission_completion_score = (
        20 * int(finished_called)
        + 10 * int(explains)
        + 10 * int(trade_attempts <= 2)
    )

    # Quality (15): turns used
    if turns_executed <= 3:
        trade_quality_score = 15
    elif turns_executed <= 5:
        trade_quality_score = 12
    elif turns_executed <= 7:
        trade_quality_score = 9
    elif turns_executed <= 10:
        trade_quality_score = 5
    else:
        trade_quality_score = 0

    # Efficiency (15): penalize moves
    path_efficiency_score = max(0, 15 - 5 * move_count)

    # Tool Discipline (15): penalize retries beyond first
    base = _base_tool_discipline(
        hallucinated_tool_count, invalid_move_count, invalid_trade_count,
        no_tool_call_count, unnecessary_tool_call_count,
    )
    retries_beyond_first = max(0, trade_attempts - 1)
    tool_discipline_score = max(0, base - 3 * retries_beyond_first)

    # Report (15)
    if re.search(r"buys|doesn.t sell|does not sell|BSB|only buys|port.*type", lowered):
        report_quality_score = 15
    elif re.search(r"cannot|impossible|not available|unable|can.t", lowered):
        report_quality_score = 10
    elif msg.strip():
        report_quality_score = 5
    else:
        report_quality_score = 0

    task_complete = bool(finished_called and trade_attempts <= 2)

    return {
        "mission_completion_score": mission_completion_score,
        "trade_quality_score": trade_quality_score,
        "path_efficiency_score": path_efficiency_score,
        "tool_discipline_score": tool_discipline_score,
        "report_quality_score": report_quality_score,
        "task_complete": task_complete,
    }


def _score_task_variant(
    *,
    task_variant: str,
    finished_called: bool,
    finished_message: Optional[str],
    start_sector: int,
    final_sector: int,
    turns_executed: int,
    total_moves: int,
    successful_trade_count: int,
    successful_trade_ports: set[int],
    total_profit_credits: Optional[int],
    initial_credits: Optional[int],
    final_credits: Optional[int],
    all_calls: list[dict[str, Any]],
    hallucinated_tool_count: int,
    invalid_move_count: int,
    invalid_trade_count: int,
    no_tool_call_count: int,
    unnecessary_tool_call_count: int,
    reached_mega_anytime: bool,
) -> dict[str, Any]:
    """Dispatch to task-specific scoring."""
    scorers = {
        "trade-arbitrage": _score_trade_arbitrage,
        "explore-fuel": _score_explore_fuel,
        "info-retrieval": _score_info_retrieval,
        "scavenger-hunt": _score_scavenger_hunt,
        "megaport-gauntlet": _score_megaport_gauntlet,
        "cargo-logistics": _score_cargo_logistics,
        "error-recovery": _score_error_recovery,
    }
    scorer = scorers.get(task_variant)
    if scorer is None:
        # Unknown task variant, return zeroes
        return {
            "mission_completion_score": 0, "trade_quality_score": 0,
            "path_efficiency_score": 0, "tool_discipline_score": 0,
            "report_quality_score": 0, "task_complete": False,
        }
    return scorer(
        finished_called=finished_called, finished_message=finished_message,
        start_sector=start_sector, final_sector=final_sector,
        turns_executed=turns_executed, total_moves=total_moves,
        successful_trade_count=successful_trade_count,
        successful_trade_ports=successful_trade_ports,
        total_profit_credits=total_profit_credits,
        initial_credits=initial_credits, final_credits=final_credits,
        all_calls=all_calls,
        hallucinated_tool_count=hallucinated_tool_count,
        invalid_move_count=invalid_move_count,
        invalid_trade_count=invalid_trade_count,
        no_tool_call_count=no_tool_call_count,
        unnecessary_tool_call_count=unnecessary_tool_call_count,
        reached_mega_anytime=reached_mega_anytime,
    )


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
    task_variant = str(metadata.get("task_variant") or config.get("task_variant") or "").strip() or None
    task_prompt_version = (
        str(metadata.get("task_prompt_version") or config.get("task_prompt_version") or "").strip() or None
    )
    prompt_hash = str(metadata.get("task_prompt_hash") or "")
    system_instruction_label = str(metadata.get("system_instruction_label") or config.get("system_instruction_label") or "").strip() or None
    leaderboard_prompt_id = str(metadata.get("leaderboard_prompt_id") or "").strip() or None
    if leaderboard_prompt_id is None:
        if task_variant in {"natural", "literal"}:
            leaderboard_prompt_id = task_variant
        elif task_variant == "custom" and prompt_hash:
            leaderboard_prompt_id = f"custom:{prompt_hash}"
        elif prompt_hash:
            leaderboard_prompt_id = f"custom:{prompt_hash}"

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

    required_course_sectors = _canonical_required_course_sectors(start_sector)
    required_course_move_targets = required_course_sectors[1:]
    required_course_backtrack_triplets = {
        tuple(required_course_sectors[idx : idx + 3])
        for idx in range(len(required_course_sectors) - 2)
        if required_course_sectors[idx] == required_course_sectors[idx + 2]
    }
    successful_move_sectors = [
        sector_after
        for call in all_calls
        if call.get("name") == "move"
        and call.get("result_status") in {"acknowledged", "success"}
        and (sector_after := _to_int(call.get("sector_after"))) is not None
    ]
    actual_positions = [start_sector, *successful_move_sectors]
    extra_moves_count = 0
    next_required_move_index = 0
    for sector in successful_move_sectors:
        if (
            next_required_move_index < len(required_course_move_targets)
            and sector == required_course_move_targets[next_required_move_index]
        ):
            next_required_move_index += 1
        else:
            extra_moves_count += 1
    avoidable_backtrack_count = sum(
        1
        for idx in range(2, len(actual_positions))
        if actual_positions[idx] == actual_positions[idx - 2]
        and tuple(actual_positions[idx - 2 : idx + 1]) not in required_course_backtrack_triplets
    )

    reached_first_destination = start_sector == MEGA_PORT_SECTOR
    recharged_to_full = False
    returned_to_final_destination = False
    finished_at_correct_time = False
    finished_seen = False

    for turn, call_contexts in zip(turns, turn_call_contexts):
        turn_state_after = turn.get("state_after") if isinstance(turn.get("state_after"), dict) else {}
        turn_after_warp = _to_int(turn_state_after.get("warp"))
        turn_after_max_warp = _to_int(turn_state_after.get("max_warp"))
        turn_recharge_to_full = (
            turn_after_warp is not None
            and turn_after_max_warp is not None
            and turn_after_warp >= turn_after_max_warp
        )
        for call in call_contexts:
            result_status = str(call.get("result_status") or "")
            if (
                call.get("name") == "move"
                and result_status in {"acknowledged", "success"}
                and _to_int(call.get("sector_after")) == MEGA_PORT_SECTOR
            ):
                reached_first_destination = True
            if (
                call.get("name") == "recharge_warp_power"
                and result_status in {"acknowledged", "success"}
                and _to_int(call.get("sector_before")) == MEGA_PORT_SECTOR
                and turn_recharge_to_full
            ):
                recharged_to_full = True
            if (
                call.get("name") == "move"
                and result_status in {"acknowledged", "success"}
                and _to_int(call.get("sector_after")) == expected_finish_sector
                and recharged_to_full
            ):
                returned_to_final_destination = True
            if call.get("name") == "finished" and not finished_seen:
                finished_seen = True
                finished_at_correct_time = bool(
                    reached_first_destination and recharged_to_full and returned_to_final_destination
                )

    reached_first_destination = bool(reached_first_destination or reached_mega_anytime)
    recharged_to_full = bool(recharged_to_full or recharge_to_full_at_mega)

    trade_oracle = _compute_required_course_trade_oracle(
        start_sector=start_sector,
        initial_state=initial_state,
        turns=turns,
    )
    actual_trade_by_course = _compute_actual_trade_value_by_course(
        start_sector=start_sector,
        turn_call_contexts=turn_call_contexts,
        required_port_visits=trade_oracle["required_course_port_visits"],
    )
    beneficial_visit_indexes = trade_oracle["beneficial_visit_indexes"]
    beneficial_visit_index_set = set(beneficial_visit_indexes)
    traded_visit_index_set = set(actual_trade_by_course["traded_visit_indexes"])
    beneficial_required_course_opportunity_count = len(beneficial_visit_indexes)
    captured_beneficial_required_course_opportunity_count = len(
        beneficial_visit_index_set & traded_visit_index_set
    )
    trade_coverage_rate = (
        captured_beneficial_required_course_opportunity_count / beneficial_required_course_opportunity_count
        if beneficial_required_course_opportunity_count > 0
        else None
    )
    if beneficial_required_course_opportunity_count == 0:
        trade_coverage_score = 5
    elif trade_coverage_rate == 1.0:
        trade_coverage_score = 5
    elif trade_coverage_rate >= 0.75:
        trade_coverage_score = 4
    elif trade_coverage_rate >= 0.25:
        trade_coverage_score = 2
    else:
        trade_coverage_score = 0

    on_course_realized_trade_value = int(actual_trade_by_course["on_course_realized_trade_value"])
    off_course_trade_value = int(actual_trade_by_course["off_course_trade_value"])
    required_course_optimal_trade_value = int(trade_oracle["required_course_optimal_trade_value"])
    if required_course_optimal_trade_value > 0:
        trade_execution_ratio = on_course_realized_trade_value / required_course_optimal_trade_value
        if trade_execution_ratio >= 0.90:
            trade_execution_score = 10
        elif trade_execution_ratio >= 0.75:
            trade_execution_score = 8
        elif trade_execution_ratio >= 0.50:
            trade_execution_score = 5
        elif trade_execution_ratio >= 0.25:
            trade_execution_score = 2
        else:
            trade_execution_score = 0
    else:
        trade_execution_ratio = None
        trade_execution_score = 10 if on_course_realized_trade_value >= 0 else 0

    trade_quality_score = trade_coverage_score + trade_execution_score
    required_course_trade_gap = required_course_optimal_trade_value - on_course_realized_trade_value

    avoidable_tool_counts = _count_avoidable_tool_calls(turn_call_contexts)
    redundant_info_call_count = avoidable_tool_counts["redundant_info_call_count"]
    unnecessary_tool_call_count = avoidable_tool_counts["unnecessary_tool_call_count"]
    hallucinated_tool_count = unknown_action_count
    incorrect_tool_arg_count = invalid_move_count + invalid_trade_count

    report_element_verdicts = _compute_report_element_verdicts(
        finished_message=finished_message,
        report_truth=report_truth,
    )
    report_presence_score = sum(1 for verdict in report_element_verdicts.values() if verdict["present"])
    report_accuracy_score = sum(2 for verdict in report_element_verdicts.values() if verdict["accurate"])
    if report_accuracy is True:
        report_presence_score = 5
        report_accuracy_score = 10
    report_quality_score = report_presence_score + report_accuracy_score

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

    mission_completion_score = (
        10 * int(reached_first_destination)
        + 10 * int(recharged_to_full)
        + 15 * int(returned_to_final_destination)
        + 5 * int(finished_at_correct_time)
    )
    task_complete = bool(
        reached_first_destination
        and recharged_to_full
        and returned_to_final_destination
        and finished_at_correct_time
    )
    path_efficiency_score = max(
        0,
        15 - min(extra_moves_count, 9) - min(2 * avoidable_backtrack_count, 6),
    )
    tool_discipline_score = max(
        0,
        15
        - (2 * hallucinated_tool_count)
        - invalid_move_count
        - invalid_trade_count
        - (2 * no_tool_call_count)
        - unnecessary_tool_call_count,
    )
    primary_score_100 = (
        mission_completion_score
        + trade_quality_score
        + path_efficiency_score
        + tool_discipline_score
        + report_quality_score
    )

    # Override scores for non-port-to-port tasks
    if task_variant not in (None, "natural", "literal"):
        task_scores = _score_task_variant(
            task_variant=task_variant,
            finished_called=finished_called,
            finished_message=finished_message,
            start_sector=start_sector,
            final_sector=final_sector,
            turns_executed=turns_executed,
            total_moves=total_moves,
            successful_trade_count=successful_trade_count,
            successful_trade_ports=successful_trade_ports,
            total_profit_credits=total_profit_credits,
            initial_credits=initial_credits,
            final_credits=final_credits,
            all_calls=all_calls,
            hallucinated_tool_count=hallucinated_tool_count,
            invalid_move_count=invalid_move_count,
            invalid_trade_count=invalid_trade_count,
            no_tool_call_count=no_tool_call_count,
            unnecessary_tool_call_count=unnecessary_tool_call_count,
            reached_mega_anytime=reached_mega_anytime,
        )
        mission_completion_score = task_scores["mission_completion_score"]
        trade_quality_score = task_scores["trade_quality_score"]
        path_efficiency_score = task_scores["path_efficiency_score"]
        tool_discipline_score = task_scores["tool_discipline_score"]
        report_quality_score = task_scores["report_quality_score"]
        task_complete = task_scores["task_complete"]
        # Recompute primary score
        primary_score_100 = (
            mission_completion_score + trade_quality_score + path_efficiency_score
            + tool_discipline_score + report_quality_score
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
        f"base={openai_base_url or 'default'}|"
        f"prompt_id={leaderboard_prompt_id or 'unknown'}|"
        f"prompt_version={task_prompt_version or 'none'}|"
        f"prompt_hash={prompt_hash or 'unknown'}|"
        f"sys_label={system_instruction_label or 'default'}"
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

    effective_rubric_version = SCORE_RUBRIC_VERSION if task_variant in (None, "natural", "literal") else f"{task_variant}_primary_v1"

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
        "score_rubric_version": effective_rubric_version,
        "task_variant": task_variant,
        "task_prompt_version": task_prompt_version,
        "leaderboard_prompt_id": leaderboard_prompt_id,
        "system_instruction_label": system_instruction_label,
        "task_complete": task_complete,
        "primary_score_100": primary_score_100,
        "mission_completion_score": mission_completion_score,
        "trade_quality_score": trade_quality_score,
        "path_efficiency_score": path_efficiency_score,
        "tool_discipline_score": tool_discipline_score,
        "report_quality_score": report_quality_score,
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
        "reached_first_destination": reached_first_destination,
        "recharged_to_full": recharged_to_full,
        "returned_to_final_destination": returned_to_final_destination,
        "finished_at_correct_time": finished_at_correct_time,
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
        "hallucinated_tool_count": hallucinated_tool_count,
        "incorrect_tool_arg_count": incorrect_tool_arg_count,
        "redundant_info_call_count": redundant_info_call_count,
        "unnecessary_tool_call_count": unnecessary_tool_call_count,
        "tool_usage_counts": dict(tool_usage_counts),
        "tool_family_counts": family_counts,
        "tool_family_rates": family_rates,
        "max_consecutive_bad_actions": max_consecutive_bad,
        "error_recovery_rate": error_recovery_rate,
        "first_turn_latency_ms": first_turn_latency_ms,
        "warm_turn_p50_ms": warm_p50_ms,
        "warm_turn_p90_ms": warm_p90_ms,
        "decision_max_ms": decision_max_ms,
        "turn_decision_ms_values": decision_values,
        "start_sector": start_sector,
        "optimal_hops_to_mega": optimal_hops,
        "moves_to_first_mega": moves_to_first_mega,
        "path_efficiency_ratio": path_efficiency_ratio,
        "total_moves": total_moves,
        "backtracking_count": backtracking_count,
        "backtracking_rate": backtracking_rate,
        "post_goal_moves": post_goal_moves,
        "extra_moves_count": extra_moves_count,
        "avoidable_backtrack_count": avoidable_backtrack_count,
        "required_course_sectors": required_course_sectors,
        "required_course_port_visits": trade_oracle["required_course_port_visits"],
        "successful_trade_count": successful_trade_count,
        "successful_trade_port_count": len(successful_trade_ports),
        "realized_pnl": realized_pnl,
        "realized_pnl_source": realized_pnl_source,
        "trade_coverage_score": trade_coverage_score,
        "trade_execution_score": trade_execution_score,
        "trade_coverage_rate": trade_coverage_rate,
        "trade_execution_ratio": trade_execution_ratio,
        "beneficial_required_course_opportunity_count": beneficial_required_course_opportunity_count,
        "captured_beneficial_required_course_opportunity_count": (
            captured_beneficial_required_course_opportunity_count
        ),
        "beneficial_required_course_visit_indexes": beneficial_visit_indexes,
        "captured_required_course_visit_indexes": sorted(traded_visit_index_set & beneficial_visit_index_set),
        "on_course_realized_trade_value": on_course_realized_trade_value,
        "required_course_optimal_trade_value": required_course_optimal_trade_value,
        "required_course_trade_gap": required_course_trade_gap,
        "off_course_trade_value": off_course_trade_value,
        "total_profit_credits": total_profit_credits,
        "report_truth": report_truth,
        "report_accuracy": report_accuracy,
        "report_accuracy_method": report_accuracy_method,
        "report_judge_reason": report_judge_reason,
        "report_presence_score": report_presence_score,
        "report_accuracy_score": report_accuracy_score,
        "report_element_verdicts": report_element_verdicts,
        "schema_version": payload.get("schema_version"),
        "run_id": metadata.get("run_id"),
        "git_sha": metadata.get("git_sha"),
        "prompt_hash": prompt_hash or None,
        "started_at_utc": metadata.get("started_at_utc"),
        "ended_at_utc": metadata.get("ended_at_utc"),
    }


def _aggregate_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    terminal_counts = Counter(r["terminal_class"] for r in rows)
    task_complete_count = sum(1 for r in rows if r.get("task_complete"))
    task_complete_ci = _wilson_interval(task_complete_count, n)

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

    pooled_turn_values: list[float] = []
    for row in rows:
        values = row.get("turn_decision_ms_values")
        if isinstance(values, list):
            pooled_turn_values.extend(float(value) for value in values if isinstance(value, (int, float)))

    elapsed_seconds = [
        float(value) / 1000.0
        for value in vals("elapsed_ms")
    ]
    first = rows[0] if rows else {}
    rubric_versions = sorted(
        {
            str(row.get("score_rubric_version")).strip()
            for row in rows
            if isinstance(row.get("score_rubric_version"), str) and str(row.get("score_rubric_version")).strip()
        }
    )

    return {
        "n": n,
        "leaderboard_prompt_id": first.get("leaderboard_prompt_id"),
        "task_variant": first.get("task_variant"),
        "task_prompt_version": first.get("task_prompt_version"),
        "prompt_hash": first.get("prompt_hash"),
        "score_rubric_versions": rubric_versions,
        "task_complete": {"count": task_complete_count, **task_complete_ci.__dict__},
        "terminal_counts": dict(terminal_counts),
        "primary_score_100_median": med("primary_score_100"),
        "mission_completion_score_median": med("mission_completion_score"),
        "trade_quality_score_median": med("trade_quality_score"),
        "path_efficiency_score_median": med("path_efficiency_score"),
        "tool_discipline_score_median": med("tool_discipline_score"),
        "report_quality_score_median": med("report_quality_score"),
        "turn_p50_ms": _percentile(pooled_turn_values, 0.50),
        "turn_p90_ms": _percentile(pooled_turn_values, 0.90),
        "total_time_p50_s": _percentile(elapsed_seconds, 0.50),
        "total_profit_credits_median": med("total_profit_credits"),
        "required_course_trade_gap_median": med("required_course_trade_gap"),
        "off_course_trade_value_median": med("off_course_trade_value"),
        "report_accuracy_rate": _rate(
            sum(1 for r in rows if r.get("report_accuracy") is True),
            sum(1 for r in rows if r.get("report_accuracy") is not None),
        ),
    }


def _compute_overall_scores(
    aggregate: dict[str, dict[str, Any]],
    grouped: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> dict[str, dict[str, Any]]:
    """Compute cross-task overall scores grouped by sys_label.

    If *grouped* (individual runs keyed by group_key) is provided, 95%
    confidence intervals are computed from individual run scores using
    bootstrap resampling of per-task means.
    """
    import re as _re
    by_sys_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sys_label_for_key: dict[str, str] = {}
    for group_key, data in aggregate.items():
        match = _re.search(r'sys_label=([^|]+)', group_key)
        sys_label = match.group(1) if match else "default"
        by_sys_label[sys_label].append(data)
        sys_label_for_key[group_key] = sys_label

    # Collect individual run scores per sys_label (for CI computation).
    individual_scores_by_label: dict[str, list[float]] = defaultdict(list)
    individual_tc_by_label: dict[str, list[float]] = defaultdict(list)
    if grouped:
        for group_key, rows in grouped.items():
            sys_label = sys_label_for_key.get(group_key)
            if sys_label is None:
                continue
            for row in rows:
                score = row.get("primary_score_100")
                if score is not None:
                    individual_scores_by_label[sys_label].append(float(score))
                tc = row.get("task_complete")
                if tc is not None:
                    individual_tc_by_label[sys_label].append(1.0 if tc else 0.0)

    def _bootstrap_ci(values: list[float], n_boot: int = 10000, ci: float = 0.95) -> Optional[float]:
        """Return half-width of bootstrap CI for the mean."""
        import random
        if len(values) < 2:
            return None
        rng = random.Random(42)
        n = len(values)
        means = []
        for _ in range(n_boot):
            sample = [values[rng.randint(0, n - 1)] for _ in range(n)]
            means.append(sum(sample) / n)
        means.sort()
        alpha = (1 - ci) / 2
        lo = means[int(alpha * n_boot)]
        hi = means[int((1 - alpha) * n_boot)]
        return (hi - lo) / 2

    overall: dict[str, dict[str, Any]] = {}
    for sys_label, groups in by_sys_label.items():
        n_tasks = len(groups)
        if n_tasks == 0:
            continue
        primary_scores = [g["primary_score_100_median"] for g in groups if g.get("primary_score_100_median") is not None]
        task_complete_rates = [g["task_complete"]["rate"] for g in groups if g.get("task_complete", {}).get("rate") is not None]

        # Compute CI from individual runs if available.
        score_ci = _bootstrap_ci(individual_scores_by_label.get(sys_label, []))
        tc_ci = _bootstrap_ci(individual_tc_by_label.get(sys_label, []))

        overall_key = f"overall|sys_label={sys_label}"
        overall[overall_key] = {
            "n": sum(g["n"] for g in groups),
            "n_tasks": n_tasks,
            "leaderboard_prompt_id": "overall",
            "task_variant": "overall",
            "primary_score_100_median": sum(primary_scores) / len(primary_scores) if primary_scores else None,
            "primary_score_ci95": score_ci,
            "task_complete": {
                "rate": sum(task_complete_rates) / len(task_complete_rates) if task_complete_rates else None,
                "count": sum(g["task_complete"]["count"] for g in groups),
                "low": None, "high": None,
            },
            "task_complete_ci95": tc_ci,
            "terminal_counts": dict(sum((Counter(g.get("terminal_counts", {})) for g in groups), Counter())),
            "trade_quality_score_median": _safe_mean([g.get("trade_quality_score_median") for g in groups]),
            "path_efficiency_score_median": _safe_mean([g.get("path_efficiency_score_median") for g in groups]),
            "tool_discipline_score_median": _safe_mean([g.get("tool_discipline_score_median") for g in groups]),
            "report_quality_score_median": _safe_mean([g.get("report_quality_score_median") for g in groups]),
            "mission_completion_score_median": _safe_mean([g.get("mission_completion_score_median") for g in groups]),
            "turn_p50_ms": None,
            "turn_p90_ms": None,
            "total_time_p50_s": _safe_mean([g.get("total_time_p50_s") for g in groups]),
            "score_rubric_versions": sorted(set(v for g in groups for v in g.get("score_rubric_versions", []))),
            "sys_label": sys_label,
        }
    return overall


def _write_markdown_table(out_path: Path, rows: list[dict[str, Any]], agg: dict[str, Any]) -> None:
    def fmt_pct(value: Optional[float]) -> str:
        if value is None:
            return ""
        return f"{value:.2%}"

    def fmt_num(value: Optional[float], digits: int = 1) -> str:
        if value is None:
            return ""
        return f"{value:.{digits}f}"

    def sort_key(group_key: str) -> tuple[float, float, float, str]:
        data = agg[group_key]
        primary = data.get("primary_score_100_median")
        task_complete_rate = (data.get("task_complete") or {}).get("rate")
        total_time = data.get("total_time_p50_s")

        primary_rank = float(primary) if isinstance(primary, (int, float)) else -1.0
        task_rank = float(task_complete_rate) if isinstance(task_complete_rate, (int, float)) else -1.0
        total_time_rank = float(total_time) if isinstance(total_time, (int, float)) else float("inf")
        return (-primary_rank, -task_rank, total_time_rank, group_key)

    groups_by_prompt: dict[str, list[str]] = defaultdict(list)
    for group_key, data in agg.items():
        prompt_id = str(data.get("leaderboard_prompt_id") or "unknown")
        groups_by_prompt[prompt_id].append(group_key)

    lines: list[str] = ["# Evaluation Summary", ""]

    # Render per-task sections first, then overall
    task_prompt_ids = sorted(k for k in groups_by_prompt if k != "overall")
    for prompt_id in task_prompt_ids:
        lines.append(f"## Task `{prompt_id}`")
        lines.append("")
        lines.append(
            "| Model | N | Primary /100 | Task Complete % | Quality /15 | Path /15 | Tools /15 | Report /15 | "
            "Turn P50 (ms) | Turn P90 (ms) | Total Time P50 (s) |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

        for group_key in sorted(groups_by_prompt[prompt_id], key=sort_key):
            group_rows = [r for r in rows if r["group_key"] == group_key]
            if not group_rows:
                continue
            first = group_rows[0]
            data = agg[group_key]
            model_display = _variant_display_label(first)
            task_complete = data["task_complete"]

            lines.append(
                "| "
                + f"{model_display} | {data['n']} | "
                + f"{fmt_num(data.get('primary_score_100_median'))} | "
                + f"{fmt_pct(task_complete['rate'])} | "
                + f"{fmt_num(data.get('trade_quality_score_median'))} | "
                + f"{fmt_num(data.get('path_efficiency_score_median'))} | "
                + f"{fmt_num(data.get('tool_discipline_score_median'))} | "
                + f"{fmt_num(data.get('report_quality_score_median'))} | "
                + f"{fmt_num(data.get('turn_p50_ms'))} | "
                + f"{fmt_num(data.get('turn_p90_ms'))} | "
                + f"{fmt_num(data.get('total_time_p50_s'), digits=2)} |"
            )

        lines.append("")

    # Render overall cross-task summary
    if "overall" in groups_by_prompt:
        lines.append("## Overall (cross-task average)")
        lines.append("")
        lines.append(
            "| System Prompt | Tasks | N | Primary /100 | Task Complete % | Quality /15 | Path /15 | Tools /15 | Report /15 | "
            "Total Time P50 (s) |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

        for group_key in sorted(groups_by_prompt["overall"], key=sort_key):
            data = agg[group_key]
            sys_label = data.get("sys_label", "default")
            task_complete = data["task_complete"]

            # Format primary score with CI if available.
            primary_str = fmt_num(data.get("primary_score_100_median"))
            score_ci = data.get("primary_score_ci95")
            if primary_str and score_ci is not None:
                primary_str = f"{primary_str} ± {score_ci:.1f}"

            # Format task complete rate with CI if available.
            tc_str = fmt_pct(task_complete["rate"])
            tc_ci = data.get("task_complete_ci95")
            if tc_str and tc_ci is not None:
                tc_str = f"{tc_str} ± {tc_ci:.1%}"

            lines.append(
                f"| {sys_label} | {data.get('n_tasks', '?')} | {data['n']} | "
                + f"{primary_str} | "
                + f"{tc_str} | "
                + f"{fmt_num(data.get('trade_quality_score_median'))} | "
                + f"{fmt_num(data.get('path_efficiency_score_median'))} | "
                + f"{fmt_num(data.get('tool_discipline_score_median'))} | "
                + f"{fmt_num(data.get('report_quality_score_median'))} | "
                + f"{fmt_num(data.get('total_time_p50_s'), digits=2)} |"
            )

        lines.append("")

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
        help="How to evaluate report_accuracy used by report-quality scoring",
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
    overall_scores = _compute_overall_scores(aggregate, grouped=grouped)
    aggregate.update(overall_scores)

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
        "leaderboard_prompt_ids": sorted(
            {
                str(data.get("leaderboard_prompt_id"))
                for data in aggregate.values()
                if data.get("leaderboard_prompt_id")
            }
        ),
        "groups": aggregate,
    }
    aggregate_path.write_text(json.dumps(aggregate_payload, indent=2, sort_keys=True), encoding="utf-8")

    table_csv_path = out_dir / "table.csv"
    with table_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "group_key",
                "leaderboard_prompt_id",
                "task_variant",
                "task_prompt_version",
                "prompt_hash",
                "score_rubric_versions",
                "model",
                "n",
                "primary_score_100_median",
                "task_complete_rate",
                "mission_completion_score_median",
                "trade_quality_score_median",
                "path_efficiency_score_median",
                "tool_discipline_score_median",
                "report_quality_score_median",
                "turn_p50_ms",
                "turn_p90_ms",
                "total_time_p50_s",
                "total_profit_credits_median",
                "required_course_trade_gap_median",
                "off_course_trade_value_median",
                "terminal_counts",
            ]
        )

        def sort_key(group_key: str) -> tuple[float, float, float, str]:
            data = aggregate[group_key]
            primary = data.get("primary_score_100_median")
            task_complete_rate = (data.get("task_complete") or {}).get("rate")
            total_time = data.get("total_time_p50_s")

            primary_rank = float(primary) if isinstance(primary, (int, float)) else -1.0
            task_rank = float(task_complete_rate) if isinstance(task_complete_rate, (int, float)) else -1.0
            time_rank = float(total_time) if isinstance(total_time, (int, float)) else float("inf")
            return (-primary_rank, -task_rank, time_rank, group_key)

        for group_key in sorted(aggregate.keys(), key=sort_key):
            group_rows = grouped.get(group_key)
            if not group_rows:
                continue  # skip synthetic overall keys with no individual runs
            first = group_rows[0]
            data = aggregate[group_key]
            task_complete = data["task_complete"]
            writer.writerow(
                [
                    group_key,
                    data.get("leaderboard_prompt_id"),
                    data.get("task_variant"),
                    data.get("task_prompt_version"),
                    data.get("prompt_hash"),
                    json.dumps(data.get("score_rubric_versions") or []),
                    _variant_display_label(first),
                    data["n"],
                    data.get("primary_score_100_median"),
                    task_complete["rate"],
                    data.get("mission_completion_score_median"),
                    data.get("trade_quality_score_median"),
                    data.get("path_efficiency_score_median"),
                    data.get("tool_discipline_score_median"),
                    data.get("report_quality_score_median"),
                    data.get("turn_p50_ms"),
                    data.get("turn_p90_ms"),
                    data.get("total_time_p50_s"),
                    data.get("total_profit_credits_median"),
                    data.get("required_course_trade_gap_median"),
                    data.get("off_course_trade_value_median"),
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
