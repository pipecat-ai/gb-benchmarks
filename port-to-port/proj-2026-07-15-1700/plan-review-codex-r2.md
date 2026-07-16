# Plan review — Codex R2

## Verdict

Not implementation-ready yet. The revision resolves the sweep-filter, per-config token-cap, request-boundary, retry-gating, and most data-preservation issues from R1. Three execution blockers remain: Step 1 still does not predeclare an operational decision threshold, the canonical-infra classifier does not match the harness's actual terminal reasons, and Step 5's judging/derivative workflow is internally inconsistent with both the repository rule and the leaderboard builder's resolved-path join.

## R1 blocking items

| R1 item | R2 status | Evidence / remaining issue |
|---|---|---|
| B1. Exact `CONFIG_FILTER` and count assertion | **Resolved** | Step 4 (`PLAN.md:50-52`) uses the exact list `inkling-low,inkling-high,inkling-max`, explicitly rejects glob semantics, and requires selected/expected and `25 × configs` assertions. |
| B2. Durable per-config `max_tokens` | **Resolved** | Step 3 (`PLAN.md:46-48`) specifies `slug\|model\|thinking\|max_tokens`, explicitly replaces the old `thinking="${rest##*|}"` parser, passes the per-config cap, tests parsed tuples and command args, and logs the cap at all three lifecycle markers. |
| B3. Preserve failed data and make reruns/canonical selection explicit | **Partially resolved; blocking remainder** | Rules (`PLAN.md:30-33`) and Step 4 (`PLAN.md:50-52`) now preserve JSON/logs, use new attempt stems, classify reruns, record infra counts, and acknowledge the weak resume predicate. However, the exclusion vocabulary is not executable as written: the harness emits terminal reason `inference_error` for the Baseten non-429 API-error path (`mini-rl-env.py:2065-2067`), while the plan lists `inference_failure`; an outer `timeout` is an exit status and often has no JSON/terminal reason. Define the exact classifier over terminal reason, turn telemetry, worker exit code, and artifact presence, including `inference_error`, and define the canonical set deterministically (for example, first 25 non-infra attempts by monotonically assigned attempt number). |
| B4. Controlled probe protocol | **Partially resolved; blocking remainder** | Step 1 (`PLAN.md:38-40`) now isolates request shapes, adds a no-effort control, fixes temperature/cap, repeats samples, covers `max`, records the required telemetry, and separates the cap experiment. But “MONOTONICALLY moves reasoning_tokens / 400s the wrong field” is not a predeclared threshold: sample count, statistic, tolerated overlap, and minimum effect are still unspecified. It would also reject the known-good control in the cited integration data, whose medians are non-monotonic (`minimal` 76 > `low` 66 and `xhigh` 176 > `max` 162). Predeclare a finite sample count and an operational pass/fail rule before collecting data; otherwise Step 1 cannot objectively unblock Step 2. Also choose one SDK form for shape (ii), rather than the current “native kwarg / `extra_body`” alternative. |
| B5. Live harness smoke plus final-call verification | **Resolved** | The correctness rule (`PLAN.md:28-29`), Step 2 (`PLAN.md:42-44`), and Step 4 (`PLAN.md:50-52`) require an offline `chat.completions.create` boundary spy and a live one-episode smoke before promotion, while correctly treating `provider_invocation_params` as insufficient. |
| B6. Reproducible, non-destructive leaderboard workflow | **Partially resolved; blocking remainder** | Step 5 (`PLAN.md:54-56`) fixes the root README path, avoids in-place raw mutation, judges only new work, preserves existing enriched rows, builds to scratch, and approval-gates committed outputs. Two details remain blocking: (1) Rules say every failed run with JSON must be judged (`PLAN.md:31`), but Step 5 says to judge only canonical artifacts (`PLAN.md:55`), which excludes infra-failure JSONs; evaluate all new Inkling JSON artifacts, then restrict only the leaderboard input to the canonical 25. (2) `build_primary_leaderboard.py:272-278,329-346` joins each run to an enriched row by resolved file path. If originals are judged and renamed derivative copies are used as leaderboard inputs, the join fails. State the exact order—e.g. create derivatives first, evaluate those derivatives so enriched `file` paths match, then symlink those same derivatives into the input—or keep the raw model name/use the bracketed alias. |

## R1 should-fix items

| R1 item | R2 status | Evidence / remaining issue |
|---|---|---|
| S1. Name Pipecat/SDK/wire effort representation and clear stale controls | **Resolved** | Current state, Rules, and Step 2 (`PLAN.md:15,27,43`) distinguish the layers, make the probe choose the representation, and require exactly one surviving control. |
| S2. Tighten temperature wording and add conflict coverage | **Resolved** | Current state (`PLAN.md:15,18`) accurately describes post-construction mutation; Step 2 (`PLAN.md:43`) adds the `0.2 → 1.0` Inkling conflict test and negative controls. |
| S3. Exercise both transport-empty retry gates; do not model-gate 429 | **Resolved** | Current state and Rules (`PLAN.md:16,26`) cite the wrapper and install site and forbid a model gate; Step 2 (`PLAN.md:43`) tests runtime plus tracker recheck and a non-Baseten negative. |
| S4. Exact model set and meaningful validation invariant | **Resolved** | Rules and Step 2 (`PLAN.md:25,43`) use exactly `{inkling, thinkingmachines/inkling}`, preserve the six-level CLI invariant, and avoid requiring a no-op validation branch. |
| S5. Make the canonical `none` policy explicit | **Still open — Should-fix** | Step 3 (`PLAN.md:47`) still defers include/exclude to a later “viability call,” while Step 4's full-run filter (`PLAN.md:51`) always excludes `inkling-none`. Declare one policy now: either `none` is probe/smoke-only and never canonical, or define an objective Step-1 criterion that adds it to both the full-run filter and expected count, with folded-CoT labeling. |
| S6. Replace/define `cx-delegate` | **Resolved** | Process Rules (`PLAN.md:34`) assign it to the orchestrator and identify the commit authority. Per the R2 review instruction, it is available in that environment. |

## New / remaining should-fix items

1. **Step 5 must decide the filtered output, not defer the decision.** `PLAN.md:55` says to “decide and document” whether `leaderboard-natural-filtered.md` gets the same bytes. The prior ambiguity is acknowledged but not resolved. Since there is no filter builder and the files are currently identical, either declare that the same approved scratch bytes go to both, or specify an actual filter operation.

2. **Scope the Step-4 count assertions.** `PLAN.md:51` requires a final count of `25 × configs` but also permits additional-attempt JSONs. State that the exact count applies to the initial full-run directory and that a separate attempt/canonical manifest accounts for smoke and replacement artifacts.

3. **Allow the expected scratch metadata diff.** A rebuild with a scratch combined enriched file/input glob changes the generated `Source runs` and `Enriched scores` header lines. Step 5 should require only expected metadata changes plus Inkling rows, not literally “ONLY Inkling rows.”

4. **State the function-call timeout.** `run_baseten_sweep.sh` currently defaults to 30 seconds, while repository benchmark defaults specify 20. Step 4 should set 20, or explicitly retain 30 for Baseten-baseline comparability and record the exception.

## Nice-to-have

- The R1 reference corrections are resolved in Current state (`PLAN.md:12-21`).
- The cost/time stopping estimate remains only partial. Step 1 requests rough timing and Step 4 implies 75 canonical episodes, but the repeated-probe sample count, maximum total attempts, expected wall time, and spend ceiling are still unstated. Fixing the Step-1 sample count will make this estimate possible.

## Priority summary

- **Blocking:** operational Step-1 threshold; exact infra classifier/deterministic canonical manifest; judge-all-new versus canonical-only split; derivative/enriched resolved-path alignment.
- **Should-fix:** explicit `none` policy; filtered leaderboard policy; count scope; expected metadata diff; function-call-timeout choice.
- **Nice-to-have:** bounded cost/time estimate.
- **Resolved:** R1 B1, B2, B5; most of B3/B4/B6; S1-S4 and S6.

**Implementation-ready: No.** The remaining blockers are narrow and can be fixed in the plan without changing the overall five-step design.
