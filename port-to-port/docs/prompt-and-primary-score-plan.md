# Prompt And Primary Score Plan

## Goals

We want two changes to the port-to-port benchmark:

1. Keep a natural default task instruction that reflects how capable-model users talk to agents.
2. Add a second, more literal task instruction for small models.
3. Use a richer primary leaderboard metric that captures more of the performance variation we actually care about than a single pass/fail column.

The same core task should remain unchanged across both prompts:

- navigate from the start sector to the nearest mega-port
- recharge to full at the mega-port
- trade as profitably as possible along the required route
- return to the start sector
- provide a finished message with the required elements

## Current State

Current default task text in [mini-rl-env.py](../mini-rl-env.py) is intentionally natural:

> Go round-trip from our current location to the nearest mega-port. At the mega-port, recharge to full warp power. While traveling there and back, trade at every port that provides a trading opportunity. Make as much money as possible. Be sure you know how to trade well. When you're back where you started, give me a quick summary with the mega-port you used, how much warp you recharged and what it cost, how many ports you traded at, and total profit from the whole trip.

Current leaderboard summaries are still too centered on boolean completion outcomes.

This is too coarse for top models. It distinguishes catastrophic failures from clean completions, but it does not separate:

- clean but low-profit runs
- efficient vs wasteful navigation
- smart trading vs merely valid trading
- exact vs contradictory final reports
- disciplined vs sloppy tool use

## Observed Run Patterns

Patterns from earlier evaluations:

- Strong runs do more than finish. They infer profitable trade chains, avoid bad actions, and produce clean summaries with correct whole-trip accounting.
- Middling runs often complete the route and recharge correctly, but leave profit on the table, make a few invalid or unnecessary calls, or produce contradictory summaries.
- Poor runs fall into a few distinct buckets:
  - premature `finished` before returning home
  - repeated invalid or low-value trades
  - verbose planning without tool calls
  - max-turn exhaustion after completing only part of the task
  - correct route execution but incorrect final accounting

These differences are too important to collapse into a single strict boolean.

## Prompt Split Proposal

### Prompt A: Natural Prompt

Keep a natural default prompt for large-model / natural-user evaluation, but tighten it slightly so the no-detour constraint is explicit.

Draft text:

```text
Go round-trip from our current location to the nearest mega-port. At the mega-port, recharge to full warp power. While traveling there and back, make as much money as possible by trading optimally at profitable ports on your route without going off-course. When you're back where you started, give me a quick summary with the mega-port you used, how much warp you recharged and what it cost, how many distinct ports you traded at, and total profit or loss from the whole trip.
```

This prompt is valuable because:

- it matches how users naturally speak to high-capability agents
- it rewards planning, abstraction, and implicit checklist-following
- it still exposes whether a model can infer missing operational structure
- it makes the benchmark's intended no-detour trading constraint explicit

### Prompt B: Literal Small-Model Prompt

Add a second built-in task instruction designed for smaller or less agentically reliable models.

Draft text:

```text
Go from your current sector to the nearest mega-port, then return to the sector where you started.

Follow these rules exactly:
1. First identify the nearest mega-port sector that is not your current sector.
2. Plot a route to that mega-port.
3. Move one sector at a time along that route.
4. On the way to the mega-port, if the current sector has a profitable trading opportunity on your route, trade there.
5. When you arrive at the mega-port, recharge warp power to full.
6. Then plot a route back to your starting sector.
7. Move one sector at a time along the route back.
8. On the way back, if the current sector has a profitable trading opportunity on your route, trade there.
9. Do not call `finished` until you are back in your starting sector.
10. Every response must call a tool. Do not answer with plain text instead of a tool call.
11. Before you call `finished`, check all of these:
   - you reached the mega-port
   - you recharged to full at the mega-port
   - you are now back in the starting sector
12. In the `finished` message, include all of these:
   - the mega-port name and sector
   - how many warp units you recharged
   - the total recharge cost
   - how many distinct ports you traded at
   - the total profit or loss for the whole trip
```

Why this should help small models:

- it removes ambiguity about sequencing
- it makes the route checkpoint explicit
- it explicitly forbids non-tool narration
- it turns the final report into a checklist

This second prompt should not change the task, only the amount of scaffolding.

## Implementation Contract

These identifiers and field names define the current benchmark contract.

Prompt variant ids:

- `natural`
- `literal`
- `custom`

Expected harness metadata/config fields:

- `metadata.task_variant`
- `metadata.task_prompt_version`
- `metadata.task_prompt_hash`
- `config.task_variant`
- `config.task_prompt_version`

Expected evaluator output fields:

- `score_rubric_version`
- `task_complete`
- `leaderboard_prompt_id`

Resolution rules:

- if `--task` is provided, it overrides `--task-variant`
- if `--task` is not provided, `--task-variant` selects a built-in prompt
- built-in prompt runs must stamp `task_variant`, `task_prompt_version`, and `task_prompt_hash`
- if `--task` is provided, the run should store `task_variant=custom` and `task_prompt_hash`
- `task_prompt_version` is for built-in prompts only

Evaluator input contract:

- target schema is `mini_rl_run.v3`
- score derivation should primarily use:
  - `metadata.initial_state`
  - `summary`
  - `termination`
  - `turns[*].tool_calls`
  - `turns[*].state_before`
  - `turns[*].state_after`
  - `turns[*].bad_action_increment`

Minimum clean-room artifact requirements:

- per run:
  - start sector
  - initial credits
  - initial cargo by commodity
  - cargo capacity
  - target mega-port sector used for judging first-destination completion
  - final credits
  - final sector
  - whether recharge-to-full occurred at a mega-port
  - whether `finished` was called, and with what message
- per turn:
  - sequential turn index
  - zero or more tool calls in order, with tool name, normalized args, and result status
  - pre-turn and post-turn ship state
  - whether the turn produced a bad-action increment

If a new environment cannot emit the current `mini_rl_run.v3` shape exactly, it should still preserve those semantics.

Score contract:

- each category score is an integer
- each category score is clamped to its category bounds
- `primary_score_100` is an integer in `[0, 100]`
- `primary_score_100 = mission_completion_score + trade_quality_score + path_efficiency_score + tool_discipline_score + report_quality_score`

Ground-truth accounting contract:

- `distinct_ports_traded` means the number of unique sectors at which at least one successful `trade` call occurred
- `total_profit_credits` means `final_credits - initial_credits`
- `total_profit_credits` is a whole-trip credits delta, not a trade-only subtotal
- recharge cost is judged separately from total profit

## Scoring Direction

### Replace Boolean Primary Score With A 100-Point Score

Keep one supporting binary completion metric for summary views:

- `task_complete`

Definition:

- `task_complete` means the run reached the mega-port, recharged to full, returned to the start sector, and the first `finished` call happened only after those mission conditions were satisfied.

But define a new primary metric:

- `primary_score_100`

This score should be comparable across both prompt variants.

### Design Principles

- The score should reward real task completion first.
- It should distinguish mediocre from excellent runs.
- It should combine programmatic scoring and judged scoring.
- It should penalize wasted or incorrect behavior without letting one small mistake dominate the full score.
- It should not require special-case scoring for the natural vs literal prompt.
- It should judge execution of the instructed round-trip task, not reward separate route-planning creativity.

## Proposed Score Structure

### 1. Mission Completion: 40 points

- Reach the first required destination (nearest mega-port): 10
- Recharge to full at the mega-port: 10
- Return to the required final destination (start sector): 15
- Call `finished` only after satisfying the route completion conditions: 5

Why 40:

- This remains the backbone of the task.
- Runs that miss these checkpoints should not be competitive even if they trade well.

### 2. Trade Quality: 15 points

- Trade opportunity coverage on the required course: 5
- Commodity-choice quality / realized trade value quality on the required course: 10

Recommended implementation split:

- `trade_coverage_score`
  - did the run actually trade when a beneficial opportunity existed on the required course?
  - did it skip obviously beneficial on-course trades?
- `trade_quality_score`
  - compare realized on-course trade value against a required-course oracle optimum
  - do not reward extra profit from off-course sectors

Why required-course optimum:

- It matches the benchmark task: execute the instructed round trip well.
- It rewards trading skill without turning route choice into a second benchmark.
- It prevents profitable off-course detours from inflating the trade score.

Formal definition:

- Fix the benchmark's required navigation course: start sector -> nearest mega-port -> start sector, using the benchmark's canonical shortest valid round trip.
- In the current synthetic world this course is deterministic. If a future environment introduces multiple equally short valid courses, add a canonical tie-breaker and version the benchmark rather than leaving the choice implicit.
- Fix the actual starting state:
  - credits
  - cargo
  - cargo capacity
  - sector
- Fix the non-trade world events implied by that required course:
  - movement path
  - recharge event and recharge cost
  - any mandatory benchmark actions already taken
- Define `on_course_realized_trade_value` as the net credits gained or lost from successful `trade` calls that occur at required-course port visits before the first valid return to the start sector.
- Off-course trade calls do not increase trade score.
- Then compute `required_course_optimal_trade_value` for a perfect trader who is only allowed to choose different `trade` actions at the ports on the required course, in course order.
- Trade scoring compares `on_course_realized_trade_value` to `required_course_optimal_trade_value`, not whole-trip profit after off-course detours.

Oracle implementation rule:

- the oracle should be a dynamic program over the required-course port sequence
- oracle state should include at least:
  - current visit index
  - credits
  - cargo inventory by commodity
  - remaining free holds
- allowed actions at each required-course port visit should be:
  - any valid buy, sell, or skip action permitted by benchmark trade rules at that port
- invalid or impossible trade actions from the original run do not constrain the oracle; only the required course constrains it

This means the oracle may optimize trading decisions, but it may not:

- invent a different route
- insert extra sectors or ports
- reorder required-course visits
- assume access to off-course opportunities

Worked example:

- In the current world, the required-course port sequence is `3080 -> 4874 -> 2831 -> 1611 -> 2831 -> 4874 -> 3080`.
- The oracle may decide that the best required-course plan is:
  - sell QF at 3080
  - buy RO at 4874
  - recharge at 1611
  - sell RO and buy NS at 2831 on the way back
  - sell NS at 3080
- But it may not add a profitable detour to sector `1928`, because off-course opportunities are outside the task-constrained oracle.

Scoring implication:

- navigation quality should answer whether the model stayed on the required course efficiently
- trade quality should answer whether the model traded well on that course

Keep secondary diagnostics:

- `off_course_trade_value`
- `required_course_trade_gap`
- `global_profit_gap`

- `off_course_trade_value` captures how much trade value came from sectors that should not increase the benchmark score.
- `required_course_trade_gap = required_course_optimal_trade_value - on_course_realized_trade_value`
- `global_profit_gap` remains useful for analysis, but it should not drive the primary score.

Edge case:

- if `required_course_optimal_trade_value <= 0`, do not use the normal ratio bands
- in that case:
  - award full trade-execution credit if `on_course_realized_trade_value >= 0`
  - otherwise treat the run as having made harmful trade choices and assign a low trade-execution score

## 3. Path Efficiency: 15 points

- shortest-path compliance to first destination: 7
- shortest-path compliance on the return leg: 8

This category should judge whether the model stayed on the instructed course. Profitable off-course detours should still be penalized in V1.

Recommended implementation:

- score against shortest-path baseline
- penalize off-course movement, repeated backtracking, and wandering after goals are known
- do not offset extra movement with extra profit

Phase segmentation for path scoring:

- outbound phase: from start until first arrival at the chosen mega-port
- recharge phase: turns at the mega-port before recharge is completed
- return phase: from the first post-mega move until first arrival back at the start sector
- post-objective phase: any turns after the model has already returned home but before `finished`

`extra_moves_count` should always be counted against the current phase objective:

- outbound objective: reduce distance to mega-port
- return objective: reduce distance to start sector
- post-objective objective: finish immediately

V1 detour rule:

- any move that leaves the canonical shortest round-trip course counts as extra movement
- pure oscillations such as `A -> B -> A` count as avoidable backtracking unless `B` was required for direct mission progress

## 4. Tool Discipline: 15 points

Start this category at 15 and deduct within it.

- hallucinated tool names or impossible tool calls
- incorrect arguments, tracked diagnostically
- invalid moves
- invalid trades
- repeated unnecessary info calls
- plain-text no-tool turns

This category should capture the difference between:

- a model that is slightly noisy but operationally competent
- a model that repeatedly burns turns on avoidable mistakes

## 5. Final Report Quality: 15 points

- inclusion of required elements: 5
- element accuracy of required elements: 10

Required elements:

- mega-port used
- recharge amount
- recharge cost
- distinct ports traded
- whole-trip total profit or loss

This category should continue to rely on the LLM judge for semantic flexibility, but with ground-truth numbers supplied programmatically.

Judge output contract:

```json
{
  "overall_accuracy": true,
  "reason": "PASS|FAIL|UNSURE plus short explanation",
  "elements": {
    "mega_port_used": {"present": true, "accurate": true},
    "recharge_amount": {"present": true, "accurate": true},
    "recharge_cost": {"present": true, "accurate": true},
    "ports_traded": {"present": true, "accurate": true},
    "total_profit": {"present": true, "accurate": true}
  }
}
```

Total: 100 points

## V1 Scoring Formula

This is the formula a fresh implementation should use. If we retune it later, we should version the rubric rather than reinterpret these constants.

### Mission Completion: 40

- `mission_completion_score = 10 * reached_first_destination + 10 * recharged_to_full + 15 * returned_to_final_destination + 5 * finished_at_correct_time`

### Trade Quality: 15

Trade coverage: 5

Define:

- `beneficial_required_course_opportunity_count =` number of required-course port occurrences used by the required-course oracle for positive trade value
- `captured_beneficial_required_course_opportunity_count =` number of those port occurrences where the model executed at least one successful `trade` on that same required-course visit
- if `beneficial_required_course_opportunity_count == 0`, set `trade_coverage_score = 5`
- otherwise compute `trade_coverage_rate = captured_beneficial_required_course_opportunity_count / beneficial_required_course_opportunity_count`

Then score:

- 5: `trade_coverage_rate == 1.0`
- 4: `0.75 <= trade_coverage_rate < 1.0`
- 2: `0.25 <= trade_coverage_rate < 0.75`
- 0: `trade_coverage_rate < 0.25`

Trade execution vs required-course optimum: 10

- 10: at least 90% of required-course optimal trade value
- 8: 75% to 89%
- 5: 50% to 74%
- 2: 25% to 49%
- 0: below 25%

Use:

- `trade_execution_ratio = on_course_realized_trade_value / required_course_optimal_trade_value`

only when `required_course_optimal_trade_value > 0`.

Set:

- `trade_quality_score = trade_coverage_score + trade_execution_score`

### Path Efficiency: 15

Start at 15 and deduct:

- minus 1 for each unnecessary move after the correct route is already known, cap 9
- minus 2 for each avoidable backtracking loop, cap 6

Profitable off-course detours should still be penalized.

Formula:

- `path_efficiency_score = max(0, 15 - min(extra_moves_count, 9) - min(2 * avoidable_backtrack_count, 6))`

### Tool Discipline: 15

Start at 15 and deduct:

- minus 2 per hallucinated tool name or impossible tool call
- minus 1 per invalid move or invalid trade attempt
- minus 2 per plain-text no-tool turn
- minus 1 per unnecessary tool call that does not materially advance task state, information state, or scoring outcome

Floor at 0.

Formula:

- `tool_discipline_score = max(0, 15 - 2 * hallucinated_tool_count - invalid_move_count - invalid_trade_count - 2 * no_tool_call_count - unnecessary_tool_call_count)`

Scoring rule:

- `unnecessary_tool_call_count` excludes calls already counted as hallucinated or invalid

Definitions:

- `unnecessary_tool_call_count` is the umbrella count of tool calls that were avoidable and did not materially improve progress.
- `redundant_info_call_count` is a specific subset of `unnecessary_tool_call_count`.
- Example `redundant_info_call_count` cases:
  - repeated `my_status` with no relevant state change
  - repeated `load_game_info` for the same topic after the needed rules are already known
  - repeated route/info queries after the answer is already available in context

In other words:

- every `redundant_info_call` is an `unnecessary_tool_call`
- not every `unnecessary_tool_call` is a `redundant_info_call`

Diagnostic-only rule:

- keep `incorrect_tool_arg_count` as a raw field for analysis
- do not deduct it on top of `invalid_move_count` or `invalid_trade_count` for the same tool call
- each failed tool call should contribute at most one primary tool-discipline deduction bucket

Examples of unnecessary but non-info calls:

- re-plotting the same route with no state change
- calling a tool that is valid but obviously irrelevant to the current objective
- making a low-value side call that neither helps navigation nor improves trade execution

### Final Report Quality: 15

Required-element presence: 5

- 1 point each for:
  - mega-port used
  - recharge amount
  - recharge cost
  - distinct ports traded
  - whole-trip total profit or loss

Required-element accuracy: 10

- 2 points each for correctness of the same five elements

This keeps the report score explicit and explainable while still allowing LLM-based semantic matching.

Judge operational rules:

- if `finished` was never called, skip the LLM judge and set all report-element `present=false`, `accurate=false`
- if the judge returns `UNSURE` or malformed JSON, treat `overall_accuracy=false` and preserve the raw judge output for inspection
- `accurate=true` is only valid when `present=true`

Formula:

- `report_quality_score = report_presence_score + report_accuracy_score`
- `report_presence_score = sum(1 for each required element with present=true)`
- `report_accuracy_score = sum(2 for each required element with accurate=true)`

## Recommended Penalty Mechanics

Not every category needs to be purely additive. Some should behave as deduction buckets inside the category cap.

Recommended pattern:

- additive points for mission completion and trade quality
- deduction-style scoring inside tool discipline and path efficiency

Example:

- `tool_discipline_score = 15 - penalties`, floor at 0
- `path_efficiency_score = 15 - penalties`, floor at 0

This avoids making the rubric too brittle while still reflecting visible sloppiness.

## Suggested Subscores

Recommended output columns / JSON fields:

- `primary_score_100`
- `task_complete`
- `mission_completion_score`
- `trade_quality_score`
- `path_efficiency_score`
- `tool_discipline_score`
- `report_quality_score`

Supporting diagnostic fields:

- `reached_first_destination`
- `recharged_to_full`
- `returned_to_final_destination`
- `finished_at_correct_time`
- `trade_coverage_rate`
- `on_course_realized_trade_value`
- `required_course_optimal_trade_value`
- `required_course_trade_gap`
- `off_course_trade_value`
- `realized_pnl_vs_required_course_optimal`
- `global_profit_gap`
- `extra_moves_count`
- `avoidable_backtrack_count`
- `hallucinated_tool_count`
- `incorrect_tool_arg_count`
- `invalid_move_count`
- `invalid_trade_count`
- `redundant_info_call_count`
- `unnecessary_tool_call_count`
- `no_tool_call_count`
- `report_element_presence`
- `report_element_accuracy`
- `report_element_verdicts`
- `judge_raw_response`

Interpretation note:

- `on_course_realized_trade_value` and `required_course_optimal_trade_value` are the primary trading-score fields
- `off_course_trade_value` and `realized_pnl_vs_required_course_optimal` are optional secondary diagnostics for whole-trip accounting and debugging

## Leaderboard Aggregation Contract

Per-run:

- compute and store `primary_score_100`
- compute and store `task_complete`

Per-model/config group:

- `primary_score_100_median`
- `task_complete_rate`
- `trade_quality_score_median`
- `path_efficiency_score_median`
- `tool_discipline_score_median`
- `report_quality_score_median`
- `turn_p50_ms`
- `turn_p90_ms`
- `total_time_p50_s`

Recommended human-facing summary table:

- `Model`
- `N`
- `Primary /100`
- `Task Complete %`
- `Trade /15`
- `Path /15`
- `Tools /15`
- `Report /15`
- `Turn P50 (ms)`
- `Turn P90 (ms)`
- `Total Time P50 (s)`

Recommended primary leaderboard sort:

1. `primary_score_100_median` descending
2. `task_complete_rate` descending
3. `total_time_p50_s` ascending

Why median first:

- it is more robust to one-off collapses or one-off hero runs
- it better reflects typical run quality in a 20-run batch

Grouping rule:

- each leaderboard covers exactly one prompt definition
- built-in prompt leaderboards are keyed by `(task_variant, task_prompt_version)`
- custom prompt leaderboards are keyed by `task_prompt_hash`
- do not combine natural and literal runs in the same leaderboard
- create a custom-prompt leaderboard only when the same custom prompt is used for more than one run

## Concrete Failure Modes The Score Should Distinguish

The new rubric should separate:

- clean optimal run
- clean but low-profit run
- route success with inaccurate final summary
- route success with noisy tool discipline
- reached mega and recharged, but did not return home
- returned home without valid recharge
- got stuck in no-tool narration
- got trapped in invalid trade or invalid move loops
- premature `finished`

A single binary completion flag would only separate some of these.

## Implementation Notes

### Prompt Implementation

Add named built-in task instructions rather than relying on ad hoc string overrides.

Recommended interface:

- `default` or `natural`
- `small` or `literal`

Recommended CLI shape:

- `--task-variant natural|literal`
- if both `--task` and `--task-variant` are passed, `--task` should win
- if only `--task-variant` is passed, resolve the prompt from the built-in task map
- if `--task` is passed, stamp `task_variant=custom`

The harness should stamp both:

- task label
- built-in prompt version when applicable
- task prompt hash

This keeps leaderboard grouping explicit.

Evaluator and leaderboard grouping should:

- treat leaderboard scope as prompt-specific, not cross-prompt
- build one leaderboard for `natural`
- build one leaderboard for `literal`
- build one leaderboard per repeated custom prompt hash
- reject mixed-prompt input when generating a single leaderboard table

Canonical maintained output files for the built-in prompts:

- `port-to-port/leaderboards/leaderboard-natural.md`
- `port-to-port/leaderboards/leaderboard-literal.md`

Those filenames should stay stable.
Prompt version and rubric version belong in the file metadata/header, not in the canonical filename.

### Scoring Implementation

Use a hybrid evaluator:

- programmatic scoring for navigation, recharge, tool correctness, move efficiency, and required-course trading metrics
- LLM judging for final-report completeness and semantic correctness

Potential new helper components:

- required-course trade oracle
- extra-move classifier
- unnecessary-tool-call classifier
- richer report-element judge output
- active-phase classifier

Recommended helper signatures:

- `_extract_phase_timeline(payload) -> list[PhaseSpan]`
- `_compute_on_course_realized_trade_value(payload) -> int`
- `_compute_required_course_optimal_trade_value(payload) -> OracleResult`
- `_count_unnecessary_tool_calls(payload) -> ToolDisciplineCounts`
- `_judge_report_elements(...) -> ReportJudgeVerdict`

## Provisional V1 Decisions

These should be treated as implementation defaults unless we explicitly revise the rubric later.

### 1. Off-Course Detours

- off-course detours should be penalized in path efficiency even if they happen to be profitable
- off-course profit should not increase trade score
- use the V1 detour rule above rather than ad hoc human interpretation

### 2. Beneficial Opportunity Definition

- derive this from the required-course oracle rather than hand-written heuristics
- if the oracle uses a required-course trade opportunity in its optimal policy, skipping it counts against coverage

### 3. Harmful But Valid Trades

- harmful but valid trades should hurt trade quality first
- off-course but valid trades should not improve trade quality
- they should not also count as tool-discipline failures unless they are obviously repeated, pointless, and do not improve information state

### 4. Unnecessary Tool Calls

- track `unnecessary_tool_call_count` as the umbrella scored field
- track `redundant_info_call_count` as a diagnostic subset
- apply penalties per occurrence, but at low weight

## Proposed Next Steps

1. Add the second built-in small-model task prompt and expose prompt labels in run metadata.
2. Add `--task-variant natural|literal`, with `--task` overriding when both are supplied.
3. Write `docs/scoring-notes.md` for the new subscore fields, judge prompts, and observed failure patterns.
4. Implement required-course trade-optimality scoring.
5. Add `primary_score_100` plus subscores to `evaluate_runs.py`.
6. Update leaderboard generation so each output table is scoped to exactly one prompt.
7. Re-score a mixed sample of strong, middling, and weak models to check whether the rubric spreads models across the full scale instead of bunching them together.
