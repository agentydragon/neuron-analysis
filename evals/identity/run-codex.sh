#!/usr/bin/env bash
# Run the named Inspect task with native Codex and your file-backed ChatGPT login.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.cache/uv}"
exec uv run --group evals python -m evals.identity.codex_run "$@"
