"""
services/attendance_service.py
-------------------------------
Business logic for the attendance recording workflow.

The flow:
  1. Admin logs in (PIN) → gets staff identity
  2. Admin enters TOTP code → RecordingSession created (presence verified)
  3. Admin picks class + slot → system shows teacher + student roster
  4. Admin records teacher status + student statuses → saves both
  5. Admin moves to next class (within same RecordingSession)
  6. Admin finishes → RecordingSession marked complete

This service handles steps 2-6. Auth (step 1) is in auth_service.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from models import (
    Staff,
    RecordingSession,
    AttendanceSession,
    TeacherAttendanceRecord,
    StudentAttendanceRecord,
    ScheduleSlot,
    Student,
    Class,
    Teacher,
)
from services.totp_service import validate_code


# ── Recording Session ───────────────────────────────────────────────────────

def start_recording_session(
    db: Session,
    staff_id: int,
    totp_code: str,
) -> dict:
    """
    Start a new recording session after TOTP verification.
    Requires daily approval from headmaster/owner.
    
    Returns the session info if approved + TOTP valid,
    raises ValueError if not.
    """
    from models import DailyApproval

    # Verify staff exists
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise ValueError("Staff not found")

    # Check daily approval (only for admin role)
    if staff.role == "admin":
        today = date.today()
        approval = (
            db.query(DailyApproval)
            .filter(
                DailyApproval.staff_id == staff_id,
                DailyApproval.date == today,
            )
            .first()
        )
        if not approval:
            raise ValueError("Belum disetujui oleh kepala sekolah hari ini")

    # Validate TOTP
    totp_valid = validate_code(totp_code)

    # Create session regardless (log the attempt), but mark verified status
    session = RecordingSession(
        staff_id=staff_id,
        totp_code_entered=totp_code,
        totp_verified=totp_valid,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    if not totp_valid:
        raise ValueError(
            f"Invalid TOTP code. Session {session.id} logged as unverified."
        )

    return {
        "recording_session_id": session.id,
        "staff_name": staff.name,
        "started_at": session.started_at.isoformat(),
        "totp_verified": True,
    }


def complete_recording_session(db: Session, session_id: int) -> dict:
    """Mark a recording session as complete."""
    session = (
        db.query(RecordingSession)
        .filter(RecordingSession.id == session_id)
        .first()
    )
    if not session:
        raise ValueError("Recording session not found")

    session.completed_at = datetime.now(timezone.utc)
    db.commit()

    # Count how many attendance sessions were recorded
    count = (
        db.query(AttendanceSession)
        .filter(AttendanceSession.recording_session_id == session_id)
        .count()
    )

    return {
        "recording_session_id": session.id,
        "completed_at": session.completed_at.isoformat(),
        "sessions_recorded": count,
    }


# ── Schedule Lookup ─────────────────────────────────────────────────────────

def get_today_schedule(
    db: Session,
    day_name: str,
    class_id: Optional[int] = None,
) -> list[dict]:
    """
    Get today's schedule slots for a given day.
    Optionally filter by class.
    
    This is what the admin sees when picking which slot to record.
    """
    query = (
        db.query(ScheduleSlot)
        .join(Teacher)
        .join(Class)
        .filter(ScheduleSlot.day_of_week == day_name)
        .options(
            joinedload(ScheduleSlot.teacher),
            joinedload(ScheduleSlot.kelas),
        )
    )

    if class_id:
        query = query.filter(ScheduleSlot.class_id == class_id)

    query = query.order_by(ScheduleSlot.class_id, ScheduleSlot.period_start)
    slots = query.all()

    return [
        {
            "slot_id": s.id,
            "class_name": s.kelas.name,
            "class_id": s.class_id,
            "teacher_name": s.teacher.name,
            "teacher_kode": s.teacher.kode,
            "subject": s.subject,
            "period_start": s.period_start,
            "period_end": s.period_end,
            "sub_kode": s.sub_kode,
        }
        for s in slots
    ]


def get_class_students(db: Session, class_id: int) -> list[dict]:
    """
    Get all active students in a class — the roster shown
    on page 2 of the admin UI.
    """
    students = (
        db.query(Student)
        .filter(
            Student.class_id == class_id,
            Student.is_active == True,
        )
        .order_by(Student.name)
        .all()
    )

    return [
        {
            "student_id": s.id,
            "nis": s.nis,
            "name": s.name,
            "gender": s.gender,
        }
        for s in students
    ]


# ── Attendance Recording ────────────────────────────────────────────────────

def record_attendance(
    db: Session,
    recording_session_id: int,
    schedule_slot_id: int,
    attendance_date: date,
    teacher_status: str,
    teacher_notes: Optional[str],
    student_statuses: list[dict],  # [{"student_id": 1, "status": "hadir"}, ...]
) -> dict:
    """
    Record attendance for one schedule slot.
    This is the core function — called when admin submits page 2.
    
    Creates:
      - 1 AttendanceSession
      - 1 TeacherAttendanceRecord
      - N StudentAttendanceRecords
    
    All in one transaction.
    
    student_statuses format:
      [
        {"student_id": 42, "status": "hadir"},
        {"student_id": 43, "status": "tidak_hadir"},
        {"student_id": 44, "status": "sakit"},
        ...
      ]
    """
    # Verify recording session exists and is verified
    rec_session = (
        db.query(RecordingSession)
        .filter(RecordingSession.id == recording_session_id)
        .first()
    )
    if not rec_session:
        raise ValueError("Recording session not found")
    if not rec_session.totp_verified:
        raise ValueError("Recording session not TOTP-verified")
    if rec_session.completed_at is not None:
        raise ValueError("Recording session already completed")

    # Verify schedule slot exists
    slot = (
        db.query(ScheduleSlot)
        .filter(ScheduleSlot.id == schedule_slot_id)
        .first()
    )
    if not slot:
        raise ValueError("Schedule slot not found")

    # Check for duplicate: already recorded this slot for this date?
    existing = (
        db.query(AttendanceSession)
        .filter(
            AttendanceSession.schedule_slot_id == schedule_slot_id,
            AttendanceSession.date == attendance_date,
        )
        .first()
    )
    if existing:
        raise ValueError(
            f"Attendance already recorded for slot {schedule_slot_id} "
            f"on {attendance_date} (session {existing.id})"
        )

    # ── Create everything in one transaction ────────────────────────────

    # 1. AttendanceSession
    att_session = AttendanceSession(
        schedule_slot_id=schedule_slot_id,
        recording_session_id=recording_session_id,
        date=attendance_date,
    )
    db.add(att_session)
    db.flush()  # get att_session.id without committing

    # 2. TeacherAttendanceRecord
    teacher_record = TeacherAttendanceRecord(
        attendance_session_id=att_session.id,
        status=teacher_status,
        notes=teacher_notes,
    )
    db.add(teacher_record)

    # 3. StudentAttendanceRecords
    student_records = []
    for entry in student_statuses:
        record = StudentAttendanceRecord(
            attendance_session_id=att_session.id,
            student_id=entry["student_id"],
            status=entry.get("status", "hadir"),
        )
        db.add(record)
        student_records.append(record)

    db.commit()

    # Count statuses
    status_counts = {}
    for entry in student_statuses:
        s = entry.get("status", "hadir")
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "attendance_session_id": att_session.id,
        "schedule_slot_id": schedule_slot_id,
        "date": attendance_date.isoformat(),
        "teacher_status": teacher_status,
        "students_recorded": len(student_records),
        "student_status_summary": status_counts,
    }


# ── Quick Stats ─────────────────────────────────────────────────────────────

def get_recording_session_summary(db: Session, session_id: int) -> dict:
    """Summary of a recording session — for the admin's review screen."""
    session = (
        db.query(RecordingSession)
        .options(joinedload(RecordingSession.staff))
        .filter(RecordingSession.id == session_id)
        .first()
    )
    if not session:
        raise ValueError("Recording session not found")

    att_sessions = (
        db.query(AttendanceSession)
        .options(
            joinedload(AttendanceSession.schedule_slot)
            .joinedload(ScheduleSlot.kelas),
            joinedload(AttendanceSession.teacher_record),
        )
        .filter(AttendanceSession.recording_session_id == session_id)
        .all()
    )

    entries = []
    for a in att_sessions:
        entries.append({
            "class": a.schedule_slot.kelas.name,
            "period": f"{a.schedule_slot.period_start}-{a.schedule_slot.period_end}",
            "teacher_status": a.teacher_record.status if a.teacher_record else None,
            "students_recorded": len(a.student_records),
        })

    return {
        "recording_session_id": session.id,
        "staff_name": session.staff.name,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "totp_verified": session.totp_verified,
        "total_sessions": len(entries),
        "entries": entries,
    }
