# Scoring Notes

This document translates the planning rubric into implementation-facing notes.

Related doc:

- [prompt-and-primary-score-plan.md](/Users/khkramer/src/gb-benchmarks/port-to-port/docs/prompt-and-primary-score-plan.md)

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
- `metadata.task_variant` when present
- `summary`
- `termination`
- `turns[*].tool_calls`
- `turns[*].state_before`
- `turns[*].state_after`
- `turns[*].bad_action_increment`

Everything else should be derived from those fields where possible.

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

## Representative Runs

Strong runs:

- [sonnet46-medium-r10.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/data-collection-20260226T070342Z/json/sonnet46-medium-r10.json)
- [sonnet46-medium-r02.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/data-collection-20260226T070342Z/json/sonnet46-medium-r02.json)

Observed pattern:

- complete route execution
- recharge at the correct mega-port
- no bad actions
- limited info calls
- profitable multi-hop trading
- accurate and internally consistent finished message

Middling runs:

- [run-05.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/nemotron3-super-120b-th512-20x-20260305T225007Z/run-05.json)
- [run-14.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/nemotron3-super-120b-th512-20x-20260305T225007Z/run-14.json)

Observed pattern:

- route completion is often correct
- recharge is often correct
- trading is valid but not especially strong
- some invalid calls occur
- final summary may be contradictory or numerically wrong even when the route is complete

Poor but benchmark-valid runs:

- [run-001.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/supernova-low-20-batch4-20260226T234711Z/run-001.json)
- [run-008.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/gpt-5-mini-20x3-batch12-instrfix-20260227T185757Z/minimal/run-008.json)

Observed pattern:

- premature `finished` before final objective completion
- repeated invalid trade attempts
- failure to recover after local mistakes
- exhausting turns after partial success
- coherent-looking summary without actual completion

## Taxonomy Of What We Want To Score

The rubric should separate these dimensions:

1. Did the model complete the route objectives?
2. Did it trade well on the path it actually took?
3. Did it move efficiently?
4. Did it use tools correctly and economically?
5. Did it produce a correct final message?

That yields the five score families from the planning doc:

- mission completion
- trade quality
- path efficiency
- tool discipline
- final report quality

## Mission Completion Notes

This category should be high-weight and simple.

Important distinctions:

- reached mega-port vs never reached mega-port
- reached mega-port but did not recharge
- recharged but did not get home
- got home but called `finished` at the wrong time

Representative examples:

- clean success: [sonnet46-medium-r10.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/data-collection-20260226T070342Z/json/sonnet46-medium-r10.json)
- premature-finish failure: [run-001.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/supernova-low-20-batch4-20260226T234711Z/run-001.json)

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

Trade quality should use route-conditioned optimality as the primary measure.

Two separate things matter:

1. Trade coverage
2. Trade execution quality

### Trade Coverage

Question:

- when the model visited a port where a beneficial trade was available on its actual route, did it take that opportunity?

This should not be scored with naive "did any trade happen?" logic.

Instead:

- compute the route-conditioned oracle policy
- identify the beneficial visited opportunities the oracle actually uses
- compare model behavior to that opportunity set

V1 coverage counting rule:

- count a beneficial visited opportunity at the port-visit level, not just the sector level
- a port visit counts as captured if the model made at least one successful `trade` on that same oracle-used visit

This avoids arbitrary hand-written definitions of "should have traded here."

### Trade Execution

Question:

- given the route and visit order the model actually chose, how much of the available trade value did it capture?

Representative examples:

- strong execution: Claude Sonnet runs, especially [sonnet46-medium-r02.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/data-collection-20260226T070342Z/json/sonnet46-medium-r02.json)
- middling execution: [run-05.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/nemotron3-super-120b-th512-20x-20260305T225007Z/run-05.json)
- collapse after partial success: [run-008.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/gpt-5-mini-20x3-batch12-instrfix-20260227T185757Z/minimal/run-008.json)

Implementation note:

- use route-conditioned optimum for primary score
- keep global optimum as a secondary diagnostic only

Definitions:

`realized_trade_value`

- net credits gained or lost from successful `trade` calls only
- do not include recharge cost, movement cost, or other non-trade costs

`route_conditioned_optimal_trade_value`

- maximum achievable `realized_trade_value` on the model's actual visited port sequence and visit order

Oracle implementation rule:

- implement this as a dynamic program over the visited-port sequence
- oracle state should include at least:
  - visit index
  - credits
  - cargo inventory by commodity
  - remaining free holds
- the oracle may choose any valid buy, sell, or skip action at a visited port
- the oracle may not change route, visit order, recharge behavior, or any non-trade world event

Edge case:

- if `route_conditioned_optimal_trade_value <= 0`, do not use the normal ratio bands
- in that case:
  - award full trade-execution credit if `realized_trade_value >= 0`
  - otherwise treat the run as having made harmful trade choices

## Path Efficiency Notes

Path efficiency should score route quality without wiping out profitable detours.

We want to distinguish:

- shortest sensible route
- slightly inefficient but still reasonable route
- wandering
- repeated backtracking loops

### Definitions

`extra_moves_count`

- moves beyond the minimum required for the route actually being attempted, excluding moves that clearly produced value through trade or goal progress

`avoidable_backtrack_count`

- repeated sector revisits that do not appear necessary for:
  - reaching the mega-port
  - returning home
  - taking a clearly profitable trade detour

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

- forgive an extra move only when it lies on a shortest path to a later visited port that the route-conditioned oracle uses for positive trade value
- pure oscillations such as `A -> B -> A` count as avoidable backtracking unless `B` contributed direct mission progress or positive oracle-used trade value

Representative examples:

- efficient route with profitable detour: Claude Sonnet runs
- noisy but recoverable route: Nemotron middling runs
- premature finish with incomplete return leg: [run-001.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/supernova-low-20-batch4-20260226T234711Z/run-001.json)

Implementation note:

- path score should answer "how efficiently did the model pursue the objective it was on?"
- it should not re-score trade quality

## Tool Discipline Notes

This is the main penalty bucket for operational sloppiness.

We should score per occurrence, not once per category.

Important because:

- one invalid trade is a small mistake
- eighteen invalid trades is a collapse

Representative example:

- [run-008.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/gpt-5-mini-20x3-batch12-instrfix-20260227T185757Z/minimal/run-008.json) has repeated invalid `trade` attempts and one invalid `salvage_collect`, with `bad_actions_count=18`

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

Representative examples:

- strong report: [sonnet46-medium-r10.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/data-collection-20260226T070342Z/json/sonnet46-medium-r10.json)
- contradictory report despite route success: [run-14.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/nemotron3-super-120b-th512-20x-20260305T225007Z/run-14.json)

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

### Strong Claude Run

Example:

- [sonnet46-medium-r10.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/data-collection-20260226T070342Z/json/sonnet46-medium-r10.json)

Expected shape:

- near-max mission completion
- near-max trade quality
- near-max path efficiency
- full or near-full tool discipline
- full report score

Expected band:

- roughly `90-100`

### Middling Nemotron Run

Example:

- [run-05.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/nemotron3-super-120b-th512-20x-20260305T225007Z/run-05.json)

Expected shape:

- strong mission completion
- middling trade quality
- some tool-discipline deductions
- correct but not especially strong report

Expected band:

- roughly `55-80`

### Route Success But Bad Report

Example:

- [run-14.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/nemotron3-super-120b-th512-20x-20260305T225007Z/run-14.json)

Expected shape:

- high mission completion
- non-zero trade score
- non-zero tool-discipline score
- substantial report-quality deductions

Expected band:

- clearly below a comparable clean success

### Premature Finish

Example:

- [run-001.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/supernova-low-20-batch4-20260226T234711Z/run-001.json)

Expected shape:

- some completion credit for reaching mega and recharging
- zero return-home credit
- zero correct-finish-timing credit
- some report credit if the summary is present and semantically coherent

This run should score above a total collapse, but far below a true success.

### Tool-Use Collapse

Example:

- [run-008.json](/Users/khkramer/src/gb-benchmarks/port-to-port/runs/gpt-5-mini-20x3-batch12-instrfix-20260227T185757Z/minimal/run-008.json)

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
- store `realized_trade_value`
- store `route_conditioned_optimal_trade_value`

Then derive:

- `tool_discipline_score`
- `trade_quality_score`
- `primary_score_100`

This will make the score easier to inspect, tune, and backfill on existing runs.

Storage recommendation:

- store raw counts and oracle outputs in `enriched_runs.jsonl`
- store derived subscores alongside them
- keep primary-score computation pure and reproducible from the stored raw fields

## Immediate Implementation Targets

1. Add built-in prompt variants and persist `task_variant`
2. Add `docs/scoring-notes.md` to the implementation sequence
3. Implement route-conditioned trade oracle
4. Add raw count fields needed for:
   - unnecessary tool calls
   - redundant info calls
   - avoidable backtracks
   - extra moves
5. Add per-element report verdicts from the judge
6. Combine those into subscores and `primary_score_100`
