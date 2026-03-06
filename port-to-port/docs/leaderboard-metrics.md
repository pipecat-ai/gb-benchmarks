# Leaderboard Metrics (9x Matrix)

This file records the agreed primary leaderboard columns and generation workflow for canonical `mini_rl_run.v3`.

## Column Set

- `Model`
- `N` (number of runs)
- `Strict Success` (LLM-judged)
  - Source: `evaluate_runs.py` `strict_success` from `enriched_runs.jsonl`
- `Partial Success`
  - Definition: `summary.finished_called == true && summary.final_sector_matches_start == true && summary.reached_mega_anytime == true && summary.recharge_to_full_at_mega == true`
- `Avg Time (s)`
  - Mean of `summary.elapsed_ms / 1000`
- `Avg Turns`
  - Mean of `summary.turns_executed`
- `Turn P50 (ms)`
  - P50 over pooled `turn.decision_ms` values for the model
- `Turn P95 (ms)`
  - P95 over pooled `turn.decision_ms` values for the model
- `Bad Move Rate`
  - `(count of turns where any tool_calls[*].name == "move" with result_status in {"error","post_finished_call_rejected"}, and bad_action_increment > 0) / total_turns`
- `Bad Trade Rate`
  - `(count of turns where any tool_calls[*].name == "trade" with result_status in {"error","post_finished_call_rejected"}, and bad_action_increment > 0) / total_turns`
- `Unknown Tool/Action Rate`
  - `(count of turns where any tool_calls[*].name is not in the benchmark tool catalog, result_status in {"error","post_finished_call_rejected"}, and bad_action_increment > 0) / total_turns`
- `No Tool Call Rate`
  - `(count of turns where failure_class == "no_tool_call") / total_turns`
- `Inference Failure Rate`
  - `(count of turns where failure_class == "inference_failure") / total_turns`

`Parse/Format Error Rate` is removed in v3 because runs use native function calling instead of JSON action parsing.

## Sort Order

1. `Strict Success` rate descending
2. `Avg Time (s)` ascending

## Scripts To Re-use

### 1) Produce LLM-judged strict success (`enriched_runs.jsonl`)

```bash
cd port-to-port
# source provider API keys (example):
# set -a && source ~/.env.llm && set +a
uv run python evaluate_runs.py \
  "runs/mega-sweep-20260221T174828Z/model-matrix/*.json" \
  --out-dir "runs/mega-sweep-20260221T174828Z/eval-llm-<timestamp>" \
  --report-accuracy-judge llm
```

### 2) Build the primary leaderboard table with the agreed columns

```bash
cd port-to-port
uv run python build_primary_leaderboard.py \
  --runs-glob "runs/mega-sweep-20260221T174828Z/model-matrix/*.json" \
  --enriched-jsonl "runs/mega-sweep-20260221T174828Z/eval-llm-<timestamp>/enriched_runs.jsonl" \
  --out "runs/mega-sweep-20260221T174828Z/leaderboard-primary-9x-all-runs-v3.md"
```

## Current Output Paths

- Table: `runs/mega-sweep-20260221T174828Z/leaderboard-primary-9x-all-runs-v3.md`
- LLM eval used for strict success: `runs/mega-sweep-20260221T174828Z/eval-llm-20260222T024828Z/enriched_runs.jsonl`
