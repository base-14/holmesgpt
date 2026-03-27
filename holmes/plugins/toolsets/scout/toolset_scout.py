import logging
import os
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type, Union
from urllib.parse import urlparse

import requests as http_requests
from pydantic import Field

from holmes.core.tools import (
    CallablePrerequisite,
    ToolsetTag,
)
from holmes.plugins.toolsets.mcp.toolset_mcp import (
    MCPConfig,
    MCPMode,
    RemoteMCPToolset,
)
from holmes.utils.pydantic_utils import ToolsetConfig

logger = logging.getLogger(__name__)

TOOLSET_CONFIG_MISSING_ERROR = "Scout config not provided. Set api_url and either api_token or username/password."


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
    username: Optional[str] = Field(
        default=None,
        title="Username",
        description="Keycloak username for OAuth authentication",
    )
    password: Optional[str] = Field(
        default=None,
        title="Password",
        description="Keycloak password for OAuth authentication",
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


def _discover_and_obtain_token(api_url: str, username: str, password: str, verify_ssl: bool) -> str:
    """Discover Keycloak endpoint from Scout's well-known URL and exchange credentials for a JWT.

    1. GET the well-known OAuth metadata from Scout
    2. Extract the authorization server (Keycloak token endpoint)
    3. POST a resource-owner password grant to obtain an access token
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

    logger.debug(f"Exchanging credentials at {token_url}")
    token_resp = http_requests.post(
        token_url,
        data={
            "grant_type": "password",
            "username": username,
            "password": password,
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
