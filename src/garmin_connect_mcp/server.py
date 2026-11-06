"""Private transports: stdio or bearer-protected loopback HTTP.

Use stdio through Secure MCP Tunnel for ChatGPT. Public unauthenticated hosting
and OAuth server implementations are intentionally not part of this project.
"""
from __future__ import annotations
import asyncio
import json
import secrets
import sys
from contextlib import asynccontextmanager
from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from .errors import ConfigurationError
from .protocol import MAX_REQUEST_BYTES, VERSIONS, Protocol, error, loads
from .tools import ToolService


async def serve_stdio(service: ToolService) -> None:
    protocol = Protocol(service)
    initialized = False
    try:
        while True:
            raw = await asyncio.to_thread(sys.stdin.buffer.readline, MAX_REQUEST_BYTES + 1)
            if not raw:
                break
            if len(raw) > MAX_REQUEST_BYTES:
                # Oversized input closes the channel; don't parse fragments as new messages.
                reply = error(None, -32600, "Request exceeds the size limit; restart the client.")
                sys.stdout.write(json.dumps(reply) + "\n")
                sys.stdout.flush()
                break
            try:
                message = loads(raw)
            except (ValueError, UnicodeError):
                reply = error(None, -32700, "Invalid JSON.")
            else:
                if isinstance(message, dict) and message.get("method") not in {"initialize", "ping"} and not initialized and "id" in message:
                    reply = error(message.get("id"), -32000, "Initialize the MCP connection first.")
                else:
                    reply = await protocol.handle(message)
                    if isinstance(message, dict) and message.get("method") == "initialize" and reply and "result" in reply:
                        initialized = True
            if reply is not None:
                sys.stdout.write(json.dumps(reply, ensure_ascii=False, allow_nan=False) + "\n")
                sys.stdout.flush()
    finally:
        await service.client.aclose()


def create_app(service: ToolService) -> Starlette:
    token = service.client.settings.access_token
    if token is None:
        raise ConfigurationError("Local HTTP requires a separate access token. Run garmin-connect-mcp configure-http first, or use stdio.")
    protocol = Protocol(service)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await service.client.aclose()

    async def health(request: Request):
        return JSONResponse({"status": "ok", "upstream": "not_checked"}, headers={"Cache-Control": "no-store"})

    async def endpoint(request: Request):
        headers = {"Cache-Control": "no-store"}
        # Refuse browser origins entirely: this is a private machine-to-machine endpoint.
        if request.headers.get("origin") is not None:
            return JSONResponse({"error": "Browser origins are not permitted."}, status_code=403, headers=headers)
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(supplied.encode(), ("Bearer " + token).encode()):
            return JSONResponse({"error": "Unauthorized."}, status_code=401,
                                headers={**headers, "WWW-Authenticate": 'Bearer realm="garmin-connect-mcp"'})
        if request.method != "POST":
            return Response(status_code=405, headers={**headers, "Allow": "POST"})
        if request.headers.get("content-type", "").split(";")[0].lower() != "application/json":
            return Response(status_code=415, headers=headers)
        accept = request.headers.get("accept", "")
        if "application/json" not in accept and "*/*" not in accept:
            return Response(status_code=406, headers=headers)
        version = request.headers.get("mcp-protocol-version", "2025-03-26")
        if version not in VERSIONS:
            return JSONResponse({"error": "Unsupported MCP-Protocol-Version."}, status_code=400, headers=headers)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_REQUEST_BYTES:
                return Response(status_code=413, headers=headers)
        try:
            message = loads(bytes(raw))
        except (ValueError, UnicodeError):
            return JSONResponse(error(None, -32700, "Invalid JSON."), status_code=400, headers=headers)
        reply = await protocol.handle(message)
        # Stateless MCP does not issue MCP-Session-Id. No GET/SSE stream is required.
        if reply is None:
            return Response(status_code=202, headers=headers)
        return JSONResponse(reply, headers=headers)

    app = Starlette(routes=[Route("/healthz", health),
                            Route("/mcp", endpoint, methods=["POST", "GET", "DELETE"])], lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])
    return app
