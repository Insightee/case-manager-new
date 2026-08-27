"""Thin MCP adapter — translates tool calls into integration facade operations.

This package must not import SQLAlchemy Session or run queries directly.
"""
from __future__ import annotations

from app.mcp.server import build_mcp_server, get_mcp_asgi_app, mcp_public_error

__all__ = ["build_mcp_server", "get_mcp_asgi_app", "mcp_public_error"]
