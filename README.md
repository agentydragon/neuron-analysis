# Cell analysis

Can an agent find the dark cells along the side of a *Xenopus laevis* embryo in a microscopy video and keep
each cell's identity across frames? This repository holds the sample video, a small set of hand-painted
identity marks, the task an agent is given, the tools that render and score its answer, and an
[Inspect](https://inspect.aisi.org.uk/) eval that runs the whole thing in a container.

What the dark cells are is not confirmed yet (see `TODO.md`), so the task and the code call them cells.

| Path | What it holds |
| --- | --- |
| `data/` | The original video and target reference (Git LFS), and `data/eval/`: the frames and hand-painted marks the eval scores against. |
| `cell_tracking/` | The package: whole-cell mask format, renderer, identity scoring, and frame and clip tools. |
| `tasks/identity/` | What the agent reads (prompt and target description) and a Codex launcher. |
| `evals/identity/` | The Inspect eval: sandbox, agents and scorer. |
| `debug/` | Notes on running long Codex jobs. |

## Setup

Install [uv](https://docs.astral.sh/uv/) and Git LFS, then run from the repository root:

```bash
git lfs install --local
git lfs pull
uv sync --locked
uv run pytest
```

`uv` installs the Python version in `.python-version` and the locked dependencies. The command-line tools are
`uv run cell-render`, `uv run cell-views`, `uv run cell-identity` and `uv run cell-eval-frames`.

The original video and target reference are tracked with Git LFS under `data/`; their hashes and source
metadata are in `data/README.md`. Rollout data is tracked too, under Git LFS:
each real run has its own folder `runs/<run-id>/` with the Inspect log, saved answers and transcripts. Throwaway output
goes in `runs/scratch/` and caches in `.cache/`, both git-ignored; see `AGENTS.md`.

## What the agent produces

One file, `annotations.json`: a whole-cell mask for each cell in each frame where it is visible, and nothing
else (no source, frame list, colors or review state).

```json
{
  "masks": [
    { "cell": "A", "frame": 0, "mask": [[10, 20, 27], [11, 20, 23]] },
    { "cell": "A", "frame": 1, "mask": [[12, 22, 29], [13, 22, 25]] },
    { "cell": "B", "frame": 0, "mask": [[30, 5, 9]] }
  ]
}
```

A mask is a list of horizontal runs `[y, x_start, x_end]` with an exclusive end: `[10, 20, 27]` is the pixels
(20, 10) through (26, 10). Runs are sorted by row then column and must not overlap or touch within a mask; a cell
that is not visible in a frame has no entry for it. The model is `CellMasks` in `cell_tracking/masks.py`. The JSON
Schema is derived from it when needed and is not committed: `uv run python -m cell_tracking.schema`, printed or
written with `--output FILE`.

## Rendering

The renderer reads the video itself for dimensions and timing and gives each cell a stable color from its id.
From the repository root, render one frame or the whole video:

```bash
uv run cell-render --source "$PWD/data/timelapse1.avi" --annotations runs/example/annotations.json \
  --frame 68 --output "$PWD/runs/renderer/frame_068.png"

uv run cell-render --source "$PWD/data/timelapse1.avi" --annotations runs/example/annotations.json \
  --output "$PWD/runs/renderer/annotated.mp4"
```

Repeat `--cell ID` to draw only some cells; `--no-labels` leaves pixel boundaries unobscured. Every output gets a
`.png.json` or `.mp4.json` report with the annotation and output hashes, the colors, and the original and output
timestamps. Videos use H.264 High profile, level 4.0, CRF 18, yuv420p and MP4 faststart for sharing with phones.
Frames repeat at 30 fps with a constant source-frame cadence and the original total duration rounded up by
less than 1/30 second. The report maps each output frame back to its source frame; the renderer decodes the
MP4 to check frame count and dimensions. Video dimensions must be even. For lossless pixel inspection use
PNG exports or `cell-views`; internal eval clips remain lossless FFV1 AVI with unchanged frame numbering.
Rendering is not evidence of correct cells or tracking; open the outputs.

## Plotting cell sizes

From the repository root, plot mask area against the original video's timestamps:

```bash
uv run --locked --script scripts/plot-cell-areas.py \
  --source data/timelapse1.avi --annotations runs/example/annotations.json \
  --output-prefix runs/scratch/cell-areas --title "Cell mask area over time"
```

The committed script and its adjacent lockfile pin the plotting environment separately
from the agent environment. Each fresh output prefix produces PNG and SVG charts,
a self-contained interactive HTML chart, a CSV of measurements, and a provenance
JSON with input, script, lockfile and output hashes. Colors are the same as the
renderer's cell-ID colors. Size is the count of annotated mask pixels; missing
entries produce gaps rather than zeros. Use the source video rather than the
rendered MP4 so repeated playback frames do not become extra measurements.

## Viewing every frame

`cell-views` exports every source frame as a lossless PNG at its original size, plus labelled,
paginated contact sheets for orientation:

```bash
uv run cell-views --source data/timelapse1.avi --output runs/scratch/raw-views
uv run cell-views --source data/timelapse1.avi --annotations runs/example/annotations.json \
  --output runs/scratch/mask-review
```

Each output directory must be new. It contains `frames/`, `sheets/` and `frames.json` recording every
frame's index, timestamp and hash, the source hash and, for overlays, the saved annotation hash and
stable cell colors. After editing annotations, use a new review directory. `--width`, `--columns` and
`--per-sheet` control contact sheets; individual frame PNGs always retain full resolution. Open each
overlay and use close crops to assess pixels: generating images or viewing a sheet is not visual validation.

## Identity eval

Hand-painted marks in `data/eval/` (see its README) say which spots in which frames are the same cell. Score an
annotation file with

```bash
uv run cell-identity check --annotations ANNOTATIONS --marks data/eval/identity_marks.json
```

The scores are `same_cell` and `different_cell` (soft, so partial coverage and split marks give fractions),
`marks_covered`, `mark_share` and `all_pass`, described in `evals/identity/README.md`. They cover the marked
cells only: nothing penalizes extra cells, and mask boundaries are not compared.

## Running an agent

- `tasks/identity/run.sh NAME` stages a clean workspace (prompt, target text, schema, video, reference image and
  renderer code, with no evaluation data) and launches Codex in it; see `tasks/identity/README.md`.
- `evals/identity/` runs the same task as an Inspect eval in a Docker sandbox, with native Codex or Claude Code
  using your subscription login, including Claude Code on the web;
  see `evals/identity/README.md`.

## Source

Imported from [`agentydragon/ducktape`, `x/neuron_tracking`](https://github.com/agentydragon/ducktape/tree/5ef11a907269bf2b532736c4e09b77188892b3c4/x/neuron_tracking).
