#!/usr/bin/env bash
# Natural-variant port-to-port sweep for Baseten-hosted models.
#
# Configs (6):
#   zai-org/GLM-5.2                          thinking: none, low, medium, high
#   nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B thinking: none, high
# (Nemotron Ultra reasoning is binary on Baseten, so only none + high are run.)
#
# Each config runs ROUNDS episodes. Configs run as parallel background workers;
# each worker runs its rounds sequentially. Already-completed rounds (valid JSON
# with a "success" key) are skipped, so the script is resumable.
set -uo pipefail

cd "$(dirname "$0")"

ROUNDS="${ROUNDS:-25}"
# 8192 is a sanity ceiling for reasoning-on Baseten configs (Mechanism A);
# escalate if step-5 validation still shows truncation.
MAX_TOKENS="${MAX_TOKENS:-8192}"
MAX_TURNS="${MAX_TURNS:-50}"
FC_TIMEOUT="${FC_TIMEOUT:-30}"
PER_RUN_TIMEOUT="${PER_RUN_TIMEOUT:-600}"
BASE_URL="https://inference.baseten.co/v1"
ENV_FILE="/home/khkramer/src/gb-benchmarks/.env"

TS="$(date -u +%Y%m%d-%H%M%S)"
RUN_DIR="runs/baseten-sweep-${TS}"
PY=".venv/bin/python"

# Baseten uses the OpenAI-compatible client; the harness reads OPENAI_API_KEY.
BASETEN_API_KEY="$(grep '^BASETEN_API_KEY=' "$ENV_FILE" | cut -d= -f2-)"
if [[ -z "$BASETEN_API_KEY" ]]; then
  echo "ERROR: BASETEN_API_KEY not found in $ENV_FILE" >&2
  exit 1
fi
export OPENAI_API_KEY="$BASETEN_API_KEY"

# config slug | model | thinking
CONFIGS=(
  "glm52-none|zai-org/GLM-5.2|none"
  "glm52-low|zai-org/GLM-5.2|low"
  "glm52-medium|zai-org/GLM-5.2|medium"
  "glm52-high|zai-org/GLM-5.2|high"
  "nemotron-ultra-none|nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B|none"
  "nemotron-ultra-high|nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B|high"
)

mkdir -p "$RUN_DIR"
echo "RUN_DIR=$RUN_DIR ROUNDS=$ROUNDS configs=${#CONFIGS[@]}" | tee "$RUN_DIR/sweep.log"

round_is_done() {
  local f="$1"
  [[ -s "$f" ]] && "$PY" - "$f" <<'PYEOF' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    sys.exit(0 if isinstance(d.get("summary", {}).get("success"), bool) else 1)
except Exception:
    sys.exit(1)
PYEOF
}

run_config() {
  local spec="$1"
  local slug="${spec%%|*}"
  local rest="${spec#*|}"
  local model="${rest%%|*}"
  local thinking="${rest##*|}"
  local cfg_dir="$RUN_DIR/$slug"
  mkdir -p "$cfg_dir"
  local plog="$cfg_dir/progress.log"

  for ((r=1; r<=ROUNDS; r++)); do
    local rr; printf -v rr "%02d" "$r"
    local json_file="$cfg_dir/${slug}-r${rr}.json"
    if round_is_done "$json_file"; then
      echo "$(date -u +%H:%M:%S) SKIP  $slug r$rr (already complete)" >> "$plog"
      continue
    fi
    local t0=$(date +%s)
    timeout "$PER_RUN_TIMEOUT" "$PY" mini-rl-env.py \
      --provider openai \
      --model "$model" \
      --openai-base-url "$BASE_URL" \
      --task-variant natural \
      --thinking "$thinking" \
      --max-tokens "$MAX_TOKENS" \
      --max-turns "$MAX_TURNS" \
      --function-call-timeout-secs "$FC_TIMEOUT" \
      --log-json "$json_file" > "$cfg_dir/${slug}-r${rr}.out" 2>&1
    local rc=$?
    local elapsed=$(( $(date +%s) - t0 ))
    local ok="?"
    round_is_done "$json_file" && ok="yes" || ok="NO"
    echo "$(date -u +%H:%M:%S) DONE  $slug r$rr rc=$rc ok=$ok elapsed_s=$elapsed" >> "$plog"
  done
  echo "$(date -u +%H:%M:%S) CONFIG_COMPLETE $slug" >> "$plog"
}

pids=()
for spec in "${CONFIGS[@]}"; do
  run_config "$spec" &
  pids+=("$!")
  echo "launched worker pid=$! for ${spec%%|*}" | tee -a "$RUN_DIR/sweep.log"
done

fail=0
for pid in "${pids[@]}"; do
  wait "$pid" || fail=1
done

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) SWEEP_COMPLETE fail=$fail run_dir=$RUN_DIR" | tee -a "$RUN_DIR/sweep.log"

# Tally
echo "=== TALLY ===" | tee -a "$RUN_DIR/sweep.log"
"$PY" - "$RUN_DIR" <<'PYEOF' | tee -a "$RUN_DIR/sweep.log"
import json, sys, glob, os
run_dir = sys.argv[1]
from collections import defaultdict
agg = defaultdict(lambda: [0, 0])
for f in sorted(glob.glob(os.path.join(run_dir, "*", "*.json"))):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    s = d.get("summary", {})
    if not isinstance(s.get("success"), bool):
        continue
    cfg = d.get("config", {})
    key = f"{cfg.get('model')} th={cfg.get('thinking')}"
    agg[key][0] += 1 if s["success"] else 0
    agg[key][1] += 1
for key in sorted(agg):
    succ, tot = agg[key]
    pct = (100.0 * succ / tot) if tot else 0.0
    print(f"  {key:55s} {succ:2d}/{tot:2d}  {pct:5.1f}%")
PYEOF
echo "run_dir=$RUN_DIR"
exit $fail
