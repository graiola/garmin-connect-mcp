import os
from pathlib import Path
import pytest
from garmin_connect_mcp.config import Settings, read_secret, find_secret
from garmin_connect_mcp.cli import write_secret
from garmin_connect_mcp.errors import ConfigurationError


def test_secret_file_permissions_and_no_overwrite(tmp_path):
    p = tmp_path / "private" / "key"
    write_secret(p, "test-key")
    assert read_secret(p) == "test-key"
    if os.name == "posix":
        assert p.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_secret(p, "another")
    assert read_secret(p) == "test-key"


def test_secret_not_in_settings_repr(settings):
    assert settings.api_key not in repr(settings)
    assert settings.access_token not in repr(settings)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_world_readable_secret_refused(tmp_path):
    p = tmp_path / "key"
    p.write_text("test")
    p.chmod(0o644)
    with pytest.raises(ConfigurationError, match="chmod 600"):
        read_secret(p)


def test_explicit_file_not_silently_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "other-key")
    monkeypatch.setenv("TEST_KEY_FILE", str(tmp_path / "missing"))
    with pytest.raises(ConfigurationError):
        find_secret("TEST_KEY", "TEST_KEY_FILE", tmp_path / "default")


@pytest.mark.parametrize("kwargs", [{"api_key": ""}, {"api_key": "a b"}, {"api_key": "test", "access_token": "tiny"}, {"api_key": "test", "timezone": "bad/timezone"}, {"api_key": "test", "timeout_seconds": 0}])
def test_settings_validation(kwargs):
    with pytest.raises(ConfigurationError):
        Settings(**kwargs)
