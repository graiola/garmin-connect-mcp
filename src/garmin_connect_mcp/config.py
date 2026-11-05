"""Secret discovery without command-line secrets or implicit dotenv loading."""
from __future__ import annotations
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .errors import ConfigurationError

DEFAULT_DIR = Path.home() / ".config" / "garmin-connect-mcp"


def read_secret(path: Path) -> str:
    path = path.expanduser()
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 16384:
            raise ConfigurationError("Secret file must be a small regular file.")
        if os.name == "posix" and info.st_mode & 0o077:
            raise ConfigurationError("Secret file permissions are too broad. Use chmod 600 locally.")
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise ConfigurationError("Cannot read the configured secret file.") from None
    return validate_secret(value)


def validate_secret(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 16384 or any(c.isspace() for c in value):
        raise ConfigurationError("Secret must be non-empty and contain no whitespace.")
    return value


def find_secret(env_name: str, file_env: str, default: Path, *, required: bool = True) -> str | None:
    if file_env in os.environ:
        return read_secret(Path(os.environ[file_env]))
    if env_name in os.environ:
        return validate_secret(os.environ[env_name])
    if default.exists():
        return read_secret(default)
    if required:
        raise ConfigurationError("Garmin API key missing. Run garmin-connect-mcp configure locally.")
    return None


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    access_token: str | None = field(default=None, repr=False)
    timezone: str = "Europe/Rome"
    timeout_seconds: float = 20.0
    max_response_bytes: int = 2 * 1024 * 1024

    def __post_init__(self) -> None:
        validate_secret(self.api_key)
        if self.access_token is not None:
            validate_secret(self.access_token)
            if len(self.access_token) < 32:
                raise ConfigurationError("HTTP access token must contain at least 32 characters.")
            if self.access_token == self.api_key:
                raise ConfigurationError("The HTTP token must be different from the Garmin API key.")
        if not 0 < self.timeout_seconds <= 60:
            raise ConfigurationError("Timeout must be between 0 and 60 seconds.")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ConfigurationError("Unknown timezone; use an IANA timezone such as Europe/Rome.") from None

    @classmethod
    def load(cls) -> Settings:
        return cls(
            api_key=find_secret("GARMIN_PERSONAL_API_KEY", "GARMIN_PERSONAL_API_KEY_FILE", DEFAULT_DIR / "api-key"),
            access_token=find_secret("GARMIN_MCP_ACCESS_TOKEN", "GARMIN_MCP_ACCESS_TOKEN_FILE", DEFAULT_DIR / "http-token", required=False),
            timezone=os.environ.get("GARMIN_MCP_TIMEZONE", "Europe/Rome"),
        )
