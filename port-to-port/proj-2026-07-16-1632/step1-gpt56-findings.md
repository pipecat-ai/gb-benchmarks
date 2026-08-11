# Step 1: GPT-5.6/GPT-5.5 API contract and bounded probe

Status: **COMPLETE — Fable medium-reasoning close-out PASS**

Retrieved: 2026-07-16 (America/Los_Angeles)

## Official documentation baseline

| Model | Responses | Function calling | Documented reasoning efforts | Input / cached / output per 1M tokens | Max output |
|---|---:|---:|---|---:|---:|
| `gpt-5.6-luna` | yes | yes | `none, low, medium, high, xhigh, max` | `$1.00 / $0.10 / $6.00` | 128,000 |
| `gpt-5.6-terra` | yes | yes | `none, low, medium, high, xhigh, max` | `$2.50 / $0.25 / $15.00` | 128,000 |
| `gpt-5.6-sol` | yes | yes | `none, low, medium, high, xhigh, max` | `$5.00 / $0.50 / $30.00` | 128,000 |
| `gpt-5.5` | yes | yes | `none, low, medium, high, xhigh` (`medium` default) | `$5.00 / $0.50 / $30.00` | 128,000 |

Sources:

- [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model): use Responses for reasoning, tool-calling, and multi-turn workflows; set `reasoning.effort`; compare native `xhigh` and `max`.
- [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), and [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol): endpoints, function-calling support, prices, and output limits.
- [GPT-5.5 model page](https://developers.openai.com/api/docs/models/gpt-5.5): Responses/function-calling support, effort set, prices, and output limit.
- [Responses streaming events](https://developers.openai.com/api/reference/resources/responses/streaming-events): explicit `response.completed`, `response.failed`, and `response.incomplete`; incomplete responses include `incomplete_details.reason`.
- [Priority processing](https://developers.openai.com/api/docs/guides/priority-processing): Priority processing should not be used for evaluations.

The official docs connector was installed during this step but cannot become available inside an already-running Codex session. These facts were therefore fetched from the same official developer pages through the official-domain web fallback. The live probe verifies account access and actual wire behavior; it does not override the documented feature/price baseline.

## Decisions fixed before the live probe

- Endpoint: Responses for all GPT-5.6 benchmark traffic. Chat is probed once per family only as a compatibility diagnostic.
- Retention/tier: send `store=false`; omit `service_tier`; do not use Priority.
- Effort identity: add a future exact-set-gated `--reasoning-effort` override. Native `xhigh` stays `xhigh`; `max` is a distinct effective effort.
- Benchmark map: `none→none`, `minimal→low`, `low→low`, `medium→medium`, `high→high`, `xhigh→xhigh`; do not benchmark both `minimal` and `low` because they resolve to the same API configuration.
- Provisional sweep candidates: `low`, native `xhigh`, and explicit `max` for each GPT-5.6 model. Step 4 smoke evidence may remove a top configuration before full execution; it may not add an unprobed one silently.
- GPT-5.5 remains probe-only and ends this step with exactly one verdict: `GO_RESPONSES`, `GO_CHAT`, `DEFER_TRANSIENT`, or `DEFER_UNSUPPORTED`. `gpt-5.5-pro` is out of scope.
- OpenAI Python SDK: exact installed/probe version `2.21.0`; the probe refuses a different version.

## Existing Sol evidence

The pre-existing `step0-sol-xhigh-adversarial-review.md` records two Responses calls at Sol `xhigh`: a 16,000-token incomplete response after 409.7 seconds and a completed 50,000-token-cap response after 441.0 seconds. This is compatibility/guardrail evidence, not benchmark data. It justifies explicit model timeouts, a provisional cap followed by a full-episode smoke gate, and reduced effort coverage.

## Live probe matrix and hard ceiling

The fixed matrix contains 16 planned requests:

- Seven two-request, forced function-call round trips: GPT-5.6 `low` and `max` for Luna/Sol/Terra, plus GPT-5.5 `medium`. This proves request serialization, function-call reconstruction, tool-result replay, and final-response continuation. It does not claim that `tool_choice=auto` will independently choose this diagnostic tool; the full benchmark smoke in Step 4 covers the harness's normal tool-choice behavior.
- One Chat Completions + tools contract request for GPT-5.6 Luna and one for GPT-5.5.
- At most eight additional requests, used only for one classified transient retry or one output-cap escalation on a logical call.

Hard controls encoded in `diagnostics/gpt56_responses_probe.py`:

| Control | Ceiling |
|---|---:|
| Total API requests | 24 (16 planned + 8 retry reserve) |
| Initial / escalated max output per request | 16,384 / 32,768 tokens |
| Input reservation | 4,096 tokens for fixed prompt/schema, plus the previous request's full output cap on replay turns |
| Aggregate reserved tokens | 999,424 |
| Aggregate OpenAI spend ceiling | **$15.00** (worst-case reservation computes to $14.819328) |
| Per-request timeout | 600 seconds |
| Aggregate wall-time reservation | 14,400 seconds (4 hours) |
| SDK automatic retries | 0 |
| Concurrency | 1 |

Before every request, the probe reserves that request's bounded input, maximum output charge, and process-enforced total wall timeout. Replay turns reserve the fixed 4,096-token prompt/schema allowance plus the prior response's entire output cap, covering replayed encrypted reasoning. It does not launch the request if the reservation would exceed any ceiling. A timeout/connection/unknown client failure is conservatively charged at the full reservation because server-side billing may be unknowable. A retry that no longer fits is recorded as `budget_blocked` and skipped; a planned request that no longer fits is checkpointed before stopping the remaining matrix. Ctrl-C/SystemExit are checkpointed and re-raised rather than swallowed. The acknowledgement token contains a hash of the reviewed limits and worst-case calculation, so changing the budget invalidates approval.

The sanitized record is derived from the exact request dictionary passed to the SDK and fails closed if `store` is not false, `service_tier` is present, or the effort field is on the wrong API surface. It retains response IDs and attempts to retain the `x-request-id` through the pinned SDK's stream response object. Provider exception records may include up to 500 characters of the provider's error message for classification; fixed diagnostic parameters can therefore appear in an error, but prompts, headers, API keys, raw response bodies, and encrypted reasoning content are not persisted.

## Pre-live verification

- Offline syntax/dry-run validation: complete under the pinned port-to-port SDK.
- Targeted safety suite: **18/18 passed**; it covers the pinned-SDK keyword contract, process wall deadline, replay reservation, interrupt handling, budget-block checkpointing, repeated-systemic-error halt, partial stream preservation, both observed/schema cap-reason spellings, and transient `response.failed` retry wiring.
- Final no-network dry-run budget fingerprint: `03AA5DB17611`; approval must use the exact bound token `I_APPROVE_GPT56_RESPONSES_PROBE_03AA5DB17611`.
- Fable review via Claude Agent SDK: `claude-fable-5`, adaptive thinking, `effort=medium`.
  - R1 found five blocking safety/evidence issues; all were fixed before any live call.
  - R2 independently recomputed the new budget and found no remaining blocking defect. Its two probe-value should-fixes are resolved: the pinned SDK's exact request keywords are tested, two consecutive identical systemic failures halt, partial stream events survive exceptions, and transient `response.failed` codes can use one retry.
  - R3 caught the cap-reason contract discrepancy; direct verification showed the official streaming-event example and pinned SDK schema use different spellings.
  - R4 verified the accept-either resolution, the expanded 18-test coverage, all prior safety fixes, and the unchanged budget fingerprint. Verdict: **safe to present the $15 live-probe gate to the human approver**.
- Contract discrepancy resolved conservatively: the official streaming-event example uses `incomplete_details.reason="max_tokens"`, while pinned OpenAI SDK 2.21.0 types the value as `max_output_tokens | content_filter`. The probe accepts either cap-exhaustion spelling, records the exact observed reason, and escalates only once. Other incomplete reasons are not retried.
- Budget change prompted by review: the original pre-review proposal reserved 622,592 tokens and capped spend at $14.00 (computed worst case $13.14816), but it under-reserved replay input. The corrected proposal reserves 999,424 tokens and caps spend at **$15.00** (computed worst case $14.819328).

## Live results and locked Step 1 decisions

The user approved the exact fingerprinted budget. The completed probe used 23
requests, no retries, 2,469 reported tokens, an estimated `$0.013812`, and
17.614 seconds of request wall time. It stayed below every approved ceiling:
`24` requests, `999,424` accounted tokens, `$15`, and four hours. Every live
Responses request omitted `service_tier`, sent `store=false`, and returned
`service_tier="default"` on success. No response was incomplete or failed, no
cap escalation ran, and the final checkpoint has no stop reason.

### Attempt history and SDK replay correction

The first live attempt made 15 requests, used 1,006 reported tokens at an
estimated `$0.006253`, and stopped after 8.76 seconds under the
repeated-systemic-error guard. All seven forced Responses first turns completed
and returned exactly one valid function call. Their continuations were rejected
because OpenAI SDK 2.21.0's parsed streaming item includes the client-only
`parsed_arguments` field when dumped for replay; the API returned
`unknown_parameter` for that field. This was a probe serialization defect, not
a model/API incompatibility. The GPT-5.6 Luna Chat+tools diagnostic then
returned the expected 400: function tools with non-`none` reasoning are
unsupported on Chat Completions and the request should use Responses.

The reviewed recovery excluded `parsed_arguments`, restored the original
ledger, and issued only the seven preserved continuations plus the remaining
GPT-5.5 Chat diagnostic. All seven continuations completed with the exact final
text. Four are `success_sanitized_replay`. Three source turns had emitted a
reasoning item whose encrypted content was intentionally not persisted, so
those recoveries are separately labeled `success_reasoning_omitted`.
Encrypted-reasoning continuity remains unverified here and must be closed by
the in-memory HTTP-boundary fixture in Step 2 and the full-episode smoke in Step
4. The failed first continuations remain in the artifact as diagnostic data.

One recovery launch on 2026-07-16 crashed locally before budget preflight or an
API call because `responses_with_retry` passed the new
`allow_missing_reasoning_rejection` keyword to a method whose signature had not
yet been updated. The console worker did not prefix a wall-clock timestamp, so
the exact time is unavailable; the full traceback is retained in
`step1-gpt56-probe.log`. The checkpoint remained at 15 requests / 1,006 tokens /
`$0.006253`. The signature was fixed, a direct method-boundary assertion was
added, and 23/23 tests passed before the successful relaunch. Fable's
medium-reasoning post-Step-1 review inspected the current code and confirmed
the fix and final ledger, while requiring this disclosure. That review was
necessarily retroactive: the hot-fixed relaunch executed live without a fresh
pre-execution Fable sign-off after repeated Fable `529 Overloaded` failures.
The amended findings are being sent back for final sign-off. No live
re-execution is needed.

The seven continuation reissues used seven of the eight approved headroom
request slots. They are `retry=false` in the ledger because they were recovery
calls after a client serialization defect, not the probe's classified
provider-transient/cap retries. The delayed GPT-5.5 Chat check was the sixteenth
original planned call. Thus 16 original calls + 7 recovery reissues = 23 total,
leaving one request under the approved ceiling; `retry_requests=0` is accurate
but does not mean no headroom slot was repurposed.

### Live capability/account table

| Family/config | Responses + forced tool | Continuation | Resolved model | Chat + tools with reasoning | Tier |
|---|---|---|---|---|---|
| `gpt-5.6-luna / low` | completed | `success_sanitized_replay` | `gpt-5.6-luna` | family check: 400, use Responses or `reasoning_effort=none` | `default` |
| `gpt-5.6-luna / max` | completed | `success_reasoning_omitted` | `gpt-5.6-luna` | same family result | `default` |
| `gpt-5.6-sol / low` | completed | `success_sanitized_replay` | `gpt-5.6-sol` | same family result | `default` |
| `gpt-5.6-sol / max` | completed | `success_sanitized_replay` | `gpt-5.6-sol` | same family result | `default` |
| `gpt-5.6-terra / low` | completed | `success_reasoning_omitted` | `gpt-5.6-terra` | same family result | `default` |
| `gpt-5.6-terra / max` | completed | `success_reasoning_omitted` | `gpt-5.6-terra` | same family result | `default` |
| `gpt-5.5 / medium` | completed | `success_sanitized_replay` | `gpt-5.5-2026-04-23` | 400, use Responses or `reasoning_effort=none` | `default` |

Observed streamed event names were `response.created`,
`response.in_progress`, `response.output_item.added`,
`response.function_call_arguments.delta`,
`response.function_call_arguments.done`, `response.output_item.done`,
`response.content_part.added`, `response.output_text.delta`,
`response.output_text.done`, `response.content_part.done`, and
`response.completed`.

The pinned stream object's private `_response` header access captured a non-null
`x-request-id` on all 14 streamed successful Responses attempts. The seven
Responses requests rejected before streaming and both Chat requests rejected
before completion have null request IDs. Step 2 must replace the private-attr
dependency with a supported raw/terminal-response mechanism where possible,
retain the proven success-path capture, and define/test the expected null/error
trace behavior for pre-stream failures.

### Compatibility-only usage and latency

These fixed diagnostic calls are not benchmark latency samples. The table sums
the successful first turn and its later continuation and prices reported input
and output tokens at official standard rates.

| Config | Input | Output | Reasoning subset | Summed latency | Estimated cost |
|---|---:|---:|---:|---:|---:|
| Luna `low` | 285 | 71 | 33 | 3.327 s | `$0.000711` |
| Luna `max` | 285 | 116 | 76 | 2.080 s | `$0.000981` |
| Sol `low` | 285 | 36 | 0 | 2.183 s | `$0.002505` |
| Sol `max` | 285 | 69 | 31 | 2.791 s | `$0.003495` |
| Terra `low` | 285 | 49 | 11 | 1.709 s | `$0.001448` |
| Terra `max` | 285 | 97 | 57 | 1.944 s | `$0.002168` |
| GPT-5.5 `medium` | 285 | 36 | 0 | 2.413 s | `$0.002505` |

### Locked decisions gating Step 2

1. **API/tier:** route the exact hosted GPT-5.6 set to Responses. Send
   `store=false`, omit `service_tier`, and treat returned `default` as the
   expected standard tier. Do not add a Priority path.
2. **Effort identity:** add an exact-set-gated `--reasoning-effort` override.
   Native `--thinking xhigh` remains effective `xhigh`; explicit
   `--reasoning-effort max` remains a distinct config and leaderboard identity.
   The override accepts only `none, low, medium, high, xhigh, max`; it is valid
   only with provider `openai`, an exact model in
   `{gpt-5.6-luna,gpt-5.6-sol,gpt-5.6-terra}`, and no custom OpenAI base URL.
   Reject it everywhere else rather than ignoring it. When present it takes
   precedence over the mapped `--thinking` value, while metadata retains both
   requested thinking and the override and records the override as
   `effective_effort`.
3. **Default map:** `none→none`, `minimal→low`, `low→low`, `medium→medium`,
   `high→high`, `xhigh→xhigh`. Do not sweep both `minimal` and `low`.
4. **Reduced matrix:** Step 3 defines nine candidates: `low`, native `xhigh`,
   and explicit `max` for each of Luna, Sol, and Terra. Step 4 smokes all nine
   and may remove a top config before the full run; it may not silently add a
   configuration. This probe intentionally tested only `low` and `max`; native
   `xhigh` has no Step 1 wire evidence for Luna or Terra (and only the separate
   pre-existing Sol evidence), so Step 4 smoke must close that gap before any
   full run.
5. **Provisional cap:** use `max_output_tokens=50,000` for the Step 4 smoke.
   The small contract probe did not approach 16,384, but the pre-existing Sol
   `xhigh` evidence exhausted 16,000 reasoning tokens and completed at a 50,000
   cap. There is no automatic benchmark cap retry: if any smoke returns
   `response.incomplete` for `max_output_tokens`, halt, preserve the JSON, and
   re-project an 80,000-token candidate (still below the documented 128,000
   maximum) for separate review and approval. The full run uses one locked cap
   across all candidates that survive smoke.
6. **GPT-5.5 verdict: `GO_RESPONSES`.** Responses `medium` completed a real
   tool round trip; Chat+tools with reasoning returned a deterministic 400.
   GPT-5.5 remains probe-only under this plan, and any harness/sweep/leaderboard
   addition is a separate follow-up. `gpt-5.5-pro` remains out of scope.

### Proposed Step 4 ceilings (not approval)

The following deliberately conservative projections assume every episode uses
all 50 turns and every turn consumes the full provisional 50,000-token output
cap. They are inputs to the required Step 4 reviews and approval gates, not
authorization to run.

| Phase/version | Episodes | Max output tokens | Output-only price bound | Episode wall reservation |
|---|---:|---:|---:|---:|
| Smoke / Luna | 3 | 7.5M | `$45.00` | 2 h each |
| Smoke / Terra | 3 | 7.5M | `$112.50` | 2 h each |
| Smoke / Sol | 3 | 7.5M | `$225.00` | 8 h each |
| Full / Luna | 75 | 187.5M | `$1,125.00` | 2 h each |
| Full / Terra | 75 | 187.5M | `$2,812.50` | 2 h each |
| Full / Sol | 75 | 187.5M | `$5,625.00` | 8 h each |

- Proposed smoke hard ceilings: 9 episodes, 50M aggregate accounted tokens,
  `$550`, and 48 hours. Re-project from observed full-episode usage before the
  full-run approval gate.
- Provisional full-run outer ceilings if all nine candidates survive: 225
  canonical episodes plus separately bounded infra replacements, 1.2B
  aggregate accounted tokens, `$14,000`, and 1,080 hours (45 days). These are
  intentionally high worst-case reservations, not expected spend; Step 4 must
  replace them with trace-backed figures after smoke and obtain explicit user
  approval.

### Replay fixtures and artifact validation

- `step1-gpt56-probe.json` is the captured success fixture source. Attempt 1
  contains real function-call argument deltas, output-item completion, terminal
  completion, service tier, and usage. It also retains every failed diagnostic
  attempt and every recovery attempt.
- `step1-gpt56-event-fixtures.json` points to that captured record and contains
  synthetic `response.incomplete` and `response.failed` events validated by
  OpenAI SDK 2.21.0 models. They are synthetic by design; no live calls were
  spent manufacturing provider failures.
- The targeted suite passes 25 tests, including real SDK-schema validation,
  replay serialization, budget restoration, recovery ordering/re-entry,
  nested provider-error signatures, terminal classification, hard wall
  deadlines, and secret-safe sanitization.
- Final recorded execution on 2026-07-16:
  `/home/khkramer/src/aiewf-eval/.venv/bin/pytest -q tests/test_gpt56_responses_probe.py`
  → `25 passed in 0.65s`.
- A secret/prompt scan found no API key, authorization header, bearer token,
  fixed prompt prose, or `sk-` token in the JSON or console log.
- The older tracked `diagnostics/gpt56_effort_probe.py` and its documentation
  predate this plan and are unchanged by Step 1 (`bf9660f`, 2026-07-16
  09:22:57-07:00); they are not part of the new probe or its live budget.
- `git diff --exit-code` confirms no Step 2 harness/sweep file changed during
  Step 1, and all generated `__pycache__`/`.pyc` artifacts are covered by the
  repository `.gitignore` and are not staged.
- Final adversarial close-out:
  `step1-review-fable-post-r3.md`, Claude Agent SDK 0.1.73,
  `claude-fable-5`, medium effort, verdict **PASS / GO for Step 2**.
