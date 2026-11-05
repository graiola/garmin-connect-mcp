"""No secrets in command arguments, no credentials sent to the model."""
from __future__ import annotations
import argparse
import asyncio
import getpass
import json
import logging
import os
from pathlib import Path
import secrets
import sys
from .client import GarminClient
from .config import DEFAULT_DIR, Settings, validate_secret
from .errors import ConfigurationError, ConnectorError
from .server import create_app, serve_stdio
from .tools import ToolService


def write_secret(path: Path, value: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        path.parent.chmod(0o700)
    # Refuse existing targets/symlinks rather than overwriting a possibly wrong secret.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(value + "\n")


def configure() -> None:
    if not sys.stdin.isatty():
        raise ConfigurationError("Run configure in your own interactive terminal; no secrets on stdin/pipes.")
    key_path = DEFAULT_DIR / "api-key"
    if key_path.exists():
        raise ConfigurationError("API-key file already exists; replace it locally in a secure editor, keeping permissions 600.")
    key = validate_secret(getpass.getpass("Garmin Personal API key (hidden): "))
    write_secret(key_path, key)
    token_path = DEFAULT_DIR / "http-token"
    if not token_path.exists():
        write_secret(token_path, secrets.token_urlsafe(48))
    print(f"Secrets saved outside the repository in {DEFAULT_DIR}. Values not printed.")


async def doctor(settings: Settings) -> None:
    client = GarminClient(settings)
    try:
        # A read probe only. Never print the user's activity list in diagnostics.
        await client.get("/activitylist-service/activities/search/activities", {"start": 0, "limit": 1})
        print(json.dumps({"garmin_authentication": "ok", "activities_read": "ok", "mcp_connection": "not_checked"}))
    finally:
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Garmin Personal API MCP connector.")
    parser.add_argument("command", nargs="?", choices=["stdio", "http", "configure", "doctor", "tools"], default="stdio")
    parser.add_argument("--port", type=int, default=8765, help="Loopback HTTP port only.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.ERROR)
    try:
        if args.command == "configure":
            configure()
            return
        if args.command == "tools":
            from .tools import TOOLS
            print(json.dumps([t.definition() for t in TOOLS], indent=2))
            return
        settings = Settings.load()
        if args.command == "doctor":
            asyncio.run(doctor(settings))
            return
        if args.command == "http":
            if not 1024 <= args.port <= 65535:
                raise ConfigurationError("Choose an unprivileged port between 1024 and 65535.")
            import uvicorn
            uvicorn.run(create_app(ToolService(GarminClient(settings))), host="127.0.0.1", port=args.port,
                        access_log=False, log_level="warning", proxy_headers=False)
        else:
            asyncio.run(serve_stdio(ToolService(GarminClient(settings))))
    except (ConnectorError, FileExistsError) as exc:
        message = str(exc) if isinstance(exc, ConnectorError) else "Secret file already exists; it was not overwritten."
        print(message, file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
