# Round-3 Review: final PLAN.md confirmation

Reviewed the current `PLAN.md` only. No plan or code changes.

## Verdict

Implementation-ready for `/implement`. I found no remaining blocking item.

## Confirmations

- **Round-2 should-fix 1, staged validation cost:** resolved. Step 5 now explicitly uses seed-matched 3-5 round smoke stages and reserves full 25-round sequential sweeps for the sequential baseline, final candidate, or ambiguous stages (`PLAN.md:75-76`).
- **Round-2 should-fix 2, logging format:** resolved. Validation now requires canonical `.log` worker capture with `tee` plus `RUN_START`/`RUN_EXIT`, and the rule is repeated in Step 5's run-script work (`PLAN.md:48-50`, `PLAN.md:75-77`).
- **Round-2 should-fix 3, retry tests:** resolved. Step 3 now requires the empty->retry->success test to assert no nudge is appended and `_no_tool_watchdog_handle` is cancelled/cleared before retry; the safety rules also require immediate watchdog cancellation and separate retry telemetry (`PLAN.md:42-46`, `PLAN.md:67-69`).
- **Nice-to-have, Step 1 diagnostic-only label:** resolved. The concurrency probe is labeled a bounded diagnostic exception and never leaderboard data in both validation rules and Step 1 (`PLAN.md:48-50`, `PLAN.md:59-60`).
- **Nice-to-have, define no error frame:** resolved. The B signature now excludes synthesized `inference_failure`, tool `error_event`, and visible text-only no-tool responses; Step 3 also tests those exclusions (`PLAN.md:22`, `PLAN.md:45`, `PLAN.md:67-69`).

## Prompt-step removal

Dropping the prompt-change step introduced no gap. The plan states there is no prompt change (`PLAN.md:6`), records that prompt-hash hazards do not arise (`PLAN.md:24`), and explicitly forbids changes to `system_instruction.txt` or `args.task` (`PLAN.md:40`). Step 5 is now validation only, with scratch leaderboard output and user-gated committed leaderboard updates (`PLAN.md:75-77`). I found no stale Step 5 prompt-change, system-instruction edit, or prompt-scoping action.

## Numbering

Step numbering and cross-references are consistent after the renumbering. The executable steps are 1-5 (`PLAN.md:59`, `PLAN.md:63`, `PLAN.md:67`, `PLAN.md:71`, `PLAN.md:75`), and the progress table matches those same five steps (`PLAN.md:82-86`). Cross-references map cleanly: Step 1 gates Steps 3 and 4 (`PLAN.md:60`, `PLAN.md:68`, `PLAN.md:72`), Step 2's escalation references Step 5 (`PLAN.md:64`), and Step 5 attributes effects across Steps 2-4 (`PLAN.md:76`).
