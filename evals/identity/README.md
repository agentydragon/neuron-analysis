# Identity eval (Inspect)

An [Inspect](https://inspect.aisi.org.uk/) task that gives an agent the clip and the target image in a
Docker sandbox, asks for `output/annotations.json`, and scores it against the painted identity marks in
`data/eval/` (see `data/eval/README.md` for what the score means). The scorer validates the file with the
`CellMasks` pydantic model (the same model the agent's schema is derived from) and the video's dimensions and
frame count; an invalid or missing file scores 0 with the reason recorded. The marks and scoring code stay on the host; the sandbox never contains them.

```bash
uv run --group evals inspect eval evals/identity/task.py --model mockllm/model -T agent=stub_oracle
```

## Agents (`-T agent=...`)

- `claude_cli` (default): runs the Claude Code CLI in the sandbox with a **subscription** token
  (`CLAUDE_CODE_OAUTH_TOKEN`), so nothing is billed to the metered API. Inspect makes no model calls, so
  pass `--model mockllm/model`. Options: `-T model=haiku|sonnet|...`, `-T effort=low|medium|high|xhigh|max`,
  `-T minutes=120` (the agent's wall-clock limit, 2 hours by default for both tasks; the sample limit adds
  5 minutes for setup and scoring). The raw `stream-json` transcript goes to `runs/transcripts/`.
- `claude`: Inspect's own Claude Code agent; model calls go through Inspect and need an Anthropic API key.
- `stub_oracle`, `stub_empty`, `stub_invalid`: write a fixed file with no model, to test the pipeline.
  The oracle reproduces the marks and must score 1.0 on every metric.

`identity_clips` is a smaller version: one lossless clip per marked group (its frames plus `-T margin=2`
frames on each side, cut by `cell_tracking/clips.py` and cached in `runs/clips/`), run as parallel samples
that are each scored against only that group's marks, remapped to the clip's frame numbers. Choose groups
with `-T groups=24-32,66-72`; the time limit is the same 2 hours as for the full video. The clips keep the source's pixels
exactly but not its timestamps (constant 2 fps), and the agent is told the clip is `clip.avi`.

Scores are `valid`, `same_cell`, `different_cell`, `marks_covered`, `mark_share` (all fractions) and `all_pass`.
`mark_share` is the mean, over all marks, of the fraction of a mark's pixels under its best-matching predicted cell
(0 for a mark no cell touches), so it also reflects a cell covering only part of a mark;
failing pairs are in the sample's score metadata.

## Sandbox

A plain `python:3.12-slim` image pinned by digest (`compose.yaml`), with no Dockerfile. For the Claude
agents Inspect uploads the prompt, target definition, schema, video, reference image (as `target.jpg`) and the renderer source
(`cell_tracking/annotations.py`, `hashing.py`, `masks.py`, `render.py`) into `/workspace`, then runs a setup script as root that
creates an `agent` user, installs the locked environment (`uv sync --locked --no-dev --group agent`, which
adds numpy, scipy, scikit-image, opencv, matplotlib and imageio) and the pinned Claude Code CLI. Setup takes
about 40 seconds and needs network access. Only the renderer is exposed; check, identity and eval code is
never uploaded. The agent runs as `agent` with permissions bypassed inside the container.

## Running on your own machine

Needs Docker and a Claude subscription:

```bash
claude setup-token                      # once; prints a long-lived token
export CLAUDE_CODE_OAUTH_TOKEN=...      # do not commit it or paste it into logs
uv run --group evals inspect eval evals/identity/task.py --model mockllm/model \
  -T agent=claude_cli -T model=haiku -T effort=xhigh
```

## Running inside Claude Code on the web

`evals/identity/run-claude-code-web.sh [-T ...]` does the same from a Claude Code on the web session, using
that session's own login. Three environment-specific steps, all in the script or its compose file:

1. The container has a Docker engine but no running daemon, so the script starts `dockerd` if needed.
2. The session's login is an OAuth token in the file named by `CLAUDE_SESSION_INGRESS_TOKEN_FILE`
   (`claude auth status` reports `authMethod: oauth_token`; there is no API key). The script exports its
   contents as `CLAUDE_CODE_OAUTH_TOKEN` for the eval process only. A smoke test confirmed that the Claude
   Code CLI installed in a container in this environment, given that variable, answers as the same
   subscription session.
3. The network re-signs TLS with a private CA, so `compose.claude-code-web.yaml` mounts
   `/root/.ccr/ca-bundle.crt` into the sandbox and points pip, npm and Python at it.

What this exposes: the token is in the environment of the processes the agent runs, so the agent can read
it. Treat it as the session's login: it is scoped to that session, never written to a file or to Git by
this code, and the saved transcripts do not contain it unless the agent echoes it, so keep `runs/` out of
Git and do not share it. Runs use the session's subscription allowance, so long runs count against it.
