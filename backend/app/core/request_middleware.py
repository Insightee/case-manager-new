"""Request ID and safe access logging (no bodies or PHI)."""
from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_log = logging.getLogger("insightcase")
_request_counters: dict[str, int] = {}
_slow_requests = 0
_SLOW_MS = 1200


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = (request.headers.get("X-Request-ID") or "").strip() or str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        metric_key = f"{request.method} {request.url.path}"
        _request_counters[metric_key] = _request_counters.get(metric_key, 0) + 1
        global _slow_requests
        if duration_ms >= _SLOW_MS:
            _slow_requests += 1
            _log.warning(
                "slow_request method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                request_id,
            )
        _log.info(
            "request method=%s path=%s status=%s duration_ms=%.1f request_id=%s count=%s slow_total=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
            _request_counters[metric_key],
            _slow_requests,
        )
        response.headers["X-Request-ID"] = request_id
        return response
