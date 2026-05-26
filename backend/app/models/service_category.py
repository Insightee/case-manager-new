from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    access_group: Mapped[str] = mapped_column(String(64), default="Clinical", nullable=False, server_default="Clinical")
    product_modules: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    products = relationship(
        "ServiceProduct",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="ServiceProduct.sort_order",
    )
