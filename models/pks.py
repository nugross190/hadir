"""
models/pks.py
-------------
PKS (Patroli Keamanan Sekolah / Student Security Patrol) class assignments
and their attendance check records.

PKS users live in the regular Staff table with role='pks' — same login flow
as admin/headmaster. These tables only carry PKS-specific data:
which classes a PKS staff is assigned to, and the patrol checks they record.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Date, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class PKSClassAssignment(Base):
    """Which classes each PKS staff is responsible for patrolling."""
    __tablename__ = "pks_class_assignments"
    __table_args__ = (
        UniqueConstraint("staff_id", "class_id", name="uq_pks_class"),
    )

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)

    kelas = relationship("Class")

    def __repr__(self):
        return f"<PKSClassAssignment(staff_id={self.staff_id}, class_id={self.class_id})>"


class PKSAttendanceCheck(Base):
    """One patrol check per PKS staff per class per date."""
    __tablename__ = "pks_attendance_checks"
    __table_args__ = (
        UniqueConstraint("staff_id", "class_id", "check_date", name="uq_pks_check_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    check_date = Column(Date, nullable=False)
    checked_at = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=True)

    kelas = relationship("Class")
    student_checks = relationship("PKSStudentCheck", back_populates="attendance_check", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PKSAttendanceCheck(staff_id={self.staff_id}, class_id={self.class_id}, date={self.check_date})>"


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
