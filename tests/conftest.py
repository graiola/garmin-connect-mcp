import base64
import json
import time
import pytest
from garmin_connect_mcp.config import Settings


def jwt(exp=None, suffix="signature"):
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp or time.time() + 86400}).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJSUzI1NiJ9.{payload}.{suffix}"


@pytest.fixture
def settings():
    return Settings(api_key="synthetic-test-key-not-real", access_token="a" * 48)
