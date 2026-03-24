#!/usr/bin/env bash
set -u

# Without job control (`set -m`), all background children inherit our process
# group.  Ctrl+C sends SIGINT to the entire foreground process group, killing
# the script and every descendant in one shot.  The trap is a safety net.
trap 'echo "" >&2; echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) PROMPT_SWEEP interrupted, killing child processes..." >&2; kill 0 2>/dev/null; wait 2>/dev/null; exit 130' INT TERM

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# uv-managed Python links against its own OpenSSL, which may not find the
# system CA bundle (e.g. NixOS puts certs at a non-default path).
if [[ -z "${SSL_CERT_FILE:-}" && -f /etc/ssl/certs/ca-certificates.crt ]]; then
  export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
fi

TS="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="runs/prompt-sweep-${TS}"
mkdir -p "$RUN_DIR"

ROUNDS="${ROUNDS:-10}"
PARALLEL_PER_MODEL="${PARALLEL_PER_MODEL:-10}"
UV_BIN="${UV_BIN:-uv}"
PROMPTS_DIR="${PROMPTS_DIR:-system_prompts}"

# Task variants to sweep. Override with e.g. TASK_VARIANTS="natural,trade-arbitrage"
DEFAULT_TASK_VARIANTS="natural,trade-arbitrage,explore-fuel,info-retrieval,scavenger-hunt,megaport-gauntlet,cargo-logistics,error-recovery"
TASK_VARIANTS="${TASK_VARIANTS:-$DEFAULT_TASK_VARIANTS}"
IFS=',' read -ra TASKS <<< "$TASK_VARIANTS"

# ── Model matrix ─────────────────────────────────────────────────────────
# Each entry is "provider:model:thinking[:openai_base_url]".
# Override with e.g. MODELS="openai:gpt-4.1:none"
DEFAULT_MODELS="openai:gpt-4.1:none,google:gemini-2.5-flash:high,anthropic:claude-sonnet-4-6:none"
MODELS="${MODELS:-$DEFAULT_MODELS}"
IFS=',' read -ra MODEL_SPECS <<< "$MODELS"

# Prompt files that need load_game_info excluded (game info is inlined in the prompt).
INLINED_SUFFIXES="_inlined"

sanitize_slug() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '_'
}

metric_from_log() {
  local key="$1"
  local file="$2"
  grep -m1 "^${key}=" "$file" 2>/dev/null | cut -d= -f2-
}

if ! command -v "$UV_BIN" >/dev/null 2>&1; then
  echo "ERROR: uv binary not found: $UV_BIN" >&2
  exit 127
fi

# Validate API keys for all providers in the model matrix.
validate_provider_key() {
  local provider="$1"
  local base_url="$2"
  case "$provider" in
    google)
      if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
        echo "ERROR: GOOGLE_API_KEY is required for provider=google." >&2
        exit 2
      fi
      ;;
    openai)
      if [[ -z "${OPENAI_API_KEY:-}" && -z "$base_url" ]]; then
        echo "ERROR: OPENAI_API_KEY is required for provider=openai (unless a base URL is set)." >&2
        exit 2
      fi
      ;;
    anthropic)
      if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
        echo "ERROR: ANTHROPIC_API_KEY is required for provider=anthropic." >&2
        exit 2
      fi
      ;;
  esac
}

for spec in "${MODEL_SPECS[@]}"; do
  IFS=':' read -r _prov _model _think _base_url <<< "$spec"
  validate_provider_key "$_prov" "${_base_url:-}"
done

RESULTS="$RUN_DIR/results.tsv"
RESULTS_LOCK="$RUN_DIR/.results.lock"
echo -e "round\tmodel_spec\ttask_variant\tprompt_label\texit_code\telapsed_s\tattempts\tsuccess\tbad_actions\tfinal_sector\tcoherent_report\tturns\tlog\tjson" > "$RESULTS"

PROMPT_FILES=("$PROMPTS_DIR"/*.txt)
jobs_per_model=$((ROUNDS * ${#PROMPT_FILES[@]} * ${#TASKS[@]}))
total=$((jobs_per_model * ${#MODEL_SPECS[@]}))

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) PROMPT_SWEEP start rounds=${ROUNDS} prompts=${#PROMPT_FILES[@]} tasks=${#TASKS[@]} models=${#MODEL_SPECS[@]} total=${total} parallel_per_model=${PARALLEL_PER_MODEL}"

# Run a single benchmark and append results to the TSV.
run_one() {
  local round="$1"
  local prompt_file="$2"
  local task_variant="$3"
  local model_spec="$4"

  # Parse model spec: provider:model:thinking[:openai_base_url]
  IFS=':' read -r PROVIDER MODEL THINKING OPENAI_BASE_URL <<< "$model_spec"
  OPENAI_BASE_URL="${OPENAI_BASE_URL:-}"

  local prompt_label
  prompt_label="$(basename "$prompt_file" .txt)"
  local run_tag="r$(printf '%02d' "$round")-${task_variant}-${prompt_label}"
  local slug
  slug="$(sanitize_slug "${PROVIDER}-${MODEL}-${run_tag}")"
  local log_file="$RUN_DIR/${slug}.log"
  local json_file="$RUN_DIR/${slug}.json"

  local start_epoch
  start_epoch="$(date +%s)"

  # Per-task turn budgets.
  local max_turns=50
  case "$task_variant" in
    explore-fuel)     max_turns=150 ;;
    trade-arbitrage)  max_turns=100 ;;
  esac

  local cmd=(
    "$UV_BIN" run python mini-rl-env.py
    --provider "$PROVIDER"
    --model "$MODEL"
    --thinking "$THINKING"
    --task-variant "$task_variant"
    --max-turns "$max_turns"
    --function-call-timeout-secs 20
    --system-instruction "$prompt_file"
    --system-instruction-label "$prompt_label"
    --log-json "$json_file"
  )

  # Pass custom OpenAI-compatible base URL if set.
  if [[ -n "$OPENAI_BASE_URL" ]]; then
    cmd+=(--openai-base-url "$OPENAI_BASE_URL")
  fi

  # For inlined prompts, exclude the load_game_info tool.
  if [[ "$prompt_label" == *"$INLINED_SUFFIXES"* ]]; then
    cmd+=(--exclude-tools load_game_info)
  fi

  local max_attempts=10
  local attempt=1
  local backoff=30
  local rc=1

  while (( attempt <= max_attempts )); do
    "${cmd[@]}" > "$log_file" 2>&1
    rc=$?

    # A run succeeded if the JSON output was written (even if exit code is 1,
    # which just means the port-to-port success criteria weren't met).
    if (( rc == 0 )) || [[ -s "$json_file" ]]; then
      break
    fi

    local retry_msg="$(date -u +%Y-%m-%dT%H:%M:%SZ) RETRY round=${round} model=${MODEL} task=${task_variant} prompt=${prompt_label} attempt=${attempt}/${max_attempts} rc=${rc} backoff=${backoff}s"
    echo "$retry_msg" >> "$RUN_DIR/progress.log"
    echo "$retry_msg" >&2

    if (( attempt == max_attempts )); then
      local fail_msg="$(date -u +%Y-%m-%dT%H:%M:%SZ) FAILED round=${round} model=${MODEL} task=${task_variant} prompt=${prompt_label} exhausted ${max_attempts} attempts"
      echo "$fail_msg" >> "$RUN_DIR/progress.log"
      echo "$fail_msg" >&2
      break
    fi

    sleep "$backoff"
    # Cap backoff at 120s: 30, 60, 120, 120, ...
    (( backoff = backoff * 2 > 120 ? 120 : backoff * 2 ))
    (( attempt++ ))
  done

  local end_epoch
  end_epoch="$(date +%s)"
  local elapsed=$((end_epoch - start_epoch))

  local success bad_actions final_sector coherent_report turns
  success="$(metric_from_log SUCCESS "$log_file")"
  bad_actions="$(metric_from_log BAD_ACTIONS_COUNT "$log_file")"
  final_sector="$(metric_from_log FINAL_SECTOR "$log_file")"
  coherent_report="$(metric_from_log COHERENT_REPORT "$log_file")"
  turns="$(metric_from_log TURNS "$log_file")"

  # Append to results with flock to avoid interleaved writes.
  (
    flock 9
    echo -e "${round}\t${model_spec}\t${task_variant}\t${prompt_label}\t${rc}\t${elapsed}\t${attempt}\t${success:-}\t${bad_actions:-}\t${final_sector:-}\t${coherent_report:-}\t${turns:-}\t${log_file}\t${json_file}" >> "$RESULTS"
  ) 9>"$RESULTS_LOCK"

  local msg="$(date -u +%Y-%m-%dT%H:%M:%SZ) round=${round} model=${MODEL} task=${task_variant} prompt=${prompt_label} rc=${rc} attempts=${attempt} elapsed_s=${elapsed} success=${success:-}"
  echo "$msg" >> "$RUN_DIR/progress.log"
  # Also print to stderr so the user sees live progress.
  echo "$msg" >&2
}

export -f run_one metric_from_log sanitize_slug
export UV_BIN RUN_DIR RESULTS RESULTS_LOCK INLINED_SUFFIXES

# ── Per-model worker ─────────────────────────────────────────────────────
# Each model gets its own subprocess that processes its job list with up to
# PARALLEL_PER_MODEL concurrent tasks. This way all models run in parallel
# while each respects its own per-provider concurrency limit.
run_model_jobs() {
  local model_spec="$1"
  local job_file="$2"
  local max_parallel="$3"

  local active_pids=()
  while IFS=$'\t' read -r round prompt_file task_variant; do
    # Wait if we've hit the per-model parallelism limit.
    while (( ${#active_pids[@]} >= max_parallel )); do
      wait -n 2>/dev/null || true
      surviving=()
      for pid in "${active_pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
          surviving+=("$pid")
        fi
      done
      active_pids=("${surviving[@]}")
    done

    run_one "$round" "$prompt_file" "$task_variant" "$model_spec" &
    active_pids+=($!)
  done < "$job_file"

  wait
}

export -f run_model_jobs

# Build per-model job lists and launch a worker for each model.
model_worker_pids=()
for model_spec in "${MODEL_SPECS[@]}"; do
  job_file="$RUN_DIR/.jobs.$(sanitize_slug "$model_spec")"
  : > "$job_file"
  for round in $(seq 1 "$ROUNDS"); do
    for prompt_file in "${PROMPT_FILES[@]}"; do
      for task_variant in "${TASKS[@]}"; do
        printf '%s\t%s\t%s\n' "$round" "$prompt_file" "$task_variant" >> "$job_file"
      done
    done
  done

  IFS=':' read -r _prov _model _think _base_url <<< "$model_spec"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Starting worker for ${_model} (${jobs_per_model} jobs, ${PARALLEL_PER_MODEL} parallel)" >&2

  run_model_jobs "$model_spec" "$job_file" "$PARALLEL_PER_MODEL" &
  model_worker_pids+=($!)
done

# Wait for all model workers to finish.
wait

# Run evaluation.
eval_status="EVAL_OK"
eval_log="$RUN_DIR/evaluate.log"
if ! "$UV_BIN" run python evaluate_runs.py \
  "$RUN_DIR/*.json" \
  --out-dir "$RUN_DIR/eval" \
  --report-accuracy-judge llm \
  --judge-model "${EVAL_JUDGE_MODEL:-claude-sonnet-4-6}" \
  > "$eval_log" 2>&1; then
  eval_status="EVAL_FAILED"
  echo "Evaluator failed; see $eval_log" >&2
fi

cat > "$RUN_DIR/DONE" <<DONE
finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
eval_status=$eval_status
models=$MODELS
rounds=$ROUNDS
parallel_per_model=$PARALLEL_PER_MODEL
prompts=${#PROMPT_FILES[@]}
tasks=${TASK_VARIANTS}
DONE

# Clean up per-model job files.
rm -f "$RESULTS_LOCK" "$RUN_DIR"/.jobs.*
echo "$RUN_DIR" > runs/LATEST_PROMPT_SWEEP_RUN
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) PROMPT_SWEEP complete eval_status=${eval_status} run_dir=${RUN_DIR}"
exit 0
