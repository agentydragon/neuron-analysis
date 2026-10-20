# Identity-only annotation task

A reduced version of the full annotation task: given the video and the reference
image showing the target region, annotate each neuron with a persistent identity
across frames. Body and branches are not separated; each neuron's whole visible
extent is one mask in `body`, with `branches` left empty. The format, schema,
renderer and scorer are the same as for the full task.

Files here are the annotation agent's inputs: `annotate.md` (prompt) and
`format.md` (how to save masks) and `target.md` (the sample's target region, adapted from
`sample_task.md` without its body/branch separation), plus the reference image.

## Run

```bash
tasks/identity/run.sh NAME
```

This stages `runs/identity_NAME/workspace/` containing only the prompt, format,
schema, video, reference image and renderer code, then starts Codex there with the
same model settings as the first runs. The agent writes under `workspace/output/`;
the hand-off message and event log go next to the workspace. Use a fresh `NAME`
each time. `--stage-only` stages without launching. Evaluation data in `data/eval/`
is not copied, so the workspace does not contain it; the prompt additionally tells
the agent not to look for evaluation answers.

## Score

```bash
uv run neuron-identity check \
  --annotations runs/identity_NAME/workspace/output/annotations.json \
  --marks data/eval/identity_marks.json
```

Passing means the marked cells keep consistent, distinct identities. It says nothing
about extra neurons, missed unmarked cells or mask boundaries; see `data/eval/README.md`.

## Terminology

The agent-facing files (`annotate.md`, `target.md`, the launch prompt) say "cells" and "dark cells",
and `target.md` states that cell type is not asserted, because it is not yet confirmed that these are
neurons. The schema's field names (`neurons`, `neuron_id`) and the `neuron-*` tool names are unchanged;
`format.md` says so. See the terminology item in `TODO.md`.
