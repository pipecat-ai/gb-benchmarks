"""Synthetic world model for mini RL benchmark harness.

This module mirrors TaskAgent event-driven semantics:
- async tools return immediate ack in the harness
- real state updates are committed when synthetic events are delivered
"""

from __future__ import annotations

import json
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


MEGA_PORT_SECTOR = 1611
UNIVERSE_SIZE = 5000
COMMODITIES = ("quantum_foam", "retro_organics", "neuro_symbolics")
AVAILABLE_INFO_TOPICS = (
    "exploration",
    "trading",
    "combat",
    "corporations",
    "transfers",
    "ships",
    "event_logs",
)
GAME_INFO_FRAGMENTS_DIR = Path(__file__).resolve().parent / "game_info_fragments"


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso8601_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _load_game_info_fragment(topic: str) -> str:
    path = GAME_INFO_FRAGMENTS_DIR / f"{topic}.md"
    if not path.exists():
        raise FileNotFoundError(f"Knowledge file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


@dataclass
class PortMarket:
    name: str
    buys: dict[str, int] = field(default_factory=dict)
    sells: dict[str, int] = field(default_factory=dict)
    stock: dict[str, int] = field(default_factory=dict)

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
    ship_name: str = "Kestrel Courier"
    ship_type: str = "courier"
    ship_id: str = "d95cf2de-0000-4000-8000-000000000000"
    corporation_name: Optional[str] = None
    combat_id: Optional[str] = None

    @property
    def used_holds(self) -> int:
        return sum(self.cargo.values())

    @property
    def empty_holds(self) -> int:
        return max(0, self.holds_total - self.used_holds)


@dataclass
class EventPlan:
    event_name: str
    source_tool: str
    delay_s: float = 0.0
    summary: Any = None
    payload: Any = None
    mutation: Optional[Callable[[], None]] = None
    summary_factory: Optional[Callable[[], Any]] = None
    payload_factory: Optional[Callable[[], Any]] = None


@dataclass
class ToolExecution:
    payload: dict[str, Any]
    events: list[EventPlan]
    ok: bool


class SyntheticWorld:
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
        2833: [4884],
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
        self.ports = {
            sector: PortMarket(
                name=market.name,
                buys=dict(market.buys),
                sells=dict(market.sells),
                stock=dict(market.stock),
            )
            for sector, market in type(self).ports.items()
        }
        self.bad_actions_count = 0
        self.trade_events: list[dict[str, Any]] = []
        self.salvage_by_id: dict[str, Salvage] = {}
        self.event_history: list[dict[str, Any]] = []
        self.garrisons: dict[int, int] = {}
        self.corp_members: list[str] = ["Jane Eyre"]
        self.corporation_id = "corp-7f4c1d"
        self.player_name = "Jane Eyre"
        self.current_task_id: Optional[str] = None

        for market in self.ports.values():
            for commodity in COMMODITIES:
                if commodity not in market.stock:
                    if commodity in market.sells:
                        market.stock[commodity] = 1200
                    elif commodity in market.buys:
                        market.stock[commodity] = 0
                    else:
                        market.stock[commodity] = 0

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
            "ship_name": self.state.ship_name,
            "ship_type": self.state.ship_type,
            "ship_id": self.state.ship_id,
            "corporation_name": self.state.corporation_name,
            "fighters": self.state.fighters,
            "combat_id": self.state.combat_id,
        }

    def record_event(
        self,
        *,
        event_name: str,
        response_data: Any,
        event_payload: Any = None,
        source_tool: str,
    ) -> None:
        record = {
            "timestamp": _iso_utc_now(),
            "event_name": event_name,
            "response_data": response_data,
            "event_payload": event_payload,
            "source_tool": source_tool,
            "sector": self.state.sector,
            "task_id": self.current_task_id,
        }
        self.event_history.append(record)

    def increment_bad_action(self) -> None:
        self.bad_actions_count += 1

    def _corporation_payload(self) -> Optional[dict[str, Any]]:
        if not self.state.corporation_name:
            return None
        return {
            "corp_id": self.corporation_id,
            "name": self.state.corporation_name,
            "member_count": len(self.corp_members),
        }

    @staticmethod
    def _port_code_and_mega(name: str) -> tuple[str, bool]:
        mega = name.startswith("MEGA")
        code = name.replace("MEGA", "").strip() if mega else name
        return code, mega

    def _port_payload_for_sector(self, sector: int) -> Optional[dict[str, Any]]:
        market = self.ports.get(sector)
        if market is None:
            return None
        code, mega = self._port_code_and_mega(market.name)
        prices = {**market.buys, **market.sells}
        return {
            "code": code,
            "mega": mega,
            "prices": dict(prices),
            "stock": dict(market.stock),
            "observed_at": _iso_utc_now(),
        }

    def _garrison_payload(self, sector: int) -> Optional[dict[str, Any]]:
        fighters = self.garrisons.get(sector, 0)
        if fighters <= 0:
            return None
        return {
            "owner_name": self.player_name,
            "owner_id": "player-jane-eyre",
            "fighters": fighters,
            "mode": "offensive",
            "toll_amount": 0,
        }

    def _salvage_payload_for_sector(self, sector: int) -> list[dict[str, Any]]:
        containers: list[dict[str, Any]] = []
        for salvage in self.salvage_by_id.values():
            if salvage.sector != sector:
                continue
            containers.append(
                {
                    "salvage_id": salvage.salvage_id,
                    "credits": 0,
                    "scrap": 0,
                    "cargo": dict(salvage.cargo),
                }
            )
        return containers

    def _sector_payload(self, sector: int) -> dict[str, Any]:
        corp = self._corporation_payload()
        player_entry: dict[str, Any] = {
            "name": self.player_name,
            "ship": {
                "ship_name": self.state.ship_name,
                "ship_type": self.state.ship_type,
            },
        }
        if corp:
            player_entry["corporation"] = {"name": corp["name"]}

        return {
            "id": sector,
            "adjacent_sectors": list(self.graph.get(sector, [])),
            "region": "Federation Space",
            "port": self._port_payload_for_sector(sector),
            "players": [player_entry] if sector == self.state.sector else [],
            "garrison": self._garrison_payload(sector),
            "salvage": self._salvage_payload_for_sector(sector),
            "unowned_ships": [],
        }

    def _player_payload(self) -> dict[str, Any]:
        visited = int(self.state.explored_count)
        corp_known = visited + 300
        total_known = corp_known + 14

        payload: dict[str, Any] = {
            "name": self.player_name,
            "display_name": self.player_name,
            "credits_on_hand": self.state.credits,
            "credits_in_bank": self.state.bank_credits,
            "sectors_visited": visited,
            "corp_sectors_visited": corp_known,
            "total_sectors_known": total_known,
            "universe_size": UNIVERSE_SIZE,
        }
        corp = self._corporation_payload()
        if corp:
            payload["corporation"] = {"name": corp["name"]}
        return payload

    def _ship_payload(self) -> dict[str, Any]:
        return {
            "ship_id": self.state.ship_id,
            "ship_name": self.state.ship_name,
            "ship_type": self.state.ship_type,
            "ship_type_name": self.state.ship_type,
            "credits": self.state.credits,
            "cargo": dict(self.state.cargo),
            "cargo_capacity": self.state.holds_total,
            "warp_power": self.state.warp,
            "warp_power_capacity": self.state.max_warp,
            "shields": self.state.shields,
            "max_shields": self.state.max_shields,
            "fighters": self.state.fighters,
        }

    def _status_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "player": self._player_payload(),
            "ship": self._ship_payload(),
            "sector": self._sector_payload(self.state.sector),
            "current_sector": self.state.sector,
        }
        corp = self._corporation_payload()
        if corp:
            payload["corporation"] = corp
        return payload

    def _map_payload(self, center_sector: int, max_hops: int) -> dict[str, Any]:
        max_hops = max(0, int(max_hops))
        queue: deque[tuple[int, int]] = deque([(center_sector, 0)])
        seen: set[int] = {center_sector}
        sectors: list[dict[str, Any]] = []

        while queue:
            sector, hops = queue.popleft()
            visited = sector in self.state.visited_sectors
            sectors.append(
                {
                    "id": sector,
                    "visited": visited,
                    "hops_from_center": hops,
                    "region": "Federation Space" if visited else None,
                }
            )
            if hops >= max_hops:
                continue
            for neighbor in self.graph.get(sector, []):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append((neighbor, hops + 1))

        total_visited = sum(1 for sector in sectors if sector.get("visited"))
        total_sectors = len(sectors)
        total_unvisited = total_sectors - total_visited
        sectors.sort(key=lambda item: (item.get("hops_from_center", 0), item.get("id", 0)))

        return {
            "center_sector": center_sector,
            "current_sector": self.state.sector,
            "max_hops": max_hops,
            "neighbors": list(self.graph.get(center_sector, [])),
            "sectors": sectors,
            "total_visited": total_visited,
            "total_sectors": total_sectors,
            "total_unvisited": total_unvisited,
        }

    def _movement_start_payload(self, target: int) -> dict[str, Any]:
        return {
            "sector": {
                "id": target,
                "region": "Federation Space",
            },
            "hyperspace_time": 0.5,
        }

    def _movement_complete_payload(self, *, first_visit: bool) -> dict[str, Any]:
        payload = self._status_payload()
        payload["first_visit"] = first_visit
        payload["known_to_corp"] = not first_visit
        return payload

    def _port_update_payload(self, sector: int) -> dict[str, Any]:
        return {
            "sector": {
                "id": sector,
                "port": self._port_payload_for_sector(sector),
            }
        }

    def _error(self, endpoint: str, message: str) -> ToolExecution:
        self.increment_bad_action()
        return ToolExecution(
            payload={
                "error": message,
                "endpoint": endpoint,
                "status": 400,
                "source": {"type": "synthetic"},
                "synthesized": True,
            },
            events=[],
            ok=False,
        )

    def _status_snapshot(self) -> str:
        sector = self.state.sector
        neighbors = self.graph.get(sector, [])
        port = self.ports.get(sector)
        port_text = port.summary() if port else "None"
        garrison_qty = self.garrisons.get(sector, 0)
        lines = [
            "Player: Jane Eyre",
            f"In sector {sector}.",
            f"Adjacent sectors: {neighbors}",
            "Region: Federation Space",
            f"Explored {self.state.explored_count} sectors ({self.state.explored_percent}%).",
            f"Ship: {self.state.ship_name} ({self.state.ship_type})",
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
            f"Garrison: {garrison_qty}",
        ]
        if self.state.corporation_name:
            lines.append(f"Corporation: {self.state.corporation_name}")
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

    def initial_events(self) -> list[EventPlan]:
        return [
            EventPlan(
                event_name="status.snapshot",
                source_tool="my_status",
                payload_factory=lambda: self._status_payload(),
            ),
            EventPlan(
                event_name="map.local",
                source_tool="my_status",
                payload_factory=lambda: self._map_payload(self.state.sector, 1),
            ),
        ]

    def execute_tool(self, name: str, args: dict[str, Any]) -> ToolExecution:
        handlers = {
            "my_status": self._handle_my_status,
            "plot_course": self._handle_plot_course,
            "local_map_region": self._handle_local_map_region,
            "list_known_ports": self._handle_list_known_ports,
            "move": self._handle_move,
            "trade": self._handle_trade,
            "salvage_collect": self._handle_salvage_collect,
            "send_message": self._handle_send_message,
            "recharge_warp_power": self._handle_recharge_warp_power,
            "transfer_warp_power": self._handle_transfer_warp_power,
            "place_fighters": self._handle_place_fighters,
            "collect_fighters": self._handle_collect_fighters,
            "event_query": self._handle_event_query,
            "purchase_fighters": self._handle_purchase_fighters,
            "create_corporation": self._handle_create_corporation,
            "join_corporation": self._handle_join_corporation,
            "leave_corporation": self._handle_leave_corporation,
            "kick_corporation_member": self._handle_kick_corporation_member,
            "corporation_info": self._handle_corporation_info,
            "purchase_ship": self._handle_purchase_ship,
            "rename_ship": self._handle_rename_ship,
            "bank_deposit": self._handle_bank_deposit,
            "bank_withdraw": self._handle_bank_withdraw,
            "transfer_credits": self._handle_transfer_credits,
            "dump_cargo": self._handle_dump_cargo,
            "combat_initiate": self._handle_combat_initiate,
            "combat_action": self._handle_combat_action,
            "load_game_info": self._handle_load_game_info,
            "wait_in_idle_state": self._handle_wait_in_idle_state,
        }
        handler = handlers.get(name)
        if handler is None:
            return self._error("unknown_tool", f"Unknown tool: {name}")
        return handler(args)

    def _handle_my_status(self, _args: dict[str, Any]) -> ToolExecution:
        payload = {"status": "success"}
        events = [
            EventPlan(
                event_name="status.snapshot",
                source_tool="my_status",
                payload_factory=lambda: self._status_payload(),
            ),
            EventPlan(
                event_name="map.local",
                source_tool="my_status",
                payload_factory=lambda: self._map_payload(self.state.sector, 1),
                delay_s=0.05,
            ),
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_plot_course(self, args: dict[str, Any]) -> ToolExecution:
        to_sector = args.get("to_sector")
        if to_sector is None:
            return self._error("plot_course", "Missing required argument: to_sector")
        try:
            target = int(to_sector)
        except Exception:
            return self._error("plot_course", "to_sector must be an integer")

        try:
            from_sector = int(args.get("from_sector", self.state.sector))
        except Exception:
            return self._error("plot_course", "from_sector must be an integer")

        path = self._bfs_path(from_sector, target)
        if not path:
            return self._error("plot_course", f"No known route from sector {from_sector} to sector {target}")

        distance = max(0, len(path) - 1)
        payload = {
            "status": "success",
            "from_sector": from_sector,
            "to_sector": target,
            "distance": distance,
            "path": path,
        }
        events = [
            EventPlan(
                event_name="course.plot",
                source_tool="plot_course",
                payload=payload,
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_local_map_region(self, args: dict[str, Any]) -> ToolExecution:
        try:
            center = int(args.get("center_sector", self.state.sector))
        except Exception:
            return self._error("local_map_region", "center_sector must be an integer")
        try:
            hops = int(args.get("max_hops", 3))
        except Exception:
            return self._error("local_map_region", "max_hops must be an integer")
        payload = self._map_payload(center, hops)
        payload["status"] = "success"
        events = [
            EventPlan(
                event_name="map.region",
                source_tool="local_map_region",
                payload=payload,
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_list_known_ports(self, args: dict[str, Any]) -> ToolExecution:
        try:
            from_sector = int(args.get("from_sector", self.state.sector))
        except Exception:
            return self._error("list_known_ports", "from_sector must be an integer")

        mega_filter = args.get("mega")
        if mega_filter is not None and not isinstance(mega_filter, bool):
            return self._error("list_known_ports", "mega must be a boolean")

        max_hops_raw = args.get("max_hops")
        if max_hops_raw is None:
            max_hops = 100 if mega_filter is True else 5
        else:
            try:
                max_hops = int(max_hops_raw)
            except Exception:
                return self._error("list_known_ports", "max_hops must be an integer")

        if max_hops < 0 or max_hops > 100:
            return self._error("list_known_ports", "max_hops must be between 0 and 100")

        port_type = args.get("port_type")
        port_type_filter = str(port_type).strip().upper() if isinstance(port_type, str) and port_type.strip() else None
        commodity = args.get("commodity")
        trade_type = args.get("trade_type")

        entries: list[dict[str, Any]] = []
        for sector, market in self.ports.items():
            port_code, is_mega = self._port_code_and_mega(market.name)

            if mega_filter is True and not is_mega:
                continue
            if mega_filter is False and is_mega:
                continue
            if port_type_filter is not None and port_code.upper() != port_type_filter:
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
            hops_from_start = len(path) - 1
            if hops_from_start > max_hops:
                continue
            port_payload = self._port_payload_for_sector(sector)
            entries.append(
                {
                    "sector": {"id": sector, "port": port_payload},
                    "hops_from_start": hops_from_start,
                    "last_visited": None,
                    "updated_at": port_payload.get("observed_at") if isinstance(port_payload, dict) else None,
                }
            )

        entries.sort(key=lambda item: item["hops_from_start"])
        payload = {
            "status": "success",
            "from_sector": from_sector,
            "count": len(entries),
            "total_ports_found": len(entries),
            "max_hops": max_hops,
            "port_type": port_type_filter,
            "mega": mega_filter,
            "commodity": commodity,
            "trade_type": trade_type,
            "ports": entries[:30],
        }

        events = [
            EventPlan(
                event_name="ports.list",
                source_tool="list_known_ports",
                payload=payload,
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_move(self, args: dict[str, Any]) -> ToolExecution:
        to_sector = args.get("to_sector")
        if to_sector is None:
            return self._error("move", "Missing required argument: to_sector")
        try:
            target = int(to_sector)
        except Exception:
            return self._error("move", "to_sector must be an integer")

        current = self.state.sector
        if target not in self.graph.get(current, []):
            return self._error("move", f"Sector {target} is not adjacent to current sector {current}")
        if self.state.warp < 3:
            return self._error("move", "Insufficient warp power")
        first_visit = target not in self.state.visited_sectors

        def apply_move() -> None:
            self.state.sector = target
            self.state.warp = max(0, self.state.warp - 3)
            self.state.visited_sectors.add(target)

        payload = {"status": "success", "from_sector": current, "to_sector": target}
        events = [
            EventPlan(
                event_name="movement.start",
                source_tool="move",
                payload=self._movement_start_payload(target),
            ),
            EventPlan(
                event_name="movement.complete",
                source_tool="move",
                delay_s=0.12,
                mutation=apply_move,
                payload_factory=lambda: self._movement_complete_payload(first_visit=first_visit),
            ),
            EventPlan(
                event_name="map.local",
                source_tool="move",
                delay_s=0.14,
                payload_factory=lambda: self._map_payload(self.state.sector, 1),
            ),
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_trade(self, args: dict[str, Any]) -> ToolExecution:
        commodity_raw = args.get("commodity")
        quantity = args.get("quantity")
        trade_type = args.get("trade_type")
        if commodity_raw is None or quantity is None or trade_type is None:
            return self._error(
                "trade", "Missing required arguments: commodity, quantity, trade_type"
            )

        commodity = _canonical_commodity(str(commodity_raw))
        if commodity not in self.state.cargo:
            return self._error("trade", f"Unknown commodity: {commodity_raw}")

        try:
            quantity_value = int(quantity)
        except Exception:
            return self._error("trade", "quantity must be an integer")
        if quantity_value <= 0:
            return self._error("trade", "Quantity must be positive")

        port = self.ports.get(self.state.sector)
        if not port:
            return self._error("trade", "No port in this sector")

        trade_type_value = str(trade_type).strip().lower()

        if trade_type_value == "sell":
            if commodity not in port.buys:
                return self._error("trade", f"Port does not buy {commodity}")
            if self.state.cargo[commodity] < quantity_value:
                return self._error(
                    "trade",
                    f"Insufficient cargo. Have {self.state.cargo[commodity]}, need {quantity_value}",
                )
            price = port.buys[commodity]
            total = price * quantity_value

            def apply_trade() -> None:
                self.state.cargo[commodity] -= quantity_value
                self.state.credits += total
                port.stock[commodity] = port.stock.get(commodity, 0) + quantity_value
                self.trade_events.append(
                    {
                        "sector": self.state.sector,
                        "commodity": commodity,
                        "quantity": quantity_value,
                        "trade_type": trade_type_value,
                        "credits": self.state.credits,
                    }
                )

        elif trade_type_value == "buy":
            if commodity not in port.sells:
                return self._error("trade", f"Port does not sell {commodity}")
            if self.state.empty_holds < quantity_value:
                return self._error(
                    "trade", f"Not enough cargo space. Available: {self.state.empty_holds}"
                )
            price = port.sells[commodity]
            total = price * quantity_value
            if self.state.credits < total:
                return self._error(
                    "trade", f"Insufficient credits. Have {self.state.credits}, need {total}"
                )

            def apply_trade() -> None:
                self.state.cargo[commodity] += quantity_value
                self.state.credits -= total
                port.stock[commodity] = max(0, port.stock.get(commodity, 0) - quantity_value)
                self.trade_events.append(
                    {
                        "sector": self.state.sector,
                        "commodity": commodity,
                        "quantity": quantity_value,
                        "trade_type": trade_type_value,
                        "credits": self.state.credits,
                    }
                )

        else:
            return self._error("trade", f"Unknown trade_type: {trade_type_value}")

        payload = {
            "status": "success",
            "trade_type": trade_type_value,
            "commodity": commodity,
            "quantity": quantity_value,
            "port_sector": self.state.sector,
        }
        events = [
            EventPlan(
                event_name="trade.executed",
                source_tool="trade",
                mutation=apply_trade,
                payload_factory=lambda: {
                    "player": self._player_payload(),
                    "ship": self._ship_payload(),
                    "trade": {
                        "trade_type": trade_type_value,
                        "commodity": commodity,
                        "units": quantity_value,
                        "price_per_unit": price,
                        "total_price": total,
                        "new_credits": self.state.credits,
                        "new_cargo": dict(self.state.cargo),
                    },
                },
            ),
            EventPlan(
                event_name="status.update",
                source_tool="trade",
                delay_s=0.03,
                payload_factory=lambda: self._status_payload(),
            ),
            EventPlan(
                event_name="port.update",
                source_tool="trade",
                delay_s=0.04,
                payload_factory=lambda: self._port_update_payload(self.state.sector),
            ),
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_salvage_collect(self, args: dict[str, Any]) -> ToolExecution:
        salvage_id = str(args.get("salvage_id", "")).strip()
        if not salvage_id:
            return self._error("salvage_collect", "Missing required argument: salvage_id")

        salvage = self.salvage_by_id.get(salvage_id)
        if salvage is None:
            return self._error("salvage_collect", f"Unknown salvage id: {salvage_id}")
        if salvage.sector != self.state.sector:
            return self._error(
                "salvage_collect", f"Salvage {salvage_id} is not in current sector {self.state.sector}"
            )

        units = sum(salvage.cargo.values())
        if units > self.state.empty_holds:
            return self._error(
                "salvage_collect",
                f"Not enough cargo space. Available: {self.state.empty_holds}",
            )
        collected_cargo = dict(salvage.cargo)

        def apply_collect() -> None:
            for commodity, amount in collected_cargo.items():
                self.state.cargo[commodity] += amount
            self.salvage_by_id.pop(salvage_id, None)

        payload = {"status": "success", "salvage_id": salvage_id}
        events = [
            EventPlan(
                event_name="salvage.collected",
                source_tool="salvage_collect",
                mutation=apply_collect,
                payload_factory=lambda: {
                    "salvage_id": salvage_id,
                    "salvage_details": {
                        "collected": {
                            "cargo": dict(collected_cargo),
                            "credits": 0,
                        },
                        "fully_collected": True,
                    },
                },
            ),
            EventPlan(
                event_name="status.update",
                source_tool="salvage_collect",
                delay_s=0.03,
                payload_factory=lambda: self._status_payload(),
            ),
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_send_message(self, args: dict[str, Any]) -> ToolExecution:
        content = str(args.get("content", "")).strip()
        if not content:
            return self._error("send_message", "Missing required argument: content")
        payload = {
            "status": "success",
            "content": content,
            "to_ship_name": args.get("to_ship_name"),
            "to_ship_id": args.get("to_ship_id"),
        }
        events = [
            EventPlan(
                event_name="chat.message",
                source_tool="send_message",
                payload={
                    "type": "direct" if (args.get("to_ship_name") or args.get("to_ship_id")) else "broadcast",
                    "from_name": self.player_name,
                    "to_name": args.get("to_ship_name") or args.get("to_ship_id") or "all",
                    "content": content,
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_recharge_warp_power(self, args: dict[str, Any]) -> ToolExecution:
        units = args.get("units")
        try:
            value = int(units)
        except Exception:
            return self._error("recharge_warp_power", "units must be an integer")
        if value <= 0:
            return self._error("recharge_warp_power", "units must be positive")

        port = self.ports.get(self.state.sector)
        if not port or not port.name.startswith("MEGA"):
            return self._error(
                "recharge_warp_power",
                f"Warp power depot is only available at a mega-port. You are in sector {self.state.sector}",
            )

        remaining_capacity = max(0, self.state.max_warp - self.state.warp)
        if remaining_capacity <= 0:
            return self._error("recharge_warp_power", "Warp power is already at maximum")

        units_to_buy = min(value, remaining_capacity)
        cost = units_to_buy * 2
        if self.state.credits < cost:
            return self._error(
                "recharge_warp_power",
                f"Insufficient credits. Have {self.state.credits}, need {cost}",
            )

        def apply_recharge() -> None:
            self.state.credits -= cost
            self.state.warp = min(self.state.max_warp, self.state.warp + units_to_buy)

        payload = {"status": "success", "units": units_to_buy, "cost": cost}
        events = [
            EventPlan(
                event_name="warp.purchase",
                source_tool="recharge_warp_power",
                mutation=apply_recharge,
                payload_factory=lambda: {
                    "units": units_to_buy,
                    "total_cost": cost,
                    "new_warp_power": self.state.warp,
                    "warp_power_capacity": self.state.max_warp,
                    "ship_name": self.state.ship_name,
                    "ship_id": self.state.ship_id,
                    "new_credits": self.state.credits,
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_transfer_warp_power(self, args: dict[str, Any]) -> ToolExecution:
        units = args.get("units")
        try:
            value = int(units)
        except Exception:
            return self._error("transfer_warp_power", "units must be an integer")
        if value <= 0:
            return self._error("transfer_warp_power", "units must be positive")
        if self.state.warp < value:
            return self._error(
                "transfer_warp_power",
                f"Insufficient warp power. Have {self.state.warp}, need {value}",
            )

        def apply_transfer() -> None:
            self.state.warp -= value

        payload = {"status": "success", "units": value}
        events = [
            EventPlan(
                event_name="warp.transfer",
                source_tool="transfer_warp_power",
                mutation=apply_transfer,
                payload={
                    "transfer_direction": "sent",
                    "transfer_details": {"warp_power": value},
                    "from": {"name": self.player_name},
                    "to": {
                        "name": str(
                            args.get("to_ship_name")
                            or args.get("to_ship_id")
                            or args.get("to_player_name")
                            or "unknown"
                        )
                    },
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_place_fighters(self, args: dict[str, Any]) -> ToolExecution:
        try:
            sector = int(args.get("sector"))
            quantity = int(args.get("quantity"))
        except Exception:
            return self._error("place_fighters", "sector and quantity must be integers")
        if quantity <= 0:
            return self._error("place_fighters", "quantity must be positive")
        if self.state.fighters < quantity:
            return self._error(
                "place_fighters", f"Insufficient fighters. Have {self.state.fighters}, need {quantity}"
            )

        def apply_place() -> None:
            self.state.fighters -= quantity
            self.garrisons[sector] = self.garrisons.get(sector, 0) + quantity

        payload = {"status": "success", "sector": sector, "quantity": quantity}
        events = [
            EventPlan(
                event_name="garrison.deployed",
                source_tool="place_fighters",
                mutation=apply_place,
                payload_factory=lambda: {
                    "sector": {"id": sector},
                    "garrison": self._garrison_payload(sector),
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_collect_fighters(self, args: dict[str, Any]) -> ToolExecution:
        try:
            sector = int(args.get("sector"))
            quantity = int(args.get("quantity"))
        except Exception:
            return self._error("collect_fighters", "sector and quantity must be integers")
        if quantity <= 0:
            return self._error("collect_fighters", "quantity must be positive")

        available = self.garrisons.get(sector, 0)
        if available < quantity:
            return self._error(
                "collect_fighters", f"Insufficient garrison fighters. Have {available}, need {quantity}"
            )

        def apply_collect() -> None:
            self.garrisons[sector] = max(0, self.garrisons.get(sector, 0) - quantity)
            self.state.fighters += quantity

        payload = {"status": "success", "sector": sector, "quantity": quantity}
        events = [
            EventPlan(
                event_name="garrison.collected",
                source_tool="collect_fighters",
                mutation=apply_collect,
                payload_factory=lambda: {
                    "sector": {"id": sector},
                    "garrison": self._garrison_payload(sector),
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_event_query(self, args: dict[str, Any]) -> ToolExecution:
        start = args.get("start")
        end = args.get("end")
        if start is None or end is None:
            return self._error("event_query", "Missing required arguments: start, end")
        start_dt = _parse_iso8601_timestamp(start)
        end_dt = _parse_iso8601_timestamp(end)
        if start_dt is None or end_dt is None:
            return self._error("event_query", "start and end must be valid ISO8601 timestamps")
        if end_dt < start_dt:
            return self._error("event_query", "end must be greater than or equal to start")

        filter_event_type = args.get("filter_event_type")
        filter_sector = args.get("filter_sector")
        filter_task_id = args.get("filter_task_id")
        try:
            cursor = int(args.get("cursor") or 0)
        except Exception:
            cursor = 0
        page_size_value = args.get("max_rows")
        if page_size_value is None:
            page_size_value = args.get("limit")
        if page_size_value is None:
            page_size_value = args.get("page_size")
        try:
            page_size = int(page_size_value) if page_size_value is not None else 100
        except Exception:
            page_size = 100
        page_size = max(1, min(100, page_size))

        filtered = []
        for event_record in self.event_history:
            event_timestamp = _parse_iso8601_timestamp(event_record.get("timestamp"))
            if event_timestamp is None:
                continue
            if event_timestamp < start_dt or event_timestamp >= end_dt:
                continue
            filtered.append(event_record)
        if isinstance(filter_event_type, str) and filter_event_type.strip():
            token = filter_event_type.strip().lower()
            filtered = [e for e in filtered if str(e.get("event_name", "")).lower() == token]

        if filter_sector is not None:
            try:
                sector_value = int(filter_sector)
                filtered = [e for e in filtered if int(e.get("sector", -1)) == sector_value]
            except Exception:
                pass
        if isinstance(filter_task_id, str) and filter_task_id.strip():
            token = filter_task_id.strip()
            filtered = [
                e for e in filtered if str(e.get("task_id", "")).startswith(token)
            ]

        slice_start = max(0, cursor)
        slice_end = slice_start + page_size
        raw_page = filtered[slice_start:slice_end]
        page: list[dict[str, Any]] = []
        for event_record in raw_page:
            payload = event_record.get("event_payload")
            if payload is None:
                payload = event_record.get("response_data")
            if not isinstance(payload, dict):
                payload = {}
            page.append(
                {
                    "event": event_record.get("event_name", "unknown"),
                    "timestamp": event_record.get("timestamp"),
                    "payload": payload,
                    "task_id": event_record.get("task_id"),
                }
            )
        has_more = slice_end < len(filtered)
        next_cursor = slice_end if has_more else None

        payload = {
            "start": start,
            "end": end,
            "count": len(page),
            "events": page,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "filters": {
                "filter_event_type": filter_event_type,
                "filter_sector": filter_sector,
                "filter_task_id": filter_task_id,
            },
        }
        events = [
            EventPlan(
                event_name="event.query",
                source_tool="event_query",
                payload=payload,
            )
        ]
        return ToolExecution(payload={"status": "success", "count": len(page)}, events=events, ok=True)

    def _handle_purchase_fighters(self, args: dict[str, Any]) -> ToolExecution:
        try:
            units = int(args.get("units"))
        except Exception:
            return self._error("purchase_fighters", "units must be an integer")
        if units <= 0:
            return self._error("purchase_fighters", "units must be positive")

        port = self.ports.get(self.state.sector)
        if not port or not port.name.startswith("MEGA"):
            return self._error(
                "purchase_fighters",
                f"Armory is only available at a mega-port. You are in sector {self.state.sector}",
            )

        cost = units * 50
        if self.state.credits < cost:
            return self._error(
                "purchase_fighters", f"Insufficient credits. Have {self.state.credits}, need {cost}"
            )

        def apply_purchase() -> None:
            self.state.credits -= cost
            self.state.fighters += units

        payload = {"status": "success", "units": units, "cost": cost}
        events = [
            EventPlan(
                event_name="fighter.purchase",
                source_tool="purchase_fighters",
                mutation=apply_purchase,
                payload_factory=lambda: {
                    "units": units,
                    "total_cost": cost,
                    "fighters_after": self.state.fighters,
                    "ship_credits_after": self.state.credits,
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_create_corporation(self, args: dict[str, Any]) -> ToolExecution:
        name = str(args.get("name", "")).strip()
        if not name:
            return self._error("create_corporation", "Missing required argument: name")
        if self.state.corporation_name:
            return self._error("create_corporation", "Already in a corporation")

        def apply_create() -> None:
            self.state.corporation_name = name
            self.corp_members = ["Jane Eyre"]

        payload = {"status": "success", "name": name}
        events = [
            EventPlan(
                event_name="corporation.created",
                source_tool="create_corporation",
                mutation=apply_create,
                payload_factory=lambda: {
                    "corp_id": self.corporation_id,
                    "name": self.state.corporation_name,
                    "members": list(self.corp_members),
                    "member_count": len(self.corp_members),
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_join_corporation(self, args: dict[str, Any]) -> ToolExecution:
        invite_code = str(args.get("invite_code", "")).strip()
        if not invite_code:
            return self._error("join_corporation", "Missing required argument: invite_code")

        def apply_join() -> None:
            if not self.state.corporation_name:
                self.state.corporation_name = f"Corp-{invite_code[-4:] or '0000'}"
            if "Jane Eyre" not in self.corp_members:
                self.corp_members.append("Jane Eyre")

        payload = {"status": "success", "invite_code": invite_code}
        events = [
            EventPlan(
                event_name="corporation.member_joined",
                source_tool="join_corporation",
                mutation=apply_join,
                payload_factory=lambda: {
                    "corp_id": self.corporation_id,
                    "name": self.state.corporation_name,
                    "member_name": self.player_name,
                    "members": list(self.corp_members),
                    "member_count": len(self.corp_members),
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_leave_corporation(self, _args: dict[str, Any]) -> ToolExecution:
        if not self.state.corporation_name:
            return self._error("leave_corporation", "Not in a corporation")

        corp_name = self.state.corporation_name

        def apply_leave() -> None:
            self.state.corporation_name = None
            self.corp_members = [m for m in self.corp_members if m != "Jane Eyre"]

        payload = {"status": "success", "name": corp_name}
        events = [
            EventPlan(
                event_name="corporation.member_left",
                source_tool="leave_corporation",
                mutation=apply_leave,
                payload={
                    "corp_id": self.corporation_id,
                    "name": corp_name,
                    "member_name": self.player_name,
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_kick_corporation_member(self, args: dict[str, Any]) -> ToolExecution:
        target_id = str(args.get("target_id", "")).strip()
        if not target_id:
            return self._error("kick_corporation_member", "Missing required argument: target_id")
        if not self.state.corporation_name:
            return self._error("kick_corporation_member", "Not in a corporation")

        payload = {"status": "success", "target_id": target_id}
        events = [
            EventPlan(
                event_name="corporation.member_kicked",
                source_tool="kick_corporation_member",
                payload={
                    "corp_id": self.corporation_id,
                    "name": self.state.corporation_name,
                    "target_id": target_id,
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_corporation_info(self, _args: dict[str, Any]) -> ToolExecution:
        payload = {
            "status": "success",
            "corp_id": self.corporation_id if self.state.corporation_name else None,
            "name": self.state.corporation_name,
            "members": list(self.corp_members),
            "member_count": len(self.corp_members),
        }
        return ToolExecution(payload=payload, events=[], ok=True)

    def _handle_purchase_ship(self, args: dict[str, Any]) -> ToolExecution:
        ship_type = str(args.get("ship_type", "")).strip().lower()
        if not ship_type:
            return self._error("purchase_ship", "Missing required argument: ship_type")

        price_map = {"courier": 0, "probe": 12000, "frigate": 40000, "hauler": 25000}
        price = price_map.get(ship_type, 18000)
        if self.state.credits < price:
            return self._error("purchase_ship", f"Insufficient credits. Have {self.state.credits}, need {price}")

        def apply_purchase() -> None:
            self.state.credits -= price
            self.state.ship_type = ship_type
            self.state.ship_name = f"{ship_type.title()}-{str(uuid.uuid4())[:8]}"
            self.state.ship_id = str(uuid.uuid4())

        payload = {"status": "success", "ship_type": ship_type, "price": price}
        events = [
            EventPlan(
                event_name="status.update",
                source_tool="purchase_ship",
                mutation=apply_purchase,
                payload_factory=lambda: self._status_payload(),
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_rename_ship(self, args: dict[str, Any]) -> ToolExecution:
        ship_name = str(args.get("ship_name", "")).strip()
        if not ship_name:
            return self._error("rename_ship", "Missing required argument: ship_name")
        previous_name = self.state.ship_name

        def apply_rename() -> None:
            self.state.ship_name = ship_name

        payload = {"status": "success", "ship_name": ship_name}
        events = [
            EventPlan(
                event_name="ship.renamed",
                source_tool="rename_ship",
                mutation=apply_rename,
                payload_factory=lambda: {
                    "ship_name": self.state.ship_name,
                    "previous_ship_name": previous_name,
                    "ship_id": self.state.ship_id,
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_bank_deposit(self, args: dict[str, Any]) -> ToolExecution:
        try:
            amount = int(args.get("amount"))
        except Exception:
            return self._error("bank_deposit", "amount must be an integer")
        if amount <= 0:
            return self._error("bank_deposit", "amount must be positive")
        if self.state.credits < amount:
            return self._error(
                "bank_deposit", f"Insufficient credits. Have {self.state.credits}, need {amount}"
            )

        def apply_deposit() -> None:
            self.state.credits -= amount
            self.state.bank_credits += amount

        payload = {
            "status": "success",
            "amount": amount,
            "target_player_name": args.get("target_player_name"),
        }
        events = [
            EventPlan(
                event_name="bank.transaction",
                source_tool="bank_deposit",
                mutation=apply_deposit,
                payload_factory=lambda: {
                    "direction": "deposit",
                    "amount": amount,
                    "credits_in_bank_after": self.state.bank_credits,
                    "ship_credits_after": self.state.credits,
                    "ship_name": self.state.ship_name,
                    "ship_id": self.state.ship_id,
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_bank_withdraw(self, args: dict[str, Any]) -> ToolExecution:
        try:
            amount = int(args.get("amount"))
        except Exception:
            return self._error("bank_withdraw", "amount must be an integer")
        if amount <= 0:
            return self._error("bank_withdraw", "amount must be positive")
        if self.state.bank_credits < amount:
            return self._error(
                "bank_withdraw", f"Insufficient bank credits. Have {self.state.bank_credits}, need {amount}"
            )

        def apply_withdraw() -> None:
            self.state.bank_credits -= amount
            self.state.credits += amount

        payload = {"status": "success", "amount": amount}
        events = [
            EventPlan(
                event_name="bank.transaction",
                source_tool="bank_withdraw",
                mutation=apply_withdraw,
                payload_factory=lambda: {
                    "direction": "withdraw",
                    "amount": amount,
                    "credits_in_bank_after": self.state.bank_credits,
                    "ship_credits_after": self.state.credits,
                    "ship_name": self.state.ship_name,
                    "ship_id": self.state.ship_id,
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_transfer_credits(self, args: dict[str, Any]) -> ToolExecution:
        try:
            amount = int(args.get("amount"))
        except Exception:
            return self._error("transfer_credits", "amount must be an integer")
        if amount <= 0:
            return self._error("transfer_credits", "amount must be positive")
        if self.state.credits < amount:
            return self._error(
                "transfer_credits", f"Insufficient credits. Have {self.state.credits}, need {amount}"
            )

        def apply_transfer() -> None:
            self.state.credits -= amount

        payload = {
            "status": "success",
            "amount": amount,
            "to_ship_name": args.get("to_ship_name"),
            "to_ship_id": args.get("to_ship_id"),
        }
        events = [
            EventPlan(
                event_name="credits.transfer",
                source_tool="transfer_credits",
                mutation=apply_transfer,
                payload={
                    "transfer_direction": "sent",
                    "transfer_details": {"credits": amount},
                    "from": {"name": self.player_name},
                    "to": {
                        "name": str(
                            args.get("to_ship_name")
                            or args.get("to_ship_id")
                            or args.get("to_player_name")
                            or "unknown"
                        )
                    },
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_dump_cargo(self, args: dict[str, Any]) -> ToolExecution:
        items = args.get("items")
        if not isinstance(items, list) or not items:
            return self._error("dump_cargo", "items must be a non-empty list")

        dumped: dict[str, int] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            commodity = _canonical_commodity(str(item.get("commodity", "")))
            try:
                units = int(item.get("units", 0))
            except Exception:
                units = 0
            if commodity not in self.state.cargo or units <= 0:
                continue
            amount = min(units, self.state.cargo[commodity])
            if amount <= 0:
                continue
            dumped[commodity] = dumped.get(commodity, 0) + amount

        if not dumped:
            return self._error("dump_cargo", "No cargo was dumped")

        salvage_id = str(uuid.uuid4())

        def apply_dump() -> None:
            for commodity, amount in dumped.items():
                self.state.cargo[commodity] -= amount
            self.salvage_by_id[salvage_id] = Salvage(
                salvage_id=salvage_id,
                sector=self.state.sector,
                cargo=dict(dumped),
            )

        payload = {"status": "success", "salvage_id": salvage_id, "cargo": dumped}
        events = [
            EventPlan(
                event_name="salvage.created",
                source_tool="dump_cargo",
                mutation=apply_dump,
                payload_factory=lambda: {
                    "salvage_id": salvage_id,
                    "salvage_details": {
                        "credits": 0,
                        "scrap": 0,
                        "cargo": dict(dumped),
                    },
                },
            ),
            EventPlan(
                event_name="status.update",
                source_tool="dump_cargo",
                delay_s=0.03,
                payload_factory=lambda: self._status_payload(),
            ),
            EventPlan(
                event_name="sector.update",
                source_tool="dump_cargo",
                delay_s=0.04,
                payload_factory=lambda: self._sector_payload(self.state.sector),
            ),
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_combat_initiate(self, _args: dict[str, Any]) -> ToolExecution:
        if self.state.combat_id:
            return self._error("combat_initiate", "Combat already active")

        combat_id = str(uuid.uuid4())

        def apply_initiate() -> None:
            self.state.combat_id = combat_id

        payload = {"status": "success", "combat_id": combat_id}
        events = [
            EventPlan(
                event_name="combat.round_waiting",
                source_tool="combat_initiate",
                mutation=apply_initiate,
                payload_factory=lambda: {
                    "combat_id": self.state.combat_id,
                    "sector": {"id": self.state.sector},
                    "round": 1,
                    "deadline": _iso_utc_now(),
                    "participants": [
                        {"id": "player-jane-eyre", "name": self.player_name},
                    ],
                },
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_combat_action(self, args: dict[str, Any]) -> ToolExecution:
        combat_id = str(args.get("combat_id", "")).strip()
        action = str(args.get("action", "")).strip().upper()
        if not combat_id or not action:
            return self._error("combat_action", "Missing required arguments: combat_id, action")
        if self.state.combat_id != combat_id:
            return self._error("combat_action", f"Unknown combat_id: {combat_id}")
        if action not in {"ATTACK", "BRACE", "FLEE", "PAY"}:
            return self._error("combat_action", f"Unsupported combat action: {action}")

        def apply_action() -> None:
            if action in {"FLEE", "PAY"}:
                self.state.combat_id = None

        payload = {"status": "success", "combat_id": combat_id, "action": action}
        events = [
            EventPlan(
                event_name="combat.action_accepted",
                source_tool="combat_action",
                mutation=apply_action,
                payload={
                    "combat_id": combat_id,
                    "round": 1,
                    "action": action.lower(),
                    "round_resolved": action in {"FLEE", "PAY"},
                },
            )
        ]
        if action in {"FLEE", "PAY"}:
            events.append(
                EventPlan(
                    event_name="combat.ended",
                    source_tool="combat_action",
                    delay_s=0.03,
                    payload={
                        "combat_id": combat_id,
                        "round": 1,
                        "sector": {"id": self.state.sector},
                        "result": action.lower(),
                    },
                )
            )
        return ToolExecution(payload=payload, events=events, ok=True)

    def _handle_load_game_info(self, args: dict[str, Any]) -> ToolExecution:
        topic = str(args.get("topic", "")).strip()
        if not topic:
            return self._error("load_game_info", "Missing required argument: topic")
        if topic not in AVAILABLE_INFO_TOPICS:
            return self._error(
                "load_game_info",
                f"Unknown topic: {topic}. Available topics: {', '.join(AVAILABLE_INFO_TOPICS)}",
            )
        try:
            content = _load_game_info_fragment(topic)
        except FileNotFoundError as exc:
            return self._error("load_game_info", str(exc))
        payload = {"topic": topic, "content": content}
        return ToolExecution(payload=payload, events=[], ok=True)

    def _handle_wait_in_idle_state(self, args: dict[str, Any]) -> ToolExecution:
        seconds_raw = args.get("seconds", 60)
        try:
            seconds = int(seconds_raw)
        except Exception:
            return self._error("wait_in_idle_state", "seconds must be an integer between 1 and 60")
        if seconds < 1 or seconds > 60:
            return self._error("wait_in_idle_state", "seconds must be between 1 and 60")

        payload = {"status": "idle_complete", "elapsed_seconds": float(seconds)}
        events = [
            EventPlan(
                event_name="idle.complete",
                source_tool="wait_in_idle_state",
                delay_s=min(seconds, 1),
                summary=f"Idle wait complete after {seconds} seconds.",
                payload={"elapsed_seconds": float(seconds), "timestamp": _iso_utc_now()},
            )
        ]
        return ToolExecution(payload=payload, events=events, ok=True)


def serialize_response_data(data: Any) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)


def classify_result_status(result: Any) -> str:
    if isinstance(result, dict):
        if result.get("error_class") == "post_finished_call":
            return "post_finished_call_rejected"
        if result.get("error") is not None:
            return "error"
        status = str(result.get("status", "")).strip().lower()
        if status in {"executed.", "executed", "ack", "acknowledged"}:
            return "acknowledged"
        if status in {"success", "completed", "idle_complete", "event_received", "ok"}:
            return "success"
    return "success"
