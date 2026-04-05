"""
routers/dashboard.py
--------------------
JSON endpoints for the dashboard UI.

GET /dashboard/summary?date=2026-03-28          → today's snapshot
GET /dashboard/teacher-stats?from=...&to=...    → teacher attendance rates
GET /dashboard/class-stats?date=2026-03-28      → per-class breakdown
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import (
    Teacher, Class, Student, Staff,
    RecordingSession, AttendanceSession,
    TeacherAttendanceRecord, StudentAttendanceRecord,
    ScheduleSlot,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(
    target_date: date = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
):
    """
    Main dashboard snapshot: counts + today's attendance overview.
    """
    if target_date is None:
        target_date = date.today()

    # Entity counts
    total_teachers = db.query(Teacher).count()
    total_classes = db.query(Class).filter(Class.is_active == True).count()
    total_students = db.query(Student).count()
    total_staff = db.query(Staff).count()

    # Today's attendance sessions
    sessions_today = (
        db.query(AttendanceSession)
        .filter(AttendanceSession.date == target_date)
        .all()
    )

    # Teacher attendance breakdown for the day
    teacher_records = (
        db.query(TeacherAttendanceRecord)
        .join(AttendanceSession)
        .filter(AttendanceSession.date == target_date)
        .all()
    )

    teacher_status_counts = {}
    for r in teacher_records:
        teacher_status_counts[r.status] = teacher_status_counts.get(r.status, 0) + 1

    # Student attendance breakdown for the day
    student_records = (
        db.query(StudentAttendanceRecord)
        .join(AttendanceSession)
        .filter(AttendanceSession.date == target_date)
        .all()
    )

    student_status_counts = {}
    for r in student_records:
        student_status_counts[r.status] = student_status_counts.get(r.status, 0) + 1

    # Recording sessions (staff activity) today
    rec_sessions = (
        db.query(RecordingSession)
        .filter(func.date(RecordingSession.started_at) == target_date)
        .all()
    )

    # How many schedule slots exist for this day of week (excluding grade 12)
    day_names = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
    dow = day_names[target_date.weekday()]  # Monday=0 → 'Senin'
    total_slots_today = (
        db.query(ScheduleSlot)
        .join(Class)
        .filter(
            ScheduleSlot.day_of_week == dow,
            Class.grade_level != 12,
            Class.is_active == True,
        )
        .count()
    )

    sessions_recorded = len(sessions_today)
    coverage = round(sessions_recorded / total_slots_today * 100, 1) if total_slots_today > 0 else 0

    return {
        "date": str(target_date),
        "day_of_week": dow,
        "entity_counts": {
            "teachers": total_teachers,
            "classes": total_classes,
            "students": total_students,
            "staff": total_staff,
        },
        "today": {
            "total_schedule_slots": total_slots_today,
            "sessions_recorded": sessions_recorded,
            "coverage_pct": coverage,
            "teacher_statuses": teacher_status_counts,
            "student_statuses": student_status_counts,
            "staff_sessions": [
                {
                    "staff_name": rs.staff.name if rs.staff else "?",
                    "started_at": str(rs.started_at) if rs.started_at else None,
                    "completed_at": str(rs.completed_at) if rs.completed_at else None,
                    "is_active": rs.completed_at is None,
                }
                for rs in rec_sessions
            ],
        },
    }


@router.get("/class-stats")
def class_stats(
    target_date: date = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
):
    """Per-class attendance breakdown for a given date."""
    if target_date is None:
        target_date = date.today()

    # Get day of week for slot counting
    day_names = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
    dow = day_names[target_date.weekday()]

    classes = db.query(Class).filter(Class.is_active == True).order_by(Class.grade_level, Class.name).all()

    result = []
    for c in classes:
        # How many schedule slots exist for this class on this day
        total_slots = (
            db.query(ScheduleSlot)
            .filter(
                ScheduleSlot.class_id == c.id,
                ScheduleSlot.day_of_week == dow,
            )
            .count()
        )

        # How many have been recorded
        sessions = (
            db.query(AttendanceSession)
            .join(ScheduleSlot)
            .filter(
                AttendanceSession.date == target_date,
                ScheduleSlot.class_id == c.id,
            )
            .all()
        )

        session_ids = [s.id for s in sessions]

        student_counts = {}
        if session_ids:
            records = (
                db.query(StudentAttendanceRecord)
                .filter(StudentAttendanceRecord.attendance_session_id.in_(session_ids))
                .all()
            )
            for r in records:
                student_counts[r.status] = student_counts.get(r.status, 0) + 1

        result.append({
            "class_id": c.id,
            "class_name": c.name,
            "grade_level": c.grade_level,
            "total_students": len(c.students),
            "total_slots": total_slots,
            "sessions_recorded": len(sessions),
            "student_statuses": student_counts,
        })

    return result


@router.get("/weekly-trend")
def weekly_trend(
    target_date: date = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
):
    """Last 7 school days attendance trend (for a simple chart)."""
    if target_date is None:
        target_date = date.today()

    days = []
    d = target_date
    while len(days) < 7:
        if d.weekday() < 5:  # Mon-Fri
            days.append(d)
        d -= timedelta(days=1)

    days.reverse()

    trend = []
    for day in days:
        sessions = (
            db.query(AttendanceSession)
            .filter(AttendanceSession.date == day)
            .count()
        )
        student_present = (
            db.query(StudentAttendanceRecord)
            .join(AttendanceSession)
            .filter(
                AttendanceSession.date == day,
                StudentAttendanceRecord.status == "hadir",
            )
            .count()
        )
        student_total = (
            db.query(StudentAttendanceRecord)
            .join(AttendanceSession)
            .filter(AttendanceSession.date == day)
            .count()
        )

        trend.append({
            "date": str(day),
            "sessions": sessions,
            "students_present": student_present,
            "students_total": student_total,
            "attendance_pct": round(student_present / student_total * 100, 1) if student_total > 0 else 0,
        })

    return trend