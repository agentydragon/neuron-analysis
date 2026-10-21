# Identity annotation task

Given the video and the reference image showing the target region, annotate each cell with a
persistent identity across frames. The output is one whole-cell mask per cell per frame in which it
is visible, and nothing else (no source, frame list, colors, revision or review state):

```json
{ "masks": [ { "cell": "A", "frame": 12, "mask": [[10, 20, 27], [11, 20, 23]] } ] }
```

The renderer reads the video itself for dimensions and timing and assigns colors; the scorer reads the format
directly (`cell_tracking.masks`, `cell_tracking.identity`).

Files here are the annotation agent's inputs: `annotate.md` (prompt), `target.md` (the sample's target
region) and `annotations.schema.json`
(derived from the `CellMasks` pydantic model when the workspace is built, never committed, in place of a
separate format document). The agent
also gets the video and the reference image, uploaded as `target.jpg`. `source.txt` names the staged
video so the ready-made commands in `annotate.md` work for either a full video or a clip. `cell-views`
exports every raw or annotated frame and its contact sheets; only annotations are submitted for scoring.

## Run

```bash
tasks/identity/run.sh NAME
```

This stages `.cache/workspaces/identity_NAME/` (git-ignored) containing only the prompt, target text,
schema, video, reference image and renderer code, then starts Codex there with the
same model settings as the first runs. The agent writes under `output/`; the tracked record of
the run, in `runs/identity_NAME/`, holds the event log, the hand-off message and a copy of the answer. Use a fresh `NAME`
each time. `--stage-only` stages without launching. Evaluation data in `data/eval/`
is not copied, so the workspace does not contain it; the prompt additionally tells
the agent not to look for evaluation answers.

## Score

```bash
uv run cell-identity check \
  --annotations runs/identity_NAME/annotations.json \
  --marks data/eval/identity_marks.json
```

Passing means the marked cells keep consistent, distinct identities. It says nothing
about extra cells, missed unmarked cells or mask boundaries; see `data/eval/README.md`.

## Terminology

The agent-facing files (`annotate.md`, `target.md`, the launch prompt) say "cells" and "dark cells",
and `target.md` states that cell type is not asserted, because it is not yet confirmed that these are
neurons. Nothing the agent can read uses the word: the package is `cell_tracking`, the commands are `cell-*`, and the
mask fields are `cell`, `frame` and `mask`. See the terminology item in `TODO.md`.
