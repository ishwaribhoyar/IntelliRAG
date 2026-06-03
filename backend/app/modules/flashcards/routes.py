"""Flashcards/Generate module — routes."""
import logging
from fastapi import APIRouter, HTTPException

from app.shared.schemas.generate import GenerateRequest
from app.modules.flashcards.service import handle_generate
from app.shared.utils.rate_limiter import check_and_update_rate_limit
from app.shared.database import SessionLocal, User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Flashcards & Content"])

VALID_CONTENT_TYPES = [
    "flashcards", "summary", "slides", "fun_facts",
    "mock_test", "rapid_fire", "true_false", "fill_blanks",
]


@router.post("/generate")
async def generate(req: GenerateRequest):
    """Generate content: flashcards, summary, slides, fun_facts, etc."""
    if req.content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(400, f"Invalid content type. Must be one of: {VALID_CONTENT_TYPES}")
    
    # Restrict mock_test to premium
    if req.content_type == "mock_test":
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == req.user_id).first()
            if not user or (user.tier or "free").strip().lower() != "premium":
                raise HTTPException(
                    status_code=403,
                    detail="Exam-style Mock Tests are a Premium-only feature. Upgrade to Premium to unlock."
                )
        finally:
            db.close()

    # Rate limiting checks based on content type
    if req.content_type == "flashcards":
        check_and_update_rate_limit(req.user_id, "flashcard")
    elif req.content_type == "summary":
        check_and_update_rate_limit(req.user_id, "summary")
    elif req.content_type in ("mock_test", "rapid_fire", "true_false", "fill_blanks"):
        check_and_update_rate_limit(req.user_id, "quiz")
        
    return await handle_generate(req)

