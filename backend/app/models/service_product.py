from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ServiceProduct(Base):
    __tablename__ = "service_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_category_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("service_categories.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    billing_model: Mapped[str] = mapped_column(String(32), nullable=False, default="PER_SESSION")
    price_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    package_sessions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    discount_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    total_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    taxable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    gst_rate_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    gst_split: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    leave_policy: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    product_billing_rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_billing_rules.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category = relationship("ServiceCategory", back_populates="products")
