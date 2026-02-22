# Loop Logic (Switch-Style)

This document defines the synthetic environment handlers used by `mini-rl-env.py`.
Input to each handler is the model's most recent action output.
Output is one or more synthetic event/error lines appended back to model context.

## 1. Parse Step

Accepted model output forms:

1. JSON object with action name and args
   - `{"action":"move","args":{"to_sector":2266}}`
   - `{"name":"move","arguments":{"to_sector":2266}}`
2. Function-style call text
   - `move({"to_sector":2266})`
   - `trade({"commodity":"quantum_foam","quantity":10,"trade_type":"sell"})`

If parsing fails:
- Increment `BAD_ACTIONS_COUNT`.
- Emit synthetic parser error and continue.

## 2. Action Dispatch

Switch on action name:

- `list_known_ports`
- `plot_course`
- `move`
- `trade`
- `my_status`
- `local_map_region`
- `wait_in_idle_state`
- `load_game_info`
- `dump_cargo`
- `salvage_collect`
- `finished`

Any unknown action:
- Increment `BAD_ACTIONS_COUNT`.
- Emit generic synthetic error and continue.

## 3. Handler Rules

### `list_known_ports`
- Returns known ports filtered by:
  - `mega`
  - `commodity` + `trade_type`
  - optional `from_sector`
- Emits `ports.list` event text.

### `plot_course`
- BFS shortest path using static sector graph.
- On success: emit `course.plot` with route + distance.
- On failure: emit synthetic `error` (unreachable target).

### `move`
- Validate `to_sector` adjacency.
- On success:
  - decrement warp (3 units)
  - update sector
  - emit `movement.start`, `movement.complete`, `map.local`
- On invalid move:
  - increment `BAD_ACTIONS_COUNT`
  - emit synthetic `error` like observed runs:
    - `Sector X is not adjacent to current sector Y`

### `trade`
- Supports commodities:
  - `quantum_foam`
  - `retro_organics`
  - `neuro_symbolics`
- On success:
  - update credits/cargo
  - emit `trade.executed`, `status.update`, `port.update`
- On invalid trade:
  - increment `BAD_ACTIONS_COUNT`
  - emit synthetic error, including observed classes:
    - `Port does not buy quantum_foam`
    - `Not enough cargo space. Available: N`

### `my_status`
- Emit fresh `status.snapshot` and `map.local`.

### `local_map_region`
- Emit simplified `map.region` event for local neighborhood summary.

### `wait_in_idle_state`
- Emits `idle.complete`.
- No state changes.

### `load_game_info`
- Emit `info.loaded` response for requested topic.

### `dump_cargo`
- Remove requested cargo from hold.
- Create salvage object in current sector.
- Emit `salvage.created` + `status.update`.

### `salvage_collect`
- If salvage exists in current sector and hold capacity is available:
  - transfer cargo
  - emit `salvage.collected` + `status.update`
- Else emit synthetic `error`.

### `finished`
- Terminal action; loop exits.
- Harness computes benchmark metrics from final state + finish message.

## 4. Unknown/Error Policy

Any unrecognized action, malformed arguments, or unsupported operation:
- Emit synthetic error event.
- Continue loop.
- This explicitly stress-tests model resilience in open-ended RL settings.

## 5. Benchmark Metrics

Primary outputs:

- `SUCCESS`:
  - terminal `finished` action observed
  - final state in mega-port sector
  - finish message includes coherent trade/profit reporting
- `BAD_ACTIONS_COUNT`:
  - count of synthetic invalid actions/errors (non-adjacent moves, bad trades, parser failures, unknown actions)

Additional logs include per-turn latency, action name, and event/error class.

## 6. Observed Action/Error Coverage From v2 Sweep

Observed action classes in `tmp.run-npc-super-120b-daily-bf16-v2-*`:

- move
- list_known_ports
- plot_course
- trade
- my_status
- wait_in_idle_state
- load_game_info
- local_map_region
- dump_cargo
- salvage_collect

Observed synthesized error classes:

- move: `Sector ... is not adjacent ...`
- trade: `Port does not buy quantum_foam`
- trade: `Not enough cargo space. Available: 0`
