#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

TS="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="runs/prompt-sweep-${TS}"
mkdir -p "$RUN_DIR"

PROVIDER="${PROVIDER:-google}"
MODEL="${MODEL:-gemini-2.5-flash}"
THINKING="${THINKING:-high}"
ROUNDS="${ROUNDS:-10}"
PARALLEL="${PARALLEL:-7}"
UV_BIN="${UV_BIN:-uv}"
PROMPTS_DIR="${PROMPTS_DIR:-system_prompts}"

# Task variants to sweep. Override with e.g. TASK_VARIANTS="natural,trade-arbitrage"
DEFAULT_TASK_VARIANTS="natural,trade-arbitrage,explore-fuel,info-retrieval,scavenger-hunt,megaport-gauntlet,cargo-logistics,error-recovery"
TASK_VARIANTS="${TASK_VARIANTS:-$DEFAULT_TASK_VARIANTS}"
IFS=',' read -ra TASKS <<< "$TASK_VARIANTS"

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

if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
  echo "ERROR: GOOGLE_API_KEY is required for Gemini benchmarks." >&2
  exit 2
fi

RESULTS="$RUN_DIR/results.tsv"
RESULTS_LOCK="$RUN_DIR/.results.lock"
echo -e "round\ttask_variant\tprompt_label\texit_code\telapsed_s\tattempts\tsuccess\tbad_actions\tfinal_sector\tcoherent_report\tturns\tlog\tjson" > "$RESULTS"

PROMPT_FILES=("$PROMPTS_DIR"/*.txt)
total=$((ROUNDS * ${#PROMPT_FILES[@]} * ${#TASKS[@]}))

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) PROMPT_SWEEP start rounds=${ROUNDS} prompts=${#PROMPT_FILES[@]} tasks=${#TASKS[@]} total=${total} parallel=${PARALLEL}"

# Run a single benchmark and append results to the TSV.
run_one() {
  local round="$1"
  local prompt_file="$2"
  local task_variant="$3"

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

    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) RETRY round=${round} task=${task_variant} prompt=${prompt_label} attempt=${attempt}/${max_attempts} rc=${rc} backoff=${backoff}s" >> "$RUN_DIR/progress.log"

    if (( attempt == max_attempts )); then
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FAILED round=${round} task=${task_variant} prompt=${prompt_label} exhausted ${max_attempts} attempts" >> "$RUN_DIR/progress.log"
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
    echo -e "${round}\t${task_variant}\t${prompt_label}\t${rc}\t${elapsed}\t${attempt}\t${success:-}\t${bad_actions:-}\t${final_sector:-}\t${coherent_report:-}\t${turns:-}\t${log_file}\t${json_file}" >> "$RESULTS"
  ) 9>"$RESULTS_LOCK"

  local msg="$(date -u +%Y-%m-%dT%H:%M:%SZ) round=${round} task=${task_variant} prompt=${prompt_label} rc=${rc} attempts=${attempt} elapsed_s=${elapsed} success=${success:-}"
  echo "$msg" >> "$RUN_DIR/progress.log"
  # Also print to stderr so the user sees live progress.
  echo "$msg" >&2
}

export -f run_one metric_from_log sanitize_slug
export PROVIDER MODEL THINKING UV_BIN RUN_DIR RESULTS RESULTS_LOCK INLINED_SUFFIXES

# Build job list: one line per (round, prompt_file, task_variant) triple.
JOB_LIST="$RUN_DIR/.jobs"
: > "$JOB_LIST"
for round in $(seq 1 "$ROUNDS"); do
  for prompt_file in "${PROMPT_FILES[@]}"; do
    for task_variant in "${TASKS[@]}"; do
      printf '%s\t%s\t%s\n' "$round" "$prompt_file" "$task_variant" >> "$JOB_LIST"
    done
  done
done

# Run jobs in parallel.
active_pids=()
while IFS=$'\t' read -r round prompt_file task_variant; do
  # Wait if we've hit the parallelism limit.
  while (( ${#active_pids[@]} >= PARALLEL )); do
    wait -n 2>/dev/null || true
    # Reap finished pids.
    surviving=()
    for pid in "${active_pids[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        surviving+=("$pid")
      fi
    done
    active_pids=("${surviving[@]}")
  done

  run_one "$round" "$prompt_file" "$task_variant" &
  active_pids+=($!)
done < "$JOB_LIST"

# Wait for all remaining jobs.
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
provider=$PROVIDER
model=$MODEL
thinking=$THINKING
rounds=$ROUNDS
parallel=$PARALLEL
prompts=${#PROMPT_FILES[@]}
tasks=${TASK_VARIANTS}
DONE

rm -f "$RESULTS_LOCK" "$JOB_LIST"
echo "$RUN_DIR" > runs/LATEST_PROMPT_SWEEP_RUN
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) PROMPT_SWEEP complete eval_status=${eval_status} run_dir=${RUN_DIR}"
exit 0
