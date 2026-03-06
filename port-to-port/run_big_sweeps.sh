#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

TS="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="runs/mega-sweep-${TS}"
NEMO_DIR="$RUN_DIR/nemotron"
MATRIX_DIR="$RUN_DIR/model-matrix"
mkdir -p "$NEMO_DIR" "$MATRIX_DIR"

NEMO_BASE_URL="${NEMO_BASE_URL:-https://daily--nemotron-super-b200-bf16-v2-serve.modal.run}"
NEMO_MODEL="${NEMO_MODEL:-nemotron-3-super-120b}"
NEMO_ROUNDS="${NEMO_ROUNDS:-25}"
MATRIX_ROUNDS="${MATRIX_ROUNDS:-24}"
UV_BIN="${UV_BIN:-uv}"

MODELS=(
  "openai|gpt-4.1"
  "openai|gpt-5.1"
  "anthropic|claude-sonnet-4-6"
  "anthropic|claude-haiku-4-5-20251001"
  "anthropic|claude-opus-4-6"
  "google|gemini-2.5-flash"
  "google|gemini-3-flash-preview"
  "google|gemini-3-pro-preview"
  "google|gemini-3.1-pro-preview"
)

sanitize_slug() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '_'
}

metric_from_log() {
  local key="$1"
  local file="$2"
  grep -m1 "^${key}=" "$file" 2>/dev/null | cut -d= -f2-
}

run_nemotron_worker() {
  local results="$NEMO_DIR/results.tsv"
  echo -e "round\tthinking\tmax_tokens\texit_code\telapsed_s\tsuccess\tbad_actions\tfinal_sector\tcoherent_report\tturns\tlog\tjson" > "$results"

  local total=$((NEMO_ROUNDS * 3))
  local i=0
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) NEMOTRON start rounds=${NEMO_ROUNDS} total=${total}"

  for round in $(seq 1 "$NEMO_ROUNDS"); do
    for thinking in low medium high; do
      i=$((i + 1))
      local max_tokens=""
      if [[ "$thinking" == "low" ]]; then
        max_tokens="4608"
      elif [[ "$thinking" == "medium" ]]; then
        max_tokens="5120"
      fi

      local run_tag="r$(printf '%02d' "$round")-th${thinking}"
      local slug
      slug="$(sanitize_slug "openai-${NEMO_MODEL}-${run_tag}")"
      local log_file="$NEMO_DIR/${slug}.log"
      local json_file="$NEMO_DIR/${slug}.json"

      local start_epoch
      start_epoch="$(date +%s)"

      local cmd=(
        "$UV_BIN" run python mini-rl-env.py
        --provider openai
        --model "$NEMO_MODEL"
        --openai-base-url "$NEMO_BASE_URL"
        --thinking "$thinking"
        --max-turns 50
        --function-call-timeout-secs 20
        --log-json "$json_file"
      )
      if [[ -n "$max_tokens" ]]; then
        cmd+=(--max-tokens "$max_tokens")
      fi

      "${cmd[@]}" > "$log_file" 2>&1
      local rc=$?

      local end_epoch
      end_epoch="$(date +%s)"
      local elapsed=$((end_epoch - start_epoch))

      local success bad_actions final_sector coherent_report turns
      success="$(metric_from_log SUCCESS "$log_file")"
      bad_actions="$(metric_from_log BAD_ACTIONS_COUNT "$log_file")"
      final_sector="$(metric_from_log FINAL_SECTOR "$log_file")"
      coherent_report="$(metric_from_log COHERENT_REPORT "$log_file")"
      turns="$(metric_from_log TURNS "$log_file")"

      echo -e "${round}\t${thinking}\t${max_tokens}\t${rc}\t${elapsed}\t${success:-}\t${bad_actions:-}\t${final_sector:-}\t${coherent_report:-}\t${turns:-}\t${log_file}\t${json_file}" >> "$results"
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) NEMOTRON ${i}/${total} round=${round} thinking=${thinking} rc=${rc} elapsed_s=${elapsed}" >> "$NEMO_DIR/progress.log"
    done
  done
}

run_model_matrix_worker() {
  local results="$MATRIX_DIR/results.tsv"
  echo -e "round\tprovider\tmodel\texit_code\telapsed_s\tsuccess\tbad_actions\tfinal_sector\tcoherent_report\tturns\tlog\tjson" > "$results"

  local total=$((MATRIX_ROUNDS * ${#MODELS[@]}))
  local i=0
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) MATRIX start rounds=${MATRIX_ROUNDS} models=${#MODELS[@]} total=${total}"

  for round in $(seq 1 "$MATRIX_ROUNDS"); do
    for entry in "${MODELS[@]}"; do
      i=$((i + 1))

      local provider model
      provider="${entry%%|*}"
      model="${entry##*|}"

      local run_tag="r$(printf '%02d' "$round")"
      local slug
      slug="$(sanitize_slug "${provider}-${model}-${run_tag}")"
      local log_file="$MATRIX_DIR/${slug}.log"
      local json_file="$MATRIX_DIR/${slug}.json"

      local start_epoch
      start_epoch="$(date +%s)"

      "$UV_BIN" run python mini-rl-env.py \
        --provider "$provider" \
        --model "$model" \
        --thinking high \
        --max-turns 50 \
        --function-call-timeout-secs 20 \
        --log-json "$json_file" \
        > "$log_file" 2>&1
      local rc=$?

      local end_epoch
      end_epoch="$(date +%s)"
      local elapsed=$((end_epoch - start_epoch))

      local success bad_actions final_sector coherent_report turns
      success="$(metric_from_log SUCCESS "$log_file")"
      bad_actions="$(metric_from_log BAD_ACTIONS_COUNT "$log_file")"
      final_sector="$(metric_from_log FINAL_SECTOR "$log_file")"
      coherent_report="$(metric_from_log COHERENT_REPORT "$log_file")"
      turns="$(metric_from_log TURNS "$log_file")"

      echo -e "${round}\t${provider}\t${model}\t${rc}\t${elapsed}\t${success:-}\t${bad_actions:-}\t${final_sector:-}\t${coherent_report:-}\t${turns:-}\t${log_file}\t${json_file}" >> "$results"
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) MATRIX ${i}/${total} round=${round} provider=${provider} model=${model} rc=${rc} elapsed_s=${elapsed}" >> "$MATRIX_DIR/progress.log"
    done
  done
}

if ! command -v "$UV_BIN" >/dev/null 2>&1; then
  echo "ERROR: uv binary not found: $UV_BIN" >&2
  exit 127
fi

cat > "$RUN_DIR/README.txt" <<META
started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
run_dir=$RUN_DIR
nemotron_base_url=$NEMO_BASE_URL
nemotron_model=$NEMO_MODEL
nemotron_rounds=$NEMO_ROUNDS
nemotron_thinking_levels=low,medium,high
default_prompt=mini-rl-env.py built-in DEFAULT_BENCHMARK_TASK
matrix_rounds=$MATRIX_ROUNDS
matrix_models=${MODELS[*]}
META

run_nemotron_worker > "$RUN_DIR/nemotron-worker.out" 2>&1 &
PID_NEMO=$!

run_model_matrix_worker > "$RUN_DIR/model-matrix-worker.out" 2>&1 &
PID_MATRIX=$!

cat > "$RUN_DIR/PIDS" <<PIDS
nemotron_pid=$PID_NEMO
model_matrix_pid=$PID_MATRIX
PIDS

echo "${RUN_DIR}" > runs/LATEST_BIG_SWEEP_RUN

wait "$PID_NEMO"
RC_NEMO=$?
wait "$PID_MATRIX"
RC_MATRIX=$?

cat > "$RUN_DIR/DONE" <<DONE
finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
nemotron_exit=$RC_NEMO
model_matrix_exit=$RC_MATRIX
DONE

exit 0
