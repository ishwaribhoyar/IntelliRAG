"""Payments and Profile module — routes."""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from datetime import datetime, timezone

from app.shared.database import SessionLocal, User
from app.shared.utils.rate_limiter import FREE_TIER_LIMITS

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Payments & Profile"])


class SubscribeRequest(BaseModel):
    user_id: str
    tier: str


@router.get("/users/profile")
async def get_profile(
    user_id: Optional[str] = Query(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Retrieve user profile details, subscription tier, and daily usage statistics."""
    target_user_id = x_user_id or user_id or "default_user"
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == target_user_id).first()
        if not user:
            # If default_user is requested but not in DB, create it dynamically to prevent failure
            if target_user_id == "default_user":
                user = User(
                    id="default_user",
                    name="Default User",
                    email="default@intellirag.ai",
                    username="default_user",
                    tier="free",
                    xp=0,
                    level=1,
                    streak=0
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                raise HTTPException(status_code=404, detail="User not found")
        
        # Check and handle day boundary reset for limit counts
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if user.last_request_reset != today_str:
            user.daily_rag_count = 0
            user.daily_quiz_count = 0
            user.daily_summary_count = 0
            user.daily_flashcard_count = 0
            user.last_request_reset = today_str
            db.commit()
            db.refresh(user)
            
        tier = (user.tier or "free").strip().lower()
        
        # Calculate remaining usages
        rag_limit = FREE_TIER_LIMITS["rag"]
        quiz_limit = FREE_TIER_LIMITS["quiz"]
        flashcard_limit = FREE_TIER_LIMITS["flashcard"]
        summary_limit = FREE_TIER_LIMITS["summary"]
        
        return {
            "user_id": user.id,
            "username": user.name or user.username or user.id,
            "email": user.email,
            "tier": tier,
            "xp": user.xp or 0,
            "level": user.level or 1,
            "streak": user.streak or 0,
            "usage": {
                "rag": {
                    "used": user.daily_rag_count or 0,
                    "limit": rag_limit,
                    "remaining": max(0, rag_limit - (user.daily_rag_count or 0)) if tier == "free" else 999999
                },
                "quiz": {
                    "used": user.daily_quiz_count or 0,
                    "limit": quiz_limit,
                    "remaining": max(0, quiz_limit - (user.daily_quiz_count or 0)) if tier == "free" else 999999
                },
                "flashcard": {
                    "used": user.daily_flashcard_count or 0,
                    "limit": flashcard_limit,
                    "remaining": max(0, flashcard_limit - (user.daily_flashcard_count or 0)) if tier == "free" else 999999
                },
                "summary": {
                    "used": user.daily_summary_count or 0,
                    "limit": summary_limit,
                    "remaining": max(0, summary_limit - (user.daily_summary_count or 0)) if tier == "free" else 999999
                }
            }
        }
    finally:
        db.close()


@router.post("/payments/subscribe")
async def subscribe_user(req: SubscribeRequest):
    """Upgrade or downgrade a user's subscription tier."""
    tier = req.tier.strip().lower()
    if tier not in ["free", "standard", "premium"]:
        raise HTTPException(status_code=400, detail="Invalid tier. Choose 'free', 'standard', or 'premium'.")
        
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == req.user_id).first()
        if not user:
            user = User(
                id=req.user_id,
                name=req.user_id,
                username=req.user_id,
                tier=tier,
                xp=0,
                level=1,
                streak=0
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Created new user %s and set tier to %s", req.user_id, tier)
        else:
            user.tier = tier
            # Reset limits on tier change so they can immediately use their new quota
            user.daily_rag_count = 0
            user.daily_quiz_count = 0
            user.daily_summary_count = 0
            user.daily_flashcard_count = 0
            db.commit()
            logger.info("Successfully updated user %s to tier %s", req.user_id, tier)
            
        return {
            "user_id": user.id,
            "tier": user.tier,
            "message": f"Successfully subscribed to {tier.capitalize()} tier."
        }
    finally:
        db.close()
