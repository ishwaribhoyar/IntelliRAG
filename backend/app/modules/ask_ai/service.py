"""Ask AI module — service layer."""
import logging
from fastapi import HTTPException

from app.shared.schemas.ask import AskRequest, MentorRequest
from app.shared.utils.doc_utils import _validate_doc_ready, _ensure_doc_assets_ready
from app.config import normalize_llm_variant as norm_llm_variant
from app.rag.user_ask import ask_ai as ask_user_library_ai
from app.generators.content import ask_mentor
from app.gamification.engine import add_xp

logger = logging.getLogger(__name__)


async def handle_ask(req: AskRequest, text: str) -> dict:
    """Execute the full user-library RAG Ask pipeline."""
    llm_v = norm_llm_variant(req.llm_variant or "30b")
    result = await ask_user_library_ai(
        text,
        req.user_id,
        scope_doc_id=req.doc_id,
        llm_variant=llm_v,
        use_cache=True,
    )
    await add_xp(req.user_id, "ask")

    cd = result.get("confidence_detail")
    label = result.get("confidence")
    if isinstance(label, str):
        result["confidence_label"] = label
    result["confidence"] = cd if isinstance(cd, dict) else {"level": str(label or "medium"), "score": 0.5}
    logger.info("/ask user=%s cached=%s", req.user_id, result.get("cached"))
    return result


async def handle_mentor(req: MentorRequest) -> dict:
    """Execute the AI Mentor chat pipeline."""
    _validate_doc_ready(req.doc_id)
    await _ensure_doc_assets_ready(req.doc_id)
    result = await ask_mentor(req.doc_id, req.question, req.history, llm_variant=req.llm_variant)
    await add_xp(req.user_id, "ask")
    return result
