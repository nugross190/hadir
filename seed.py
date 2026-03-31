"""
seed.py
-------
Creates all tables and seeds data from:
  - teachers.json  (67 teachers)
  - schedule.json  (795 schedule slots)
  - 3 admin staff (hardcoded for now)
  - classes extracted from schedule.json

Student data is NOT seeded here — you'll need a roster file.
Run: python seed.py

This is like importing CSVs into your Excel workbook,
but into PostgreSQL instead.
"""

import json
import sys
from pathlib import Path

from sqlalchemy import inspect

from config import DATABASE_URL
from database import engine, SessionLocal, Base
from models import (
    Staff, Teacher, Class, Student, ScheduleSlot,
    QRToken, RecordingSession, AttendanceSession,
    TeacherAttendanceRecord, StudentAttendanceRecord,
)
from passlib.hash import bcrypt

# ── Paths to seed data ─────────────────────────────────────────────────────
SEED_DIR = Path(__file__).resolve().parent / "seed_data"
TEACHERS_FILE = SEED_DIR / "teachers.json"
SCHEDULE_FILE = SEED_DIR / "schedule.json"


def create_tables():
    """Drop and recreate all tables. Like clearing the workbook and rebuilding."""
    print("Creating tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Verify tables exist
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"  Tables created: {tables}")


def seed_staff(db):
    """Seed the 3 admin staff with simple PINs."""
    print("\nSeeding staff...")
    staff_data = [
        {"name": "Admin 1", "pin": "1234", "role": "admin"},
        {"name": "Admin 2", "pin": "5678", "role": "admin"},
        {"name": "Admin 3", "pin": "9012", "role": "admin"},
        {"name": "Kepala Sekolah", "pin": "1111", "role": "headmaster"},
    ]

    for s in staff_data:
        staff = Staff(
            name=s["name"],
            pin_hash=bcrypt.hash(s["pin"]),
            role=s["role"],
        )
        db.add(staff)

    db.commit()
    count = db.query(Staff).count()
    print(f"  -> {count} staff members seeded")


def seed_teachers(db):
    """Load teachers from teachers.json."""
    print("\nSeeding teachers...")
    with open(TEACHERS_FILE, "r", encoding="utf-8") as f:
        teachers_data = json.load(f)

    for t in teachers_data:
        teacher = Teacher(
            kode=t["kode"],
            name=t["nama"],
            nip=t.get("nip"),
            status=t.get("status"),
        )
        db.add(teacher)

    db.commit()
    count = db.query(Teacher).count()
    print(f"  -> {count} teachers seeded")


def extract_grade_level(class_name: str) -> int:
    """
    'X - A' -> 10, 'XI IPA - 1' -> 11, 'XII IPS - 4' -> 12
    """
    name = class_name.strip().upper()
    if name.startswith("XII"):
        return 12
    elif name.startswith("XI"):
        return 11
    elif name.startswith("X"):
        return 10
    return 0


def seed_classes(db, schedule_data):
    """Extract unique class names from schedule and seed them."""
    print("\nSeeding classes...")
    class_names = sorted(set(s["kelas"] for s in schedule_data))

    for name in class_names:
        kelas = Class(
            name=name,
            grade_level=extract_grade_level(name),
        )
        db.add(kelas)

    db.commit()
    count = db.query(Class).count()
    print(f"  -> {count} classes seeded")


def seed_schedule(db, schedule_data):
    """
    Load schedule slots from schedule.json.
    
    Key logic: kode_guru in schedule can be "13" or "13.1" (sub-code).
    We map to the parent teacher by taking the integer part.
    The raw sub_kode is preserved in the slot for reference.
    """
    print("\nSeeding schedule slots...")

    # Build lookup maps: kode -> teacher.id, class_name -> class.id
    teachers = {t.kode: t.id for t in db.query(Teacher).all()}
    classes = {c.name: c.id for c in db.query(Class).all()}

    # Build sub_kode -> mapel lookup from teachers.json
    with open(TEACHERS_FILE, "r", encoding="utf-8") as f:
        teachers_raw = json.load(f)

    mapel_lookup = {}  # {"13": "Fisika", "13.1": "Prakarya"}
    for t in teachers_raw:
        for mp in t.get("mata_pelajaran", []):
            mapel_lookup[mp["sub_kode"]] = mp["mapel"]

    orphans = []
    for s in schedule_data:
        kode_str = s["kode_guru"]
        parent_kode = int(float(kode_str))  # "13.1" -> 13, "9" -> 9

        teacher_id = teachers.get(parent_kode)
        class_id = classes.get(s["kelas"])

        if teacher_id is None:
            orphans.append(kode_str)
            continue
        if class_id is None:
            orphans.append(s["kelas"])
            continue

        # Look up subject from sub_kode
        subject = mapel_lookup.get(kode_str)

        slot = ScheduleSlot(
            teacher_id=teacher_id,
            class_id=class_id,
            day_of_week=s["hari"],
            period_start=s["period_start"],
            period_end=s["period_end"],
            subject=subject,
            sub_kode=kode_str,
        )
        db.add(slot)

    db.commit()
    count = db.query(ScheduleSlot).count()
    print(f"  -> {count} schedule slots seeded")

    if orphans:
        print(f"  ⚠ Orphans (no matching teacher/class): {set(orphans)}")
    else:
        print("  ✓ Zero orphans")


STUDENTS_FILE = SEED_DIR / "students.json"


def seed_students(db):
    """
    Load students from students.json (produced by parse_student_roster.py).
    
    Maps each student's class name to the Class table.
    Handles duplicate NIS (6 known duplicates from school data entry errors)
    by using (nis, class_id) as the unique constraint instead of nis alone.
    """
    print("\nSeeding students...")

    if not STUDENTS_FILE.exists():
        print(f"  ⚠ Skipped — {STUDENTS_FILE} not found")
        print(f"    Run parse_student_roster.py first, then copy students.json to {SEED_DIR}/")
        return

    with open(STUDENTS_FILE, "r", encoding="utf-8") as f:
        students_data = json.load(f)

    # Build class name -> id lookup
    classes = {c.name: c.id for c in db.query(Class).all()}

    skipped = []
    for s in students_data:
        class_id = classes.get(s["class"])
        if class_id is None:
            skipped.append(s["class"])
            continue

        student = Student(
            nis=s["nis"],
            nisn=s.get("nisn"),
            name=s["name"],
            gender=s.get("gender"),
            class_id=class_id,
        )
        db.add(student)

    db.commit()
    count = db.query(Student).count()
    print(f"  -> {count} students seeded")

    if skipped:
        print(f"  ⚠ Skipped (no matching class): {set(skipped)}")
    else:
        print("  ✓ All students mapped to classes")

    # Report per-grade counts
    for grade in [10, 11, 12]:
        grade_count = (
            db.query(Student)
            .join(Class)
            .filter(Class.grade_level == grade)
            .count()
        )
        print(f"    Grade {grade}: {grade_count} students")


def main():
    print("=" * 60)
    print("HADIR System — Database Seed")
    print(f"Database: {DATABASE_URL}")
    print("=" * 60)

    # Check seed files exist
    if not TEACHERS_FILE.exists():
        print(f"\n✗ Missing: {TEACHERS_FILE}")
        print(f"  Copy teachers.json to {SEED_DIR}/")
        sys.exit(1)
    if not SCHEDULE_FILE.exists():
        print(f"\n✗ Missing: {SCHEDULE_FILE}")
        print(f"  Copy schedule.json to {SEED_DIR}/")
        sys.exit(1)

    # Load schedule data (needed for both classes and schedule seeding)
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        schedule_data = json.load(f)

    # Create tables
    create_tables()

    # Seed in dependency order
    db = SessionLocal()
    try:
        seed_staff(db)
        seed_teachers(db)
        seed_classes(db, schedule_data)
        seed_schedule(db, schedule_data)
        seed_students(db)

        # Summary
        print("\n" + "=" * 60)
        print("Seed complete!")
        print(f"  Staff:          {db.query(Staff).count()}")
        print(f"  Teachers:       {db.query(Teacher).count()}")
        print(f"  Classes:        {db.query(Class).count()}")
        print(f"  Schedule Slots: {db.query(ScheduleSlot).count()}")
        print(f"  Students:       {db.query(Student).count()}")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n✗ Error during seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
