from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str
    role_names: list[str]
    region: Optional[str] = None
    module_assignments: list[str] = []


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    roles: list[str]
    region: Optional[str]
    module_assignments: list[str]

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    module_assignments: Optional[list[str]] = None
    region: Optional[str] = None
    is_active: Optional[bool] = None


class InviteCreate(BaseModel):
    email: EmailStr
    role_name: str
    module_assignments: list[str] = []
