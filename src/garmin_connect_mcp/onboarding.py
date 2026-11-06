"""User-run onboarding; credentials never enter client settings or diagnostics."""
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import tempfile
import warnings

from . import config
from .client import GarminClient
from .config import Settings, find_secret, validate_http_token, validate_secret, validate_timezone
from .errors import ConfigurationError


def _file_stamp(path: Path) -> tuple[int, ...] | None:
    """Inspect a managed target without following a symlink or reading its key."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise ConfigurationError("Managed secret target must be a regular file, not a symlink or directory.")
    if os.name == "posix" and info.st_mode & 0o077:
        raise ConfigurationError("Secret file permissions are too broad. Use chmod 600 locally.")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_mode


def _save_secret(path: Path, value: str, previous: tuple[int, ...] | None = None) -> None:
    value = validate_secret(value)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise ConfigurationError("Managed secret directory must not be a symlink.")
    if os.name == "posix":
        path.parent.chmod(0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            if os.name == "posix":
                os.fchmod(stream.fileno(), 0o600)
            stream.write(value + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if previous is None:
            # An exclusive link publishes the complete file without replacing an
            # existing key, including a target created while the probe was running.
            os.link(temporary_path, path)
        else:
            if _file_stamp(path) != previous:
                raise ConfigurationError("API-key file changed during setup; nothing was replaced. Try again locally.")
            os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_secret(path: Path, value: str) -> None:
    """Create a protected secret exclusively, preserving the legacy helper API."""
    _save_secret(path, value)


def _require_managed_key() -> Path:
    if config.API_KEY_FILE_ENV in os.environ or config.API_KEY_ENV in os.environ:
        raise ConfigurationError(
            "An API-key environment override is active. Update it in your secret manager, "
            "or unset both GARMIN_PERSONAL_API_KEY_FILE and GARMIN_PERSONAL_API_KEY "
            "in your own terminal before managing the default key file."
        )
    return config.DEFAULT_DIR / "api-key"


def prompt_api_key() -> str:
    if not sys.stdin.isatty():
        raise ConfigurationError("Enter the Garmin key only in your own interactive terminal; no secrets on stdin/pipes.")
    try:
        with warnings.catch_warnings():
            # getpass otherwise falls back to echoed input when terminal echo
            # control fails, even when stdin reported that it was a terminal.
            warnings.simplefilter("error", getpass.GetPassWarning)
            value = getpass.getpass("Garmin Personal API key (hidden): ")
    except (getpass.GetPassWarning, EOFError):
        raise ConfigurationError("Hidden key entry is unavailable. Run setup in your own interactive terminal.") from None
    return validate_secret(value)


def configure_http() -> None:
    """Create or reuse only the independently configured local HTTP bearer."""
    key = find_secret(config.API_KEY_ENV, config.API_KEY_FILE_ENV, config.DEFAULT_DIR / "api-key", required=False)
    token = find_secret(config.HTTP_TOKEN_ENV, config.HTTP_TOKEN_FILE_ENV, config.DEFAULT_DIR / "http-token", required=False)
    if token is not None:
        validate_http_token(token, key)
        return
    write_secret(config.DEFAULT_DIR / "http-token", validate_http_token(secrets.token_urlsafe(48), key))


def configure() -> None:
    """Legacy offline configuration, kept for existing manual workflows."""
    path = _require_managed_key()
    if _file_stamp(path) is not None:
        raise ConfigurationError("API-key file already exists. Use setup to check it or setup --replace-key to rotate it locally.")
    write_secret(path, prompt_api_key())
    configure_http()
    print(f"Secrets saved outside the repository in {config.DEFAULT_DIR}. Values not printed.")


async def check_connection(settings: Settings) -> dict[str, str]:
    client = GarminClient(settings)
    try:
        await client.get("/activitylist-service/activities/search/activities", {"start": 0, "limit": 1})
        return {"garmin_authentication": "ok", "activities_read": "ok", "mcp_connection": "not_checked"}
    finally:
        await client.aclose()


def _client_key_path() -> Path:
    if config.API_KEY_FILE_ENV in os.environ:
        value = os.environ[config.API_KEY_FILE_ENV]
        if not value:
            raise ConfigurationError("GARMIN_PERSONAL_API_KEY_FILE must identify your private key file.")
        try:
            return Path(value).expanduser().absolute()
        except (OSError, RuntimeError):
            raise ConfigurationError("Cannot determine the key-file path. Use an absolute path to your private key file.") from None
    if config.API_KEY_ENV in os.environ:
        raise ConfigurationError(
            "The API key is supplied only through an environment variable; it will not be copied into client settings. "
            "Configure that variable through your client's secret manager, or unset the API-key overrides "
            "and run setup in your own terminal to create the default private key file."
        )
    return (config.DEFAULT_DIR / "api-key").absolute()


def client_config(output_format: str = "json") -> str:
    """Render connection settings without reading credentials or contacting Garmin."""
    key_path = _client_key_path()
    timezone = validate_timezone(os.environ.get("GARMIN_MCP_TIMEZONE", "Europe/Rome"))
    if not sys.executable:
        raise ConfigurationError("Cannot determine Python's path. Run this command using the installed connector.")
    # Resolving a venv's Python symlink would select the base interpreter instead.
    command = str(Path(sys.executable).absolute())
    arguments = ["-m", "garmin_connect_mcp", "stdio"]
    environment = {config.API_KEY_FILE_ENV: str(key_path), "GARMIN_MCP_TIMEZONE": timezone}
    try:
        for value in (command, *environment.values()):
            value.encode("utf-8")
    except UnicodeEncodeError:
        raise ConfigurationError("Client settings require UTF-8 paths. Choose paths without undecodable filename bytes.") from None
    server = {"command": command, "args": arguments, "env": environment}
    if output_format == "json":
        return json.dumps({"mcpServers": {"garmin": server}}, indent=2, ensure_ascii=False)
    if output_format == "vscode":
        return json.dumps({"servers": {"garmin": {"type": "stdio", **server}}}, indent=2, ensure_ascii=False)
    if output_format == "codex":
        def quote(value):
            # JSON leaves DEL literal, but TOML forbids it. Keep non-BMP Unicode
            # literal: JSON's ASCII surrogate-pair escapes are not valid TOML.
            return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")
        return "\n".join([
            "[mcp_servers.garmin]", f"command = {quote(command)}", f"args = {quote(arguments)}", "",
            "[mcp_servers.garmin.env]", *(f"{name} = {quote(value)}" for name, value in environment.items()),
        ])
    raise ConfigurationError("Choose a client-config format: json, vscode, or codex.")


async def setup(*, replace_key: bool = False) -> None:
    previous = None
    if replace_key:
        path = _require_managed_key()
        previous = _file_stamp(path)
        if previous is None:
            raise ConfigurationError("No managed API-key file exists. Run setup without --replace-key first.")
        key = None
    else:
        key = find_secret(config.API_KEY_ENV, config.API_KEY_FILE_ENV, config.DEFAULT_DIR / "api-key", required=False)
        path = config.DEFAULT_DIR / "api-key"
    new_key = key is None
    timezone = validate_timezone(os.environ.get("GARMIN_MCP_TIMEZONE", "Europe/Rome"))
    if new_key:
        if not replace_key and _file_stamp(path) is not None:
            raise ConfigurationError("API-key file already exists; it was not overwritten.")
        key = prompt_api_key()
    print("Checking Garmin authentication and one activity read...", file=sys.stderr, flush=True)
    result = await check_connection(Settings(api_key=key, timezone=timezone))
    if new_key:
        _save_secret(path, key, previous)
    print(json.dumps(result), file=sys.stderr)
    if config.API_KEY_ENV in os.environ and config.API_KEY_FILE_ENV not in os.environ:
        print(
            "Garmin access checked using your environment key. No key file was created. "
            "Client settings were not generated: configure the same variable in your client's secret manager, "
            "or unset API-key overrides and run setup locally to store a private key file. "
            "Never paste the key into chat.", file=sys.stderr,
        )
        return
    print("Add these settings to your local MCP client, then verify a tool call. No client settings were changed.", file=sys.stderr)
    print(client_config())
