#!/usr/bin/env bash
# Dedicated, approval-gated GPT-5.6 port-to-port sweep.
# Deliberately does not use `set -e`: an infra failure must remain data and may
# be replaced without suppressing later configurations.
set -uo pipefail

EXPECTED_OPENAI_SDK_VERSION="2.21.0"

cd /home/khkramer/src/gb-benchmarks/port-to-port || exit 1

CONFIGS=(
  $'gpt56-luna-low\tgpt-5.6-luna\tlow\t-\tlow\t50000\t900\t600\t7200\t7500\t55000000\t153.75'
  $'gpt56-luna-xhigh\tgpt-5.6-luna\txhigh\t-\txhigh\t50000\t900\t600\t7200\t7500\t55000000\t153.75'
  $'gpt56-luna-max\tgpt-5.6-luna\txhigh\tmax\tmax\t50000\t900\t600\t7200\t7500\t55000000\t153.75'
  $'gpt56-terra-low\tgpt-5.6-terra\tlow\t-\tlow\t50000\t900\t600\t7200\t7500\t55000000\t384.375'
  $'gpt56-terra-xhigh\tgpt-5.6-terra\txhigh\t-\txhigh\t50000\t900\t600\t7200\t7500\t55000000\t384.375'
  $'gpt56-terra-max\tgpt-5.6-terra\txhigh\tmax\tmax\t50000\t900\t600\t7200\t7500\t55000000\t384.375'
  $'gpt56-sol-low\tgpt-5.6-sol\tlow\t-\tlow\t50000\t1200\t600\t28800\t29100\t55000000\t768.75'
  $'gpt56-sol-xhigh\tgpt-5.6-sol\txhigh\t-\txhigh\t50000\t1200\t600\t28800\t29100\t55000000\t768.75'
  $'gpt56-sol-max\tgpt-5.6-sol\txhigh\tmax\tmax\t50000\t1200\t600\t28800\t29100\t55000000\t768.75'
)

PROJECT_DIR="proj-2026-07-16-1632"
RUNS_DIR="${GPT56_RUNS_DIR:-runs}"
PHASE="${GPT56_PHASE:-full}"

case "$PHASE" in
  full)
    STATE_PATH="${GPT56_STATE_PATH:-$PROJECT_DIR/step4-runner-state.json}"
    MANIFEST_PATH="${GPT56_MANIFEST_PATH:-$PROJECT_DIR/canonical-manifest.json}"
    ;;
  smoke-core)
    STATE_PATH="${GPT56_STATE_PATH:-$PROJECT_DIR/step4-core-smoke-runner-state.json}"
    MANIFEST_PATH="${GPT56_MANIFEST_PATH:-$PROJECT_DIR/core-smoke-manifest.json}"
    ;;
  smoke-sol)
    STATE_PATH="${GPT56_STATE_PATH:-$PROJECT_DIR/step4-sol-smoke-runner-state.json}"
    MANIFEST_PATH="${GPT56_MANIFEST_PATH:-$PROJECT_DIR/sol-smoke-manifest.json}"
    ;;
  smoke-luna-xhigh-v4)
    STATE_PATH="${GPT56_STATE_PATH:-$PROJECT_DIR/step4-luna-xhigh-v4-runner-state.json}"
    MANIFEST_PATH="${GPT56_MANIFEST_PATH:-$PROJECT_DIR/luna-xhigh-v4-manifest.json}"
    ;;
  smoke-core-remainder-v5)
    STATE_PATH="${GPT56_STATE_PATH:-$PROJECT_DIR/step4-core-remainder-v5-runner-state.json}"
    MANIFEST_PATH="${GPT56_MANIFEST_PATH:-$PROJECT_DIR/core-remainder-v5-manifest.json}"
    ;;
  smoke-parallel-replay-v6)
    STATE_PATH="${GPT56_STATE_PATH:-$PROJECT_DIR/step4-parallel-replay-v6-runner-state.json}"
    MANIFEST_PATH="${GPT56_MANIFEST_PATH:-$PROJECT_DIR/parallel-replay-v6-manifest.json}"
    ;;
  production-core-v1)
    STATE_PATH="${GPT56_STATE_PATH:-$PROJECT_DIR/step4-core-production-v1-runner-state.json}"
    MANIFEST_PATH="${GPT56_MANIFEST_PATH:-$PROJECT_DIR/core-production-v1-manifest.json}"
    ;;
  production-core-v2)
    STATE_PATH="${GPT56_STATE_PATH:-$PROJECT_DIR/step4-core-production-v2-runner-state.json}"
    MANIFEST_PATH="${GPT56_MANIFEST_PATH:-$PROJECT_DIR/core-production-v2-manifest.json}"
    ;;
  production-core-v3)
    STATE_PATH="${GPT56_STATE_PATH:-$PROJECT_DIR/step4-core-production-v3-runner-state.json}"
    MANIFEST_PATH="${GPT56_MANIFEST_PATH:-$PROJECT_DIR/core-production-v3-manifest.json}"
    ;;
  *)
    printf 'GPT56_PHASE must be full, smoke-core, smoke-sol, smoke-luna-xhigh-v4, smoke-core-remainder-v5, smoke-parallel-replay-v6, production-core-v1, production-core-v2, or production-core-v3\n' >&2
    exit 2
    ;;
esac

state_tool() {
  .venv/bin/python - "$@" <<'PY'
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected an object")
    return value


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_baseline_ledger(path: Path, expected_sha256: str) -> dict[str, Any]:
    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise SystemExit(
            f"baseline ledger hash mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    ledger = load(path)
    if ledger.get("schema_version") != "gpt56_authorization_ledger.v1":
        raise SystemExit("baseline ledger schema mismatch")
    entries = ledger.get("entries")
    cumulative = ledger.get("cumulative")
    if not isinstance(entries, list) or not entries or not isinstance(cumulative, dict):
        raise SystemExit("baseline ledger requires entries and cumulative objects")

    totals = {
        "accounted_tokens": 0,
        "estimated_usd": 0.0,
        "wall_secs": 0.0,
        "physical_requests": 0,
        "known_returned_tokens": 0,
    }
    entry_ids: set[str] = set()
    repo_root = Path.cwd().resolve()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit("baseline ledger entry must be an object")
        entry_id = entry.get("entry_id")
        if not isinstance(entry_id, str) or not entry_id or entry_id in entry_ids:
            raise SystemExit("baseline ledger entry_id must be unique and non-empty")
        entry_ids.add(entry_id)
        for key in ("accounted_tokens", "physical_requests", "known_returned_tokens"):
            value = entry.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SystemExit(f"baseline ledger {entry_id}.{key} must be a nonnegative integer")
            totals[key] += value
        for key in ("estimated_usd", "wall_secs"):
            value = entry.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise SystemExit(f"baseline ledger {entry_id}.{key} must be nonnegative and finite")
            totals[key] += float(value)
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise SystemExit(f"baseline ledger {entry_id} requires evidence")
        for item in evidence:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise SystemExit(f"baseline ledger {entry_id} has invalid evidence")
            evidence_path = (repo_root / item["path"]).resolve()
            if not evidence_path.is_relative_to(repo_root):
                raise SystemExit(f"baseline ledger evidence escapes repository: {item['path']}")
            if sha256_file(evidence_path) != item.get("sha256"):
                raise SystemExit(f"baseline ledger evidence hash mismatch: {item['path']}")

    for key in ("accounted_tokens", "physical_requests", "known_returned_tokens"):
        if cumulative.get(key) != totals[key]:
            raise SystemExit(f"baseline ledger cumulative mismatch for {key}")
    for key in ("estimated_usd", "wall_secs"):
        value = cumulative.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isclose(
            float(value), totals[key], rel_tol=0.0, abs_tol=1e-9
        ):
            raise SystemExit(f"baseline ledger cumulative mismatch for {key}")
    return ledger


def aggregate_cumulative(state: dict[str, Any]) -> dict[str, Any]:
    phase = state["cumulative"]
    baseline = state.get("baseline_cumulative")
    if not isinstance(baseline, dict):
        return dict(phase)
    return {
        "accounted_tokens": int(baseline["accounted_tokens"]) + int(phase["accounted_tokens"]),
        "estimated_usd": float(baseline["estimated_usd"]) + float(phase["estimated_usd"]),
        "wall_secs": float(baseline["wall_secs"]) + float(phase["wall_secs"]),
    }


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)) and math.isfinite(value):
        return max(0, int(value))
    return 0


def nested_identity(payload: dict[str, Any], key: str) -> Any:
    for section in ("config", "summary", "metadata"):
        value = payload.get(section)
        if isinstance(value, dict) and value.get(key) not in (None, ""):
            return value[key]
    return None


def usage_from(payload: dict[str, Any]) -> tuple[dict[str, int], bool]:
    traces = payload.get("responses_traces")
    if not isinstance(traces, list) or not traces:
        return {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}, False
    result = {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
    all_usage_known = True
    for trace in traces:
        usage = trace.get("usage") if isinstance(trace, dict) else None
        if not isinstance(usage, dict):
            all_usage_known = False
            continue
        required = (
            "input_tokens",
            "cached_tokens",
            "output_tokens",
            "reasoning_tokens",
            "total_tokens",
        )
        invalid_usage = any(
            isinstance(usage.get(key), bool)
            or not isinstance(usage.get(key), int)
            or usage[key] < 0
            for key in required
        ) or (
            usage["cached_tokens"] > usage["input_tokens"]
            or usage["reasoning_tokens"] > usage["output_tokens"]
            or usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]
        )
        if invalid_usage:
            all_usage_known = False
            continue
        for key in result:
            result[key] += as_int(usage.get(key))
    result["cached_tokens"] = min(result["cached_tokens"], result["input_tokens"])
    return result, all_usage_known


def error_signature(
    classification: str,
    terminal_reason: str | None,
    traces: list[Any],
    log_path: Path,
    rc: int,
) -> str:
    if classification == "local_replay_error":
        return hashlib.sha256(
            b"local_replay_error\x1fResponsesReplayError\x1frequest_not_sent"
        ).hexdigest()[:24]
    parts: list[str] = [classification, terminal_reason or "", f"rc={rc}"]
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        parts.extend(
            str(trace.get(key) or "")
            for key in ("response_status", "incomplete_reason")
        )
        error = trace.get("error")
        if isinstance(error, dict):
            parts.extend(str(error.get(key) or "") for key in ("code", "type", "status_code", "param"))
    if not traces and log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="replace")[-8192:]
        candidates = [line for line in text.splitlines() if re.search(r"error|failed|timeout|429|5\d\d", line, re.I)]
        if candidates:
            line = candidates[-1].lower()
            line = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27,}", "<uuid>", line)
            line = re.sub(r"\b\d+(?:\.\d+)?\b", "<n>", line)
            parts.append(line[:500])
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]


def classify(json_path: Path, log_path: Path, rc: int) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    parse_error: str | None = None
    if json_path.is_file():
        try:
            candidate = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(candidate, dict):
                payload = candidate
            else:
                parse_error = "non_object_json"
        except (OSError, json.JSONDecodeError) as exc:
            parse_error = type(exc).__name__

    if payload is None:
        classification = "exit_124_no_json" if rc == 124 else "no_json"
        if parse_error:
            classification = "malformed_json"
        terminal_reason = None
        traces: list[Any] = []
        usage = {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
        usage_known = False
        eligible = False
        halt_immediately = False
    elif payload.get("schema_version") != "mini_rl_run.v3":
        classification = "invalid_schema"
        terminal_reason = None
        traces = []
        usage = {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
        usage_known = False
        eligible = False
        halt_immediately = False
    else:
        termination = payload.get("termination") if isinstance(payload.get("termination"), dict) else {}
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        terminal_reason = str(termination.get("reason") or summary.get("terminal_reason") or "unknown")
        traces = payload.get("responses_traces") if isinstance(payload.get("responses_traces"), list) else []
        turns = payload.get("turns") if isinstance(payload.get("turns"), list) else []
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        max_turns = as_int(config.get("max_turns"))
        usage, usage_known = usage_from(payload)
        local_replay_error = any(
            isinstance(trace, dict)
            and (
                trace.get("response_status") == "replay_error"
                or (
                    isinstance(trace.get("error"), dict)
                    and trace["error"].get("type") == "ResponsesReplayError"
                )
            )
            for trace in traces
        )
        halt_immediately = False
        checkpoint = payload.get("checkpoint") if isinstance(payload.get("checkpoint"), dict) else {}
        if checkpoint.get("partial") is True:
            classification = "partial_checkpoint"
            eligible = False
            # At least one provider request may still be in flight and absent
            # from the checkpoint, so partial trace sums cannot release any
            # part of the conservative attempt reservation.
            usage_known = False
        elif not traces or any(
            not isinstance(trace, dict) or trace.get("api_surface") != "responses"
            for trace in traces
        ):
            classification = "missing_responses_trace"
            eligible = False
        elif max_turns <= 0 or len(traces) != len(turns) or len(traces) > max_turns:
            classification = "inference_count_mismatch"
            eligible = False
        elif any(trace.get("openai_sdk_version") != "2.21.0" for trace in traces):
            classification = "sdk_version_mismatch"
            eligible = False
        elif any(trace.get("sdk_max_retries") != 0 for trace in traces):
            classification = "retry_policy_mismatch"
            eligible = False
        elif local_replay_error:
            classification = "local_replay_error"
            eligible = False
            usage_known = False
            halt_immediately = True
        elif terminal_reason in {"", "unknown"}:
            classification = "missing_terminal_reason"
            eligible = False
        elif terminal_reason in {"rate_limit_exhausted", "inference_error"}:
            classification = terminal_reason
            eligible = False
        else:
            classification = "eligible_model_result"
            eligible = True

    signature = None
    if not eligible:
        signature = error_signature(classification, terminal_reason, traces, log_path, rc)
    return {
        "classification": classification,
        "eligible": eligible,
        "terminal_reason": terminal_reason,
        "response_statuses": [
            trace.get("response_status") for trace in traces if isinstance(trace, dict)
        ],
        "usage": usage,
        "usage_known": usage_known,
        "halt_immediately": halt_immediately,
        "error_signature": signature,
        "parse_error": parse_error,
        "payload": payload,
    }


def price_for(model: str, payload: dict[str, Any]) -> float:
    prices = {
        "gpt-5.6-luna": (1.00, 0.10, 6.00),
        "gpt-5.6-terra": (2.50, 0.25, 15.00),
        "gpt-5.6-sol": (5.00, 0.50, 30.00),
    }
    input_price, cached_price, output_price = prices[model]
    total = 0.0
    traces = payload.get("responses_traces") if isinstance(payload.get("responses_traces"), list) else []
    for trace in traces:
        usage = trace.get("usage") if isinstance(trace, dict) else None
        if not isinstance(usage, dict):
            raise ValueError("price_for requires usage on every trace")
        input_tokens = as_int(usage.get("input_tokens"))
        cached = min(as_int(usage.get("cached_tokens")), input_tokens)
        output_tokens = as_int(usage.get("output_tokens"))
        uncached = input_tokens - cached
        long_input_multiplier = 2.0 if input_tokens > 272_000 else 1.0
        long_output_multiplier = 1.5 if input_tokens > 272_000 else 1.0
        # Conservatively treat all uncached input as a possible cache write
        # (1.25x) because Responses usage does not expose cache-write tokens.
        total += (
            uncached * input_price * 1.25 * long_input_multiplier
            + cached * cached_price * long_input_multiplier
            + output_tokens * output_price * long_output_multiplier
        ) / 1_000_000
    return total


def write_manifest(state: dict[str, Any], manifest_path: Path) -> None:
    canonical = []
    for key, attempt_number in sorted(state["canonical"].items()):
        attempt = next(item for item in state["attempts"] if item["attempt_number"] == attempt_number)
        canonical.append(
            {
                "identity": key,
                "config_slug": attempt["config_slug"],
                "model": attempt["model"],
                "effective_effort": attempt["effective_effort"],
                "round_id": attempt["round_id"],
                "attempt_number": attempt_number,
                "raw_json": attempt["raw_json"],
                "raw_log": attempt["raw_log"],
                "derivative_json": None,
                "response_statuses": attempt["response_statuses"],
                "terminal_reason": attempt["terminal_reason"],
                "usage": attempt["usage"],
                "estimated_usd": attempt["estimated_usd"],
                "json_sha256": attempt["json_sha256"],
                "log_sha256": attempt["log_sha256"],
                "selection_reason": attempt["selection_reason"],
            }
        )
    manifest = {
        "schema_version": "gpt56_sweep_manifest.v1",
        "updated_at_utc": utc_now(),
        "phase": state["phase"],
        "approval": state["approval"],
        "cumulative": state["cumulative"],
        "attempts": state["attempts"],
        "canonical": canonical,
    }
    if "baseline_ledger" in state:
        manifest["baseline_ledger"] = state["baseline_ledger"]
        manifest["baseline_cumulative"] = state["baseline_cumulative"]
        manifest["aggregate_cumulative"] = aggregate_cumulative(state)
    atomic_json(
        manifest_path,
        manifest,
    )


def budget_fits(cumulative: dict[str, Any], approval: dict[str, Any], reserve_tokens: int, reserve_usd: float, reserve_wall: float) -> tuple[bool, str]:
    checks = (
        (cumulative["accounted_tokens"] + reserve_tokens, approval["token_ceiling"], "token"),
        (cumulative["estimated_usd"] + reserve_usd, approval["usd_ceiling"], "USD"),
        (cumulative["wall_secs"] + reserve_wall, approval["wall_secs_ceiling"], "wall"),
    )
    for projected, ceiling, label in checks:
        if projected >= ceiling:
            return False, f"{label} reservation must stay below ceiling ({projected} >= {ceiling})"
    return True, "ok"


cmd = sys.argv[1]

if cmd == "classify":
    result = classify(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]))
    result.pop("payload", None)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0)

if cmd == "budget-check":
    cumulative = {"accounted_tokens": int(sys.argv[2]), "estimated_usd": float(sys.argv[3]), "wall_secs": float(sys.argv[4])}
    approval = {"token_ceiling": int(sys.argv[5]), "usd_ceiling": float(sys.argv[6]), "wall_secs_ceiling": float(sys.argv[7])}
    ok, reason = budget_fits(cumulative, approval, int(sys.argv[8]), float(sys.argv[9]), float(sys.argv[10]))
    print(json.dumps({"allowed": ok, "reason": reason}, sort_keys=True))
    raise SystemExit(0 if ok else 3)

state_path = Path(sys.argv[2])

if cmd == "init":
    manifest_path = Path(sys.argv[3])
    phase = sys.argv[4]
    approval = {
        "approval_id": sys.argv[5],
        "token_ceiling": int(sys.argv[6]),
        "usd_ceiling": float(sys.argv[7]),
        "wall_secs_ceiling": float(sys.argv[8]),
        "max_attempts": int(sys.argv[9]),
        "config_sha256": sys.argv[10],
        "runner_sha256": sys.argv[11],
        "implementation_sha256": sys.argv[12],
    }
    config_slugs = sys.argv[13].split(",")
    baseline_ledger_path = sys.argv[14] if len(sys.argv) > 14 else "-"
    baseline_ledger_sha256 = sys.argv[15] if len(sys.argv) > 15 else "-"
    preflight_path = sys.argv[16] if len(sys.argv) > 16 else "-"
    preflight_sha256 = sys.argv[17] if len(sys.argv) > 17 else "-"
    baseline_ledger: dict[str, Any] | None = None
    baseline_cumulative: dict[str, Any] | None = None
    if baseline_ledger_path != "-" or baseline_ledger_sha256 != "-":
        if baseline_ledger_path == "-" or baseline_ledger_sha256 == "-":
            raise SystemExit("baseline ledger path and hash must be supplied together")
        ledger = validate_baseline_ledger(Path(baseline_ledger_path), baseline_ledger_sha256)
        ledger_cumulative = ledger["cumulative"]
        baseline_cumulative = {
            "accounted_tokens": int(ledger_cumulative["accounted_tokens"]),
            "estimated_usd": float(ledger_cumulative["estimated_usd"]),
            "wall_secs": float(ledger_cumulative["wall_secs"]),
        }
        baseline_ledger = {
            "path": baseline_ledger_path,
            "sha256": baseline_ledger_sha256,
            "physical_requests": int(ledger_cumulative["physical_requests"]),
            "known_returned_tokens": int(ledger_cumulative["known_returned_tokens"]),
        }
        approval["baseline_ledger_sha256"] = baseline_ledger_sha256
    if preflight_path != "-" or preflight_sha256 != "-":
        if preflight_path == "-" or preflight_sha256 == "-":
            raise SystemExit("preflight path and hash must be supplied together")
        if sha256_file(Path(preflight_path)) != preflight_sha256:
            raise SystemExit("preflight document hash mismatch")
        approval["preflight_path"] = preflight_path
        approval["preflight_sha256"] = preflight_sha256
    if state_path.exists():
        state = load(state_path)
        if state.get("approval") != approval or state.get("phase") != phase:
            raise SystemExit("existing state approval/phase does not match this invocation")
    else:
        state = {
            "schema_version": "gpt56_sweep_state.v1",
            "created_at_utc": utc_now(),
            "updated_at_utc": utc_now(),
            "phase": phase,
            "approval": approval,
            "cumulative": {
                "input_tokens": 0,
                "cached_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "accounted_tokens": 0,
                "estimated_usd": 0.0,
                "wall_secs": 0.0,
            },
            "config_state": {
                slug: {"infra_replacements": 0, "last_error_signature": None, "consecutive_identical": 0, "halted": False}
                for slug in config_slugs
            },
            "attempts": [],
            "canonical": {},
            "inflight": None,
        }
        if baseline_ledger is not None and baseline_cumulative is not None:
            state["baseline_ledger"] = baseline_ledger
            state["baseline_cumulative"] = baseline_cumulative
        atomic_json(state_path, state)
    write_manifest(state, manifest_path)
    raise SystemExit(0)

state = load(state_path)

if cmd == "recover":
    inflight = state.get("inflight")
    if isinstance(inflight, dict):
        print(f"1\t{inflight['reserved_wall_secs']}")
    else:
        print("0\t0")
    raise SystemExit(0)

if cmd == "status":
    slug, round_id = sys.argv[3], sys.argv[4]
    key = f"{slug}|{round_id}"
    cfg = state["config_state"][slug]
    print(f"{int(key in state['canonical'])}\t{int(bool(cfg['halted']))}")
    raise SystemExit(0)

if cmd == "reserve":
    manifest_path = Path(sys.argv[3])
    slug, model, effective_effort, round_id = sys.argv[4:8]
    runs_dir = Path(sys.argv[8])
    reserve_tokens, reserve_usd, reserve_wall = int(sys.argv[9]), float(sys.argv[10]), float(sys.argv[11])
    if state.get("inflight") is not None:
        raise SystemExit("cannot reserve while another attempt is inflight")
    if len(state["attempts"]) >= state["approval"]["max_attempts"]:
        print("maximum attempt bound reached", file=sys.stderr)
        raise SystemExit(4)
    ok, reason = budget_fits(aggregate_cumulative(state), state["approval"], reserve_tokens, reserve_usd, reserve_wall)
    if not ok:
        print(reason, file=sys.stderr)
        raise SystemExit(3)
    attempt_number = len(state["attempts"]) + 1
    is_replacement = any(
        item.get("config_slug") == slug and item.get("round_id") == round_id
        for item in state["attempts"]
    )
    cfg = state["config_state"][slug]
    if is_replacement:
        if str(state.get("phase", "")).startswith("smoke-"):
            cfg["halted"] = True
            state["updated_at_utc"] = utc_now()
            atomic_json(state_path, state)
            write_manifest(state, manifest_path)
            print("smoke phase does not replace infrastructure failures", file=sys.stderr)
            raise SystemExit(5)
        if cfg["infra_replacements"] >= 10:
            cfg["halted"] = True
            state["updated_at_utc"] = utc_now()
            atomic_json(state_path, state)
            write_manifest(state, manifest_path)
            print("per-config infra replacement cap reached", file=sys.stderr)
            raise SystemExit(5)
        cfg["infra_replacements"] += 1
    artifact_phase = str(state.get("phase", ""))
    if artifact_phase in {"production-core-v2", "production-core-v3"}:
        stem = f"{slug}-{artifact_phase}-{round_id}-a{attempt_number:03d}"
    else:
        stem = f"{slug}-{round_id}-a{attempt_number:03d}"
    raw_json = str(runs_dir / f"{stem}.json")
    raw_log = str(runs_dir / f"{stem}.log")
    if Path(raw_json).exists() or Path(raw_log).exists():
        print(f"refusing to overwrite existing attempt artifact: {raw_json} or {raw_log}", file=sys.stderr)
        raise SystemExit(6)
    state["inflight"] = {
        "attempt_number": attempt_number,
        "config_slug": slug,
        "model": model,
        "effective_effort": effective_effort,
        "round_id": round_id,
        "raw_json": raw_json,
        "raw_log": raw_log,
        "reserved_tokens": reserve_tokens,
        "reserved_usd": reserve_usd,
        "reserved_wall_secs": reserve_wall,
        "is_replacement": is_replacement,
        "reserved_at_utc": utc_now(),
    }
    state["updated_at_utc"] = utc_now()
    atomic_json(state_path, state)
    write_manifest(state, manifest_path)
    print(f"{attempt_number}\t{raw_json}\t{raw_log}")
    raise SystemExit(0)

if cmd == "record":
    manifest_path = Path(sys.argv[3])
    rc, wall_secs = int(sys.argv[4]), float(sys.argv[5])
    inflight = state.get("inflight")
    if not isinstance(inflight, dict):
        raise SystemExit("no inflight attempt to record")
    json_path, log_path = Path(inflight["raw_json"]), Path(inflight["raw_log"])
    result = classify(json_path, log_path, rc)
    payload = result.pop("payload")
    if payload is not None:
        identity_values = {
            "model": nested_identity(payload, "model"),
            "effective_effort": nested_identity(payload, "effective_effort"),
            "round_id": nested_identity(payload, "round_id"),
        }
        expected_values = {
            "model": inflight["model"],
            "effective_effort": inflight["effective_effort"],
            "round_id": inflight["round_id"],
        }
        if result["eligible"] and identity_values != expected_values:
            result["eligible"] = False
            result["classification"] = "identity_mismatch"
            traces = payload.get("responses_traces") if isinstance(payload.get("responses_traces"), list) else []
            result["error_signature"] = error_signature(
                "identity_mismatch", result["terminal_reason"], traces, log_path, rc
            )
    usage = result["usage"]
    if result["usage_known"]:
        accounted_tokens = usage["input_tokens"] + usage["output_tokens"]
        assert payload is not None
        estimated_usd = price_for(inflight["model"], payload)
        usage_estimated = False
        accounting_basis = "measured_complete_trace_usage"
    else:
        accounted_tokens = inflight["reserved_tokens"]
        estimated_usd = inflight["reserved_usd"]
        usage_estimated = True
        accounting_basis = "full_reservation_incomplete_trace_usage"

    identity = f"{inflight['config_slug']}|{inflight['round_id']}"
    selected = bool(result["eligible"] and identity not in state["canonical"])
    if selected:
        selection_reason = (
            "selected_first_eligible_model_failure_with_json"
            if result["terminal_reason"] == "response_incomplete"
            else "selected_first_eligible"
        )
    elif result["eligible"]:
        selection_reason = "rejected_later_eligible_attempt"
    else:
        selection_reason = f"rejected_infra:{result['classification']}"

    attempt = {
        **inflight,
        "finished_at_utc": utc_now(),
        "exit_code": rc,
        "wall_secs": wall_secs,
        "classification": result["classification"],
        "eligible": result["eligible"],
        "selected": selected,
        "selection_reason": selection_reason,
        "terminal_reason": result["terminal_reason"],
        "response_statuses": result["response_statuses"],
        "error_signature": result["error_signature"],
        "usage": usage,
        "usage_estimated": usage_estimated,
        "accounting_basis": accounting_basis,
        "accounted_tokens": accounted_tokens,
        "estimated_usd": estimated_usd,
        "json_sha256": sha256_file(json_path),
        "log_sha256": sha256_file(log_path),
        "run_id": nested_identity(payload, "run_id") if payload else None,
        "requested_thinking": nested_identity(payload, "thinking") if payload else None,
        "recorded_effective_effort": nested_identity(payload, "effective_effort") if payload else None,
        "recorded_round_id": nested_identity(payload, "round_id") if payload else None,
        "derivative_json": None,
    }
    state["attempts"].append(attempt)
    if selected:
        state["canonical"][identity] = inflight["attempt_number"]

    cfg = state["config_state"][inflight["config_slug"]]
    if result["eligible"]:
        cfg["last_error_signature"] = None
        cfg["consecutive_identical"] = 0
    else:
        signature = result["error_signature"]
        if signature == cfg["last_error_signature"]:
            cfg["consecutive_identical"] += 1
        else:
            cfg["last_error_signature"] = signature
            cfg["consecutive_identical"] = 1
        if result["halt_immediately"] or cfg["consecutive_identical"] >= 2 or (
            inflight["is_replacement"] and cfg["infra_replacements"] >= 10
        ):
            cfg["halted"] = True

    cumulative = state["cumulative"]
    for key in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens"):
        cumulative[key] += usage[key]
    cumulative["accounted_tokens"] += accounted_tokens
    cumulative["estimated_usd"] += estimated_usd
    cumulative["wall_secs"] += max(0.0, wall_secs)
    state["inflight"] = None
    state["updated_at_utc"] = utc_now()
    atomic_json(state_path, state)
    write_manifest(state, manifest_path)
    output = {
        "attempt_number": attempt["attempt_number"],
        "classification": result["classification"],
        "eligible": result["eligible"],
        "selected": selected,
        "halted": cfg["halted"],
        "infra_replacements": cfg["infra_replacements"],
        "cumulative": cumulative,
    }
    if "baseline_ledger" in state:
        output["aggregate_cumulative"] = aggregate_cumulative(state)
    print(json.dumps(output, sort_keys=True))
    raise SystemExit(0)

if cmd == "summary":
    expected = int(sys.argv[3])
    output = {
        "attempts": len(state["attempts"]),
        "canonical": len(state["canonical"]),
        "expected_canonical": expected,
        "complete": len(state["canonical"]) == expected,
        "halted_configs": sorted(slug for slug, value in state["config_state"].items() if value["halted"]),
        "cumulative": state["cumulative"],
    }
    if "baseline_ledger" in state:
        output["baseline_cumulative"] = state["baseline_cumulative"]
        output["aggregate_cumulative"] = aggregate_cumulative(state)
    print(json.dumps(output, sort_keys=True))
    raise SystemExit(0 if len(state["canonical"]) == expected else 4)

raise SystemExit(f"unknown state command: {cmd}")
PY
}

validate_configs() {
  local spec slug model thinking override effective max_tokens request_timeout idle_timeout episode_timeout reserve_wall reserve_tokens reserve_usd
  local count=0
  declare -A wire_identities=()
  declare -A slugs=()
  for spec in "${CONFIGS[@]}"; do
    IFS=$'\t' read -r slug model thinking override effective max_tokens request_timeout idle_timeout episode_timeout reserve_wall reserve_tokens reserve_usd <<< "$spec"
    if [[ -n "${slugs[$slug]:-}" ]]; then
      printf 'duplicate config slug: %s\n' "$slug" >&2
      return 2
    fi
    if [[ -n "${wire_identities[$model|$effective]:-}" ]]; then
      printf 'duplicate wire identity: %s %s\n' "$model" "$effective" >&2
      return 2
    fi
    slugs[$slug]=1
    wire_identities[$model|$effective]=1
    count=$((count + 1))
  done
  [[ "$count" -eq 9 ]] || return 2
}

print_configs() {
  local spec slug model thinking override effective max_tokens request_timeout idle_timeout episode_timeout reserve_wall reserve_tokens reserve_usd round_id round_number
  printf 'config_slug\tmodel\tthinking\toverride\teffective_effort\tmax_tokens\tround_id\trequest_timeout_secs\tidle_timeout_secs\tepisode_timeout_secs\twall_reservation_secs\ttoken_reservation\tusd_reservation\n'
  if [[ "$PHASE" == smoke-* ]]; then
    for spec in "${CONFIGS[@]}"; do
      IFS=$'\t' read -r slug model thinking override effective max_tokens request_timeout idle_timeout episode_timeout reserve_wall reserve_tokens reserve_usd <<< "$spec"
      if [[ "$PHASE" == "smoke-core" && "$model" == "gpt-5.6-sol" ]]; then
        continue
      fi
      if [[ "$PHASE" == "smoke-sol" && "$model" != "gpt-5.6-sol" ]]; then
        continue
      fi
      if [[ "$PHASE" == "smoke-luna-xhigh-v4" && "$slug" != "gpt56-luna-xhigh" ]]; then
        continue
      fi
      if [[ "$PHASE" == "smoke-core-remainder-v5" \
         && "$slug" != "gpt56-luna-max" \
         && "$slug" != "gpt56-terra-low" \
         && "$slug" != "gpt56-terra-xhigh" \
         && "$slug" != "gpt56-terra-max" ]]; then
        continue
      fi
      if [[ "$PHASE" == "smoke-parallel-replay-v6" \
         && "$slug" != "gpt56-luna-low" ]]; then
        continue
      fi
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$slug" "$model" "$thinking" "$override" "$effective" "$max_tokens" "$PHASE" "$request_timeout" "$idle_timeout" "$episode_timeout" "$reserve_wall" "$reserve_tokens" "$reserve_usd"
    done
  elif [[ "$PHASE" == "production-core-v1" \
       || "$PHASE" == "production-core-v2" \
       || "$PHASE" == "production-core-v3" ]]; then
    for round_number in $(seq 1 25); do
      printf -v round_id 'r%02d' "$round_number"
      for spec in "${CONFIGS[@]}"; do
        IFS=$'\t' read -r slug model thinking override effective max_tokens request_timeout idle_timeout episode_timeout reserve_wall reserve_tokens reserve_usd <<< "$spec"
        if [[ "$model" == "gpt-5.6-sol" ]]; then
          continue
        fi
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$slug" "$model" "$thinking" "$override" "$effective" "$max_tokens" "$round_id" "$request_timeout" "$idle_timeout" "$episode_timeout" "$reserve_wall" "$reserve_tokens" "$reserve_usd"
      done
    done
  else
    for round_number in $(seq 1 25); do
      printf -v round_id 'r%02d' "$round_number"
      for spec in "${CONFIGS[@]}"; do
        IFS=$'\t' read -r slug model thinking override effective max_tokens request_timeout idle_timeout episode_timeout reserve_wall reserve_tokens reserve_usd <<< "$spec"
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$slug" "$model" "$thinking" "$override" "$effective" "$max_tokens" "$round_id" "$request_timeout" "$idle_timeout" "$episode_timeout" "$reserve_wall" "$reserve_tokens" "$reserve_usd"
      done
    done
  fi
}

validate_configs || exit $?

config_sha256() {
  {
    printf 'phase=%s\n' "$PHASE"
    print_configs
  } | sha256sum | cut -d' ' -f1
}

implementation_sha256() {
  sha256sum run_gpt56_sweep.sh mini-rl-env.py llm_factory.py openai_responses_service.py \
    report_contract.py synthetic_world.py tool_catalog.py taskagent_event_summaries.py \
    system_instruction.txt \
    | sha256sum | cut -d' ' -f1
}

if [[ "${PRINT_APPROVAL_HASHES:-0}" == "1" ]]; then
  printf 'config_sha256=%s\n' "$(config_sha256)"
  printf 'runner_sha256=%s\n' "$(sha256sum "$0" | cut -d' ' -f1)"
  printf 'implementation_sha256=%s\n' "$(implementation_sha256)"
  exit 0
fi

if [[ "${PRINT_CONFIGS:-0}" == "1" ]]; then
  print_configs
  exit 0
fi

if [[ "${CLASSIFY_ATTEMPT:-0}" == "1" ]]; then
  : "${CLASSIFY_JSON_PATH:?CLASSIFY_JSON_PATH is required}"
  : "${CLASSIFY_LOG_PATH:?CLASSIFY_LOG_PATH is required}"
  : "${CLASSIFY_EXIT_CODE:?CLASSIFY_EXIT_CODE is required}"
  state_tool classify "$CLASSIFY_JSON_PATH" "$CLASSIFY_LOG_PATH" "$CLASSIFY_EXIT_CODE"
  exit $?
fi

if [[ "${BUDGET_FIXTURE:-0}" == "1" ]]; then
  state_tool budget-check \
    "${FIXTURE_ACCOUNTED_TOKENS:?}" "${FIXTURE_ESTIMATED_USD:?}" "${FIXTURE_WALL_SECS:?}" \
    "${FIXTURE_TOKEN_CEILING:?}" "${FIXTURE_USD_CEILING:?}" "${FIXTURE_WALL_CEILING:?}" \
    "${FIXTURE_RESERVE_TOKENS:?}" "${FIXTURE_RESERVE_USD:?}" "${FIXTURE_RESERVE_WALL:?}"
  exit $?
fi

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  print_configs | while IFS=$'\t' read -r slug model thinking override effective max_tokens round_id request_timeout idle_timeout episode_timeout reserve_wall reserve_tokens reserve_usd; do
    [[ "$slug" == "config_slug" ]] && continue
    artifact_stem="${slug}-${round_id}-aNNN"
    if [[ "$PHASE" == "production-core-v2" || "$PHASE" == "production-core-v3" ]]; then
      artifact_stem="${slug}-${PHASE}-${round_id}-aNNN"
    fi
    cmd=(.venv/bin/python mini-rl-env.py --provider openai --model "$model" --task-variant natural --thinking "$thinking" --max-tokens "$max_tokens" --max-turns 50 --function-call-timeout-secs 20 --round-id "$round_id" --llm-request-timeout-secs "$request_timeout" --llm-stream-idle-timeout-secs "$idle_timeout" --log-json "$RUNS_DIR/${artifact_stem}.json")
    if [[ "$override" != "-" ]]; then
      cmd+=(--reasoning-effort "$override")
    fi
    printf 'timeout %q ' "$episode_timeout"
    printf '%q ' "${cmd[@]}"
    printf '\n'
  done
  exit 0
fi

: "${GPT56_APPROVAL_ID:?GPT56_APPROVAL_ID is required for live execution}"
: "${GPT56_TOKEN_CEILING:?GPT56_TOKEN_CEILING is required for live execution}"
: "${GPT56_USD_CEILING:?GPT56_USD_CEILING is required for live execution}"
: "${GPT56_WALL_SECS_CEILING:?GPT56_WALL_SECS_CEILING is required for live execution}"
: "${GPT56_MAX_ATTEMPTS:?GPT56_MAX_ATTEMPTS is required for live execution}"
: "${GPT56_EXPECTED_CONFIG_SHA256:?GPT56_EXPECTED_CONFIG_SHA256 is required for live execution}"
: "${GPT56_EXPECTED_RUNNER_SHA256:?GPT56_EXPECTED_RUNNER_SHA256 is required for live execution}"
: "${GPT56_EXPECTED_IMPLEMENTATION_SHA256:?GPT56_EXPECTED_IMPLEMENTATION_SHA256 is required for live execution}"

config_slugs=""
while IFS=$'\t' read -r slug _; do
  [[ "$slug" == "config_slug" ]] && continue
  config_slugs="${config_slugs:+$config_slugs,}$slug"
done < <(print_configs)
matrix_sha256="$(config_sha256)"
runner_sha256="$(sha256sum "$0" | cut -d' ' -f1)"
implementation_sha256="$(implementation_sha256)"
if [[ "$matrix_sha256" != "$GPT56_EXPECTED_CONFIG_SHA256" \
   || "$runner_sha256" != "$GPT56_EXPECTED_RUNNER_SHA256" \
   || "$implementation_sha256" != "$GPT56_EXPECTED_IMPLEMENTATION_SHA256" ]]; then
  printf 'APPROVAL_HASH_MISMATCH expected=%s/%s/%s actual=%s/%s/%s\n' \
    "$GPT56_EXPECTED_CONFIG_SHA256" "$GPT56_EXPECTED_RUNNER_SHA256" \
    "$GPT56_EXPECTED_IMPLEMENTATION_SHA256" "$matrix_sha256" "$runner_sha256" \
    "$implementation_sha256" >&2
  exit 8
fi
baseline_ledger_path="-"
baseline_ledger_sha256="-"
if [[ "$PHASE" == "smoke-core-remainder-v5" \
   || "$PHASE" == "smoke-parallel-replay-v6" \
   || "$PHASE" == "production-core-v1" \
   || "$PHASE" == "production-core-v2" \
   || "$PHASE" == "production-core-v3" ]]; then
  : "${GPT56_BASELINE_LEDGER_PATH:?GPT56_BASELINE_LEDGER_PATH is required for $PHASE}"
  : "${GPT56_EXPECTED_BASELINE_LEDGER_SHA256:?GPT56_EXPECTED_BASELINE_LEDGER_SHA256 is required for $PHASE}"
  baseline_ledger_path="$GPT56_BASELINE_LEDGER_PATH"
  baseline_ledger_sha256="$(sha256sum "$baseline_ledger_path" 2>/dev/null | cut -d' ' -f1)"
  if [[ "$baseline_ledger_sha256" != "$GPT56_EXPECTED_BASELINE_LEDGER_SHA256" ]]; then
    printf 'BASELINE_LEDGER_HASH_MISMATCH expected=%s actual=%s path=%s\n' \
      "$GPT56_EXPECTED_BASELINE_LEDGER_SHA256" "${baseline_ledger_sha256:-missing}" \
      "$baseline_ledger_path" >&2
    exit 10
  fi
fi
preflight_path="-"
preflight_sha256="-"
if [[ "$PHASE" == "smoke-parallel-replay-v6" ]]; then
  : "${GPT56_PREFLIGHT_PATH:?GPT56_PREFLIGHT_PATH is required for $PHASE}"
  : "${GPT56_EXPECTED_PREFLIGHT_SHA256:?GPT56_EXPECTED_PREFLIGHT_SHA256 is required for $PHASE}"
  preflight_path="$GPT56_PREFLIGHT_PATH"
  preflight_sha256="$GPT56_EXPECTED_PREFLIGHT_SHA256"
fi
installed_openai_sdk_version="$(.venv/bin/python -c 'import importlib.metadata; print(importlib.metadata.version("openai"))')"
if [[ "$installed_openai_sdk_version" != "$EXPECTED_OPENAI_SDK_VERSION" ]]; then
  printf 'OPENAI_SDK_VERSION_MISMATCH expected=%s actual=%s\n' \
    "$EXPECTED_OPENAI_SDK_VERSION" "$installed_openai_sdk_version" >&2
  exit 9
fi
if [[ ( "$PHASE" == "production-core-v1" \
     || "$PHASE" == "production-core-v2" \
     || "$PHASE" == "production-core-v3" ) \
   && ( -e "$STATE_PATH" || -e "$MANIFEST_PATH" ) ]]; then
  printf 'PRODUCTION_RESUME_FORBIDDEN existing state or manifest requires a new successor phase\n' >&2
  exit 11
fi
if [[ "$PHASE" == "smoke-parallel-replay-v6" \
   && ( -e "$STATE_PATH" || -e "$MANIFEST_PATH" ) ]]; then
  printf 'PHASE_RESUME_FORBIDDEN existing state or manifest requires a separately approved successor package\n' >&2
  exit 11
fi

mkdir -p "$RUNS_DIR" "$PROJECT_DIR"
if [[ "${GPT56_OFFLINE_TEST:-0}" == "1" ]]; then
  : "${GPT56_OFFLINE_LOCK_PATH:?GPT56_OFFLINE_LOCK_PATH is required in offline test mode}"
  LOCK_PATH="$GPT56_OFFLINE_LOCK_PATH"
else
  LOCK_PATH="$PROJECT_DIR/gpt56-hosted-openai.lock"
fi
exec 9>"$LOCK_PATH"
if ! flock -n 9; then
  printf 'RUNNER_LOCKED another GPT-5.6 hosted OpenAI worker holds %s\n' "$LOCK_PATH" >&2
  exit 7
fi
state_tool init "$STATE_PATH" "$MANIFEST_PATH" "$PHASE" \
  "$GPT56_APPROVAL_ID" "$GPT56_TOKEN_CEILING" "$GPT56_USD_CEILING" \
  "$GPT56_WALL_SECS_CEILING" "$GPT56_MAX_ATTEMPTS" "$matrix_sha256" "$runner_sha256" \
  "$implementation_sha256" "$config_slugs" "$baseline_ledger_path" \
  "$baseline_ledger_sha256" "$preflight_path" "$preflight_sha256" || exit $?
printf 'APPROVAL_HASH_OK phase=%s config=%s runner=%s implementation=%s baseline_ledger=%s preflight=%s\n' \
  "$PHASE" "$matrix_sha256" "$runner_sha256" "$implementation_sha256" \
  "$baseline_ledger_sha256" "$preflight_sha256"

recovery="$(state_tool recover "$STATE_PATH")" || exit $?
IFS=$'\t' read -r has_inflight recovery_wall <<< "$recovery"
if [[ "$has_inflight" == "1" ]]; then
  printf 'RECOVER_INFLIGHT classifying interrupted attempt conservatively\n'
  state_tool record "$STATE_PATH" "$MANIFEST_PATH" 125 "$recovery_wall" || exit $?
fi

if [[ "${GPT56_OFFLINE_TEST:-0}" == "1" ]]; then
  : "${GPT56_OFFLINE_EXECUTOR:?GPT56_OFFLINE_EXECUTOR is required in offline test mode}"
  OPENAI_API_KEY="offline-test-only"
else
  OPENAI_API_KEY="$(rg --no-line-number '^OPENAI_API_KEY=' /home/khkramer/src/gb-benchmarks/.env | cut -d= -f2-)"
  if [[ -z "$OPENAI_API_KEY" ]]; then
    printf 'OPENAI_API_KEY was not found in the repository .env\n' >&2
    exit 2
  fi
fi
export OPENAI_API_KEY

budget_stopped=0
while IFS=$'\t' read -r slug model thinking override effective max_tokens round_id request_timeout idle_timeout episode_timeout reserve_wall reserve_tokens reserve_usd; do
    [[ "$slug" == "config_slug" ]] && continue
    while true; do
      status_output="$(state_tool status "$STATE_PATH" "$slug" "$round_id")" || exit $?
      IFS=$'\t' read -r selected halted <<< "$status_output"
      if [[ "$selected" == "1" ]]; then
        break
      fi
      if [[ "$halted" == "1" ]]; then
        printf 'CONFIG_HALTED config=%s round=%s\n' "$slug" "$round_id"
        break
      fi

      reservation="$(state_tool reserve "$STATE_PATH" "$MANIFEST_PATH" "$slug" "$model" "$effective" "$round_id" "$RUNS_DIR" "$reserve_tokens" "$reserve_usd" "$reserve_wall")"
      reserve_rc=$?
      if [[ "$reserve_rc" -ne 0 ]]; then
        status_output="$(state_tool status "$STATE_PATH" "$slug" "$round_id")" || exit $?
        IFS=$'\t' read -r _ halted_after_reserve <<< "$status_output"
        if [[ "$halted_after_reserve" == "1" ]]; then
          printf 'CONFIG_HALTED config=%s round=%s reason=config_policy\n' "$slug" "$round_id"
        else
          case "$reserve_rc" in
            3) stop_reason=budget ;;
            4) stop_reason=max_attempts ;;
            6) stop_reason=artifact_collision ;;
            *) stop_reason=runner_error ;;
          esac
          printf 'RUNNER_STOP config=%s round=%s reason=%s rc=%s\n' "$slug" "$round_id" "$stop_reason" "$reserve_rc" >&2
          budget_stopped=1
        fi
        break
      fi
      IFS=$'\t' read -r attempt_number raw_json raw_log <<< "$reservation"

      if [[ "${GPT56_OFFLINE_TEST:-0}" == "1" ]]; then
        cmd=(.venv/bin/python "$GPT56_OFFLINE_EXECUTOR")
      else
        cmd=(.venv/bin/python mini-rl-env.py)
      fi
      cmd+=(--provider openai --model "$model" --task-variant natural --thinking "$thinking" --max-tokens "$max_tokens" --max-turns 50 --function-call-timeout-secs 20 --round-id "$round_id" --llm-request-timeout-secs "$request_timeout" --llm-stream-idle-timeout-secs "$idle_timeout" --log-json "$raw_json")
      if [[ "$override" != "-" ]]; then
        cmd+=(--reasoning-effort "$override")
      fi

      start_epoch="$(date +%s)"
      printf 'RUN_START config=%s model=%s effort=%s round=%s attempt=%s utc=%s\n' "$slug" "$model" "$effective" "$round_id" "$attempt_number" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$raw_log"
      timeout "$episode_timeout" "${cmd[@]}" < /dev/null 2>&1 | tee -a "$raw_log"
      run_rc=${PIPESTATUS[0]}
      elapsed_secs=$(( $(date +%s) - start_epoch ))
      printf 'RUN_EXIT config=%s round=%s attempt=%s rc=%s elapsed_secs=%s utc=%s\n' "$slug" "$round_id" "$attempt_number" "$run_rc" "$elapsed_secs" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$raw_log"
      state_tool record "$STATE_PATH" "$MANIFEST_PATH" "$run_rc" "$elapsed_secs" || exit $?
    done
    [[ "$budget_stopped" == "1" ]] && break
done < <(print_configs)

case "$PHASE" in
  smoke-core) expected_canonical=6 ;;
  smoke-sol) expected_canonical=3 ;;
  smoke-luna-xhigh-v4) expected_canonical=1 ;;
  smoke-core-remainder-v5) expected_canonical=4 ;;
  smoke-parallel-replay-v6) expected_canonical=1 ;;
  production-core-v1) expected_canonical=150 ;;
  production-core-v2) expected_canonical=150 ;;
  production-core-v3) expected_canonical=150 ;;
  full) expected_canonical=225 ;;
esac
state_tool summary "$STATE_PATH" "$expected_canonical"
exit $?
