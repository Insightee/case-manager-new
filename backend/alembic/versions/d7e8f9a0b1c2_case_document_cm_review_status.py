"""Rename case document status SUPERVISOR_REVIEW to CM_REVIEW

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-05-25

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE case_documents SET status = 'CM_REVIEW' WHERE status = 'SUPERVISOR_REVIEW'"
    )
    op.execute(
        "UPDATE case_document_workflow_events SET from_status = 'CM_REVIEW' "
        "WHERE from_status = 'SUPERVISOR_REVIEW'"
    )
    op.execute(
        "UPDATE case_document_workflow_events SET to_status = 'CM_REVIEW' "
        "WHERE to_status = 'SUPERVISOR_REVIEW'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE case_documents SET status = 'SUPERVISOR_REVIEW' WHERE status = 'CM_REVIEW'"
    )
    op.execute(
        "UPDATE case_document_workflow_events SET from_status = 'SUPERVISOR_REVIEW' "
        "WHERE from_status = 'CM_REVIEW'"
    )
    op.execute(
        "UPDATE case_document_workflow_events SET to_status = 'SUPERVISOR_REVIEW' "
        "WHERE to_status = 'CM_REVIEW'"
    )
