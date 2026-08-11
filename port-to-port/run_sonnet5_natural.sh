#!/usr/bin/env bash
# Add Claude Sonnet 5 to the NATURAL leaderboard, additively and non-destructively.
#
# Phase 1 (generate): N clean runs per effort level (none/low/medium/high/xhigh),
#   5 levels in parallel, retry-until-clean (same clean-check as the canonical sweep).
# Phase 2 (judge): judge ONLY the new Sonnet 5 runs with the standard judge.
# Phase 3 (build): rebuild a REFRESH leaderboard md that REUSES the existing 1300
#   enriched rows verbatim (existing models' numbers stay byte-identical) and adds
#   Sonnet 5. The canonical input dir and canonical leaderboard md are left untouched;
#   promotion is a separate, manual step printed at the end.
#
# Env overrides: TARGET_PER_CONFIG (25), MAX_ATTEMPTS_PER_CONFIG (60),
#   LEVELS ("none low medium high xhigh"), JUDGE_MODEL (claude-sonnet-4-6),
#   SKIP_GENERATE=1 (reuse an existing $RUN_DIR for phases 2-3; pass TS as $1).
set -u -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

TS="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
MODEL="claude-sonnet-5"
TARGET_PER_CONFIG="${TARGET_PER_CONFIG:-25}"
MAX_ATTEMPTS_PER_CONFIG="${MAX_ATTEMPTS_PER_CONFIG:-60}"
read -r -a LEVELS <<< "${LEVELS:-none low medium high xhigh}"
JUDGE_MODEL="${JUDGE_MODEL:-claude-sonnet-4-6}"
# Optional: fold prior-run clean dirs + their enriched jsonls into the final build,
# so a partial re-run (e.g. just `none`) still produces the complete board.
read -r -a EXTRA_CLEAN_DIRS <<< "${EXTRA_CLEAN_DIRS:-}"
read -r -a EXTRA_ENRICHED <<< "${EXTRA_ENRICHED:-}"

PY="$SCRIPT_DIR/.venv/bin/python"
REPO_ENV="/home/khkramer/src/gb-benchmarks/.env"
CANON_INPUT="$SCRIPT_DIR/runs/leaderboard-natural-v1-input"
EXISTING_ENRICHED="$SCRIPT_DIR/runs/leaderboard-natural-v1-refresh-20260629.jsonl"

RUN_DIR="$SCRIPT_DIR/runs/sonnet5-natural-${TS}"
CLEAN_DIR="$RUN_DIR/clean"
EVAL_DIR="$RUN_DIR/eval"
UNION_DIR="$RUN_DIR/leaderboard-input-union"
MERGED_ENRICHED="$RUN_DIR/merged-enriched.jsonl"
OUT_MD="$SCRIPT_DIR/runs/leaderboard-natural-v1-refresh-sonnet5-${TS}.md"
PROGRESS="$RUN_DIR/progress.log"

mkdir -p "$RUN_DIR" "$CLEAN_DIR" "$EVAL_DIR" "$UNION_DIR"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$PROGRESS"; }

# --- credentials: extract directly (repo .env has a malformed line that breaks `source`) ---
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  ANTHROPIC_API_KEY="$(rg --no-line-number '^ANTHROPIC_API_KEY=' "$REPO_ENV" | head -1 | cut -d= -f2- | tr -d '"'"'"'"' | tr -d "'")"
fi
export ANTHROPIC_API_KEY
[[ -n "$ANTHROPIC_API_KEY" ]] || { echo "ERROR: no ANTHROPIC_API_KEY" >&2; exit 2; }
[[ -f "$EXISTING_ENRICHED" ]] || { echo "ERROR: missing existing enriched jsonl: $EXISTING_ENRICHED" >&2; exit 2; }
[[ -d "$CANON_INPUT" ]] || { echo "ERROR: missing canonical input dir: $CANON_INPUT" >&2; exit 2; }

is_clean_run() {
  local json_file="$1" log_file="$2"
  [[ -f "$json_file" ]] || return 1
  if rg -q "exception \(|Something went wrong:|Traceback \(most recent call last\):|Idle timeout detected\.|forced_retry_idle_timeout" "$log_file"; then
    return 1
  fi
  return 0
}

run_level() {
  local level="$1"
  local dir="$RUN_DIR/$level"
  mkdir -p "$dir"
  local clean=0 attempt=0
  while (( clean < TARGET_PER_CONFIG )); do
    if (( attempt >= MAX_ATTEMPTS_PER_CONFIG )); then
      log "[$level] ATTEMPT-CAP hit attempts=$attempt clean=$clean/$TARGET_PER_CONFIG"
      return 0
    fi
    attempt=$(( attempt + 1 ))
    local ci=$(( clean + 1 ))
    local stem="${MODEL}-natural-${level}-c$(printf '%02d' "$ci")-a$(printf '%02d' "$attempt")-${TS}"
    local json="$dir/$stem.json"
    local logf="$dir/$stem.log"
    "$PY" mini-rl-env.py --provider anthropic --model "$MODEL" --task-variant natural \
      --thinking "$level" --max-turns 50 --function-call-timeout-secs 20 \
      --log-json "$json" > "$logf" 2>&1
    if is_clean_run "$json" "$logf"; then
      clean=$(( clean + 1 ))
      ln -sfn "$(realpath "$json")" "$CLEAN_DIR/$(basename "$json")"
      log "[$level] clean=$clean/$TARGET_PER_CONFIG (attempt=$attempt)"
    else
      log "[$level] retry (attempt=$attempt, clean=$clean) -- not a clean run"
      sleep 3
    fi
  done
  log "[$level] DONE clean=$clean attempts=$attempt"
}

# ---------------- Phase 1: generate ----------------
if [[ "${SKIP_GENERATE:-0}" != "1" ]]; then
  log "PHASE1 generate model=$MODEL levels=[${LEVELS[*]}] target=$TARGET_PER_CONFIG (parallel by level)"
  pids=()
  for lvl in "${LEVELS[@]}"; do run_level "$lvl" & pids+=($!); done
  for p in "${pids[@]}"; do wait "$p" || true; done
else
  log "PHASE1 skipped (SKIP_GENERATE=1); reusing $CLEAN_DIR"
fi

clean_count=$(find "$CLEAN_DIR" -maxdepth 1 -name '*.json' | wc -l | tr -d ' ')
log "PHASE1 done: $clean_count clean Sonnet 5 runs staged in $CLEAN_DIR"
[[ "$clean_count" -gt 0 ]] || { echo "ERROR: no clean runs produced" >&2; exit 3; }
EXPECTED_THIS_RUN=$(( TARGET_PER_CONFIG * ${#LEVELS[@]} ))
if [[ "${SKIP_GENERATE:-0}" != "1" && "$clean_count" -lt "$EXPECTED_THIS_RUN" ]]; then
  echo "ERROR: incomplete generation ($clean_count/$EXPECTED_THIS_RUN clean); a run_level worker likely died." >&2
  echo "Aborting before build to avoid a partial board. Re-run to regenerate." >&2
  exit 5
fi

# ---------------- Phase 2: judge ONLY the new runs ----------------
log "PHASE2 judge $clean_count new runs with judge=$JUDGE_MODEL"
"$PY" evaluate_runs.py "$CLEAN_DIR/*.json" \
  --out-dir "$EVAL_DIR" \
  --report-accuracy-judge llm \
  --judge-model "$JUDGE_MODEL"
SONNET5_ENRICHED="$EVAL_DIR/enriched_runs.jsonl"
[[ -f "$SONNET5_ENRICHED" ]] || { echo "ERROR: judge produced no enriched jsonl" >&2; exit 4; }
log "PHASE2 done: $(wc -l < "$SONNET5_ENRICHED") enriched Sonnet 5 rows"

# ---------------- Phase 3: additive rebuild (non-destructive) ----------------
log "PHASE3 build union dir + merged enriched + leaderboard md"
# Union dir: existing corpus (untouched canonical input) + new Sonnet 5 runs.
# All symlinks; Path.resolve() chases to the real run file on both the runs side
# and the enriched `file` side, so the path-keyed join matches.
find "$UNION_DIR" -mindepth 1 -maxdepth 1 -delete 2>/dev/null || true
while IFS= read -r e; do
  ln -sfn "$(realpath "$e")" "$UNION_DIR/$(basename "$e")"
done < <(find "$CANON_INPUT" -maxdepth 1 -name '*.json')
while IFS= read -r j; do
  ln -sfn "$(realpath "$j")" "$UNION_DIR/$(basename "$j")"
done < <(find "$CLEAN_DIR" -maxdepth 1 -name '*.json')
for xd in "${EXTRA_CLEAN_DIRS[@]}"; do
  [[ -n "$xd" && -d "$xd" ]] || continue
  while IFS= read -r j; do
    ln -sfn "$(realpath "$j")" "$UNION_DIR/$(basename "$j")"
  done < <(find "$xd" -maxdepth 1 -name '*.json')
done

cat_inputs=("$EXISTING_ENRICHED" "$SONNET5_ENRICHED")
for xe in "${EXTRA_ENRICHED[@]}"; do
  [[ -n "$xe" && -f "$xe" ]] && cat_inputs+=("$xe")
done
cat "${cat_inputs[@]}" > "$MERGED_ENRICHED"
union_count=$(find "$UNION_DIR" -maxdepth 1 -name '*.json' | wc -l | tr -d ' ')
merged_rows=$(wc -l < "$MERGED_ENRICHED")
log "PHASE3 union_runs=$union_count merged_enriched_rows=$merged_rows"

"$PY" build_primary_leaderboard.py \
  --runs-glob "$UNION_DIR/*.json" \
  --enriched-jsonl "$MERGED_ENRICHED" \
  --leaderboard-prompt-id natural \
  --out "$OUT_MD"

log "DONE refresh leaderboard -> $OUT_MD"
cat > "$RUN_DIR/DONE" <<EOF
finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status=OK
clean_runs=$clean_count
levels=${LEVELS[*]}
target_per_config=$TARGET_PER_CONFIG
refresh_leaderboard=$OUT_MD
canonical_leaderboard_untouched=leaderboards/leaderboard-natural.md
EOF

cat <<EOF

================ SONNET 5 SWEEP COMPLETE ================
Clean runs: $clean_count   Levels: ${LEVELS[*]}
Refresh leaderboard (review this): $OUT_MD
Canonical board left untouched:    leaderboards/leaderboard-natural.md

To PROMOTE Sonnet 5 onto the canonical corpus once you're happy with the refresh:
  # add the new runs into the master input dir
  for j in "$CLEAN_DIR"/*.json; do ln -sfn "\$(realpath "\$j")" "$CANON_INPUT/\$(basename "\$j")"; done
  # adopt the merged enriched rows as the new canonical enriched set
  cp "$MERGED_ENRICHED" runs/leaderboard-natural-v1-refresh-\$(date -u +%Y%m%d).jsonl
  # then rebuild leaderboards/leaderboard-natural.md from the corpus with build_primary_leaderboard.py
========================================================
EOF
