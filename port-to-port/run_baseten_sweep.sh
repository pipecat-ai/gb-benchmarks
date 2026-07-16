#!/usr/bin/env bash
# Natural-variant port-to-port sweep for Baseten-hosted models.
#
# Configs (8):
#   zai-org/GLM-5.2                          thinking: none, high, xhigh
#   nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B thinking: none, high
#   thinkingmachines/inkling                  thinking: low, high, xhigh
# Inkling runs use max_tokens=16384; GLM/Nemotron use the 8192 default.
# (Nemotron Ultra reasoning is binary on Baseten, so only none + high are run.)
#
# Each config runs ROUNDS episodes in one strictly sequential process: one
# CONFIGS loop, one rounds loop, and one mini-rl-env.py process in flight at any
# moment. Already-completed rounds (valid JSON with a "success" key) are skipped,
# so the script is resumable. Console output is tee'd to per-run .log files, with
# RUN_START/RUN_EXIT markers in the sweep log.
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
CONFIG_FILTER="${CONFIG_FILTER:-}"
PRINT_CONFIGS="${PRINT_CONFIGS:-0}"

# config slug | model | thinking | max_tokens (optional; defaults to MAX_TOKENS)
CONFIGS=(
  "glm52-none|zai-org/GLM-5.2|none"
  "glm52-high|zai-org/GLM-5.2|high"
  "glm52-xhigh|zai-org/GLM-5.2|xhigh"
  "nemotron-ultra-none|nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B|none"
  "nemotron-ultra-high|nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B|high"
  "inkling-low|thinkingmachines/inkling|low|16384"
  "inkling-high|thinkingmachines/inkling|high|16384"
  "inkling-max|thinkingmachines/inkling|xhigh|16384"
)

config_is_selected() {
  local slug="$1"
  if [[ -z "$CONFIG_FILTER" ]]; then
    return 0
  fi
  local filters="${CONFIG_FILTER//[[:space:]]/}"
  filters=",$filters,"
  [[ "$filters" == *",$slug,"* ]]
}

CONFIG_SLUG=""
CONFIG_MODEL=""
CONFIG_THINKING=""
CONFIG_MAX_TOKENS=""
parse_config() {
  local spec="$1"
  local pipes="${spec//[^|]/}"
  local n="${#pipes}"
  if (( n != 2 && n != 3 )); then
    echo "ERROR: malformed config (expected slug|model|thinking[|max_tokens]): $spec" >&2
    return 1
  fi

  IFS='|' read -r CONFIG_SLUG CONFIG_MODEL CONFIG_THINKING CONFIG_MAX_TOKENS <<< "$spec"
  CONFIG_MAX_TOKENS="${CONFIG_MAX_TOKENS:-$MAX_TOKENS}"
  if [[ -z "$CONFIG_SLUG" || -z "$CONFIG_MODEL" || -z "$CONFIG_THINKING" ]]; then
    echo "ERROR: malformed config (expected slug|model|thinking[|max_tokens]): $spec" >&2
    return 1
  fi
}

if [[ "$PRINT_CONFIGS" == "1" ]]; then
  if (( $# > 0 )); then
    PRINT_CONFIG_SPECS=("$@")
  else
    PRINT_CONFIG_SPECS=("${CONFIGS[@]}")
  fi
  for spec in "${PRINT_CONFIG_SPECS[@]}"; do
    if ! parse_config "$spec"; then
      exit 2
    fi
    if config_is_selected "$CONFIG_SLUG"; then
      echo "CONFIG_PLAN slug=$CONFIG_SLUG model=$CONFIG_MODEL thinking=$CONFIG_THINKING max_tokens=$CONFIG_MAX_TOKENS"
    fi
  done
  exit 0
fi

TS="$(date -u +%Y%m%d-%H%M%S)"
# RUN_DIR may be overridden (e.g. to run one config per process into a shared
# parent) so several single-config sequential invocations can run in parallel.
RUN_DIR="${RUN_DIR:-runs/baseten-sweep-${TS}}"
PY=".venv/bin/python"

# Baseten uses the OpenAI-compatible client; the harness reads OPENAI_API_KEY.
BASETEN_API_KEY="$(grep '^BASETEN_API_KEY=' "$ENV_FILE" | cut -d= -f2-)"
if [[ -z "$BASETEN_API_KEY" ]]; then
  echo "ERROR: BASETEN_API_KEY not found in $ENV_FILE" >&2
  exit 1
fi
export OPENAI_API_KEY="$BASETEN_API_KEY"

mkdir -p "$RUN_DIR"
echo "RUN_DIR=$RUN_DIR ROUNDS=$ROUNDS configs=${#CONFIGS[@]} config_filter=${CONFIG_FILTER:-<none>}" | tee "$RUN_DIR/sweep.log"

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

fail=0
for spec in "${CONFIGS[@]}"; do
  if ! parse_config "$spec"; then
    exit 2
  fi
  slug="$CONFIG_SLUG"
  model="$CONFIG_MODEL"
  thinking="$CONFIG_THINKING"
  mt="$CONFIG_MAX_TOKENS"

  if ! config_is_selected "$slug"; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) CONFIG_SKIP slug=$slug reason=config_filter" | tee -a "$RUN_DIR/sweep.log"
    continue
  fi

  cfg_dir="$RUN_DIR/$slug"
  mkdir -p "$cfg_dir"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) CONFIG_START slug=$slug model=$model thinking=$thinking max_tokens=$mt" | tee -a "$RUN_DIR/sweep.log"

  for ((r=1; r<=ROUNDS; r++)); do
    printf -v rr "%02d" "$r"
    json_file="$cfg_dir/${slug}-r${rr}.json"
    log_file="$cfg_dir/${slug}-r${rr}.log"

    if round_is_done "$json_file"; then
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) SKIP slug=$slug round=r$rr reason=already_complete json=$json_file" | tee -a "$RUN_DIR/sweep.log"
      continue
    fi

    start_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    t0="$(date +%s)"
    echo "RUN_START timestamp=$start_ts slug=$slug round=r$rr rc=NA ok=NA elapsed_s=0 model=$model thinking=$thinking max_tokens=$mt json=$json_file log=$log_file" | tee -a "$RUN_DIR/sweep.log"

    timeout "$PER_RUN_TIMEOUT" "$PY" mini-rl-env.py \
      --provider openai \
      --model "$model" \
      --openai-base-url "$BASE_URL" \
      --task-variant natural \
      --thinking "$thinking" \
      --max-tokens "$mt" \
      --max-turns "$MAX_TURNS" \
      --function-call-timeout-secs "$FC_TIMEOUT" \
      --log-json "$json_file" 2>&1 | tee "$log_file"
    rc="${PIPESTATUS[0]}"

    elapsed="$(( $(date +%s) - t0 ))"
    ok="NO"
    if round_is_done "$json_file"; then
      ok="yes"
    fi
    exit_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "RUN_EXIT timestamp=$exit_ts slug=$slug round=r$rr rc=$rc ok=$ok elapsed_s=$elapsed model=$model thinking=$thinking max_tokens=$mt json=$json_file log=$log_file" | tee -a "$RUN_DIR/sweep.log"

    if [[ "$rc" -ne 0 ]]; then
      fail=1
    fi
  done

  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) CONFIG_COMPLETE slug=$slug" | tee -a "$RUN_DIR/sweep.log"
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
