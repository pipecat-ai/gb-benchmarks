from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
import json

import pytest


MODULE_PATH = Path(__file__).parents[1] / "diagnostics" / "gpt56_responses_probe.py"
FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "proj-2026-07-16-1632"
    / "step1-gpt56-event-fixtures.json"
)
SPEC = importlib.util.spec_from_file_location("gpt56_responses_probe", MODULE_PATH)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


def test_planned_matrix_is_exactly_sixteen_calls() -> None:
    calls = probe.planned_calls()
    assert len(calls) == 16
    assert sum(call.api == "responses" for call in calls) == 14
    assert sum(call.api == "chat" for call in calls) == 2
    assert {(call.model, call.effort) for call in calls if call.api == "chat"} == {
        ("gpt-5.6-luna", "low"),
        ("gpt-5.5", "medium"),
    }


def test_worst_case_reservations_equal_hard_plan() -> None:
    worst = probe.planned_worst_case()
    assert worst == {
        "planned_requests": 16,
        "retry_requests_reserved": 8,
        "requests_total": 24,
        "tokens": 999_424,
        "usd": 14.819328,
        "wall_secs": 14_400.0,
    }
    assert worst["requests_total"] <= probe.MAX_REQUESTS
    assert worst["tokens"] <= probe.MAX_ACCOUNTED_TOKENS
    assert worst["usd"] <= probe.MAX_ACCOUNTED_USD
    assert worst["wall_secs"] <= probe.MAX_WALL_SECS


def test_budget_preflight_rejects_unreserved_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe.time, "monotonic", lambda: 0.0)
    ledger = probe.BudgetLedger()
    reservation = probe.reservation_for("gpt-5.6-sol", probe.ESCALATED_MAX_OUTPUT_TOKENS)
    ledger.requests = probe.MAX_REQUESTS
    with pytest.raises(probe.BudgetExceeded, match="request ceiling"):
        ledger.preflight(reservation, retry=False)


def test_unknown_timeout_charges_full_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe.time, "monotonic", lambda: 0.0)
    ledger = probe.BudgetLedger()
    reservation = probe.reservation_for("gpt-5.6-sol", probe.INITIAL_MAX_OUTPUT_TOKENS)
    ledger.preflight(reservation, retry=False)
    ledger.account(reservation, None, unknown_may_be_billable=True)
    assert ledger.accounted_tokens == reservation.tokens
    assert ledger.accounted_usd == reservation.usd


def test_request_shape_has_no_prompt_or_service_tier() -> None:
    request = probe.build_responses_request(
        model="gpt-5.6-sol",
        effort="max",
        input_items=probe.FIRST_INPUT,
        tool_choice={"type": "function", "name": "lookup_probe"},
        max_output_tokens=16_384,
    )
    shape = probe.sanitized_request_shape(
        request,
        api="responses",
        turn=1,
        input_token_reservation=probe.INPUT_TOKEN_RESERVATION,
    )
    assert shape["reasoning"] == {"effort": "max"}
    assert shape["store"] is False
    assert shape["service_tier_present"] is False
    assert "reasoning_effort" not in shape
    assert "content" not in repr(shape)

    request["service_tier"] = "priority"
    with pytest.raises(probe.ProbeError, match="omit service_tier"):
        probe.sanitized_request_shape(
            request,
            api="responses",
            turn=1,
            input_token_reservation=probe.INPUT_TOKEN_RESERVATION,
        )


def test_pinned_sdk_accepts_every_live_request_keyword() -> None:
    client = probe.OpenAI(api_key="test-only-no-network", max_retries=0)
    responses_request = probe.build_responses_request(
        model="gpt-5.6-luna",
        effort="low",
        input_items=probe.FIRST_INPUT,
        tool_choice={"type": "function", "name": "lookup_probe"},
        max_output_tokens=probe.INITIAL_MAX_OUTPUT_TOKENS,
    )
    chat_request = probe.build_chat_request(model="gpt-5.5", effort="medium")
    responses_parameters = inspect.signature(client.responses.stream).parameters
    chat_parameters = inspect.signature(client.chat.completions.create).parameters
    assert set(responses_request) <= set(responses_parameters)
    assert set(chat_request) <= set(chat_parameters)
    assert "allow_missing_reasoning_rejection" in inspect.signature(
        probe.ProbeRunner.responses_attempt
    ).parameters


def test_turn_two_reserves_previous_output_cap() -> None:
    calls = probe.planned_calls()
    turn_two = next(call for call in calls if call.api == "responses" and call.turn == 2)
    reservation = probe.reservation_for(
        turn_two.model,
        probe.INITIAL_MAX_OUTPUT_TOKENS,
        probe.INPUT_TOKEN_RESERVATION + probe.INITIAL_MAX_OUTPUT_TOKENS,
    )
    assert reservation.tokens == 36_864


def test_parsed_function_call_field_is_not_replayed() -> None:
    from openai.types.responses.parsed_response import ParsedResponseFunctionToolCall

    item = ParsedResponseFunctionToolCall(
        arguments='{"code":"gpt56-contract-v1"}',
        call_id="call_1",
        name="lookup_probe",
        type="function_call",
        parsed_arguments={"code": "gpt56-contract-v1"},
    )
    replay = probe.to_plain(item)
    assert replay["arguments"] == item.arguments
    assert "parsed_arguments" not in replay


def recovery_source(model: str, effort: str, attempt: int, *, reasoning: bool) -> dict:
    events = []
    if reasoning:
        events.append(
            {"type": "response.output_item.done", "item": {"type": "reasoning", "id": f"rs_{attempt}"}}
        )
    events.append(
        {
            "type": "response.output_item.done",
            "item": {
                "type": "function_call",
                "id": f"fc_{attempt}",
                "status": "completed",
                "call_id": f"call_{attempt}",
                "name": "lookup_probe",
                "arguments": '{"code":"gpt56-contract-v1"}',
            },
        }
    )
    return {
        "attempt_number": attempt,
        "classification": "response_completed",
        "request": {
            "api": "responses",
            "model": model,
            "reasoning": {"effort": effort},
            "turn": 1,
            "max_output_tokens": probe.INITIAL_MAX_OUTPUT_TOKENS,
        },
        "events": events,
    }


def test_recovery_orders_reasoning_free_first_chat_last_and_skips_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = probe.ProbeRunner(client=object())
    identities = [
        ("gpt-5.6-luna", "low", False),
        ("gpt-5.6-luna", "max", True),
        ("gpt-5.6-sol", "low", False),
        ("gpt-5.6-sol", "max", False),
        ("gpt-5.6-terra", "low", True),
        ("gpt-5.6-terra", "max", True),
        ("gpt-5.5", "medium", False),
    ]
    runner.records = [
        recovery_source(model, effort, index, reasoning=reasoning)
        for index, (model, effort, reasoning) in enumerate(identities, start=1)
    ]
    # Mark luna-low as already recovered to exercise re-entry selection.
    runner.records.append(
        {
            "attempt_number": 8,
            "recovery": {"source_attempt_number": 1},
            "round_trip_result": "success_sanitized_replay",
        }
    )
    runner.ledger.requests = 8
    seen: list[tuple[str, str] | tuple[str, str, str]] = []
    monkeypatch.setattr(
        runner,
        "resume_round_trip",
        lambda record: seen.append(
            (record["request"]["model"], record["request"]["reasoning"]["effort"])
        ),
    )
    monkeypatch.setattr(
        runner,
        "run_chat_check",
        lambda model, effort: seen.append(("chat", model, effort)),
    )
    runner.resume_after_contract_fix()
    assert seen == [
        ("gpt-5.6-sol", "low"),
        ("gpt-5.6-sol", "max"),
        ("gpt-5.5", "medium"),
        ("gpt-5.6-luna", "max"),
        ("gpt-5.6-terra", "low"),
        ("gpt-5.6-terra", "max"),
        ("chat", "gpt-5.5", "medium"),
    ]


def test_checkpoint_function_call_recovers_exact_sanitized_item() -> None:
    record = {
        "events": [
            {"type": "response.output_item.done", "item": {"type": "reasoning", "id": "rs_1"}},
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "id": "fc_1",
                    "status": "completed",
                    "call_id": "call_1",
                    "name": "lookup_probe",
                    "arguments": '{"code":"gpt56-contract-v1"}',
                },
            },
        ]
    }
    call, omitted = probe.ProbeRunner._checkpoint_function_call(record)
    assert call["call_id"] == "call_1"
    assert omitted == 1


def test_checkpoint_restore_rejects_ledger_record_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checkpoint = tmp_path / "probe.json"
    checkpoint.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "limits": probe.limits_payload(),
                "planned_worst_case": probe.planned_worst_case(),
                "ledger": {
                    "requests": 2,
                    "retry_requests": 0,
                    "accounted_tokens": 0,
                    "accounted_usd": 0,
                    "elapsed_wall_secs": 0,
                },
                "records": [{"attempt_number": 1}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(probe, "OUTPUT_JSON", checkpoint)
    with pytest.raises(probe.ProbeError, match="ledger does not match"):
        probe.ProbeRunner.from_checkpoint(object())


def test_expected_missing_reasoning_400_does_not_prime_systemic_halt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openai import BadRequestError
    import httpx

    runner = probe.ProbeRunner(client=object())
    monkeypatch.setattr(runner, "checkpoint", lambda: None)
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(400, request=request)
    error = BadRequestError(
        "function_call was provided without its required reasoning item",
        response=response,
        body={"param": "input", "code": "invalid_request"},
    )
    result, record = runner._attempt(
        api="responses",
        model="gpt-5.6-terra",
        effort="max",
        turn=2,
        max_output_tokens=100,
        input_token_reservation=100,
        retry=False,
        operation=lambda: (_ for _ in ()).throw(error),
        request_shape={"api": "responses"},
        allow_missing_reasoning_rejection=True,
    )
    assert result is None
    assert record["systemic_halt_exempt"] == "sanitized_checkpoint_omitted_reasoning"
    assert runner.consecutive_systemic_errors == 0


def test_public_exception_extracts_nested_provider_signature() -> None:
    from openai import BadRequestError
    import httpx

    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(400, request=request)
    error = BadRequestError(
        "unknown parameter",
        response=response,
        body={
            "error": {
                "message": "unknown parameter",
                "param": "input[1].parsed_arguments",
                "code": "unknown_parameter",
            }
        },
    )
    public = probe.public_exception(error)
    assert public["provider_code"] == "unknown_parameter"
    assert public["provider_param"] == "input[1].parsed_arguments"


def test_total_request_deadline_is_a_wall_clamp() -> None:
    import time

    with pytest.raises(probe.RequestWallTimeout):
        with probe.total_request_deadline(0.01):
            time.sleep(0.05)


def test_operator_interrupt_is_checkpointed_and_reraised(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = probe.ProbeRunner(client=object())
    monkeypatch.setattr(runner, "checkpoint", lambda: None)
    with pytest.raises(KeyboardInterrupt):
        runner._attempt(
            api="responses",
            model="gpt-5.6-luna",
            effort="low",
            turn=1,
            max_output_tokens=100,
            input_token_reservation=100,
            retry=False,
            operation=lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
            request_shape={"api": "responses"},
        )
    assert runner.records[-1]["classification"] == "operator_interrupt"
    assert runner.stop_reason == "operator_interrupt"


def test_budget_block_is_checkpointed_without_counting_a_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = probe.ProbeRunner(client=object())
    monkeypatch.setattr(runner, "checkpoint", lambda: None)
    before = runner.ledger.requests
    record = runner.budget_blocked_record(
        api="responses",
        model="gpt-5.6-sol",
        effort="max",
        turn=2,
        max_output_tokens=probe.ESCALATED_MAX_OUTPUT_TOKENS,
        input_token_reservation=probe.INPUT_TOKEN_RESERVATION
        + probe.ESCALATED_MAX_OUTPUT_TOKENS,
        retry=True,
        error=probe.BudgetExceeded("retry ceiling"),
    )
    assert record["classification"] == "budget_blocked"
    assert runner.ledger.requests == before


def test_two_identical_systemic_errors_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = probe.ProbeRunner(client=object())
    monkeypatch.setattr(runner, "checkpoint", lambda: None)

    def fail() -> tuple[object, str | None, list[dict[str, object]]]:
        raise TypeError("pinned SDK rejected a request keyword")

    kwargs = {
        "api": "responses",
        "model": "gpt-5.6-luna",
        "effort": "low",
        "turn": 1,
        "max_output_tokens": 100,
        "input_token_reservation": 100,
        "retry": False,
        "operation": fail,
        "request_shape": {"api": "responses"},
    }
    response, record = runner._attempt(**kwargs)
    assert response is None
    assert record["classification"] == "unexpected_client_error"
    with pytest.raises(probe.SystemicProbeStop):
        runner._attempt(**kwargs)
    assert runner.stop_reason.startswith("repeated_systemic_error")


def test_transient_response_failed_is_retry_eligible() -> None:
    assert probe.transient_failed_response({"error": {"code": "server_error"}})
    assert not probe.transient_failed_response({"error": {"code": "invalid_request"}})


def test_cap_retry_accepts_both_documented_and_pinned_sdk_spellings() -> None:
    for reason in ("max_tokens", "max_output_tokens"):
        record = {
            "response": {"status": "incomplete", "incomplete_reason": reason},
        }
        assert probe.ProbeRunner._needs_cap_retry(
            record, probe.INITIAL_MAX_OUTPUT_TOKENS
        )
    assert not probe.ProbeRunner._needs_cap_retry(
        {"response": {"status": "incomplete", "incomplete_reason": "content_filter"}},
        probe.INITIAL_MAX_OUTPUT_TOKENS,
    )


def test_partial_stream_evidence_survives_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = probe.ProbeRunner(client=object())
    monkeypatch.setattr(runner, "checkpoint", lambda: None)
    partial = probe.PartialStreamError(
        TypeError("stream decoder failed"),
        [{"type": "response.output_item.added", "sequence_number": 1}],
        "req_partial_1",
    )
    response, record = runner._attempt(
        api="responses",
        model="gpt-5.6-luna",
        effort="low",
        turn=1,
        max_output_tokens=100,
        input_token_reservation=100,
        retry=False,
        operation=lambda: (_ for _ in ()).throw(partial),
        request_shape={"api": "responses"},
    )
    assert response is None
    assert record["request_id"] == "req_partial_1"
    assert record["events"] == partial.events
    assert record["error"]["type"] == "TypeError"


def test_transient_failed_response_uses_exactly_one_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = probe.ProbeRunner(client=object())
    calls: list[bool] = []

    def fake_attempt(**kwargs):
        calls.append(kwargs["retry"])
        if len(calls) == 1:
            return {"status": "failed"}, {
                "response": {"status": "failed", "error": {"code": "server_error"}},
                "transient_retry_eligible": True,
            }
        return {"status": "completed"}, {
            "response": {"status": "completed"},
        }

    monkeypatch.setattr(runner, "responses_attempt", fake_attempt)
    monkeypatch.setattr(probe.time, "sleep", lambda _seconds: None)
    response, record = runner.responses_with_retry(
        model="gpt-5.6-luna",
        effort="low",
        turn=1,
        input_items=probe.FIRST_INPUT,
        tool_choice={"type": "function", "name": "lookup_probe"},
        input_token_reservation=probe.INPUT_TOKEN_RESERVATION,
    )
    assert response == {"status": "completed"}
    assert record["response"]["status"] == "completed"
    assert calls == [False, True]


def test_sanitize_event_never_persists_reasoning_or_output_text() -> None:
    event = {
        "type": "response.completed",
        "sequence_number": 7,
        "response": {
            "id": "resp_1",
            "model": "gpt-5.6-sol",
            "status": "completed",
            "output": [
                {"type": "reasoning", "encrypted_content": "secret-ciphertext"},
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "fixed answer"}],
                },
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "output_tokens_details": {"reasoning_tokens": 12},
            },
        },
    }
    sanitized = probe.sanitize_event(event)
    rendered = repr(sanitized)
    assert "secret-ciphertext" not in rendered
    assert "fixed answer" not in rendered
    assert sanitized["response"]["output_types"] == ["reasoning", "message"]


def test_step1_captured_and_synthetic_event_fixtures_validate() -> None:
    from openai.types.responses import ResponseFailedEvent, ResponseIncompleteEvent

    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    captured = fixtures["captured_success"]
    events = captured["events"]
    actual_types = {event["type"] for event in events}
    assert set(captured["expected_event_types"]) <= actual_types
    done = next(
        event
        for event in events
        if event["type"] == "response.function_call_arguments.done"
    )
    assert done["arguments"] == captured["function_call_arguments"]
    completed = next(event for event in events if event["type"] == "response.completed")
    assert completed["response"]["status"] == captured["terminal_status"]

    synthetic = fixtures["synthetic_sdk_schema_events"]
    incomplete = ResponseIncompleteEvent.model_validate(synthetic["incomplete"])
    failed = ResponseFailedEvent.model_validate(synthetic["failed"])
    assert probe.sanitize_event(incomplete)["response"]["incomplete_reason"] == (
        "max_output_tokens"
    )
    assert probe.sanitize_event(failed)["response"]["error"]["code"] == "server_error"


def test_exact_tool_call_validation() -> None:
    good = {
        "output": [
            {
                "type": "function_call",
                "name": "lookup_probe",
                "call_id": "call_1",
                "arguments": '{"code":"gpt56-contract-v1"}',
            }
        ]
    }
    call, error = probe.response_function_call(good)
    assert error is None
    assert call is not None

    bad = {"output": [{**good["output"][0], "arguments": '{"code":"wrong"}'}]}
    call, error = probe.response_function_call(bad)
    assert call is None
    assert "unexpected function arguments" in error


def test_live_mode_requires_exact_acknowledgement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe, "installed_sdk_version", lambda: probe.EXPECTED_OPENAI_SDK)
    with pytest.raises(probe.ProbeError, match="exact approval token"):
        probe.main(["--execute", "--approval-token", "wrong"])
