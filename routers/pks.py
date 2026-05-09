"""
routers/pks.py
--------------
PKS (Student Security Patrol) endpoints.

PKS users log in via the standard /auth/login flow (role='pks'),
so there's no PKS-specific login endpoint here — only the
patrol/check operations once they're authenticated.

GET  /pks/my-classes                — classes assigned to a PKS staff
GET  /pks/class/{class_id}/students — students in a class + existing check data
POST /pks/check                     — submit a patrol attendance check
GET  /pks/history                   — past check history for a PKS staff
"""

from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Staff
from models.pks import PKSClassAssignment, PKSAttendanceCheck, PKSStudentCheck
from models.school import Student

router = APIRouter(prefix="/pks", tags=["pks"])

VALID_STATUSES = {"hadir", "tidak_hadir", "izin", "sakit", "alpa"}


# ── Request Schemas ────────────────────────────────────────────────────────────

class StudentCheckItem(BaseModel):
    student_id: int
    status: str
    notes: Optional[str] = None


class PKSCheckRequest(BaseModel):
    class_id: int
    notes: Optional[str] = None
    students: List[StudentCheckItem]


def _ensure_pks(db: Session, staff_id: int) -> Staff:
    staff = db.query(Staff).filter(Staff.id == staff_id, Staff.is_active == True).first()
    if not staff or staff.role != "pks":
        raise HTTPException(status_code=403, detail="Akun bukan PKS")
    return staff


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/my-classes")
def get_my_classes(staff_id: int = Query(...), db: Session = Depends(get_db)):
    _ensure_pks(db, staff_id)

    assignments = (
        db.query(PKSClassAssignment)
        .filter(PKSClassAssignment.staff_id == staff_id)
        .all()
    )

    today = date.today()
    result = []
    for a in assignments:
        check = db.query(PKSAttendanceCheck).filter(
            PKSAttendanceCheck.staff_id == staff_id,
            PKSAttendanceCheck.class_id == a.class_id,
            PKSAttendanceCheck.check_date == today,
        ).first()

        student_count = db.query(Student).filter(
            Student.class_id == a.class_id,
            Student.is_active == True,
        ).count()

        result.append({
            "class_id": a.class_id,
            "class_name": a.kelas.name,
            "grade_level": a.kelas.grade_level,
            "student_count": student_count,
            "checked_today": check is not None,
            "check_id": check.id if check else None,
            "checked_at": check.checked_at.isoformat() if check else None,
        })

    result.sort(key=lambda x: (x["grade_level"], x["class_name"]))
    return result


@router.get("/class/{class_id}/students")
def get_class_students(
    class_id: int,
    staff_id: int = Query(...),
    check_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    _ensure_pks(db, staff_id)

    assignment = db.query(PKSClassAssignment).filter(
        PKSClassAssignment.staff_id == staff_id,
        PKSClassAssignment.class_id == class_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="Tidak memiliki akses ke kelas ini")

    target_date = date.fromisoformat(check_date) if check_date else date.today()

    students = (
        db.query(Student)
        .filter(Student.class_id == class_id, Student.is_active == True)
        .order_by(Student.name)
        .all()
    )

    check = db.query(PKSAttendanceCheck).filter(
        PKSAttendanceCheck.staff_id == staff_id,
        PKSAttendanceCheck.class_id == class_id,
        PKSAttendanceCheck.check_date == target_date,
    ).first()

    existing = {}
    if check:
        for sc in check.student_checks:
            existing[sc.student_id] = {"status": sc.status, "notes": sc.notes}

    return {
        "class_name": assignment.kelas.name,
        "grade_level": assignment.kelas.grade_level,
        "already_checked": check is not None,
        "check_id": check.id if check else None,
        "notes": check.notes if check else None,
        "students": [
            {
                "student_id": s.id,
                "nis": s.nis,
                "name": s.name,
                "gender": s.gender,
                "status": existing.get(s.id, {}).get("status", "hadir"),
                "notes": existing.get(s.id, {}).get("notes"),
            }
            for s in students
        ],
    }


@router.post("/check")
def submit_check(
    req: PKSCheckRequest,
    staff_id: int = Query(...),
    db: Session = Depends(get_db),
):
    _ensure_pks(db, staff_id)

    assignment = db.query(PKSClassAssignment).filter(
        PKSClassAssignment.staff_id == staff_id,
        PKSClassAssignment.class_id == req.class_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="Tidak memiliki akses ke kelas ini")

    for item in req.students:
        if item.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Status tidak valid: {item.status}")

    today = date.today()
    now = datetime.now()

    check = db.query(PKSAttendanceCheck).filter(
        PKSAttendanceCheck.staff_id == staff_id,
        PKSAttendanceCheck.class_id == req.class_id,
        PKSAttendanceCheck.check_date == today,
    ).first()

    if check:
        check.notes = req.notes
        check.checked_at = now
        db.query(PKSStudentCheck).filter(PKSStudentCheck.check_id == check.id).delete()
    else:
        check = PKSAttendanceCheck(
            staff_id=staff_id,
            class_id=req.class_id,
            check_date=today,
            checked_at=now,
            notes=req.notes,
        )
        db.add(check)
        db.flush()

    for item in req.students:
        db.add(PKSStudentCheck(
            check_id=check.id,
            student_id=item.student_id,
            status=item.status,
            notes=item.notes,
        ))

    db.commit()
    db.refresh(check)

    present = sum(1 for s in req.students if s.status == "hadir")
    absent = len(req.students) - present

    return {
        "status": "ok",
        "check_id": check.id,
        "class_name": assignment.kelas.name,
        "total": len(req.students),
        "present": present,
        "absent": absent,
    }


@router.get("/history")
def get_check_history(staff_id: int = Query(...), db: Session = Depends(get_db)):
    _ensure_pks(db, staff_id)

    checks = (
        db.query(PKSAttendanceCheck)
        .filter(PKSAttendanceCheck.staff_id == staff_id)
        .order_by(PKSAttendanceCheck.check_date.desc(), PKSAttendanceCheck.checked_at.desc())
        .limit(100)
        .all()
    )

    return [
        {
            "check_id": c.id,
            "class_name": c.kelas.name,
            "grade_level": c.kelas.grade_level,
            "check_date": c.check_date.isoformat(),
            "checked_at": c.checked_at.isoformat(),
            "notes": c.notes,
            "total": len(c.student_checks),
            "present": sum(1 for s in c.student_checks if s.status == "hadir"),
            "absent": sum(1 for s in c.student_checks if s.status != "hadir"),
        }
        for c in checks
    ]
