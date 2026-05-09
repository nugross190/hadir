"""
main.py
-------
FastAPI entry point for HADIR system.

Run: uvicorn main:app --reload

Routes:
  /                         → system info
  /health                   → database health check
  /stats                    → entity counts
  /classes                  → list all classes
  /auth/*                   → staff login
  /totp/*                   → TOTP display + validation
  /attendance/*             → recording sessions + attendance
"""

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from database import engine, Base, get_db
from models import *  # ensures all models are registered

# Import routers
from routers.auth import router as auth_router
from routers.totp import router as totp_router
from routers.attendance import router as attendance_router
from routers.reports import router as reports_router
from routers.dashboard import router as dashboard_router
from routers.students import router as students_router
from routers.approval import router as approval_router
from routers.pks import router as pks_router

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-create tables on startup. On Railway, no manual seed.py needed."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="HADIR System",
    description="School Attendance Recording System — SMAN 5 Garut",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(totp_router)
app.include_router(attendance_router)
app.include_router(reports_router)
app.include_router(dashboard_router)
app.include_router(students_router)
app.include_router(approval_router)
app.include_router(pks_router)


# ── Core Endpoints ──────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Serve the centralized login page."""
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/login")
def login_page():
    """Serve the centralized login page."""
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/input")
def input_page():
    """Serve the admin attendance recording page."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/display")
def display():
    """Serve the bell PC TOTP display page."""
    return FileResponse(FRONTEND_DIR / "display.html")


@app.get("/dashboard")
def dashboard_page():
    """Serve the dashboard page."""
    return FileResponse(FRONTEND_DIR / "dashboard.html")


@app.get("/panel")
def panel_page():
    """Serve the owner admin panel."""
    return FileResponse(FRONTEND_DIR / "panel.html")


@app.get("/pks-patrol")
def pks_page():
    """Serve the PKS (Student Security Patrol) attendance check page."""
    return FileResponse(FRONTEND_DIR / "pks.html")


@app.get("/api")
def api_info():
    return {
        "system": "HADIR",
        "full_name": "Hadirkan Administrasi Digital untuk Institusi dan Rekap",
        "version": "0.2.0",
        "status": "running",
    }


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Verify database connection and list tables."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return {
        "database": "connected",
        "tables": tables,
        "table_count": len(tables),
    }


@app.get("/stats")
def system_stats(db: Session = Depends(get_db)):
    """Quick count of all entities."""
    from models import (
        Staff, Teacher, Class, Student, ScheduleSlot,
        RecordingSession, AttendanceSession,
    )

    return {
        "staff": db.query(Staff).count(),
        "teachers": db.query(Teacher).count(),
        "classes": db.query(Class).count(),
        "students": db.query(Student).count(),
        "schedule_slots": db.query(ScheduleSlot).count(),
        "recording_sessions": db.query(RecordingSession).count(),
        "attendance_sessions": db.query(AttendanceSession).count(),
    }


@app.get("/classes")
def list_classes(
    grade: int = Query(None, description="Filter by grade level: 10, 11, 12"),
    db: Session = Depends(get_db),
):
    """List all classes, optionally filtered by grade."""
    from models import Class

    query = db.query(Class).filter(Class.is_active == True)
    if grade:
        query = query.filter(Class.grade_level == grade)

    classes = query.order_by(Class.grade_level, Class.name).all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "grade_level": c.grade_level,
            "student_count": len(c.students),
        }
        for c in classes
    ]


@app.post("/seed")
def seed_database(db: Session = Depends(get_db)):
    """
    One-time seed endpoint for Railway deployment.
    Call this once after first deploy to populate data.
    
    POST /seed — loads teachers, classes, schedule, students, staff.
    Safe to call multiple times (checks if data already exists).
    """
    import json
    from pathlib import Path
    from passlib.hash import bcrypt
    from models import Staff, Teacher, Class, Student, ScheduleSlot

    seed_dir = Path(__file__).resolve().parent / "seed_data"

    # Skip if already seeded
    if db.query(Teacher).count() > 0:
        return {"status": "already seeded", "teachers": db.query(Teacher).count()}

    # Seed staff
    for s in [("Admin 1","1234","admin"),("Admin 2","5678","admin"),("Admin 3","9012","admin"),("Kepala Sekolah","1111","headmaster")]:
        db.add(Staff(name=s[0], pin_hash=bcrypt.hash(s[1]), role=s[2]))
    db.commit()


    # Seed teachers
    with open(seed_dir / "teachers.json", encoding="utf-8") as f:
        for t in json.load(f):
            db.add(Teacher(kode=t["kode"], name=t["nama"], nip=t.get("nip"), status=t.get("status")))
    db.commit()

    # Seed classes + schedule
    with open(seed_dir / "schedule.json", encoding="utf-8") as f:
        schedule_data = json.load(f)

    class_names = sorted(set(s["kelas"] for s in schedule_data))
    for name in class_names:
        grade = 12 if name.upper().startswith("XII") else 11 if name.upper().startswith("XI") else 10
        db.add(Class(name=name, grade_level=grade))
    db.commit()

    # Build lookups
    teachers_map = {t.kode: t.id for t in db.query(Teacher).all()}
    classes_map = {c.name: c.id for c in db.query(Class).all()}

    # Mapel lookup
    with open(seed_dir / "teachers.json", encoding="utf-8") as f:
        mapel_lookup = {}
        for t in json.load(f):
            for mp in t.get("mata_pelajaran", []):
                mapel_lookup[mp["sub_kode"]] = mp["mapel"]

    for s in schedule_data:
        parent_kode = int(float(s["kode_guru"]))
        tid = teachers_map.get(parent_kode)
        cid = classes_map.get(s["kelas"])
        if tid and cid:
            db.add(ScheduleSlot(
                teacher_id=tid, class_id=cid, day_of_week=s["hari"],
                period_start=s["period_start"], period_end=s["period_end"],
                subject=mapel_lookup.get(s["kode_guru"]), sub_kode=s["kode_guru"],
            ))
    db.commit()

    # Seed students
    students_file = seed_dir / "students.json"
    if students_file.exists():
        with open(students_file, encoding="utf-8") as f:
            for s in json.load(f):
                cid = classes_map.get(s["class"])
                if cid:
                    db.add(Student(
                        nis=s["nis"], nisn=s.get("nisn"), name=s["name"],
                        gender=s.get("gender"), class_id=cid,
                    ))
        db.commit()

    # Seed PKS accounts + class assignments
    # 4 groups, each covering 3 classes from grade X and 3 from grade XI
    from models.pks import PKSAccount, PKSClassAssignment
    pks_groups = [
        ("PKS Kelompok 1", "pks1", "1001", 1, ["X - A","X - B","X - C","X - D","X - E","X - F"]),
        ("PKS Kelompok 2", "pks2", "2002", 2, ["X - G","X - H","X - I","X - J","X - K","X - L"]),
        ("PKS Kelompok 3", "pks3", "3003", 3, ["XI - A","XI - B","XI - C","XI - D","XI - E","XI - F"]),
        ("PKS Kelompok 4", "pks4", "4004", 4, ["XI - G","XI - H","XI - I","XI - J","XI - K","XI - L"]),
    ]
    classes_map_fresh = {c.name: c.id for c in db.query(Class).all()}
    for name, username, pin, group, class_names in pks_groups:
        pks = PKSAccount(name=name, username=username, pin_hash=bcrypt.hash(pin), group_number=group)
        db.add(pks)
        db.flush()
        for cname in class_names:
            cid = classes_map_fresh.get(cname)
            if cid:
                db.add(PKSClassAssignment(pks_id=pks.id, class_id=cid))
    db.commit()

    return {
        "status": "seeded",
        "staff": db.query(Staff).count(),
        "teachers": db.query(Teacher).count(),
        "classes": db.query(Class).count(),
        "schedule_slots": db.query(ScheduleSlot).count(),
        "students": db.query(Student).count(),
        "pks_accounts": db.query(PKSAccount).count(),
    }


@app.post("/seed-pks")
def seed_pks(db: Session = Depends(get_db)):
    """
    Seed PKS accounts and class assignments independently.
    Safe to call on an already-seeded database.
    Call this if the main /seed was run before the PKS feature was added.
    """
    from passlib.hash import bcrypt
    from models.pks import PKSAccount, PKSClassAssignment

    if db.query(PKSAccount).count() > 0:
        return {
            "status": "already seeded",
            "pks_accounts": db.query(PKSAccount).count(),
        }

    classes_map = {c.name: c.id for c in db.query(Class).all()}
    if not classes_map:
        return {"status": "error", "detail": "No classes found — run /seed first"}

    pks_groups = [
        ("PKS Kelompok 1", "pks1", "1001", 1, ["X - A","X - B","X - C","X - D","X - E","X - F"]),
        ("PKS Kelompok 2", "pks2", "2002", 2, ["X - G","X - H","X - I","X - J","X - K","X - L"]),
        ("PKS Kelompok 3", "pks3", "3003", 3, ["XI - A","XI - B","XI - C","XI - D","XI - E","XI - F"]),
        ("PKS Kelompok 4", "pks4", "4004", 4, ["XI - G","XI - H","XI - I","XI - J","XI - K","XI - L"]),
    ]

    for name, username, pin, group, class_names in pks_groups:
        pks = PKSAccount(name=name, username=username, pin_hash=bcrypt.hash(pin), group_number=group)
        db.add(pks)
        db.flush()
        for cname in class_names:
            cid = classes_map.get(cname)
            if cid:
                db.add(PKSClassAssignment(pks_id=pks.id, class_id=cid))
    db.commit()

    return {
        "status": "seeded",
        "pks_accounts": db.query(PKSAccount).count(),
        "assignments": db.query(PKSClassAssignment).count(),
    }
