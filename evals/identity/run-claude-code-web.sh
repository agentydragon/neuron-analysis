#!/usr/bin/env bash
# Run the identity eval with the Claude Code agent from inside a Claude Code on the web session,
# using that session's own subscription login. Extra arguments go to `inspect eval`, e.g.
#   evals/identity/run-claude-code-web.sh -T model=haiku -T effort=xhigh
# Set TASK to pick another task, e.g. TASK=evals/identity/task.py@identity_clips.
# See evals/identity/README.md for what this does and what it exposes to the agent.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# The web container has a Docker engine but no running daemon.
if ! docker info >/dev/null 2>&1; then
  nohup dockerd >/tmp/dockerd.log 2>&1 &
  for _ in $(seq 15); do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || { echo "dockerd did not start; see /tmp/dockerd.log" >&2; exit 1; }
fi

# The session's Claude Code login is an OAuth token in a file. Handing it to the in-container CLI as
# CLAUDE_CODE_OAUTH_TOKEN makes that CLI use the same subscription route, not the metered API.
: "${CLAUDE_SESSION_INGRESS_TOKEN_FILE:?not a Claude Code on the web session; use a 'claude setup-token' token instead}"
CLAUDE_CODE_OAUTH_TOKEN="$(cat "$CLAUDE_SESSION_INGRESS_TOKEN_FILE")"
export CLAUDE_CODE_OAUTH_TOKEN

exec uv run --group evals inspect eval "${TASK:-evals/identity/task.py}" --model mockllm/model \
  -T agent=claude_cli -T compose=evals/identity/compose.claude-code-web.yaml "$@"
