"""Auth module — routes (thin layer: validate → service → response)."""
import uuid
import logging
from fastapi import APIRouter, HTTPException

from app.shared.schemas.auth import AuthRequest
from app.modules.auth.service import register_user, login_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Auth"])


@router.post("/register")
async def register(req: AuthRequest):
    """Register a new user."""
    if not req.username or len(req.username) < 5:
        raise HTTPException(400, "Email must be valid")
    if not req.password or len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    return await register_user(req)


@router.post("/login")
async def login(req: AuthRequest):
    """Login with credentials."""
    return await login_user(req)
