"""
routers/auth.py
----------------
Authentication endpoints.

POST /auth/login         — verify staff PIN (admin, headmaster)
POST /auth/owner-login   — verify owner/administrator PIN (env var based)
GET  /auth/staff         — list active staff (for login screen)
POST /auth/add-staff     — add a new staff account (for seeding missing accounts)
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

from database import get_db
from services.auth_service import verify_staff_pin, list_staff
from models import Staff

router = APIRouter(prefix="/auth", tags=["auth"])

OWNER_PIN = os.environ.get("OWNER_PIN", "admin2026")


class LoginRequest(BaseModel):
    staff_id: int
    pin: str


class OwnerLoginRequest(BaseModel):
    pin: str


class AddStaffRequest(BaseModel):
    name: str
    pin: str
    role: str = "admin"


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    try:
        result = verify_staff_pin(db, req.staff_id, req.pin)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/owner-login")
def owner_login(req: OwnerLoginRequest):
    if req.pin != OWNER_PIN:
        raise HTTPException(status_code=401, detail="PIN salah")
    return {"role": "owner", "name": "Administrator"}


@router.get("/staff")
def get_staff_list(
    role: str = Query(None, description="Filter by role: admin, headmaster"),
    db: Session = Depends(get_db),
):
    return list_staff(db, role=role)


@router.post("/add-staff")
def add_staff(
    req: AddStaffRequest,
    owner_pin: str = Query(..., alias="key"),
    db: Session = Depends(get_db),
):
    if owner_pin != OWNER_PIN:
        raise HTTPException(status_code=403, detail="Akses ditolak")
    if req.role not in ("admin", "headmaster"):
        raise HTTPException(status_code=400, detail="Role harus admin atau headmaster")
    existing = db.query(Staff).filter(Staff.name == req.name).first()
    if existing:
        return {"status": "already exists", "staff_id": existing.id, "name": existing.name, "role": existing.role}
    staff = Staff(name=req.name.strip(), pin_hash=bcrypt.hash(req.pin), role=req.role)
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return {"status": "created", "staff_id": staff.id, "name": staff.name, "role": staff.role}
