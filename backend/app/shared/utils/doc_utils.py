"""Shared utilities — document lifecycle helpers.

Extracted from api/routes.py to break the circular import with rag/user_ask.py.
All logic is identical to the original; only the location changed.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from fastapi import HTTPException

from app.config import ALLOWED_EXTENSIONS, UPLOAD_DIR, FAISS_INDEX_DIR, CHUNKS_DIR
from app.database import SessionLocal, Document, CourseNode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Progress mapping
# ---------------------------------------------------------------------------

_STAGE_PROGRESS = {
    "uploaded": 20,
    "parsed": 20,
    "structured": 40,
    "embedded": 70,
    "indexed": 100,
}


def _doc_progress(doc: Document) -> int:
    """Map document stage/status to a 0-100 progress integer."""
    if doc.status == "failed":
        return 0
    if doc.status == "ready":
        return 100
    if doc.status == "partially_ready":
        return 70
    if doc.processing_stage == "embedded":
        return 40
    if doc.processing_stage == "indexed":
        return 70
    return _STAGE_PROGRESS.get(doc.processing_stage or "uploaded", 0)


# ---------------------------------------------------------------------------
# Request validation helpers
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def _log_request(endpoint: str, doc_id: str, query: str = "", cache_hit: bool = False):
    logger.info(
        f"[REQUEST] {endpoint} | doc={doc_id} | query={query[:80]}... | cache_hit={cache_hit}"
    )


def _validate_doc_ready(doc_id: str) -> None:
    """Raise 404/400 if the document is not ready."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.doc_id == doc_id).first()
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc.status == "failed":
            raise HTTPException(400, f"Document processing failed: {doc.error_message}")
        if doc.status == "processing":
            raise HTTPException(400, "Document is still processing")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Doc assets recovery
# ---------------------------------------------------------------------------

async def _ensure_doc_assets_ready(doc_id: str) -> None:
    """Self-heal for old docs: load or rebuild indexes/chunks if missing."""
    from app.state import faiss_indexes, chunk_store
    from app.indexing.builder import load_indexes
    from app.core.course_structure import ensure_course_structure
    from app.core.unified_hierarchy import upsert_from_structure

    async def _course_nodes_exist() -> bool:
        db = SessionLocal()
        try:
            return (
                db.query(CourseNode).filter(CourseNode.doc_id == doc_id).first()
                is not None
            )
        finally:
            db.close()

    async def _backfill_course_nodes_from_chunks():
        legacy = ensure_course_structure(doc_id)
        if not legacy:
            return
        structure = legacy.get("structure", [])
        if not structure:
            return
        upsert_from_structure(doc_id, structure, subject="General Studies")

    if doc_id in faiss_indexes and doc_id in chunk_store:
        if not await _course_nodes_exist():
            await _backfill_course_nodes_from_chunks()
        return

    loaded = await load_indexes(doc_id)
    if loaded and doc_id in chunk_store:
        if not await _course_nodes_exist():
            await _backfill_course_nodes_from_chunks()
        return

    # Rebuild from original upload if artifacts are missing/corrupt.
    source_file = None
    for ext in ALLOWED_EXTENSIONS:
        candidate = UPLOAD_DIR / f"{doc_id}{ext}"
        if candidate.exists():
            source_file = candidate
            break

    if not source_file:
        # Legacy recovery path: clone artifacts from another doc with same file_hash.
        db = SessionLocal()
        try:
            current_doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if current_doc and current_doc.file_hash:
                sibling_docs = (
                    db.query(Document)
                    .filter(
                        Document.file_hash == current_doc.file_hash,
                        Document.doc_id != doc_id,
                        Document.status == "ready",
                    )
                    .all()
                )
                for sibling in sibling_docs:
                    sibling_id = sibling.doc_id
                    sibling_index = FAISS_INDEX_DIR / f"{sibling_id}.index"
                    sibling_chunks = CHUNKS_DIR / f"{sibling_id}.json"
                    sibling_bm25 = CHUNKS_DIR / f"{sibling_id}_bm25.json"
                    if sibling_index.exists() and sibling_chunks.exists():
                        shutil.copy2(sibling_index, FAISS_INDEX_DIR / f"{doc_id}.index")
                        shutil.copy2(sibling_chunks, CHUNKS_DIR / f"{doc_id}.json")
                        if sibling_bm25.exists():
                            shutil.copy2(sibling_bm25, CHUNKS_DIR / f"{doc_id}_bm25.json")
                        logger.warning(
                            "[%s] Recovered artifacts by cloning from sibling doc %s",
                            doc_id,
                            sibling_id,
                        )
                        loaded = await load_indexes(doc_id)
                        if loaded and doc_id in chunk_store:
                            return
        finally:
            db.close()

        raise HTTPException(
            500,
            "Document artifacts are missing and could not be recovered automatically. "
            "Please re-upload this file once to regenerate indexes.",
        )

    logger.warning("[%s] Missing artifacts detected. Rebuilding indexes...", doc_id)
    from app.tasks.background import process_document_pipeline
    await process_document_pipeline(doc_id, str(source_file))


# ---------------------------------------------------------------------------
# Auto-classification
# ---------------------------------------------------------------------------

async def _ensure_auto_classified(doc_id: str, title: str = "") -> None:
    """Ensure a document is present in at least one subject bucket."""
    from app.core.classifier import classify_document
    from app.core.library import add_to_library, get_subjects, get_subject_docs
    from app.core.unified_hierarchy import update_subject_title

    await _ensure_doc_assets_ready(doc_id)

    subjects = get_subjects()
    for subject_info in subjects:
        subject_name = subject_info.get("subject", "")
        docs = get_subject_docs(subject_name)
        if any(d.get("doc_id") == doc_id for d in docs):
            return

    subject = await classify_document(doc_id)
    final_subject = subject if subject else "General Studies"
    if final_subject == "General":
        final_subject = "General Studies"
    add_to_library(doc_id, final_subject, title or doc_id)
    update_subject_title(doc_id, final_subject)
    logger.info("[%s] Auto-classified into '%s'", doc_id, final_subject)
