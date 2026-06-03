"""Upload Pipeline module — service layer.

All upload business logic extracted from the monolithic routes.py.
Logic is 100% identical; only organization has changed.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import (
    ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE_MB, UPLOAD_DIR,
    MAX_INGEST_QUEUE_SIZE, FAISS_INDEX_DIR, CHUNKS_DIR,
)
from app.shared.database import SessionLocal, Document
from app.shared.utils.doc_utils import _doc_progress, _ensure_auto_classified
from app.state import faiss_indexes, chunk_store, bm25_indexes, generated_cache
from app.tasks.pipeline_queue import enqueue_pipeline_job, queue_stats, get_doc_queue_info
from app.gamification.engine import add_xp

logger = logging.getLogger(__name__)


async def handle_single_upload(file: UploadFile, user_id: str) -> JSONResponse:
    """Process single file upload with deduplication and cloning."""
    start = time.time()

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(400, f"File too large. Max: {MAX_UPLOAD_SIZE_MB}MB")

    original_filename = file.filename or "document"
    file_hash = hashlib.md5(contents).hexdigest()
    import uuid
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"

    db = SessionLocal()
    try:
        # Check if THIS USER already has this exact file
        existing_for_user = db.query(Document).filter(
            Document.file_hash == file_hash,
            Document.user_id == user_id,
        ).first()
        logger.info(
            "UPLOAD DEBUG: user_id=%s, hash=%s, existing_for_user=%s",
            user_id, file_hash[:12],
            existing_for_user.doc_id if existing_for_user else None,
        )
        if existing_for_user and existing_for_user.status == "ready":
            if not existing_for_user.filename:
                existing_for_user.filename = original_filename
                db.commit()
            await _ensure_auto_classified(existing_for_user.doc_id, existing_for_user.filename or original_filename)
            await add_xp(user_id, "upload")
            return JSONResponse({
                "doc_id": existing_for_user.doc_id, "status": "ready",
                "filename": existing_for_user.filename or original_filename,
                "message": "Document already processed", "duplicate": True,
            })

        # Check if ANOTHER user has this file (reuse processing)
        existing_other = db.query(Document).filter(
            Document.file_hash == file_hash,
            Document.status == "ready",
        ).first()
    finally:
        db.close()

    file_path = UPLOAD_DIR / f"{doc_id}{ext}"
    with open(file_path, "wb") as f:
        f.write(contents)

    if existing_other:
        return await _clone_from_existing(
            doc_id, user_id, original_filename, file_hash, existing_other, file_path, ext
        )

    # Brand new document — process from scratch
    db = SessionLocal()
    try:
        doc = Document(
            doc_id=doc_id, user_id=user_id, filename=original_filename,
            file_hash=file_hash, status="processing", processing_stage="uploaded",
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()

    try:
        await enqueue_pipeline_job(doc_id, str(file_path), file_size_mb=size_mb)
    except asyncio.QueueFull:
        _mark_doc_failed(doc_id, f"Ingestion queue is full (max={MAX_INGEST_QUEUE_SIZE}). Please try again later.")
        raise HTTPException(429, "Ingestion queue is full. Please try again later.")

    await add_xp(user_id, "upload")
    latency = round(time.time() - start, 3)
    logger.info("Upload accepted: doc_id=%s, filename=%s, latency=%ss", doc_id, original_filename, latency)
    return JSONResponse({
        "doc_id": doc_id, "status": "processing",
        "filename": original_filename,
        "message": "Document upload accepted, queued for processing",
    })


async def _clone_from_existing(
    doc_id: str, user_id: str, original_filename: str, file_hash: str,
    existing_other: Document, file_path: Path, ext: str,
) -> JSONResponse:
    """Clone artifacts from an existing processed document for a new user."""
    source_id = existing_other.doc_id
    logger.info("Cloning processed data from %s for user %s", source_id, user_id)

    if source_id in faiss_indexes:
        faiss_indexes[doc_id] = faiss_indexes[source_id]
    if source_id in chunk_store:
        chunk_store[doc_id] = chunk_store[source_id]
    if source_id in bm25_indexes:
        bm25_indexes[doc_id] = bm25_indexes[source_id]
    if source_id in generated_cache:
        generated_cache[doc_id] = generated_cache[source_id]

    for src_path, dst_path in [
        (FAISS_INDEX_DIR / f"{source_id}.index", FAISS_INDEX_DIR / f"{doc_id}.index"),
        (CHUNKS_DIR / f"{source_id}.json", CHUNKS_DIR / f"{doc_id}.json"),
        (CHUNKS_DIR / f"{source_id}_bm25.json", CHUNKS_DIR / f"{doc_id}_bm25.json"),
    ]:
        if src_path.exists() and not dst_path.exists():
            shutil.copy2(src_path, dst_path)

    import uuid
    from datetime import datetime, timezone
    db = SessionLocal()
    try:
        doc = Document(
            doc_id=doc_id, user_id=user_id, filename=original_filename,
            file_hash=file_hash, status="ready", processing_stage="indexed",
        )
        doc.processed_time = datetime.now(timezone.utc)
        db.add(doc)
        db.commit()
    finally:
        db.close()

    await add_xp(user_id, "upload")
    await _ensure_auto_classified(doc_id, original_filename)
    return JSONResponse({
        "doc_id": doc_id, "status": "ready",
        "filename": original_filename,
        "message": "Document processed (shared data)",
    })


def _mark_doc_failed(doc_id: str, error_msg: str) -> None:
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.doc_id == doc_id).first()
        if doc:
            doc.status = "failed"
            doc.error_message = error_msg
            doc.last_error = error_msg
            db.commit()
    finally:
        db.close()


async def handle_multi_upload(incoming_files: list[UploadFile], user_id: str) -> dict:
    """Handle batch upload of multiple files."""
    accepted = []
    rejected = []
    import uuid
    db = SessionLocal()
    try:
        for file in incoming_files:
            ext = Path(file.filename or "").suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                rejected.append({"filename": file.filename, "error": f"Invalid type: {ext}"})
                continue

            contents = await file.read()
            size_mb = len(contents) / (1024 * 1024)
            if size_mb > MAX_UPLOAD_SIZE_MB:
                rejected.append({"filename": file.filename, "error": f"File too large (> {MAX_UPLOAD_SIZE_MB}MB)"})
                continue

            original_filename = file.filename or "document"
            file_hash = hashlib.md5(contents).hexdigest()
            existing = db.query(Document).filter(
                Document.file_hash == file_hash,
                Document.user_id == user_id,
            ).first()
            if existing and existing.status in ("ready", "partially_ready", "processing"):
                accepted.append({
                    "doc_id": existing.doc_id,
                    "filename": existing.filename or original_filename,
                    "status": existing.status,
                    "processing_stage": existing.processing_stage,
                    "duplicate": True,
                })
                continue

            doc_id = f"doc_{uuid.uuid4().hex[:12]}"
            file_path = UPLOAD_DIR / f"{doc_id}{ext}"
            with open(file_path, "wb") as f:
                f.write(contents)

            doc = Document(
                doc_id=doc_id, user_id=user_id, filename=original_filename,
                file_hash=file_hash, status="processing", processing_stage="uploaded",
            )
            db.add(doc)
            doc_entry = {
                "doc_id": doc_id, "filename": original_filename,
                "status": "queued", "processing_stage": "uploaded", "duplicate": False,
            }
            try:
                await enqueue_pipeline_job(doc_id, str(file_path), file_size_mb=size_mb)
                accepted.append(doc_entry)
            except asyncio.QueueFull:
                err = f"Ingestion queue is full (max={MAX_INGEST_QUEUE_SIZE}). Please try again later."
                doc.status = "failed"
                doc.error_message = err
                doc.last_error = err
                rejected.append({"filename": original_filename, "doc_id": doc_id, "error": err})
                continue
        db.commit()
    finally:
        db.close()

    if accepted:
        await add_xp(user_id, "upload")
    return {
        "user_id": user_id,
        "accepted_files": accepted,
        "rejected_files": rejected,
        "queue_status": queue_stats(),
        "accepted": accepted,
        "rejected": rejected,
        "queue": queue_stats(),
    }


async def get_doc_status(doc_id: str) -> dict:
    """Return processing status for a single document."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.doc_id == doc_id).first()
        if not doc:
            raise HTTPException(404, "Document not found")
        queue_info = await get_doc_queue_info(doc_id)
        return {
            "doc_id": doc.doc_id, "status": doc.status,
            "processing_stage": doc.processing_stage,
            "progress": _doc_progress(doc), "error": doc.error_message,
            "retry_count": doc.retry_count, "last_error": doc.last_error,
            "queue_position": queue_info.get("doc_position_in_queue") if queue_info else None,
            "estimated_wait": queue_info.get("estimated_wait") if queue_info else None,
        }
    finally:
        db.close()


async def get_user_status(user_id: str) -> dict:
    """Return processing overview for all documents of a user."""
    db = SessionLocal()
    try:
        docs = (
            db.query(Document)
            .filter(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .all()
        )
        items = []
        for d in docs:
            queue_info = await get_doc_queue_info(d.doc_id)
            items.append({
                "doc_id": d.doc_id, "filename": d.filename or d.doc_id,
                "status": d.status, "processing_stage": d.processing_stage,
                "progress": _doc_progress(d), "error": d.error_message,
                "retry_count": d.retry_count, "last_error": d.last_error,
                "queue_position": queue_info.get("doc_position_in_queue") if queue_info else None,
                "estimated_wait": queue_info.get("estimated_wait") if queue_info else None,
            })
        summary = {
            "processing": sum(1 for d in docs if d.status == "processing"),
            "queued": sum(1 for d in docs if d.status == "processing" and (d.processing_stage or "uploaded") == "uploaded"),
            "completed": sum(1 for d in docs if d.status == "ready"),
            "partially_ready": sum(1 for d in docs if d.status == "partially_ready"),
            "failed": sum(1 for d in docs if d.status == "failed"),
        }
        return {"user_id": user_id, "summary": summary, "queue": queue_stats(), "documents": items}
    finally:
        db.close()


async def retry_failed_doc(doc_id: str) -> dict:
    """Re-queue a failed document for processing."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.doc_id == doc_id).first()
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc.status != "failed":
            raise HTTPException(400, "Document is not in failed state")

        next_retry = (doc.retry_count or 0) + 1
        doc.status = "processing"
        doc.processing_stage = "uploaded"
        doc.error_message = None
        doc.last_error = None
        doc.retry_count = next_retry
        db.commit()
    finally:
        db.close()

    source_file = None
    for ext in ALLOWED_EXTENSIONS:
        candidate = UPLOAD_DIR / f"{doc_id}{ext}"
        if candidate.exists():
            source_file = candidate
            break

    if not source_file:
        raise HTTPException(404, "Source file not found in uploads folder")

    file_size_mb = source_file.stat().st_size / (1024 * 1024)
    try:
        await enqueue_pipeline_job(doc_id, str(source_file), file_size_mb=file_size_mb)
    except asyncio.QueueFull:
        _mark_doc_failed(doc_id, f"Ingestion queue is full (max={MAX_INGEST_QUEUE_SIZE}).")
        raise HTTPException(429, "Ingestion queue is full. Please try again later.")

    return {"status": "requeued", "doc_id": doc_id, "retry_count": next_retry}


async def list_docs_for_user(user_id: str) -> dict:
    """List all documents for a user with queue info."""
    db = SessionLocal()
    try:
        docs = (
            db.query(Document)
            .filter(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .all()
        )
        items = []
        for doc in docs:
            queue_info = await get_doc_queue_info(doc.doc_id)
            items.append({
                "doc_id": doc.doc_id,
                "filename": doc.filename or doc.doc_id,
                "status": doc.status,
                "processing_stage": doc.processing_stage,
                "progress": _doc_progress(doc),
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "error": doc.error_message,
                "retry_count": doc.retry_count,
                "last_error": doc.last_error,
                "queue_position": queue_info.get("doc_position_in_queue") if queue_info else None,
                "estimated_wait": queue_info.get("estimated_wait") if queue_info else None,
            })
        return {"queue": queue_stats(), "documents": items}
    finally:
        db.close()


async def serve_pdf_file(doc_id: str):
    """Serve uploaded PDF for in-app viewing."""
    from app.shared.utils.doc_utils import _validate_doc_ready
    _validate_doc_ready(doc_id)
    for ext in ALLOWED_EXTENSIONS:
        file_path = UPLOAD_DIR / f"{doc_id}{ext}"
        if file_path.exists():
            media = "application/pdf" if ext == ".pdf" else "application/octet-stream"
            return FileResponse(
                path=str(file_path), media_type=media,
                filename=f"{doc_id}{ext}",
                headers={"Content-Disposition": f'inline; filename="{doc_id}{ext}"'},
            )
    raise HTTPException(404, "PDF file not found")


async def delete_document_all(doc_id: str) -> dict:
    """Delete a document and all associated data (indexes, chunks, cache, DB rows).

    This is a hard delete — all artifacts are permanently removed.
    Equivalent to the DELETE /doc/{doc_id} handler in the legacy routes.py.
    """
    from app.state import doc_locks, llm_cache
    from app.indexing.vector_index import delete_vector_index
    from app.indexing.bm25_index import delete_bm25_index
    from app.generators.cache import clear_cached
    from app.core.library import remove_from_library
    from app.core.course_structure import delete_course_structure
    from app.core.unified_hierarchy import delete_doc_hierarchy
    from app.shared.database import Attempt

    # 1. Remove vector and BM25 indexes
    await delete_vector_index(doc_id)
    delete_bm25_index(doc_id)
    await clear_cached(doc_id)

    # 2. Clear in-memory LLM cache for this doc
    async with doc_locks[doc_id]:
        keys_to_remove = [k for k in llm_cache if k[0] == doc_id]
        for k in keys_to_remove:
            del llm_cache[k]

    # 3. Clear BM25 in-memory store
    bm25_indexes.pop(doc_id, None)

    # 4. Delete raw uploaded file(s)
    import gc
    import time
    for ext in ALLOWED_EXTENSIONS:
        file_path = UPLOAD_DIR / f"{doc_id}{ext}"
        if file_path.exists():
            gc.collect()
            deleted = False
            for attempt in range(5):
                try:
                    file_path.unlink()
                    deleted = True
                    break
                except PermissionError:
                    gc.collect()
                    time.sleep(0.2)
            if not deleted:
                logger.warning(
                    "Could not delete locked file %s (being used by another process). Proceeding with database cleanup.",
                    file_path
                )

    # 5. Remove from content library and course hierarchy
    remove_from_library(doc_id)
    delete_course_structure(doc_id)
    delete_doc_hierarchy(doc_id)

    # 6. Hard-delete DB rows
    db = SessionLocal()
    try:
        db.query(Document).filter(Document.doc_id == doc_id).delete()
        db.query(Attempt).filter(Attempt.doc_id == doc_id).delete()
        db.commit()
    finally:
        db.close()

    logger.info("Document %s permanently deleted.", doc_id)
    return {"status": "deleted", "doc_id": doc_id}

