"""Exercise printed client settings with real processes, never a live Garmin API."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from garmin_connect_mcp import __version__


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_KEY = "synthetic-subprocess-key-not-real"
IGNORED_KEY = "synthetic-lower-priority-key-not-real"


@pytest.fixture
def private_environment(tmp_path):
    # Block networking inside child processes as well as using synthetic keys.
    # asyncio's local socketpair still works; DNS and outbound connects do not.
    guard = tmp_path / "network-guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(
        "import socket\n"
        "def blocked(*args, **kwargs):\n"
        "    raise AssertionError('This subprocess test must not use the network')\n"
        "socket.getaddrinfo = blocked\n"
        "socket.socket.connect = blocked\n"
        "socket.socket.connect_ex = blocked\n",
        encoding="utf-8",
    )
    key_path = tmp_path / "private café 🔑" / "key file"
    key_path.parent.mkdir()
    key_path.write_text(SYNTHETIC_KEY + "\n", encoding="utf-8")
    key_path.chmod(0o600)
    # Do not inherit unrelated secrets, even in pytest's failure-fixture repr.
    environment = {
        name: os.environ[name] for name in ("PATH", "SYSTEMROOT", "WINDIR")
        if name in os.environ
    }
    environment.update({
        "LANG": "C.UTF-8",
        "PYTHONPATH": os.pathsep.join((str(guard), str(ROOT / "src"))),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GARMIN_PERSONAL_API_KEY_FILE": str(key_path),
        "GARMIN_PERSONAL_API_KEY": IGNORED_KEY,
        "GARMIN_MCP_ACCESS_TOKEN_FILE": str(tmp_path / "missing-http-token"),
        "GARMIN_MCP_TIMEZONE": "Pacific/Auckland",
    })
    return environment, key_path, tmp_path


def run_cli(private_environment, *arguments):
    environment, _, directory = private_environment
    return subprocess.run(
        [sys.executable, "-m", "garmin_connect_mcp", *arguments],
        input="", text=True, encoding="utf-8", capture_output=True,
        cwd=directory, env=environment, timeout=10,
    )


def read_server(output, output_format):
    if output_format == "codex":
        return tomllib.loads(output)["mcp_servers"]["garmin"]
    key = "servers" if output_format == "vscode" else "mcpServers"
    return json.loads(output)[key]["garmin"]


def run_generated_server(server, private_environment):
    environment, _, directory = private_environment
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "synthetic-onboarding-check", "version": "1"},
        }},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "garmin_connector_status", "arguments": {},
        }},
    ]
    # Remove the original key-source variables: the generated environment must
    # carry the correct file reference itself, rather than work by inheritance.
    runtime_environment = {
        name: value for name, value in environment.items()
        if name not in {"GARMIN_PERSONAL_API_KEY", "GARMIN_PERSONAL_API_KEY_FILE", "GARMIN_MCP_TIMEZONE"}
    }
    runtime_environment.update(server["env"])
    return subprocess.run(
        [server["command"], *server["args"]],
        input="".join(json.dumps(message) + "\n" for message in messages),
        text=True, encoding="utf-8", capture_output=True,
        cwd=directory, env=runtime_environment, timeout=10,
    )


@pytest.mark.parametrize("output_format", ["json", "vscode", "codex"])
def test_generated_configs_start_stdio_without_network(private_environment, output_format):
    _, key_path, _ = private_environment
    exported = run_cli(private_environment, "client-config", "--format", output_format)
    assert exported.returncode == 0, exported.stderr
    assert exported.stderr == ""
    assert SYNTHETIC_KEY not in exported.stdout
    assert IGNORED_KEY not in exported.stdout
    server = read_server(exported.stdout, output_format)
    assert server["command"] == os.path.abspath(sys.executable)
    assert server["args"] == ["-m", "garmin_connect_mcp", "stdio"]
    assert server["env"] == {
        "GARMIN_PERSONAL_API_KEY_FILE": str(key_path),
        "GARMIN_MCP_TIMEZONE": "Pacific/Auckland",
    }
    if output_format == "vscode":
        assert server["type"] == "stdio"

    process = run_generated_server(server, private_environment)
    assert process.returncode == 0, process.stderr
    assert process.stderr == ""
    assert SYNTHETIC_KEY not in process.stdout
    replies = [json.loads(line) for line in process.stdout.splitlines()]
    assert [reply["id"] for reply in replies] == [1, 2, 3]
    assert replies[0]["result"]["serverInfo"]["version"] == __version__
    assert len(replies[1]["result"]["tools"]) == 6
    status = replies[2]["result"]["structuredContent"]
    assert status["timezone"] == "Pacific/Auckland"
    assert status["data"]["version"] == __version__
    assert status["data"]["read_only"] is True
    assert status["data"]["garmin_authenticated"] == "not_checked"


@pytest.mark.parametrize("contents", [b"", b"synthetic invalid secret", b"\xff\xfe"])
def test_export_does_not_read_malformed_key_but_startup_rejects_it(private_environment, contents):
    _, key_path, _ = private_environment
    key_path.write_bytes(contents)
    exported = run_cli(private_environment, "client-config")
    assert exported.returncode == 0, exported.stderr
    server = read_server(exported.stdout, "json")
    process = run_generated_server(server, private_environment)
    assert process.returncode == 1
    assert process.stdout == ""
    assert "Traceback" not in process.stderr
    assert "synthetic invalid secret" not in process.stderr
    assert IGNORED_KEY not in process.stderr
    assert str(key_path) not in process.stderr


def test_missing_selected_key_fails_doctor_without_fallback_or_network(private_environment):
    environment, _, directory = private_environment
    missing = directory / "missing-private-key"
    environment["GARMIN_PERSONAL_API_KEY_FILE"] = str(missing)
    exported = run_cli(private_environment, "client-config")
    assert exported.returncode == 0
    assert read_server(exported.stdout, "json")["env"]["GARMIN_PERSONAL_API_KEY_FILE"] == str(missing)
    checked = run_cli(private_environment, "doctor")
    assert checked.returncode == 1
    assert checked.stdout == ""
    assert checked.stderr == "Cannot read the configured secret file.\n"
    assert IGNORED_KEY not in checked.stderr


def test_environment_only_key_is_never_serialized(private_environment):
    environment, _, _ = private_environment
    environment.pop("GARMIN_PERSONAL_API_KEY_FILE")
    result = run_cli(private_environment, "client-config")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "secret manager" in result.stderr
    assert IGNORED_KEY not in result.stderr
    assert "Traceback" not in result.stderr


def test_bad_http_bearer_is_ignored_by_stdio_but_rejected_by_http(private_environment):
    environment, _, _ = private_environment
    environment.pop("GARMIN_MCP_ACCESS_TOKEN_FILE")
    environment["GARMIN_MCP_ACCESS_TOKEN"] = "tiny"
    exported = run_cli(private_environment, "client-config")
    process = run_generated_server(read_server(exported.stdout, "json"), private_environment)
    assert process.returncode == 0, process.stderr
    rejected = run_cli(private_environment, "http")
    assert rejected.returncode == 1
    assert rejected.stdout == ""
    assert rejected.stderr == "HTTP access token must contain at least 32 characters.\n"


def test_codex_config_handles_del_in_an_explicit_path(private_environment):
    environment, _, directory = private_environment
    # POSIX permits DEL in a filename; TOML requires this character to be escaped.
    environment["GARMIN_PERSONAL_API_KEY_FILE"] = str(directory / "private-\x7f-key")
    exported = run_cli(private_environment, "client-config", "--format", "codex")
    assert exported.returncode == 0, exported.stderr
    server = read_server(exported.stdout, "codex")
    assert server["env"]["GARMIN_PERSONAL_API_KEY_FILE"] == environment["GARMIN_PERSONAL_API_KEY_FILE"]
