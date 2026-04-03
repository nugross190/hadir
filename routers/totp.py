"""
routers/totp.py
"""
import os
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from services.totp_service import get_current_code, validate_code, get_display_info

router = APIRouter(prefix="/totp", tags=["totp"])
DISPLAY_KEY = os.environ.get("DISPLAY_KEY", "hadir-display-2026")

def _check_display_key(key: str = Query(None)):
    if not key or key != DISPLAY_KEY:
        raise HTTPException(status_code=403, detail="Akses ditolak")

class ValidateRequest(BaseModel):
    code: str

@router.get("/current")
def current_code(key: str = Query(None)):
    _check_display_key(key)
    return get_current_code()

@router.get("/display")
def display_info(key: str = Query(None)):
    _check_display_key(key)
    return get_display_info()

@router.post("/validate")
def validate(req: ValidateRequest):
    is_valid = validate_code(req.code)
    return {"code": req.code, "valid": is_valid}
