#!/usr/bin/env bash
# Stage a clean workspace for one identity-annotation run and launch Codex in it.
# Usage: tasks/identity/run.sh NAME [--stage-only]
# The workspace holds only the prompt, format, schema, inputs and renderer code,
# so the agent's working directory contains no evaluation data.
set -euo pipefail

name="${1:?usage: run.sh NAME [--stage-only]}"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
run="${NEURON_RUNS:-$repo/runs}/identity_$name"
workspace="$run/workspace"
[ ! -e "$run" ] || { echo "$run already exists; use a fresh NAME" >&2; exit 1; }

mkdir -p "$workspace/output"
cp "$repo/tasks/identity/annotate.md" "$repo/tasks/identity/format.md" "$repo/annotations.schema.json" "$workspace/"
cp "$repo/data/IMG_6128.AVI" "$repo/data/photo_2026-10-19_14-30-28.jpg" "$workspace/"
cp "$repo/pyproject.toml" "$repo/uv.lock" "$repo/.python-version" "$workspace/"
mkdir "$workspace/neuron_tracking"
# Only the annotation model and renderer are copied; evaluation, clip and checking code stays out.
cp "$repo/neuron_tracking/annotations.py" "$repo/neuron_tracking/render.py" "$workspace/neuron_tracking/"
sed -i '/^neuron-check\|^neuron-identity\|^neuron-eval-frames/d' "$workspace/pyproject.toml"
printf '# Renderer workspace\n' > "$workspace/README.md"

[ "${2:-}" != "--stage-only" ] || { echo "$workspace"; exit 0; }

cd "$workspace"
codex exec --model gpt-6-luna -c 'model_reasoning_effort="xhigh"' \
  --approve-for-me --json -C "$workspace" \
  --output-last-message "$run/handoff.md" \
  "Read annotate.md and format.md. Process all frames from IMG_6128.AVI. The red outline in photo_2026-10-19_14-30-28.jpg marks the region whose neurons to annotate. Save the annotations to output/annotations.json." \
  > "$run/codex_events.jsonl"
