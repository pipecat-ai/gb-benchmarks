#!/usr/bin/env bash

ROOT=/home/khkramer/src/gb-benchmarks
PORT="$ROOT/port-to-port"
PROJECT="$PORT/proj-2026-07-30-gemma4-26b-a4b"
CAMPAIGN="$PORT/runs/gemma4-26b-a4b-baseten-vllm-nightly-apc-mtp-n25-20260730"
SCHEDULE="$PROJECT/frozen-order.tsv"
BASE_URL=https://model-qel1y223.api.baseten.co/deployment/qz4zpye/sync/v1
MODEL=google/gemma-4-26B-A4B-it
OPENAI_API_KEY="$(rg --no-line-number '^BASETEN_API_KEY=' "$ROOT/.env" | cut -d= -f2-)"
export OPENAI_API_KEY

mkdir -p "$CAMPAIGN"
touch "$CAMPAIGN/attempts.tsv" "$CAMPAIGN/canonical.tsv"
if [[ ! -s "$CAMPAIGN/attempts.tsv" ]]; then
  printf 'slot\tpair\tsetting\tattempt\tstarted_at\texit_code\traw_json\tclassification\n' >> "$CAMPAIGN/attempts.tsv"
fi
if [[ ! -s "$CAMPAIGN/canonical.tsv" ]]; then
  printf 'slot\tpair\tsetting\traw_json\n' >> "$CAMPAIGN/canonical.tsv"
fi

total_attempts=$(($(wc -l < "$CAMPAIGN/attempts.tsv") - 1))
high_replacements=$(awk -F '\t' 'NR>1 && $3=="high" && $8=="no_json" {n++} END {print n+0}' "$CAMPAIGN/attempts.tsv")
none_replacements=$(awk -F '\t' 'NR>1 && $3=="none" && $8=="no_json" {n++} END {print n+0}' "$CAMPAIGN/attempts.tsv")
stop=0

while IFS=$'\t' read -r slot pair setting; do
  [[ "$slot" == "slot" ]] && continue
  if awk -F '\t' -v s="$slot" 'NR>1 && $1==s {found=1} END {exit !found}' "$CAMPAIGN/canonical.tsv"; then
    echo "$(date -u +%FT%TZ) SLOT_SKIP slot=$slot pair=$pair setting=$setting reason=already_canonical"
    continue
  fi

  while true; do
    attempt=$(awk -F '\t' -v s="$slot" 'NR>1 && $1==s {n++} END {print n+1}' "$CAMPAIGN/attempts.tsv")
    if (( total_attempts >= 60 )); then
      echo "$(date -u +%FT%TZ) CAMPAIGN_STOP reason=total_attempt_ceiling attempts=$total_attempts"
      stop=1
      break
    fi
    if [[ "$setting" == "high" ]] && (( attempt > 1 && high_replacements >= 5 )); then
      echo "$(date -u +%FT%TZ) CAMPAIGN_STOP reason=high_replacement_ceiling replacements=$high_replacements"
      stop=1
      break
    fi
    if [[ "$setting" == "none" ]] && (( attempt > 1 && none_replacements >= 5 )); then
      echo "$(date -u +%FT%TZ) CAMPAIGN_STOP reason=none_replacement_ceiling replacements=$none_replacements"
      stop=1
      break
    fi

    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    started_at="$(date -u +%FT%TZ)"
    stem="gemma4-26b-a4b-baseten-h100-vllm-nightly-apc-mtp-natural-${setting}-slot$(printf '%02d' "$slot")-pair$(printf '%02d' "$pair")-attempt$(printf '%02d' "$attempt")-${ts}"
    raw="$CAMPAIGN/$stem.json"
    log="$CAMPAIGN/$stem.log"
    echo "$started_at RUN_START slot=$slot pair=$pair setting=$setting attempt=$attempt stem=$stem"

    timeout --signal=INT --kill-after=30s 900s \
      "$PORT/.venv/bin/python" "$PORT/mini-rl-env.py" \
        --provider openai \
        --model "$MODEL" \
        --openai-base-url "$BASE_URL" \
        --task-variant natural \
        --thinking "$setting" \
        --max-tokens 4096 \
        --max-turns 50 \
        --function-call-timeout-secs 20 \
        --log-json "$raw" \
        2>&1 | tee "$log"
    rc=${PIPESTATUS[0]}
    total_attempts=$((total_attempts + 1))
    echo "$(date -u +%FT%TZ) RUN_EXIT slot=$slot pair=$pair setting=$setting attempt=$attempt rc=$rc stem=$stem"

    if [[ -s "$raw" ]]; then
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$slot" "$pair" "$setting" "$attempt" "$started_at" "$rc" "$raw" "canonical_json" \
        >> "$CAMPAIGN/attempts.tsv"
      printf '%s\t%s\t%s\t%s\n' "$slot" "$pair" "$setting" "$raw" >> "$CAMPAIGN/canonical.tsv"
      break
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$slot" "$pair" "$setting" "$attempt" "$started_at" "$rc" "$raw" "no_json" \
      >> "$CAMPAIGN/attempts.tsv"
    if [[ "$setting" == "high" ]]; then
      high_replacements=$((high_replacements + 1))
    else
      none_replacements=$((none_replacements + 1))
    fi
  done

  (( stop == 1 )) && break
done < "$SCHEDULE"

unset OPENAI_API_KEY
canonical_count=$(($(wc -l < "$CAMPAIGN/canonical.tsv") - 1))
echo "$(date -u +%FT%TZ) CAMPAIGN_DONE canonical=$canonical_count attempts=$total_attempts high_replacements=$high_replacements none_replacements=$none_replacements"
if (( canonical_count == 50 )); then
  exit 0
fi
exit 1
