"""
features.gamification
======================
Top-level feature: Gamification

Business capability: Drive learner engagement through XP awards, level
progression, leaderboards, badges, and activity streak tracking.

Sub-features mapped to existing modules
-----------------------------------------
xp               → app.gamification.engine      (XP award and user stats)
levels           → app.gamification.levels      (level thresholds)
leaderboard      → app.gamification.leaderboard (leaderboard cache + routes)
activity_tracking→ app.gamification.engine      (activity event logging)
badges           → (stub — future)
streaks          → (stub — future)
rewards          → (stub — future)
"""

from app.modules.gamification.routes import router as gamification_router  # noqa: F401
from app.gamification.leaderboard import get_leaderboard                   # noqa: F401
from app.gamification.levels import get_level, xp_for_next_level           # noqa: F401

__all__ = [
    "gamification_router",
    "get_leaderboard",
    "get_level",
    "xp_for_next_level",
]
