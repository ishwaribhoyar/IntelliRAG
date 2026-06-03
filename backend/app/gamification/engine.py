"""Gamification engine — XP, levels, streaks with per-user locking and batch writes."""
import logging
from datetime import datetime, timezone
from app.config import (
    XP_UPLOAD, XP_ASK, XP_QUIZ_COMPLETE, XP_CORRECT_ANSWER, XP_DAILY_STREAK
)
from app.state import user_xp_cache, leaderboard_cache, pending_updates, user_locks
from app.database import SessionLocal, User, Leaderboard
from app.gamification.levels import get_level

logger = logging.getLogger(__name__)


def _ensure_user_cache(user_id: str):
    """Load user into cache if not present."""
    if user_id not in user_xp_cache:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user_xp_cache[user_id] = {
                    "xp": user.xp,
                    "level": user.level,
                    "streak": user.streak,
                    "daily_xp": user.daily_xp,
                }
            else:
                # Create new user
                new_user = User(id=user_id, xp=0, level=1, streak=0, daily_xp=0)
                db.add(new_user)
                db.commit()
                user_xp_cache[user_id] = {
                    "xp": 0, "level": 1, "streak": 0, "daily_xp": 0,
                }
                # Also init leaderboard
                lb = Leaderboard(user_id=user_id, daily_xp=0)
                db.add(lb)
                db.commit()
        finally:
            db.close()


async def add_xp(user_id: str, action: str, correct_count: int = 0):
    """Add XP for a user action. Thread-safe via user_locks."""
    async with user_locks[user_id]:
        _ensure_user_cache(user_id)
        cache = user_xp_cache[user_id]

        xp_gained = 0
        if action == "upload":
            xp_gained = XP_UPLOAD
        elif action == "ask":
            xp_gained = XP_ASK
        elif action == "quiz_complete":
            xp_gained = XP_QUIZ_COMPLETE + (correct_count * XP_CORRECT_ANSWER)
        elif action == "correct_answer":
            xp_gained = XP_CORRECT_ANSWER
        elif action == "daily_streak":
            xp_gained = XP_DAILY_STREAK

        cache["xp"] += xp_gained
        cache["daily_xp"] += xp_gained
        cache["level"] = get_level(cache["xp"])

        # Update leaderboard cache
        leaderboard_cache[user_id] = cache["daily_xp"]

        # Queue DB write (batch, not immediate)
        def _write(db):
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.xp = cache["xp"]
                user.level = cache["level"]
                user.daily_xp = cache["daily_xp"]
                user.last_active = datetime.now(timezone.utc)
            lb = db.query(Leaderboard).filter(Leaderboard.user_id == user_id).first()
            if lb:
                lb.daily_xp = cache["daily_xp"]

        pending_updates.append({"fn": _write})

        logger.info(f"User {user_id}: +{xp_gained} XP ({action}), total={cache['xp']}, level={cache['level']}")
        return cache.copy()


async def get_user_score(user_id: str) -> dict:
    """Get user's current score from cache."""
    async with user_locks[user_id]:
        _ensure_user_cache(user_id)
        return user_xp_cache.get(user_id, {}).copy()