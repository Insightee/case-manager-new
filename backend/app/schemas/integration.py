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
    scopes: Optional[list[str]] = None
    info_access: Optional[list[str]] = None
    allow_read: Optional[bool] = None
    allow_write: Optional[bool] = None
    case_ids: list[int] = Field(default_factory=list)
    all_cases: bool = False
    rate_limit_per_minute: Optional[int] = None
    access_token_minutes: Optional[int] = None
    key_ttl_days: Optional[int] = None
    mcp_enabled: Optional[bool] = None


class IntegrationClientUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    scopes: Optional[list[str]] = None
    info_access: Optional[list[str]] = None
    allow_read: Optional[bool] = None
    allow_write: Optional[bool] = None
    case_ids: Optional[list[int]] = None
    all_cases: Optional[bool] = None
    rate_limit_per_minute: Optional[int] = None
    access_token_minutes: Optional[int] = None
    key_ttl_days: Optional[int] = None
    mcp_enabled: Optional[bool] = None


class IntegrationSignalRead(BaseModel):
    id: int
    case_id: int
    domain: str
    signal_key: str
    level: Optional[int] = None
    status: str
    created_at: Optional[str] = None


class IntegrationClientRead(BaseModel):
    id: int
    name: str
    status: str
    scopes: list[str]
    allow_read: bool = False
    allow_write: bool = False
    info_access: list[str] = Field(default_factory=list)
    access_token_minutes: int = 15
    key_ttl_days: int = 365
    mcp_enabled: bool = True
    public_client_id: Optional[str] = None
    key_expires_at: Optional[str] = None
    all_cases: bool = False
    case_ids: list[int]
    granted_case_count: Optional[int] = None
    rate_limit_per_minute: int
    active_credential_count: int
    recent_signals: list[IntegrationSignalRead] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IntegrationClientCreated(IntegrationClientRead):
    client_id: str
    client_secret: str
    message: str = "Store the client_secret now; it will not be shown again."


class IntegrationSecretRotated(BaseModel):
    id: int
    client_id: str
    client_secret: str
    message: str = "Previous secrets were revoked. Store the new client_secret now."


class IntegrationErrorBody(BaseModel):
    code: str
    message: str
    detail: Optional[Any] = None


class IntegrationWebhookCreate(BaseModel):
    integration_client_id: int
    url: str = Field(min_length=8, max_length=512)
    events: list[str]


class IntegrationWebhookUpdate(BaseModel):
    url: Optional[str] = Field(default=None, min_length=8, max_length=512)
    events: Optional[list[str]] = None
    status: Optional[str] = None


class IntegrationWebhookRead(BaseModel):
    id: int
    integration_client_id: int
    client_name: str
    url: str
    events: list[str]
    status: str
    created_at: Optional[str] = None


class IntegrationWebhookCreated(IntegrationWebhookRead):
    signing_secret: str
    message: str = "Store the signing secret now; it will not be shown again."


class IntegrationSignalCreate(BaseModel):
    case_id: int
    domain: str
    signal_key: str
    level: Optional[int] = Field(default=None, ge=1, le=5)


class IntegrationTherapistProfileCreate(BaseModel):
    """Website listing fields only. Leave, TDS, review snapshots, and login email stay off the wire.

    New listings are always Pending. Any other status is refused.
    """

    user_id: int
    display_name: Optional[str] = Field(None, max_length=255)
    short_bio: Optional[str] = Field(None, max_length=2000)
    academic_qualifications: Optional[str] = Field(None, max_length=4000)
    professional_certificates: Optional[list[str]] = None
    services_offered: Optional[list[str]] = None
    status: Optional[str] = "PENDING"
