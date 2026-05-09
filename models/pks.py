"""
models/pks.py
-------------
PKS (Patroli Keamanan Sekolah / Student Security Patrol) accounts
and their weekly Monday attendance check records.

4 PKS groups, each responsible for 6 classes (3 from grade X, 3 from grade XI).
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Date, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class PKSAccount(Base):
    __tablename__ = "pks_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    pin_hash = Column(String(255), nullable=False)
    group_number = Column(Integer, nullable=False)  # 1–4
    is_active = Column(Boolean, default=True)

    assignments = relationship("PKSClassAssignment", back_populates="pks_account")
    checks = relationship("PKSAttendanceCheck", back_populates="pks_account")

    def __repr__(self):
        return f"<PKSAccount(username='{self.username}', group={self.group_number})>"


class PKSClassAssignment(Base):
    """Which classes each PKS group is responsible for patrolling."""
    __tablename__ = "pks_class_assignments"
    __table_args__ = (
        UniqueConstraint("pks_id", "class_id", name="uq_pks_class"),
    )

    id = Column(Integer, primary_key=True, index=True)
    pks_id = Column(Integer, ForeignKey("pks_accounts.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)

    pks_account = relationship("PKSAccount", back_populates="assignments")
    kelas = relationship("Class")

    def __repr__(self):
        return f"<PKSClassAssignment(pks_id={self.pks_id}, class_id={self.class_id})>"


class PKSAttendanceCheck(Base):
    """One patrol check per PKS group per class per date."""
    __tablename__ = "pks_attendance_checks"
    __table_args__ = (
        UniqueConstraint("pks_id", "class_id", "check_date", name="uq_pks_check_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    pks_id = Column(Integer, ForeignKey("pks_accounts.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    check_date = Column(Date, nullable=False)
    checked_at = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=True)

    pks_account = relationship("PKSAccount", back_populates="checks")
    kelas = relationship("Class")
    student_checks = relationship("PKSStudentCheck", back_populates="attendance_check", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PKSAttendanceCheck(pks_id={self.pks_id}, class_id={self.class_id}, date={self.check_date})>"


class PKSStudentCheck(Base):
    """Individual student status recorded during a PKS patrol check."""
    __tablename__ = "pks_student_checks"
    __table_args__ = (
        UniqueConstraint("check_id", "student_id", name="uq_pks_student_check"),
    )

    id = Column(Integer, primary_key=True, index=True)
    check_id = Column(Integer, ForeignKey("pks_attendance_checks.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    status = Column(String(20), nullable=False, default="hadir")  # hadir | tidak_hadir | izin | sakit | alpa
    notes = Column(String(200), nullable=True)

    attendance_check = relationship("PKSAttendanceCheck", back_populates="student_checks")
    student = relationship("Student")

    def __repr__(self):
        return f"<PKSStudentCheck(check_id={self.check_id}, student_id={self.student_id}, status='{self.status}')>"
