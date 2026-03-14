from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import evaluate_runs
from synthetic_world import COMMODITIES, SyntheticWorld


REPLAY_BUNDLE_SCHEMA_VERSION = "mini_rl_replay_bundle.v1"
REPLAY_STREAM_SCHEMA_VERSION = "mini_rl_replay_stream.v1"
PORT_TO_PORT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PORT_TO_PORT_DIR.parent
DEFAULT_RUNS_DIR = PORT_TO_PORT_DIR / "runs"
FINAL_SCORE_FIELDS = [
    "primary_score_100",
    "mission_completion_score",
    "trade_quality_score",
    "path_efficiency_score",
    "tool_discipline_score",
    "report_quality_score",
    "strict_success",
    "objective_success",
    "task_complete",
    "report_accuracy",
    "report_accuracy_method",
    "report_judge_reason",
    "total_profit_credits",
    "terminal_reason",
    "finished_called",
]
LIVE_STEP_TYPES = {"session_start", "inference_input", "turn", "summary", "output_written", "run_interrupted"}
RUN_INDEX_SUFFIX_RE = re.compile(r"^(?P<base>.+)-run\d+$")


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _state_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None
    return None


def _to_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _cargo_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    delta: dict[str, int] = {}
    before_cargo = _state_dict(before.get("cargo"))
    after_cargo = _state_dict(after.get("cargo"))
    for commodity in COMMODITIES:
        before_value = _to_int(before_cargo.get(commodity)) or 0
        after_value = _to_int(after_cargo.get(commodity)) or 0
        delta[commodity] = after_value - before_value
    return delta


def _state_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "sector_from": _to_int(before.get("sector")),
        "sector_to": _to_int(after.get("sector")),
        "credits": (_to_int(after.get("credits")) or 0) - (_to_int(before.get("credits")) or 0),
        "warp": (_to_int(after.get("warp")) or 0) - (_to_int(before.get("warp")) or 0),
        "empty_holds": (_to_int(after.get("empty_holds")) or 0) - (_to_int(before.get("empty_holds")) or 0),
        "used_holds": (_to_int(after.get("used_holds")) or 0) - (_to_int(before.get("used_holds")) or 0),
        "cargo": _cargo_delta(before, after),
    }


def _coerce_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    cargo = _state_dict(snapshot.get("cargo"))
    empty_holds = _to_int(snapshot.get("empty_holds"))
    used_holds = _to_int(snapshot.get("used_holds"))
    holds_total = None
    if empty_holds is not None and used_holds is not None:
        holds_total = empty_holds + used_holds
    return {
        "sector": _to_int(snapshot.get("sector")),
        "warp": _to_int(snapshot.get("warp")),
        "max_warp": _to_int(snapshot.get("max_warp")),
        "credits": _to_int(snapshot.get("credits")),
        "bank_credits": _to_int(snapshot.get("bank_credits")),
        "cargo": {
            commodity: _to_int(cargo.get(commodity)) or 0
            for commodity in COMMODITIES
        },
        "empty_holds": empty_holds,
        "used_holds": used_holds,
        "holds_total": holds_total,
        "visited_sector_count": _to_int(snapshot.get("visited_sector_count")),
        "ship_name": snapshot.get("ship_name"),
        "ship_type": snapshot.get("ship_type"),
        "ship_id": snapshot.get("ship_id"),
        "corporation_name": snapshot.get("corporation_name"),
        "fighters": _to_int(snapshot.get("fighters")),
        "combat_id": snapshot.get("combat_id"),
    }


def _state_signature(snapshot: dict[str, Any]) -> tuple[Any, ...]:
    normalized = _coerce_snapshot(snapshot)
    cargo = normalized["cargo"]
    return (
        normalized.get("sector"),
        normalized.get("warp"),
        normalized.get("max_warp"),
        normalized.get("credits"),
        normalized.get("bank_credits"),
        cargo.get("quantum_foam"),
        cargo.get("retro_organics"),
        cargo.get("neuro_symbolics"),
        normalized.get("empty_holds"),
        normalized.get("used_holds"),
        normalized.get("ship_name"),
        normalized.get("ship_type"),
        normalized.get("corporation_name"),
        normalized.get("fighters"),
        normalized.get("combat_id"),
    )


def _apply_state_snapshot(world: SyntheticWorld, snapshot: dict[str, Any]) -> None:
    normalized = _coerce_snapshot(snapshot)
    state = world.state
    if normalized["sector"] is not None:
        state.sector = normalized["sector"]
    if normalized["warp"] is not None:
        state.warp = normalized["warp"]
    if normalized["max_warp"] is not None:
        state.max_warp = normalized["max_warp"]
    if normalized["credits"] is not None:
        state.credits = normalized["credits"]
    if normalized["bank_credits"] is not None:
        state.bank_credits = normalized["bank_credits"]
    if normalized["holds_total"] is not None and normalized["holds_total"] > 0:
        state.holds_total = normalized["holds_total"]
    state.cargo = dict(normalized["cargo"])
    if normalized["ship_name"]:
        state.ship_name = str(normalized["ship_name"])
    if normalized["ship_type"]:
        state.ship_type = str(normalized["ship_type"])
    if normalized["ship_id"]:
        state.ship_id = str(normalized["ship_id"])
    state.corporation_name = (
        str(normalized["corporation_name"]) if normalized["corporation_name"] is not None else None
    )
    if normalized["fighters"] is not None:
        state.fighters = normalized["fighters"]
    state.combat_id = (
        str(normalized["combat_id"]) if normalized["combat_id"] is not None else None
    )
    sector = normalized["sector"]
    if sector is not None:
        state.visited_sectors.add(sector)


def resolve_artifact_path(path_text: str, *, default_dir: Optional[Path] = None) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    if default_dir is not None:
        return (default_dir / candidate).resolve()
    return (REPO_ROOT / candidate).resolve()


def discover_judge_path(run_path: Path) -> Optional[Path]:
    run_path = run_path.resolve()
    seen: set[Path] = set()

    def _candidate_jsonl_paths(stem: str) -> list[Path]:
        candidates: list[Path] = []
        direct = (run_path.parent / f"eval-{stem}" / "enriched_runs.jsonl").resolve()
        if direct not in seen:
            candidates.append(direct)
            seen.add(direct)

        sibling_dirs = sorted(
            (path for path in run_path.parent.glob(f"eval-{stem}*") if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for directory in sibling_dirs:
            candidate = (directory / "enriched_runs.jsonl").resolve()
            if candidate not in seen:
                candidates.append(candidate)
                seen.add(candidate)
        return candidates

    candidate_paths = _candidate_jsonl_paths(run_path.stem)
    stem_match = RUN_INDEX_SUFFIX_RE.match(run_path.stem)
    if stem_match is not None:
        candidate_paths.extend(_candidate_jsonl_paths(stem_match.group("base")))

    for candidate in candidate_paths:
        if candidate.exists():
            return candidate

    try:
        payload = _load_json(run_path)
    except Exception:
        return None

    fallback_candidates = sorted(
        (
            path.resolve()
            for path in run_path.parent.glob("eval-*/enriched_runs.jsonl")
            if path.exists()
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in fallback_candidates:
        if candidate in seen:
            continue
        try:
            rows = _load_jsonl_rows(candidate)
        except Exception:
            continue
        if _match_judge_row(run_path=run_path, payload=payload, rows=rows) is not None:
            return candidate
    return None


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _match_judge_row(
    *,
    run_path: Path,
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    if not rows:
        return None

    metadata = _state_dict(payload.get("metadata"))
    run_id = str(metadata.get("run_id") or "").strip()
    resolved_run = str(run_path.resolve())

    if run_id:
        for row in rows:
            if str(row.get("run_id") or "").strip() == run_id:
                return row

    for row in rows:
        row_file = str(row.get("file") or "").strip()
        if row_file and str(Path(row_file).expanduser().resolve()) == resolved_run:
            return row

    if len(rows) == 1:
        return rows[0]
    return None


def load_completed_run(
    run_path: Path,
    *,
    judge_path: Optional[Path] = None,
) -> tuple[dict[str, Any], Optional[dict[str, Any]], Optional[Path]]:
    payload = _load_json(run_path)
    resolved_judge = judge_path.resolve() if judge_path is not None else discover_judge_path(run_path)
    if resolved_judge is None or not resolved_judge.exists():
        return payload, None, None
    rows = _load_jsonl_rows(resolved_judge)
    return payload, _match_judge_row(run_path=run_path, payload=payload, rows=rows), resolved_judge


def _score_snapshot(metrics: dict[str, Any], *, exact_final: bool) -> dict[str, Any]:
    snapshot = {field: metrics.get(field) for field in FINAL_SCORE_FIELDS}
    snapshot["exact_final"] = exact_final
    return snapshot


def _override_with_final_judge(
    *,
    metrics: dict[str, Any],
    judge_row: Optional[dict[str, Any]],
) -> dict[str, Any]:
    if judge_row is None:
        return metrics
    merged = dict(metrics)
    for field in FINAL_SCORE_FIELDS:
        if field in judge_row:
            merged[field] = judge_row.get(field)
    return merged


def _step_type_for_tool(name: Optional[str], result_status: str) -> str:
    if name == "move":
        return "move"
    if name == "trade":
        return "trade"
    if name == "recharge_warp_power":
        return "recharge"
    if name == "plot_course":
        return "plot_course"
    if name == "finished":
        return "finished"
    if result_status in {"error", "post_finished_call_rejected"}:
        return "error"
    return "info"


def _extract_step_details(
    *,
    tool_name: Optional[str],
    args: dict[str, Any],
    execution_payload: dict[str, Any],
    event_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "course_path": None,
        "trade": None,
        "recharge": None,
        "finished_message": None,
    }

    if tool_name == "plot_course":
        path = execution_payload.get("path")
        if isinstance(path, list) and all(_to_int(item) is not None for item in path):
            details["course_path"] = [_to_int(item) for item in path]

    if tool_name == "trade":
        trade_payload = None
        for payload in event_payloads:
            candidate = _state_dict(payload.get("trade"))
            if candidate:
                trade_payload = candidate
                break
        details["trade"] = {
            "commodity": str(args.get("commodity") or ""),
            "quantity": _to_int(args.get("quantity")),
            "trade_type": str(args.get("trade_type") or ""),
            "price_per_unit": _to_int((trade_payload or {}).get("price_per_unit")),
            "total_price": _to_int((trade_payload or {}).get("total_price")),
        }

    if tool_name == "recharge_warp_power":
        details["recharge"] = {
            "units": _to_int(execution_payload.get("units")),
            "cost": _to_int(execution_payload.get("cost")),
        }

    if tool_name == "finished":
        details["finished_message"] = str(args.get("message") or "")

    return details


def _simulate_tool_call(
    *,
    world: SyntheticWorld,
    call: dict[str, Any],
) -> tuple[list[str], dict[str, Any], list[dict[str, Any]], list[str]]:
    tool_name = str(call.get("name") or "")
    args = _state_dict(call.get("args"))
    result_status = str(call.get("result_status") or "unknown")
    warnings: list[str] = []

    if tool_name == "finished":
        return [], {"status": "completed", "message": str(args.get("message") or "")}, [], warnings

    if result_status not in {"acknowledged", "success"}:
        return [], {}, [], warnings

    execution = world.execute_tool(tool_name, dict(args))
    if not execution.ok:
        warnings.append(
            f"Simulator could not replay {tool_name} even though artifact marked it {result_status}."
        )
        return [], _state_dict(execution.payload), [], warnings

    event_names: list[str] = []
    event_payloads: list[dict[str, Any]] = []
    for event_plan in execution.events:
        if event_plan.mutation is not None:
            event_plan.mutation()
        if event_plan.payload_factory is not None:
            payload = event_plan.payload_factory()
        else:
            payload = event_plan.payload
        event_names.append(event_plan.event_name)
        event_payloads.append(_state_dict(payload))
    return event_names, _state_dict(execution.payload), event_payloads, warnings


def _build_partial_turn(
    *,
    source_turn: dict[str, Any],
    partial_tool_calls: list[dict[str, Any]],
    state_after: dict[str, Any],
    bad_actions_after: int,
    error_event: Optional[dict[str, Any]],
) -> dict[str, Any]:
    state_before = _state_dict(source_turn.get("state_before"))
    bad_before = _to_int(source_turn.get("bad_actions_before")) or 0
    partial_turn: dict[str, Any] = {
        "llm_turn": _to_int(source_turn.get("llm_turn")),
        "decision_ms": _to_float(source_turn.get("decision_ms")),
        "tool_calls": _json_copy(partial_tool_calls),
        "raw_response_text": source_turn.get("raw_response_text") or "",
        "failure_class": str(source_turn.get("failure_class") or "none"),
        "bad_actions_before": bad_before,
        "bad_actions_after": bad_actions_after,
        "bad_action_increment": bad_actions_after - bad_before,
        "state_before": _json_copy(state_before),
        "state_after": _json_copy(state_after),
        "inference_index": _to_int(source_turn.get("inference_index")),
    }
    if "raw_thought_text" in source_turn:
        partial_turn["raw_thought_text"] = source_turn.get("raw_thought_text")
    if "usage" in source_turn:
        partial_turn["usage"] = _json_copy(source_turn.get("usage"))
    if "ttfb" in source_turn:
        partial_turn["ttfb"] = _json_copy(source_turn.get("ttfb"))
    if "ttfb_ms" in source_turn:
        partial_turn["ttfb_ms"] = source_turn.get("ttfb_ms")
    if error_event:
        partial_turn["error_event"] = _json_copy(error_event)
    return partial_turn


def _build_replay_timeline(
    *,
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    metadata = _state_dict(payload.get("metadata"))
    initial_state = _state_dict(metadata.get("initial_state"))
    raw_turns = _list_of_dicts(payload.get("turns"))

    world = SyntheticWorld()
    if initial_state:
        _apply_state_snapshot(world, initial_state)

    steps: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []
    warnings: list[str] = []

    for turn_index, source_turn in enumerate(raw_turns):
        state_before_turn = _state_dict(source_turn.get("state_before"))
        if state_before_turn and _state_signature(world.state_snapshot()) != _state_signature(state_before_turn):
            warnings.append(
                f"Turn {turn_index + 1} state_before did not match simulator state; using artifact snapshot."
            )
            _apply_state_snapshot(world, state_before_turn)

        step_start_index = len(steps)
        tool_calls = _list_of_dicts(source_turn.get("tool_calls"))
        bad_before = _to_int(source_turn.get("bad_actions_before")) or 0
        bad_after_turn = _to_int(source_turn.get("bad_actions_after"))
        turn_bad_budget = (
            max(0, bad_after_turn - bad_before)
            if bad_after_turn is not None
            else max(0, _to_int(source_turn.get("bad_action_increment")) or 0)
        )
        bad_count_so_far = 0

        if not tool_calls:
            state_after_turn = _state_dict(source_turn.get("state_after"))
            failure_bad_after = bad_before + turn_bad_budget
            steps.append(
                {
                    "step_index": len(steps),
                    "turn_index": turn_index,
                    "turn_number": _to_int(source_turn.get("llm_turn")) or (turn_index + 1),
                    "inference_index": _to_int(source_turn.get("inference_index")),
                    "tool_call_index": None,
                    "partial_tool_call_count": 0,
                    "step_type": "turn_failure",
                    "tool_name": None,
                    "result_status": None,
                    "args": {},
                    "state_before": _json_copy(state_before_turn),
                    "state_after": _json_copy(state_after_turn),
                    "delta": _state_delta(state_before_turn, state_after_turn),
                    "event_names": [],
                    "details": {},
                    "failure_class": str(source_turn.get("failure_class") or "none"),
                    "bad_actions_before": bad_before,
                    "bad_actions_after": failure_bad_after,
                }
            )
            _apply_state_snapshot(world, state_after_turn)
        else:
            for tool_call_index, call in enumerate(tool_calls):
                state_before_call = world.state_snapshot()
                bad_actions_before = bad_before + bad_count_so_far
                event_names, execution_payload, event_payloads, sim_warnings = _simulate_tool_call(
                    world=world,
                    call=call,
                )
                warnings.extend(
                    f"Turn {turn_index + 1} call {tool_call_index + 1}: {warning}"
                    for warning in sim_warnings
                )

                result_status = str(call.get("result_status") or "unknown")
                if result_status in {"error", "post_finished_call_rejected"} and bad_count_so_far < turn_bad_budget:
                    bad_count_so_far += 1
                bad_actions_after = bad_before + bad_count_so_far
                state_after_call = world.state_snapshot()
                details = _extract_step_details(
                    tool_name=str(call.get("name") or "") or None,
                    args=_state_dict(call.get("args")),
                    execution_payload=execution_payload,
                    event_payloads=event_payloads,
                )
                steps.append(
                    {
                        "step_index": len(steps),
                        "turn_index": turn_index,
                        "turn_number": _to_int(source_turn.get("llm_turn")) or (turn_index + 1),
                        "inference_index": _to_int(source_turn.get("inference_index")),
                        "tool_call_index": tool_call_index,
                        "partial_tool_call_count": tool_call_index + 1,
                        "step_type": _step_type_for_tool(str(call.get("name") or "") or None, result_status),
                        "tool_name": str(call.get("name") or "") or None,
                        "result_status": result_status,
                        "args": _json_copy(_state_dict(call.get("args"))),
                        "state_before": _json_copy(state_before_call),
                        "state_after": _json_copy(state_after_call),
                        "delta": _state_delta(state_before_call, state_after_call),
                        "event_names": event_names,
                        "details": details,
                        "failure_class": str(source_turn.get("failure_class") or "none"),
                        "bad_actions_before": bad_actions_before,
                        "bad_actions_after": bad_actions_after,
                    }
                )

        step_end_index = len(steps) - 1
        if step_end_index >= step_start_index and bad_after_turn is not None:
            steps[step_end_index]["bad_actions_after"] = bad_after_turn

        state_after_turn = _state_dict(source_turn.get("state_after"))
        if state_after_turn and _state_signature(world.state_snapshot()) != _state_signature(state_after_turn):
            warnings.append(
                f"Turn {turn_index + 1} state_after did not match simulator state; using artifact snapshot."
            )
            _apply_state_snapshot(world, state_after_turn)

        turns.append(
            {
                "turn_index": turn_index,
                "turn_number": _to_int(source_turn.get("llm_turn")) or (turn_index + 1),
                "inference_index": _to_int(source_turn.get("inference_index")),
                "decision_ms": _to_float(source_turn.get("decision_ms")),
                "failure_class": str(source_turn.get("failure_class") or "none"),
                "raw_response_text": source_turn.get("raw_response_text") or "",
                "raw_thought_text": source_turn.get("raw_thought_text"),
                "usage": _json_copy(source_turn.get("usage")),
                "ttfb": _json_copy(source_turn.get("ttfb")),
                "ttfb_ms": _to_float(source_turn.get("ttfb_ms")),
                "state_before": _json_copy(state_before_turn),
                "state_after": _json_copy(state_after_turn),
                "bad_actions_before": bad_before,
                "bad_actions_after": bad_after_turn,
                "bad_action_increment": _to_int(source_turn.get("bad_action_increment")),
                "error_event": _json_copy(source_turn.get("error_event")),
                "step_start_index": step_start_index,
                "step_end_index": step_end_index,
                "tool_call_count": len(tool_calls),
            }
        )

    return turns, steps, warnings


def _build_partial_metrics(
    *,
    run_path: Path,
    payload: dict[str, Any],
    source_turns: list[dict[str, Any]],
    replay_turns: list[dict[str, Any]],
    replay_steps: list[dict[str, Any]],
    judge_row: Optional[dict[str, Any]],
) -> None:
    prefix_turns: list[dict[str, Any]] = []
    previous_score: Optional[dict[str, Any]] = None

    for turn_index, source_turn in enumerate(source_turns):
        turn_meta = replay_turns[turn_index]
        step_start_index = _to_int(turn_meta.get("step_start_index")) or 0
        step_end_index = _to_int(turn_meta.get("step_end_index")) or -1

        for step_index in range(step_start_index, step_end_index + 1):
            step = replay_steps[step_index]
            partial_tool_count = _to_int(step.get("partial_tool_call_count")) or 0
            partial_tool_calls = _list_of_dicts(source_turn.get("tool_calls"))[:partial_tool_count]
            error_event = (
                _state_dict(source_turn.get("error_event"))
                if step_index == step_end_index or str(step.get("result_status") or "") == "error"
                else None
            )

            partial_turn = _build_partial_turn(
                source_turn=source_turn,
                partial_tool_calls=partial_tool_calls,
                state_after=_state_dict(step.get("state_after")),
                bad_actions_after=_to_int(step.get("bad_actions_after")) or 0,
                error_event=error_event,
            )

            finished_message = ""
            if partial_tool_calls:
                for call in partial_tool_calls:
                    if str(call.get("name") or "") == "finished":
                        finished_message = str(_state_dict(call.get("args")).get("message") or "")

            partial_payload = {
                "schema_version": payload.get("schema_version"),
                "metadata": _json_copy(_state_dict(payload.get("metadata"))),
                "config": _json_copy(_state_dict(payload.get("config"))),
                "summary": {},
                "termination": {
                    "reason": "finished_tool" if finished_message else "",
                    "finished_called": bool(finished_message),
                    "finished_message": finished_message,
                },
                "turns": prefix_turns + [partial_turn],
            }

            metrics = evaluate_runs._derive_run_metrics(run_path, partial_payload, report_judge=None)
            is_final_step = step_index == len(replay_steps) - 1
            score_metrics = _override_with_final_judge(metrics=metrics, judge_row=judge_row if is_final_step else None)
            score = _score_snapshot(score_metrics, exact_final=is_final_step and judge_row is not None)
            if previous_score is None:
                delta = {
                    field: score.get(field)
                    for field in [
                        "primary_score_100",
                        "mission_completion_score",
                        "trade_quality_score",
                        "path_efficiency_score",
                        "tool_discipline_score",
                        "report_quality_score",
                    ]
                }
            else:
                delta = {}
                for field in [
                    "primary_score_100",
                    "mission_completion_score",
                    "trade_quality_score",
                    "path_efficiency_score",
                    "tool_discipline_score",
                    "report_quality_score",
                ]:
                    current_value = _to_int(score.get(field))
                    previous_value = _to_int(previous_score.get(field))
                    delta[field] = (
                        current_value - previous_value
                        if current_value is not None and previous_value is not None
                        else None
                    )
            replay_steps[step_index]["score"] = score
            replay_steps[step_index]["score_delta"] = delta
            previous_score = score

        prefix_turns.append(_json_copy(source_turn))


def build_replay_bundle_from_payload(
    *,
    run_path: Path,
    payload: dict[str, Any],
    judge_row: Optional[dict[str, Any]] = None,
    judge_path: Optional[Path] = None,
    live: bool = False,
    stream_path: Optional[Path] = None,
) -> dict[str, Any]:
    metadata = _state_dict(payload.get("metadata"))
    config = _state_dict(payload.get("config"))
    summary = _state_dict(payload.get("summary"))
    termination = _state_dict(payload.get("termination"))
    source_turns = _list_of_dicts(payload.get("turns"))
    inference_inputs = _list_of_dicts(payload.get("inference_inputs"))

    replay_turns, replay_steps, warnings = _build_replay_timeline(payload=payload)
    _build_partial_metrics(
        run_path=run_path,
        payload=payload,
        source_turns=source_turns,
        replay_turns=replay_turns,
        replay_steps=replay_steps,
        judge_row=judge_row,
    )

    final_metrics = (
        _override_with_final_judge(
            metrics=evaluate_runs._derive_run_metrics(run_path, payload, report_judge=None),
            judge_row=judge_row,
        )
        if source_turns
        else {}
    )
    if not inference_inputs:
        warnings.append("This run does not include inference_inputs; context replay is unavailable.")

    return {
        "schema_version": REPLAY_BUNDLE_SCHEMA_VERSION,
        "loaded_at_utc": _iso_utc_now(),
        "live": live,
        "source": {
            "run_path": str(run_path.resolve()),
            "judge_path": str(judge_path.resolve()) if judge_path is not None else None,
            "stream_path": str(stream_path.resolve()) if stream_path is not None else None,
        },
        "run": {
            "metadata": _json_copy(metadata),
            "config": _json_copy(config),
            "summary": _json_copy(summary),
            "termination": _json_copy(termination),
        },
        "judge": _json_copy(judge_row),
        "final_score": _score_snapshot(final_metrics, exact_final=judge_row is not None) if final_metrics else None,
        "turns": replay_turns,
        "steps": replay_steps,
        "inference_inputs": _json_copy(inference_inputs),
        "warnings": warnings,
    }


def build_replay_bundle_for_completed_run(
    run_path: Path,
    *,
    judge_path: Optional[Path] = None,
) -> dict[str, Any]:
    payload, judge_row, resolved_judge = load_completed_run(run_path, judge_path=judge_path)
    return build_replay_bundle_from_payload(
        run_path=run_path,
        payload=payload,
        judge_row=judge_row,
        judge_path=resolved_judge,
    )


def build_payload_from_replay_stream(stream_path: Path) -> dict[str, Any]:
    session: dict[str, Any] = {}
    turns: list[dict[str, Any]] = []
    inference_inputs: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    termination: dict[str, Any] = {}

    for raw_line in stream_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "")
        if event_type not in LIVE_STEP_TYPES:
            continue
        if event_type == "session_start":
            session = event
        elif event_type == "inference_input":
            entry = _state_dict(event.get("inference_input"))
            if entry:
                inference_inputs.append(entry)
        elif event_type == "turn":
            turn = _state_dict(event.get("turn"))
            if turn:
                turns.append(turn)
        elif event_type in {"summary", "run_interrupted"}:
            summary = _state_dict(event.get("summary"))
            termination = _state_dict(event.get("termination"))

    payload = {
        "schema_version": session.get("run_schema_version"),
        "metadata": _state_dict(session.get("metadata")),
        "config": _state_dict(session.get("config")),
        "summary": summary,
        "termination": termination,
        "turns": turns,
    }
    if inference_inputs:
        payload["inference_inputs"] = inference_inputs
    return payload


def build_replay_bundle_for_stream(stream_path: Path) -> dict[str, Any]:
    payload = build_payload_from_replay_stream(stream_path)
    metadata = _state_dict(payload.get("metadata"))
    run_path_text = str(metadata.get("run_file") or stream_path)
    run_path = resolve_artifact_path(run_path_text, default_dir=stream_path.parent)
    return build_replay_bundle_from_payload(
        run_path=run_path,
        payload=payload,
        judge_row=None,
        judge_path=None,
        live=True,
        stream_path=stream_path,
    )


def list_available_runs(*, runs_dir: Path = DEFAULT_RUNS_DIR, limit: int = 40) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for run_path in sorted(runs_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        payload = _load_json(run_path)
        config = _state_dict(payload.get("config"))
        metadata = _state_dict(payload.get("metadata"))
        judge_path = discover_judge_path(run_path)
        judge_row = None
        if judge_path is not None:
            try:
                rows = _load_jsonl_rows(judge_path)
                judge_row = _match_judge_row(
                    run_path=run_path,
                    payload=payload,
                    rows=rows,
                )
            except Exception:
                judge_row = None
        stat = run_path.stat()
        items.append(
            {
                "name": run_path.name,
                "run_path": str(run_path.resolve()),
                "judge_path": str(judge_path.resolve()) if judge_path is not None else None,
                "size_bytes": stat.st_size,
                "started_at_utc": metadata.get("started_at_utc"),
                "ended_at_utc": metadata.get("ended_at_utc"),
                "modified_at_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "primary_score_100": judge_row.get("primary_score_100") if isinstance(judge_row, dict) else None,
                "model": (
                    judge_row.get("model") if isinstance(judge_row, dict) else None
                ) or config.get("model"),
                "strict_success": judge_row.get("strict_success") if isinstance(judge_row, dict) else None,
            }
        )
        if len(items) >= limit:
            break
    return items
