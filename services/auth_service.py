"""
services/auth_service.py
-------------------------
Simple PIN-based authentication for admin staff.

No JWT tokens for now — just verify PIN and return staff info.
In production you'd add JWT, but for a school internal app
with 3 users behind a TOTP gate, this is sufficient for v1.
"""

from sqlalchemy.orm import Session
from passlib.hash import bcrypt

from models import Staff


def verify_staff_pin(db: Session, staff_id: int, pin: str) -> dict:
    """
    Verify a staff member's PIN.
    
    Returns staff info if valid, raises ValueError if not.
    """
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise ValueError("Staff not found")

    if not staff.is_active:
        raise ValueError("Staff account is deactivated")

    if not bcrypt.verify(pin, staff.pin_hash):
        raise ValueError("Invalid PIN")

    return {
        "staff_id": staff.id,
        "name": staff.name,
        "role": staff.role,
    }


def list_staff(db: Session, role: str = None) -> list[dict]:
    """
    List all active staff — shown on the login screen
    so admin can tap their name instead of typing an ID.
    Optionally filter by role (e.g. 'admin', 'headmaster').
    """
    query = db.query(Staff).filter(Staff.is_active == True)
    if role:
        query = query.filter(Staff.role == role)
    staff = query.order_by(Staff.name).all()

    return [
        {
            "staff_id": s.id,
            "name": s.name,
            "role": s.role,
        }
        for s in staff
    ]
