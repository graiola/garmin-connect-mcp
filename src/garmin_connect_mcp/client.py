"""Bounded HTTPS requests to Garmin's official Personal API only.

Endpoint contract: Garmin's official connect-personal-api-python client,
commit ac111a0ff8e37dfbc24c616fcc27691520c7278b (see docs/API_CONTRACT.md).
The token endpoint returns a raw JWT, not necessarily OAuth JSON.
"""
from __future__ import annotations
import asyncio
import base64
import json
import math
import time
from collections.abc import Awaitable, Callable
import httpx
from .config import Settings
from .errors import ConnectorError, UpstreamError

BASE_URL = "https://personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"


class GarminClient:
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None,
                 clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.settings = settings
        self._http = httpx.AsyncClient(
            base_url=BASE_URL, timeout=settings.timeout_seconds,
            follow_redirects=False, trust_env=False, transport=transport,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
        )
        self._clock, self._sleep = clock, sleep
        self._token: str | None = None
        self._expires_at = 0.0
        self._auth_lock = asyncio.Lock()
        self._requests = asyncio.Semaphore(4)

    async def aclose(self) -> None:
        self._token = None
        await self._http.aclose()

    async def _request(self, method: str, path: str, authorization: str,
                       params: dict | None = None) -> tuple[int, bytes, httpx.Headers]:
        # No redirects, arbitrary hosts, arbitrary methods or general proxy tool.
        if not path.startswith("/") or path.startswith("//") or ":" in path or ".." in path:
            raise ConnectorError("Invalid internal API path.")
        if method not in {"GET", "POST"} or (method == "POST" and path != TOKEN_PATH):
            raise ConnectorError("Garmin writes are disabled.")
        try:
            async with self._requests, self._http.stream(
                method, path, params=params,
                headers={"Authorization": authorization, "Accept": "*/*" if method == "POST" else "application/json"},
            ) as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self.settings.max_response_bytes:
                        raise ConnectorError("Garmin response too large. Request fewer activities or a shorter date range.")
                return response.status_code, bytes(body), response.headers
        except httpx.HTTPError:
            raise ConnectorError("Cannot reach Garmin securely. Check the network and retry.") from None

    async def _access_token(self, rejected: str | None = None) -> str:
        async with self._auth_lock:
            if (self._token is not None and self._token != rejected
                    and self._expires_at > self._clock() + 300):
                return self._token
            status, body, _ = await self._request("POST", TOKEN_PATH, f"ApiKey {self.settings.api_key}")
            if not 200 <= status < 300:
                raise UpstreamError(status)
            try:
                token = body.decode("utf-8").strip()
                # Official API returns raw JWT. Accept a JSON string/object for compatibility.
                if token.startswith(('"', '{')):
                    value = json.loads(token)
                    token = value if isinstance(value, str) else value["access_token"]
                if not isinstance(token, str) or any(c.isspace() for c in token):
                    raise ValueError
                encoded = token.split(".")[1]
                claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
                expiry = float(claims["exp"])
                if not math.isfinite(expiry) or expiry <= self._clock() + 5:
                    raise ValueError
            except (UnicodeError, ValueError, TypeError, KeyError, IndexError):
                raise ConnectorError("Garmin token response has an invalid or expired format.") from None
            # exp is used ONLY for cache scheduling. TLS authenticates Garmin;
            # this is NOT JWT validation for incoming MCP authorization.
            self._token, self._expires_at = token, expiry
            return token

    async def get(self, path: str, params: dict | None = None) -> object:
        token = await self._access_token()
        refreshed = False
        retried = False
        for _ in range(3):
            status, body, headers = await self._request("GET", path, f"Bearer {token}", params)
            if status == 401 and not refreshed:
                token = await self._access_token(rejected=token)
                refreshed = True
                continue
            if status in {429, 502, 503, 504} and not retried:
                try:
                    delay = float(headers.get("retry-after", "1"))
                except ValueError:
                    delay = 999.0  # Date-shaped/unknown Retry-After: fail rather than retry early.
                if math.isfinite(delay) and 0 <= delay <= 5:
                    retried = True
                    await self._sleep(max(delay, 0.1))
                    continue
            if not 200 <= status < 300:
                raise UpstreamError(status)
            if not body:
                return None
            try:
                return json.loads(body, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError, UnicodeError):
                raise ConnectorError("Garmin returned a non-JSON data response.") from None
        raise ConnectorError("Garmin did not recover after the bounded retries.")
