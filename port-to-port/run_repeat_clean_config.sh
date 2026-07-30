#!/usr/bin/env bash
set -u -o pipefail

if (( $# < 8 )); then
  echo "usage: $0 <target> <label> <env_name> <env_value> <json_dir> <accepted_dir> <progress_log> <results_tsv> -- <command...>" >&2
  exit 2
fi

TARGET="$1"
LABEL="$2"
ENV_NAME="$3"
ENV_VALUE="$4"
JSON_DIR="$5"
ACCEPTED_DIR="$6"
PROGRESS_LOG="$7"
RESULTS_TSV="$8"
shift 8

if [[ "${1:-}" != "--" ]]; then
  echo "missing -- before command" >&2
  exit 2
fi
shift

if (( $# == 0 )); then
  echo "missing command" >&2
  exit 2
fi

mkdir -p "$JSON_DIR" "$ACCEPTED_DIR"
echo -e "label\tclean_index\tattempt_index\texit_code\tclean\tjson\tlog" > "$RESULTS_TSV"

is_clean_run() {
  local json_file="$1"
  local log_file="$2"
  [[ -f "$json_file" ]] || return 1
  if rg -q "exception \\(|Something went wrong:|Traceback \\(most recent call last\\):|Idle timeout detected\\.|forced_retry_idle_timeout" "$log_file"; then
    return 1
  fi
  return 0
}

clean_count=0
attempt_count=0
while (( clean_count < TARGET )); do
  attempt_count=$(( attempt_count + 1 ))
  clean_index=$(( clean_count + 1 ))
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  stem="${LABEL}-c$(printf '%02d' "$clean_index")-a$(printf '%02d' "$attempt_count")-${ts}"
  slug="$(echo "$stem" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '_')"
  json_file="$JSON_DIR/${slug}.json"
  log_file="$JSON_DIR/${slug}.log"
  rc=0

  {
    echo "RUN_START label=${LABEL} clean_index=${clean_index} attempt_index=${attempt_count} at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    env "$ENV_NAME=$ENV_VALUE" "$@" --log-json "$json_file"
    rc=$?
    echo "RUN_EXIT label=${LABEL} clean_index=${clean_index} attempt_index=${attempt_count} rc=${rc} at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if is_clean_run "$json_file" "$log_file"; then
      echo "RUN_CLEAN label=${LABEL} clean_index=${clean_index} attempt_index=${attempt_count}"
    else
      echo "RUN_RETRY label=${LABEL} clean_index=${clean_index} attempt_index=${attempt_count}"
    fi
  } > "$log_file" 2>&1

  if is_clean_run "$json_file" "$log_file"; then
    clean_count=$clean_index
    ln -sfn "$(readlink -f "$json_file")" "$ACCEPTED_DIR/$(basename "$json_file")"
    echo -e "${LABEL}\t${clean_index}\t${attempt_count}\t${rc}\t1\t${json_file}\t${log_file}" >> "$RESULTS_TSV"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) label=${LABEL} clean=${clean_count}/${TARGET} attempts=${attempt_count}" >> "$PROGRESS_LOG"
  else
    echo -e "${LABEL}\t${clean_index}\t${attempt_count}\t${rc}\t0\t${json_file}\t${log_file}" >> "$RESULTS_TSV"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) label=${LABEL} retry-needed after attempt=${attempt_count}" >> "$PROGRESS_LOG"
  fi
done
