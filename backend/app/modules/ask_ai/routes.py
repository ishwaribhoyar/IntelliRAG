"""Ask AI module — routes."""
import logging
from fastapi import APIRouter, HTTPException

from app.shared.schemas.ask import AskRequest, MentorRequest
from app.modules.ask_ai.service import handle_ask, handle_mentor
from app.shared.utils.rate_limiter import check_and_update_rate_limit
from app.shared.database import SessionLocal, User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Ask AI"])


@router.post("/ask")
async def ask_question(req: AskRequest):
    """RAG Q&A across the user's entire document library."""
    text = (req.query or req.question or "").strip()
    if not text:
        raise HTTPException(400, "Provide `query` or `question`")
    if len(text) < 3:
        raise HTTPException(400, "Please enter a valid question")
    
    # Enforce premium-only check for multi-PDF cross-document library-wide queries
    if not req.doc_id:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == req.user_id).first()
            if not user or (user.tier or "free").strip().lower() != "premium":
                raise HTTPException(
                    status_code=403,
                    detail="Multi-PDF cross-document reasoning is a Premium-only feature. Upgrade to Premium to search across your entire library."
                )
        finally:
            db.close()
            
    # Enforce free tier daily rate limits
    check_and_update_rate_limit(req.user_id, "rag")
    
    return await handle_ask(req, text)


@router.post("/mentor")
async def mentor_chat(req: MentorRequest):
    """AI Mentor mode — context-aware chat for a document."""
    # Enforce premium-only restriction for AI Study Coach (Mentor Chat)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == req.user_id).first()
        if not user or (user.tier or "free").strip().lower() != "premium":
            raise HTTPException(
                status_code=403,
                detail="AI Study Coach (Mentor Chat) is a Premium-only feature. Upgrade to Premium to unlock."
            )
    finally:
        db.close()
        
    return await handle_mentor(req)

