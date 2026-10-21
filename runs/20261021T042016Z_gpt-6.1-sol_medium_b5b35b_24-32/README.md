# GPT-6.1 Sol identity eval: 24-32

- Model: `gpt-6.1-sol`
- Reasoning effort: `medium`
- Attempts: one
- Agent: native Codex CLI 0.162.1, using subscription authentication
- Task: `evals/identity/task.py@identity_clips`
- Agent wall-clock limit: 120 minutes (plus 5 minutes for setup and scoring)
- Input: 13 frames, staged as `clip.avi`
- Source frames 22-34; output frame 0 maps to source frame 22. Margin: 2 frames, clipped at video boundaries.
- Source video SHA-256: `36d2a3aa7065af6a14f87e397895e6871e412bba7851f4a86e7f6203735d10ed`
- Staged video SHA-256: `c74ab4f8597a58a8b11d4d0f1666421620fec37ddd960bbfcc5513a40a926a33`
- Scoring marks SHA-256: `9aa0861ced47a95c669b14d74c2cc8777759b1885ebbc030b073e5bda8862c2e`
- Runner implementation: `d1e882c902b2845ee866777f44d53ffae94d544c`
- Host user service: `neuron-eval-sol-medium-24-32-b5b35b.service`

The Inspect log, saved answer and transcripts are collected here by `run-codex.sh`.
The launcher scans run artifacts for its initial and final login tokens on exit.
