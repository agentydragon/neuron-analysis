# Prompt v2: GPT-6.1 Sol medium, 66-72

- Prompt version: v2 (complete annotation/review, abrupt-pose guidance and ready-made view commands)
- Model: `gpt-6.1-sol`
- Reasoning effort: `medium`
- Attempts: one
- Agent: native Codex CLI 0.162.1 with subscription authentication
- Task: `evals/identity/task.py@identity_clips`
- Agent wall-clock limit: 120 minutes, plus 5 minutes for setup and scoring
- Input: 9 frames
- Staged video SHA-256: `a9fce4d4215ea8482dfbf441590a88925ee65b8869be76ddd97b86c154790f39`
- Implementation commit: `e2c2d64c1a5bb2bd6c670f63d6003bd50608f1b8`
- Comparison baseline: `../20261021T042016Z_gpt-6.1-sol_medium_b5b35b_66-72/`
- Host user service: `neuron-eval-sol-medium-v2-66-72-7fe1a4.service`

The staged video hash and model/effort settings match the baseline. Original videos and marks are unchanged.
`inputs/` snapshots the task instructions, target definition, launch message, schema and source filename.
The Inspect log, saved annotations and native transcripts are collected here by `run-codex.sh`.
The launcher scans artifacts for its initial and final login tokens on exit.
