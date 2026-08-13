#!/usr/bin/env bash

set -u -o pipefail

PORT_TO_PORT_DIR="/home/khkramer/src/gb-benchmarks/port-to-port"
BASE_URL="http://127.0.0.1:8000/v1"
HEALTH_URL="http://127.0.0.1:8000/health"
FLUSH_URL="http://127.0.0.1:8000/flush_cache"
MODEL="nemotron-3-nano-30b-nvfp4"
RUNS_PER_MODE="${1:-25}"
BATCH_STAMP="${2:-$(date -u +%Y%m%dT%H%M%SZ)}"

cd "$PORT_TO_PORT_DIR" || exit 1
mkdir -p runs

echo "BATCH_START stamp=$BATCH_STAMP model=$MODEL base_url=$BASE_URL"
echo "BATCH_CONFIG cadence=alternating modes=none,high runs_per_mode=$RUNS_PER_MODE none_sampling=temperature:0 high_sampling=temperature:0.6,top_p:0.95 max_tokens=10000 thinking_budget=omitted pipeline_idle_timeout_secs=900"

flush_cache() {
  local stem="$1"
  local flush_log="runs/${stem}.flush.log"
  local attempt http_status

  : > "$flush_log"
  for attempt in 1 2 3 4 5 6; do
    http_status="$(curl -sS -o "${flush_log}.body" -w '%{http_code}' \
      --request POST "$FLUSH_URL")"
    {
      echo "FLUSH_ATTEMPT=$attempt HTTP_STATUS=$http_status UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      if [[ -f "${flush_log}.body" ]]; then
        sed 's/^/FLUSH_BODY=/' "${flush_log}.body"
      fi
    } | tee -a "$flush_log"
    if [[ "$http_status" == "200" ]]; then
      return 0
    fi
    sleep 5
  done
  return 1
}

for run_index in $(seq 1 "$RUNS_PER_MODE"); do
  run_number="$(printf '%02d' "$run_index")"
  round_id="r${run_number}"
  for mode in none high; do
    if [[ "$mode" == "none" ]]; then
      mode_label="none"
      params_json='{"temperature":0}'
    else
      mode_label="high-native"
      params_json='{"temperature":0.6,"top_p":0.95}'
    fi
    stem="nemotron-3-nano-30b-nvfp4-natural-${mode_label}-sglang-${BATCH_STAMP}-${round_id}"

    if ! curl -fsS "$HEALTH_URL" >/dev/null; then
      echo "RUN_EXIT stem=$stem rc=86 reason=endpoint_unhealthy_before utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      continue
    fi
    if ! flush_cache "$stem"; then
      echo "RUN_EXIT stem=$stem rc=87 reason=cache_flush_failed utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      continue
    fi

    echo "RUN_START stem=$stem mode=$mode round_id=$round_id utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    OPENAI_API_KEY="dummy" .venv/bin/python mini-rl-env.py \
      --provider openai \
      --model "$MODEL" \
      --openai-base-url "$BASE_URL" \
      --openai-no-budget-thinking-toggle \
      --openai-params-json "$params_json" \
      --task-variant natural \
      --thinking "$mode" \
      --round-id "$round_id" \
      --max-tokens 10000 \
      --max-turns 50 \
      --function-call-timeout-secs 20 \
      --pipeline-idle-timeout-secs 900 \
      --log-json "runs/${stem}.json" \
      2>&1 | tee "runs/${stem}.log"
    run_rc=${PIPESTATUS[0]}
    echo "RUN_EXIT stem=$stem rc=$run_rc utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    if ! curl -fsS "$HEALTH_URL" >/dev/null; then
      echo "ENDPOINT_UNHEALTHY after=$stem utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    fi
  done
done

echo "BATCH_EXIT stamp=$BATCH_STAMP utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
