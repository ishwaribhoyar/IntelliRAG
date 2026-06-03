"""Courses module — service layer."""
import logging
from fastapi import HTTPException

from app.shared.schemas.course import CourseActionRequest, CourseChatRequest
from app.shared.utils.doc_utils import _validate_doc_ready, _ensure_doc_assets_ready
from app.shared.utils.search_utils import format_course_ai_output
from app.query.expander import sanitize_query
from app.core.unified_hierarchy import get_doc_hierarchy, upsert_from_structure, get_node
from app.core.course_structure import ensure_course_structure, split_structure_and_content
from app.retrieval.hybrid import retrieve_for_task
from app.retrieval.mmr import mmr_filter
from app.rag.llm_client import call_llm
from app.gamification.engine import add_xp

logger = logging.getLogger(__name__)


async def handle_course_structure(doc_id: str) -> dict:
    """Return or backfill the course hierarchy for a document."""
    _validate_doc_ready(doc_id)
    await _ensure_doc_assets_ready(doc_id)
    data = get_doc_hierarchy(doc_id)
    if (not data.get("structure")) or (len(data.get("node_content", {})) == 0):
        legacy = ensure_course_structure(doc_id)
        if legacy.get("structure"):
            upsert_from_structure(doc_id, legacy.get("structure", []), subject="General Studies")
            data = get_doc_hierarchy(doc_id)
            if data.get("structure"):
                return data
        return split_structure_and_content(legacy)
    return data


async def handle_course_action(req: CourseActionRequest) -> dict:
    """Run a summarize or explain action on a course section."""
    _validate_doc_ready(req.doc_id)
    await _ensure_doc_assets_ready(req.doc_id)

    action = (req.action or "").strip().lower()
    if action not in ("summarize", "explain"):
        raise HTTPException(400, "action must be 'summarize' or 'explain'")

    node = get_node(req.doc_id, req.node_id)
    if not node:
        raise HTTPException(404, "Section not found")

    node_heading = node.get("title", "Section")
    node_content = (node.get("content") or "").strip()
    if not node_content:
        raise HTTPException(400, "This section has no content to process")

    if action == "summarize":
        prompt = (
            "You are a teaching assistant. Produce clean markdown with this exact structure:\n"
            "## Quick Summary\n"
            "- 4 to 7 bullet points, each one line\n"
            "## Important Terms\n"
            "- 3 to 6 key terms with short meaning\n"
            "## Key Takeaways\n"
            "- 2 to 4 concise exam-ready takeaways\n\n"
            "Rules: keep language simple, avoid fluff, avoid repeating the same idea."
        )
    else:
        prompt = (
            "You are a teaching mentor. Produce clean markdown with this exact structure:\n"
            "## Concept Overview\n"
            "- 2 to 4 lines plain-language overview\n"
            "## Step-by-Step Explanation\n"
            "- 5 to 9 ordered or bullet steps\n"
            "## Worked Intuition / Example\n"
            "- Give one short intuitive example\n"
            "## Common Mistakes\n"
            "- 3 to 5 common errors students make\n"
            "## Revision Points\n"
            "- 3 to 5 quick revision bullets\n\n"
            "Rules: simple wording, technically correct, no unrelated theory."
        )

    result = await call_llm(
        req.doc_id, f"course_{action}", prompt,
        f"Section: {node_heading}\n\nContent:\n{node_content}",
        llm_variant=req.llm_variant,
    )
    raw = result.get("answer", "")
    answer = format_course_ai_output(raw, action, node_heading)
    return {"action": action, "node_id": req.node_id, "answer": answer}


async def handle_course_chat(req: CourseChatRequest) -> dict:
    """Context-aware course chat: section context + full doc fallback."""
    _validate_doc_ready(req.doc_id)
    await _ensure_doc_assets_ready(req.doc_id)

    q = sanitize_query(req.question or "")
    if not q:
        raise HTTPException(400, "Invalid or empty query")

    node = get_node(req.doc_id, req.node_id) if req.node_id else None
    section_heading = node.get("title", "") if node else ""
    section_content = (node.get("content") or "") if node else ""

    retrieved = await retrieve_for_task(req.doc_id, q, task_type="ask")
    retrieved = mmr_filter(retrieved, max_chunks=4)
    full_doc_context = "\n\n".join(c.get("text", "") for c in retrieved if c.get("text"))

    prompt = (
        "You are an AI mentor for a course page.\n"
        "Priority rules:\n"
        "1) Prefer answering using current section context if it is relevant.\n"
        "2) If section context is insufficient, use full document context.\n"
        "3) If answer is not available, clearly say what is missing.\n"
        "Be concise and learner-friendly."
    )
    context = (
        f"Current section title: {section_heading or 'None'}\n\n"
        f"Current section content:\n{section_content[:3500] if section_content else 'Not selected'}\n\n"
        f"Additional document context:\n{full_doc_context[:3500] if full_doc_context else 'None'}\n\n"
        f"Question: {q}"
    )

    result = await call_llm(req.doc_id, "course_chat", prompt, context, llm_variant=req.llm_variant)
    await add_xp(req.user_id, "ask")
    return {"answer": result.get("answer", ""), "node_id": req.node_id, "section": section_heading}
