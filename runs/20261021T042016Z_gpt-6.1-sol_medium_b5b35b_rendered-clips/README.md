# GPT-6.1 Sol medium: rendered baseline clips

- `24-32.avi`: saved answer from `20261021T042016Z_gpt-6.1-sol_medium_b5b35b_24-32`, rendered over its original lossless clip with stable cell colors and labels.
- `52-58.avi`: saved answer from `20261021T042016Z_gpt-6.1-sol_medium_b5b35b_52-58`, rendered over its original lossless clip with stable cell colors and labels.
- `58-62.avi`: saved answer from `20261021T042016Z_gpt-6.1-sol_medium_b5b35b_58-62`, rendered over its original lossless clip with stable cell colors and labels.
- `66-72.avi`: saved answer from `20261021T042016Z_gpt-6.1-sol_medium_b5b35b_66-72`, rendered over its original lossless clip with stable cell colors and labels.

Each AVI has a JSON report with input/output hashes, cell colors, frame coverage and timestamps.

Phone-compatible H.264 MP4 versions are `24-32.mp4`, `52-58.mp4`, `58-62.mp4` and `66-72.mp4`.

`full.mp4` renders all 73 frames of `data/timelapse1.avi` using the saved answer from
`20261021T042016Z_gpt-6.1-sol_medium_b5b35b_full/outputs/20261020T214601_full.annotations.json`.
It is 36.5 seconds at 30 fps (15 repeated frames per source frame), 1376 x 1024.
`full.mp4.json` records hashes, colors, timing and the output-to-source frame mapping.
