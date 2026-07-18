# Step 4 staged smoke run report

Status: **CORE SMOKE AND LUNA/TERRA PRODUCTION COMPLETE; 150/150 CANONICAL V3 RUNS**

Date: 2026-07-17

## Authorization and execution boundary

The user approved `step4-core-preflight-v3.md` exactly, limited to Luna and
Terra and to cumulative ceilings including v1 of 100,000,000 accounted tokens,
$500, and 50,000 seconds. Sol and production remained unauthorized.

All approval IDs and the diagnostic, config, runner, and implementation hashes
matched the approved values before key access or client construction. The
history gate and runner were then executed in the documented order. Hosted
OpenAI concurrency remained one. SDK retries were configured to zero. No
infrastructure replacement was launched, and there was no manual termination,
Sol call, production round, judging, or leaderboard mutation.

## V3 history gate: pass

All six planned Responses requests completed: three for Luna followed by three
for Terra. For each model, the diagnostic forced a tool call, losslessly
replayed its complete output group plus the tool result to exact assistant
text, then losslessly replayed the accumulated assistant history to the exact
confirmation. The completed artifact records encrypted reasoning, exact
function arguments and text assertions, `store=false`, tools present, no
requested service tier, returned tier `default`, complete usage, and status
`completed` for every call.

| Model | Requests | Returned tokens | Reasoning tokens | Elapsed |
|---|---:|---:|---:|---:|
| Luna | 3 | 607 | 77 | 4.002 s |
| Terra | 3 | 548 | 45 | 2.866 s |
| **Total** | **6** | **1,155** | **122** | **6.868 s request time** |

The durable authorization ledger charged the complete token and dollar
reservations: 4,257,344 accounted tokens and $19.081048. It charged 6.969
seconds of actual elapsed wall time rather than the 3,600-second planned wall
reservation. These are conservative authorization-accounting values, not
claimed invoice values.

## Benchmark attempt 1: Luna low pass

`gpt56-luna-low|smoke-core` completed successfully and was selected as the
first eligible canonical result. It used 30 turns, returned to the starting
sector, reached and recharged at a mega-port, made no bad action or no-tool
call, and terminated with `finished_tool`.

- 30 Responses traces and 30 unique response IDs;
- every status `completed`, with no incomplete reason or error;
- requested and resolved model `gpt-5.6-luna`, effective effort `low`;
- `store=false`, tools present, requested service tier absent, returned tier
  `default`;
- OpenAI SDK 2.21.0, `sdk_max_retries=0`, and replay-miss count zero;
- 296,557 input tokens, of which 270,315 were cached; 1,112 output tokens,
  including 295 reasoning tokens; 297,669 total/accounted tokens;
- $0.066506 estimated runner cost and 81 accounted wall seconds (79.414 seconds
  recorded by the episode).

The raw JSON and log hashes match the canonical manifest and runner state.

## Benchmark attempt 2: Luna xhigh infrastructure timeout

Luna xhigh made 13 healthy tool-calling turns. Turn 14 began at 21:45:01 PDT
but emitted no tool result. At 21:50:01 Pipecat's 300-second pipeline idle
watchdog cancelled the pipeline and recorded `failure=no_tool_call`. It fired
before the approved 600-second service stream-idle timeout and 900-second
request timeout could govern the request. Earlier project evidence included a
441-second silent xhigh reasoning call, so this watchdog mismatch was a
foreseeable configuration gap rather than a sufficient model-failure signal.

After cancellation, the process remained alive and silent until the episode's
approved outer timeout ended it at 7,200 seconds with exit 124. The artifacts
do not include a stack dump or other evidence that proves where shutdown was
blocked, so this report does not attribute the hang specifically to provider
stream teardown. A future offline fix must align the pipeline watchdog with
the reviewed service timeouts and make cancellation promptly terminate while
persisting a partial JSON artifact.

No raw JSON was written, so the runner classified the attempt
`exit_124_no_json`, made it ineligible, and preserved its console log. The
runner correctly charged the complete token and dollar reservation of
55,000,000 accounted tokens and $153.75, plus the actual 7,200-second wall
time; the preflight wall reservation had been 7,500 seconds. Usage for the 13
completed provider responses is not recoverable from a run JSON and is
therefore not guessed.

The loop's next reserve check was for a same-config Luna-xhigh infrastructure
replacement. Its 55,000,000-token reservation would have raised runner
accounting to 110,297,669 tokens, which is not strictly below the
94,629,520-token ceiling. The budget check runs before the smoke phase's
no-replacement check, so the attempted reservation was rejected with rc 3 and
no replacement state or API call was created. Had the budget check fit, the
smoke no-replacement rule would have halted the config without launching it.

The runner emitted `RUNNER_STOP ... reason=budget`, then its incomplete summary
exited 4 because only one of six expected canonical results existed. It never
advanced to Luna max or any of the three Terra benchmark episodes. The token
ceiling was binding; the dollar and wall ceilings still had headroom. Because
one no-JSON attempt consumes 55 million accounted tokens, this package could
not continue after such a failure under its 94.6-million-token runner ceiling.
That brittleness was safe but must be explicit in any replacement package.

## V4 Luna xhigh timeout-validation smoke: pass

After offline remediation and Fable's medium-reasoning `CLEAN` preflight
review, the user approved `step4-luna-xhigh-preflight-v4.md` exactly: one Luna
xhigh episode, no second attempt, and cumulative ceilings of 116,000,000
accounted tokens, $330, and 15,000 seconds including v1/v3. Terra, Sol, and
production remained unauthorized.

The approval-bound hashes matched immediately before execution. The runner
created exactly one `RUN_START` and one matching `RUN_EXIT`, both for
`gpt56-luna-xhigh|smoke-luna-xhigh-v4`; no other model, effort, or phase was
started. The attempt completed with rc 0 and was selected as the first eligible
canonical result. It used 36 turns, returned to the starting sector, recharged
to full at the nearest mega-port, traded at three distinct ports, made no bad
action or no-tool call, and terminated with `finished_tool`.

- 36 Responses traces and 36 unique request and response IDs;
- every status `completed`, with no incomplete reason or error;
- requested and resolved model `gpt-5.6-luna`, effective effort `xhigh`;
- `store=false`, tools present, requested service tier absent, returned tier
  `default`;
- OpenAI SDK 2.21.0, `sdk_max_retries=0`, and replay-miss count zero;
- 477,034 input tokens, of which 440,445 were cached; 4,113 output tokens,
  including 3,084 reasoning tokens; 481,147 total/accounted tokens;
- $0.114459 estimated runner cost and 110 accounted wall seconds (108.630
  seconds recorded by the episode).

Trace 31 had a prompt-cache miss (`cached_tokens=0` on 17,683 input tokens).
The episode cost remains internally consistent and conservative, but future
full-run projections must not assume uninterrupted prompt-cache continuity.

The live configuration recorded the intended 600-second Responses stream-idle
timeout, 900-second request timeout, and 930-second pipeline fallback. An
atomic partial checkpoint landed after every turn. The final atomic write
removed the checkpoint marker and retained 36 inference inputs, turns, and
Responses traces. Raw JSON/log hashes match the runner state and canonical
manifest.

This successful episode did not stall, so none of the three timeout controls
fired. It validates that the timeout remediation does not regress a complete
Luna-xhigh run and that partial-to-final checkpoint replacement works on the
normal path. The offline real-pipeline stalled-stream test remains the direct
evidence for timeout ordering and partial persistence; this live result alone
does not prove provider-first timeout behavior under a new stall.

## V5 core-remainder smoke: four canonical artifacts, one lexical false negative

After the cross-phase ledger and exact four-row package passed two Fable
medium preflight reviews, the user approved
`step4-core-remainder-preflight-v5.md` exactly. The approval allowed one Luna
max episode followed by Terra low, native xhigh, and explicit max, with no
replacement. Its cumulative ceilings were 121,000,000 accounted tokens, $600,
and 16,000 seconds including v1/v3/v4. Sol, production, judging, leaderboard
mutation, recovery, and reruns remained unauthorized.

The worker emitted the positive `APPROVAL_HASH_OK` marker before its first
`RUN_START`. It then emitted exactly four sequential `RUN_START`/`RUN_EXIT`
pairs in the approved order and no fifth attempt. State finished with no
inflight reservation, four selected first-eligible canonical artifacts, no
replacement, no halted config, and aggregate totals below every ceiling.

| Config | Raw result | Turns | Input | Cached | Output | Reasoning | Accounted | Est. cost | Wall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Luna max | pass | 38 | 638,211 | 614,261 | 9,279 | 8,168 | 647,490 | $0.147038 | 156 s |
| Terra low | pass | 29 | 290,436 | 262,699 | 1,190 | 462 | 291,626 | $0.170203 | 80 s |
| Terra xhigh | pass | 33 | 382,281 | 365,402 | 3,866 | 2,904 | 386,147 | $0.202087 | 112 s |
| Terra max | fail: report heuristic | 35 | 438,635 | 420,146 | 4,865 | 3,867 | 443,500 | $0.235790 | 125 s |
| **V5 total** | **3 pass / 1 raw fail** | **135** | **1,749,563** | **1,662,508** | **19,200** | **15,401** | **1,768,763** | **$0.755117** | **473 s** |

Every one of the 135 turns has exactly one inference input and one sanitized
Responses trace. All 135 traces have unique request and response IDs, status
`completed`, no incomplete reason or error, exact requested/resolved model and
effective effort, `store=false`, tools present, omitted requested service
tier, returned tier `default`, OpenAI SDK 2.21.0, zero SDK retries, and zero
reasoning-replay misses. Per-trace usage is internally consistent and sums
exactly to the state and manifest. Every final atomic JSON replaced its partial
checkpoint and contains no checkpoint marker; the raw hashes match state and
manifest.

No output-cap or latency gate fired. The largest single response used 3,791
output tokens against the 50,000-token cap. Across the four rows, the largest
input was 23,839 tokens, episode duration was at most 153.974 seconds, and
decision-time P50 ranged from 1.226 to 1.674 seconds. Cache continuity was not
assumed: six first-or-later traces had zero cached input across the four
episodes, while the cost calculation used returned cache data trace by trace.
The successful live runs did not exercise the timeout chain, so the prior
offline stalled-stream test remains its direct validation.

Terra max completed the actual task: it returned to sector 3080, recharged 33
warp for 66 credits at MEGA SSS, traded at four distinct ports, emptied cargo,
and correctly reported the on-hand change from 16,564 to 18,568 as +2,004.
The raw run nevertheless has `success=false`, `coherent_report=false`, and
rc 1. The cause is lexical: the frozen coherence predicate accepted `profit`,
`net change`, `net result`, and several `overall` forms, but not the report's
semantically equivalent phrase `Net on-hand credits increased`. Per the
first-eligible policy this failed-with-JSON model result remains canonical and
was not rerun or rewritten.

The live and evaluation paths now use one shared predicate that accepts the
narrow phrase `net on-hand`, with a regression test for each caller and an
identity assertion preventing copy drift. The full non-probe suite passes 190
tests, including both new cases, and `git diff --check` passes. This offline
remediation does not mutate the v5 raw artifact: its raw summary remains
`success=false` and `coherent_report=false`. Judging remains deferred because
it was explicitly outside the v5 authorization.

The downstream effect is explicit and requires approval: `evaluate_runs.py`
recomputes a false raw coherence value from the finished message, so Step 5
will classify this exact immutable Terra-max artifact as
`coherent_report=true` and `lenient_success=true`. That post-observation policy
correction aligns the lexical check with the already-semantic report-judge
contract, but it must be accepted on the record in the production/Step 5
package rather than presented as if the raw verdict changed. The Step 5 legacy
byte-identity baseline must also test whether any pre-existing run uses the new
phrase; if it changes legacy output, the difference must be isolated and
reviewed instead of silently waived.

The correction changes the live harness after the smoke-validated v5
implementation hash. Any production or optional Sol package must bind a new
implementation hash and enumerate the delta as the shared-predicate extraction
plus the one `net on-hand` outcome marker. Consequently, the six smoke raw
artifacts retain their old raw scoring, while future live episodes use the
corrected predicate. This is a monotone fail-to-pass expansion aligned with the
semantic report contract, but the raw-scoring asymmetry is part of the approval
record and must not be hidden by downstream enrichment.

Fable's first medium post-run review independently checked the exact four-run
scope, order, 135 trace/turn/input triplets, ledger arithmetic, first-eligible
selection, raw Terra-max preservation and diagnosis, and absence of Sol,
production, judge, or leaderboard actions. It found no blocker and raised the
three disclosures/hardening items closed above. A focused medium closure review
verified the shared implementation, evaluation/raw distinction, legacy
byte-baseline declaration, and restoration of the immutable approved preflight,
and found no blocker to preparing a separately reviewed production package.
The two reviews cost $0.86236850 and $0.38244215 through the Claude Agents SDK;
those review costs are separate from OpenAI benchmark accounting.

## Core production v1: failed closed before the first canonical slot

The user approved `step4-core-production-preflight-v1.md` exactly: 25 rounds
each for Luna low/xhigh/max and Terra low/xhigh/max in round-robin order, with
cumulative ceilings of 200,000,000 accounted tokens, $650, and 38,000 seconds,
and at most 160 package attempts. Sol, judging, leaderboard mutation, manual
reruns, and resume/recovery launches remained unauthorized.

Immediately before execution, the phase/config/runner/implementation/baseline
ledger hashes matched the approved values, the production state, manifest, and
worker log did not exist, the cross-process lock was available, and all
baseline-ledger evidence hashes matched. The worker then launched the approved
no-resume phase in a live PTY and remained sequential on hosted OpenAI.

Only two attempts were launched, both for the first planned slot,
`gpt56-luna-low|r01`:

| Attempt | Completed provider requests | Observed action | Terminal result | Persisted returned tokens | Authorization accounting |
|---|---:|---|---|---:|---:|
| a001 | 1 | Three parallel `list_known_ports` calls | `inference_error`; traces `completed,replay_error` | 6,397 | 55,000,000 tokens / $153.75 / 5 s |
| a002 | 2 | `load_game_info`, then seven parallel `list_known_ports` calls | `inference_error`; traces `completed,completed,replay_error` | 13,931 | 55,000,000 tokens / $153.75 / 7 s |

In both attempts, every actual provider response completed. The next inference
failed locally during request construction with `Provider output could not be
replayed losslessly; request not sent`; therefore the `replay_error` traces
have no provider request ID or usage. The runner conservatively charged the
full token and dollar reservation for each failed attempt instead of inferring
usage from the completed subset. The 20,328 persisted returned tokens are
reported separately and do not replace authorization accounting.

After a002, a third 55,000,000-token reservation would have raised aggregate
accounting to 227,875,403, which is not strictly below the approved
200,000,000-token ceiling. The pre-launch budget gate rejected it with rc 3 and
emitted `RUNNER_STOP ... reason=budget`; no third state row, key-backed client,
or provider request was created. The final phase result is 0/150 canonical
slots, two attempts, no inflight reservation, and an incomplete manifest. The
two structurally different trace sequences produced different error-signature
hashes, so the identical-signature halt did not fire; the aggregate token gate
was independently sufficient to stop the package.

No Terra or Sol call was made. No judging, derivative creation, leaderboard
mutation, manual rerun, resume, or recovery was attempted. The approved
preflight is retained unchanged, and all raw JSON/log artifacts remain
immutable.

### Offline diagnosis and remediation

The remembered Responses output was correctly retained as one complete group,
including all parallel function-call items and encrypted reasoning. Pipecat,
however, serialized one multi-call provider response into multiple assistant
messages, one function call per message, interleaved with tool outputs and
asynchronously delivered game events. The lossless replay matcher required one
assistant message to contain the complete provider group's ordered call-ID
tuple, so it could not match either observed multi-call history shape. The
earlier smoke happened not to exercise this serialization shape.

The offline matcher now associates each chronological provider group with one
or more assistant-message fragments while allowing non-assistant tool/event
messages between them. It requires the exact call-ID set and exact aggregated
assistant text, tolerates parallel calls completing in a different order,
replays the provider-owned items once at the first fragment, suppresses later
assistant duplicates, and retains the observed tool/event ordering. Unknown or
partial groups still fail closed before a request is sent. A regression fixture
reproduces the split/interleaved shape with reversed completion order. After
the first Fable post-run review, strict reasoning-only, text-fragment,
partial/duplicate/empty-fragment, and matched-group-plus-orphan cases expanded
the passing GPT-5.6 harness module from 31 to 35 tests; the complete non-probe
suite now passes 200 tests. This is offline evidence only, not live validation,
and it confers no recovery or successor-run authority.

Fable's first medium post-production review independently recomputed every
scope and accounting claim and verified the root-cause diagnosis. It required
the successor to pin full-reservation treatment, halt local replay defects
after one attempt, close reasoning-only/orphan replay gaps, make successor
headroom explicit, and hash-bind the approval document. The v6 implementation
and one-attempt preflight close those findings. A second medium review found
one missing direct orphan-branch test plus low-severity disclosures; those were
added. The focused closure review then verified all findings in code/tests or
accurate disclosure and returned `VERDICT: CLEAN`.

The resulting `smoke-parallel-replay-v6` package contains exactly one
Luna-low episode, no replacement, a cumulative hash/evidence-bound baseline of
172,875,403 tokens / $484.020130225 / 7,884.506 seconds, and strictly bounded
ceilings of 230,000,000 tokens / $650 / 16,000 seconds. It requires the exact
preflight SHA-256 from the user's approval record before state creation or key
extraction. The three successful Fable reviews cost $2.52179420 through the
Claude Agents SDK, separate from benchmark accounting. One intervening SDK
session failed without producing a review artifact or result-cost record.

## V6 parallel-replay validation: clean run, inconclusive validation

The user approved `step4-parallel-replay-preflight-v6.md` at SHA-256
`3515a408ee75da19bd06bd98ec66a8c8200586bfbebe6259f092fe4044baa70a`,
limited to one Luna-low episode and no replacement, with cumulative ceilings
of 230,000,000 accounted tokens, $650, and 16,000 seconds and a package maximum
of one attempt. Terra, Sol, production, judging, leaderboard mutation, manual
reruns, resume, recovery, and any second attempt remained unauthorized.

Immediately before execution, the approved preflight, baseline ledger,
phase/config, runner, and implementation hashes matched; the dedicated state,
manifest, and worker log did not exist; and the hosted-OpenAI lock was
available. The worker emitted the positive `APPROVAL_HASH_OK` marker, exactly
one `RUN_START`, and exactly one matching `RUN_EXIT`. It launched no other
model, effort, phase, or attempt.

The Luna-low episode completed successfully with rc 0 in 28 turns and
terminated with `finished_tool`. It returned to sector 3080, recharged 33 warp
units at MEGA SSS for 66 credits, traded at one distinct port, and reported a
264-credit profit after recharge. It recorded one bad action at turn 19 when a
non-adjacent `move` was rejected; the model recovered on the next turn and did
not record a second bad action. Its immutable final artifact contains 28
inference inputs, 28 turns, and 28 Responses traces with matching contiguous
indices. Every trace is `completed`, has complete internally consistent usage,
uses the Responses API with `store=false` and tools present, omits requested
service tier, records OpenAI SDK 2.21.0 and zero SDK retries, has a unique
request and response ID, and has zero reasoning-replay misses and no error.
The final JSON contains no partial-checkpoint marker, and its JSON/log hashes
match runner state and manifest.

Measured usage was 276,198 input tokens, including 249,573 cached tokens,
plus 1,062 output tokens, including 380 reasoning tokens: 277,260 total
accounted tokens. Runner-estimated cost was $0.064610550 and accounted wall
time was 70 seconds. The state correctly records
`accounting_basis=measured_complete_trace_usage`; no reservation charge was
retained because every transmitted request had complete usage.

The validation is nevertheless **inconclusive** under the approved go/no-go
contract. Every turn contained exactly one tool call: the raw summary records
`multi_call_turn_count=0` and `max_tool_calls_per_turn=1`. Consequently there
is no multi-call turn and no later completed trace that can prove the fixed
split/interleaved parallel-output group was reconstructed and transmitted.
Task success and clean sequential replay satisfy the ordinary run contract but
do not substitute for the two required parallel-replay predicates. Production
therefore remains no-go. The package permits no automatic or manual rerun, and
none was launched.

## V7 deterministic continuation validation: inconclusive after request 1

Because v6 relied on an ordinary benchmark policy to emit parallel calls, its
clean single-call-only result could not validate the repair. The offline v7
package instead permits at most two sequential Luna-low Responses requests.
The first explicitly asks for one live provider output group containing three
independent calls. Only if that exact gate passes does the production matcher
retain the complete output, represent it as `3,1,2` split assistant fragments
with tool/event messages interleaved, require exactly-once reconstruction and
zero replay misses, validate the reconstructed input against the installed SDK
schema, and send one continuation. A go result means the matcher passed at
launch time and the provider accepted the reconstructed live
encrypted-reasoning/tool input; it is not production authority.

Forced function choice does not guarantee three calls. A one- or two-call
response is a plausible safe inconclusive outcome that exhausts v7 after its
first request; the probability is unknown and no retry is authorized. The
diagnostic intentionally exercises the exact production matcher but not the
full game/Pipecat pipeline, whose fragment shape is covered by the immutable
production-v1 history and offline regression fixtures.

The user explicitly confirmed the exact approval block for
`step4-parallel-replay-continuation-preflight-v7.md` at SHA-256
`cbd040735ef295462ca055153ae857fcb4f6d81962c397db0dba72c83975c9ee`,
limited to the documented at-most-two-request Luna-low state machine, no retry
or replacement, and cumulative ceilings of 174,000,000 accounted tokens,
$486, and 9,500 seconds. Terra, Sol, benchmark production, judging,
leaderboard mutation, manual reruns, resume, recovery, a third request, and
every follow-up action remained unauthorized. The user also waived all
further Fable reviews.

Immediately before execution, the preflight, baseline ledger, script,
expanded implementation, and config hashes matched the approved values;
OpenAI SDK 2.21.0 was installed; the dedicated JSON and worker log were absent;
and the hosted-OpenAI lock was available. The live validator printed the
positive `APPROVAL_HASH_OK` marker and sent request 1 only.

Request 1 returned `completed` in 1.556 seconds with one function-call output
item, no assistant text, complete internally consistent usage, resolved model
`gpt-5.6-luna`, returned service tier `default`, and unique request/response
IDs. It used 143 input plus 24 output tokens, with zero cached and zero
reasoning tokens, for 167 total. Although the request included
`reasoning.encrypted_content`, the response contained no encrypted reasoning
item. The first gate therefore failed closed as `INCONCLUSIVE`,
`replay_validation_go=false`, with process rc 4. The validator did not build
or transmit reconstructed history, did not send request 2, and did not retry.
The completed artifact has `replay_evidence=null` and records measured usage
rather than the request reservation.

The package baseline was the unchanged actual cumulative accounting after v6:
173,152,663 tokens / $484.084740775 / 7,954.506 seconds, 254 physical requests,
and 2,846,386 known returned tokens. Two full reservations project to
173,560,855 tokens / $484.633892775 / 9,154.506 seconds under proposed ceilings
of 174,000,000 tokens / $486 / 9,500 seconds. Each request is bounded at a
200,000-token input reservation, 4,096 output tokens, $0.274576, and 600
seconds; the package also rejects any serialized request over 100,000 bytes.
Complete usage replaces a reservation with measured accounting; otherwise the
full reservation remains. Remaining headroom cannot fund a retry or third
request.

The diagnostic and package passed 9 dedicated, 79 focused, and 209 complete
non-probe tests plus compile and diff checks. Fable's first medium review found
no blocker and independently recomputed the budget, ledger, crash/no-resume,
lock, key, privacy, and request-cap contracts. Its findings narrowed the live
claim to provider acceptance, made the possible inconclusive outcome explicit,
renamed the artifact flag to `replay_validation_go`, hardened quoted-key
parsing, added a direct negative matcher test, and treated matching group
digests as corroboration rather than a redundant independent gate. A focused
closure passed, and a final wording review returned `VERDICT: CLEAN`. The three
successful SDK reviews report $2.31540750 in model cost, separate from OpenAI
benchmark accounting; earlier depleted-key startup failures returned no review
content and reported zero cost.

The final immutable preflight is
`step4-parallel-replay-continuation-preflight-v7.md` at SHA-256
`cbd040735ef295462ca055153ae857fcb4f6d81962c397db0dba72c83975c9ee`.
V7 is exhausted. Its JSON and worker log hashes are recorded below; no second
request, rerun, replacement, or follow-up action was launched.

## V8 production-input replay validation: local pre-request failure

V8 reuses the immutable messages and 30 tool definitions from inference 0 of
production-v1 attempt `gpt56-luna-low-r01-a001`. That exact source input
previously produced a completed output group with 49 reasoning tokens and
three parallel `list_known_ports` calls, so it is a stronger live-shape source
than v7's synthetic forced-tool prompt. V8 does not rerun the game or execute
any returned game tool. It sends at most one direct Luna-low source-input
request, synthesizes tool outputs in memory only if the response contains
encrypted reasoning plus 2-16 valid calls, and sends at most one reconstructed
continuation. No retry, replacement, or third request exists.

The baseline includes measured v7 accounting: 173,152,830 tokens /
$484.085063525 / 7,956.062 seconds, 255 physical requests, and 2,846,553 known
returned tokens. Two full reservations project to 173,361,022 tokens /
$484.384215525 / 9,156.062 seconds under proposed ceilings of 173,500,000
tokens / $485 / 9,500 seconds. Each request reserves 100,000 input plus 4,096
output tokens, $0.149576, and 600 seconds, with a 100,000-byte serialized
request cap.

The successor passes 17 dedicated, 96 focused GPT-5.6, and 226 complete
non-probe tests. Its production tool conversion is equal to the bound service;
the state-machine tests prove two requests only on GO, one request on an
inconclusive first gate, and one request plus NO-GO on matcher rejection.
Per the user's direction, no Fable review was requested.

The user approved the final preflight
`step4-production-input-replay-preflight-v8.md` at SHA-256
`2cada023ceb95bca630bfd6c4b28c043102cf55b8d250a308b9339bd23e5d841`.
All approval hashes passed and the validator constructed a key-backed client,
but it failed before `REQUEST_START` with a content-free
`ModuleNotFoundError`. Direct-script execution puts `diagnostics/`, not the
repository root, first on `sys.path`; the late root-level
`openai_responses_service` import therefore failed. Module-based unit tests had
the repository root on `sys.path` and missed the entrypoint-specific defect.

V8 wrote a complete terminal `NO_GO` artifact with an empty `records` array,
zero phase requests, tokens, dollars, and wall time, unchanged aggregate
accounting, `replay_evidence=null`, and `replay_validation_go=false`. No
provider request or game tool was executed. V8 is exhausted and was not
rerun. A successor must validate the production matcher and complete first
request from the exact direct-script entrypoint during dry-run and before key
access.

## July 17 service correction: v9 superseded without launch

The incremental v6-v9 validation ladder was based on a mistaken architecture:
the benchmark retained encrypted provider output and attempted to match it
back to Pipecat's split assistant history. That layer was not used by the
proven `../aiewf-eval` GPT-5.6 integration and caused both production-v1
attempts to fail locally after otherwise completed provider responses.

V9 was never launched. Its preflight, ledger, diagnostic, and tests remain as
historical audit material, but the diagnostic is not a next action. The active
service now follows the aiewf application-level contract: construct each
continuation from standard assistant `function_call` items and
`function_call_output` items, do not request or retain encrypted reasoning,
and dispatch all function calls from a completed response as one batch.

The benchmark-specific safeguards remain: exact GPT-5.6 routing, `store=false`,
omitted service tier, zero SDK retries, request and stream-idle deadlines,
explicit completed/incomplete/failed handling, sanitized request/response and
usage traces, and outer accounting callbacks. Active offline tests cover all
three model routes, real `/v1/responses` serialization, parallel calls with
out-of-order tool results, continuation reconstruction, terminal outcomes,
timeouts, and legacy-provider non-interference. Historical matcher validators
are explicitly skipped rather than treated as current service requirements.

The full non-probe offline suite discovered 234 tests: all 182 active tests
passed and 52 historical replay-validator tests were skipped. An additional
read-only reconstruction of production-v1 attempt
`gpt56-luna-low-r01-a001` inference 1 converted its exact 13 recorded provider
messages to 13 SDK-valid Responses input items, including all three function
calls and all three function outputs, with zero reasoning items. The focused
sweep config and exact CLI dry-run passed, and v9 live mode now refuses before
key access with an explicit retired-path error.

Per the user's direction, engineering fixes and bounded validation no longer
create incremental approval or Fable-review steps.

## Core production v3: 150/150 canonical slots complete

The standing core scope ran 25 round-robin rounds each for Luna and Terra at
low, native xhigh, and explicit max. Production v3 produced 150 attempts and
selected all 150 as the first eligible result for their `(config, round_id)`
slot. There were no infrastructure replacements and no halted configurations.
Terminal reasons were 145 `finished_tool` and five `max_turns_exhausted`; all
150 retained complete raw JSON and were classified as eligible model results.

The main worker completed attempts 1–149 and then failed closed before the last
Terra-max row: its fixed 7,500-second reservation projected 38,050.062 seconds,
50.062 above the 38,000-second ceiling. Actual aggregate use was 30,550.062
seconds. The final run kept the exact 7,200-second outer execution timeout and
reserved that timeout, projecting 37,750.062 seconds under the unchanged
ceiling. It completed in 353 seconds. This completed the already-authorized
150-slot matrix without expanding scope or any ceiling.

Reconciliation against the final state and manifest passed. Every recorded raw
JSON/log exists and matches its SHA-256; every config has 25 canonical rounds;
every round has six configs; all 150 run IDs are unique. Across 5,237 Responses
traces, all response IDs are unique, every response status is `completed`, no
trace has an incomplete reason or error, request and resolved models/efforts
match, tools are present, `store=false`, requested service tier is absent,
complete usage is recorded, and SDK retries are zero.

## Cumulative accounting

| Work | Accounted tokens | Accounted USD | Accounted wall |
|---|---:|---:|---:|
| Prior v1 checkpoint | 1,070,480 | $2.753000 | 1.537 s |
| V3 history gate | 4,257,344 | $19.081048 | 6.969 s |
| V3 runner | 55,297,669 | $153.816506 | 7,281.000 s |
| V4 Luna xhigh | 481,147 | $0.114459 | 110.000 s |
| V5 core remainder | 1,768,763 | $0.755117 | 473.000 s |
| Production v1 completed provider usage | 20,328 | $0.020981 | 12.000 s |
| V6 Luna-low validation | 277,260 | $0.064611 | 70.000 s |
| V7 deterministic continuation | 167 | $0.000323 | 1.556 s |
| V8 pre-request local failure | 0 | $0.000000 | 0.000 s |
| **Operational baseline** | **63,173,158** | **$176.606045** | **7,956.062 s** |
| Production v3 (150 attempts) | 58,820,724 | $30.538874 | 22,947.000 s |
| **Final aggregate through Step 4** | **121,993,882** | **$207.144919** | **30,903.062 s** |
| **Standing production ceiling** | **200,000,000** | **$650.000000** | **38,000.000 s** |
| **Remaining ceiling headroom** | **78,006,118** | **$442.855081** | **7,096.938 s** |

The earlier conservative ledger charged both production-v1 local replay
failures their full 55-million-token/$153.75 reservations even though the raw
artifacts contain complete usage for every physical request. The operational
baseline releases those reservations and accounts the observed three provider
requests: 20,328 tokens and $0.02098145. The evidence-bound rebase is in
`step4-authorization-ledger-production-core-v2.json`; the original artifacts
and prior ledger remain unchanged. This is an accounting correction, not new
budget or scope.

V5's complete returned usage has an estimated benchmark cost of $0.755117.
Known persisted returned usage is 2,846,553 tokens: the prior 2,569,126 plus
277,260 returned by the 28 completed v6 provider requests and 167 returned by
the sole v7 request. Usage and invoice treatment for the timed-out v3
Luna-xhigh request remain unknown. Two hundred fifty-five physical API
requests were started: the prior 226 plus 28 v6 requests and one v7 request.
The known-returned-token total includes cached input tokens and is not a
billed-token-equivalent metric.
The much larger cumulative authorization-accounting total retains full
reservations for attempts whose complete provider usage is unavailable.

The v5 runner closed the v4 carry-forwards: it validated an immutable
hash/evidence-bound ledger for v1/v3/v4 before key extraction, imported the
baseline into durable state, applied every next-run reservation against the
aggregate ceilings, and logged a positive approval-hash marker. Because all
four v5 artifacts had complete consistent usage, their reservations were
released to measured accounting before the next distinct row was considered.

## Verdict and next boundary

The remediated complete-output history contract and the Responses request,
identity, trace, retry, usage, checkpoint, cap-presence, and standard-tier
contracts are live-validated for Luna and Terra at all six planned core
efforts. The core production matrix is complete at 25 canonical rounds per
config. Neither smoke nor production validates near-cap or cap-driven
`response.incomplete` behavior; every response was far below the cap.

The observed watchdog and partial-artifact defects are remediated, and every
core config has a complete smoke artifact. The Terra-max coherence false
negative is understood and fixed offline without changing its raw result.
Production v1 remains preserved at 0/150 with both failed attempts and their
raw usage evidence intact. Production v2 then stopped before any provider
request because its first artifact name collided with v1. V3 uses a
phase-qualified artifact namespace; its 53-test focused suite, exact 150-row
dry-run, shell checks, and compile checks passed before launch.

The response-group matcher is not being repaired or live-validated further;
it has been removed. The relevant continuation contract is the one already
used successfully by aiewf-eval. V6-v9 remain historical evidence of the
discarded approach, and v9 must not be launched. Step 4 continues from the
aiewf-compatible service after offline verification. Normal fixes and bounded
validation within the task do not require fresh approval or Fable review.
Sol was left unrun as the optional last stage. Step 4 is complete. Judging,
derivative creation, and leaderboard mutation remain approval-gated Step 5
work rather than part of this run.

## Artifacts

| Artifact | SHA-256 |
|---|---|
| `step4-assistant-history-core-smoke-v3.json` | `9267233b8ef80661512f0ef5ac63ee3f36f11e4c21a96ef5055bd122da3a3b75` |
| `step4-assistant-history-core-smoke-v3.log` | `5976af2fec7bb1db077351f8db6c21293dcfe28c8467c10a3e01c00a89ef207a` |
| `step4-core-smoke-runner-state.json` | `0b6591b8b20a9fbbb44aac17e4e25514629bf3161dd0efe281e56fb68be93441` |
| `core-smoke-manifest.json` | `9476befc1abccfa42b4eebbbd12775cefc7002722a43789f9c1e1bc98eed4e3f` |
| `step4-core-smoke-worker-v3.log` | `7109493efecfe0161728b4b2877a04203dee0ebc144dbb704c47b33933949999` |
| `gpt56-luna-low-smoke-core-a001.json` | `79d02e679516418d5dacd03a8aa402f252af11e3f6b3140f7963ada455e69106` |
| `gpt56-luna-low-smoke-core-a001.log` | `510fb4a452dd87e18e91d473a7b15a9c15b1c3eae65711836aafb94350df0c7b` |
| `gpt56-luna-xhigh-smoke-core-a002.log` | `c612cdee7fd9900baac146428d208dae23b44b10922ff243dad84ab6c9956d7b` |
| `step4-luna-xhigh-v4-runner-state.json` | `aa4241287f3fabe41c8be9042bde216588e9150c7a5c60e92f015c9245e7d0c1` |
| `luna-xhigh-v4-manifest.json` | `b9951dbc56aad7d260eecd90c6d7881d3e285d2506a79d932262139907be4685` |
| `step4-luna-xhigh-worker-v4.log` | `a9b4fa4c4fae833859bf8db7560e00333add72c8913935d4aaa5ca1c0ee4aafd` |
| `gpt56-luna-xhigh-smoke-luna-xhigh-v4-a001.json` | `264fef371c6672867f82124fbffb7f01623e678e9768a72541180dacbb8d17b7` |
| `gpt56-luna-xhigh-smoke-luna-xhigh-v4-a001.log` | `28ee9f834e5c9ae85cfad3dbfb3bcf5fea9184d8ad2d97a7b08981fe9d743404` |
| `step4-core-remainder-v5-runner-state.json` | `f5d72461a184834fe8e5f679c13a7c3fb81e68513cc724bbb30a82d120da61ff` |
| `core-remainder-v5-manifest.json` | `4ea086b259f3eff95134cbba270585fc42246da4d04d4dfa5431b408e7b14f42` |
| `step4-core-remainder-worker-v5.log` | `ef77c3fda82b9805cdfdfd047609a68f659cce902c4b74af8356d076180f5c24` |
| `gpt56-luna-max-smoke-core-remainder-v5-a001.json` | `96f21383cc2352cf5257eb2b545047bedb2659e7aca266bc50a216f43bed33f4` |
| `gpt56-luna-max-smoke-core-remainder-v5-a001.log` | `2d15a09d064af8f6bb2a03229a2c62515c638a94805c2794d385f1da457b47c4` |
| `gpt56-terra-low-smoke-core-remainder-v5-a002.json` | `45e5245d09d008563d7ac17abcaadfacb9243e2e2fc0c3aff0b7bdb477aeeb95` |
| `gpt56-terra-low-smoke-core-remainder-v5-a002.log` | `1bb3b9d958b44c847d266fac9d4b32338285e7e73c0c8ca05d069c03c0b85660` |
| `gpt56-terra-xhigh-smoke-core-remainder-v5-a003.json` | `f128c25b2612304e008200a84e94a267b503366b4303563b9beccf32553628a3` |
| `gpt56-terra-xhigh-smoke-core-remainder-v5-a003.log` | `6412432ab6b93c6aa8f7352c34bde9a8c0ec977da457d2c7bc6cec20bd58953e` |
| `gpt56-terra-max-smoke-core-remainder-v5-a004.json` | `0d7b9f94a436b75ba89a03259a7d75c2683a30e929126bd3e0f495c28a483c1e` |
| `gpt56-terra-max-smoke-core-remainder-v5-a004.log` | `9f9c05b5914f874f487b34b504eae7372c9f95a2ab2f81fd928b23efd2b134f5` |
| `step4-core-production-v1-runner-state.json` | `997132baae971e1c7140ce8d185faeaa94a249d2b6006b04eea76297478be76f` |
| `core-production-v1-manifest.json` | `39f214decb48ed068e4583871bbd2eff74eab3d9a24c24e6e0071e48153e1b63` |
| `step4-core-production-worker-v1.log` | `02573cf9c3e4cdcac865933e4112a0fb7189e573fcfa999060820bc3db3c4431` |
| `gpt56-luna-low-r01-a001.json` | `4e12b1ec71fbe9ef6cb4223d50cc03e7b229fca0243effea27346c53436fe871` |
| `gpt56-luna-low-r01-a001.log` | `bebeecf2d1dd66a5d2f37f763b3b19a144eace529220f482d32bacbba87a7b35` |
| `gpt56-luna-low-r01-a002.json` | `de6e60acc60d927b4d77099b7ffa593f4567d5c0d9246b9d85976defb0b99590` |
| `gpt56-luna-low-r01-a002.log` | `8f96449acf3dc38c42565d73eca33c339a7a0409478ed1216e34c2af7e4e4953` |
| `step4-core-production-run-review-fable-v1.md` | `d498176cf400dc9e72f0ba1f919ca6f6ebf01390ca72900a5e89d9df2e66b14c` |
| `step4-authorization-ledger-parallel-replay-v6.json` | `c83ce7e9a60e1715ac67b188876113406a482b1a860188b223dbdfa597c283cd` |
| `step4-parallel-replay-preflight-v6.md` | `3515a408ee75da19bd06bd98ec66a8c8200586bfbebe6259f092fe4044baa70a` |
| `step4-parallel-replay-preflight-review-fable-v6.md` | `c0cd2a94b50a91342af897ff8cabfca9ae4022b9d86ea1779fdf6c68c0f4757d` |
| `step4-parallel-replay-preflight-review-fable-v6-closure.md` | `fe21570ab45ee92f012e4e549e2baa0f9c80197273495a11070cf8a9865053ac` |
| `step4-parallel-replay-v6-runner-state.json` | `6f06bf8e3eacd53c23d3ca9f5f8b4f7909a26850d8034476d88c53224d78740a` |
| `parallel-replay-v6-manifest.json` | `1cf75c74375855423fa56de340ef8e273d5d6e84cf26efc111e3af3ba973e2bf` |
| `step4-parallel-replay-worker-v6.log` | `0c70beec27a90f6407bd22f6b7514a99bd80ca4e3962a051f1090ea807ac2404` |
| `gpt56-luna-low-smoke-parallel-replay-v6-a001.json` | `2ee9f37bd9d146279a36bb70003dccfc2570fa229586b75caa0080c04af2375d` |
| `gpt56-luna-low-smoke-parallel-replay-v6-a001.log` | `118e9f87310df37ec636433acf674ba6c20ccdc09d98f06439082971a6003806` |
| `step4-parallel-replay-run-review-fable-v6.md` | `e9eec7b40b12fb962c2ef05014f06646ac62d35e7b24e87aa574a4f2353dd633` |
| `step4-parallel-replay-run-review-fable-v6-closure.md` | `82bca7195219e4926b58cc9c54c7dfe3da13ff38f12de529aac35e6599c2ffd9` |
| `step4-authorization-ledger-parallel-replay-v7.json` | `9bf230643a65a8c823da90d42434a75f6d1d111841a2c0f8286d57e9aa02a022` |
| `step4-parallel-replay-continuation-preflight-v7.md` | `cbd040735ef295462ca055153ae857fcb4f6d81962c397db0dba72c83975c9ee` |
| `step4-parallel-replay-continuation-preflight-review-fable-v7.md` | `4da045104240f731f2fe0e33a2e3c255d41f688fef26dc1878a65c337191bec2` |
| `step4-parallel-replay-continuation-preflight-review-fable-v7-closure.md` | `87f48972469d6868a5f7c286a2c2259c3402e9ad5f02253df06d7e713f5a2187` |
| `step4-parallel-replay-continuation-preflight-review-fable-v7-final.md` | `578a0df0cafd44d0e46b980ae7cf3a07f23b47a19a0e01630c8ffa7fdd68bb1a` |
| `diagnostics/gpt56_parallel_replay_validation.py` | `35fb1a2acc87a7f519f854a331667a87e7abdfef5ac3bf90dd5f47e1c126ec37` |
| `step4-parallel-replay-continuation-v7.json` | `a5747ed2233ced3c36811eafe7b470e251f73f00b4d0951d2bbea5c9449a2502` |
| `step4-parallel-replay-continuation-worker-v7.log` | `77704fbe81f7e6f01205c19676fd4705a6f23dd2430b3392cfc69eaa0b0d081d` |
| `step4-authorization-ledger-production-input-replay-v8.json` | `ce392e821618cdcbd5762dcf148776b72245add2dcff4c952398f8cae1fb8f97` |
| `step4-production-input-replay-preflight-v8.md` | `2cada023ceb95bca630bfd6c4b28c043102cf55b8d250a308b9339bd23e5d841` |
| `diagnostics/gpt56_production_input_replay_validation.py` | `19492a684765a8b6ab67fec9d72392bb2835542120ce9f0b4bfc837346df885a` |
| `tests/test_gpt56_production_input_replay_validation.py` | `64105e47861ca6f4b8b28465a02551719282b911ed34df9ee8656675756213b0` |
| `step4-production-input-replay-validation-v8.json` | `10779d88a4f0ab75ab949404c4fb913e71bf23721fafce35649e5624763d9235` |
| `step4-production-input-replay-worker-v8.log` | `993c36266faf64f6eb64444c7088ca302bcba9a7bb5164e6924f9cce2953c0c2` |
| `step4-authorization-ledger-production-input-replay-v9.json` | `f971b97282e84f3b88d53ce6c917fe9628d83ef701d7533f952f7a83245ab7b4` |
| `step4-production-input-replay-preflight-v9.md` | `6c7cfb9aa71ea3d57b576d527e8b57903fd76cf45263c5190aacfa0e5d7c9cd8` |
| `diagnostics/gpt56_production_input_replay_validation_v9.py` | `77906eed009787788a830671482c53d832653048311c0901c8564a6e4d3315b3` |
| `tests/test_gpt56_production_input_replay_validation_v9.py` | `ad472ecaa1ee5b21a7a2634a4903c48c5786077de22d014750321b8e766b667e` |
| `step4-core-production-v3-runner-state.json` | `50207b5359d2647aba6bac5d2036c4ed52cf54f2c4342c95ed335d4594ec6888` |
| `core-production-v3-manifest.json` | `ce4479626a2031c66514d22c181e6b5078d16fe4efcfa975613bdd8d5015c076` |
| `step4-core-production-worker-v3.log` | `c5db7a383d98e6280be010cef15ab19882ff3fef583b48e6ba0f6c0dcb3e7ee4` |
| `gpt56-terra-max-production-core-v3-r25-a150.json` | `00db3e0f0058590e51c04ab9573cb913bb431db0c7a90706243302f3c9bfbaf3` |
| `gpt56-terra-max-production-core-v3-r25-a150.log` | `c1ffd3e614bf82b039e14738751144f1a8762740c7c9a479f9c153d2fcde61a9` |
