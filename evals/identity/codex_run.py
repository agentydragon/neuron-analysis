"""Native Codex launcher; credentials never enter Inspect's command arguments or uploaded files."""

import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


def auth_file() -> Path:
    path = Path(os.environ.get("CODEX_AUTH_FILE") or
                Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "auth.json").expanduser().resolve()
    try:
        auth = json.loads(path.read_text())
    except (OSError, ValueError):
        raise RuntimeError(
            "Cannot read Codex auth.json. Run `codex login -c 'cli_auth_credentials_store=\"file\"'` "
            "or set CODEX_AUTH_FILE to your existing file-backed ChatGPT login."
        ) from None
    tokens = (auth.get("tokens") or {}) if isinstance(auth, dict) else {}
    if not isinstance(auth, dict) or auth.get("auth_mode") not in (None, "chatgpt") or auth.get("OPENAI_API_KEY") or not (
        isinstance(tokens, dict) and all(isinstance(tokens.get(key), str) and tokens[key]
                                        for key in ("access_token", "refresh_token"))
    ):
        raise RuntimeError("CODEX_AUTH_FILE must contain a managed ChatGPT login, with access and refresh tokens.")
    os.environ["CODEX_AUTH_FILE"] = str(path)
    return path


def credential_values(path: Path) -> set[bytes]:
    auth = json.loads(path.read_text())
    tokens = auth.get("tokens") or {}
    return {tokens[key].encode() for key in ("access_token", "refresh_token", "id_token")
            if isinstance(tokens.get(key), str) and tokens[key]}


def contains_credential(stream: BinaryIO, secrets: set[bytes]) -> bool:
    overlap = max(map(len, secrets), default=1) - 1
    tail = b""
    while chunk := stream.read(1024 * 1024):
        data = tail + chunk
        if any(secret in data for secret in secrets):
            return True
        tail = data[-overlap:] if overlap else b""
    return False


def scan_credentials(folder: Path, secrets: set[bytes]) -> list[str]:
    """Scan raw artifacts and compressed Inspect .eval members without printing the matching secret."""
    matches = []
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                if any(info.compress_type == 93 for info in archive.infolist()):
                    # Inspect writes Zstandard ZIPs; Python 3.12 needs its compatibility module.
                    import zipfile_zstd  # noqa: F401

                for name in archive.namelist():
                    with archive.open(name) as stream:
                        if contains_credential(stream, secrets):
                            matches.append(f"{path.relative_to(folder)}!{name}")
        with path.open("rb") as stream:
            if contains_credential(stream, secrets):
                matches.append(str(path.relative_to(folder)))
    return matches


def main() -> int:
    source = auth_file()
    task = os.environ.get("TASK", "evals/identity/task.py@identity")
    if "@" not in task or not task.rsplit("@", 1)[1]:
        raise RuntimeError("TASK must name a task, e.g. evals/identity/task.py@identity_clips")
    run = Path(os.environ.get("RUN_DIR") or ROOT / "runs" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"_codex_{task.rsplit('@', 1)[1]}_{uuid4().hex[:8]}"
    )).resolve()
    if source.is_relative_to(run):
        raise RuntimeError("Keep CODEX_AUTH_FILE outside the run folder.")
    run.mkdir(parents=True, exist_ok=False)
    os.environ["RUN_DIR"] = str(run)
    # No Claude/API credentials pass through this compose file. The auth path is interpolated by Docker.
    command = ["uv", "run", "--group", "evals", "inspect", "eval", task, *sys.argv[1:],
               "--model", "mockllm/model", "-T", "agent=codex_cli", "--log-dir", str(run)]
    secrets = credential_values(source)
    print(f"run folder: {run}", file=sys.stderr)
    env = dict(os.environ)
    env.setdefault("XDG_DATA_HOME", str(ROOT / ".cache" / "xdg-data"))
    env.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache" / "xdg-cache"))
    try:
        return subprocess.run(command, cwd=ROOT, env=env).returncode
    finally:
        secrets |= credential_values(source)  # include tokens refreshed by Codex during the run
        matches = scan_credentials(run, secrets)
        if matches:
            raise RuntimeError("Credentials found in run artifacts; do not commit or share: " + ", ".join(matches))
        print("Credential scan passed (initial and final auth tokens).", file=sys.stderr)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
