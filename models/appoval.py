"""
models/approval.py
------------------
Daily approval — headmaster (or owner) approves each admin
to work for one day. Without approval, admin cannot start
a recording session even with a valid TOTP.

One tap per admin per day. Valid from approval time until midnight.
"""

from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class DailyApproval(Base):
    __tablename__ = "daily_approvals"
    __table_args__ = (
        UniqueConstraint("staff_id", "date", name="uq_approval_staff_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    approved_by = Column(Integer, ForeignKey("staff.id"), nullable=True)  # NULL = owner
    approved_at = Column(DateTime, server_default=func.now())

    # Relationships
    staff = relationship("Staff", foreign_keys=[staff_id])
    approver = relationship("Staff", foreign_keys=[approved_by])

    def __repr__(self):
        return f"<DailyApproval(staff={self.staff_id}, date={self.date})>"
