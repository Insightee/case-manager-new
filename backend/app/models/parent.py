from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

parent_child_link = Table(
    "parent_child_links",
    Base.metadata,
    Column("parent_guardian_id", Integer, ForeignKey("parent_guardians.id", ondelete="CASCADE"), primary_key=True),
    Column("child_id", Integer, ForeignKey("children.id", ondelete="CASCADE"), primary_key=True),
)


class ParentGuardian(Base):
    __tablename__ = "parent_guardians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="parent_profile")
    children = relationship("Child", secondary=parent_child_link)
