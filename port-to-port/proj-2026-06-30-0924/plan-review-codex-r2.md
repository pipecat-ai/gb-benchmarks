# Round-2 Review: revised PLAN.md

Reviewed `PLAN.md` against `plan-review-codex-r1.md`, the current Baseten sweep script, and the relevant harness paths. Review only; no plan or code changes.

## Verdict

No remaining round-1 blocking issue is open at the plan level. The revision is much closer to implementation-ready: retry accounting, capture ownership, watchdog cancellation, Baseten/GLM gating, prompt-scope protection, and sequential validation are now explicitly called out.

I would not run Step 6 exactly as written at full default scale. Full sequential staging is likely too expensive, so the plan should add explicit reduced round counts or an early-stage smoke matrix before full validation. One round-1 should-fix also remains partially open: validation logging still does not say whether `*.out` is accepted or converted to `.log`/`tee` worker logs.

## Round-1 Blocking Items

| R1 item | Status | Resolution / remaining gap |
|---|---:|---|
| Retry capture lifecycle would corrupt inference capture bookkeeping | Resolved | `PLAN.md:18` now identifies the active capture lifecycle, `PLAN.md:41-44` requires retry ownership of the active empty-attempt capture, and `PLAN.md:66-68` requires tests for empty->success and exhausted retry paths. |
| Retry must cancel/own the already-armed no-tool watchdog | Resolved | `PLAN.md:17`, `PLAN.md:21`, `PLAN.md:43`, and `PLAN.md:66-68` now describe the ordering and require immediate watchdog cancellation before retry. |
| Mechanism-B signature/gating/turn-accounting was insufficient | Resolved | `PLAN.md:36-44` and `PLAN.md:66-68` add Baseten GLM/Nemotron gating, empty thought, no usage, no error frame, no `turn_count`/`turns_executed`, no normal `turn_log`, and separate telemetry. |
| GLM `reasoning_content` preservation was under-specified | Resolved | `PLAN.md:29-30`, `PLAN.md:37-38`, `PLAN.md:58-60`, and `PLAN.md:70-72` now make this a spike-first task, require raw reasoning-shape evidence, forbid pipecat edits, and require a new Baseten-GLM predicate instead of `_is_glm_sglang_binary_reasoning_model`. |
| Prompt changes could silently mix in leaderboards | Resolved | `PLAN.md:23-24`, `PLAN.md:46-50`, `PLAN.md:74-76`, and `PLAN.md:78-80` now call out the `task_prompt_hash` hazard and require separate prompt scope or `system_instruction_hash` scoping plus scratch leaderboard output. |
| Validation violated sequential-per-endpoint rules | Resolved for validation | `PLAN.md:47` and `PLAN.md:78-79` require sequential Baseten validation and `RUN_START`/`RUN_EXIT`. Step 1's deliberate concurrency probe is a diagnostic exception, not leaderboard validation. |

## Round-1 Should-Fix Items

| R1 item | Status | Resolution / remaining gap |
|---|---:|---|
| Land the simple Mechanism-A token-cap fix before risky reasoning work | Resolved | Step 2 now raises Baseten max tokens before Step 3/4 (`PLAN.md:62-64`). |
| Step 1 should collect reasoning evidence for GLM preservation | Resolved | Step 1 now captures `delta.reasoning_content` and `message.reasoning_content` on successful GLM turns (`PLAN.md:58-60`). |
| Handle Nemotron `force_nonempty_content` limitation explicitly | Resolved | `PLAN.md:10`, `PLAN.md:39`, and `PLAN.md:59` make this evidence-gated and out of reach unless Baseten proves support. |
| Add eval/leaderboard regression coverage for new transport telemetry | Resolved | `PLAN.md:25`, `PLAN.md:41-44`, and `PLAN.md:66-68` require telemetry to remain separate and add an eval regression for discipline metrics and grouping. |
| Make validation attribution staged | Resolved, with new scale concern | `PLAN.md:78-79` now stages baseline -> max_tokens -> retry -> reasoning -> prompt, but full 25-round staging is too large; see new Should-fix below. |
| Clarify run logging and monitoring | Partially open | `PLAN.md:47` and `PLAN.md:78-79` add `RUN_START`/`RUN_EXIT`, but the current script still writes per-run `*.out` (`run_baseten_sweep.sh:88`) and the plan does not say whether those become `.log` files or worker logs with `tee` as required by `../AGENTS.md:9`. |
| Account for `FC_TIMEOUT=30` | Resolved | `PLAN.md:27` notes the current value and `PLAN.md:50` says to keep it intentionally for baseline comparability. |

## New Findings

### Should-fix: Step 6 full sequential staging is too expensive

As written, Step 6 implies 5 stages x 6 configs x 25 rounds = 750 sequential episodes on one Baseten base URL. The 2026-06-29 progress logs show config averages around 99-206 seconds per episode, so the historical mean puts a full staged run around 32 hours before evaluation; the `PER_RUN_TIMEOUT=600` ceiling makes the worst case about 125 hours. The later 20260630 run already has 600-second timeouts in GLM configs, and `MAX_TOKENS=8192` plus retries may increase elapsed time.

Recommended plan adjustment: make Step 6 explicitly two-tiered. Use small seed-matched smoke stages, for example 3-5 rounds per config or targeted GLM/Nemotron configs, to attribute effects. Reserve 25-round sequential sweeps for the sequential baseline that tests the concurrency hypothesis and the final candidate, or for any stage whose smoke result is ambiguous. Keep prompt-changed validation in its own scope.

### Should-fix: logging format remains underspecified

The plan now requires `RUN_START`/`RUN_EXIT`, but it should also say whether the sequential mode renames per-run `*.out` to `*.log`, tees command output to a worker log, or explicitly treats the worker log as the canonical console capture. This is still an AGENTS.md compliance gap, not a harness correctness issue.

### Should-fix: add explicit watchdog assertions to Step 3 tests

The rules require immediate `_no_tool_watchdog_handle` cancellation, but the Step 3 test list should explicitly assert that no nudge message is appended during an empty-response retry and that the watchdog handle is canceled/cleared before the retry is scheduled. Exhausted retries should still hit the existing nudge/stall behavior.

### Nice-to-have: document Step 1 as a bounded diagnostic exception

Step 1's concurrency test does intentionally violate the normal sequential-per-endpoint rule, but it is justified because it tests whether the original violation induced Mechanism B. To avoid confusion, the plan should label it as diagnostic-only, not judgeable benchmark data, keep sample counts bounded, and avoid feeding those outputs into leaderboards.

### Nice-to-have: define "no error frame"

Step 3 says the B signature requires "no error frame" (`PLAN.md:66-68`). The current harness has synthesized `inference_failure` handling around `mini-rl-env.py:2434-2467` and tool-result `error_event` handling in `_finalize_if_ready`. The implementation plan could name the exact negative cases: do not retry if an exception/synthesized inference failure is observed, and do not classify visible text-only no-tool responses as transport empties even if usage is absent.

## Answers To The Specific Round-2 Questions

- **(a) Step 6 tractability:** not tractable at full 25 rounds for every stage. Reduce intermediate-stage rounds and keep full 25-round sequential runs for baseline/final or ambiguous stages.
- **(b) Step 1 concurrency conflict:** acceptable as an intentional diagnostic exception, provided it is bounded and not treated as benchmark/leaderboard data.
- **(c) Step 3 conditionality:** resolved. `PLAN.md:66` correctly says retry is only implemented if Step 1 shows B is per-request; otherwise it downscopes to telemetry-only.
- **(d) capture/watchdog/turn accounting:** resolved at plan level. The remaining improvement is test specificity for "no nudge during retry" and watchdog-handle state.
