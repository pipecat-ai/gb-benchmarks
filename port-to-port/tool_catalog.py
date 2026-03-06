"""TaskAgent-parity tool catalog for mini RL harness."""

from __future__ import annotations

from typing import Any

from pipecat.adapters.schemas.tools_schema import ToolsSchema

from tools_schema import (
    BankDeposit,
    BankWithdraw,
    CollectFighters,
    CombatAction,
    CombatInitiate,
    CorporationInfo,
    CreateCorporation,
    DumpCargo,
    EventQuery,
    JoinCorporation,
    KickCorporationMember,
    LeaveCorporation,
    ListKnownPorts,
    LoadGameInfo,
    LocalMapRegion,
    Move,
    MyStatus,
    PlaceFighters,
    PlotCourse,
    PurchaseFighters,
    PurchaseShip,
    RechargeWarpPower,
    RenameShip,
    SalvageCollect,
    SendMessage,
    TaskFinished,
    Trade,
    TransferCredits,
    TransferWarpPower,
    WaitInIdleState,
)

EXPECTED_TASK_AGENT_DEFAULT_TOOL_NAMES = [
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
]

DEFAULT_TOOL_CLASSES = [
    MyStatus,
    PlotCourse,
    LocalMapRegion,
    ListKnownPorts,
    Move,
    Trade,
    SalvageCollect,
    SendMessage,
    RechargeWarpPower,
    TransferWarpPower,
    PlaceFighters,
    CollectFighters,
    EventQuery,
    PurchaseFighters,
    CreateCorporation,
    JoinCorporation,
    LeaveCorporation,
    KickCorporationMember,
    CorporationInfo,
    PurchaseShip,
    RenameShip,
    BankDeposit,
    BankWithdraw,
    TransferCredits,
    DumpCargo,
    CombatInitiate,
    CombatAction,
    LoadGameInfo,
    WaitInIdleState,
    TaskFinished,
]

BENCHMARK_ASYNC_TOOL_COMPLETIONS = {
    "move": "movement.complete",
    "my_status": "status.snapshot",
    "list_known_ports": "ports.list",
    "trade": "trade.executed",
    "recharge_warp_power": "warp.purchase",
    "transfer_warp_power": "warp.transfer",
    "salvage_collect": "salvage.collected",
    "place_fighters": "garrison.deployed",
    "collect_fighters": "garrison.collected",
    "send_message": "chat.message",
    "event_query": "event.query",
    "purchase_fighters": "fighter.purchase",
    "purchase_ship": "status.update",
    "rename_ship": "ship.renamed",
    "bank_deposit": "bank.transaction",
    "bank_withdraw": "bank.transaction",
    "transfer_credits": "credits.transfer",
    "dump_cargo": "salvage.created",
    "create_corporation": "corporation.created",
    "join_corporation": "corporation.member_joined",
    "leave_corporation": "corporation.member_left",
    "kick_corporation_member": "corporation.member_kicked",
    "combat_initiate": "combat.round_waiting",
    "combat_action": "combat.action_accepted",
    "wait_in_idle_state": "idle.complete",
}

# Events from sync tools that should NOT be added to LLM context.
# TaskAgent keeps these out of context because tool results already contain the
# same payload; events still flow to observers/logging.
BENCHMARK_SYNC_TOOL_EVENTS: dict[str, str] = {
    "local_map_region": "map.region",
    "plot_course": "course.plot",
}


def get_default_tool_names() -> list[str]:
    return [tool_class.schema().name for tool_class in DEFAULT_TOOL_CLASSES]


def build_tools_schema() -> ToolsSchema:
    return ToolsSchema(standard_tools=[tool_class.schema() for tool_class in DEFAULT_TOOL_CLASSES])


def get_required_fields_by_tool() -> dict[str, set[str]]:
    required: dict[str, set[str]] = {}
    for tool_class in DEFAULT_TOOL_CLASSES:
        schema = tool_class.schema()
        required[schema.name] = set(schema.required or [])
    return required


def assert_catalog_parity() -> None:
    current_names = get_default_tool_names()

    if current_names != EXPECTED_TASK_AGENT_DEFAULT_TOOL_NAMES:
        raise RuntimeError(
            "Benchmark default tool-name order drifted. "
            f"expected={EXPECTED_TASK_AGENT_DEFAULT_TOOL_NAMES} actual={current_names}"
        )

    if set(current_names) != set(BENCHMARK_ASYNC_TOOL_COMPLETIONS).union(BENCHMARK_SYNC_TOOL_EVENTS).union(
        {"corporation_info", "load_game_info", "finished", "plot_course", "local_map_region"}
    ):
        # This guard catches obvious map/name mismatches while allowing tools
        # that are neither async-completion nor sync-event-skipped.
        raise RuntimeError("Tool mode maps do not align with benchmark tool catalog.")


def summarize_tool_schema_shapes() -> dict[str, dict[str, Any]]:
    shapes: dict[str, dict[str, Any]] = {}
    for tool_class in DEFAULT_TOOL_CLASSES:
        schema = tool_class.schema()
        properties = schema.properties or {}
        property_names = sorted(properties.keys())
        shapes[schema.name] = {
            "required": sorted(schema.required or []),
            "properties": property_names,
        }
    return shapes
