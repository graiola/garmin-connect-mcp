#!/usr/bin/env bash
# Configure a private tunnel; no API keys are embedded in arguments or files here.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
root="$(pwd -P)"
command -v tunnel-client >/dev/null || { echo 'Install the official OpenAI tunnel-client first; see docs/CHATGPT.md.' >&2; exit 1; }
[[ -x "$root/.venv/bin/garmin-connect-mcp" ]] || { echo 'Install the project into .venv first.' >&2; exit 1; }
[[ "${1:-}" =~ ^tunnel_[A-Za-z0-9_-]+$ ]] || { echo 'Usage: ./scripts/tunnel_stdio.sh tunnel_ID' >&2; exit 1; }
[[ "$root" != *[[:space:]]* ]] || { echo 'For the tunnel command, use a project path without spaces.' >&2; exit 1; }
if [[ -z "${CONTROL_PLANE_API_KEY:-}" ]]; then
  read -r -s -p 'OpenAI tunnel runtime API key (NOT Garmin, hidden): ' CONTROL_PLANE_API_KEY
  printf '\n'
  export CONTROL_PLANE_API_KEY
fi
profile="garmin-personal"
tunnel-client init --sample sample_mcp_stdio_local --profile "$profile" --tunnel-id "$1" \
  --mcp-command "$root/.venv/bin/garmin-connect-mcp stdio"
tunnel-client doctor --profile "$profile" --explain
exec tunnel-client run --profile "$profile"
