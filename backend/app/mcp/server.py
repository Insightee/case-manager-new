"""Remote MCP server (Streamable HTTP) for InsighteCase tools."""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.services.integration import facade
from app.services.integration.access import require_mcp
from app.services.integration.errors import IntegrationError

logger = logging.getLogger("insightcase.mcp")

_mcp_server = None
_mcp_asgi_app = None


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
    # Prefer request_context.request.headers — Context.headers raises when no active request.
    try:
        req = ctx.request_context.request
        headers = getattr(req, "headers", None)
    except Exception:
        headers = None
    if headers is None:
        try:
            # Only call the property if request_context is already available.
            rc = getattr(ctx, "_request_context", None)
            if rc is not None:
                headers = getattr(getattr(rc, "request", None), "headers", None)
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
    principal = facade.principal_from_bearer(token)
    require_mcp(principal)
    return principal


def build_mcp_server():
    """Construct MCPServer. Clinical tools stay read-only; profile create is scoped."""
    from mcp.server.mcpserver import Context, MCPServer

    server = MCPServer(
        name="InsighteCase",
        instructions=(
            "InsighteCase tools for an integration Bearer access token. "
            "Clinical tools are read-only and never complete a report or replace therapist notes. "
            "list_therapist_profiles needs profiles:read. "
            "create_therapist_profile needs profiles:write and an existing therapist user id."
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

    _run_list_authorised_reports.__globals__["Context"] = Context
    server.add_tool(
        _run_list_authorised_reports,
        name="list_authorised_reports",
        description="List reports for cases granted to this integration client.",
    )

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

    def _get_finance_receivables(billing_month: str, ctx: Context | None = None) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            return json.dumps(facade.get_finance_receivables(principal, billing_month))
        except Exception as exc:
            return mcp_public_error(exc)

    _get_finance_receivables.__globals__["Context"] = Context
    server.add_tool(
        _get_finance_receivables,
        name="get_finance_receivables",
        description=(
            "Client invoice totals for granted cases in YYYY-MM. "
            "Requires finance:read and case grants or all_cases. "
            "No child names. Refuses when the client has zero grants."
        ),
    )

    def _get_finance_ledger(billing_month: str, ctx: Context | None = None) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            return json.dumps(facade.get_finance_ledger(principal, billing_month))
        except Exception as exc:
            return mcp_public_error(exc)

    _get_finance_ledger.__globals__["Context"] = Context
    server.add_tool(
        _get_finance_ledger,
        name="get_finance_ledger",
        description=(
            "Billing ledger totals by status for granted cases in YYYY-MM. "
            "Requires finance:read and case grants or all_cases. "
            "No notes or child names. Refuses when the client has zero grants."
        ),
    )

    def _list_goal_framework(page: int = 1, page_size: int = 25, ctx: Context | None = None) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            return json.dumps(facade.list_goal_framework(principal, page=page, page_size=page_size))
        except Exception as exc:
            return mcp_public_error(exc)

    _list_goal_framework.__globals__["Context"] = Context
    server.add_tool(
        _list_goal_framework,
        name="list_goal_framework",
        description=(
            "Goal and strategy identifiers for granted cases, one page at a time. "
            "Strategy rows use linked_goal_card_id (an IEP card), not goals[].goal_id. "
            "Labels are short. No narratives."
        ),
    )

    def _list_iep_framework(page: int = 1, page_size: int = 25, ctx: Context | None = None) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            return json.dumps(facade.list_iep_framework(principal, page=page, page_size=page_size))
        except Exception as exc:
            return mcp_public_error(exc)

    _list_iep_framework.__globals__["Context"] = Context
    server.add_tool(
        _list_iep_framework,
        name="list_iep_framework",
        description="IEP framework identifiers and counts for granted cases, one page at a time. No plan text.",
    )

    def _list_therapist_profiles(
        page: int = 1,
        page_size: int = 25,
        status: str | None = None,
        q: str | None = None,
        ctx: Context | None = None,
    ) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            return json.dumps(
                facade.list_therapist_profiles(
                    principal,
                    page=page,
                    page_size=page_size,
                    status=status,
                    q=q,
                )
            )
        except Exception as exc:
            return mcp_public_error(exc)

    _list_therapist_profiles.__globals__["Context"] = Context
    server.add_tool(
        _list_therapist_profiles,
        name="list_therapist_profiles",
        description="List therapist website profiles: name, bio, qualifications, certificates, services, and status.",
    )

    def _create_therapist_profile(
        user_id: int,
        display_name: str = "",
        short_bio: str = "",
        academic_qualifications: str = "",
        professional_certificates: str = "",
        services_offered: str = "",
        status: str = "PENDING",
        ctx: Context | None = None,
    ) -> str:
        try:
            principal = _principal_from_ctx(ctx)
            payload: dict[str, Any] = {"user_id": user_id, "status": status or "PENDING"}
            if display_name:
                payload["display_name"] = display_name
            if short_bio:
                payload["short_bio"] = short_bio
            if academic_qualifications:
                payload["academic_qualifications"] = academic_qualifications
            certs = [part.strip() for part in (professional_certificates or "").split(",") if part.strip()]
            services = [part.strip() for part in (services_offered or "").split(",") if part.strip()]
            if certs:
                payload["professional_certificates"] = certs
            if services:
                payload["services_offered"] = services
            return json.dumps(facade.create_therapist_profile(principal, payload))
        except Exception as exc:
            return mcp_public_error(exc)

    _create_therapist_profile.__globals__["Context"] = Context
    server.add_tool(
        _create_therapist_profile,
        name="create_therapist_profile",
        description=(
            "Create a Pending website listing for an existing therapist user. "
            "Status is always Pending. A case manager approves it. "
            "Certificates and services are comma-separated. Does not edit clinical notes or revive a deleted listing."
        ),
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


def init_mcp(*, force_new: bool = False) -> tuple[Any, Any] | tuple[None, None]:
    """Build MCP server + Streamable HTTP ASGI app.

    host=0.0.0.0 avoids localhost-only DNS-rebinding locks so remote MCP clients
    can reach the mounted endpoint on Railway / public URLs.

    force_new=True rebuilds the ASGI app so StreamableHTTPSessionManager.run()
    can be entered again (TestClient / uvicorn --reload re-enter lifespan).
    """
    global _mcp_server, _mcp_asgi_app
    if not settings.mcp_enabled or not settings.integration_api_enabled:
        return None, None
    if not force_new and _mcp_asgi_app is not None and _mcp_server is not None:
        return _mcp_server, _mcp_asgi_app
    _mcp_server = build_mcp_server()
    _mcp_asgi_app = _mcp_server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        host="0.0.0.0",
    )
    return _mcp_server, _mcp_asgi_app


def remount_mcp(app: Any) -> Any | None:
    """Rebuild MCP ASGI app, replace `/mcp` mount, return a fresh session manager."""
    server, asgi = init_mcp(force_new=True)
    if server is None or asgi is None:
        return None
    router = getattr(app, "router", None)
    routes = getattr(router, "routes", None)
    if routes is not None:
        # Drop prior /mcp mounts so the live ASGI app matches this session manager.
        router.routes = [
            route
            for route in list(routes)
            if not (getattr(route, "path", None) == "/mcp" and type(route).__name__ == "Mount")
        ]
    app.mount("/mcp", asgi)
    return server.session_manager


def get_mcp_server():
    return _mcp_server


def get_mcp_asgi_app():
    """Lazy Streamable HTTP ASGI app mounted at /mcp when MCP_ENABLED."""
    _server, asgi = init_mcp()
    return asgi


def reset_mcp_for_tests() -> None:
    """Clear cached MCP instances between tests."""
    global _mcp_server, _mcp_asgi_app
    _mcp_server = None
    _mcp_asgi_app = None
