from __future__ import annotations

import enum
from typing import Optional

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.role import user_roles


class EmploymentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        Enum(EmploymentStatus), default=EmploymentStatus.ACTIVE, nullable=False
    )
    location: Mapped[Optional[str]] = mapped_column(String(255))
    home_address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    home_address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    home_city: Mapped[Optional[str]] = mapped_column(String(128))
    home_state: Mapped[Optional[str]] = mapped_column(String(128))
    home_pincode: Mapped[Optional[str]] = mapped_column(String(16))
    home_landmark: Mapped[Optional[str]] = mapped_column(String(255))
    home_latitude: Mapped[Optional[float]] = mapped_column(Float)
    home_longitude: Mapped[Optional[float]] = mapped_column(Float)
    region: Mapped[Optional[str]] = mapped_column(String(64))
    avatar_path: Mapped[Optional[str]] = mapped_column(String(512))
    module_assignments: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    roles = relationship("Role", secondary=user_roles, back_populates="users")
    parent_profile = relationship("ParentGuardian", back_populates="user", uselist=False)

    @property
    def role_names(self) -> list[str]:
        return [r.name for r in self.roles]

    @property
    def permission_names(self) -> set[str]:
        perms: set[str] = set()
        for role in self.roles:
            for perm in role.permissions:
                perms.add(perm.name)
        return perms


class InviteToken(Base):
    __tablename__ = "invite_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_name: Mapped[str] = mapped_column(String(64), nullable=False)
    module_assignments: Mapped[Optional[list ]] = mapped_column(JSON, default=list)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime ]] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[Optional[int ]] = mapped_column(ForeignKey("users.id"))
    linked_child_id: Mapped[Optional[int]] = mapped_column(ForeignKey("children.id"), nullable=True)
    invite_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
