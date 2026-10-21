@README.md

Use `uv sync --locked` for dependencies and `uv run pytest` for tests.

Keep original inputs in `data/` under Git LFS. Rollout data is tracked too, also under Git LFS: each real run
gets its own folder `runs/<run-id>/` holding the Inspect log, the saved `annotations.json` answers and the agent
transcripts. `evals/identity/run-claude-code-web.sh` creates and fills it (set `RUN_DIR` to choose the folder);
commit the folder when a run is worth keeping. Put stub runs, tests and other throwaway output in `runs/scratch/`
and caches in `.cache/`; both are git-ignored.

Before committing rollout data, scan it for the session login token. It reaches the sandbox through the compose
file's environment pass-through, not Inspect's exec options, so a run's logs should not contain it, but check.
When launching Inspect, name the task (`task.py@identity` or `task.py@identity_clips`); a bare `task.py` runs every
task in the file.

Preserve input files and existing annotations, and do not delete or rewrite committed rollout data.
