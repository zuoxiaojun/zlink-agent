"""MCP server configuration schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    name: str
    transport: Literal["stdio", "http"] = "stdio"
    command: str | None = None
    args: list[str] = []
    url: str | None = None
    headers: dict[str, str] = {}
    env: dict[str, str] = {}
    enabled: bool = True
    timeout: int = Field(default=120, ge=10, le=600)


class MCPServerStatus(BaseModel):
    name: str
    transport: str
    enabled: bool
    builtin: bool = False
    status: Literal["connected", "disconnected", "error"]
    tool_count: int = 0
    error_message: str | None = None
    command: str | None = None
    args: list[str] = []
    url: str | None = None
    headers: dict[str, str] = {}
    env: dict[str, str] = {}
    timeout: int = 120


class MCPTestResult(BaseModel):
    success: bool
    tools_discovered: int = 0
    tool_names: list[str] = []
    error_message: str | None = None
