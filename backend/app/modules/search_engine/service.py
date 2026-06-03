"""Search Engine module — service layer."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import HTTPException

from app.config import CHUNKS_DIR
from app.shared.schemas.search import SearchRequest, UserSearchRequest
from app.shared.database import SessionLocal, Document
from app.shared.utils.doc_utils import _validate_doc_ready, _ensure_doc_assets_ready
from app.shared.utils.search_utils import (
    get_subtopic_by_title, normalize_search_item,
)
from app.query.expander import sanitize_query
from app.search.engine import search
from app.search.spell import suggest_autocomplete, suggest_autocomplete_user
from app.core.unified_hierarchy import get_doc_breadcrumb_map
from app.gamification.engine import add_xp

logger = logging.getLogger(__name__)


async def handle_search(req: SearchRequest) -> dict:
    """Execute document-scoped search and normalize results."""
    _validate_doc_ready(req.doc_id)
    await _ensure_doc_assets_ready(req.doc_id)

    clean_q = sanitize_query(req.query)
    if not clean_q:
        raise HTTPException(400, "Invalid or empty query")

    result = await search(req.doc_id, clean_q, mode=req.mode, user_id=req.user_id, llm_variant=req.llm_variant)

    if isinstance(result, dict) and isinstance(result.get("results"), list):
        breadcrumb_map = get_doc_breadcrumb_map(req.doc_id)
        subtopic_by_title = await get_subtopic_by_title(req.doc_id)
        db = SessionLocal()
        doc = db.query(Document).filter(Document.doc_id == req.doc_id).first()
        filename = doc.filename if doc and doc.filename else req.doc_id
        db.close()
        result["results"] = [
            normalize_search_item(item, req.doc_id, filename, breadcrumb_map, subtopic_by_title)
            for item in result["results"]
        ]

    await add_xp(req.user_id, "ask")
    return result


async def handle_user_search(req: UserSearchRequest) -> dict:
    """Execute user-scoped search across all documents."""
    clean_q = sanitize_query(req.query)
    if not clean_q:
        raise HTTPException(400, "Invalid or empty query")

    db = SessionLocal()
    try:
        docs = (
            db.query(Document)
            .filter(Document.user_id == req.user_id, Document.status.in_(["ready", "partially_ready"]))
            .order_by(Document.created_at.desc())
            .all()
        )
    finally:
        db.close()

    if not docs:
        return {"mode": req.mode, "results": [], "query": clean_q, "user_id": req.user_id}

    merged: list[dict] = []
    did_you_mean = None
    original_query = clean_q

    for doc in docs:
        penalty = 0.75 if doc.status == "partially_ready" else 1.0
        try:
            await _ensure_doc_assets_ready(doc.doc_id)
            r = await search(doc.doc_id, clean_q, mode=req.mode, user_id=req.user_id)
            if not did_you_mean and r.get("did_you_mean"):
                did_you_mean = r.get("did_you_mean")
                original_query = r.get("original_query", clean_q)
            breadcrumb_map = get_doc_breadcrumb_map(doc.doc_id)
            subtopic_by_title = await get_subtopic_by_title(doc.doc_id)
            for it in r.get("results", []):
                normalized = normalize_search_item(it, doc.doc_id, doc.filename or doc.doc_id, breadcrumb_map, subtopic_by_title)
                if penalty != 1.0:
                    normalized["score"] = normalized.get("score", 0) * penalty
                merged.append(normalized)
        except Exception:
            logger.warning("[search/user] failed on doc=%s", doc.doc_id, exc_info=True)

    merged.sort(key=lambda x: x.get("score", 0), reverse=True)
    out = {
        "mode": req.mode, "query": clean_q, "user_id": req.user_id,
        "results": merged[: max(1, req.limit)],
    }
    if did_you_mean:
        out["did_you_mean"] = did_you_mean
        out["original_query"] = original_query
    await add_xp(req.user_id, "ask")
    return out


async def handle_suggest(doc_id: str, q: str, limit: int) -> dict:
    """Return autocomplete suggestions for a document."""
    _validate_doc_ready(doc_id)
    await _ensure_doc_assets_ready(doc_id)
    suggestions = suggest_autocomplete(q, doc_id, limit=limit)
    return {"doc_id": doc_id, "query": q, "suggestions": suggestions}


async def handle_user_suggest(user_id: str, q: str, limit: int) -> dict:
    """Return user-scoped autocomplete suggestions."""
    suggestions = suggest_autocomplete_user(q, user_id=user_id, limit=limit)
    return {"user_id": user_id, "query": q, "suggestions": suggestions}


async def handle_node_chunks(doc_id: str, node_id: str, user_id: str) -> dict:
    """Return chunks for a specific hierarchy node."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.doc_id == doc_id, Document.user_id == user_id).first()
        if not doc:
            raise HTTPException(404, "Document not found")
    finally:
        db.close()

    if not node_id:
        raise HTTPException(400, "Missing node_id")

    chunks_path = Path(CHUNKS_DIR) / f"{doc_id}.json"
    if not chunks_path.exists():
        return {"doc_id": doc_id, "node_id": node_id, "chunks": []}

    try:
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    except Exception:
        chunks = []

    from app.shared.utils.search_utils import expected_subtopic_title, pick_node_id
    subtopic_by_title = await get_subtopic_by_title(doc_id)
    out = []
    for c in chunks or []:
        cid = c.get("chunk_id", "") or ""
        text = c.get("text", "") or ""
        page = int(c.get("page", 1) or 1)
        sec_title = (c.get("section", "") or "").strip()
        exp_title = expected_subtopic_title(sec_title, subtopic_by_title)
        candidate = subtopic_by_title.get(exp_title, [])
        mapped_node_id = pick_node_id(candidate, page) if exp_title else ""
        if mapped_node_id == node_id and cid:
            out.append({"chunk_id": cid, "text": text, "page": page, "node_id": node_id})

    return {"doc_id": doc_id, "node_id": node_id, "chunks": out}
