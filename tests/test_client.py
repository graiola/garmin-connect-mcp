import asyncio
import json
import time
import httpx
import pytest
from garmin_connect_mcp.client import BASE_URL, TOKEN_PATH, GarminClient
from garmin_connect_mcp.errors import ConnectorError, UpstreamError
from conftest import jwt


async def test_exchange_raw_jwt_and_get_cache(settings):
    seen = []
    token = jwt()
    def handler(req):
        seen.append(req)
        assert str(req.url).startswith(BASE_URL)
        if req.url.path == TOKEN_PATH:
            assert req.method == "POST"
            assert req.headers["authorization"] == "ApiKey synthetic-test-key-not-real"
            return httpx.Response(200, text=token)
        assert req.method == "GET"
        assert req.headers["authorization"] == "Bearer " + token
        return httpx.Response(200, json={"data": [1]})
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    try:
        assert await client.get("/test") == {"data": [1]}
        assert await client.get("/test") == {"data": [1]}
        assert sum(r.method == "POST" for r in seen) == 1
    finally:
        await client.aclose()


@pytest.mark.parametrize("json_shape", ["string", "object"])
async def test_json_token_compatibility(settings, json_shape):
    token = jwt()
    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, json=token if json_shape == "string" else {"access_token": token})
        return httpx.Response(200, json=[])
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    assert await client.get("/test") == []
    await client.aclose()


async def test_concurrent_calls_exchange_once(settings):
    tokens = 0
    async def handler(req):
        nonlocal tokens
        if req.method == "POST":
            tokens += 1
            await asyncio.sleep(0.01)
            return httpx.Response(200, text=jwt())
        return httpx.Response(200, json={})
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    await asyncio.gather(*(client.get("/test") for _ in range(12)))
    assert tokens == 1
    await client.aclose()


async def test_early_refresh(settings):
    now = [time.time()]
    tokens = 0
    def handler(req):
        nonlocal tokens
        if req.method == "POST":
            tokens += 1
            return httpx.Response(200, text=jwt(now[0] + 86400, str(tokens)))
        return httpx.Response(200, json={})
    client = GarminClient(settings, transport=httpx.MockTransport(handler), clock=lambda: now[0])
    await client.get("/test")
    now[0] += 86400 - 100
    await client.get("/test")
    assert tokens == 2
    await client.aclose()


async def test_401_refresh_once(settings):
    tokens = 0
    reads = 0
    def handler(req):
        nonlocal tokens, reads
        if req.method == "POST":
            tokens += 1
            return httpx.Response(200, text=jwt(suffix=str(tokens)))
        reads += 1
        return httpx.Response(401, text="private upstream detail") if reads == 1 else httpx.Response(200, json={"ok": True})
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    assert await client.get("/test") == {"ok": True}
    assert tokens == 2
    assert reads == 2
    await client.aclose()


async def test_persistent_401_is_bounded(settings):
    count = 0
    def handler(req):
        nonlocal count
        count += 1
        return httpx.Response(200, text=jwt(suffix=str(count))) if req.method == "POST" else httpx.Response(401, text="SECRET")
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(UpstreamError) as caught:
        await client.get("/test")
    assert count == 4
    assert "SECRET" not in str(caught.value)
    await client.aclose()


@pytest.mark.parametrize("status", [403, 404, 500, 302])
async def test_upstream_status_sanitized(settings, status):
    def handler(req):
        return httpx.Response(200, text=jwt()) if req.method == "POST" else httpx.Response(status, text="PRIVATE_TOKEN", headers={"location": "https://evil.example"})
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(UpstreamError) as caught:
        await client.get("/test")
    assert caught.value.status == status
    assert "PRIVATE_TOKEN" not in str(caught.value)
    await client.aclose()


async def test_rate_retry_bounded(settings):
    reads, delays = [], []
    async def sleep(delay):
        delays.append(delay)
    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, text=jwt())
        reads.append(req)
        return httpx.Response(429, headers={"retry-after": "2"})
    client = GarminClient(settings, transport=httpx.MockTransport(handler), sleep=sleep)
    with pytest.raises(UpstreamError):
        await client.get("/test")
    assert len(reads) == 2 and delays == [2.0]
    await client.aclose()


@pytest.mark.parametrize("retry_after", ["99", "NaN", "Wed, 01 Jan 2030 00:00:00 GMT", "-5"])
async def test_no_early_retry_for_long_unknown_delay(settings, retry_after):
    reads = []
    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, text=jwt())
        reads.append(req)
        return httpx.Response(429, headers={"retry-after": retry_after})
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(UpstreamError):
        await client.get("/test")
    assert len(reads) == 1
    await client.aclose()


@pytest.mark.parametrize("body", ["not-a-jwt", "{}", '"broken"', "a.b.c"])
async def test_bad_token_response(settings, body):
    client = GarminClient(settings, transport=httpx.MockTransport(lambda req: httpx.Response(200, text=body)))
    with pytest.raises(ConnectorError):
        await client.get("/test")
    await client.aclose()


async def test_response_size_limit(settings):
    from dataclasses import replace
    small = replace(settings, max_response_bytes=1024)
    client = GarminClient(small, transport=httpx.MockTransport(
        lambda req: httpx.Response(200, text=jwt() if req.method == "POST" else "x" * 1025)))
    with pytest.raises(ConnectorError, match="too large"):
        await client.get("/test")
    await client.aclose()


async def test_network_error_sanitized(settings):
    def handler(req):
        raise httpx.ConnectError("SECRET in remote error")
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(ConnectorError) as caught:
        await client.get("/test")
    assert "SECRET" not in str(caught.value)
    await client.aclose()


@pytest.mark.parametrize("path", ["//evil.example/x", "https://evil.example/x", "/../x"])
async def test_no_arbitrary_remote_urls(settings, path):
    client = GarminClient(settings, transport=httpx.MockTransport(lambda req: httpx.Response(200, text=jwt())))
    with pytest.raises(ConnectorError, match="Invalid internal"):
        await client.get(path)
    await client.aclose()


async def test_no_data_write(settings):
    client = GarminClient(settings)
    with pytest.raises(ConnectorError, match="writes are disabled"):
        await client._request("POST", "/activity-service/activity/1", "Bearer synthetic")
    await client.aclose()


@pytest.mark.parametrize("body", ['{"a": NaN}', "<html>error</html>"])
async def test_invalid_json_data(settings, body):
    client = GarminClient(settings, transport=httpx.MockTransport(
        lambda req: httpx.Response(200, text=jwt() if req.method == "POST" else body)))
    with pytest.raises(ConnectorError, match="non-JSON"):
        await client.get("/test")
    await client.aclose()
