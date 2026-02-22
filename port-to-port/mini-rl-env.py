#!/usr/bin/env python3
"""Standalone mini RL benchmark harness for one Gradient Bang task loop.

This harness has no dependency on Supabase edge functions or game servers.
It runs a synthetic environment loop locally and drives model inference each turn.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pipecat.processors.aggregators.llm_context import LLMContext

from llm_factory import (  # noqa: E402
    LLMProvider,
    LLMServiceConfig,
    UnifiedThinkingConfig,
    create_llm_service,
)


def _find_repo_root(start_dir: Path) -> Path:
    for candidate in [start_dir, *start_dir.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start_dir


HARNESS_DIR = Path(__file__).resolve().parent
REPO_ROOT = _find_repo_root(HARNESS_DIR)


MEGA_PORT_SECTOR = 1611
DEFAULT_BENCHMARK_TASK = (
    "Find the nearest mega-port that's not our current location. "
    "Fly there, trading opportunistically along the way.\n"
    "When we get there, report how many ports we traded at, and how much profit we made in total."
)
ACTION_FORMAT_REMINDER = (
    'Respond with exactly one action as JSON: '
    '{"action":"<name>","args":{...}}. '
    'Use "finished" when task is complete: '
    '{"action":"finished","args":{"message":"..."}}.'
)

RUN_SCHEMA_VERSION = "mini_rl_run.v2"
RUNNER_VERSION = "2026-02-21"


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_task_instruction_user_message(task: str) -> str:
    prompt_parts = [
        "# Agent Instructions",
        "",
        "You are an autonomous agent. Execute this task step by step. After each step, observe the results and react accordingly. Responses you generate from each inference call will be used only internally to complete the task. The only information that is returned to the user is the final result message that is passed to the `finished` tool call.",
        "",
        "When you have completed the task, call the `finished` tool with a message to be returned to the user who initiated the task.",
        "",
        "# Current time (UTC)",
        f"{datetime.now(timezone.utc).isoformat()}",
        "",
        "# Task Instructions",
        "",
        f"{task}",
        "",
    ]
    return "\n".join(prompt_parts)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_sha(repo_root: Path) -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _canonical_commodity(name: str) -> str:
    normalized = name.strip().lower().replace("-", "_").replace(" ", "_")
    alias = {
        "qf": "quantum_foam",
        "quantumfoam": "quantum_foam",
        "ro": "retro_organics",
        "retroorganics": "retro_organics",
        "ns": "neuro_symbolics",
        "neurosymbolics": "neuro_symbolics",
    }
    return alias.get(normalized, normalized)


def _display_commodity(name: str) -> str:
    mapping = {
        "quantum_foam": "quantum foam",
        "retro_organics": "retro organics",
        "neuro_symbolics": "neuro symbolics",
    }
    return mapping.get(name, name.replace("_", " "))


@dataclass
class PortMarket:
    name: str
    buys: dict[str, int] = field(default_factory=dict)
    sells: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        parts: list[str] = []
        if self.buys:
            buy_str = ",".join(
                f"{k.split('_')[0].upper()}@{v}" for k, v in sorted(self.buys.items())
            )
            parts.append(f"buys {buy_str}")
        if self.sells:
            sell_str = ",".join(
                f"{k.split('_')[0].upper()}@{v}" for k, v in sorted(self.sells.items())
            )
            parts.append(f"sells {sell_str}")
        return f"{self.name} {' '.join(parts)}" if parts else self.name


@dataclass
class Salvage:
    salvage_id: str
    sector: int
    cargo: dict[str, int]


@dataclass
class GameState:
    sector: int = 3080
    warp: int = 500
    max_warp: int = 500
    shields: int = 150
    max_shields: int = 150
    fighters: int = 300
    credits: int = 16564
    bank_credits: int = 0
    cargo: dict[str, int] = field(
        default_factory=lambda: {
            "quantum_foam": 10,
            "retro_organics": 0,
            "neuro_symbolics": 0,
        }
    )
    holds_total: int = 30
    explored_count: int = 101
    explored_percent: int = 2
    visited_sectors: set[int] = field(default_factory=lambda: {3080})

    @property
    def used_holds(self) -> int:
        return sum(self.cargo.values())

    @property
    def empty_holds(self) -> int:
        return max(0, self.holds_total - self.used_holds)


class MiniRLEnv:
    graph: dict[int, list[int]] = {
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

    ports: dict[int, PortMarket] = {
        3080: PortMarket(
            name="BSB",
            buys={"quantum_foam": 33, "neuro_symbolics": 52},
            sells={"retro_organics": 8},
        ),
        1611: PortMarket(
            name="MEGA SSS",
            sells={"quantum_foam": 19, "retro_organics": 8, "neuro_symbolics": 30},
        ),
        1928: PortMarket(
            name="BBS",
            buys={"quantum_foam": 32, "retro_organics": 13},
            sells={"neuro_symbolics": 30},
        ),
        2831: PortMarket(
            name="SSB",
            buys={"neuro_symbolics": 52},
            sells={"quantum_foam": 19, "retro_organics": 8},
        ),
        4874: PortMarket(
            name="SSS",
            sells={"quantum_foam": 19, "retro_organics": 8, "neuro_symbolics": 30},
        ),
    }

    def __init__(self) -> None:
        self.state = GameState()
        self.salvage_by_id: dict[str, Salvage] = {}
        self.bad_actions_count = 0
        self.turn_count = 0
        self.trade_events: list[dict[str, Any]] = []

    def state_snapshot(self) -> dict[str, Any]:
        return {
            "sector": self.state.sector,
            "warp": self.state.warp,
            "max_warp": self.state.max_warp,
            "credits": self.state.credits,
            "bank_credits": self.state.bank_credits,
            "cargo": dict(self.state.cargo),
            "empty_holds": self.state.empty_holds,
            "used_holds": self.state.used_holds,
            "visited_sector_count": len(self.state.visited_sectors),
        }

    def _status_snapshot(self) -> str:
        sector = self.state.sector
        neighbors = self.graph.get(sector, [])
        port = self.ports.get(sector)
        port_text = port.summary() if port else "None"

        lines = [
            "Player: Jane Eyre",
            f"In sector {sector}.",
            f"Adjacent sectors: {neighbors}",
            "Region: Federation Space",
            f"Explored {self.state.explored_count} sectors ({self.state.explored_percent}%).",
            "Ship: Kestrel Courier (Kestrel Courier)",
            (
                f"Credits: {self.state.credits} (bank: {self.state.bank_credits}). "
                f"Cargo: {self.state.cargo['quantum_foam']} QF | "
                f"{self.state.cargo['retro_organics']} RO | "
                f"{self.state.cargo['neuro_symbolics']} NS. "
                f"Empty holds: {self.state.empty_holds}."
            ),
            (
                f"Warp: {self.state.warp}/{self.state.max_warp}. "
                f"Shields: {self.state.shields}/{self.state.max_shields}. "
                f"Fighters: {self.state.fighters}."
            ),
            f"Port: {port_text}",
            "Garrison: None",
        ]
        return "\n".join(lines)

    def _map_local(self) -> str:
        sector = self.state.sector
        neighbors = self.graph.get(sector, [])
        visited = sum(1 for s in neighbors if s in self.state.visited_sectors)
        total = len(neighbors)
        unvisited = [s for s in neighbors if s not in self.state.visited_sectors]
        nearest = ", ".join(f"{s} (1 hops)" for s in unvisited[:3]) if unvisited else "None"
        return (
            f"Local map around sector {sector}: {visited}/{total} visited, {len(unvisited)} unvisited.\n"
            "Region: Federation Space.\n"
            f"Nearest unvisited: {nearest}.\n"
            f"We are currently in sector {sector}."
        )

    def initial_observation(self) -> str:
        return (
            f"[EVENT] status.snapshot: {self._status_snapshot()}\n"
            f"[EVENT] map.local: {self._map_local()}\n\n"
            f"[REMINDER] {ACTION_FORMAT_REMINDER}"
        )

    def _bfs_path(self, start: int, target: int) -> Optional[list[int]]:
        if start == target:
            return [start]
        queue: deque[int] = deque([start])
        parent: dict[int, Optional[int]] = {start: None}
        while queue:
            cur = queue.popleft()
            for nxt in self.graph.get(cur, []):
                if nxt in parent:
                    continue
                parent[nxt] = cur
                if nxt == target:
                    path: list[int] = [target]
                    while parent[path[-1]] is not None:
                        path.append(parent[path[-1]])
                    path.reverse()
                    return path
                queue.append(nxt)
        return None

    def _emit_error(self, endpoint: str, message: str) -> str:
        self.bad_actions_count += 1
        payload = {
            "endpoint": endpoint,
            "error": message,
            "source": {"type": "synthetic"},
            "synthesized": True,
            "status": 400,
        }
        return f"[EVENT] error: {json.dumps(payload)}\n\n[REMINDER] {ACTION_FORMAT_REMINDER}"

    def _handle_list_known_ports(self, args: dict[str, Any]) -> str:
        from_sector = int(args.get("from_sector", self.state.sector))
        mega_only = bool(args.get("mega", False))
        commodity = args.get("commodity")
        trade_type = args.get("trade_type")

        entries: list[tuple[int, int, PortMarket]] = []
        for sector, market in self.ports.items():
            if mega_only and not market.name.startswith("MEGA"):
                continue
            if commodity and trade_type:
                commodity_name = _canonical_commodity(str(commodity))
                if str(trade_type) == "sell" and commodity_name not in market.buys:
                    continue
                if str(trade_type) == "buy" and commodity_name not in market.sells:
                    continue
            path = self._bfs_path(from_sector, sector)
            if not path:
                continue
            entries.append((sector, len(path) - 1, market))

        entries.sort(key=lambda item: item[1])
        if not entries:
            return f"[EVENT] ports.list: No matching ports found from sector {from_sector}.\n\n[REMINDER] {ACTION_FORMAT_REMINDER}"

        lines = [f"[EVENT] ports.list: Found {len(entries)} ports from sector {from_sector}:"]
        for sector, hops, market in entries[:10]:
            lines.append(f"  - Sector {sector} ({hops} hops): {market.summary()}")
        lines.append("")
        lines.append(f"[REMINDER] {ACTION_FORMAT_REMINDER}")
        return "\n".join(lines)

    def _handle_plot_course(self, args: dict[str, Any]) -> str:
        to_sector = args.get("to_sector")
        if to_sector is None:
            return self._emit_error("plot_course", "Missing required argument: to_sector")
        to_sector = int(to_sector)
        path = self._bfs_path(self.state.sector, to_sector)
        if not path:
            return self._emit_error("plot_course", f"No known route to sector {to_sector}")
        distance = max(0, len(path) - 1)
        return (
            f"[EVENT] course.plot: Course: {path}. Distance: {distance}.\n\n"
            f"[REMINDER] {ACTION_FORMAT_REMINDER}"
        )

    def _handle_move(self, args: dict[str, Any]) -> str:
        to_sector = args.get("to_sector")
        if to_sector is None:
            return self._emit_error("move", "Missing required argument: to_sector")
        to_sector = int(to_sector)
        current = self.state.sector
        if to_sector not in self.graph.get(current, []):
            return self._emit_error(
                "move", f"Sector {to_sector} is not adjacent to current sector {current}"
            )

        self.state.sector = to_sector
        self.state.warp = max(0, self.state.warp - 3)
        self.state.visited_sectors.add(to_sector)

        return (
            f"[EVENT] movement.start: Entering hyperspace to sector {to_sector} (ETA: 0.5s). "
            "Region: Federation Space.\n"
            f"[EVENT] movement.complete: {self._status_snapshot()}\n"
            f"[EVENT] map.local: {self._map_local()}\n\n"
            f"[REMINDER] {ACTION_FORMAT_REMINDER}"
        )

    def _handle_trade(self, args: dict[str, Any]) -> str:
        commodity_raw = args.get("commodity")
        quantity = args.get("quantity")
        trade_type = args.get("trade_type")
        if commodity_raw is None or quantity is None or trade_type is None:
            return self._emit_error(
                "trade", "Missing required arguments: commodity, quantity, trade_type"
            )

        commodity = _canonical_commodity(str(commodity_raw))
        if commodity not in self.state.cargo:
            return self._emit_error("trade", f"Unknown commodity: {commodity_raw}")

        quantity = int(quantity)
        if quantity <= 0:
            return self._emit_error("trade", "Quantity must be positive")

        port = self.ports.get(self.state.sector)
        if not port:
            return self._emit_error("trade", "No port in this sector")

        trade_type = str(trade_type)
        if trade_type == "sell":
            if commodity not in port.buys:
                return self._emit_error("trade", f"Port does not buy {commodity}")
            if self.state.cargo[commodity] < quantity:
                return self._emit_error(
                    "trade", f"Insufficient cargo. Have {self.state.cargo[commodity]}, need {quantity}"
                )
            price = port.buys[commodity]
            total = price * quantity
            self.state.cargo[commodity] -= quantity
            self.state.credits += total
            action_text = (
                f"Sold {quantity} {_display_commodity(commodity)} (@ {price} each, total {total})"
            )
        elif trade_type == "buy":
            if commodity not in port.sells:
                return self._emit_error("trade", f"Port does not sell {commodity}")
            if self.state.empty_holds < quantity:
                return self._emit_error(
                    "trade", f"Not enough cargo space. Available: {self.state.empty_holds}"
                )
            price = port.sells[commodity]
            total = price * quantity
            if self.state.credits < total:
                return self._emit_error(
                    "trade", f"Insufficient credits. Have {self.state.credits}, need {total}"
                )
            self.state.cargo[commodity] += quantity
            self.state.credits -= total
            action_text = (
                f"Bought {quantity} {_display_commodity(commodity)} (@ {price} each, total {total})"
            )
        else:
            return self._emit_error("trade", f"Unknown trade_type: {trade_type}")

        self.trade_events.append(
            {
                "sector": self.state.sector,
                "commodity": commodity,
                "quantity": quantity,
                "trade_type": trade_type,
                "credits": self.state.credits,
            }
        )

        return (
            f"[EVENT] trade.executed: Trade executed. Credits: {self.state.credits}. {action_text}. "
            f"Cargo: {self.state.cargo['quantum_foam']} QF | {self.state.cargo['retro_organics']} RO | "
            f"{self.state.cargo['neuro_symbolics']} NS. Fighters: {self.state.fighters}.\n"
            f"[EVENT] status.update: Status update: Sector {self.state.sector}; Credits {self.state.credits} "
            f"(bank {self.state.bank_credits}); Warp {self.state.warp}/{self.state.max_warp}; "
            f"Shields {self.state.shields}/{self.state.max_shields}; Fighters {self.state.fighters};\n"
            f"[EVENT] port.update: Port update at sector {self.state.sector} ({port.name}).\n\n"
            f"[REMINDER] {ACTION_FORMAT_REMINDER}"
        )

    def _handle_my_status(self, _args: dict[str, Any]) -> str:
        return (
            f"[EVENT] status.snapshot: {self._status_snapshot()}\n"
            f"[EVENT] map.local: {self._map_local()}\n\n"
            f"[REMINDER] {ACTION_FORMAT_REMINDER}"
        )

    def _handle_local_map_region(self, args: dict[str, Any]) -> str:
        center = int(args.get("center_sector", self.state.sector))
        hops = int(args.get("max_hops", 1))
        neighbors = self.graph.get(center, [])
        return (
            f"[EVENT] map.region: Region map around sector {center} (max_hops={hops}). "
            f"Known adjacent sectors: {neighbors}.\n\n"
            f"[REMINDER] {ACTION_FORMAT_REMINDER}"
        )

    def _handle_wait_in_idle_state(self, _args: dict[str, Any]) -> str:
        return f"[EVENT] idle.complete: Wait complete.\n\n[REMINDER] {ACTION_FORMAT_REMINDER}"

    def _handle_load_game_info(self, args: dict[str, Any]) -> str:
        topic = str(args.get("topic", "general"))
        return (
            f"[EVENT] info.loaded: Loaded game info topic '{topic}'. "
            "Use trading and movement tools to execute the task.\n\n"
            f"[REMINDER] {ACTION_FORMAT_REMINDER}"
        )

    def _handle_dump_cargo(self, args: dict[str, Any]) -> str:
        items = args.get("items")
        if not isinstance(items, list) or not items:
            return self._emit_error("dump_cargo", "items must be a non-empty list")

        dumped: dict[str, int] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            commodity = _canonical_commodity(str(item.get("commodity", "")))
            units = int(item.get("units", 0))
            if commodity not in self.state.cargo or units <= 0:
                continue
            amount = min(units, self.state.cargo[commodity])
            if amount <= 0:
                continue
            self.state.cargo[commodity] -= amount
            dumped[commodity] = dumped.get(commodity, 0) + amount

        if not dumped:
            return self._emit_error("dump_cargo", "No cargo was dumped")

        salvage_id = str(uuid.uuid4())
        self.salvage_by_id[salvage_id] = Salvage(
            salvage_id=salvage_id,
            sector=self.state.sector,
            cargo=dumped,
        )
        return (
            f"[EVENT] salvage.created: Salvage created in sector {self.state.sector}. "
            f"ID: {salvage_id}, cargo: {dumped}.\n"
            f"[EVENT] status.update: Status update: Sector {self.state.sector}; Credits {self.state.credits}.\n\n"
            f"[REMINDER] {ACTION_FORMAT_REMINDER}"
        )

    def _handle_salvage_collect(self, args: dict[str, Any]) -> str:
        salvage_id = str(args.get("salvage_id", "")).strip()
        if not salvage_id:
            return self._emit_error("salvage_collect", "Missing required argument: salvage_id")

        salvage = self.salvage_by_id.get(salvage_id)
        if not salvage:
            return self._emit_error("salvage_collect", f"Unknown salvage id: {salvage_id}")
        if salvage.sector != self.state.sector:
            return self._emit_error(
                "salvage_collect", f"Salvage {salvage_id} is not in current sector {self.state.sector}"
            )

        units = sum(salvage.cargo.values())
        if units > self.state.empty_holds:
            return self._emit_error(
                "salvage_collect", f"Not enough cargo space. Available: {self.state.empty_holds}"
            )

        for commodity, amount in salvage.cargo.items():
            self.state.cargo[commodity] += amount
        del self.salvage_by_id[salvage_id]

        return (
            f"[EVENT] salvage.collected: Collected salvage {salvage_id}.\n"
            f"[EVENT] status.update: Status update: Sector {self.state.sector}; Credits {self.state.credits}.\n\n"
            f"[REMINDER] {ACTION_FORMAT_REMINDER}"
        )

    def apply_action(self, action: str, args: dict[str, Any]) -> str:
        self.turn_count += 1
        handlers = {
            "list_known_ports": self._handle_list_known_ports,
            "plot_course": self._handle_plot_course,
            "move": self._handle_move,
            "trade": self._handle_trade,
            "my_status": self._handle_my_status,
            "local_map_region": self._handle_local_map_region,
            "wait_in_idle_state": self._handle_wait_in_idle_state,
            "load_game_info": self._handle_load_game_info,
            "dump_cargo": self._handle_dump_cargo,
            "salvage_collect": self._handle_salvage_collect,
        }
        handler = handlers.get(action)
        if not handler:
            return self._emit_error("unknown_action", f"Unsupported action: {action}")
        return handler(args)


def _extract_first_json_object(text: str) -> Optional[dict[str, Any]]:
    text = text.strip()
    if not text:
        return None

    candidates: list[str] = [text]

    fenced = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    candidates.extend(fenced)

    if "{" in text and "}" in text:
        start = text.find("{")
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _parse_args_blob(blob: str) -> dict[str, Any]:
    blob = blob.strip()
    if not blob:
        return {}
    try:
        parsed = json.loads(blob)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    try:
        parsed = ast.literal_eval(blob)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_action(text: str) -> tuple[Optional[str], dict[str, Any], Optional[str]]:
    raw = (text or "").strip()
    if not raw:
        return None, {}, "empty model response"

    fn_match = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\((\{[\s\S]*\})\)", raw)
    if fn_match:
        action = fn_match.group(1)
        args = _parse_args_blob(fn_match.group(2))
        return action, args, None

    parsed = _extract_first_json_object(raw)
    if parsed is None:
        return None, {}, "could not parse JSON or function-style action"

    if "action" in parsed:
        action = str(parsed["action"]).strip()
        args = parsed.get("args")
        if not isinstance(args, dict):
            args = {}
        return action, args, None

    if "name" in parsed:
        action = str(parsed["name"]).strip()
        args = parsed.get("arguments")
        if not isinstance(args, dict):
            args = {}
        return action, args, None

    return None, {}, "parsed JSON object missing action/name field"


def _extract_error_event(observation: str) -> Optional[dict[str, Any]]:
    match = re.search(r"\[EVENT\] error:\s*(\{.*\})", observation)
    if not match:
        return None
    payload_text = match.group(1).strip()
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return {"raw": payload_text}
    return payload if isinstance(payload, dict) else {"raw": payload_text}


def _provider_from_str(provider: str) -> LLMProvider:
    normalized = provider.strip().lower()
    if normalized == "openai":
        return LLMProvider.OPENAI
    if normalized == "google":
        return LLMProvider.GOOGLE
    if normalized == "anthropic":
        return LLMProvider.ANTHROPIC
    raise ValueError(f"Unsupported provider: {provider}")


def _load_system_instruction(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _thinking_config_from_arg(value: str) -> Optional[UnifiedThinkingConfig]:
    normalized = value.strip().lower()
    if normalized in {"", "none", "default", "unlimited"}:
        return None
    budget = int(value)
    if budget <= 0:
        return None
    return UnifiedThinkingConfig(enabled=True, budget_tokens=budget, include_thoughts=True)


def _get_openai_inference_debug(llm_service: Any) -> Optional[dict[str, Any]]:
    getter = getattr(llm_service, "get_last_inference_debug", None)
    if not callable(getter):
        return None
    try:
        payload = getter()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to collect OpenAI inference debug payload: {}", exc)
        return None
    return payload if isinstance(payload, dict) else None


async def _run_benchmark(args: argparse.Namespace) -> int:
    provider = _provider_from_str(args.provider)

    if provider == LLMProvider.OPENAI and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "dummy"

    thinking = _thinking_config_from_arg(args.thinking_budget)
    config = LLMServiceConfig(
        provider=provider,
        model=args.model,
        thinking=thinking,
        function_call_timeout_secs=args.function_call_timeout_secs,
        run_in_parallel=False,
        openai_base_url=args.openai_base_url,
    )
    llm_service = create_llm_service(config)

    harness_dir = Path(__file__).resolve().parent
    system_instruction = _load_system_instruction(harness_dir / "system_instruction.md")

    env = MiniRLEnv()
    initial_user = create_task_instruction_user_message(args.task)
    initial_user += f"\n{ACTION_FORMAT_REMINDER}\n"

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": initial_user},
        {"role": "user", "content": env.initial_observation()},
    ]

    turn_logs: list[dict[str, Any]] = []
    finished_message: Optional[str] = None
    finished_called = False
    terminal_reason = "max_turns_exhausted"
    started = time.perf_counter()
    started_at_utc = _iso_utc_now()
    run_id = str(uuid.uuid4())
    initial_state_snapshot = env.state_snapshot()
    reached_mega_anytime = env.state.sector == MEGA_PORT_SECTOR

    logger.info(
        "HARNESS_CONFIG provider={} model={} openai_base_url={} thinking_budget={} max_tokens={} max_turns={}",
        provider.value,
        args.model,
        args.openai_base_url or "(default)",
        thinking.budget_tokens if thinking else "default",
        args.max_tokens,
        args.max_turns,
    )

    for turn in range(1, args.max_turns + 1):
        state_before = env.state_snapshot()
        bad_before = env.bad_actions_count

        context = LLMContext(messages=messages)
        t0 = time.perf_counter()
        try:
            response = await llm_service.run_inference(context, max_tokens=args.max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.error("TURN {} inference failure: {}", turn, exc)
            observation = env._emit_error("inference", str(exc))
            error_event = _extract_error_event(observation)
            messages.append({"role": "user", "content": observation})
            bad_after = env.bad_actions_count
            state_after = env.state_snapshot()
            turn_logs.append(
                {
                    "turn": turn,
                    "decision_ms": round((time.perf_counter() - t0) * 1000, 2),
                    "action": None,
                    "args": {},
                    "parse_error": "inference failure",
                    "raw_response": "",
                    "bad_actions_before": bad_before,
                    "bad_actions_after": bad_after,
                    "bad_action_increment": bad_after - bad_before,
                    "state_before": state_before,
                    "state_after": state_after,
                    "error_event": error_event,
                }
            )
            continue

        decision_ms = round((time.perf_counter() - t0) * 1000, 2)
        assistant_text = (response or "").strip()
        openai_inference_debug = _get_openai_inference_debug(llm_service)
        messages.append({"role": "assistant", "content": assistant_text})

        action, action_args, parse_error = parse_action(assistant_text)

        if parse_error:
            observation = env._emit_error("parser", parse_error)
            error_event = _extract_error_event(observation)
            messages.append({"role": "user", "content": observation})
            bad_after = env.bad_actions_count
            state_after = env.state_snapshot()
            logger.info(
                "TURN {} decision_ms={} action=parse_error bad_actions={} err={}",
                turn,
                decision_ms,
                env.bad_actions_count,
                parse_error,
            )
            turn_logs.append(
                {
                    "turn": turn,
                    "decision_ms": decision_ms,
                    "action": None,
                    "args": {},
                    "parse_error": parse_error,
                    "raw_response": assistant_text,
                    "bad_actions_before": bad_before,
                    "bad_actions_after": bad_after,
                    "bad_action_increment": bad_after - bad_before,
                    "state_before": state_before,
                    "state_after": state_after,
                    "error_event": error_event,
                    "openai_inference_debug": openai_inference_debug,
                }
            )
            continue

        if action == "finished":
            finished_called = True
            terminal_reason = "finished_action"
            finished_message = str(action_args.get("message") or action_args.get("summary") or "").strip()
            state_after = env.state_snapshot()
            bad_after = env.bad_actions_count
            logger.info(
                "TURN {} decision_ms={} action=finished message_len={} bad_actions={}",
                turn,
                decision_ms,
                len(finished_message),
                env.bad_actions_count,
            )
            turn_logs.append(
                {
                    "turn": turn,
                    "decision_ms": decision_ms,
                    "action": action,
                    "args": action_args,
                    "parse_error": None,
                    "raw_response": assistant_text,
                    "bad_actions_before": bad_before,
                    "bad_actions_after": bad_after,
                    "bad_action_increment": bad_after - bad_before,
                    "state_before": state_before,
                    "state_after": state_after,
                    "openai_inference_debug": openai_inference_debug,
                }
            )
            break

        observation = env.apply_action(action, action_args)
        error_event = _extract_error_event(observation)
        messages.append({"role": "user", "content": observation})
        bad_after = env.bad_actions_count
        state_after = env.state_snapshot()
        reached_mega_anytime = reached_mega_anytime or (env.state.sector == MEGA_PORT_SECTOR)

        logger.info(
            "TURN {} decision_ms={} action={} bad_actions={} sector={} warp={}",
            turn,
            decision_ms,
            action,
            env.bad_actions_count,
            env.state.sector,
            env.state.warp,
        )
        turn_logs.append(
            {
                "turn": turn,
                "decision_ms": decision_ms,
                "action": action,
                "args": action_args,
                "parse_error": None,
                "raw_response": assistant_text,
                "bad_actions_before": bad_before,
                "bad_actions_after": bad_after,
                "bad_action_increment": bad_after - bad_before,
                "state_before": state_before,
                "state_after": state_after,
                "error_event": error_event,
                "openai_inference_debug": openai_inference_debug,
            }
        )

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    ended_at_utc = _iso_utc_now()

    final_sector_is_mega = env.state.sector == MEGA_PORT_SECTOR
    coherent_report = False
    if finished_message:
        lowered = finished_message.lower()
        coherent_report = "profit" in lowered and (
            "trade" in lowered or "traded" in lowered or "ports" in lowered
        )

    success = bool(finished_message and final_sector_is_mega and coherent_report)

    summary = {
        "schema_version": RUN_SCHEMA_VERSION,
        "success": success,
        "success_legacy": success,
        "bad_actions_count": env.bad_actions_count,
        "finished_message": finished_message,
        "final_sector": env.state.sector,
        "reached_mega": final_sector_is_mega,
        "final_sector_is_mega": final_sector_is_mega,
        "reached_mega_anytime": reached_mega_anytime,
        "coherent_report": coherent_report,
        "finished_called": finished_called,
        "terminal_reason": terminal_reason,
        "turns_executed": len(turn_logs),
        "elapsed_ms": total_ms,
        "provider": provider.value,
        "model": args.model,
        "thinking_budget": thinking.budget_tokens if thinking else None,
        "max_tokens": args.max_tokens,
    }

    print(f"SUCCESS={summary['success']}")
    print(f"BAD_ACTIONS_COUNT={summary['bad_actions_count']}")
    print(f"FINAL_SECTOR={summary['final_sector']}")
    print(f"COHERENT_REPORT={summary['coherent_report']}")
    print(f"TURNS={summary['turns_executed']}")
    print(f"ELAPSED_MS={summary['elapsed_ms']}")
    if finished_message:
        print(f"FINISH_MESSAGE={finished_message}")

    if args.log_json:
        git_sha = _git_sha(REPO_ROOT)
        config_snapshot = {
            "provider": provider.value,
            "model": args.model,
            "openai_base_url": args.openai_base_url,
            "thinking_budget": thinking.budget_tokens if thinking else None,
            "max_tokens": args.max_tokens,
            "max_turns": args.max_turns,
            "function_call_timeout_secs": args.function_call_timeout_secs,
            "task": args.task,
        }
        metadata = {
            "run_id": run_id,
            "runner_version": RUNNER_VERSION,
            "started_at_utc": started_at_utc,
            "ended_at_utc": ended_at_utc,
            "repo_root": str(REPO_ROOT),
            "git_sha": git_sha,
            "system_instruction_path": str(harness_dir / "system_instruction.md"),
            "system_instruction_hash": _sha256_text(system_instruction),
            "task_prompt_hash": _sha256_text(args.task),
            "action_format_reminder_hash": _sha256_text(ACTION_FORMAT_REMINDER),
            "initial_state": initial_state_snapshot,
        }
        termination = {
            "reason": terminal_reason,
            "finished_called": finished_called,
            "finished_message": finished_message,
            "elapsed_ms": total_ms,
        }
        payload = {
            "schema_version": RUN_SCHEMA_VERSION,
            "metadata": metadata,
            "config": config_snapshot,
            "termination": termination,
            "summary": summary,
            "turns": turn_logs,
        }
        Path(args.log_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("WROTE {}", args.log_json)

    return 0 if success else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run standalone mini RL benchmark harness")
    parser.add_argument(
        "--task",
        default=DEFAULT_BENCHMARK_TASK,
        help="Task prompt for the benchmark",
    )
    parser.add_argument(
        "--provider",
        default=os.getenv("TASK_LLM_PROVIDER", "openai"),
        choices=["openai", "google", "anthropic"],
        help="LLM provider",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("TASK_LLM_MODEL", "nemotron-3-super-120b"),
        help="Model name",
    )
    parser.add_argument(
        "--openai-base-url",
        default=None,
        help="OpenAI-compatible base URL (with or without /v1)",
    )
    parser.add_argument(
        "--thinking-budget",
        default=os.getenv("TASK_LLM_THINKING_BUDGET", "512"),
        help="Thinking budget tokens, or one of: default|none|unlimited",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional per-turn max tokens override",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=40,
        help="Max inference turns before hard stop",
    )
    parser.add_argument(
        "--function-call-timeout-secs",
        type=float,
        default=float(os.getenv("TASK_LLM_FUNCTION_CALL_TIMEOUT_SECS", "20")),
        help="LLM function call timeout passed to service config",
    )
    parser.add_argument(
        "--log-json",
        default=None,
        help="Optional output file for structured run logs",
    )
    return parser


def main() -> int:
    logger.configure(handlers=[{"sink": sys.stderr, "level": os.getenv("LOGURU_LEVEL", "INFO")}])
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run_benchmark(args))


if __name__ == "__main__":
    raise SystemExit(main())
