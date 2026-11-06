"""Onboarding tests use isolated directories and synthetic credentials only."""
import json
import os
from pathlib import Path
import sys
import tomllib
from types import SimpleNamespace
import warnings

import pytest

from garmin_connect_mcp import __version__, cli, config, onboarding
from garmin_connect_mcp.errors import ConfigurationError, ConnectorError, UpstreamError


SYNTHETIC_KEY = "synthetic-onboarding-key-not-real"
PRIVATE_ACTIVITY = "synthetic-private-activity-never-print"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    for name in (config.API_KEY_ENV, config.API_KEY_FILE_ENV, config.HTTP_TOKEN_ENV,
                 config.HTTP_TOKEN_FILE_ENV, "GARMIN_MCP_TIMEZONE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "DEFAULT_DIR", tmp_path / "private-config")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(onboarding, "GarminClient", lambda *_: pytest.fail("Unexpected Garmin client creation"))


@pytest.fixture
def hidden_input(monkeypatch):
    prompts = []
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    def read(prompt):
        prompts.append(prompt)
        return SYNTHETIC_KEY
    monkeypatch.setattr(onboarding.getpass, "getpass", read)
    return prompts


@pytest.fixture
def fake_garmin(monkeypatch):
    state = SimpleNamespace(clients=[], calls=[], failure=None, on_get=None)
    class FakeClient:
        def __init__(self, settings):
            self.settings, self.closed = settings, False
            state.clients.append(self)

        async def get(self, path, params):
            state.calls.append((path, params))
            if state.on_get:
                state.on_get()
            if state.failure:
                raise state.failure
            return [{"activityName": PRIVATE_ACTIVITY}]

        async def aclose(self):
            self.closed = True
    monkeypatch.setattr(onboarding, "GarminClient", FakeClient)
    return state


def run(monkeypatch, *arguments, code=None):
    monkeypatch.setattr(sys, "argv", ["garmin-connect-mcp", *arguments])
    if code is None:
        cli.main()
    else:
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == code


def assert_private_output(capsys, *extra_keys):
    captured = capsys.readouterr()
    for value in (SYNTHETIC_KEY, PRIVATE_ACTIVITY, *extra_keys):
        assert value not in captured.out + captured.err
    return captured


def test_first_setup_checks_before_saving_and_prints_only_safe_config(monkeypatch, hidden_input, fake_garmin, capsys):
    key_path = config.DEFAULT_DIR / "api-key"
    fake_garmin.on_get = lambda: pytest.fail("Key saved before verification") if key_path.exists() else None
    run(monkeypatch, "setup")
    assert config.read_secret(key_path) == SYNTHETIC_KEY
    assert not (config.DEFAULT_DIR / "http-token").exists()
    assert len(hidden_input) == 1
    assert fake_garmin.calls == [("/activitylist-service/activities/search/activities", {"start": 0, "limit": 1})]
    assert fake_garmin.clients[0].closed
    if os.name == "posix":
        assert key_path.stat().st_mode & 0o777 == 0o600
        assert key_path.parent.stat().st_mode & 0o777 == 0o700
    captured = assert_private_output(capsys)
    server = json.loads(captured.out)["mcpServers"]["garmin"]
    assert server["env"][config.API_KEY_FILE_ENV] == str(key_path)
    assert '"mcp_connection": "not_checked"' in captured.err
    assert "No client settings were changed" in captured.err
    assert list(config.DEFAULT_DIR.iterdir()) == [key_path]


def test_setup_reports_progress_before_network_probe(monkeypatch, hidden_input, fake_garmin, capsys):
    before_probe = []
    fake_garmin.on_get = lambda: before_probe.append(capsys.readouterr())
    run(monkeypatch, "setup")
    assert len(before_probe) == 1
    assert not before_probe[0].out
    assert before_probe[0].err == "Checking Garmin authentication and one activity read...\n"
    captured = assert_private_output(capsys)
    assert "mcpServers" in json.loads(captured.out)


def test_repeat_setup_reuses_key_without_prompt_or_write(monkeypatch, fake_garmin, capsys):
    key_path = config.DEFAULT_DIR / "api-key"
    onboarding.write_secret(key_path, SYNTHETIC_KEY)
    before = key_path.stat()
    run(monkeypatch, "setup")
    after = key_path.stat()
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
    assert fake_garmin.clients[0].settings.api_key == SYNTHETIC_KEY
    assert_private_output(capsys)


def test_setup_explicit_file_has_precedence_and_is_not_copied(tmp_path, monkeypatch, fake_garmin, capsys):
    explicit = tmp_path / "separate-store" / "selected-key"
    onboarding.write_secret(explicit, SYNTHETIC_KEY)
    monkeypatch.setenv(config.API_KEY_FILE_ENV, str(explicit))
    monkeypatch.setenv(config.API_KEY_ENV, "synthetic-lower-priority-key")
    run(monkeypatch, "setup")
    assert fake_garmin.clients[0].settings.api_key == SYNTHETIC_KEY
    assert not config.DEFAULT_DIR.exists()
    captured = assert_private_output(capsys, "synthetic-lower-priority-key")
    assert json.loads(captured.out)["mcpServers"]["garmin"]["env"][config.API_KEY_FILE_ENV] == str(explicit)


def test_setup_env_key_is_checked_but_not_copied_or_exported(monkeypatch, fake_garmin, capsys):
    monkeypatch.setenv(config.API_KEY_ENV, SYNTHETIC_KEY)
    run(monkeypatch, "setup")
    assert fake_garmin.clients[0].settings.api_key == SYNTHETIC_KEY
    assert not config.DEFAULT_DIR.exists()
    captured = assert_private_output(capsys)
    assert not captured.out
    assert "Client settings were not generated" in captured.err
    assert "secret manager" in captured.err


@pytest.mark.parametrize("error", [UpstreamError(401), ConnectorError("Cannot reach Garmin securely.")])
@pytest.mark.parametrize("replace", [False, True])
def test_failed_probe_never_persists_candidate(monkeypatch, hidden_input, fake_garmin, capsys, error, replace):
    key_path = config.DEFAULT_DIR / "api-key"
    if replace:
        onboarding.write_secret(key_path, "synthetic-previous-key")
        previous = key_path.read_bytes()
    fake_garmin.failure = error
    run(monkeypatch, "setup", *(["--replace-key"] if replace else []), code=1)
    assert fake_garmin.clients[0].closed
    if replace:
        assert key_path.read_bytes() == previous
    else:
        assert not key_path.exists()
    assert_private_output(capsys, "synthetic-previous-key")


def test_rotation_probes_before_atomic_replacement(monkeypatch, hidden_input, fake_garmin, capsys):
    key_path = config.DEFAULT_DIR / "api-key"
    onboarding.write_secret(key_path, "synthetic-previous-key")
    before = key_path.stat()
    seen = []
    fake_garmin.on_get = lambda: seen.append(config.read_secret(key_path))
    run(monkeypatch, "setup", "--replace-key")
    assert seen == ["synthetic-previous-key"]
    assert config.read_secret(key_path) == SYNTHETIC_KEY
    assert key_path.stat().st_ino != before.st_ino
    assert list(config.DEFAULT_DIR.iterdir()) == [key_path]
    assert_private_output(capsys, "synthetic-previous-key")


@pytest.mark.parametrize("variable", [config.API_KEY_ENV, config.API_KEY_FILE_ENV])
@pytest.mark.parametrize("command", [["setup", "--replace-key"], ["configure"]])
def test_managed_writes_refuse_environment_overrides(monkeypatch, variable, command, capsys):
    monkeypatch.setenv(variable, SYNTHETIC_KEY)
    run(monkeypatch, *command, code=1)
    assert not config.DEFAULT_DIR.exists()
    assert "environment override" in assert_private_output(capsys).err


@pytest.mark.parametrize("kind", ["missing", "directory", "symlink", "broken-symlink"])
def test_rotation_rejects_nonregular_or_missing_target(tmp_path, monkeypatch, kind, capsys):
    path = config.DEFAULT_DIR / "api-key"
    path.parent.mkdir()
    if kind == "directory":
        path.mkdir()
    elif kind in {"symlink", "broken-symlink"}:
        target = tmp_path / "elsewhere" / "key"
        if kind == "symlink":
            onboarding.write_secret(target, SYNTHETIC_KEY)
        path.symlink_to(target)
    run(monkeypatch, "setup", "--replace-key", code=1)
    assert_private_output(capsys)


def test_first_setup_rejects_broken_symlink_before_prompt(tmp_path, monkeypatch, capsys):
    path = config.DEFAULT_DIR / "api-key"
    path.parent.mkdir()
    path.symlink_to(tmp_path / "missing")
    run(monkeypatch, "setup", code=1)
    assert "regular file" in assert_private_output(capsys).err


@pytest.mark.parametrize("replace", [False, True])
def test_concurrent_file_change_is_not_overwritten(monkeypatch, hidden_input, fake_garmin, replace, capsys):
    key_path = config.DEFAULT_DIR / "api-key"
    if replace:
        onboarding.write_secret(key_path, "synthetic-original")
        fake_garmin.on_get = lambda: key_path.write_text("synthetic-concurrent-key\n")
    else:
        fake_garmin.on_get = lambda: onboarding.write_secret(key_path, "synthetic-concurrent-key")
    run(monkeypatch, "setup", *(["--replace-key"] if replace else []), code=1)
    assert config.read_secret(key_path) == "synthetic-concurrent-key"
    assert list(config.DEFAULT_DIR.iterdir()) == [key_path]
    assert_private_output(capsys, "synthetic-concurrent-key")


def test_failed_atomic_replace_preserves_old_key_and_cleans_temp(monkeypatch, hidden_input, fake_garmin, capsys):
    key_path = config.DEFAULT_DIR / "api-key"
    onboarding.write_secret(key_path, "synthetic-previous-key")
    def fail_replace(*_):
        raise PermissionError("synthetic-error-must-not-print")
    monkeypatch.setattr(onboarding.os, "replace", fail_replace)
    run(monkeypatch, "setup", "--replace-key", code=1)
    assert config.read_secret(key_path) == "synthetic-previous-key"
    assert list(config.DEFAULT_DIR.iterdir()) == [key_path]
    assert "Cannot access local configuration safely" in assert_private_output(capsys, "synthetic-error-must-not-print").err


@pytest.mark.parametrize("failure", ["not-tty", "warning", "eof", "interrupt", "invalid"])
def test_hidden_input_fails_closed(monkeypatch, failure, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: failure != "not-tty")
    def cannot_read(_):
        if failure == "not-tty":
            pytest.fail("getpass must not be called without a terminal")
        if failure == "warning":
            warnings.warn("echo unavailable", onboarding.getpass.GetPassWarning)
            pytest.fail("getpass fallback must not continue")
        if failure == "eof":
            raise EOFError
        if failure == "interrupt":
            raise KeyboardInterrupt
        return "bad secret"
    monkeypatch.setattr(onboarding.getpass, "getpass", cannot_read)
    run(monkeypatch, "setup", code=130 if failure == "interrupt" else 1)
    assert not config.DEFAULT_DIR.exists()
    assert_private_output(capsys, "bad secret")


@pytest.mark.parametrize("invalid_source", ["missing-file", "empty-file-variable", "empty-key"])
def test_explicit_invalid_source_does_not_fall_back(tmp_path, monkeypatch, invalid_source, capsys):
    onboarding.write_secret(config.DEFAULT_DIR / "api-key", SYNTHETIC_KEY)
    if invalid_source == "empty-key":
        monkeypatch.setenv(config.API_KEY_ENV, "")
    else:
        monkeypatch.setenv(config.API_KEY_FILE_ENV, "" if invalid_source == "empty-file-variable" else str(tmp_path / "missing"))
        monkeypatch.setenv(config.API_KEY_ENV, SYNTHETIC_KEY)
    run(monkeypatch, "setup", code=1)
    assert_private_output(capsys)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
@pytest.mark.parametrize("command", [["setup"], ["setup", "--replace-key"]])
def test_setup_refuses_broad_key_permissions(monkeypatch, command, capsys):
    path = config.DEFAULT_DIR / "api-key"
    onboarding.write_secret(path, SYNTHETIC_KEY)
    path.chmod(0o644)
    run(monkeypatch, *command, code=1)
    assert "chmod 600" in assert_private_output(capsys).err


@pytest.mark.parametrize("command", ["setup", "doctor"])
def test_non_http_checks_ignore_bad_http_secret(monkeypatch, fake_garmin, command, capsys):
    onboarding.write_secret(config.DEFAULT_DIR / "api-key", SYNTHETIC_KEY)
    monkeypatch.setenv(config.HTTP_TOKEN_FILE_ENV, "/synthetic/nonexistent/http-token")
    run(monkeypatch, command)
    assert fake_garmin.clients[0].settings.access_token is None
    assert_private_output(capsys)


@pytest.mark.parametrize("arguments", [[], ["stdio"]])
def test_stdio_defaults_and_ignores_http_credentials(monkeypatch, arguments):
    monkeypatch.setenv(config.API_KEY_ENV, SYNTHETIC_KEY)
    monkeypatch.setenv(config.HTTP_TOKEN_ENV, "too-short")
    monkeypatch.setattr(cli, "GarminClient", lambda settings: SimpleNamespace(settings=settings))
    received = []
    async def serve(service):
        received.append(service.client.settings)
    monkeypatch.setattr(cli, "serve_stdio", serve)
    run(monkeypatch, *arguments)
    assert received[0].access_token is None


def test_http_still_validates_separate_bearer(monkeypatch, capsys):
    monkeypatch.setenv(config.API_KEY_ENV, SYNTHETIC_KEY)
    monkeypatch.setenv(config.HTTP_TOKEN_ENV, "too-short")
    run(monkeypatch, "http", code=1)
    assert "at least 32" in assert_private_output(capsys).err


def test_configure_http_is_offline_idempotent_and_does_not_create_api_key(monkeypatch, capsys):
    token = "synthetic-independent-http-token-value-at-least-32"
    monkeypatch.setattr(onboarding.secrets, "token_urlsafe", lambda _: token)
    run(monkeypatch, "configure-http")
    path = config.DEFAULT_DIR / "http-token"
    before = path.stat()
    run(monkeypatch, "configure-http")
    assert config.read_secret(path) == token
    assert path.stat().st_ino == before.st_ino
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert not (config.DEFAULT_DIR / "api-key").exists()
    assert_private_output(capsys, token)


def test_configure_http_reuses_explicit_source(tmp_path, monkeypatch, capsys):
    path = tmp_path / "other" / "bearer"
    token = "synthetic-explicit-http-token-long-enough"
    onboarding.write_secret(path, token)
    monkeypatch.setenv(config.HTTP_TOKEN_FILE_ENV, str(path))
    monkeypatch.setenv(config.HTTP_TOKEN_ENV, "lower-priority")
    run(monkeypatch, "configure-http")
    assert not config.DEFAULT_DIR.exists()
    assert_private_output(capsys, token, "lower-priority")


def test_configure_http_refuses_reused_garmin_key(monkeypatch, capsys):
    key = "synthetic-shared-key-value-at-least-32-characters"
    monkeypatch.setenv(config.API_KEY_ENV, key)
    monkeypatch.setenv(config.HTTP_TOKEN_ENV, key)
    run(monkeypatch, "configure-http", code=1)
    assert "different" in assert_private_output(capsys, key).err


def test_legacy_configure_remains_offline_and_does_not_overwrite(monkeypatch, hidden_input, capsys):
    run(monkeypatch, "configure")
    assert config.read_secret(config.DEFAULT_DIR / "api-key") == SYNTHETIC_KEY
    assert len(config.read_secret(config.DEFAULT_DIR / "http-token")) >= 32
    run(monkeypatch, "configure", code=1)
    assert len(hidden_input) == 1
    assert "already exists" in assert_private_output(capsys).err


@pytest.mark.parametrize("output_format", ["json", "vscode", "codex"])
def test_client_config_is_pure_and_reads_no_credentials(monkeypatch, output_format, capsys):
    monkeypatch.setenv("GARMIN_MCP_TIMEZONE", "Europe/London")
    monkeypatch.setattr(config, "read_secret", lambda *_: pytest.fail("Client config read credentials"))
    run(monkeypatch, "client-config", "--format", output_format)
    captured = assert_private_output(capsys)
    assert not captured.err
    if output_format == "codex":
        server = tomllib.loads(captured.out)["mcp_servers"]["garmin"]
    elif output_format == "vscode":
        server = json.loads(captured.out)["servers"]["garmin"]
        assert server.pop("type") == "stdio"
    else:
        server = json.loads(captured.out)["mcpServers"]["garmin"]
    assert server == {"command": str(Path(sys.executable).absolute()),
                      "args": ["-m", "garmin_connect_mcp", "stdio"],
                      "env": {config.API_KEY_FILE_ENV: str(config.DEFAULT_DIR / "api-key"),
                              "GARMIN_MCP_TIMEZONE": "Europe/London"}}
    assert not config.DEFAULT_DIR.exists()


@pytest.mark.parametrize("output_format", ["json", "vscode", "codex"])
def test_client_config_preserves_virtualenv_symlink_and_escapes_paths(tmp_path, monkeypatch, output_format):
    interpreter = tmp_path / 'virtual env "quoted" 🏃' / "python"
    interpreter.parent.mkdir()
    interpreter.symlink_to(sys.executable)
    secret = tmp_path / 'private "quoted" 🏊' / "api-key"
    monkeypatch.setattr(sys, "executable", str(interpreter))
    monkeypatch.setenv(config.API_KEY_FILE_ENV, str(secret))
    monkeypatch.setenv(config.API_KEY_ENV, SYNTHETIC_KEY)
    rendered = onboarding.client_config(output_format)
    parsed = tomllib.loads(rendered) if output_format == "codex" else json.loads(rendered)
    server = next(iter(parsed.values()))["garmin"]
    assert server["command"] == str(interpreter)
    assert server["env"][config.API_KEY_FILE_ENV] == str(secret)
    assert SYNTHETIC_KEY not in rendered


def test_client_config_uses_default_json(monkeypatch, capsys):
    run(monkeypatch, "client-config")
    assert "mcpServers" in json.loads(capsys.readouterr().out)


def test_client_config_refuses_raw_key_export(monkeypatch, capsys):
    monkeypatch.setenv(config.API_KEY_ENV, SYNTHETIC_KEY)
    run(monkeypatch, "client-config", code=1)
    captured = assert_private_output(capsys)
    assert not captured.out
    assert "secret manager" in captured.err


@pytest.mark.parametrize("variable,value", [(config.API_KEY_FILE_ENV, ""), ("GARMIN_MCP_TIMEZONE", "not/a-timezone")])
def test_client_config_validates_nonsecret_settings(monkeypatch, variable, value, capsys):
    monkeypatch.setenv(variable, value)
    run(monkeypatch, "client-config", code=1)
    assert not assert_private_output(capsys).out


@pytest.mark.parametrize("arguments", [["doctor", "--replace-key"], ["setup", "--format", "json"], ["client-config", "--format", "unknown"]])
def test_command_specific_flags_are_rejected(monkeypatch, arguments):
    run(monkeypatch, *arguments, code=2)


def test_settings_keep_http_validation_by_default(monkeypatch):
    monkeypatch.setenv(config.API_KEY_ENV, SYNTHETIC_KEY)
    monkeypatch.setenv(config.HTTP_TOKEN_ENV, "tiny")
    assert config.Settings.load(include_http=False).access_token is None
    with pytest.raises(ConfigurationError, match="at least 32"):
        config.Settings.load()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_secret_permissions_are_owner_read_write_even_with_restrictive_umask():
    old_umask = os.umask(0o777)
    try:
        path = config.DEFAULT_DIR / "api-key"
        onboarding.write_secret(path, SYNTHETIC_KEY)
    finally:
        os.umask(old_umask)
    assert path.stat().st_mode & 0o777 == 0o600
    assert config.read_secret(path) == SYNTHETIC_KEY


@pytest.mark.parametrize("command", ["setup", "client-config"])
def test_unknown_home_in_explicit_path_is_sanitized(monkeypatch, command, capsys):
    monkeypatch.setenv(config.API_KEY_FILE_ENV, "~synthetic-user-missing-from-this-machine/private/key")
    run(monkeypatch, command, code=1)
    captured = assert_private_output(capsys)
    assert "Traceback" not in captured.err
    assert not captured.out


def test_version_requires_no_credentials_or_network(monkeypatch, capsys):
    monkeypatch.setattr(config, "read_secret", lambda *_: pytest.fail("Version read credentials"))
    run(monkeypatch, "--version", code=0)
    captured = assert_private_output(capsys)
    assert captured.out == f"garmin-connect-mcp {__version__}\n"
    assert not captured.err
    assert not config.DEFAULT_DIR.exists()


def test_codex_config_escapes_del_in_paths(monkeypatch):
    interpreter = "/synthetic/python-\x7f"
    key_path = "/synthetic/key-\x7f"
    monkeypatch.setattr(sys, "executable", interpreter)
    monkeypatch.setenv(config.API_KEY_FILE_ENV, key_path)
    rendered = onboarding.client_config("codex")
    server = tomllib.loads(rendered)["mcp_servers"]["garmin"]
    assert server["command"] == interpreter
    assert server["env"][config.API_KEY_FILE_ENV] == key_path
    assert "\x7f" not in rendered
    assert "\\u007f" in rendered


@pytest.mark.parametrize("output_format", ["json", "vscode", "codex"])
@pytest.mark.parametrize("source", ["key-file", "interpreter"])
def test_client_config_rejects_unencodable_paths_safely(monkeypatch, output_format, source, capsys):
    if source == "key-file":
        monkeypatch.setenv(config.API_KEY_FILE_ENV, "/synthetic/undecodable-\udcff")
    else:
        monkeypatch.setattr(sys, "executable", "/synthetic/unpaired-surrogate-\ud800")
    run(monkeypatch, "client-config", "--format", output_format, code=1)
    captured = assert_private_output(capsys)
    assert not captured.out
    assert "UTF-8 paths" in captured.err
    assert "Traceback" not in captured.err
    assert "/synthetic/" not in captured.err
