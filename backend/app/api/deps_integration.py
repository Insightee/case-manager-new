"""Dependencies for integration Bearer JWT authentication."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.integration.access import IntegrationPrincipal
from app.services.integration.auth_service import ensure_integration_enabled, resolve_principal_from_token
from app.services.integration.errors import FeatureDisabledError, IntegrationError, UnauthorizedError
security = HTTPBearer(auto_error=False)


def raise_integration_http(exc: IntegrationError) -> None:
    raise HTTPException(
        status_code=exc.http_status,
        detail={"code": exc.code, "message": exc.message},
    )


def get_integration_principal(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> IntegrationPrincipal:
    try:
        ensure_integration_enabled()
        if not credentials:
            raise UnauthorizedError()
        return resolve_principal_from_token(db, credentials.credentials)
    except IntegrationError as exc:
        raise_integration_http(exc)
        raise  # pragma: no cover


def get_request_meta(request: Request) -> dict:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
