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
