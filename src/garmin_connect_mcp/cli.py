"""No secrets in command arguments, no credentials sent to the model."""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import sys
from . import __version__
from .client import GarminClient
from .config import Settings
from .errors import ConfigurationError, ConnectorError
from .onboarding import check_connection, client_config, configure, configure_http, setup, write_secret
from .server import create_app, serve_stdio
from .tools import ToolService


async def doctor(settings: Settings) -> None:
    print(json.dumps(await check_connection(settings)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Garmin Personal API MCP connector.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("command", nargs="?", choices=["stdio", "http", "setup", "client-config", "configure", "configure-http", "doctor", "tools"], default="stdio")
    parser.add_argument("--port", type=int, default=8765, help="Loopback HTTP port only.")
    parser.add_argument("--replace-key", action="store_true", help="For setup: check and atomically replace the default key file.")
    parser.add_argument("--format", choices=["json", "vscode", "codex"], default=None, help="For client-config: settings format (default: json).")
    args = parser.parse_args()
    if args.replace_key and args.command != "setup":
        parser.error("--replace-key is only available with setup.")
    if args.format is not None and args.command != "client-config":
        parser.error("--format is only available with client-config.")
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.ERROR)
    try:
        if args.command == "setup":
            asyncio.run(setup(replace_key=args.replace_key))
            return
        if args.command == "client-config":
            print(client_config(args.format or "json"))
            return
        if args.command == "configure":
            configure()
            return
        if args.command == "configure-http":
            configure_http()
            print("Local HTTP token ready. Secret values were not printed; no Garmin request was made.")
            return
        if args.command == "tools":
            from .tools import TOOLS
            print(json.dumps([t.definition() for t in TOOLS], indent=2))
            return
        settings = Settings.load(include_http=args.command == "http")
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
    except (ConnectorError, OSError) as exc:
        if isinstance(exc, ConnectorError):
            message = str(exc)
        elif isinstance(exc, FileExistsError):
            message = "Secret file already exists; it was not overwritten."
        else:
            message = "Cannot access local configuration safely. Check directory permissions in your own terminal."
        print(message, file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
