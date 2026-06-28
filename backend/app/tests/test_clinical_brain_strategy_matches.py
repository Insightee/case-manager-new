"""Strategy pool deterministic ranking."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.case import Case
from app.models.goal_repository import RepositoryItemStatus, StrategyRepositoryItem
from app.services import strategy_pool_matching_service as match_svc
from app.services.clinical_brain_metadata import dump_metadata


def test_strategy_pool_ranking_prefers_domain_match():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        from app.models.user import User

        admin = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        assert case and admin
        case_id = case.id
        domain = "communication_aac"
        a = StrategyRepositoryItem(
            case_id=None,
            created_by_user_id=admin.id,
            label="Domain match strategy",
            domain_key=domain,
            status=RepositoryItemStatus.APPROVED.value,
            scope="organization",
            metadata_json=dump_metadata({"support_need": "transitions"}),
        )
        b = StrategyRepositoryItem(
            case_id=None,
            created_by_user_id=admin.id,
            label="Other domain strategy",
            domain_key="peer_social",
            status=RepositoryItemStatus.APPROVED.value,
            scope="organization",
            metadata_json=dump_metadata({"support_need": "transitions"}),
        )
        db.add_all([a, b])
        db.commit()
        db.refresh(a)
        db.refresh(b)

        ranked = match_svc.match_strategy_pool(
            db, case_id, domain=domain, support_need="transitions", limit=50
        )
        ids = [row["id"] for row in ranked]
        assert ids.index(a.id) < ids.index(b.id)
