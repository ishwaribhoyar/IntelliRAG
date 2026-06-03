"""Flashcards/Generate module — service layer."""
import logging

from app.shared.schemas.generate import GenerateRequest
from app.shared.utils.doc_utils import _validate_doc_ready, _ensure_doc_assets_ready
from app.generators.content import generate_content
from app.gamification.engine import add_xp

logger = logging.getLogger(__name__)


async def handle_generate(req: GenerateRequest) -> dict:
    """Generate educational content from a document."""
    _validate_doc_ready(req.doc_id)
    await _ensure_doc_assets_ready(req.doc_id)
    result = await generate_content(
        req.doc_id,
        req.content_type,
        req.query,
        llm_variant=req.llm_variant,
        refresh=bool(req.refresh),
        previous_output=req.previous_output,
        source_chunk_ids=list(req.source_chunk_ids) if req.source_chunk_ids else None,
    )
    await add_xp(req.user_id, "ask")
    return result
