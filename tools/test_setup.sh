#!/bin/bash
#
# tools/test_setup.sh - one-time setup for CLI testing of tap-jira.
# Creates the venv at the repo root, installs the tap, and (if
# tools/test_config.json exists) runs a cheap auth smoke test.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"   # tools/
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$REPO_ROOT"
python3 -m venv venv/tap-jira
. venv/tap-jira/bin/activate
pip install -e .            # or: make venv

# Config lives in tools/test_config.json (Basic Auth: username=email,
# password=Jira API token, base_url=https://your-org.atlassian.net).
# See tools/test_config.json.template.
if [ ! -f "$SCRIPT_DIR/test_config.json" ]; then
  echo ""
  echo "Next: create tools/test_config.json with your token, then re-run this script."
  echo "  cp tools/test_config.json.template tools/test_config.json   # then edit it"
  exit 0
fi

# Cheap credential smoke test: discovery itself authenticates (main() builds the
# client and hits /myself + /serverInfo).
tap-jira --config "$SCRIPT_DIR/test_config.json" --discover >/dev/null && echo "AUTH OK"
