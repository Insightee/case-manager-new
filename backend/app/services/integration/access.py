"""Case-grant and scope enforcement for integration principals."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.integration import IntegrationCaseGrant, IntegrationClient
from app.services.integration.errors import ForbiddenError, NotFoundError


@dataclass(frozen=True)
class IntegrationPrincipal:
    client: IntegrationClient
    credential_id: int
    public_client_id: str
    scopes: frozenset[str]

    @property
    def client_id(self) -> int:
        return self.client.id


def require_scope(principal: IntegrationPrincipal, scope: str) -> None:
    if scope not in principal.scopes:
        raise ForbiddenError(f"Missing required scope: {scope}")


def require_mcp(principal: IntegrationPrincipal) -> None:
    if not bool(getattr(principal.client, "mcp_enabled", True)):
        raise ForbiddenError("MCP is turned off for this key.")


def granted_case_ids(db: Session, principal: IntegrationPrincipal) -> set[int]:
    if principal.client.all_cases:
        rows = db.scalars(select(Case.id)).all()
        return set(int(x) for x in rows)
    rows = db.scalars(
        select(IntegrationCaseGrant.case_id).where(
            IntegrationCaseGrant.integration_client_id == principal.client_id
        )
    ).all()
    return set(int(x) for x in rows)


def require_case_grant(db: Session, principal: IntegrationPrincipal, case_id: int) -> None:
    if principal.client.all_cases:
        if db.get(Case, case_id) is None:
            raise NotFoundError("Case not found")
        return
    granted = db.scalars(
        select(IntegrationCaseGrant.id).where(
            IntegrationCaseGrant.integration_client_id == principal.client_id,
            IntegrationCaseGrant.case_id == case_id,
        )
    ).first()
    if not granted:
        # Hide existence of ungranted cases from external callers.
        raise NotFoundError("Case not found")


def filter_to_granted_cases(db: Session, principal: IntegrationPrincipal, case_ids: list[int] | None) -> set[int]:
    allowed = granted_case_ids(db, principal)
    if case_ids is None:
        return allowed
    requested = set(int(c) for c in case_ids)
    return allowed & requested
