# Prompt And Primary Score Plan

## Goals

We want two changes to the port-to-port benchmark:

1. Keep a natural default task instruction that reflects how capable-model users talk to agents.
2. Add a second, more literal task instruction for small models.
3. Replace `strict_success` as the primary leaderboard metric with a richer score that captures more of the performance variation we actually care about.

The same core task should remain unchanged across both prompts:

- navigate from the start sector to the nearest mega-port
- recharge to full at the mega-port
- trade opportunistically along the way
- return to the start sector
- provide a finished message with the required elements

## Current State

Current default task text in [mini-rl-env.py](/Users/khkramer/src/gb-benchmarks/port-to-port/mini-rl-env.py) is intentionally natural:

> Go round-trip from our current location to the nearest mega-port. At the mega-port, recharge to full warp power. While traveling there and back, trade at every port that provides a trading opportunity. Make as much money as possible. Be sure you know how to trade well. When you're back where you started, give me a quick summary with the mega-port you used, how much warp you recharged and what it cost, how many ports you traded at, and total profit from the whole trip.

Current primary pass/fail columns are still centered on:

- `objective_success`
- `lenient_success`
- `strict_success`

This is too coarse for top models. It distinguishes catastrophic failures from clean completions, but it does not separate:

- clean but low-profit runs
- efficient vs wasteful navigation
- smart trading vs merely valid trading
- exact vs contradictory final reports
- disciplined vs sloppy tool use

## Observed Run Patterns

Representative successful runs:

- [sonnet46-medium-r10.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/data-collection-20260226T070342Z/json/sonnet46-medium-r10.json)
- [sonnet46-medium-r02.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/data-collection-20260226T070342Z/json/sonnet46-medium-r02.json)

Representative middling Nemotron 3 Super runs:

- [run-05.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/nemotron3-super-120b-th512-20x-20260305T225007Z/run-05.json)
- [run-14.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/nemotron3-super-120b-th512-20x-20260305T225007Z/run-14.json)

Representative poor but benchmark-valid runs:

- [run-001.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/supernova-low-20-batch4-20260226T234711Z/run-001.json)
- [run-008.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/gpt-5-mini-20x3-batch12-instrfix-20260227T185757Z/minimal/run-008.json)

Patterns from those runs:

- Strong Claude runs do more than finish. They infer profitable trade chains, take productive detours, avoid bad actions, and produce clean summaries with correct whole-trip accounting.
- Middling Nemotron runs often complete the route and recharge correctly, but leave profit on the table, make a few invalid or unnecessary calls, or produce contradictory summaries.
- Poor runs fall into a few distinct buckets:
  - premature `finished` before returning home
  - repeated invalid or low-value trades
  - verbose planning without tool calls
  - max-turn exhaustion after completing only part of the task
  - correct route execution but incorrect final accounting

These differences are too important to collapse into a single strict boolean.

## Prompt Split Proposal

### Prompt A: Natural Prompt

Keep the current default prompt as the large-model / natural-user prompt.

This prompt is valuable because:

- it matches how users naturally speak to high-capability agents
- it rewards planning, abstraction, and implicit checklist-following
- it exposes whether a model can infer missing operational structure

### Prompt B: Literal Small-Model Prompt

Add a second built-in task instruction designed for smaller or less agentically reliable models.

Draft text:

```text
Go from your current sector to the nearest mega-port, then return to the sector where you started.

Follow these rules exactly:
1. First identify the nearest mega-port sector that is not your current sector.
2. Plot a route to that mega-port.
3. Move one sector at a time along that route.
4. On the way to the mega-port, if the current sector has a valid trading opportunity, trade there.
5. When you arrive at the mega-port, recharge warp power to full.
6. Then plot a route back to your starting sector.
7. Move one sector at a time along the route back.
8. On the way back, if the current sector has a valid trading opportunity, trade there.
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

These identifiers and field names should be treated as stable unless we intentionally version the benchmark again.

Prompt variant ids:

- `natural`
- `literal`
- `custom`

Expected harness metadata/config fields:

- `metadata.task_variant`
- `metadata.task_prompt_hash`
- `config.task_variant`

Resolution rules:

- if `--task` is provided, it overrides `--task-variant`
- if `--task` is not provided, `--task-variant` selects a built-in prompt
- if `--task` is provided, the run should store `task_variant=custom`
- if an older run does not contain `task_variant`, downstream code should fall back to `task_prompt_hash`

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

Keep existing booleans as supporting columns:

- `objective_success`
- `lenient_success`
- `strict_success`

But define a new primary metric:

- `primary_score_100`

This score should be comparable across both prompt variants.

### Design Principles

- The score should reward real task completion first.
- It should distinguish mediocre from excellent runs.
- It should combine programmatic scoring and judged scoring.
- It should penalize wasted or incorrect behavior without letting one small mistake dominate the full score.
- It should not require special-case scoring for the natural vs literal prompt.

## Proposed Score Structure

### 1. Mission Completion: 35 points

- Reach the first required destination (nearest mega-port): 10
- Recharge to full at the mega-port: 10
- Return to the required final destination (start sector): 10
- Call `finished` only after satisfying the route completion conditions: 5

Why 35:

- This remains the backbone of the task.
- Runs that miss these checkpoints should not be competitive even if they trade well.

### 2. Trade Quality: 25 points

- Trade opportunity coverage on visited route: 10
- Commodity-choice quality / realized trade value quality: 15

Recommended implementation split:

- `trade_coverage_score`
  - did the run actually trade when a valid opportunity existed?
  - did it skip obviously beneficial trades?
- `trade_quality_score`
  - compare realized trade value against a route-conditioned oracle optimum
  - do not compare only raw profit across different realized routes

Why route-conditioned optimum:

- It is fairer than comparing to a global omniscient optimum.
- It isolates trading quality from navigation quality.
- It still gives strong models room to separate themselves by choosing better commodities and cargo transitions.

Formal definition:

- Fix the model's actual visited port sequence and visit order.
- Fix the actual starting state:
  - credits
  - cargo
  - cargo capacity
  - sector
- Fix the actual non-trade world events:
  - movement path
  - recharge event and recharge cost
  - any mandatory benchmark actions already taken
- Define `realized_trade_value` as the net credits gained or lost from successful `trade` calls only.
- Then compute `route_conditioned_optimal_trade_value` for a perfect trader who is only allowed to choose different `trade` actions at the ports actually visited, in the order actually visited.
- Trade scoring compares `realized_trade_value` to `route_conditioned_optimal_trade_value`, not whole-trip profit after recharge.

Oracle implementation rule:

- the oracle should be a dynamic program over the visited-port sequence
- oracle state should include at least:
  - current visit index
  - credits
  - cargo inventory by commodity
  - remaining free holds
- allowed actions at each visited port should be:
  - any valid buy, sell, or skip action permitted by benchmark trade rules at that port
- invalid or impossible trade actions from the original run do not constrain the oracle; only the visited route and visit order constrain it

This means the oracle may optimize trading decisions, but it may not:

- invent a different route
- insert extra ports
- reorder visits
- assume access to opportunities the run never reached

Worked example:

- If a run visits `3080 -> 4874 -> 1611 -> 2831 -> 3080`, the oracle may optimize trades across that exact sequence.
- It may decide that the best route-conditioned plan is:
  - sell QF at 3080
  - buy RO at 4874
  - skip a bad buy at 1611
  - sell RO and buy NS at 2831
  - sell NS at 3080
- But it may not add a profitable detour to sector `1928` unless the model actually visited `1928`.

Scoring implication:

- navigation quality should answer whether the model chose a strong route
- trade quality should answer whether the model traded well on the route it chose

Keep a secondary diagnostic:

- `global_profit_gap`

That captures strategic route quality without double-penalizing navigation inside the trade score.

Edge case:

- if `route_conditioned_optimal_trade_value <= 0`, do not use the normal ratio bands
- in that case:
  - award full trade-execution credit if `realized_trade_value >= 0`
  - otherwise treat the run as having made harmful trade choices and assign a low trade-execution score

## 3. Path Efficiency: 10 points

- shortest-path efficiency to first destination: 5
- shortest-path efficiency on the return leg: 5

This category should allow some profitable detours without flattening all non-shortest routes into failures.

Recommended implementation:

- score against shortest-path baseline
- forgive detours that produce measurable trade gain
- penalize repeated backtracking and wandering after goals are known

Phase segmentation for path scoring:

- outbound phase: from start until first arrival at the chosen mega-port
- recharge phase: turns at the mega-port before recharge is completed
- return phase: from the first post-mega move until first arrival back at the start sector
- post-objective phase: any turns after the model has already returned home but before `finished`

`extra_moves_count` should always be counted against the current phase objective:

- outbound objective: reduce distance to mega-port
- return objective: reduce distance to start sector
- post-objective objective: finish immediately

Profitable detours are allowed only if they produce clear trade value according to the route-conditioned oracle.

V1 detour rule:

- forgive extra movement only when the move lies on a shortest path to a later visited port that the route-conditioned oracle uses for positive trade value
- pure oscillations such as `A -> B -> A` count as avoidable backtracking unless `B` was needed for positive oracle-used trade value or direct mission progress

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

Backward-compatibility rule:

- `strict_success` should continue to use the existing overall `report_accuracy` boolean
- the new per-element fields should be additive outputs, not breaking changes

Total: 100 points

## V1 Scoring Formula

This is the formula a fresh implementation should use. If we retune it later, we should version the rubric rather than reinterpret these constants.

### Mission Completion: 35

- `mission_completion_score = 10 * reached_first_destination + 10 * recharged_to_full + 10 * returned_to_final_destination + 5 * finished_at_correct_time`

### Trade Quality: 25

Trade coverage: 10

Define:

- `beneficial_visited_opportunity_count =` number of visited port occurrences used by the route-conditioned oracle for positive trade value
- `captured_beneficial_opportunity_count =` number of those port occurrences where the model executed at least one successful `trade`
- if `beneficial_visited_opportunity_count == 0`, set `trade_coverage_score = 10`
- otherwise compute `trade_coverage_rate = captured_beneficial_opportunity_count / beneficial_visited_opportunity_count`

Then score:

- 10: `trade_coverage_rate == 1.0`
- 7: `0.75 <= trade_coverage_rate < 1.0`
- 4: `0.25 <= trade_coverage_rate < 0.75`
- 0: `trade_coverage_rate < 0.25`

Trade execution vs route-conditioned optimum: 15

- 15: at least 90% of route-conditioned optimal trade value
- 12: 75% to 89%
- 8: 50% to 74%
- 4: 25% to 49%
- 0: below 25%

Use:

- `trade_execution_ratio = realized_trade_value / route_conditioned_optimal_trade_value`

only when `route_conditioned_optimal_trade_value > 0`.

Set:

- `trade_quality_score = trade_coverage_score + trade_execution_score`

### Path Efficiency: 10

Start at 10 and deduct:

- minus 1 for each unnecessary move after the correct route is already known, cap 6
- minus 2 for each avoidable backtracking loop, cap 4

Profitable detours should not be penalized automatically.

Formula:

- `path_efficiency_score = max(0, 10 - min(extra_moves_count, 6) - min(2 * avoidable_backtrack_count, 4))`

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
- `path_efficiency_score = 10 - penalties`, floor at 0

This avoids making the rubric too brittle while still reflecting visible sloppiness.

## Suggested Subscores

Recommended output columns / JSON fields:

- `primary_score_100`
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
- `realized_trade_value`
- `route_conditioned_optimal_profit`
- `route_conditioned_optimal_trade_value`
- `route_conditioned_profit_gap`
- `realized_pnl_vs_route_optimal`
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

- `realized_trade_value` and `route_conditioned_optimal_trade_value` are the primary trading-score fields
- `route_conditioned_optimal_profit` and `realized_pnl_vs_route_optimal` are optional secondary diagnostics for whole-trip accounting

## Leaderboard Aggregation Contract

Per-run:

- compute and store `primary_score_100`

Per-model/config group:

- `primary_score_100_median`
- `primary_score_100_mean`
- existing success-rate fields remain available:
  - `strict_success_rate`
  - `lenient_success_rate`
  - `objective_success_rate`

Recommended primary leaderboard sort:

1. `primary_score_100_median` descending
2. `strict_success_rate` descending
3. `avg_time_s` ascending

Why median first:

- it is more robust to one-off collapses or one-off hero runs
- it better reflects typical run quality in a 20-run batch

Backward-compatibility rule:

- older runs without `task_variant` should still be groupable via `prompt_hash`
- newer runs should group by explicit `task_variant` first

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

Current `strict_success` only separates some of these.

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
- task prompt hash

This keeps leaderboard grouping explicit.

Evaluator and leaderboard grouping should:

- prefer `task_variant` when present
- fall back to `prompt_hash` for older runs that do not have a variant label

### Scoring Implementation

Use a hybrid evaluator:

- programmatic scoring for navigation, recharge, tool correctness, move efficiency, and route-conditioned trading metrics
- LLM judging for final-report completeness and semantic correctness

Potential new helper components:

- route-conditioned trade oracle
- extra-move classifier
- unnecessary-tool-call classifier
- richer report-element judge output
- active-phase classifier

Recommended helper signatures:

- `_extract_phase_timeline(payload) -> list[PhaseSpan]`
- `_compute_realized_trade_value(payload) -> int`
- `_compute_route_conditioned_optimal_trade_value(payload) -> OracleResult`
- `_count_unnecessary_tool_calls(payload) -> ToolDisciplineCounts`
- `_judge_report_elements(...) -> ReportJudgeVerdict`

## Provisional V1 Decisions

These should be treated as implementation defaults unless we explicitly revise the rubric later.

### 1. Beneficial Detours

- penalize detours only when they do not produce mission progress or positive route-conditioned trade value
- use the V1 detour rule above rather than ad hoc human interpretation

### 2. Beneficial Opportunity Definition

- derive this from the route-conditioned oracle rather than hand-written heuristics
- if the oracle uses a visited trade opportunity in its optimal policy, skipping it counts against coverage

### 3. Harmful But Valid Trades

- harmful but valid trades should hurt trade quality first
- they should not also count as tool-discipline failures unless they are obviously repeated, pointless, and do not improve information state

### 4. Unnecessary Tool Calls

- track `unnecessary_tool_call_count` as the umbrella scored field
- track `redundant_info_call_count` as a diagnostic subset
- apply penalties per occurrence, but at low weight

## Proposed Next Steps

1. Add the second built-in small-model task prompt and expose prompt labels in run metadata.
2. Add `--task-variant natural|literal`, with `--task` overriding when both are supplied.
3. Write `docs/scoring-notes.md` for the new subscore fields, judge prompts, and observed failure patterns.
4. Implement route-conditioned trade-optimality scoring.
5. Add `primary_score_100` plus subscores to `evaluate_runs.py`.
6. Update leaderboard grouping to prefer `task_variant` over raw prompt hash where possible.
7. Re-score a mixed sample of Claude, Nemotron, and weaker models to check whether the rubric spreads models across the full scale instead of bunching them together.
