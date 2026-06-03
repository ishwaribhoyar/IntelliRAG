"""Quiz module — service layer."""
import logging
from fastapi import HTTPException

from app.shared.schemas.quiz import QuizStartRequest, QuizSubmitRequest
from app.shared.database import SessionLocal, Attempt
from app.shared.utils.doc_utils import _validate_doc_ready, _ensure_doc_assets_ready
from app.generators.quiz import generate_quiz, evaluate_quiz
from app.personalization.tracker import record_quiz_results, record_quiz_answer_logs
from app.gamification.engine import add_xp, get_user_score

logger = logging.getLogger(__name__)


async def handle_quiz_start(req: QuizStartRequest) -> dict:
    """Generate adaptive quiz questions for a document."""
    _validate_doc_ready(req.doc_id)
    await _ensure_doc_assets_ready(req.doc_id)
    return await generate_quiz(
        req.doc_id,
        req.quiz_type,
        user_id=req.user_id,
        llm_variant=req.llm_variant,
        refresh=bool(req.refresh),
        previous_output=req.previous_output,
        source_chunk_ids=list(req.source_chunk_ids) if req.source_chunk_ids else None,
    )


async def handle_quiz_submit(req: QuizSubmitRequest) -> dict:
    """Grade quiz answers and record performance for personalization."""
    evaluation = evaluate_quiz(req.questions, req.answers)
    qtype = req.quiz_type if req.quiz_type in ("quiz", "mock_test") else "quiz"

    record_quiz_results(req.user_id, evaluation.get("details", []), doc_id=req.doc_id)
    record_quiz_answer_logs(req.user_id, req.doc_id, evaluation.get("details", []), quiz_type=qtype)
    await add_xp(req.user_id, "quiz_complete", correct_count=evaluation["correct"])

    db = SessionLocal()
    try:
        attempt = Attempt(
            user_id=req.user_id, doc_id=req.doc_id, quiz_type=qtype,
            score=evaluation["score"], total=evaluation["total"], accuracy=evaluation["accuracy"],
        )
        db.add(attempt)
        db.commit()
    finally:
        db.close()

    user_score = await get_user_score(req.user_id)
    return {**evaluation, "xp": user_score}
