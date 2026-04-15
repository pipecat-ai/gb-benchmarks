#!/usr/bin/env bash
set -u -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

TS="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
TARGET_PER_CONFIG="${TARGET_PER_CONFIG:-25}"
RUN_DIR="runs/natural-leaderboard-sweep-${TS}"
ACCEPTED_DIR="$RUN_DIR/accepted"
JUDGEABLE_DIR="$RUN_DIR/judgeable"
LATEST_PTR="runs/LATEST_NATURAL_LEADERBOARD_SWEEP"
CONFIG_COUNT=28
EXPECTED_ACCEPTED_COUNT=$(( TARGET_PER_CONFIG * CONFIG_COUNT ))

mkdir -p \
  "$RUN_DIR/anthropic" \
  "$RUN_DIR/openai" \
  "$RUN_DIR/google" \
  "$RUN_DIR/nemotron-nano" \
  "$RUN_DIR/nemotron-super" \
  "$RUN_DIR/gemma4" \
  "$ACCEPTED_DIR" \
  "$JUDGEABLE_DIR"

echo "$RUN_DIR" > "$LATEST_PTR"

sanitize_slug() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '_'
}

extract_key() {
  local key="$1"
  rg --no-line-number "^${key}=" /home/khkramer/src/gb-benchmarks/.env | cut -d= -f2-
}

ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-$(extract_key ANTHROPIC_API_KEY)}"
OPENAI_API_KEY="${OPENAI_API_KEY:-$(extract_key OPENAI_API_KEY)}"
GOOGLE_API_KEY="${GOOGLE_API_KEY:-$(extract_key GOOGLE_API_KEY)}"

if [[ -z "$ANTHROPIC_API_KEY" || -z "$OPENAI_API_KEY" || -z "$GOOGLE_API_KEY" ]]; then
  echo "ERROR: missing one or more API keys" >&2
  exit 2
fi

NEMO_NANO_URL="https://daily--nemotron-nano-b200-sglang-serve.modal.run"
NEMO_SUPER_URL="https://daily--nemotron-super-b200-sglang-serve.modal.run"
GEMMA4_URL="https://daily--gemma4-31b-vllm.modal.run"

is_clean_run() {
  local json_file="$1"
  local log_file="$2"
  [[ -f "$json_file" ]] || return 1
  if rg -q "exception \\(|Something went wrong:|Traceback \\(most recent call last\\):|Idle timeout detected\\.|forced_retry_idle_timeout" "$log_file"; then
    return 1
  fi
  return 0
}

run_cmd_with_env() {
  local env_name="$1"
  local env_value="$2"
  shift 2
  env "$env_name=$env_value" "$@"
}

build_cmd() {
  local worker="$1"
  local label="$2"
  local json_file="$3"
  local -n out_cmd="$4"

  case "${worker}:${label}" in
    anthropic:claude-sonnet-4-6-natural-none)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider anthropic --model claude-sonnet-4-6 --task-variant natural --thinking none --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    anthropic:claude-sonnet-4-6-natural-low)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider anthropic --model claude-sonnet-4-6 --task-variant natural --thinking low --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    anthropic:claude-sonnet-4-6-natural-medium)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider anthropic --model claude-sonnet-4-6 --task-variant natural --thinking medium --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    anthropic:claude-haiku-4-5-natural-low)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider anthropic --model claude-haiku-4-5-20251001 --task-variant natural --thinking low --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    anthropic:claude-haiku-4-5-natural-medium)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider anthropic --model claude-haiku-4-5-20251001 --task-variant natural --thinking medium --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;

    openai:gpt-5.2-natural-medium)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model gpt-5.2 --task-variant natural --thinking medium --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    openai:gpt-5.1-natural-low)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model gpt-5.1 --task-variant natural --thinking low --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    openai:gpt-5.1-natural-medium)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model gpt-5.1 --task-variant natural --thinking medium --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    openai:gpt-4.1-natural-none)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model gpt-4.1 --task-variant natural --thinking none --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    openai:gpt-5.4-mini-natural-none)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model gpt-5.4-mini --task-variant natural --thinking none --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    openai:gpt-5.4-mini-natural-low)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model gpt-5.4-mini --task-variant natural --thinking low --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    openai:gpt-5.4-mini-natural-medium)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model gpt-5.4-mini --task-variant natural --thinking medium --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    openai:gpt-5.4-mini-natural-high)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model gpt-5.4-mini --task-variant natural --thinking high --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    openai:gpt-5.4-mini-natural-xhigh)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model gpt-5.4-mini --task-variant natural --thinking xhigh --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;

    google:gemini-3.1-flash-lite-preview-natural-minimal)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider google --model gemini-3.1-flash-lite-preview --task-variant natural --thinking minimal --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    google:gemini-3.1-flash-lite-preview-natural-medium)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider google --model gemini-3.1-flash-lite-preview --task-variant natural --thinking medium --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    google:gemini-3.1-flash-lite-preview-natural-high)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider google --model gemini-3.1-flash-lite-preview --task-variant natural --thinking high --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    google:gemini-3.1-pro-preview-natural-medium)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider google --model gemini-3.1-pro-preview --task-variant natural --thinking medium --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    google:gemini-2.5-flash-natural-budget2048)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider google --model gemini-2.5-flash --task-variant natural --thinking-budget 2048 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;

    nemotron-nano:nemotron-3-nano-30b-natural-none)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model nemotron-3-nano-30b --openai-base-url "$NEMO_NANO_URL" --task-variant natural --thinking none --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    nemotron-nano:nemotron-3-nano-30b-natural-low)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model nemotron-3-nano-30b --openai-base-url "$NEMO_NANO_URL" --task-variant natural --thinking low --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    nemotron-nano:nemotron-3-nano-30b-natural-medium)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model nemotron-3-nano-30b --openai-base-url "$NEMO_NANO_URL" --task-variant natural --thinking medium --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    nemotron-nano:nemotron-3-nano-30b-natural-high)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model nemotron-3-nano-30b --openai-base-url "$NEMO_NANO_URL" --task-variant natural --thinking high --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;

    nemotron-super:nemotron-3-super-120b-natural-none)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model nemotron-3-super-120b --openai-base-url "$NEMO_SUPER_URL" --task-variant natural --thinking none --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    nemotron-super:nemotron-3-super-120b-natural-low)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model nemotron-3-super-120b --openai-base-url "$NEMO_SUPER_URL" --task-variant natural --thinking low --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    nemotron-super:nemotron-3-super-120b-natural-medium)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model nemotron-3-super-120b --openai-base-url "$NEMO_SUPER_URL" --task-variant natural --thinking medium --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    nemotron-super:nemotron-3-super-120b-natural-high)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model nemotron-3-super-120b --openai-base-url "$NEMO_SUPER_URL" --task-variant natural --thinking high --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;

    gemma4:gemma-4-31b-natural-high)
      out_cmd=(.venv/bin/python mini-rl-env.py --provider openai --model gemma-4-31b --openai-base-url "$GEMMA4_URL" --task-variant natural --thinking high --max-tokens 4096 --max-turns 50 --function-call-timeout-secs 20 --log-json "$json_file")
      ;;
    *)
      echo "ERROR: unsupported worker/label combination: ${worker}:${label}" >&2
      return 1
      ;;
  esac
}

run_worker() {
  local worker="$1"
  shift
  local -a labels=("$@")
  local results_file="$RUN_DIR/${worker}-results.tsv"
  local progress_log="$RUN_DIR/${worker}-progress.log"
  local worker_dir="$RUN_DIR/${worker}"
  local env_name=""
  local env_value=""

  case "$worker" in
    anthropic)
      env_name="ANTHROPIC_API_KEY"
      env_value="$ANTHROPIC_API_KEY"
      ;;
    google)
      env_name="GOOGLE_API_KEY"
      env_value="$GOOGLE_API_KEY"
      ;;
    openai|nemotron-nano|nemotron-super)
      env_name="OPENAI_API_KEY"
      env_value="$OPENAI_API_KEY"
      ;;
    gemma4)
      env_name="OPENAI_API_KEY"
      env_value="dummy"
      ;;
    *)
      echo "ERROR: unknown worker $worker" >&2
      return 2
      ;;
  esac

  echo -e "worker\tlabel\tclean_index\tattempt_index\texit_code\tclean\tjson\tlog" > "$results_file"

  declare -A clean_counts
  declare -A attempt_counts
  for label in "${labels[@]}"; do
    clean_counts["$label"]=0
    attempt_counts["$label"]=0
  done

  local remaining=1
  while (( remaining )); do
    remaining=0
    for label in "${labels[@]}"; do
      local clean_count="${clean_counts[$label]}"
      if (( clean_count >= TARGET_PER_CONFIG )); then
        continue
      fi
      remaining=1

      local attempt_index=$(( attempt_counts[$label] + 1 ))
      attempt_counts["$label"]=$attempt_index
      local clean_index=$(( clean_count + 1 ))
      local stem="${label}-c$(printf '%02d' "$clean_index")-a$(printf '%02d' "$attempt_index")-${TS}"
      local slug
      slug="$(sanitize_slug "$stem")"
      local json_file="$worker_dir/${slug}.json"
      local log_file="$worker_dir/${slug}.log"
      local -a cmd=()

      build_cmd "$worker" "$label" "$json_file" cmd || return 2

      local rc=0
      {
        echo "RUN_START worker=${worker} label=${label} clean_index=${clean_index} attempt_index=${attempt_index} at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        run_cmd_with_env "$env_name" "$env_value" "${cmd[@]}"
        rc=$?
        echo "RUN_EXIT worker=${worker} label=${label} clean_index=${clean_index} attempt_index=${attempt_index} rc=${rc} at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        if is_clean_run "$json_file" "$log_file"; then
          echo "RUN_CLEAN worker=${worker} label=${label} clean_index=${clean_index} attempt_index=${attempt_index}"
        else
          echo "RUN_RETRY worker=${worker} label=${label} clean_index=${clean_index} attempt_index=${attempt_index}"
        fi
      } > "$log_file" 2>&1

      if [[ -f "$json_file" ]]; then
        ln -sfn "$(pwd)/$json_file" "$JUDGEABLE_DIR/$(basename "$json_file")"
      fi

      if is_clean_run "$json_file" "$log_file"; then
        clean_counts["$label"]=$clean_index
        ln -sfn "$(pwd)/$json_file" "$ACCEPTED_DIR/$(basename "$json_file")"
        echo -e "${worker}\t${label}\t${clean_index}\t${attempt_index}\t${rc}\t1\t${json_file}\t${log_file}" >> "$results_file"
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) worker=${worker} label=${label} clean=${clean_index}/${TARGET_PER_CONFIG} attempts=${attempt_index}" >> "$progress_log"
      else
        echo -e "${worker}\t${label}\t${clean_index}\t${attempt_index}\t${rc}\t0\t${json_file}\t${log_file}" >> "$results_file"
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) worker=${worker} label=${label} retry-needed after attempt=${attempt_index}" >> "$progress_log"
      fi
    done
  done
}

rebuild_leaderboard_input_dir() {
  local input_dir="$1"
  mkdir -p "$input_dir"
  find "$input_dir" -mindepth 1 -maxdepth 1 \( -type f -o -type l \) -name '*.json' -delete

  while IFS= read -r judgeable_json; do
    ln -sfn "$(readlink -f "$judgeable_json")" "$input_dir/$(basename "$judgeable_json")"
  done < <(find "$JUDGEABLE_DIR" -maxdepth 1 -type l -name '*.json' | sort)
}

refresh_leaderboard() {
  local refresh_tag="$1"
  local leaderboard_input_dir="runs/leaderboard-natural-v1-input"
  local leaderboard_input_glob="${leaderboard_input_dir}/*.json"
  local refresh_enriched_jsonl="runs/leaderboard-natural-v1-refresh-${refresh_tag}.jsonl"
  local refresh_leaderboard_md="runs/leaderboard-natural-v1-refresh-${refresh_tag}.md"
  local accepted_count
  accepted_count="$(find "$ACCEPTED_DIR" -maxdepth 1 -type l -name '*.json' | wc -l | tr -d ' ')"
  if [[ "$accepted_count" != "$EXPECTED_ACCEPTED_COUNT" ]]; then
    echo "ERROR: expected ${EXPECTED_ACCEPTED_COUNT} accepted JSONs before refresh, found ${accepted_count}" >&2
    return 2
  fi

  rebuild_leaderboard_input_dir "$leaderboard_input_dir"

  local refresh_out="runs/eval-leaderboard-natural-v1-refresh-${refresh_tag}"
  ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" .venv/bin/python evaluate_runs.py \
    "$leaderboard_input_glob" \
    --out-dir "$refresh_out" \
    --report-accuracy-judge llm \
    --judge-model claude-sonnet-4-6

  cp "$refresh_out/enriched_runs.jsonl" "$refresh_enriched_jsonl"

  .venv/bin/python build_primary_leaderboard.py \
    --runs-glob "$leaderboard_input_glob" \
    --enriched-jsonl "$refresh_enriched_jsonl" \
    --leaderboard-prompt-id natural \
    --out "$refresh_leaderboard_md"

  echo "refresh leaderboard written to ${refresh_leaderboard_md}"
  echo "canonical leaderboard left untouched at leaderboards/leaderboard-natural.md"
}

ANTHROPIC_LABELS=(
  "claude-sonnet-4-6-natural-none"
  "claude-sonnet-4-6-natural-low"
  "claude-sonnet-4-6-natural-medium"
  "claude-haiku-4-5-natural-low"
  "claude-haiku-4-5-natural-medium"
)

OPENAI_LABELS=(
  "gpt-5.2-natural-medium"
  "gpt-5.1-natural-low"
  "gpt-5.1-natural-medium"
  "gpt-4.1-natural-none"
  "gpt-5.4-mini-natural-none"
  "gpt-5.4-mini-natural-low"
  "gpt-5.4-mini-natural-medium"
  "gpt-5.4-mini-natural-high"
  "gpt-5.4-mini-natural-xhigh"
)

GOOGLE_LABELS=(
  "gemini-3.1-flash-lite-preview-natural-minimal"
  "gemini-3.1-flash-lite-preview-natural-medium"
  "gemini-3.1-flash-lite-preview-natural-high"
  "gemini-3.1-pro-preview-natural-medium"
  "gemini-2.5-flash-natural-budget2048"
)

NANO_LABELS=(
  "nemotron-3-nano-30b-natural-none"
  "nemotron-3-nano-30b-natural-low"
  "nemotron-3-nano-30b-natural-medium"
  "nemotron-3-nano-30b-natural-high"
)

SUPER_LABELS=(
  "nemotron-3-super-120b-natural-none"
  "nemotron-3-super-120b-natural-low"
  "nemotron-3-super-120b-natural-medium"
  "nemotron-3-super-120b-natural-high"
)

GEMMA4_LABELS=(
  "gemma-4-31b-natural-high"
)

cat > "$RUN_DIR/README.txt" <<EOF
started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
run_dir=$RUN_DIR
target_per_config=$TARGET_PER_CONFIG
prompt_scope=natural
config_count=$CONFIG_COUNT
expected_accepted_json_count=$EXPECTED_ACCEPTED_COUNT
clean_run_definition=json_exists_and_no_provider_exception_markers_in_log
EOF

run_worker anthropic "${ANTHROPIC_LABELS[@]}" > "$RUN_DIR/anthropic-worker.out" 2>&1 &
PID_ANTHROPIC=$!
run_worker openai "${OPENAI_LABELS[@]}" > "$RUN_DIR/openai-worker.out" 2>&1 &
PID_OPENAI=$!
run_worker google "${GOOGLE_LABELS[@]}" > "$RUN_DIR/google-worker.out" 2>&1 &
PID_GOOGLE=$!
run_worker nemotron-nano "${NANO_LABELS[@]}" > "$RUN_DIR/nemotron-nano-worker.out" 2>&1 &
PID_NANO=$!
run_worker nemotron-super "${SUPER_LABELS[@]}" > "$RUN_DIR/nemotron-super-worker.out" 2>&1 &
PID_SUPER=$!
run_worker gemma4 "${GEMMA4_LABELS[@]}" > "$RUN_DIR/gemma4-worker.out" 2>&1 &
PID_GEMMA4=$!

cat > "$RUN_DIR/PIDS" <<EOF
anthropic_pid=$PID_ANTHROPIC
openai_pid=$PID_OPENAI
google_pid=$PID_GOOGLE
nemotron_nano_pid=$PID_NANO
nemotron_super_pid=$PID_SUPER
gemma4_pid=$PID_GEMMA4
EOF

wait "$PID_ANTHROPIC"; RC_ANTHROPIC=$?
wait "$PID_OPENAI"; RC_OPENAI=$?
wait "$PID_GOOGLE"; RC_GOOGLE=$?
wait "$PID_NANO"; RC_NANO=$?
wait "$PID_SUPER"; RC_SUPER=$?
wait "$PID_GEMMA4"; RC_GEMMA4=$?

if (( RC_ANTHROPIC != 0 || RC_OPENAI != 0 || RC_GOOGLE != 0 || RC_NANO != 0 || RC_SUPER != 0 || RC_GEMMA4 != 0 )); then
  cat > "$RUN_DIR/DONE" <<EOF
finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status=WORKER_FAILED
anthropic_exit=$RC_ANTHROPIC
openai_exit=$RC_OPENAI
google_exit=$RC_GOOGLE
nemotron_nano_exit=$RC_NANO
nemotron_super_exit=$RC_SUPER
gemma4_exit=$RC_GEMMA4
EOF
  exit 1
fi

refresh_leaderboard "$TS"

cat > "$RUN_DIR/DONE" <<EOF
finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status=OK
anthropic_exit=$RC_ANTHROPIC
openai_exit=$RC_OPENAI
google_exit=$RC_GOOGLE
nemotron_nano_exit=$RC_NANO
nemotron_super_exit=$RC_SUPER
gemma4_exit=$RC_GEMMA4
accepted_json_count=$(find "$ACCEPTED_DIR" -maxdepth 1 -type l -name '*.json' | wc -l)
judgeable_json_count=$(find "$JUDGEABLE_DIR" -maxdepth 1 -type l -name '*.json' | wc -l)
leaderboard=runs/leaderboard-natural-v1-refresh-${TS}.md
canonical_leaderboard=leaderboards/leaderboard-natural.md
EOF
