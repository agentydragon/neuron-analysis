# Haiku, high effort, clip 24-32 (rerun on the new video)

Task `evals/identity/task.py@identity_clips -T groups=24-32`, agent `claude_cli`, model `haiku`, effort `high`,
120 minutes, margin 2, code at commit `f91467a`. This reruns the clip that the batch in
`20261021T0006Z_identity_clips/` lost to a container restart. Unlike that batch, this run uses the full-resolution
`data/timelapse1.avi` (1376x1024) and the marks rescaled onto it. A single run, not conclusive.

| Clip | same_cell | different_cell | marks_covered | mark_share | all_pass | Cells annotated | Agent minutes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 24-32 | 0.20 | 0.13 | 0.50 | 0.43 | no | 127 | 17.2 |

3 of the 6 marks were hit, with 127 cell ids annotated. The log and saved answer were scanned for the session
login token before committing and contain none.
