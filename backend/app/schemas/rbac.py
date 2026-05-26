from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModuleGrantEntry(BaseModel):
    enabled: bool = True
    access: str = "write"


class RbacPreviewRequest(BaseModel):
    role_names: List[str] = Field(default_factory=list)
    module_access_grants: Dict[str, Any] = Field(default_factory=dict)
    feature_overrides: Dict[str, Any] = Field(default_factory=dict)
    view_only: bool = False


class AccessConfig(BaseModel):
    """RBAC payload for user create, invite, and update."""

    module_assignments: List[str] = Field(default_factory=list)
    module_access_grants: Optional[Dict[str, Any]] = None
    feature_overrides: Optional[Dict[str, Any]] = None
    view_only: bool = False
