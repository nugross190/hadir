"""
models/__init__.py
------------------
Import all models here so that:
1. Base.metadata.create_all() finds every table
2. Other files can do: from models import Teacher, Class, Student, etc.
"""

from models.staff import Staff
from models.teacher import Teacher
from models.school import Class, Student
from models.schedule import ScheduleSlot
from models.attendance import (
    QRToken,
    RecordingSession,
    AttendanceSession,
    TeacherAttendanceRecord,
    StudentAttendanceRecord,
)

from models.approval import DailyApproval
from models.pks import PKSAccount, PKSClassAssignment, PKSAttendanceCheck, PKSStudentCheck

__all__ = [
    "Staff",
    "Teacher",
    "Class",
    "Student",
    "ScheduleSlot",
    "QRToken",
    "RecordingSession",
    "AttendanceSession",
    "TeacherAttendanceRecord",
    "StudentAttendanceRecord",
    "DailyApproval",
    "PKSAccount",
    "PKSClassAssignment",
    "PKSAttendanceCheck",
    "PKSStudentCheck",
]