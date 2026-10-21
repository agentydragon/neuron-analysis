# GPT-6.1 Sol medium: prompt v2 rendered runs

These use the answers from the prompt v2 batch, before the later cell-ID wording changes.
H.264 MP4, 30 fps, original dimensions and duration, stable cell colors and labels.

- `24-32.mp4`: 13 source frames, 6.5 seconds; answer `runs/20261021T044420Z_gpt-6.1-sol_medium_prompt-v2_7fe1a4_24-32/outputs/20261020T215648_24-32.annotations.json`.
- `52-58.mp4`: 11 source frames, 5.5 seconds; answer `runs/20261021T044420Z_gpt-6.1-sol_medium_prompt-v2_7fe1a4_52-58/outputs/20261020T215239_52-58.annotations.json`.
- `58-62.mp4`: 9 source frames, 4.5 seconds; answer `runs/20261021T044420Z_gpt-6.1-sol_medium_prompt-v2_7fe1a4_58-62/outputs/20261020T215333_58-62.annotations.json`.
- `66-72.mp4`: 9 source frames, 4.5 seconds; answer `runs/20261021T044420Z_gpt-6.1-sol_medium_prompt-v2_7fe1a4_66-72/outputs/20261020T214912_66-72.annotations.json`.

Each `.mp4.json` records input/output hashes, colors, timing and source-frame mapping.
Original inputs and saved answers are preserved.

All five runs are complete.

`full.mp4` renders the completed full-video answer (73 source frames, 36.5 seconds).
`full-cell-areas.png`, `.svg`, `.html` and `.csv` show its cell mask areas; the
provenance JSON records input, script, dependency-lock and output hashes.

Reproduce the plot from the repository root with a fresh output prefix:

```bash
uv run --locked --script scripts/plot-cell-areas.py \
  --source data/timelapse1.avi \
  --annotations runs/20261021T044420Z_gpt-6.1-sol_medium_prompt-v2_7fe1a4_full/outputs/20261020T221434_full.annotations.json \
  --output-prefix runs/scratch/prompt-v2-cell-areas \
  --title "Cell mask area over time — full video (prompt v2)"
```
