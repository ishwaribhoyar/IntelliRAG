"""Gamification module — routes."""
import logging
from fastapi import APIRouter, Query

from app.gamification.leaderboard import get_leaderboard
from app.gamification.engine import get_user_score

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Gamification"])


@router.get("/leaderboard")
async def leaderboard(limit: int = Query(20, ge=1, le=100)):
    """Return the daily XP leaderboard."""
    return {"leaderboard": get_leaderboard(limit)}


@router.get("/score")
async def score(user_id: str = "default_user"):
    """Return a user's XP score and level."""
    return await get_user_score(user_id)
