#!/usr/bin/env bash
# Stage a clean workspace for one identity-annotation run and launch Codex in it.
# Usage: tasks/identity/run.sh NAME [--stage-only]
# The workspace (git-ignored, under .cache/workspaces/) holds only the prompt, target text, schema, inputs and
# renderer code, so the agent's working directory contains no evaluation data. The tracked record of the
# run (Codex events, hand-off message and the saved answer) goes to runs/identity_NAME/.
set -euo pipefail

name="${1:?usage: run.sh NAME [--stage-only]}"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
run="${RUNS_DIR:-$repo/runs}/identity_$name"
workspace="${CACHE_DIR:-$repo/.cache}/workspaces/identity_$name"
[ ! -e "$run" ] && [ ! -e "$workspace" ] || { echo "$run or $workspace already exists; use a fresh NAME" >&2; exit 1; }

mkdir -p "$workspace/output" "$run"
cp "$repo/tasks/identity/annotate.md" "$repo/tasks/identity/target.md" "$workspace/"
uv run --project "$repo" --no-sync python -m cell_tracking.schema --output "$workspace/annotations.schema.json"
cp "$repo/data/timelapse1.avi" "$workspace/"
cp "$repo/data/photo_2026-10-19_14-30-28.jpg" "$workspace/target.jpg"
cp "$repo/pyproject.toml" "$repo/uv.lock" "$repo/.python-version" "$workspace/"
mkdir "$workspace/cell_tracking"
# Only the annotation model and renderer are copied; evaluation, clip and checking code stays out.
cp "$repo/cell_tracking/core.py" "$repo/cell_tracking/hashing.py" "$repo/cell_tracking/masks.py" "$repo/cell_tracking/render.py" "$workspace/cell_tracking/"
sed -i '/^cell-identity\|^cell-eval-frames/d' "$workspace/pyproject.toml"
printf '# Renderer workspace\n' > "$workspace/README.md"

[ "${2:-}" != "--stage-only" ] || { echo "$workspace"; exit 0; }

cd "$workspace"
codex exec --model gpt-6-luna -c 'model_reasoning_effort="xhigh"' \
  --approve-for-me --json -C "$workspace" \
  --output-last-message "$run/handoff.md" \
  "Read annotate.md and target.md. Process all frames from timelapse1.avi. The red outline in target.jpg marks the region whose dark cells to annotate. Save the annotations to output/annotations.json." \
  > "$run/codex_events.jsonl"
cp "$workspace/output/annotations.json" "$run/annotations.json" 2>/dev/null || echo "no output/annotations.json was written" >&2
