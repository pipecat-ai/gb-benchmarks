#!/usr/bin/env bash

set -u -o pipefail

PORT_TO_PORT_DIR="/home/khkramer/src/gb-benchmarks/port-to-port"
BASE_URL="http://127.0.0.1:8000/v1"
HEALTH_URL="http://127.0.0.1:8000/health"
MODEL="nemotron-3.5-lightning"
BATCH_STAMP="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
OPENAI_KEY="$(rg --no-line-number '^OPENAI_API_KEY=' /home/khkramer/src/gb-benchmarks/.env | cut -d= -f2-)"

cd "$PORT_TO_PORT_DIR" || exit 1

echo "BATCH_START stamp=$BATCH_STAMP model=$MODEL base_url=$BASE_URL"
echo "BATCH_CONFIG deployment=marlin-no-prefix-cache modes=none,high runs_per_mode=25 temperature=1.0 top_p=0.95 max_tokens=omitted thinking_budget=omitted pipeline_idle_timeout_secs=900"

for mode in none high; do
  if [[ "$mode" == "none" ]]; then
    mode_label="none"
  else
    mode_label="high-unbounded"
  fi

  for run_number in $(seq -w 1 25); do
    round_id="r${run_number}"
    stem="nemotron-3.5-lightning-natural-${mode_label}-marlin-noapc-${BATCH_STAMP}-${round_id}"

    if ! curl -fsS "$HEALTH_URL" >/dev/null; then
      echo "ENDPOINT_UNHEALTHY before=$stem utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      exit 86
    fi

    echo "RUN_START stem=$stem mode=$mode round_id=$round_id utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    OPENAI_API_KEY="$OPENAI_KEY" .venv/bin/python mini-rl-env.py \
      --provider openai \
      --model "$MODEL" \
      --openai-base-url "$BASE_URL" \
      --openai-no-budget-thinking-toggle \
      --openai-params-json '{"temperature":1.0,"top_p":0.95}' \
      --task-variant natural \
      --thinking "$mode" \
      --round-id "$round_id" \
      --max-turns 50 \
      --function-call-timeout-secs 20 \
      --pipeline-idle-timeout-secs 900 \
      --log-json "runs/${stem}.json" \
      2>&1 | tee "runs/${stem}.log"
    run_rc=${PIPESTATUS[0]}

    echo "RUN_EXIT stem=$stem rc=$run_rc utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    if ! curl -fsS "$HEALTH_URL" >/dev/null; then
      echo "ENDPOINT_UNHEALTHY after=$stem utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      exit 86
    fi
  done
done

echo "BATCH_EXIT stamp=$BATCH_STAMP utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
