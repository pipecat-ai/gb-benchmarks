#!/usr/bin/env bash

set -u -o pipefail

PORT_TO_PORT_DIR="/home/khkramer/src/gb-benchmarks/port-to-port"
BATCH_STAMP="20260811T223912Z"
ANTHROPIC_KEY="$(rg --no-line-number '^ANTHROPIC_API_KEY=' /home/khkramer/src/gb-benchmarks/.env | cut -d= -f2-)"

cd "$PORT_TO_PORT_DIR" || exit 1

for mode in none high-unbounded; do
  input_glob="runs/nemotron-3.5-lightning-natural-${mode}-sglang-${BATCH_STAMP}-r*.json"
  out_dir="runs/eval-nemotron-3.5-lightning-natural-${mode}-sglang-${BATCH_STAMP}"
  log_file="runs/eval-nemotron-3.5-lightning-natural-${mode}-sglang-${BATCH_STAMP}.log"

  echo "JUDGE_START mode=$mode input=$input_glob out_dir=$out_dir utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ANTHROPIC_API_KEY="$ANTHROPIC_KEY" .venv/bin/python evaluate_runs.py \
    "$input_glob" \
    --out-dir "$out_dir" \
    --report-accuracy-judge llm \
    --judge-model claude-sonnet-4-6 \
    2>&1 | tee "$log_file"
  judge_rc=${PIPESTATUS[0]}
  echo "JUDGE_EXIT mode=$mode rc=$judge_rc utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
done

echo "JUDGING_COMPLETE stamp=$BATCH_STAMP utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
