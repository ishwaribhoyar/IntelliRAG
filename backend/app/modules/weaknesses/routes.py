"""Weaknesses / Personalization module — routes."""
import logging
from fastapi import APIRouter

from app.modules.weaknesses.service import handle_weakness_dashboard

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Personalization"])


@router.get("/weakness/{user_id}")
async def get_weakness_dashboard(user_id: str):
    """Get user's weak topics with AI-generated study insights."""
    return await handle_weakness_dashboard(user_id)
