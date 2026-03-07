# Scoring Notes

This document translates the planning rubric into implementation-facing notes.

Related doc:

- [prompt-and-primary-score-plan.md](./prompt-and-primary-score-plan.md)

## Purpose

The new primary score should:

- preserve task-completion pressure
- separate excellent, middling, and poor runs
- avoid double-penalizing the same underlying mistake
- remain interpretable from stored run artifacts

This document records the observed failure patterns from representative runs and defines the categories we want the evaluator to score.

## Data Contract

An implementation from scratch should assume `mini_rl_run.v3` input and rely on these fields first:

- `metadata.initial_state`
- `metadata.task_prompt_hash`
- `metadata.task_prompt_version` for built-in prompts
- `metadata.task_variant`
- `summary`
- `termination`
- `turns[*].tool_calls`
- `turns[*].state_before`
- `turns[*].state_after`
- `turns[*].bad_action_increment`

Everything else should be derived from those fields where possible.

Evaluator outputs should also stamp `score_rubric_version` so rescoring and leaderboard grouping stay explicit when the rubric changes.
Evaluator outputs should also stamp `leaderboard_prompt_id` so summary tables can stay single-prompt by construction.

Minimum clean-room artifact requirements:

- per run:
  - start sector
  - initial credits
  - initial cargo by commodity
  - cargo capacity
  - target mega-port sector used for first-destination judging
  - final credits
  - final sector
  - recharge-to-full truth at a mega-port
  - finished-message text, if any
- per turn:
  - turn index
  - tool calls in order, with normalized args and result status
  - pre-turn and post-turn state
  - bad-action increment

If a fresh implementation cannot preserve `mini_rl_run.v3` exactly, it should still preserve those semantics.

## Representative Patterns

Observed strong pattern:

- complete route execution
- recharge at the correct mega-port
- no bad actions
- limited info calls
- profitable multi-hop trading
- accurate and internally consistent finished message

Observed middling pattern:

- route completion is often correct
- recharge is often correct
- trading is valid but not especially strong
- some invalid calls occur
- final summary may be contradictory or numerically wrong even when the route is complete

Observed poor-but-valid pattern:

- premature `finished` before final objective completion
- repeated invalid trade attempts
- failure to recover after local mistakes
- exhausting turns after partial success
- coherent-looking summary without actual completion

## Taxonomy Of What We Want To Score

The rubric should separate these dimensions:

1. Did the model complete the route objectives?
2. Did it trade well on the required course?
3. Did it move efficiently?
4. Did it use tools correctly and economically?
5. Did it produce a correct final message?

That yields the five score families from the planning doc:

- mission completion
- trade quality
- path efficiency
- tool discipline
- final report quality

V1 weight split:

- mission completion: 40
- trade quality: 15
- path efficiency: 15
- tool discipline: 15
- final report quality: 15

Human-facing summary metric:

- `task_complete` is the one binary completion metric we should surface in summary tables
- `task_complete` means: reached the mega-port, recharged to full, returned to the start sector, and first `finished` happened only after those conditions were satisfied

## Mission Completion Notes

This category should be high-weight and simple.

V1 weighting note:

- mission completion is the heaviest category at 40 points

Important distinctions:

- reached mega-port vs never reached mega-port
- reached mega-port but did not recharge
- recharged but did not get home
- got home but called `finished` at the wrong time

Implementation note:

- `finished_called=true` should not by itself earn completion points
- the model only earns the final-timing points if the route conditions are already satisfied when `finished` is called

`finished_at_correct_time` should mean:

- `finished_called == true`
- the first `finished` call occurs after:
  - first arrival at the mega-port
  - successful recharge to full at the mega-port
  - first return to the start sector

Ground-truth accounting definitions used by scoring and report judging:

- `distinct_ports_traded` means the number of unique sectors with at least one successful `trade`
- `total_profit_credits` means `final_credits - initial_credits`
- `total_profit_credits` is whole-trip credits delta, not trade-only profit

## Trade Quality Notes

Trade quality should use required-course optimality as the primary measure.

V1 weighting note:

- trade quality is intentionally lower-weight than mission because off-course route creativity is no longer part of the score

Two separate things matter:

1. Trade coverage
2. Trade execution quality

### Trade Coverage

Question:

- when the model reached a required-course port visit where a beneficial trade was available, did it take that opportunity?

This should not be scored with naive "did any trade happen?" logic.

Instead:

- compute the required-course oracle policy
- identify the beneficial required-course opportunities the oracle actually uses
- compare model behavior to that opportunity set

V1 coverage counting rule:

- count a beneficial required-course opportunity at the port-visit level, not just the sector level
- a port visit counts as captured if the model made at least one successful `trade` on that same oracle-used required-course visit

This avoids arbitrary hand-written definitions of "should have traded here."

### Trade Execution

Question:

- given the benchmark's required course, how much of the available trade value did it capture without going off-course?

Implementation note:

- use required-course optimum for primary score
- keep global optimum as a secondary diagnostic only

Definitions:

`on_course_realized_trade_value`

- net credits gained or lost from successful `trade` calls at required-course port visits only
- do not include recharge cost, movement cost, or other non-trade costs
- off-course trades do not increase this value

`required_course_optimal_trade_value`

- maximum achievable `on_course_realized_trade_value` on the benchmark's canonical required-course port sequence and visit order

`off_course_trade_value`

- net credits gained or lost from successful `trade` calls outside required-course port visits
- diagnostic only; this should not increase trade score

`required_course_trade_gap`

- `required_course_optimal_trade_value - on_course_realized_trade_value`
- diagnostic only; useful for inspecting how much on-course trade value the run left on the table

Oracle implementation rule:

- implement this as a dynamic program over the required-course port sequence
- oracle state should include at least:
  - visit index
  - credits
  - cargo inventory by commodity
  - remaining free holds
- the oracle may choose any valid buy, sell, or skip action at a required-course port visit
- the oracle may not change route, visit order, recharge behavior, or any non-trade world event
- in the current synthetic world the required course is unique; if a future environment introduces tied shortest valid courses, add a canonical tie-breaker and version the benchmark explicitly

Edge case:

- if `required_course_optimal_trade_value <= 0`, do not use the normal ratio bands
- in that case:
  - award full trade-execution credit if `on_course_realized_trade_value >= 0`
  - otherwise treat the run as having made harmful trade choices

## Path Efficiency Notes

Path efficiency should score route compliance and efficiency. Profitable off-course detours should still be penalized.

V1 weighting note:

- path efficiency has the same weight as trade quality because staying on the required course is part of task execution, not just a small cleanup penalty

We want to distinguish:

- shortest sensible route
- slightly inefficient but still reasonable route
- wandering
- repeated backtracking loops

### Definitions

`extra_moves_count`

- moves beyond the minimum required for the benchmark's canonical shortest round trip

`avoidable_backtrack_count`

- repeated sector revisits that do not appear necessary for:
  - reaching the mega-port
  - returning home
  - recovering from direct mission progress on the required course

Path-efficiency phase segmentation:

- outbound phase: start until first arrival at the mega-port
- recharge phase: turns at the mega-port before recharge is completed
- return phase: first post-mega move until first return to start sector
- post-objective phase: any turns after returning home but before `finished`

`extra_moves_count` should be measured against the active phase objective:

- outbound objective: reduce distance to mega-port
- return objective: reduce distance to start sector
- post-objective objective: finish immediately

V1 detour rule:

- any move that leaves the canonical shortest round-trip course counts as extra movement
- pure oscillations such as `A -> B -> A` count as avoidable backtracking unless `B` contributed direct mission progress

Representative cases:

- efficient route with strong on-course trading
- noisy but recoverable route
- premature finish with incomplete return leg

Implementation note:

- path score should answer "how efficiently did the model pursue the objective it was on?"
- it should not re-score trade quality

## Tool Discipline Notes

This is the main penalty bucket for operational sloppiness.

We should score per occurrence, not once per category.

Important because:

- one invalid trade is a small mistake
- eighteen invalid trades is a collapse

Representative failure shape:

- repeated invalid `trade` attempts and occasional hallucinated side actions can drive `bad_actions_count` into the high teens

### Definitions

`hallucinated_tool_count`

- tool call names not in the benchmark catalog
- or impossible calls that clearly do not belong to the benchmark action space

`incorrect_tool_arg_count`

- tool calls to a valid tool with incorrect or self-defeating arguments that produce failure
- examples:
  - invalid trade direction
  - selling zero quantity
  - buying impossible quantity

`invalid_move_count`

- move calls rejected because the target is not valid from the current sector or otherwise fails movement rules

`invalid_trade_count`

- trade calls rejected because arguments are invalid or the trade is impossible in context

`no_tool_call_count`

- turns where the model emits no tool call

`unnecessary_tool_call_count`

- umbrella count of valid-but-avoidable tool calls that do not materially improve task state, information state, or score outcome

`redundant_info_call_count`

- subset of `unnecessary_tool_call_count`
- repeated information requests after the relevant information is already known

Examples of `redundant_info_call_count`:

- repeated `my_status` with no relevant state change
- repeated `load_game_info` for the same topic
- repeated route or port info requests after the answer is already in context

Examples of unnecessary but non-info calls:

- re-plotting the same route with no state change
- calling a valid but irrelevant tool
- making a side call that does not help either navigation or trade quality

Implementation note:

- keep both counts
- use `unnecessary_tool_call_count` for scoring
- keep `redundant_info_call_count` for diagnostics and breakdowns
- classify unnecessary calls conservatively; when uncertain, prefer not counting them

Scoring precedence rule:

- `incorrect_tool_arg_count` is diagnostic and should not add an extra deduction on top of `invalid_move_count` or `invalid_trade_count` for the same failed call
- each failed tool call should contribute to at most one primary tool-discipline deduction bucket

## Final Report Quality Notes

Final report quality should remain split into:

1. presence of required elements
2. correctness of required elements

Required elements:

- mega-port used
- recharge amount
- recharge cost
- number of distinct ports traded
- whole-trip total profit or loss

Representative cases:

- strong report
- contradictory report despite route success

Important distinction:

- a summary can be coherent-sounding but still numerically wrong
- that should score much better than a missing summary, but worse than a correct one

Implementation note:

- keep semantic flexibility in the judge
- return per-element verdicts, not just PASS/FAIL

Target judge schema:

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

Operational rules:

- if `finished` was never called, do not invoke the LLM judge; set all elements to `present=false`, `accurate=false`
- if the judge returns malformed JSON or `UNSURE`, mark `overall_accuracy=false` and preserve the raw judge response
- `accurate=true` is only valid when `present=true`

V1 scoring reminder:

- element presence is worth 1 point each
- element correctness is worth 2 points each

## Penalty Philosophy

The score should be expressive, but not chaotic.

Recommended pattern:

- additive points for mission completion and trade quality
- deduction buckets for path efficiency and tool discipline

Reason:

- task completion and trading are positive achievements
- wasted moves and sloppy tool use are better modeled as penalties against otherwise successful behavior

## Worked Interpretations

These are not exact frozen scores yet. They are interpretation targets for the final rubric.

### Strong Run

Expected shape:

- near-max mission completion
- near-max trade quality
- near-max path efficiency
- full or near-full tool discipline
- full report score

Expected band:

- roughly `90-100`

### Middling Run

Expected shape:

- strong mission completion
- middling trade quality
- some tool-discipline deductions
- correct but not especially strong report

Expected band:

- roughly `55-80`

### Route Success But Bad Report

Expected shape:

- high mission completion
- non-zero trade score
- non-zero tool-discipline score
- substantial report-quality deductions

Expected band:

- clearly below a comparable clean success

### Premature Finish

Expected shape:

- some completion credit for reaching mega and recharging
- zero return-home credit
- zero correct-finish-timing credit
- some report credit if the summary is present and semantically coherent

This run should score above a total collapse, but far below a true success.

### Tool-Use Collapse

Expected shape:

- some completion credit because mega-port and recharge were reached
- low trade-quality score despite many trade attempts
- heavy tool-discipline deductions from repeated invalid trades
- low or zero final-report score because `finished` was never called

This is the canonical example of why per-occurrence tool penalties matter.

## Implementation Notes

Evaluator code should prefer storing raw counts and raw diagnostic values first.

Examples:

- store `invalid_trade_count`
- store `redundant_info_call_count`
- store `on_course_realized_trade_value`
- store `required_course_optimal_trade_value`
- store `off_course_trade_value`
- store `required_course_trade_gap`
- store `score_rubric_version`

Then derive:

- `tool_discipline_score`
- `trade_quality_score`
- `primary_score_100`

This will make the score easier to inspect, tune, and backfill on existing runs.

Storage recommendation:

- store raw counts and oracle outputs in `enriched_runs.jsonl`
- store derived subscores alongside them
- keep primary-score computation pure and reproducible from the stored raw fields

Leaderboard recommendation:

- the human-facing summary table should surface `primary_score_100`, `task_complete_rate`, subscore medians for trade/path/tools/report, and timing columns
- it should not surface extra boolean report-accuracy columns as primary summary metrics
- each leaderboard should cover exactly one prompt definition
- maintain separate summary tables for `natural`, `literal`, and any repeated custom prompt
- leaderboard generation should fail fast if the input run set contains more than one leaderboard prompt id
- the canonical maintained markdown outputs should be `port-to-port/leaderboards/leaderboard-natural.md` and `port-to-port/leaderboards/leaderboard-literal.md`

## Immediate Implementation Targets

1. Add built-in prompt variants and persist `task_variant` plus `task_prompt_version`
2. Add `docs/scoring-notes.md` to the implementation sequence
3. Implement required-course trade oracle
4. Add raw count fields needed for:
   - unnecessary tool calls
   - redundant info calls
   - avoidable backtracks
   - extra moves
5. Add per-element report verdicts from the judge
6. Combine those into subscores, `primary_score_100`, `task_complete`, and a prompt-specific leaderboard key
