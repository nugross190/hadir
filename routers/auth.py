"""
routers/auth.py
----------------
Staff authentication endpoints.

POST /auth/login      — verify staff PIN
GET  /auth/staff      — list active staff (for login screen)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from services.auth_service import verify_staff_pin, list_staff

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    staff_id: int
    pin: str


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Verify staff PIN. Returns staff info on success."""
    try:
        result = verify_staff_pin(db, req.staff_id, req.pin)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/staff")
def get_staff_list(
    role: str = Query(None, description="Filter by role: admin, headmaster"),
    db: Session = Depends(get_db),
):
    """List all active staff for the login screen, optionally filtered by role."""
    return list_staff(db, role=role)
