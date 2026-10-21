# Identity eval (Inspect)

An [Inspect](https://inspect.aisi.org.uk/) task that gives an agent the clip and the target image in a
Docker sandbox, asks for `output/annotations.json`, and scores it against the painted identity marks in
`data/eval/` (see `data/eval/README.md` for what the score means). The scorer validates the file with the
`CellMasks` pydantic model (the same model the agent's schema is derived from) and the video's dimensions and
frame count; an invalid or missing file scores 0 with the reason recorded. The marks and scoring code stay on the host; the sandbox never contains them.

Each launch through `run-claude-code-web.sh` or `run-codex.sh` writes a fresh folder under `runs/`, holding the Inspect log
(`*.eval`), `outputs/` (the saved `annotations.json` per sample) and `transcripts/`; it is tracked with Git LFS. Runs
that don't go through the launcher, such as stubs, write their outputs to the git-ignored `runs/scratch/`.

```bash
uv run --group evals inspect eval evals/identity/task.py@identity --model mockllm/model -T agent=stub_oracle
```

Always name the task (`@identity` or `@identity_clips`): a bare `task.py` runs every task in the file.

## Agents (`-T agent=...`)

- `codex_cli`: runs the pinned native Codex CLI with your file-backed ChatGPT login. Inspect makes no
  model calls; pass `--model mockllm/model`. Options: `-T model=gpt-6-luna` (default), `-T effort=low|medium|high|xhigh`
  (supported values depend on the model), and `-T minutes=120`. Use `run-codex.sh` below to supply the auth
  mount and collect and scan the run. Both `identity` and `identity_clips` support it.
- `claude_cli` (default): runs the Claude Code CLI in the sandbox with a **subscription** token
  (`CLAUDE_CODE_OAUTH_TOKEN`), so nothing is billed to the metered API. Inspect makes no model calls, so
  pass `--model mockllm/model`. Options: `-T model=haiku|sonnet|...`, `-T effort=low|medium|high|xhigh|max`,
  `-T minutes=120` (the agent's wall-clock limit, 2 hours by default for both tasks; the sample limit adds
  5 minutes for setup and scoring). The raw `stream-json` transcript goes to the run folder's `transcripts/`.
- `claude`: Inspect's own Claude Code agent; model calls go through Inspect and need an Anthropic API key.
- `stub_oracle`, `stub_empty`, `stub_invalid`: write a fixed file with no model, to test the pipeline.
  The oracle reproduces the marks and must score 1.0 on every metric.

`identity_clips` is a smaller version: one lossless clip per marked group (its frames plus `-T margin=2`
frames on each side, cut by `cell_tracking/clips.py` and cached in `.cache/clips/`), run as parallel samples
that are each scored against only that group's marks, remapped to the clip's frame numbers. Choose groups
with `-T groups=24-32,66-72`; the time limit is the same 2 hours as for the full video. The clips keep the source's pixels
exactly but not its timestamps (constant 2 fps), and the agent is told the clip is `clip.avi`.

Scores are `valid`, `same_cell`, `different_cell`, `marks_covered`, `mark_share` (all fractions) and `all_pass`.
`mark_share` is the mean, over all marks, of the fraction of a mark's pixels under its best-matching predicted cell
(0 for a mark no cell touches). `same_cell` and `different_cell` are soft: for a pair of marks, pick a random pixel
from each; a same-cell pair scores the chance both pixels are under the same predicted cell, a different-cell pair the
chance they are under two different cells (a pixel under several cells is split evenly, unmatched pixels count for
neither). With fully owned marks this is exactly pass/fail; split or partly covered marks give fractions. The
`passed`/`total` pair counts stay in the score metadata, and `all_pass` still uses them;
failing pairs are in the sample's score metadata.

## Sandbox

A plain `python:3.12-slim` image pinned by digest (`compose.yaml`), with no Dockerfile. For either native
agent Inspect uploads the prompt, target definition, schema, video, reference image (as `target.jpg`),
`source.txt` with the staged video filename, and the rendering/frame-view source
(`cell_tracking/core.py`, `hashing.py`, `masks.py`, `render.py`, `views.py`) into `/workspace`, then runs a setup script as root that
creates an `agent` user, installs the locked environment (`uv sync --locked --no-dev --group agent`, which
adds numpy, scipy, scikit-image, opencv, matplotlib and imageio) and the selected, pinned CLI (Claude Code 2.1.305 or Codex 0.162.1). Setup takes
about 40 seconds and needs network access. The renderer and `cell-views` frame/contact-sheet tool are exposed; check, identity and eval code is
never uploaded. The agent runs as `agent` with permissions bypassed inside the container. Codex's agent uid matches the
host user so it can access a private auth file; when the launcher runs as root, Codex runs as root in
its container. Containers have no host workspace mount and evaluation data stays on the host.

## Running on your own machine

Needs Docker and a Claude subscription:

```bash
claude setup-token                      # once; prints a long-lived token
export CLAUDE_CODE_OAUTH_TOKEN=...      # do not commit it or paste it into logs
uv run --group evals inspect eval evals/identity/task.py@identity --model mockllm/model \
  -T agent=claude_cli -T model=haiku -T effort=xhigh
```

## Running Codex with your existing login

Needs a local Docker daemon and a file-backed Codex ChatGPT login:

```bash
# Only needed if you have not signed in, or your login is stored in an OS keyring:
codex login -c 'cli_auth_credentials_store="file"'

# Full video:
evals/identity/run-codex.sh -T model=gpt-6-luna -T effort=low

# One marked group, with a short wall-clock limit:
TASK=evals/identity/task.py@identity_clips \
  evals/identity/run-codex.sh -T groups=24-32 -T minutes=5 -T effort=low
```

The launcher reads `${CODEX_HOME:-$HOME/.codex}/auth.json`; set `CODEX_AUTH_FILE` to select another file.
It rejects API-key auth so this route cannot silently switch to metered API billing. An OS keyring alone
is not available inside the container. `TASK` must name a task (`task.py@identity` or `task.py@identity_clips`).
Set `RUN_DIR` to choose a **new, nonexistent** run directory; the default includes UTC time, agent, task and a
random suffix. Existing run folders are never overwritten. `uv sync --locked --group evals` installs the
optional eval dependencies; the launcher also requests that group automatically. Launcher caches and
Inspect trace files default to `.cache/` (existing `UV_CACHE_DIR` and XDG overrides are respected).

Only `auth.json` is bind-mounted, read/write at `/run/codex-auth.json`. Each sample gets a private
`/home/agent/.codex` containing a symlink to it. Native Codex can persist refreshed tokens back to your
original login file, while personal configuration, skills and conversation history are not mounted.
The Compose file explicitly opts into Inspect's writable-host-mount setting for this auth bind.
The file stays mode 0600 when your existing login has that mode. This requires a local Docker daemon that
can access that host path and supports the matching uid. Rootless/user-remapped daemons may need uid mapping.

**The agent can read and modify the mounted login.** Use this with trusted tasks. Parallel samples share it;
there is deliberately no token-refresh locking or serialization. For an independent eval login, sign in with
a separate `CODEX_HOME` and point `CODEX_AUTH_FILE` there. See OpenAI's
[authentication documentation](https://learn.chatgpt.com/docs/auth) for file-backed login and
[account-auth lifecycle guidance](https://learn.chatgpt.com/docs/auth/ci-cd-auth) for token refresh behavior.

For each sample, `transcripts/codex_<unique-id>/` holds `events.jsonl`, `stderr.txt`, `final.md` and
`status.json` (sample id, model, effort, CLI version, duration, exit code and timeout status), plus the native
`session_*.jsonl` transcripts, which include tool events omitted from the CLI stream. Partial
transcripts are collected after timeouts and execution errors too. The scorer saves and evaluates the
agent's `output/annotations.json` using the same rules as Claude; a failed CLI run may leave a partial answer,
so check `status.json` as well as the scores.

The launcher scans raw artifacts and compressed Inspect log members for the initial and final auth tokens
after Inspect exits, including on failure. A match makes the launcher fail and identifies affected files
without printing tokens; do not commit or share those artifacts. This scan does not cover intermediate
rotated tokens or encoded/transformed secrets, so inspect suspicious agent output before sharing it.
For an additional scan later, with the same auth file selected:

```bash
uv run --group evals python -c '
from pathlib import Path
from evals.identity.codex_run import auth_file, credential_values, scan_credentials
print(scan_credentials(Path("runs/YOUR_RUN"), credential_values(auth_file())))
'
```

The native runner talks to Codex's subscription service itself. It does not use `inspect_swe.codex_cli`,
which sends inference through Inspect's model proxy, or implement a custom Responses/OAuth client.

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

What this exposes (the token reaches the container through the compose file's `environment` pass-through, not
through Inspect's exec options, so it is not written into the eval logs; check a log before sharing one): the token is in the environment of the processes the agent runs, so the agent can read
it. Treat it as the session's login: it is scoped to that session, never written to a file or to Git by
this code, and the saved transcripts do not contain it unless the agent echoes it, so scan a run folder for it before
committing and do not share one that has it. Runs use the session's subscription allowance, so long runs count against it.
