"""Auth module — service layer (all business logic lives here)."""
import uuid
import logging
from fastapi import HTTPException

from app.shared.schemas.auth import AuthRequest
from app.shared.database import SessionLocal, User
from app.shared.utils.doc_utils import _hash_password

logger = logging.getLogger(__name__)


async def register_user(req: AuthRequest) -> dict:
    """Create a new user account."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == req.username).first()
        if existing:
            raise HTTPException(409, "An account with this email already exists")

        user_id = f"user_{uuid.uuid4().hex[:10]}"
        user = User(
            id=user_id,
            name=req.name or req.username,
            email=req.email or req.username,
            username=req.username,
            password_hash=_hash_password(req.password),
        )
        db.add(user)
        db.commit()
        return {
            "user_id": user_id,
            "username": user.name or req.username,
            "message": "Registration successful",
        }
    finally:
        db.close()


async def login_user(req: AuthRequest) -> dict:
    """Validate credentials and return user profile."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username).first()
        if not user or user.password_hash != _hash_password(req.password):
            raise HTTPException(401, "Invalid email or password")
        return {
            "user_id": user.id,
            "username": user.name or user.username,
            "xp": user.xp,
            "level": user.level,
            "streak": user.streak,
        }
    finally:
        db.close()
