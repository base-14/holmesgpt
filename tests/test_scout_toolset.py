import pytest

from holmes.plugins.toolsets.scout.toolset_scout import ScoutConfig, ScoutToolset


class TestScoutConfig:
    def test_valid_config_with_token(self):
        config = ScoutConfig(
            api_url="https://scout.example.com/mcp/v1",
            api_token="test-token-123",
        )
        assert config.api_url == "https://scout.example.com/mcp/v1"
        assert config.api_token == "test-token-123"
        assert config.username is None
        assert config.password is None

    def test_valid_config_with_credentials(self):
        config = ScoutConfig(
            api_url="https://scout.example.com/mcp/v1",
            username="admin",
            password="secret",
        )
        assert config.username == "admin"
        assert config.password == "secret"
        assert config.api_token is None

    def test_api_url_required(self):
        with pytest.raises(Exception):
            ScoutConfig(api_token="test-token")

    def test_default_mode_is_streamable_http(self):
        config = ScoutConfig(
            api_url="https://scout.example.com/mcp/v1",
            api_token="token",
        )
        assert config.mode.value == "streamable-http"

    def test_verify_ssl_default_true(self):
        config = ScoutConfig(
            api_url="https://scout.example.com/mcp/v1",
            api_token="token",
        )
        assert config.verify_ssl is True


class TestScoutToolset:
    def test_toolset_name(self):
        toolset = ScoutToolset()
        assert toolset.name == "base14/scout"

    def test_toolset_disabled_by_default(self):
        toolset = ScoutToolset()
        assert toolset.enabled is False

    def test_prerequisites_fails_without_auth(self, monkeypatch):
        monkeypatch.delenv("SCOUT_API_TOKEN", raising=False)
        monkeypatch.delenv("SCOUT_USERNAME", raising=False)
        monkeypatch.delenv("SCOUT_PASSWORD", raising=False)
        toolset = ScoutToolset()
        ok, msg = toolset.prerequisites_callable({"api_url": "https://scout.example.com/mcp/v1"})
        assert ok is False
        assert "api_token" in msg or "username" in msg

    def test_prerequisites_fails_with_empty_config(self, monkeypatch):
        monkeypatch.delenv("SCOUT_API_URL", raising=False)
        monkeypatch.delenv("SCOUT_API_TOKEN", raising=False)
        monkeypatch.delenv("SCOUT_USERNAME", raising=False)
        monkeypatch.delenv("SCOUT_PASSWORD", raising=False)
        toolset = ScoutToolset()
        ok, msg = toolset.prerequisites_callable({})
        assert ok is False
