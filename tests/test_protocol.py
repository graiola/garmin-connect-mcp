import json
import os
from pathlib import Path
import subprocess
import sys
import httpx
import pytest
from garmin_connect_mcp.client import GarminClient
from garmin_connect_mcp.protocol import Protocol
from garmin_connect_mcp.server import create_app
from garmin_connect_mcp.tools import ToolService
from garmin_connect_mcp.errors import ConfigurationError
from dataclasses import replace
from conftest import jwt


def rpc(method, params=None, id=1):
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def make_service(settings):
    return ToolService(GarminClient(settings, transport=httpx.MockTransport(
        lambda req: httpx.Response(200, text=jwt()) if req.method == "POST" else httpx.Response(200, json=[]))))


async def test_protocol_initialize_list_call(settings):
    service = make_service(settings)
    protocol = Protocol(service)
    result = await protocol.handle(rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}))
    assert result["result"]["protocolVersion"] == "2025-11-25"
    assert result["result"]["capabilities"] == {"tools": {"listChanged": False}}
    result = await protocol.handle(rpc("tools/list"))
    assert len(result["result"]["tools"]) == 6
    result = await protocol.handle(rpc("tools/call", {"name": "garmin_list_activities", "arguments": {"limit": 1}}))
    assert result["result"]["structuredContent"]["data"] == []
    assert json.loads(result["result"]["content"][0]["text"]) == result["result"]["structuredContent"]
    await service.client.aclose()


@pytest.mark.parametrize("message,code", [
    ([], -32600), (None, -32600), ({"jsonrpc": "2.0", "method": "ping", "id": True}, -32600),
    (rpc("unknown"), -32601), (rpc("tools/call", {"name": "invented"}), -32602),
    (rpc("tools/call", {"name": "garmin_get_activity", "arguments": {"activity_id": "SECRET"}}), -32602),
    (rpc("tools/list", {"cursor": "a"}), -32602), (rpc("initialize"), -32602),
])
async def test_protocol_errors(settings, message, code):
    service = make_service(settings)
    reply = await Protocol(service).handle(message)
    assert reply["error"]["code"] == code
    assert "SECRET" not in str(reply)
    await service.client.aclose()


async def test_notification_never_executes_tool(settings):
    service = make_service(settings)
    assert await Protocol(service).handle({"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "garmin_list_activities"}}) is None
    assert service.client._token is None
    await service.client.aclose()


async def test_tool_errors_not_protocol_errors(settings):
    client = GarminClient(settings, transport=httpx.MockTransport(lambda req: httpx.Response(403, text="SECRET")))
    result = await Protocol(ToolService(client)).handle(rpc("tools/call", {"name": "garmin_list_activities"}))
    assert result["result"]["isError"] is True
    assert "SECRET" not in str(result)
    await client.aclose()


async def test_http_transport_and_security(settings):
    service = make_service(settings)
    app = create_app(service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8765") as c:
        assert (await c.get("/healthz")).json()["upstream"] == "not_checked"
        assert (await c.post("/mcp", json=rpc("tools/list"))).status_code == 401
        auth = {"Authorization": "Bearer " + settings.access_token, "Accept": "application/json, text/event-stream"}
        assert (await c.post("/mcp", json=rpc("tools/list"), headers={**auth, "Origin": "https://evil.example"})).status_code == 403
        assert (await c.post("/mcp", json=rpc("tools/list"), headers={**auth, "Host": "evil.example"})).status_code == 400
        assert (await c.post("/mcp", json=rpc("tools/list"), headers={**auth, "MCP-Protocol-Version": "wrong"})).status_code == 400
        assert (await c.get("/mcp", headers=auth)).status_code == 405
        assert (await c.delete("/mcp", headers=auth)).status_code == 405
        assert (await c.post("/mcp", content="text", headers=auth)).status_code == 415
        bad_json = await c.post("/mcp", content="broken", headers={**auth, "Content-Type": "application/json"})
        assert bad_json.status_code == 400
        assert bad_json.json()["error"]["code"] == -32700
        assert (await c.post("/mcp", content="x" * 40000, headers={**auth, "Content-Type": "application/json"})).status_code == 413
        result = await c.post("/mcp", json=rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test"}}), headers=auth)
        assert result.status_code == 200
        assert "mcp-session-id" not in result.headers
        notification = await c.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=auth)
        assert notification.status_code == 202 and not notification.content
        tools = await c.post("/mcp", json=rpc("tools/list"), headers=auth)
        assert len(tools.json()["result"]["tools"]) == 6
        result = await c.post("/mcp", json=rpc("tools/call", {"name": "garmin_list_activities", "arguments": {"limit": 1}}), headers=auth)
        assert result.json()["result"]["structuredContent"]["data"] == []
    await service.client.aclose()


def test_http_requires_separate_secret(settings):
    service = make_service(replace(settings, access_token=None))
    with pytest.raises(ConfigurationError, match="separate access token"):
        create_app(service)


def test_stdio_subprocess():
    messages = [rpc("tools/list", id=0), rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test"}}, id=1),
                {"jsonrpc": "2.0", "method": "notifications/initialized"}, rpc("tools/list", id=2),
                rpc("tools/call", {"name": "garmin_connector_status"}, id=3)]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src"), "GARMIN_PERSONAL_API_KEY": "synthetic-key-for-test"}
    env.pop("GARMIN_PERSONAL_API_KEY_FILE", None)
    run = subprocess.run([sys.executable, "-m", "garmin_connect_mcp", "stdio"], input="".join(json.dumps(m) + "\n" for m in messages),
                         text=True, capture_output=True, env=env, timeout=15)
    assert run.returncode == 0, run.stderr
    replies = [json.loads(line) for line in run.stdout.splitlines()]
    assert len(replies) == 4
    assert replies[0]["error"]["code"] == -32000
    assert replies[1]["result"]["serverInfo"]["name"] == "garmin-connect-mcp"
    assert replies[-1]["result"]["structuredContent"]["data"]["read_only"] is True
    assert "synthetic-key-for-test" not in run.stdout + run.stderr
