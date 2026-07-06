#!/bin/bash
#
# tools/test_catalog.sh - discover all streams, then split them into two bronze
# catalogs by replication method:
#   jira_bronze_master_data_catalog.json - FULL_TABLE streams (master data:
#       join dimensions / denormalization lookups, e.g. issue_fields,
#       workflow_statuses, projects, boards, ...)
#   jira_bronze_streams_catalog.json      - INCREMENTAL streams (event data:
#       issues, issue_comments, changelogs, issue_transitions, worklogs)
#
# Splitting by "forced-replication-method" (from discovery metadata) means no
# hardcoded stream list to maintain, and each catalog stays dependency-complete
# (FULL_TABLE children sit with their FULL_TABLE parents, likewise incremental).
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"   # tools/
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

if [ ! -d "$REPO_ROOT/venv/tap-jira" ]; then
    echo "Run ./tools/test_setup.sh first"
    exit 1
fi
command -v jq >/dev/null 2>&1 || { echo "jq is required (apt-get install jq)"; exit 1; }

. "$REPO_ROOT/venv/tap-jira/bin/activate"

CONFIG="$SCRIPT_DIR/test_config.json"
SRC="$SCRIPT_DIR/jira_source_catalog.json"
MASTER="$SCRIPT_DIR/jira_bronze_master_data_catalog.json"
STREAMS="$SCRIPT_DIR/jira_bronze_streams_catalog.json"

# Discovery -> full catalog. Emits every stream with its schema and metadata.
# (Discovery authenticates, so a failure here usually means bad credentials in
# tools/test_config.json.)
tap-jira --config "$CONFIG" --discover > "$SRC"
echo "Discovered the entire Jira source catalog - all streams"

# Select every stream whose breadcrumb-[] metadata has
# forced-replication-method == $1, writing the result to $2.
select_by_method() {
    local method="$1" out="$2"
    jq --arg m "$method" '
        .streams |= map(
          if any(.metadata[]; .breadcrumb==[] and .metadata."forced-replication-method"==$m)
          then .metadata |= map(if .breadcrumb==[] then .metadata.selected = true else . end)
          else . end)
      ' "$SRC" > "$out"
}

report_selected() {
    jq -r '.streams[]
           | select(any(.metadata[]; .breadcrumb==[] and .metadata.selected==true))
           | "  * " + .tap_stream_id' "$1"
}

select_by_method FULL_TABLE  "$MASTER"
select_by_method INCREMENTAL "$STREAMS"

echo ""
echo "Created $MASTER (master data / FULL_TABLE):"
report_selected "$MASTER"

echo ""
echo "Created $STREAMS (event streams / INCREMENTAL):"
report_selected "$STREAMS"

# (No jq? Open jira_source_catalog.json and add "selected": true inside the
# breadcrumb-[] metadata of the streams you want, saving to the catalog above.)
