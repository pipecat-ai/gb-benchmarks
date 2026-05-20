#!/usr/bin/env bash
set -u -o pipefail

cd /home/khkramer/src/gb-benchmarks/port-to-port

launch=0
if [[ "${1:-}" == "--launch" ]]; then
  launch=1
  shift
fi

if (( $# != 0 )); then
  echo "usage: $0 [--launch]" >&2
  exit 2
fi

TARGET="${TARGET:-25}"
MODEL="gemini-3.5-flash"
PROVIDER="google"
TASK_VARIANT="natural"
THINKING_LEVELS=(minimal low medium high)

TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="runs/gemini35-flash-thinking-sweep-${TS}"
mkdir -p "$RUN_DIR"

write_worker() {
  local thinking="$1"
  local worker_dir="$RUN_DIR/$thinking"
  local raw_dir="$worker_dir/raw"
  local accepted_dir="$worker_dir/accepted"
  local progress_log="$worker_dir/progress.log"
  local results_tsv="$worker_dir/results.tsv"
  local worker_log="$worker_dir/worker.log"
  local worker_sh="$worker_dir/worker.sh"
  local label="${MODEL}-${TASK_VARIANT}-${thinking}"

  mkdir -p "$raw_dir" "$accepted_dir"
  : > "$progress_log"
  : > "$worker_log"

  cat > "$worker_sh" <<EOF
#!/usr/bin/env bash
set -u -o pipefail
cd /home/khkramer/src/gb-benchmarks/port-to-port
GOOGLE_API_KEY="\$(rg --no-line-number '^GOOGLE_API_KEY=' /home/khkramer/src/gb-benchmarks/.env | cut -d= -f2-)"
bash ./run_repeat_clean_config.sh ${TARGET} "${label}" GOOGLE_API_KEY "\$GOOGLE_API_KEY" \\
  "${raw_dir}" "${accepted_dir}" "${progress_log}" "${results_tsv}" -- \\
  .venv/bin/python mini-rl-env.py --provider ${PROVIDER} --model ${MODEL} \\
  --task-variant ${TASK_VARIANT} --thinking ${thinking} \\
  --max-turns 50 --function-call-timeout-secs 20
EOF
  chmod +x "$worker_sh"

  if (( launch )); then
    nohup bash -lc "
      echo \"WORKER_START thinking=${thinking} at=\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
      bash \"$worker_sh\"
      rc=\$?
      echo \"WORKER_EXIT thinking=${thinking} rc=\${rc} at=\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
      exit \$rc
    " >> "$worker_log" 2>&1 < /dev/null &
    echo "$!" > "$worker_dir/worker.pid"
  fi

  echo "$worker_sh"
}

declare -a WORKERS
for thinking in "${THINKING_LEVELS[@]}"; do
  WORKERS+=("$(write_worker "$thinking")")
done

echo "RUN_DIR=$RUN_DIR"
echo "TARGET_PER_LEVEL=$TARGET"
for w in "${WORKERS[@]}"; do
  echo "WORKER=$w"
done

if (( launch )); then
  echo "LAUNCHED=1"
  for thinking in "${THINKING_LEVELS[@]}"; do
    echo "TAIL_${thinking}=$RUN_DIR/$thinking/progress.log"
  done
else
  echo "LAUNCHED=0"
  echo "Run all four workers in parallel:"
  echo "  bash $0 --launch"
  echo "Or one at a time:"
  for w in "${WORKERS[@]}"; do
    echo "  bash $w"
  done
fi
