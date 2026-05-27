from __future__ import annotations

from typing import Optional

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Child(Base):
    __tablename__ = "children"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_client_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    date_of_birth: Mapped[Optional[date ]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cases = relationship("Case", back_populates="child")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
