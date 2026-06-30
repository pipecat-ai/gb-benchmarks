# Step 3 Codex Review: Baseten Empty/No-Usage Transport Retry

Verdict: **Blocking until the retry gate is narrowed to the intended Baseten GLM/Nemotron model set.** The core retry state machine otherwise looks coherent: capture ownership, turn accounting, watchdog cancellation, and retry exhaustion behavior line up with the Step 3 invariants.

## Blocking

1. **Retry and telemetry are gated to every Baseten endpoint, not Baseten GLM/Nemotron only.**
   - Plan Step 3 says the B signature is "gated to Baseten GLM/Nemotron" (`PLAN.md:68-70`), and the rules require model-identity gating for affected behavior (`PLAN.md:35-38`).
   - Runtime enables the feature solely from `_is_baseten_endpoint(args.openai_base_url)` at `mini-rl-env.py:1776`.
   - `_transport_empty_retry_enabled()` only rechecks the Baseten URL at `mini-rl-env.py:1519-1523`.
   - Per-turn telemetry is also host-wide at `mini-rl-env.py:1697-1699`, and summary telemetry is host-wide at `mini-rl-env.py:2463-2469`.
   - The tests accidentally encode this too-broad scope by using `model="baseten-demo"` with a Baseten URL at `tests/test_empty_retry.py:112-118` and enabling retry from URL alone at `tests/test_empty_retry.py:133`.
   - Impact: any non-target model served from Baseten can now retry empty/no-usage responses and emit the new telemetry fields. Non-Baseten URLs are unaffected, but non-target Baseten models are not.

## Should-Fix

1. **Add explicit negative coverage for non-target gating.**
   - There is no test proving a non-Baseten URL does not match the signature or emit `transport_empty_*` / `empty_response_*` telemetry.
   - There is also no test proving a Baseten non-GLM/non-Nemotron model is unchanged. This matters because the current fixture uses `baseten-demo` and would need to change once the gate is corrected.

2. **Exhaustion capture cleanup is not asserted.**
   - The success test does assert the final retry capture owns the successful turn and clears capture state (`tests/test_empty_retry.py:250-253`).
   - The exhausted path test asserts accounting and nudge behavior (`tests/test_empty_retry.py:274-298`), but it does not assert the exhausted turn's `inference_index`, earlier discarded capture entries, empty pending queue, or cleared `_active_inference_capture_index`.
   - Implementation appears correct via `discard_active_inference_capture()` at `mini-rl-env.py:2056-2062` and active-index clearing in `discard_pending_inference_capture()` at `mini-rl-env.py:2036-2046`, but this is a hard invariant and should be locked down.

3. **Whitespace/raw-sanitized edge cases are untested.**
   - The signature requires exact empty sanitized text, raw text, and thought at `mini-rl-env.py:1525-1534`, so whitespace-only or raw-control-token-only text is not retried. That is a conservative reading of "empty text/raw", but the only text negative test is visible prose (`tests/test_empty_retry.py:306-333`).

## Clean / Confirmed

- Capture lifecycle: empty -> retry -> success is handled correctly. The first response activates the current capture at `mini-rl-env.py:1540-1547`; retry queues a new capture before queuing `LLMRunFrame` at `mini-rl-env.py:1428-1431`; `_finalize_if_ready()` then discards the active empty-attempt capture at `mini-rl-env.py:1649-1651`. Because `discard_pending_inference_capture()` clears `_active_inference_capture_index` when it matches (`mini-rl-env.py:2040-2041`), the retry response activates its own pending capture.
- Accounting: `_transport_empty_retries` is initialized outside `_reset_response()` (`mini-rl-env.py:1499`) and `_reset_response()` does not clear it (`mini-rl-env.py:1502-1517`). Successful retry returns before `no_tool_call_count`, `bad_actions_count`, turn log append, or `turn_count` increment (`mini-rl-env.py:1634-1652`). Exhaustion falls through to the existing no-tool path and counts once at `mini-rl-env.py:1668-1671`, then resets retry state after final turn completion at `mini-rl-env.py:1717-1724`.
- Watchdog: `on_response_end()` arms the no-tool watchdog for no-tool responses at `mini-rl-env.py:1194-1201`; retry cancels both no-tool and inference watchdog handles before queuing the retry at `mini-rl-env.py:1404-1409`. Exhaustion leaves the watchdog path intact.
- Signature: visible text-only responses are not retried because both sanitized and raw response text must be exactly empty (`mini-rl-env.py:1529-1530`), and observed `last_error_event` blocks retry (`mini-rl-env.py:1533`). The tests cover visible text-only no-usage (`tests/test_empty_retry.py:306-333`) and an existing error event (`tests/test_empty_retry.py:341-361`).
- Re-entrancy/races: `can_retry_transport_empty_response()` blocks retry while an LLM call or tool call is in flight (`mini-rl-env.py:1391-1398`), and retry sets `_llm_inflight = True` before queueing the new run (`mini-rl-env.py:1428-1431`). The retry path prunes empty assistant context messages before the retry run (`mini-rl-env.py:1411-1420`). With the universal assistant aggregator used by the pipeline, true empty responses do not append a later empty assistant message on response end because aggregation is empty.

## Test Run

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_empty_retry.py -p no:cacheprovider` could not run because the venv has no `pytest`.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/test_empty_retry.py` passed: 5 tests, OK.
