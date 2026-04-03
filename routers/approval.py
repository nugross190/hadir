"""
routers/approval.py
--------------------
Daily approval endpoints.

GET  /approval/status?date=           → approval status for all admins today
POST /approval/approve                → approve an admin for today
POST /approval/revoke                 → revoke an admin's approval for today
GET  /approval/check/{staff_id}       → check if a specific admin is approved today
"""

import os
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Staff, DailyApproval

router = APIRouter(prefix="/approval", tags=["approval"])

OWNER_PIN = os.environ.get("OWNER_PIN", "admin2026")


class ApproveRequest(BaseModel):
    staff_id: int
    approver_staff_id: int | None = None  # NULL = owner


class RevokeRequest(BaseModel):
    staff_id: int


@router.get("/status")
def approval_status(
    target_date: date = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
):
    """
    Get approval status for all admin staff on a given date.
    Used by headmaster dashboard to show approve/revoke buttons.
    """
    if target_date is None:
        target_date = date.today()

    admins = (
        db.query(Staff)
        .filter(Staff.role == "admin", Staff.is_active == True)
        .order_by(Staff.name)
        .all()
    )

    approvals = (
        db.query(DailyApproval)
        .filter(DailyApproval.date == target_date)
        .all()
    )
    approved_map = {a.staff_id: a for a in approvals}

    result = []
    for admin in admins:
        approval = approved_map.get(admin.id)
        result.append({
            "staff_id": admin.id,
            "name": admin.name,
            "approved": approval is not None,
            "approved_at": approval.approved_at.isoformat() if approval else None,
            "approved_by": approval.approver.name if approval and approval.approver else ("Administrator" if approval else None),
        })

    return {"date": str(target_date), "admins": result}


@router.post("/approve")
def approve_admin(
    req: ApproveRequest,
    db: Session = Depends(get_db),
):
    """
    Approve an admin for today. Called by headmaster or owner.
    Safe to call multiple times — skips if already approved.
    """
    today = date.today()

    # Verify the admin exists and is an admin
    admin = db.query(Staff).filter(Staff.id == req.staff_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Staff tidak ditemukan")
    if admin.role != "admin":
        raise HTTPException(status_code=400, detail="Hanya admin yang perlu persetujuan")

    # Check if already approved
    existing = (
        db.query(DailyApproval)
        .filter(DailyApproval.staff_id == req.staff_id, DailyApproval.date == today)
        .first()
    )
    if existing:
        return {
            "status": "already_approved",
            "staff_id": admin.id,
            "name": admin.name,
            "date": str(today),
        }

    approval = DailyApproval(
        staff_id=req.staff_id,
        date=today,
        approved_by=req.approver_staff_id,  # NULL if owner
    )
    db.add(approval)
    db.commit()

    return {
        "status": "approved",
        "staff_id": admin.id,
        "name": admin.name,
        "date": str(today),
    }


@router.post("/revoke")
def revoke_approval(
    req: RevokeRequest,
    db: Session = Depends(get_db),
):
    """Revoke an admin's approval for today."""
    today = date.today()

    approval = (
        db.query(DailyApproval)
        .filter(DailyApproval.staff_id == req.staff_id, DailyApproval.date == today)
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Tidak ada persetujuan untuk dibatalkan")

    db.delete(approval)
    db.commit()

    return {"status": "revoked", "staff_id": req.staff_id, "date": str(today)}


@router.get("/check/{staff_id}")
def check_approval(
    staff_id: int,
    db: Session = Depends(get_db),
):
    """
    Check if a specific admin is approved for today.
    Called by the input page before allowing TOTP entry.
    """
    today = date.today()

    approval = (
        db.query(DailyApproval)
        .filter(DailyApproval.staff_id == staff_id, DailyApproval.date == today)
        .first()
    )

    return {
        "staff_id": staff_id,
        "date": str(today),
        "approved": approval is not None,
    }
