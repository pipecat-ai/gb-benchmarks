# Leaderboard Metrics (9x Matrix)

This file records the agreed primary leaderboard columns and generation workflow.

## Column Set

- `Model`
- `N` (number of runs)
- `Strict Success` (LLM-judged)
  - Source: `evaluate_runs.py` `strict_success` from `enriched_runs.jsonl`
- `Partial Success`
  - Definition: `summary.final_sector_is_mega == true`
- `Avg Time (s)`
  - Mean of `summary.elapsed_ms / 1000`
- `Avg Turns`
  - Mean of `summary.turns_executed`
- `Turn P50 (ms)`
  - P50 over pooled `turn.decision_ms` values for the model
- `Turn P95 (ms)`
  - P95 over pooled `turn.decision_ms` values for the model
- `Bad Move Rate`
  - `(count of turns where action == "move" and bad_action_increment > 0 and no parse_error) / total_turns`
- `Bad Trade Rate`
  - `(count of turns where action == "trade" and bad_action_increment > 0 and no parse_error) / total_turns`
- `Unknown Tool/Action Rate`
  - `(count of turns where action is unknown, bad_action_increment > 0, and no parse_error) / total_turns`
- `Parse/Format Error Rate`
  - `(count of turns where parse_error is set and parse_error != "inference failure") / total_turns`
- `Inference Failure Rate`
  - `(count of turns where parse_error == "inference failure") / total_turns`

## Sort Order

1. `Strict Success` rate descending
2. `Avg Time (s)` ascending

## Scripts To Re-use

### 1) Produce LLM-judged strict success (`enriched_runs.jsonl`)

```bash
cd benchmarks/mini-rl-harness
set -a && source /Users/khkramer/src/gradient-bang/.env.bot && set +a
uv run python evaluate_runs.py \
  "runs/mega-sweep-20260221T174828Z/model-matrix/*.json" \
  --out-dir "runs/mega-sweep-20260221T174828Z/eval-llm-<timestamp>" \
  --report-accuracy-judge llm
```

### 2) Build the primary leaderboard table with the agreed columns

```bash
cd benchmarks/mini-rl-harness
uv run python build_primary_leaderboard.py \
  --runs-glob "runs/mega-sweep-20260221T174828Z/model-matrix/*.json" \
  --enriched-jsonl "runs/mega-sweep-20260221T174828Z/eval-llm-<timestamp>/enriched_runs.jsonl" \
  --out "runs/mega-sweep-20260221T174828Z/leaderboard-primary-9x-all-runs-v2.md"
```

## Current Output Paths

- Table: `runs/mega-sweep-20260221T174828Z/leaderboard-primary-9x-all-runs-v2.md`
- LLM eval used for strict success: `runs/mega-sweep-20260221T174828Z/eval-llm-20260222T024828Z/enriched_runs.jsonl`
