#!/bin/bash
#
# tools/test_catalog.sh - discover all streams, then write
# tools/jira_bronze_catalog.json with the streams in WANT selected.
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
BRONZE="$SCRIPT_DIR/jira_bronze_catalog.json"

# Discovery -> full catalog. Emits every stream with its schema and metadata.
# Nothing is "selected" yet. (Discovery authenticates, so a failure here usually
# means bad credentials in tools/test_config.json.)
tap-jira --config "$CONFIG" --discover > "$SRC"
echo "Discovered the entire Jira source catalog - all streams"

# Build the bronze catalog with the streams you want. The tap syncs a stream
# only if its breadcrumb [] metadata has "selected": true.
#
# Edit this list. Dependency rules - validate_dependencies() hard-fails if a
# child is selected without its parent:
#   - versions, components                          -> require projects
#   - changelogs, issue_comments, issue_transitions -> require issues
#   - issue_board, project_board, epics, sprints    -> require boards
WANT='["projects","issues","changelogs","issue_transitions","boards","epics","sprints","board_projects","board_issues"]'

jq --argjson want "$WANT" '
    .streams |= map(
      if (.tap_stream_id as $id | $want | index($id)) then
        .metadata |= map(if .breadcrumb == [] then .metadata.selected = true else . end)
      else . end)
  ' "$SRC" > "$BRONZE"

echo ""
echo "Created $BRONZE :"
echo "Streams not selected:"
# A discovered stream that isn't in WANT has no "selected" key at all (not
# selected==false), so match "no breadcrumb-[] entry with selected==true".
jq -r '.streams[]
       | select(any(.metadata[]; .breadcrumb==[] and .metadata.selected==true) | not)
       | "  * " + .tap_stream_id' "$BRONZE"

echo ""
echo "Streams selected for extraction:"
jq -r '.streams[]
       | select(any(.metadata[]; .breadcrumb==[] and .metadata.selected==true))
       | "  * " + .tap_stream_id' "$BRONZE"

# (No jq? Open jira_source_catalog.json and add "selected": true inside each
# desired stream's breadcrumb [] metadata object, saving as jira_bronze_catalog.json.)
