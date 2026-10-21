# Identity-mark eval frames

Evaluator-only inputs; keep them out of any annotation agent's workspace.
`frames/` holds lossless PNGs of the marked source frames (frame index = decode order,
as in `cell-render`), `frames.json` pins the source SHA-256 and each PNG's hash.
Regenerate with `uv run cell-eval-frames --source data/IMG_6128.AVI --output data/eval --frame N ...`; add `--sheets` for labelled contact sheets of all frames (not committed).

## Marking

Copy each `frames/frame_NNN.png` to `marked/<group>/frame_NNN.png` and paint solid marks on cells; never edit
`frames/`. A mark means "some part of this cell" (body or branch). One colour is one cell across every frame.
Use a hard pencil with no antialiasing and no transparency; keep marks a few pixels wide and inside the cell.
Outlines are fine: enclosed holes count as part of the mark.
Use any solid colours that do not occur in the grayscale source; each exact RGB value is one cell, and no
palette is fixed in advance. MS Paint's default swatches work, for example red `237,28,36`,
orange `255,127,39`, green `34,177,76`, blue `0,162,232` and purple `163,73,164`.
Reuse a colour only for the same cell in other frames.
Pixels that differ from the original frame define the marks, so do not touch anything else, and save as PNG.

## Layout and scoring

```
frames/                 originals, never edited
marked/<group>/frame_NNN.png   one folder per set of frames whose colours correspond
frames.json             source and frame hashes
identity_marks.json     derived labels (committed; regenerate, do not edit)
```

A group is a set of frames marked together. A colour means the same cell only within its group, so
colours may be reused for different cells in other groups, and one frame may appear in several groups.
`marked/` frames are stored as separate copies per group. Groups so far: `66-72`, `58-62`, `52-58`, `24-32`.

```bash
uv run cell-identity derive --frames data/eval/frames --marked data/eval/marked \
  --output data/eval/identity_marks.json
uv run cell-identity check --annotations runs/<run>/annotations.json \
  --marks data/eval/identity_marks.json
```

`derive` takes the pixels that differ from the original as marks, one exact colour per cell. It fills
the inside of outlined marks and rejects a colour with two disconnected blobs in a frame, a mark that
encloses another, or a frame that is not the one in `frames.json`.

`check` matches each mark to the predicted cells under it (ties keep every tied id). Every pair of marks in a
group is then an assertion: the same colour in different frames should be the same predicted cell, and different
colours should not share one. A mark that no cell touches fails its pairs. The JSON report (an `Evaluation`)
gives pass counts and soft scores per kind, `marks_covered`, `mark_share` and each failing pair; the exit status
is 1 unless everything passes. Unmarked cells are not scored, so extra cells are not penalised.
