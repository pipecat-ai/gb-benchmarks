# Step 2 — GPT-5.6 harness and Responses observability

Status: complete

Date: 2026-07-16

## Implemented contract

- The single shared `_is_gpt56_responses_model(model, openai_base_url)` decision is exact, normalized membership in `gpt-5.6-luna`, `gpt-5.6-sol`, or `gpt-5.6-terra`, with `openai_base_url is None`.
- All three exact hosted versions route to `OpenAIResponsesLLMService`. Near misses, aliases, snapshots, and custom base URLs do not take this route.
- The GPT-5.6 thinking branch precedes the generic GPT-5 Chat Completions branch and emits:
  - `reasoning={"effort": <effective effort>}`
  - `store=false`
  - `include=["reasoning.encrypted_content"]`
  - no top-level `reasoning_effort`
  - no `service_tier`
- Native `--thinking xhigh` remains effective effort `xhigh`. `--reasoning-effort max` is a distinct explicit override and identity. `minimal` maps to `low`; all other native labels map directly.
- `--reasoning-effort` is rejected outside the exact hosted GPT-5.6 set and when it redundantly equals the native thinking mapping. Priority (`service_tier`) is rejected for that set. Round IDs and positive timeout values are validated; the two model-latency timeout flags are rejected off the exact GPT-5.6 route rather than silently ignored.
- Added `--round-id`, `--reasoning-effort`, `--llm-request-timeout-secs`, and `--llm-stream-idle-timeout-secs`.
- Requested thinking, optional override, effective effort, round ID, and both timeouts propagate to config, summary, and metadata. `RUNNER_VERSION` is now `2026-07-16-gpt56-responses-v1`.

## Responses lifecycle and continuity

- For the exact GPT-5.6 route, one total provider-request deadline and one between-event stream-idle deadline are enforced. The provider request deadline ends before tool dispatch; tools remain governed by the existing function-call timeout. GPT-5.4 retains its legacy no-explicit-deadline service behavior.
- `response.completed`, `response.incomplete`, `response.failed`, and SDK `error`/legacy `response.error` events are explicit terminal outcomes. A stream with no terminal event is a protocol error.
- Per-inference traces contain only the required sanitized fields: API surface, requested/resolved model, requested effective effort and output cap, tools/store/service-tier presence, request/response IDs, returned tier, status, incomplete/error detail, event types, usage including cached/reasoning tokens, and timeout identity. Prompts, headers, keys, and raw encrypted reasoning are not persisted.
- With `store=false`, encrypted reasoning items are retained only in service memory and replayed immediately before their matching function call or assistant-text history item. SDK-only `parsed_arguments` is recursively removed before replay. Remember/replay text keys share one whitespace- and multipart-normalization function. Every remembered assistant text gets either its reasoning block or an explicit no-reasoning marker, so only an actually unmatched history item increments the sanitized miss counter and emits a prompt-free warning.
- Strict terminal observability and encrypted-reasoning replay are factory-scoped to the exact GPT-5.6 route. GPT-5.4 retains its legacy runtime path, request shape, immediate completed-event tool dispatch, and absence of benchmark traces/replay.
- Runtime terminal mapping is locked as follows:

| Provider outcome | Turn failure class | Terminal reason | Canonical interpretation for Step 3 |
|---|---|---|---|
| `response.completed` | normal tool/no-tool semantics | normal harness semantics | model result |
| `response.incomplete` | `response_incomplete` | `response_incomplete` | failed-with-JSON model result |
| `response.failed`/SDK `error` without a rate-limit code, 5xx, request timeout, idle timeout | `inference_failure` | `inference_error` | infra-ineligible |
| 429 surfaced after the OpenAI SDK's asserted default two retries, or a failed/error terminal with `rate_limit_exceeded`/`rate_limit_error` | `rate_limit_exhausted` | `rate_limit_exhausted` | infra-ineligible |

The runtime callback is attached before execution, traces are persisted at top-level `responses_traces`, and turns reference the matching trace index.

## Verification

OpenAI Python SDK: `2.21.0` (same version pinned by the Step 1 fixtures).

`tests/test_gpt56_harness.py` contains 23 offline tests covering:

- real-factory HTTP `MockTransport` boundary checks for luna, sol, and terra (`/v1/responses` only, exact serialized body), plus a real SDK `responses.stream` SSE round-trip that captures the HTTP request ID;
- exact route and override-rejection negatives;
- native-xhigh versus override-max identity serialization;
- config/summary/metadata propagation;
- encrypted reasoning replay and persistence exclusion, canonical multipart/whitespace matching, SDK-schema validation of assistant + `input_text`, and a sanitized replay-miss counter;
- replay of the captured Step 1 completed/function-delta/usage sequence;
- SDK-schema-validated incomplete and failed fixtures plus SDK error events;
- request and idle timeout injection, including proof that the request timeout does not cover tool execution;
- 429 and 503 fault injection and terminal classification;
- behavior snapshots for GPT-5.4 (including shared-service runtime scope, endpoint class, max-token mapping, and tool dispatch), GPT-5.2, GPT-5.1, GPT-4.1, a custom GPT-5.6 URL, and Google;
- the SDK client retry invariant (`openai.DEFAULT_MAX_RETRIES == client.max_retries == 2`), redundant override rejection, exact-route timeout validation, non-null tool strictness, and `include` on the production streaming request.

The assistant-history `input_text` shape is accepted by the OpenAI 2.21.0 `ResponseInputItemParam` schema and predates this change (commit `ed1545f`). Step 1 did not exercise it live, so Step 4 now explicitly requires one bounded live assistant-history continuation per version inside the separately approved smoke budget before any production sweep.

Verification results before adversarial review:

- GPT-5.6 Step 2 tests: 23/23 passed.
- Full non-probe unittest set (GPT-5.6 tests plus Baseten sweep, empty-retry, Gemma, Inkling, rate-limit, and regression suites): 151/151 passed after the round-2 note remediation.
- Python compilation and `git diff --check`: passed.
- The repository virtual environment does not contain pytest, so unittest discovery cannot import the pre-existing pytest-based Step 1 probe suite; that suite was already executed in Step 1 (25 passed) and was not changed in Step 2.

No live provider calls were made in Step 2.

## Fable remediation (round 1)

The first medium-reasoning Fable review (`step2-review-fable.md`) required changes. The implementation now:

1. uses one canonical normalization function for remembered and replayed assistant text and tests multipart/trailing-whitespace cases;
2. scopes strict lifecycle handling, explicit request/idle deadlines, traces, and encrypted replay to exact GPT-5.6 so GPT-5.4's shared-service behavior stays legacy-compatible;
3. drives the production streaming path through the real OpenAI SDK and `httpx.MockTransport`, including SSE parsing, serialized `stream=true`, tool dispatch, usage, and request-ID extraction;
4. asserts the SDK/client two-retry default before classifying a surfaced 429 as exhausted;
5. SDK-schema-validates assistant + `input_text` replay and adds the missing live validation to the separately approved Step 4 smoke gate.

## Fable remediation (round 2 notes)

The second medium-reasoning Fable review (`step2-review-fable-r2.md`) passed the step with notes. The remaining substantive notes are now closed:

- every remembered assistant text now carries either its exact reasoning block or an explicit no-reasoning marker, eliminating replay-miss false positives while preserving transformed-text misses;
- the terminal table now reflects rate-limit-coded `response.failed`/SDK error events;
- model-latency timeout flags are `None` off-route, resolve to 900/600 only for exact GPT-5.6, and are rejected if explicitly supplied elsewhere;
- the streaming boundary now asserts encrypted-content inclusion and non-null tool strictness; redundant same-wire effort overrides are rejected.

`run_inference` remains a non-benchmark diagnostic helper; production benchmark observability is attached to `_process_context`/`responses.stream`, which is covered by the real SDK SSE transport test.

The final scoped medium-reasoning review (`step2-review-fable-r3.md`) verified all note closures and concluded: "PASS — round-2 note closures are real and correctly tested; proceed to Step 3." Its only remaining low note is enforced as a Step 3 matrix assertion: no cross-config pair may share the same `(model, effective_effort)` wire identity.
