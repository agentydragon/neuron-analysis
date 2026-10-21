import asyncio
import io
import json
import os
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.identity import codex_run


@pytest.fixture
def auth(tmp_path, monkeypatch):
    path = tmp_path / "login" / "auth.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"auth_mode": "chatgpt", "tokens": {
        "access_token": "secret-access", "refresh_token": "secret-refresh", "id_token": "secret-id",
    }}))
    path.chmod(0o600)
    monkeypatch.setenv("CODEX_AUTH_FILE", str(path))
    return path


def test_auth_uses_codex_home_without_logging_secrets(auth, monkeypatch):
    monkeypatch.delenv("CODEX_AUTH_FILE")
    monkeypatch.setenv("CODEX_HOME", str(auth.parent))
    assert codex_run.auth_file() == auth
    assert os.environ["CODEX_AUTH_FILE"] == str(auth)
    auth.write_text('{"auth_mode": "apikey", "OPENAI_API_KEY": "do-not-print-this"}')
    with pytest.raises(RuntimeError, match="ChatGPT") as error:
        codex_run.auth_file()
    assert "do-not-print-this" not in str(error.value)


@pytest.mark.parametrize("contents", ["bad-json", "[]", '{"tokens": null}', '{"tokens": ["secret"]}',
                                     '{"tokens": {"access_token": 123, "refresh_token": "secret"}}'])
def test_bad_auth_has_actionable_error_without_contents(auth, contents):
    auth.write_text(contents)
    with pytest.raises(RuntimeError, match="Codex auth.json|ChatGPT"):
        codex_run.auth_file()


def test_scan_checks_compressed_eval_members_and_chunk_boundaries(tmp_path):
    secret = b"not-for-an-artifact"
    payload = b"x" * (1024 * 1024 - 3) + secret
    assert codex_run.contains_credential(io.BytesIO(payload), {secret})
    (tmp_path / "events.jsonl").write_bytes(payload)
    with zipfile.ZipFile(tmp_path / "run.eval", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("samples/1.json", payload)
    assert sorted(codex_run.scan_credentials(tmp_path, {secret})) == ["events.jsonl", "run.eval!samples/1.json"]
    assert codex_run.scan_credentials(tmp_path, {b"another-token"}) == []


def test_scan_checks_inspect_zstandard_logs(tmp_path):
    pytest.importorskip("zipfile_zstd")
    with zipfile.ZipFile(tmp_path / "run.eval", "w", compression=zipfile.ZIP_ZSTANDARD) as archive:
        archive.writestr("samples/1.json", "hidden-credential")
    assert "run.eval!samples/1.json" in codex_run.scan_credentials(tmp_path, {b"hidden-credential"})


def test_launcher_preserves_auth_and_scans_refreshed_credentials(auth, tmp_path, monkeypatch):
    run = tmp_path / "run"
    monkeypatch.setenv("RUN_DIR", str(run))
    monkeypatch.setenv("TASK", "evals/identity/task.py@identity_clips")
    monkeypatch.setattr("sys.argv", ["codex_run", "-T", "groups=24-32"])
    seen = []

    def execute(command, **kwargs):
        seen.append(command)
        updated = json.loads(auth.read_text())
        updated["tokens"]["access_token"] = "rotated-access"
        auth.write_text(json.dumps(updated))
        (run / "events.jsonl").write_text("rotated-access")
        return SimpleNamespace(returncode=17)

    monkeypatch.setattr(subprocess, "run", execute)
    with pytest.raises(RuntimeError, match="Credentials found.*events.jsonl") as error:
        codex_run.main()
    assert "rotated-access" not in str(error.value)
    command = seen[0]
    assert "evals/identity/task.py@identity_clips" in command
    assert "groups=24-32" in command and "agent=codex_cli" in command
    assert not any("secret-" in arg for arg in command)
    assert json.loads(auth.read_text())["tokens"]["access_token"] == "rotated-access"


def test_launcher_preserves_exit_status_and_refuses_existing_run(auth, tmp_path, monkeypatch):
    run = tmp_path / "run"
    monkeypatch.setenv("RUN_DIR", str(run))
    monkeypatch.setattr("sys.argv", ["codex_run"])
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=17))
    assert codex_run.main() == 17
    with pytest.raises(FileExistsError):
        codex_run.main()


def test_launcher_rejects_bare_task_before_creating_run(auth, tmp_path, monkeypatch):
    monkeypatch.setenv("TASK", "evals/identity/task.py")
    monkeypatch.setenv("RUN_DIR", str(tmp_path / "run"))
    with pytest.raises(RuntimeError, match="must name a task"):
        codex_run.main()
    assert not (tmp_path / "run").exists()


def test_codex_task_uses_native_compose_and_preserves_claude_default(auth):
    pytest.importorskip("inspect_ai")
    from evals.identity.task import identity, identity_clips

    native = identity_clips(agent="codex_cli", groups="24-32", minutes=1)
    assert native.sandbox.config.endswith("compose.codex.yaml")
    script = native.dataset[0].setup
    assert "@openai/codex@0.162.1" in script
    assert "@anthropic-ai" not in script
    assert "/run/codex-auth.json" in script
    assert "secret-access" not in script
    claude = identity()
    assert claude.sandbox.config.endswith("compose.yaml")
    assert "@anthropic-ai/claude-code@2.1.305" in claude.dataset[0].setup

    import yaml

    folder = Path(__file__).resolve().parents[1] / "evals" / "identity"
    native_compose = yaml.safe_load((folder / "compose.codex.yaml").read_text())
    service = native_compose["services"]["default"]
    assert native_compose["x-inspect_docker_sandbox"]["unsafe_allow_writable_host_mounts"] is True
    assert service["image"] == yaml.safe_load((folder / "compose.yaml").read_text())["services"]["default"]["image"]
    assert len(service["volumes"]) == 1
    assert service["volumes"][0]["target"] == "/run/codex-auth.json"
    assert service["volumes"][0]["bind"]["create_host_path"] is False
    assert "environment" not in service


@pytest.mark.parametrize("outcome", ["success", "failure", "timeout", "exec_error"])
def test_codex_collects_transcripts_even_after_timeout_or_exec_error(tmp_path, monkeypatch, outcome):
    pytest.importorskip("inspect_ai")
    from evals.identity import task

    calls = []

    class Sandbox:
        async def exec(self, command, **kwargs):
            calls.append((command, kwargs))
            if command[0] == "find":
                return SimpleNamespace(returncode=0, stdout="/home/agent/.codex/sessions/native.jsonl\n")
            if outcome == "timeout":
                raise TimeoutError
            if outcome == "exec_error":
                raise ConnectionError("sandbox disconnected")
            return SimpleNamespace(returncode=2 if outcome == "failure" else 0)

        async def read_file(self, path):
            if path == "/tmp/codex_events.jsonl":
                return '{"type":"turn.started"}\n'
            if path == "/tmp/codex_version.txt":
                return "codex-cli 0.162.1\n"
            if path.endswith("/native.jsonl"):
                return '{"type":"response_item","payload":{"name":"view_image"}}\n'
            raise FileNotFoundError(path)

    monkeypatch.setattr(task, "sandbox", Sandbox)
    monkeypatch.setattr(task, "transcript", lambda: SimpleNamespace(info=lambda *args, **kwargs: None))
    monkeypatch.setenv("RUN_DIR", str(tmp_path))
    state = SimpleNamespace(input_text="Look at target.jpg; write output/annotations.json", sample_id="clip", metadata={})
    solve = task.codex_cli("gpt-6-luna", "low", 1)
    if outcome == "exec_error":
        with pytest.raises(ConnectionError):
            asyncio.run(solve(state, None))
    else:
        asyncio.run(solve(state, None))
    folder, = (tmp_path / "transcripts").iterdir()
    assert json.loads((folder / "events.jsonl").read_text())["type"] == "turn.started"
    status = json.loads((folder / "status.json").read_text())
    assert status["timed_out"] == (outcome == "timeout")
    assert status["returncode"] == {"success": 0, "failure": 2}.get(outcome)
    assert status["version"] == "codex-cli 0.162.1"
    assert status["native_transcript_error"] is None
    assert "view_image" in (folder / "session_native.jsonl").read_text()
    command, kwargs = calls[0]
    assert "--skip-git-repo-check" in command[2]
    assert "--ignore-user-config" in command[2]
    assert kwargs["timeout"] == 60 and kwargs["timeout_retry"] is False
    assert "secret-" not in str(calls)
