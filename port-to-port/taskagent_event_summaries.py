"""TaskAgent-compatible event summary registry for the mini RL harness."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from taskagent_summary_formatters import (
    bank_transaction_summary,
    character_moved_summary,
    chat_message_summary,
    combat_action_accepted_summary,
    combat_ended_summary,
    combat_round_resolved_summary,
    combat_round_waiting_summary,
    corporation_ship_purchased_summary,
    event_query_summary,
    garrison_character_moved_summary,
    garrison_combat_alert_summary,
    join_summary,
    list_known_ports_summary,
    map_local_summary,
    move_summary,
    movement_start_summary,
    plot_course_summary,
    port_update_summary,
    salvage_collected_summary,
    salvage_created_summary,
    sector_update_summary,
    ship_renamed_summary,
    ships_list_summary,
    status_update_summary,
    task_cancel_summary,
    task_finish_summary,
    task_start_summary,
    trade_executed_summary,
    transfer_summary,
    warp_purchase_summary,
)


class TaskAgentEventSummaries:
    """Stateful formatter registry matching AsyncGameClient defaults."""

    def __init__(self) -> None:
        self._current_sector: Optional[int] = None
        self._corporation_id: Optional[str] = None
        self._summary_formatters = self._build_default_summaries()

    def _build_default_summaries(self) -> dict[str, Callable[[dict[str, Any]], str]]:
        def map_local_wrapper(data: dict[str, Any]) -> str:
            current = self._current_sector
            if current is None and isinstance(data, Mapping):
                current_candidate = data.get("center_sector")
                if isinstance(current_candidate, int):
                    current = current_candidate
            return map_local_summary(data, current)

        def event_query_wrapper(data: dict[str, Any]) -> str:
            def nested_summary(event_name: str, payload: dict[str, Any]) -> Optional[str]:
                if event_name == "event.query":
                    count = payload.get("count", 0)
                    has_more = payload.get("has_more", False)
                    more_str = " (more available)" if has_more else ""
                    return f"nested query returned {count} events{more_str}"
                return self.get_summary(event_name, payload)

            return event_query_summary(data, nested_summary)

        def character_moved_wrapper(data: dict[str, Any]) -> str:
            return character_moved_summary(data, self._corporation_id)

        def garrison_character_moved_wrapper(data: dict[str, Any]) -> str:
            return garrison_character_moved_summary(data, self._corporation_id)

        return {
            "status.snapshot": join_summary,
            "status.update": status_update_summary,
            "movement.complete": move_summary,
            "movement.start": movement_start_summary,
            "course.plot": plot_course_summary,
            "ports.list": list_known_ports_summary,
            "map.local": map_local_wrapper,
            "map.region": map_local_wrapper,
            "map.update": map_local_wrapper,
            "trade.executed": trade_executed_summary,
            "credits.transfer": transfer_summary,
            "warp.transfer": transfer_summary,
            "warp.purchase": warp_purchase_summary,
            "bank.transaction": bank_transaction_summary,
            "chat.message": chat_message_summary,
            "port.update": port_update_summary,
            "ships.list": ships_list_summary,
            "character.moved": character_moved_wrapper,
            "ship.renamed": ship_renamed_summary,
            "corporation.ship_purchased": corporation_ship_purchased_summary,
            "combat.round_waiting": combat_round_waiting_summary,
            "combat.action_accepted": combat_action_accepted_summary,
            "combat.round_resolved": combat_round_resolved_summary,
            "combat.ended": combat_ended_summary,
            "salvage.created": salvage_created_summary,
            "salvage.collected": salvage_collected_summary,
            "garrison.combat_alert": garrison_combat_alert_summary,
            "garrison.character_moved": garrison_character_moved_wrapper,
            "sector.update": sector_update_summary,
            "task.start": task_start_summary,
            "task.cancel": task_cancel_summary,
            "task.finish": task_finish_summary,
            "event.query": event_query_wrapper,
        }

    def _set_current_sector(self, candidate: Any) -> None:
        if candidate is None or isinstance(candidate, bool):
            return
        try:
            value = int(candidate)
        except (TypeError, ValueError):
            return
        self._current_sector = value

    def _maybe_update_current_sector(self, event_name: str, payload: Mapping[str, Any]) -> None:
        sector_id: Optional[Any] = None

        if event_name in {"movement.complete", "status.snapshot", "status.update"}:
            sector = payload.get("sector")
            if isinstance(sector, Mapping):
                sector_id = sector.get("id")

        if sector_id is None and "current_sector" in payload:
            sector_id = payload.get("current_sector")

        if sector_id is None and event_name in {"map.local", "local_map_region", "map.region"}:
            sector_id = payload.get("center_sector")

        if sector_id is not None:
            self._set_current_sector(sector_id)

    def _maybe_update_corporation_id(self, event_name: str, payload: Mapping[str, Any]) -> None:
        if event_name not in {"status.snapshot", "status.update"}:
            return
        corporation = payload.get("corporation")
        if not isinstance(corporation, Mapping):
            return
        corp_id = corporation.get("corp_id")
        if isinstance(corp_id, str):
            self._corporation_id = corp_id
        elif corp_id is None:
            self._corporation_id = None

    def get_summary(self, event_name: str, payload: dict[str, Any]) -> Optional[str]:
        formatter = self._summary_formatters.get(event_name)
        if formatter is None:
            return None

        try:
            summary = formatter(payload)
        except Exception:
            return None

        if summary is None:
            return None

        if not isinstance(summary, str):
            summary = str(summary)

        summary = summary.strip()
        if not summary:
            return None

        return summary

    def summarize_event(self, event_name: str, payload: Any) -> Optional[str]:
        if isinstance(payload, Mapping):
            self._maybe_update_current_sector(event_name, payload)
            self._maybe_update_corporation_id(event_name, payload)

        if not isinstance(payload, dict):
            return None

        return self.get_summary(event_name, payload)
