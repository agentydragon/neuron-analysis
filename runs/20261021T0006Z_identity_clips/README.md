# Haiku, high effort, one run per clip (partial)

Task `evals/identity/task.py@identity_clips`, agent `claude_cli`, model `haiku`, effort `high`, 120 minutes,
margin 2, code at commit `e320059`. Clips are cut from the 1280x944 `data/IMG_6128.AVI` and scored against the
marks as they were before they were rescaled to `data/timelapse1.avi`, so these results are on the old video.

A container restart killed the batch before the 24-32 clip finished, so the Inspect log (status `started`) holds
three scored samples and 24-32 is missing. Each clip was run once; these are single runs and not conclusive.

| Clip | same_cell | different_cell | marks_covered | mark_share | all_pass | Cells annotated | Agent minutes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 66-72 | 0.99 | 0.99 | 1.00 | 0.99 | yes | 33 | 6.2 |
| 58-62 | 0.63 | 0.46 | 0.80 | 0.70 | no | 18 | 7.2 |
| 52-58 | 0.00 | 0.00 | 0.00 | 0.00 | no | 13 | 7.9 |

Files: the Inspect log, `outputs/` (the answer each agent saved, `<time>_<clip>.annotations.json`) and
`transcripts/` (the Claude Code stream-json transcripts). The log and saved answers were scanned for the session
login token before committing and contain none.
