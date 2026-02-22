#!/usr/bin/env bash
set -u

TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="runs/matrix-${TS}"
mkdir -p "$RUN_DIR"
UV_BIN="${UV_BIN:-uv}"

if ! command -v "$UV_BIN" >/dev/null 2>&1; then
  echo "ERROR: uv binary not found: $UV_BIN" >&2
  exit 127
fi

RESULTS="$RUN_DIR/results.tsv"
echo -e "provider\tmodel\texit_code\telapsed_s\tsuccess\tbad_actions\tfinal_sector\tcoherent_report\tturns\tlog\tjson" > "$RESULTS"

models=(
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

for entry in "${models[@]}"; do
  provider="${entry%%|*}"
  model="${entry##*|}"
  slug="$(echo "${provider}-${model}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '_')"

  log_file="$RUN_DIR/${slug}.log"
  json_file="$RUN_DIR/${slug}.json"

  start_epoch="$(date +%s)"

  "$UV_BIN" run python mini-rl-env.py \
    --provider "$provider" \
    --model "$model" \
    --max-turns 40 \
    --log-json "$json_file" \
    > "$log_file" 2>&1
  rc=$?

  end_epoch="$(date +%s)"
  elapsed="$((end_epoch - start_epoch))"

  success="$(grep -m1 '^SUCCESS=' "$log_file" | cut -d= -f2- 2>/dev/null)"
  bad_actions="$(grep -m1 '^BAD_ACTIONS_COUNT=' "$log_file" | cut -d= -f2- 2>/dev/null)"
  final_sector="$(grep -m1 '^FINAL_SECTOR=' "$log_file" | cut -d= -f2- 2>/dev/null)"
  coherent_report="$(grep -m1 '^COHERENT_REPORT=' "$log_file" | cut -d= -f2- 2>/dev/null)"
  turns="$(grep -m1 '^TURNS=' "$log_file" | cut -d= -f2- 2>/dev/null)"

  success="${success:-}"
  bad_actions="${bad_actions:-}"
  final_sector="${final_sector:-}"
  coherent_report="${coherent_report:-}"
  turns="${turns:-}"

  echo -e "${provider}\t${model}\t${rc}\t${elapsed}\t${success}\t${bad_actions}\t${final_sector}\t${coherent_report}\t${turns}\t${log_file}\t${json_file}" >> "$RESULTS"
done

eval_status="EVAL_OK"
eval_log="$RUN_DIR/evaluate.log"
judge_args=(--report-accuracy-judge deterministic)
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  judge_args=(
    --report-accuracy-judge llm
    --judge-model "${EVAL_JUDGE_MODEL:-claude-sonnet-4-6}"
  )
fi
if ! "$UV_BIN" run python evaluate_runs.py "$RUN_DIR/*.json" --out-dir "$RUN_DIR/eval" "${judge_args[@]}" > "$eval_log" 2>&1; then
  eval_status="EVAL_FAILED"
  echo "Evaluator failed; see $eval_log" >&2
fi

{
  echo "DONE"
  echo "$eval_status"
} > "$RUN_DIR/DONE"
echo "$RUN_DIR" > runs/LATEST_MATRIX_RUN
