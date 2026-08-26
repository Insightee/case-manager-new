"""Remote MCP server (Streamable HTTP) for InsighteCase read-only tools."""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.services.integration import facade
from app.services.integration.errors import IntegrationError

logger = logging.getLogger("insightcase.mcp")


def mcp_public_error(exc: Exception) -> str:
    """Map exceptions to client-safe MCP error text (no DB / stack details)."""
    if isinstance(exc, IntegrationError):
        return json.dumps({"code": exc.code, "message": exc.message})
    logger.exception("Unexpected MCP tool error")
    return json.dumps({"code": "error", "message": "Request could not be completed"})


def _auth_header_from_ctx(ctx: Any) -> str | None:
    if ctx is None:
        return None
    headers = None
    if hasattr(ctx, "headers"):
        try:
            headers = ctx.headers
        except Exception:
            headers = None
    if headers is None:
        try:
            req = ctx.request_context.request
            headers = getattr(req, "headers", None)
        except Exception:
            headers = None
    if not headers:
        return None
    try:
        return headers.get("authorization") or headers.get("Authorization")
    except Exception:
        return None


def _principal_from_ctx(ctx: Any):
    token = facade.bearer_from_authorization_header(_auth_header_from_ctx(ctx))
    return facade.principal_from_bearer(token)


def build_mcp_server():
    """Construct MCPServer with read-only InsighteCase tools."""
    from mcp.server.mcpserver import Context, MCPServer

    server = MCPServer(
        name="InsighteCase",
        instructions=(
            "Read-only InsighteCase clinical operations tools. "
            "Requires an integration Bearer access token. "
            "Never exposes raw clinical notes, child PII, or write/approve actions."
        ),
    )

    def _run_list_authorised_reports(
        page: int = 1,
        page_size: int = 25,
        case_id: int | None = None,
        status: str | None = None,
        month: str | None = None,
        report_type: str = "all",
        ctx: Context | None = None,
    ) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            data = facade.list_authorised_reports(
                principal,
                page=page,
                page_size=page_size,
                case_id=case_id,
                status=status,
                month=month,
                report_type=report_type,
            )
            return json.dumps(data)
        except Exception as exc:
            return mcp_public_error(exc)

    # Bind annotations in function __globals__ for MCP signature evaluation.
    _run_list_authorised_reports.__globals__["Context"] = Context
    server.add_tool(_run_list_authorised_reports, name="list_authorised_reports")

    def _get_report(report_id: int, report_type: str = "monthly", ctx: Context | None = None) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            return json.dumps(facade.get_report(principal, report_id, report_type=report_type))
        except Exception as exc:
            return mcp_public_error(exc)

    _get_report.__globals__["Context"] = Context
    server.add_tool(
        _get_report,
        name="get_report",
        description="Read one authorised report (masked metadata and summary excerpt only).",
    )

    def _get_case_summary(case_id: int, ctx: Context | None = None) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            return json.dumps(facade.get_case_summary(principal, case_id))
        except Exception as exc:
            return mcp_public_error(exc)

    _get_case_summary.__globals__["Context"] = Context
    server.add_tool(_get_case_summary, name="get_case_summary", description="Masked case summary for a granted case.")

    def _get_session_summary(case_id: int, ctx: Context | None = None) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            return json.dumps(facade.get_session_summary(principal, case_id))
        except Exception as exc:
            return mcp_public_error(exc)

    _get_session_summary.__globals__["Context"] = Context
    server.add_tool(
        _get_session_summary,
        name="get_session_summary",
        description="Aggregated session/attendance counts for a granted case.",
    )

    def _list_pending_reporting(page: int = 1, page_size: int = 25, ctx: Context | None = None) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            return json.dumps(facade.list_pending_reporting(principal, page=page, page_size=page_size))
        except Exception as exc:
            return mcp_public_error(exc)

    _list_pending_reporting.__globals__["Context"] = Context
    server.add_tool(
        _list_pending_reporting,
        name="list_pending_reporting",
        description="Pending under-review and missing monthly reports for granted cases.",
    )

    def _get_anonymised_ops_summary(ctx: Context | None = None) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            return json.dumps(facade.get_anonymised_ops_summary(principal))
        except Exception as exc:
            return mcp_public_error(exc)

    _get_anonymised_ops_summary.__globals__["Context"] = Context
    server.add_tool(
        _get_anonymised_ops_summary,
        name="get_anonymised_ops_summary",
        description="Anonymised operational counts across granted cases (no names or identifiers).",
    )

    @server.resource("insightcase://cases/{case_id}/summary")
    def case_summary_resource(case_id: str) -> str:
        return json.dumps(
            {
                "code": "validation_error",
                "message": "Use the get_case_summary tool with an Authorization Bearer token.",
            }
        )

    @server.resource("insightcase://reports/{report_id}")
    def report_resource(report_id: str) -> str:
        return json.dumps(
            {
                "code": "validation_error",
                "message": "Use the get_report tool with an Authorization Bearer token.",
            }
        )

    return server


_mcp_asgi_app = None


def get_mcp_asgi_app():
    """Lazy Streamable HTTP ASGI app mounted at /mcp when MCP_ENABLED."""
    global _mcp_asgi_app
    if not settings.mcp_enabled or not settings.integration_api_enabled:
        return None
    if _mcp_asgi_app is None:
        server = build_mcp_server()
        _mcp_asgi_app = server.streamable_http_app(
            streamable_http_path="/",
            stateless_http=True,
            json_response=True,
        )
    return _mcp_asgi_app
