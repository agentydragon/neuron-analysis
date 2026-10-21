# Prompt v2: GPT-6.1 Sol medium, 52-58

- Prompt version: v2 (complete annotation/review, abrupt-pose guidance and ready-made view commands)
- Model: `gpt-6.1-sol`
- Reasoning effort: `medium`
- Attempts: one
- Agent: native Codex CLI 0.162.1 with subscription authentication
- Task: `evals/identity/task.py@identity_clips`
- Agent wall-clock limit: 120 minutes, plus 5 minutes for setup and scoring
- Input: 11 frames
- Staged video SHA-256: `db6c2785fe06087e146fc2a4dc8625530608ffbada20edec8f773bd21924921a`
- Implementation commit: `e2c2d64c1a5bb2bd6c670f63d6003bd50608f1b8`
- Comparison baseline: `../20261021T042016Z_gpt-6.1-sol_medium_b5b35b_52-58/`
- Host user service: `neuron-eval-sol-medium-v2-52-58-7fe1a4.service`

The staged video hash and model/effort settings match the baseline. Original videos and marks are unchanged.
`inputs/` snapshots the task instructions, target definition, launch message, schema and source filename.
The Inspect log, saved annotations and native transcripts are collected here by `run-codex.sh`.
The launcher scans artifacts for its initial and final login tokens on exit.
