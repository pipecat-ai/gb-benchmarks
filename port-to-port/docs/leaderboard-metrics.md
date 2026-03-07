# Summary Leaderboard Metrics (11x Matrix)

This file records the agreed human-facing summary leaderboard columns and generation workflow for canonical `mini_rl_run.v3`.

Leaderboard scope rule:

- each leaderboard covers exactly one prompt definition
- maintain separate leaderboards for `natural` and `literal`
- create a separate leaderboard for any custom prompt used more than once
- do not mix runs from different prompts in the same table
- leaderboard generation should reject a mixed-prompt input set

Canonical maintained leaderboard files:

- `port-to-port/leaderboards/leaderboard-natural.md`
- `port-to-port/leaderboards/leaderboard-literal.md`

These two files are the up-to-date human-facing leaderboards for the current built-in prompts.
Historical snapshots should be archived separately rather than versioned in the canonical filename.

## Column Set

- `Model`
- `N` (number of runs)
- `Primary /100`
  - Median of per-run `primary_score_100`
- `Task Complete %`
  - Rate of runs where `task_complete == true`
  - `task_complete` means: reached the mega-port, recharged to full, returned to the start sector, and first `finished` happened only after those conditions were satisfied
- `Trade /15`
  - Median of per-run `trade_quality_score`
- `Path /15`
  - Median of per-run `path_efficiency_score`
- `Tools /15`
  - Median of per-run `tool_discipline_score`
- `Report /15`
  - Median of per-run `report_quality_score`
- `Turn P50 (ms)`
  - P50 over pooled `turn.decision_ms` values for the model
- `Turn P90 (ms)`
  - P90 over pooled `turn.decision_ms` values for the model
- `Total Time P50 (s)`
  - Median of per-run `summary.elapsed_ms / 1000`

The summary table intentionally omits a separate binary report-accuracy column. Report quality is already surfaced through `Report /15`, and task reliability is already surfaced through `Task Complete %`.

## Sort Order

1. `Primary /100` descending
2. `Task Complete %` descending
3. `Total Time P50 (s)` ascending

## Scripts To Re-use

### 1) Produce enriched scored runs (`enriched_runs.jsonl`)

```bash
cd port-to-port
# source provider API keys (example):
# set -a && source ~/.env.llm && set +a
uv run python evaluate_runs.py \
  "runs/mega-sweep-20260221T174828Z/model-matrix/*.json" \
  --out-dir "runs/mega-sweep-20260221T174828Z/eval-<timestamp>" \
  --report-accuracy-judge llm
```

### 2) Build the summary leaderboard table with the agreed columns

```bash
cd port-to-port
uv run python build_primary_leaderboard.py \
  --runs-glob "runs/mega-sweep-20260221T174828Z/model-matrix/natural/*.json" \
  --enriched-jsonl "runs/mega-sweep-20260221T174828Z/eval-<timestamp>/enriched_runs.jsonl" \
  --leaderboard-prompt-id natural
```

If `--out` is omitted, the builder should write to:

- `leaderboards/leaderboard-natural.md` for `--leaderboard-prompt-id natural`
- `leaderboards/leaderboard-literal.md` for `--leaderboard-prompt-id literal`

Run the command separately for `literal` and for any repeated custom prompt.
If prompt-specific runs are not already stored in separate directories, filter them into a prompt-specific file list before calling the leaderboard script.

## Current Output Paths

- Canonical natural table: `port-to-port/leaderboards/leaderboard-natural.md`
- Canonical literal table: `port-to-port/leaderboards/leaderboard-literal.md`
- Enriched eval: `runs/mega-sweep-20260221T174828Z/eval-<timestamp>/enriched_runs.jsonl`
