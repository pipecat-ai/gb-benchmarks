# Step 3: Focused GPT-5.6 sweep and downstream identity

Status: **COMPLETE — offline-verified; Fable medium remediation audit approved completion; final should-fix items closed**

No provider calls were made in this step.

## Locked runner matrix

The dedicated `run_gpt56_sweep.sh` contains nine wire-distinct configurations, ordered identically inside every round `r01` through `r25`:

| Config | Model | Requested thinking | Override | Effective effort | Max output / turn | Request / idle / episode timeout | Wall reservation |
|---|---|---|---|---|---:|---:|---:|
| `gpt56-luna-low` | `gpt-5.6-luna` | `low` | — | `low` | 50,000 | 900 / 600 / 7,200 s | 7,500 s |
| `gpt56-luna-xhigh` | `gpt-5.6-luna` | `xhigh` | — | `xhigh` | 50,000 | 900 / 600 / 7,200 s | 7,500 s |
| `gpt56-luna-max` | `gpt-5.6-luna` | `xhigh` | `max` | `max` | 50,000 | 900 / 600 / 7,200 s | 7,500 s |
| `gpt56-terra-low` | `gpt-5.6-terra` | `low` | — | `low` | 50,000 | 900 / 600 / 7,200 s | 7,500 s |
| `gpt56-terra-xhigh` | `gpt-5.6-terra` | `xhigh` | — | `xhigh` | 50,000 | 900 / 600 / 7,200 s | 7,500 s |
| `gpt56-terra-max` | `gpt-5.6-terra` | `xhigh` | `max` | `max` | 50,000 | 900 / 600 / 7,200 s | 7,500 s |
| `gpt56-sol-low` | `gpt-5.6-sol` | `low` | — | `low` | 50,000 | 1,200 / 600 / 28,800 s | 29,100 s |
| `gpt56-sol-xhigh` | `gpt-5.6-sol` | `xhigh` | — | `xhigh` | 50,000 | 1,200 / 600 / 28,800 s | 29,100 s |
| `gpt56-sol-max` | `gpt-5.6-sol` | `xhigh` | `max` | `max` | 50,000 | 1,200 / 600 / 28,800 s | 29,100 s |

The matrix is 225 production slots in round-major order, with Sol ordered last inside every round. `PRINT_CONFIGS=1` emits all tuples without reading a key or writing state; `DRY_RUN=1` emits the exact command shapes. Smoke is split into disjoint `GPT56_PHASE=smoke-core` (six Luna/Terra slots) and `GPT56_PHASE=smoke-sol` (three optional Sol slots), each with separate state and manifests.

## Conservative reservation model

Fable round 1 correctly challenged the original 3M-input heuristic. The repaired bound derives from the current official model limits: all three [GPT-5.6 model pages](https://developers.openai.com/api/docs/models) document a 1,050,000-token context window, long-context pricing above 272K at 2× input / 1.5× output, and cache writes at 1.25× uncached input. A subsequent Step 4 preflight audit found that successful final-response usage cannot account for possibly billable work performed by hidden SDK retries. The exact GPT-5.6 service therefore pins SDK retries to zero and leaves infrastructure replacement to the artifact-producing outer runner. Before every episode, the runner atomically reserves strict headroom for:

- 52,500,000 input tokens (50 inferences × the full 1.05M context window) plus 2,500,000 output tokens (50 × the 50,000 cap), or 55,000,000 accounted tokens;
- `$153.75` for Luna, `$384.375` for Terra, or `$768.75` for Sol. This compounds the cache-write and long-input multipliers for every reserved input token and applies the long-context output multiplier to every reserved output token;
- 7,500 seconds for Luna/Terra or 29,100 seconds for Sol, adding 300 seconds of worker/tee accounting margin to the enforced episode timeout.

Actual trace usage and wall time replace that reservation in cumulative accounting after a run. Actual dollar accounting is also conservative: uncached input is always treated as a cache write, and per-request long-context multipliers are applied from each trace. If any trace lacks complete, internally consistent usage, the full episode token/dollar reservation is charged. An interrupted inflight attempt is charged the full wall reservation. The next attempt cannot start when cumulative actual/estimated use plus its full reservation is equal to or above any approved token, dollar, or wall ceiling, or when it reaches the approved maximum-attempt bound. Live mode refuses to start without the approval ID, three ceilings, maximum-attempt bound, and three reviewed hashes; fresh and resumed state are bound to those values.

These true per-episode maximum reservations supersede Step 1's provisional smoke budget proposal. A core-stage approval needs headroom for the 55M-token, `$384.375`, 7,500-second Terra maximum; the optional Sol stage separately needs headroom for 55M tokens, `$768.75`, and 29,100 seconds. No live ceiling is approved yet.

Approval binding hashes for this reviewed implementation are:

- full-phase matrix: `fb120045c719a4ab38d0ddcf69b7b52d4061813f2c749367e42333b6d00c2e7d`
- runner: `a198d077733cb512b761bb97e73eb0429f7a858d26c275277fa272cda99b19d8`
- execution implementation (`runner + mini-rl-env + factory + Responses service`): `0860bfe2bba9b2446aa5a0d0edb3073446beb47d1c97aa024a23874ae808b9f9`

All three are persisted in live state; a changed matrix, runner, harness, factory, or Responses service cannot resume under an older approval record.

## Selection, retry, and recovery invariants

- Execution is synchronous with no background workers: round outer loop, config inner loop, one `timeout`-wrapped hosted OpenAI command at a time. A nonblocking exclusive `flock` shared by smoke and full phases prevents a second runner process from using the hosted endpoint concurrently.
- The runner pins OpenAI SDK 2.21.0 before state/key access. The exact GPT-5.6 service pins the SDK to zero internal retries and records both `openai_sdk_version=2.21.0` and `sdk_max_retries=0` in every trace. Eligibility requires both values, exactly one sanitized Responses trace per finalized turn, and no more traces than configured `max_turns=50`. This locks the reservation's maximum at 50 visible provider inferences per episode.
- Every attempt gets a new `config-round-aNNN` JSON/log stem. `RUN_START` and `RUN_EXIT` are captured through `tee`; the runner never deletes artifacts.
- Canonical is the first eligible attempt for `(config_slug, round_id)`. An eligible later attempt cannot replace it. `response_incomplete` with JSON is an eligible model failure.
- `rate_limit_exhausted`, `inference_error`, exit-124-without-JSON, no/malformed JSON, invalid schema, missing/non-Responses traces, and model/effort/round identity mismatches are infra-ineligible.
- A config halts on its second consecutive identical infra signature or after its tenth replacement. The ten-replacement allowance is intentionally pooled per config across all 25 rounds, matching the plan's “per config” rule; alternating signatures still terminate at that cap. Other configs continue. A global ceiling/max-attempt stop ends the worker.
- The state write uses fsync plus atomic replace after reservation and after every attempt. An interrupted inflight reservation is recovered as a conservative no-JSON attempt with its full reserved wall time before resume.
- State and the generated manifest retain attempt order, paths, response statuses, terminal reason, usage, estimated cost, effective effort, round, hashes, and selection reason. Derivative paths remain `null` until Step 5.
- Reservation refuses any attempt stem whose JSON or log already exists. The runner does not invoke judging, leaderboard building, refresh logic, deletion, or canonical-input mutation.

## Downstream identity

`evaluate_runs.py` now copies `effective_effort` and `round_id` into every enriched row. New GPT-5.6 identities use effective effort in place of the requested thinking label; legacy rows with neither field preserve their exact previous identity and display behavior.

`build_primary_leaderboard.py` groups and displays new rows by effective effort, using the same config→summary→metadata precedence as evaluation. A synthetic 50-row test proves native `xhigh` and overridden `max` remain separate `N=25` rows and that every `(model, effective_effort, round_id)` identity is unique.

## Offline verification

- `tests/test_gpt56_sweep.py`: 19 tests covering the 225-slot tuple/order, disjoint six-slot core/three-slot Sol smoke phases and no-replacement gate, dry-run commands and custom path, exclusive-lock structure, approval/hash-before-key gates, all specified classifier fixtures, strict usage completeness, inference-count/retry-policy invariants, missing/malformed/unknown terminal data, strict budget stops, atomic first-eligible selection, second-identical halt, exact ten-replacement cap, conservative recovery and partial-usage fallback, identity/approval mismatches, artifact collision, a fully executed six-slot core reserve→run→record smoke loop, enriched identity, two `N=25` groups, one-to-one round identities, exact legacy evaluation identity, and legacy leaderboard byte identity.
- Full non-probe suite: 177 tests passed (including the 19 Step 3 runner tests and 7 Step 4 diagnostic tests).
- `bash -n run_gpt56_sweep.sh`: passed.
- `shellcheck run_gpt56_sweep.sh`: passed with no findings.
- Python compile and `git diff --check`: passed.
- Current-input rebuild SHA-256 equals committed leaderboard SHA-256: `dd8d00c01adf316abe2a390fb8222b1bfdcd5df675093604dda4faff1f5e7da7`.
- `PRINT_CONFIGS` produces 225 data rows; `DRY_RUN` produces 225 commands.

## Direct adversarial review

The primary review specifically challenged duplicate wire identities, legacy grouping drift, model-failure cherry-picking, infra replacement counting, identity-confused JSON, missing trace accounting, resume after interruption, state/config drift, and global-vs-config halt behavior. Fable round 1 additionally found the heuristic input reservation, cross-process concurrency, recovery wall undercount, partial-usage undercount, equality-at-ceiling behavior, artifact collisions, slug ambiguity, unknown terminal handling, and divergent field precedence. Fable's successful inline remediation audit found F1–F10 materially closed and said Step 3 could be marked complete, with SDK retry/inference-count pinning and a stubbed live-loop test due by the Step 4 gate. Both were implemented; the Step 4 direct audit then strengthened the retry pin from two to zero so all provider attempts remain ledger-visible, added runtime approval hashes and strict usage validation, and split smoke into core versus optional-Sol stages. The active core-stage package receives a fresh Fable review before approval. This report does not authorize a live call.
