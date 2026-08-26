"""Pydantic schemas for the external integration API."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class IntegrationTokenRequest(BaseModel):
    grant_type: str = "client_credentials"
    client_id: str
    client_secret: str


class IntegrationTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str


class IntegrationClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scopes: list[str]
    case_ids: list[int] = Field(default_factory=list)
    rate_limit_per_minute: Optional[int] = None


class IntegrationClientUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    scopes: Optional[list[str]] = None
    case_ids: Optional[list[int]] = None
    rate_limit_per_minute: Optional[int] = None


class IntegrationClientCreated(BaseModel):
    id: int
    name: str
    status: str
    scopes: list[str]
    case_ids: list[int]
    rate_limit_per_minute: int
    client_id: str
    client_secret: str
    message: str = "Store the client_secret now; it will not be shown again."


class IntegrationClientRead(BaseModel):
    id: int
    name: str
    status: str
    scopes: list[str]
    case_ids: list[int]
    rate_limit_per_minute: int
    active_credential_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IntegrationSecretRotated(BaseModel):
    id: int
    client_id: str
    client_secret: str
    message: str = "Previous secrets were revoked. Store the new client_secret now."


class IntegrationErrorBody(BaseModel):
    code: str
    message: str
    detail: Optional[Any] = None
