# Identity-mark eval frames

Evaluator-only inputs; keep them out of any annotation agent's workspace.
`frames/` holds lossless PNGs of selected source frames (frame index = decode order,
as in `neuron-render`), `frames.json` pins the source SHA-256 and each PNG's hash, and
`sheets/` holds labelled contact sheets of all 73 frames for choosing more.
Regenerate with `uv run neuron-eval-frames --source data/IMG_6128.AVI --output data/eval --frame N ... --sheets`.

## Marking

Copy each `frames/frame_NNN.png` to `marked/frame_NNN.png` and paint solid marks on cells; never edit
`frames/`. A mark means "some part of this cell" (body or branch). One colour is one cell across every frame.
Use a hard pencil with no antialiasing and no transparency; keep marks a few pixels wide and inside the cell.
Outlines are fine: enclosed holes count as part of the mark.
Use any solid colours that do not occur in the grayscale source; each exact RGB value is one cell, and no
palette is fixed in advance. MS Paint's default swatches work, for example red `237,28,36`,
orange `255,127,39`, green `34,177,76`, blue `0,162,232` and purple `163,73,164`.
Reuse a colour only for the same cell in other frames.
Pixels that differ from the original frame define the marks, so do not touch anything else, and save as PNG.
