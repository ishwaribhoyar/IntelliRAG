"""Rate limiter for Freemium tier limits.

Enforces:
- RAG Q&A (Ask AI): 5 requests/day
- Quiz / Mock Tests: 2 requests/day
- Flashcards: 2 requests/day
- Summaries: 2 requests/day
for the "free" tier users.
"""
from datetime import datetime, timezone
import logging
from fastapi import HTTPException
from app.shared.database import SessionLocal, User

logger = logging.getLogger(__name__)

# Daily limits mapping for the free tier
FREE_TIER_LIMITS = {
    "rag": 5,
    "quiz": 2,
    "flashcard": 2,
    "summary": 2,
}

def check_and_update_rate_limit(user_id: str, limit_type: str) -> None:
    """Enforce daily limits for free tier users, resetting them on day boundaries."""
    if not user_id:
        return

    # Normalize limit type
    limit_type = limit_type.strip().lower()
    if limit_type not in FREE_TIER_LIMITS:
        logger.warning("Unknown rate limit type: %s", limit_type)
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            # If user doesn't exist, create a default free user dynamically to allow testing/graceful path
            logger.warning("User %s not found in DB during rate limit check; creating default", user_id)
            user = User(id=user_id, name=user_id, username=user_id, tier="free")
            db.add(user)
            db.commit()
            db.refresh(user)

        tier = (user.tier or "free").strip().lower()
        if tier != "free":
            # Paid tiers (standard/premium) do not have these strict limits enforced here
            return

        # Check day reset (using UTC date YYYY-MM-DD)
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if user.last_request_reset != today_str:
            # Reset daily counts on day boundary
            user.daily_rag_count = 0
            user.daily_quiz_count = 0
            user.daily_summary_count = 0
            user.daily_flashcard_count = 0
            user.last_request_reset = today_str
            logger.info("Resetting daily limits for user %s to today's date %s", user_id, today_str)

        # Get limit and current usage
        limit = FREE_TIER_LIMITS[limit_type]
        if limit_type == "rag":
            current_usage = user.daily_rag_count or 0
        elif limit_type == "quiz":
            current_usage = user.daily_quiz_count or 0
        elif limit_type == "flashcard":
            current_usage = user.daily_flashcard_count or 0
        else:  # summary
            current_usage = user.daily_summary_count or 0

        if current_usage >= limit:
            logger.warning("User %s exceeded daily limit for %s (%d/%d)", user_id, limit_type, current_usage, limit)
            try:
                from app.shared.utils.usage_tracker import track_quota_exhaustion
                track_quota_exhaustion(user_id, limit_type)
            except Exception as ex:
                logger.warning("Failed to track quota exhaustion for %s: %s", user_id, ex)
            raise HTTPException(
                status_code=429,
                detail=f"Daily limit of {limit} reached for {limit_type} on Freemium tier. Upgrade to Premium for unlimited access."
            )

        # Increment usage
        if limit_type == "rag":
            user.daily_rag_count = (user.daily_rag_count or 0) + 1
        elif limit_type == "quiz":
            user.daily_quiz_count = (user.daily_quiz_count or 0) + 1
        elif limit_type == "flashcard":
            user.daily_flashcard_count = (user.daily_flashcard_count or 0) + 1
        else:  # summary
            user.daily_summary_count = (user.daily_summary_count or 0) + 1

        db.commit()
        logger.info("Incremented daily %s count for user %s to %d", limit_type, user_id, current_usage + 1)
    finally:
        db.close()
