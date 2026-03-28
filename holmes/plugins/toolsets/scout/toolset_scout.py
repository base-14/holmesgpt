import logging
import os
from typing import Any, ClassVar, Dict, Optional, Tuple, Type
from urllib.parse import urlparse

import requests as http_requests
from pydantic import Field

from holmes.core.tools import ToolsetTag
from holmes.plugins.toolsets.mcp.toolset_mcp import (
    MCPMode,
    RemoteMCPToolset,
)
from holmes.utils.pydantic_utils import ToolsetConfig

logger = logging.getLogger(__name__)


class ScoutConfig(ToolsetConfig):
    api_url: str = Field(
        title="API URL",
        description="Base14 Scout MCP endpoint URL",
        examples=["https://scout.example.com/mcp/v1"],
    )
    api_token: Optional[str] = Field(
        default=None,
        title="API Token",
        description="Pre-obtained Bearer token for authentication",
    )
    client_id: Optional[str] = Field(
        default=None,
        title="Client ID",
        description="Keycloak OAuth client ID for client_credentials grant",
    )
    client_secret: Optional[str] = Field(
        default=None,
        title="Client Secret",
        description="Keycloak OAuth client secret for client_credentials grant",
    )
    verify_ssl: bool = Field(
        default=True,
        title="Verify SSL",
        description="Whether to verify SSL certificates",
    )
    mode: MCPMode = Field(
        default=MCPMode.STREAMABLE_HTTP,
        title="MCP Mode",
        description="MCP connection mode (streamable-http recommended for Scout)",
    )


def _obtain_token_via_client_credentials(
    api_url: str, client_id: str, client_secret: str, verify_ssl: bool
) -> str:
    """Discover Keycloak token endpoint and obtain a JWT via client_credentials grant.

    1. GET the well-known OAuth metadata from Scout to find the Keycloak realm
    2. GET the OpenID configuration to find the token endpoint
    3. POST a client_credentials grant to obtain an access token
    """
    parsed = urlparse(api_url)
    well_known_path = f"/.well-known/oauth-protected-resource{parsed.path}"
    well_known_url = f"{parsed.scheme}://{parsed.netloc}{well_known_path}"

    logger.debug(f"Discovering Keycloak endpoint from {well_known_url}")
    resp = http_requests.get(well_known_url, verify=verify_ssl, timeout=10)
    resp.raise_for_status()
    metadata = resp.json()

    auth_servers = metadata.get("authorization_servers", [])
    if not auth_servers:
        raise ValueError(f"No authorization_servers found in well-known metadata at {well_known_url}")

    auth_server_url = auth_servers[0].rstrip("/")
    token_url = f"{auth_server_url}/protocol/openid-connect/token"

    logger.debug(f"Requesting token via client_credentials at {token_url}")
    token_resp = http_requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "openid profile email",
        },
        verify=verify_ssl,
        timeout=10,
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("Keycloak response did not contain an access_token")

    return access_token


class ScoutToolset(RemoteMCPToolset):
    config_classes: ClassVar[list[Type[ScoutConfig]]] = [ScoutConfig]

    def __init__(self):
        super().__init__(
            name="base14/scout",
            description="Base14 Scout observability platform - query services, traces, logs, metrics, and alerts",
            icon_url="https://scout.base14.io/favicon.ico",
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/base14-scout/",
            tags=[ToolsetTag.CORE],
            enabled=False,
        )
        self._load_llm_instructions_from_file(
            os.path.dirname(__file__), "toolset_scout.jinja2"
        )

    def prerequisites_callable(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            config = {}

        # Fall back to environment variables
        if not config.get("api_url"):
            env_url = os.environ.get("SCOUT_API_URL")
            if env_url:
                config["api_url"] = env_url
        if not config.get("api_token"):
            env_token = os.environ.get("SCOUT_API_TOKEN")
            if env_token:
                config["api_token"] = env_token
        if not config.get("client_id"):
            env_cid = os.environ.get("SCOUT_CLIENT_ID")
            if env_cid:
                config["client_id"] = env_cid
        if not config.get("client_secret"):
            env_csec = os.environ.get("SCOUT_CLIENT_SECRET")
            if env_csec:
                config["client_secret"] = env_csec

        # Validate config
        try:
            scout_config = ScoutConfig(**config)
        except Exception as e:
            return False, f"Invalid Scout config: {e}"

        # Resolve authentication to a Bearer token
        bearer_token: Optional[str] = None
        if scout_config.api_token:
            bearer_token = scout_config.api_token
        elif scout_config.client_id and scout_config.client_secret:
            try:
                bearer_token = _obtain_token_via_client_credentials(
                    api_url=scout_config.api_url,
                    client_id=scout_config.client_id,
                    client_secret=scout_config.client_secret,
                    verify_ssl=scout_config.verify_ssl,
                )
            except Exception as e:
                return False, f"Keycloak authentication failed: {e}"
        else:
            return False, "Scout requires either api_token or client_id/client_secret for authentication."

        # Build MCPConfig dict and delegate to parent for MCP session + tool discovery
        mcp_config = {
            "url": scout_config.api_url,
            "mode": scout_config.mode.value,
            "verify_ssl": scout_config.verify_ssl,
            "headers": {"Authorization": f"Bearer {bearer_token}"},
        }

        return super().prerequisites_callable(mcp_config)
