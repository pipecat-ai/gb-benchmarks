# Step 6 HTTP 429 Rate-limit Review

Scope: reviewed only the Baseten/OpenAI HTTP-429 rate-limit work in `mini-rl-env.py` and `tests/test_rate_limit.py`. Ignored unrelated Anthropic `claude-sonnet-5` / `display=summarized` changes as requested.

## Verdict

Blocking.

The retry wrapper is mostly correct at the direct `get_chat_completions` boundary, but sustained-429 exhaustion does not reach the harness-level `inference_failure` path in the real Pipecat pipeline. It is converted into an empty/no-tool response path instead, and can trigger the step-3 empty-response retry.

## Blocking

1. Sustained 429 exhaustion is not recorded as `inference_failure` in the real harness.

   In `_apply_baseten_rate_limit_retry_wrapper`, the fifth failed attempt is recorded and re-raised (`port-to-port/mini-rl-env.py:580-593`). That direct behavior is fine, but the wrapper is installed on Pipecat's OpenAI service (`port-to-port/mini-rl-env.py:2752-2757`), and the pipeline places `_BenchmarkResponseTracker` downstream of the LLM service (`port-to-port/mini-rl-env.py:2106-2112`).

   Pipecat's OpenAI service catches exceptions from `_process_context`, emits a non-fatal upstream `ErrorFrame`, and still pushes `LLMFullResponseEndFrame`. Since the error frame goes upstream, `_BenchmarkResponseTracker` does not see it. The tracker then sees start/end with no text, no tool calls, no usage, and `last_error_event is None`, matching the transport-empty signature (`port-to-port/mini-rl-env.py:1717-1726`). That drives the empty retry path (`port-to-port/mini-rl-env.py:1826-1844`) and then the normal `no_tool_call` bad-action path (`port-to-port/mini-rl-env.py:1860-1863`), not the runner exception path that synthesizes `failure_class="inference_failure"` (`port-to-port/mini-rl-env.py:2786-2814`).

   I verified this with a targeted local probe using the actual pipeline shape: sustained 429s produced 15 `create` calls, `rate_limit_count=15`, `empty_response_count=3`, and a turn log with `failure_class="no_tool_call"`, not `inference_failure`. The 15 calls came from 5 rate-limit attempts across the original turn plus two transport-empty retries; real SDK retries can add more underlying HTTP attempts.

   Impact: this violates the intended exhaustion behavior, pollutes `empty_response_count`/`no_tool_call_count`/bad actions, and makes the 429 retry path not independent from the step-3 empty retry.

## Should-fix

1. The sustained-429 test does not exercise the real exhaustion path.

   `test_sustained_429_exhausts_retries_and_propagates_for_inference_failure` calls the patched method directly and asserts `openai.APIStatusError` is raised (`port-to-port/tests/test_rate_limit.py:173-223`). That bypasses Pipecat `process_frame`, the non-fatal `ErrorFrame`, `_BenchmarkResponseTracker`, and `_runner_done`. The test name claims inference-failure behavior, but it does not assert `runtime.terminal_reason`, a turn log `failure_class`, raw JSON summary behavior, or absence of empty-response retry.

2. Catch-scope tests are incomplete.

   The implementation correctly re-raises non-429 `APIStatusError` because `_is_openai_rate_limit_error` requires status 429 for generic `APIStatusError` (`port-to-port/mini-rl-env.py:459-462`) and the wrapper re-raises when that predicate is false (`port-to-port/mini-rl-env.py:575-577`). However, no test covers a non-429 `APIStatusError`; the helper exists at `port-to-port/tests/test_rate_limit.py:81-92` but is only used with 429.

3. Gating tests cover non-Baseten OpenAI, but not non-OpenAI providers.

   The wrapper install gate is provider == OpenAI plus Baseten endpoint (`port-to-port/mini-rl-env.py:558-559`), and runtime telemetry is string-gated similarly (`port-to-port/mini-rl-env.py:1973-1977`). `test_non_baseten_endpoint_does_not_install_wrapper_or_retry` covers OpenAI on `api.openai.com` (`port-to-port/tests/test_rate_limit.py:225-252`), but there is no direct assertion that an Anthropic/Google/Cerebras provider with any URL-like arg remains unaffected.

## Nice-to-have

1. Document or bound the interaction with the OpenAI SDK's own retry policy.

   Pipecat constructs `AsyncOpenAI` without overriding `max_retries`, so the SDK default is still active. The wrapper's `BASETEN_RATE_LIMIT_MAX_ATTEMPTS = 5` (`port-to-port/mini-rl-env.py:163`) is therefore five wrapper-level stream-open attempts, not necessarily five HTTP requests. This is not inherently wrong, but it should be explicit because the outer backoff (`port-to-port/mini-rl-env.py:496-507`) stacks with SDK retries and SDK backoff.

2. Add direct coverage for `Retry-After` parsing and cap behavior.

   Numeric and HTTP-date parsing look correct: header lookup (`port-to-port/mini-rl-env.py:465-480`), numeric parse with non-negative clamp (`port-to-port/mini-rl-env.py:482-485`), HTTP-date parse with UTC fallback (`port-to-port/mini-rl-env.py:487-493`), and cap at 30 seconds (`port-to-port/mini-rl-env.py:497-499`). Current tests only cover numeric `Retry-After: 0` (`port-to-port/tests/test_rate_limit.py:131-155`).

3. Add a mid-stream 429 regression note/test if the scope is intentional.

   The wrapper catches only failures thrown by `await original(params_from_context)` (`port-to-port/mini-rl-env.py:573-575`). A 429 raised later during `async for chunk in chunk_stream` is outside this wrapper by design. The docstring says "stream-open boundary" (`port-to-port/mini-rl-env.py:557`), so this is acceptable, but a tiny test or comment would prevent accidental overclaiming.

## Clean

1. Async wrapping is correct for the harness path.

   The wrapper saves the bound `get_chat_completions` method before replacement (`port-to-port/mini-rl-env.py:564-569`), calls it with the same `params_from_context`, awaits it (`port-to-port/mini-rl-env.py:573-575`), and returns the stream object only after success (`port-to-port/mini-rl-env.py:599-601`). Pipecat builds a fresh request dict inside `get_chat_completions`, so reusing the invocation params is safe for this benchmark's universal-context text/tool path.

2. Backoff attempt math is correct.

   Attempts start at 1 (`port-to-port/mini-rl-env.py:570`); failed attempts 1-4 sleep with delays based on exponents 0-3 (`port-to-port/mini-rl-env.py:501-507`), and attempt 5 is marked exhausted with no sleep (`port-to-port/mini-rl-env.py:580-595`). This produces 2s, 4s, 8s, 16s base delays, capped at 30s with up to 1s jitter.

3. Retry-success telemetry counts only recovered 429 turns.

   `saw_rate_limit` is set only after a caught 429 (`port-to-port/mini-rl-env.py:571-580`), and `rate_limit_retry_success_count` increments only after a later successful `original(...)` call (`port-to-port/mini-rl-env.py:599-600`). It counts once per recovered call, not once per failed attempt.

4. Telemetry is Baseten-gated and does not directly affect leaderboard fields.

   Counters are initialized for runtime state (`port-to-port/mini-rl-env.py:1973-1977`) but only emitted in summary when `rate_limit_retry_enabled` is true (`port-to-port/mini-rl-env.py:2669-2675`) and printed only when present (`port-to-port/mini-rl-env.py:2858-2860`). The telemetry functions themselves only mutate rate-limit counters and log (`port-to-port/mini-rl-env.py:519-547`). The blocking exhaustion issue is an indirect interaction with the empty/no-tool paths, not the telemetry writes themselves.

## Test Status

Ran:

```bash
port-to-port/.venv/bin/python -m unittest port-to-port/tests/test_rate_limit.py
```

Result: 3 tests passed. The pass is not sufficient for the sustained-exhaustion requirement because the real Pipecat pipeline path is not covered.
