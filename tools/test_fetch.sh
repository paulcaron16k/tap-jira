#!/bin/bash
#
# tools/test_fetch.sh - sync the selected streams from the bronze catalog.
#
#   ./tools/test_fetch.sh                 # full sync -> tools/records.jsonl
#   ./tools/test_fetch.sh --head 20       # stop after 20 output lines (quick peek)
#   ./tools/test_fetch.sh --state tools/state.json --out tools/records2.jsonl
#
# Options: --head N | --state FILE | --out FILE | --config FILE | --catalog FILE
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"   # tools/
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

CONFIG="$SCRIPT_DIR/test_config.json"
CATALOG="$SCRIPT_DIR/jira_bronze_catalog.json"
OUT="$SCRIPT_DIR/records.jsonl"
LOG="$SCRIPT_DIR/tap-fetch.log"
HEAD=""
STATE=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --head)              HEAD="${2:?--head needs a number}"; shift 2 ;;
    --head=*)            HEAD="${1#*=}"; shift ;;
    --state)             STATE="${2:?--state needs a file}"; shift 2 ;;
    --out)               OUT="${2:?--out needs a file}"; shift 2 ;;
    --config)            CONFIG="${2:?}"; shift 2 ;;
    --catalog|--properties) CATALOG="${2:?}"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

if [ ! -d "$REPO_ROOT/venv/tap-jira" ]; then
    echo "Run ./tools/test_setup.sh first"
    exit 1
fi
. "$REPO_ROOT/venv/tap-jira/bin/activate"

if [ ! -f "$CATALOG" ]; then
    echo "No $CATALOG - run ./tools/test_catalog.sh first"
    exit 1
fi

args=(--config "$CONFIG" --properties "$CATALOG")
[ -n "$STATE" ] && args+=(--state "$STATE")

# stdout = Singer messages (SCHEMA/RECORD/STATE); stderr = logs/metrics -> $LOG,
# so --head sees clean output and can stop the tap early.
echo ">> fetch ${HEAD:+(first $HEAD lines) }-> $OUT   (tap logs -> $LOG)" >&2
if [ -n "$HEAD" ]; then
    # head closes the pipe after N lines, stopping the tap via SIGPIPE (a
    # broken-pipe/CRITICAL line may appear in $LOG - that's expected). head is
    # placed before tee so $OUT is limited to the same N lines as the console.
    set +o pipefail
    tap-jira "${args[@]}" 2>"$LOG" | head -n "$HEAD" | tee "$OUT"
    set -o pipefail
else
    tap-jira "${args[@]}" 2>"$LOG" | tee "$OUT"
fi

echo ">> wrote $(wc -l < "$OUT") lines to $OUT" >&2

# Inspect the output:
#   jq -c 'select(.type=="RECORD" and .stream=="projects")' tools/records.jsonl | head
#   jq -r 'select(.type=="RECORD") | .stream' tools/records.jsonl | sort | uniq -c   # counts
#
# Resume incremental streams (issues, worklogs bookmark on `updated`):
#   jq -c 'select(.type=="STATE") | .value' tools/records.jsonl | tail -1 > tools/state.json
#   ./tools/test_fetch.sh --state tools/state.json --out tools/records2.jsonl
