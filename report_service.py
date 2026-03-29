"""
services/report_service.py
---------------------------
Query logic for attendance reports.

4 report types:
  1. Teacher attendance summary (per teacher over date range)
  2. Student attendance summary (per class over date range)
  3. Staff accountability (recording sessions with timestamps)
  4. Daily recap (all classes for a single date)
"""

from datetime import date
from collections import defaultdict

from sqlalchemy import func, and_
from sqlalchemy.orm import Session, joinedload

from models import (
    Teacher, Class, Student, ScheduleSlot,
    AttendanceSession, TeacherAttendanceRecord,
    StudentAttendanceRecord, RecordingSession, Staff,
)


def teacher_attendance_summary(
    db: Session, date_from: date, date_to: date
) -> list[dict]:
    """
    Per teacher: how many sessions present/absent/late/sick/izin
    over the date range.
    """
    results = (
        db.query(
            Teacher.kode,
            Teacher.name,
            TeacherAttendanceRecord.status,
            func.count(TeacherAttendanceRecord.id).label("count"),
        )
        .join(ScheduleSlot, ScheduleSlot.teacher_id == Teacher.id)
        .join(AttendanceSession, AttendanceSession.schedule_slot_id == ScheduleSlot.id)
        .join(
            TeacherAttendanceRecord,
            TeacherAttendanceRecord.attendance_session_id == AttendanceSession.id,
        )
        .filter(
            AttendanceSession.date >= date_from,
            AttendanceSession.date <= date_to,
        )
        .group_by(Teacher.kode, Teacher.name, TeacherAttendanceRecord.status)
        .order_by(Teacher.kode)
        .all()
    )

    # Pivot: one row per teacher, columns for each status
    teacher_map = {}
    for kode, name, status, count in results:
        if kode not in teacher_map:
            teacher_map[kode] = {
                "kode": kode,
                "nama": name,
                "hadir": 0,
                "tidak_hadir": 0,
                "terlambat": 0,
                "sakit": 0,
                "izin": 0,
                "total": 0,
            }
        teacher_map[kode][status] = count
        teacher_map[kode]["total"] += count

    return sorted(teacher_map.values(), key=lambda t: t["kode"])


def student_attendance_summary(
    db: Session, class_id: int, date_from: date, date_to: date
) -> dict:
    """
    Per class: list of students with attendance counts.
    Returns class info + student rows.
    """
    kelas = db.query(Class).filter(Class.id == class_id).first()
    if not kelas:
        return {"class_name": "Unknown", "students": []}

    students = (
        db.query(Student)
        .filter(Student.class_id == class_id, Student.is_active == True)
        .order_by(Student.name)
        .all()
    )

    # Get all student attendance records for this class in date range
    records = (
        db.query(
            StudentAttendanceRecord.student_id,
            StudentAttendanceRecord.status,
            func.count(StudentAttendanceRecord.id).label("count"),
        )
        .join(
            AttendanceSession,
            AttendanceSession.id == StudentAttendanceRecord.attendance_session_id,
        )
        .join(ScheduleSlot, ScheduleSlot.id == AttendanceSession.schedule_slot_id)
        .filter(
            ScheduleSlot.class_id == class_id,
            AttendanceSession.date >= date_from,
            AttendanceSession.date <= date_to,
        )
        .group_by(StudentAttendanceRecord.student_id, StudentAttendanceRecord.status)
        .all()
    )

    # Build lookup: student_id -> {status: count}
    student_counts = defaultdict(lambda: {
        "hadir": 0, "tidak_hadir": 0, "sakit": 0, "izin": 0, "alpa": 0, "total": 0,
    })
    for student_id, status, count in records:
        student_counts[student_id][status] = count
        student_counts[student_id]["total"] += count

    student_rows = []
    for s in students:
        counts = student_counts.get(s.id, {
            "hadir": 0, "tidak_hadir": 0, "sakit": 0, "izin": 0, "alpa": 0, "total": 0,
        })
        student_rows.append({
            "nis": s.nis,
            "nama": s.name,
            "gender": s.gender,
            **counts,
        })

    return {
        "class_name": kelas.name,
        "grade_level": kelas.grade_level,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "students": student_rows,
    }


def staff_accountability_report(
    db: Session, date_from: date, date_to: date
) -> list[dict]:
    """
    Staff recording sessions: who recorded, when, TOTP verified,
    how many sessions per recording.
    """
    sessions = (
        db.query(RecordingSession)
        .join(Staff)
        .filter(
            func.date(RecordingSession.started_at) >= date_from,
            func.date(RecordingSession.started_at) <= date_to,
        )
        .options(joinedload(RecordingSession.staff))
        .order_by(RecordingSession.started_at)
        .all()
    )

    results = []
    for s in sessions:
        att_count = (
            db.query(func.count(AttendanceSession.id))
            .filter(AttendanceSession.recording_session_id == s.id)
            .scalar()
        )
        results.append({
            "staff_name": s.staff.name,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "totp_verified": s.totp_verified,
            "totp_code": s.totp_code_entered,
            "sessions_recorded": att_count,
        })

    return results


def daily_recap(db: Session, target_date: date) -> list[dict]:
    """
    All classes for a single date: class, period, teacher, teacher status,
    total students, absent count.
    """
    sessions = (
        db.query(AttendanceSession)
        .filter(AttendanceSession.date == target_date)
        .options(
            joinedload(AttendanceSession.schedule_slot)
            .joinedload(ScheduleSlot.teacher),
            joinedload(AttendanceSession.schedule_slot)
            .joinedload(ScheduleSlot.kelas),
            joinedload(AttendanceSession.teacher_record),
        )
        .all()
    )

    results = []
    for a in sessions:
        slot = a.schedule_slot
        # Count student statuses
        student_counts = (
            db.query(
                StudentAttendanceRecord.status,
                func.count(StudentAttendanceRecord.id),
            )
            .filter(StudentAttendanceRecord.attendance_session_id == a.id)
            .group_by(StudentAttendanceRecord.status)
            .all()
        )
        sc = {status: count for status, count in student_counts}
        total_students = sum(sc.values())

        results.append({
            "class_name": slot.kelas.name,
            "period": f"{slot.period_start}-{slot.period_end}",
            "teacher_name": slot.teacher.name,
            "teacher_kode": slot.teacher.kode,
            "subject": slot.subject,
            "teacher_status": a.teacher_record.status if a.teacher_record else None,
            "teacher_notes": a.teacher_record.notes if a.teacher_record else None,
            "total_students": total_students,
            "hadir": sc.get("hadir", 0),
            "tidak_hadir": sc.get("tidak_hadir", 0),
            "sakit": sc.get("sakit", 0),
            "izin": sc.get("izin", 0),
            "alpa": sc.get("alpa", 0),
        })

    results.sort(key=lambda r: (r["class_name"], r["period"]))
    return results
