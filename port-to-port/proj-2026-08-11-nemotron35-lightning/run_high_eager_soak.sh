#!/usr/bin/env bash

set -u -o pipefail

PORT_TO_PORT_DIR="/home/khkramer/src/gb-benchmarks/port-to-port"
BASE_URL="http://127.0.0.1:8000/v1"
HEALTH_URL="http://127.0.0.1:8000/health"
MODEL="nemotron-3.5-lightning"
SOAK_STAMP="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
OPENAI_KEY="$(rg --no-line-number '^OPENAI_API_KEY=' /home/khkramer/src/gb-benchmarks/.env | cut -d= -f2-)"

cd "$PORT_TO_PORT_DIR" || exit 1

echo "SOAK_START stamp=$SOAK_STAMP model=$MODEL base_url=$BASE_URL"
echo "SOAK_CONFIG deployment=marlin-no-prefix-cache-eager mode=high runs=5 temperature=1.0 top_p=0.95 max_tokens=omitted thinking_budget=omitted pipeline_idle_timeout_secs=900"

for run_number in $(seq -w 1 5); do
  round_id="soak${run_number}"
  stem="nemotron-3.5-lightning-natural-high-unbounded-marlin-noapc-eager-soak-${SOAK_STAMP}-r${run_number}"

  if ! curl -fsS "$HEALTH_URL" >/dev/null; then
    echo "ENDPOINT_UNHEALTHY before=$stem utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    exit 86
  fi

  echo "RUN_START stem=$stem mode=high round_id=$round_id utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  OPENAI_API_KEY="$OPENAI_KEY" .venv/bin/python mini-rl-env.py \
    --provider openai \
    --model "$MODEL" \
    --openai-base-url "$BASE_URL" \
    --openai-no-budget-thinking-toggle \
    --openai-params-json '{"temperature":1.0,"top_p":0.95}' \
    --task-variant natural \
    --thinking high \
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

echo "SOAK_EXIT stamp=$SOAK_STAMP utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
