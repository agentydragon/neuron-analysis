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
Use only these colours, none of which occur in the grayscale source:

| Cell | Colour  | RGB             |
| ---- | ------- | --------------- |
| A    | red     | `255, 0, 0`     |
| B    | green   | `0, 255, 0`     |
| C    | blue    | `0, 0, 255`     |
| D    | yellow  | `255, 255, 0`   |
| E    | magenta | `255, 0, 255`   |
| F    | cyan    | `0, 255, 255`   |
| G    | orange  | `255, 128, 0`   |
| H    | purple  | `128, 0, 255`   |
| I    | pink    | `255, 128, 192` |
| J    | lime    | `128, 255, 0`   |
