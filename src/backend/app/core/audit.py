"""
Audit logging for state-changing operations.

Each audit record captures: who, what, on which resource, when, outcome, and
the request ID for correlation. Stored in the audit_logs table.

Usage::

    audit_logger = AuditLogger()
    audit_logger.log(db, user_id=user.id, action="work_order.create",
                     resource_type="work_order", resource_id=str(wo.id),
                     request_id=rid, outcome="success")
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuditLog(Base):
    """Immutable audit trail of all state-changing operations."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(200))
    request_id: Mapped[str | None] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    detail: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class AuditLogger:
    """Thin wrapper for writing audit log entries."""

    def log(
        self,
        db: Session,
        *,
        action: str,
        user_id: int | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request_id: str | None = None,
        outcome: str = "success",
        detail: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Write one audit log entry.

        Errors are caught and logged (not re-raised) so audit failures
        never block the primary operation.
        """
        try:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                request_id=request_id,
                outcome=outcome,
                detail=detail,
                ip_address=ip_address,
            )
            db.add(entry)
            db.flush()
            logger.debug(
                "audit_log",
                action=action,
                user_id=user_id,
                resource_id=resource_id,
                outcome=outcome,
            )
        except Exception as exc:
            logger.error("audit_log_failed", action=action, exc_info=exc)
