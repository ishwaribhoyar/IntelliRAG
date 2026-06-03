"""Quiz module — routes."""
import logging
from fastapi import APIRouter, HTTPException

from app.shared.schemas.quiz import QuizStartRequest, QuizSubmitRequest
from app.modules.quizzes.service import handle_quiz_start, handle_quiz_submit
from app.shared.utils.rate_limiter import check_and_update_rate_limit
from app.shared.database import SessionLocal, User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Quizzes"])


@router.post("/quiz/start")
async def start_quiz(req: QuizStartRequest):
    """Generate a quiz — adaptive: prioritizes weak topics."""
    # Enforce premium-only restriction for mock tests
    if (req.quiz_type or "").strip().lower() == "mock_test":
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

    # Enforce free tier daily rate limits
    check_and_update_rate_limit(req.user_id, "quiz")
    
    return await handle_quiz_start(req)


@router.post("/quiz/submit")
async def submit_quiz(req: QuizSubmitRequest):
    """Submit quiz answers — tracks topic accuracy for personalization."""
    return await handle_quiz_submit(req)

