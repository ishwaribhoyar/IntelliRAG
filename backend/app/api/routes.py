"""API routes — all endpoints with the Advanced RAG pipeline.
Upgraded: hybrid retrieval, search engine mode, personalization, content library.
All existing endpoints preserved + new endpoints added.
"""
import hashlib
import uuid
import time
import logging
import asyncio
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE_MB, UPLOAD_DIR, MAX_INGEST_QUEUE_SIZE
from app.config import FAISS_INDEX_DIR, CHUNKS_DIR
from app.database import SessionLocal, Document, User, Attempt, get_db, CourseNode
from app.state import (
    faiss_indexes, chunk_store, generated_cache, llm_cache,
    doc_locks, leaderboard_cache, bm25_indexes
)
from app.tasks.background import process_document_pipeline
from app.tasks.pipeline_queue import enqueue_pipeline_job, queue_stats, get_doc_queue_info

# New pipeline imports
from app.retrieval.hybrid import retrieve_for_task
from app.retrieval.mmr import mmr_filter
from app.retrieval.context_filter import filter_context
from app.reranker.llm_reranker import rerank_chunks
from app.query.router import route_query
from app.query.expander import sanitize_query
from app.llm.trust import compute_confidence, build_source_citations, should_fallback, FALLBACK_RESPONSE
from app.search.engine import search
from app.search.spell import suggest_autocomplete, suggest_autocomplete_user
from app.personalization.tracker import (
    record_quiz_results, record_quiz_answer_logs, get_weak_topics, get_all_topic_scores
)
from app.personalization.advisor import generate_advice, generate_study_plan
from app.core.library import add_to_library, get_subjects, get_subject_docs, remove_from_library
from app.core.course_structure import (
    ensure_course_structure,
    find_node,
    delete_course_structure,
    split_structure_and_content,
)
from app.core.unified_hierarchy import (
    get_doc_hierarchy,
    get_node,
    delete_doc_hierarchy,
    get_user_library_hierarchy,
    update_subject_title,
    get_doc_breadcrumb_map,
    upsert_from_structure,
)
from app.retrieval.hybrid import compare_retrieval
from app.evaluation.runner import run_evaluation, retrieval_comparison_report, get_latest_report, run_multi_evaluation
from app.reranker.llm_reranker import rerank_chunks, validate_reranker
from app.evaluation.final_report import generate_system_report
from app.chunking.validator import validate_chunks

# Existing imports (still used)
from app.rag.llm_client import call_llm
from app.rag.user_ask import ask_ai as ask_user_library_ai
from app.config import normalize_llm_variant as norm_llm_variant
from app.rag.embedder import get_model
from app.indexing.vector_index import delete_vector_index
from app.indexing.bm25_index import delete_bm25_index
from app.indexing.builder import load_indexes
from app.generators.prompts import get_prompt
from app.generators.quiz import generate_quiz, evaluate_quiz
from app.generators.content import generate_content, ask_mentor
from app.generators.cache import clear_cached
from app.gamification.engine import add_xp, get_user_score
from app.gamification.leaderboard import get_leaderboard

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Request/Response Models ---

class AskRequest(BaseModel):
    """AI Ask over the user’s entire PDF library (retrieval-first RAG)."""
    user_id: str = "default_user"
    query: str = ""
    question: str = ""  # alias for query (backward compatible)
    doc_id: Optional[str] = None  # optional: restrict search to one doc
    stream: bool = False
    llm_variant: Optional[str] = "30b"  # default 30b, switchable to 105b

class QuizStartRequest(BaseModel):
    doc_id: str
    user_id: str = "default_user"
    quiz_type: str = "quiz"
    llm_variant: Optional[str] = "30b"
    refresh: bool = False
    previous_output: Optional[str] = None
    source_chunk_ids: Optional[list] = None

class QuizSubmitRequest(BaseModel):
    doc_id: str
    user_id: str = "default_user"
    questions: list
    answers: list[str]
    quiz_type: str = "quiz"

class GenerateRequest(BaseModel):
    doc_id: str
    content_type: str
    user_id: str = "default_user"
    query: str = ""
    llm_variant: Optional[str] = "30b"
    refresh: bool = False
    previous_output: Optional[str] = None
    source_chunk_ids: Optional[list] = None

class MentorRequest(BaseModel):
    doc_id: str
    question: str
    user_id: str = "default_user"
    history: list = Field(default_factory=list)
    llm_variant: Optional[str] = "30b"

class AuthRequest(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    email: Optional[str] = None

class SearchRequest(BaseModel):
    doc_id: str
    query: str
    mode: str = "auto"  # keyword | hybrid | ai | auto
    user_id: str = "default_user"
    llm_variant: Optional[str] = "30b"


class UserSearchRequest(BaseModel):
    user_id: str
    query: str
    mode: str = "hybrid"
    limit: int = 20

class LibraryAddRequest(BaseModel):
    doc_id: str
    subject: str
    title: str = ""

class LibraryRemoveRequest(BaseModel):
    doc_id: str
    subject: str = ""

class CourseActionRequest(BaseModel):
    doc_id: str
    node_id: str
    action: str  # summarize | explain
    llm_variant: Optional[str] = "30b"

class CourseChatRequest(BaseModel):
    doc_id: str
    question: str
    node_id: str = ""
    user_id: str = "default_user"
    llm_variant: Optional[str] = "30b"


# --- Utility ---

def _log_request(endpoint: str, doc_id: str, query: str = "", cache_hit: bool = False):
    logger.info(f"[REQUEST] {endpoint} | doc={doc_id} | query={query[:80]}... | cache_hit={cache_hit}")

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


_STAGE_PROGRESS = {
    "uploaded": 20,
    "parsed": 20,
    "structured": 40,
    "embedded": 70,
    "indexed": 100,
}


def _doc_progress(doc: Document) -> int:
    # No fake progress: interpret `processing_stage` differently based on `status`.
    if doc.status == "failed":
        return 0
    if doc.status == "ready":
        return 100
    if doc.status == "partially_ready":
        # Embeddings/vector are ready, BM25/indexing may still be in-flight.
        return 70
    # doc.status == "processing"
    if doc.processing_stage == "embedded":
        # Stage `embedded` is reached after chunking; embedding completes later in indexed stage.
        return 40
    if doc.processing_stage == "indexed":
        return 70
    return _STAGE_PROGRESS.get(doc.processing_stage or "uploaded", 0)


_SUBTOPIC_BY_TITLE_CACHE: dict[str, dict[str, list[dict]]] = {}
_SUBTOPIC_BY_TITLE_CACHE_LOCK: asyncio.Lock = asyncio.Lock()


async def _get_subtopic_by_title(doc_id: str) -> dict[str, list[dict]]:
    """Build {subtopic_title: [node...]} lookup for a doc (cached)."""
    if doc_id in _SUBTOPIC_BY_TITLE_CACHE:
        return _SUBTOPIC_BY_TITLE_CACHE[doc_id]

    # Build outside lock quickly if multiple requests race; worst case repeats.
    db = SessionLocal()
    try:
        rows = (
            db.query(CourseNode)
            .filter(CourseNode.doc_id == doc_id, CourseNode.level == "subtopic")
            .order_by(CourseNode.sort_order.asc())
            .all()
        )
    finally:
        db.close()

    by_title: dict[str, list[dict]] = {}
    for r in rows:
        t = (r.title or "").strip()
        by_title.setdefault(t, []).append(
            {"node_id": r.node_id, "title": t, "page": int(r.page or 1)}
        )

    # Cache with a lock to avoid partial writes.
    async with _SUBTOPIC_BY_TITLE_CACHE_LOCK:
        _SUBTOPIC_BY_TITLE_CACHE[doc_id] = by_title
    return by_title


def _expected_subtopic_title(section_title: str, by_title: dict[str, list[dict]]) -> str:
    """Map chunk.section heading → the unified-hierarchy subtopic title."""
    def _norm_title(s: str) -> str:
        return " ".join((s or "").strip().lower().split())

    def _match_title(raw: str) -> str:
        if not raw:
            return ""
        if raw in by_title:
            return raw
        nr = _norm_title(raw)
        for k in by_title.keys():
            if _norm_title(k) == nr:
                return k
        return ""

    sec = (section_title or "").strip()
    if not sec:
        return ""

    details_raw = f"{sec} Details"

    sec_match = _match_title(sec)
    details_match = _match_title(details_raw)

    # Prefer the "Details" subtopic when it's present and plain title isn't.
    if details_match and not sec_match:
        return details_match
    if sec_match:
        return sec_match
    if details_match:
        return details_match
    # Fallback for missing titles: assume Details convention (raw).
    return details_raw


def _pick_node_id(candidates: list[dict], page: int) -> str:
    if not candidates:
        return ""
    for c in candidates:
        if int(c.get("page", 1)) == int(page):
            return c["node_id"]
    # Deterministic fallback: lowest sort_order was used to preserve ordering in candidates.
    return candidates[0]["node_id"]


def _normalize_search_item(
    item: dict,
    doc_id: str,
    filename: str,
    breadcrumb_map: dict[str, str],
    subtopic_by_title: dict[str, list[dict]],
) -> dict:
    section = (item.get("section", "") or "").strip()
    page = int(item.get("page", 1) or 1)

    expected_title = _expected_subtopic_title(section, subtopic_by_title)
    node_id = _pick_node_id(subtopic_by_title.get(expected_title, []), page) if expected_title else ""

    hierarchy_path = breadcrumb_map.get(expected_title, breadcrumb_map.get(section, item.get("hierarchy_path", section)))

    return {
        "doc_id": doc_id,
        "node_id": node_id,
        "chunk_id": item.get("chunk_id", ""),
        "page": page,
        "section_path": hierarchy_path,
        "snippet": item.get("text", "") or item.get("snippet", ""),
        "title": expected_title or section or filename or doc_id,
        "score": item.get("score", 0),
        # backward-compatible keys for existing UI
        "text": item.get("text", "") or item.get("snippet", ""),
        "section": section,
        "hierarchy_path": hierarchy_path,
        "filename": filename or doc_id,
    }


def _format_course_ai_output(answer: str, action: str, heading: str) -> str:
    """Normalize summarize/explain outputs into readable structured markdown."""
    text = (answer or "").strip()
    if not text:
        return "No response generated. Please try again."

    def _clean_lines(src: str) -> list[str]:
        raw_lines = [ln.strip() for ln in src.splitlines() if ln.strip()]
        return [
            ln.replace("**", "").replace("__", "").strip()
            for ln in raw_lines
            if ln.strip()
        ]

    lines = _clean_lines(text)
    if not lines:
        return text

    if action == "summarize":
        has_expected_sections = (
            "## Quick Summary" in text
            and "## Important Terms" in text
            and "## Key Takeaways" in text
        )
        if has_expected_sections:
            return text

        bullets = [f"- {ln.lstrip('- ').strip()}" for ln in lines[:8]]
        return (
            f"## Quick Summary\n"
            f"Section: **{heading}**\n\n"
            + "\n".join(bullets)
            + "\n\n## Important Terms\n- Add key terms from this section with one-line meanings."
            + "\n\n## Key Takeaways\n- Focus on the core definition, process, and examples."
        )

    # explain format
    has_expected_sections = (
        "## Concept Overview" in text
        and "## Step-by-Step Explanation" in text
        and "## Worked Intuition / Example" in text
        and "## Common Mistakes" in text
        and "## Revision Points" in text
    )
    if has_expected_sections:
        return text

    brief = lines[:3]
    details = lines[3:10] if len(lines) > 3 else []
    out = [
        "## Concept Overview",
        f"Section: **{heading}**",
        "",
        *brief,
        "",
        "## Step-by-Step Explanation",
    ]
    if details:
        out.extend([f"- {ln.lstrip('- ').strip()}" for ln in details])
    else:
        out.append("- Expand each idea with definitions, logic, and examples.")
    out.extend([
        "",
        "## Worked Intuition / Example",
        "- Connect this concept to one practical or exam-style scenario.",
        "",
        "## Common Mistakes",
        "- Confusing definition with implementation details.",
        "- Skipping assumptions and constraints in the section.",
        "- Memorizing terms without understanding flow/logic.",
        "",
        "## Revision Points",
        "- Remember the core definition.",
        "- Recall the main steps/process.",
        "- Keep one practical example in mind."
    ])
    return "\n".join(out)


async def _ensure_auto_classified(doc_id: str, title: str = ""):
    """Ensure a document is present in at least one subject bucket."""
    from app.core.classifier import classify_document

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


async def _ensure_doc_assets_ready(doc_id: str):
    """Self-heal for old docs: load or rebuild indexes/chunks if missing."""
    async def _course_nodes_exist() -> bool:
        db = SessionLocal()
        try:
            return db.query(CourseNode).filter(CourseNode.doc_id == doc_id).first() is not None
        finally:
            db.close()

    async def _backfill_course_nodes_from_chunks():
        # Safe recovery for older docs processed before unified hierarchy existed.
        # We derive a lightweight course structure from existing chunk sections,
        # then upsert the unified hierarchy nodes using unified_hierarchy's algorithm.
        from app.core.course_structure import ensure_course_structure
        from app.core.unified_hierarchy import upsert_from_structure

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
                sibling_docs = db.query(Document).filter(
                    Document.file_hash == current_doc.file_hash,
                    Document.doc_id != doc_id,
                    Document.status == "ready",
                ).all()
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
    await process_document_pipeline(doc_id, str(source_file))


# --- AUTH ENDPOINTS ---

@router.post("/register")
async def register(req: AuthRequest):
    """Register a new user."""
    if not req.username or len(req.username) < 5:
        raise HTTPException(400, "Email must be valid")
    if not req.password or len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == req.username).first()
        if existing:
            raise HTTPException(409, "An account with this email already exists")

        user_id = f"user_{uuid.uuid4().hex[:10]}"
        user = User(
            id=user_id,
            name=req.name or req.username,
            email=req.email or req.username,
            username=req.username,
            password_hash=_hash_password(req.password),
        )
        db.add(user)
        db.commit()
        return {"user_id": user_id, "username": user.name or req.username, "message": "Registration successful"}
    finally:
        db.close()


@router.post("/login")
async def login(req: AuthRequest):
    """Login with credentials."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username).first()
        if not user or user.password_hash != _hash_password(req.password):
            raise HTTPException(401, "Invalid email or password")
        return {"user_id": user.id, "username": user.name or user.username, "xp": user.xp, "level": user.level, "streak": user.streak}
    finally:
        db.close()


# --- DOCUMENT ENDPOINTS ---

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form("default_user"),
):
    """Upload and process a document."""
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

    db = SessionLocal()
    try:
        # Check if THIS USER already has this exact file
        existing_for_user = db.query(Document).filter(
            Document.file_hash == file_hash,
            Document.user_id == user_id
        ).first()
        logger.info(f"UPLOAD DEBUG: user_id={user_id}, hash={file_hash[:12]}, existing_for_user={existing_for_user.doc_id if existing_for_user else None}, existing_user_id={existing_for_user.user_id if existing_for_user else None}")
        if existing_for_user and existing_for_user.status == "ready":
            # Update filename if missing
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

        # Check if ANOTHER user has this file (reuse processing, but create new doc for this user)
        existing_other = db.query(Document).filter(
            Document.file_hash == file_hash,
            Document.status == "ready"
        ).first()
    finally:
        db.close()

    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    file_path = UPLOAD_DIR / f"{doc_id}{ext}"
    with open(file_path, "wb") as f:
        f.write(contents)

    # If another user already processed this file, clone the data
    if existing_other:
        source_id = existing_other.doc_id
        logger.info(f"Cloning processed data from {source_id} for user {user_id}")
        # Clone in-memory indexes and chunk data
        if source_id in faiss_indexes:
            faiss_indexes[doc_id] = faiss_indexes[source_id]
        if source_id in chunk_store:
            chunk_store[doc_id] = chunk_store[source_id]
        if source_id in bm25_indexes:
            bm25_indexes[doc_id] = bm25_indexes[source_id]
        if source_id in generated_cache:
            generated_cache[doc_id] = generated_cache[source_id]

        # Ensure on-disk artifacts exist for the NEW doc_id as well.
        # Without this, ready docs can fail retrieval after restart/eviction.
        source_index = FAISS_INDEX_DIR / f"{source_id}.index"
        source_chunks = CHUNKS_DIR / f"{source_id}.json"
        source_bm25 = CHUNKS_DIR / f"{source_id}_bm25.json"

        target_index = FAISS_INDEX_DIR / f"{doc_id}.index"
        target_chunks = CHUNKS_DIR / f"{doc_id}.json"
        target_bm25 = CHUNKS_DIR / f"{doc_id}_bm25.json"

        if source_index.exists() and not target_index.exists():
            shutil.copy2(source_index, target_index)
        if source_chunks.exists() and not target_chunks.exists():
            shutil.copy2(source_chunks, target_chunks)
        if source_bm25.exists() and not target_bm25.exists():
            shutil.copy2(source_bm25, target_bm25)

        logger.info(
            "Clone artifacts status | new_doc=%s index=%s chunks=%s bm25=%s",
            doc_id,
            target_index.exists(),
            target_chunks.exists(),
            target_bm25.exists(),
        )

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

    # Brand new document — process from scratch
    db = SessionLocal()
    try:
        doc = Document(
            doc_id=doc_id, user_id=user_id, filename=original_filename,
            file_hash=file_hash, status="processing", processing_stage="uploaded"
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()

    try:
        await enqueue_pipeline_job(doc_id, str(file_path), file_size_mb=size_mb)
    except asyncio.QueueFull:
        # Reject upload when backpressure limit is hit.
        db = SessionLocal()
        try:
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if doc:
                doc.status = "failed"
                doc.error_message = f"Ingestion queue is full (max={MAX_INGEST_QUEUE_SIZE}). Please try again later."
                doc.last_error = doc.error_message
            db.commit()
        finally:
            db.close()
        raise HTTPException(429, "Ingestion queue is full. Please try again later.")
    await add_xp(user_id, "upload")

    latency = round(time.time() - start, 3)
    logger.info(f"Upload accepted: doc_id={doc_id}, filename={original_filename}, latency={latency}s")
    return JSONResponse({
        "doc_id": doc_id, "status": "processing",
        "filename": original_filename,
        "message": "Document upload accepted, queued for processing"
    })


@router.post("/upload/multi")
async def upload_documents_multi(
    files: list[UploadFile] = File(default_factory=list),
    files_array: list[UploadFile] = File(default_factory=list, alias="files[]"),
    user_id: str = Form("default_user"),
):
    """Queue many PDFs/Excels with per-file status and real pipeline stages."""
    incoming_files = files if files else files_array
    if not incoming_files:
        raise HTTPException(400, "No files uploaded")

    accepted = []
    rejected = []
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
                doc_id=doc_id,
                user_id=user_id,
                filename=original_filename,
                file_hash=file_hash,
                status="processing",
                processing_stage="uploaded",
            )
            db.add(doc)
            doc_entry = {
                "doc_id": doc_id,
                "filename": original_filename,
                "status": "queued",
                "processing_stage": "uploaded",
                "duplicate": False,
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
        # New response keys (frontend expects these)
        "accepted_files": accepted,
        "rejected_files": rejected,
        "queue_status": queue_stats(),
        # Back-compat (older callers/tests may rely on these)
        "accepted": accepted,
        "rejected": rejected,
        "queue": queue_stats(),
    }


@router.get("/status/{doc_id}")
async def get_document_status(doc_id: str):
    """Get document processing status."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.doc_id == doc_id).first()
        if not doc:
            raise HTTPException(404, "Document not found")
        queue_info = await get_doc_queue_info(doc_id)
        return {
            "doc_id": doc.doc_id,
            "status": doc.status,
            "processing_stage": doc.processing_stage,
            "progress": _doc_progress(doc),
            "error": doc.error_message,
            "retry_count": doc.retry_count,
            "last_error": doc.last_error,
            "queue_position": queue_info.get("doc_position_in_queue") if queue_info else None,
            "estimated_wait": queue_info.get("estimated_wait") if queue_info else None,
        }
    finally:
        db.close()


@router.get("/status/user/{user_id}")
async def get_user_processing_status(user_id: str):
    """Per-user processing overview with real stage/progress."""
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(Document.user_id == user_id).order_by(Document.created_at.desc()).all()
        items = []
        for d in docs:
            queue_info = await get_doc_queue_info(d.doc_id)
            items.append({
                "doc_id": d.doc_id,
                "filename": d.filename or d.doc_id,
                "status": d.status,
                "processing_stage": d.processing_stage,
                "progress": _doc_progress(d),
                "error": d.error_message,
                "retry_count": d.retry_count,
                "last_error": d.last_error,
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


@router.post("/retry/{doc_id}")
async def retry_document(doc_id: str):
    """Retry a failed ingestion job by re-queuing it."""
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
        # Keep it failed if we cannot enqueue.
        db = SessionLocal()
        try:
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if doc:
                err = f"Ingestion queue is full (max={MAX_INGEST_QUEUE_SIZE})."
                doc.status = "failed"
                doc.error_message = err
                doc.last_error = err
                db.commit()
        finally:
            db.close()
        raise HTTPException(429, "Ingestion queue is full. Please try again later.")

    return {"status": "requeued", "doc_id": doc_id, "retry_count": next_retry}


# --- AI ENDPOINTS (UPGRADED with hybrid retrieval) ---

@router.post("/ask")
async def ask_question(req: AskRequest):
    """RAG Q&A across the user’s entire document library (hybrid retrieval → optional LLM)."""
    text = (req.query or req.question or "").strip()
    _log_request("/ask", req.doc_id or "all_user_docs", text)
    if not text:
        raise HTTPException(400, "Provide `query` or `question`")
    if len(text) < 3:
        raise HTTPException(400, "Please enter a valid question")

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


@router.post("/mentor")
async def mentor_chat(req: MentorRequest):
    """AI Mentor mode."""
    start = time.time()
    _validate_doc_ready(req.doc_id)
    await _ensure_doc_assets_ready(req.doc_id)
    result = await ask_mentor(req.doc_id, req.question, req.history, llm_variant=req.llm_variant)
    await add_xp(req.user_id, "ask")
    return result


@router.post("/quiz/start")
async def start_quiz(req: QuizStartRequest):
    """Generate a quiz — adaptive: prioritizes weak topics."""
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


@router.post("/quiz/submit")
async def submit_quiz(req: QuizSubmitRequest):
    """Submit quiz answers — now tracks topic accuracy for personalization."""
    evaluation = evaluate_quiz(req.questions, req.answers)

    qtype = req.quiz_type if req.quiz_type in ("quiz", "mock_test") else "quiz"

    # Track topic accuracy (personalization)
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


@router.post("/generate")
async def generate(req: GenerateRequest):
    """Generate content: flashcards, summary, slides, fun_facts, etc."""
    _validate_doc_ready(req.doc_id)
    await _ensure_doc_assets_ready(req.doc_id)

    valid_types = ["flashcards", "summary", "slides", "fun_facts", "mock_test", "rapid_fire", "true_false", "fill_blanks"]
    if req.content_type not in valid_types:
        raise HTTPException(400, f"Invalid content type. Must be one of: {valid_types}")

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


# --- NEW: SEARCH ENGINE ---

@router.post("/search")
async def search_endpoint(req: SearchRequest):
    """Search engine with keyword/hybrid/AI modes."""
    _validate_doc_ready(req.doc_id)
    await _ensure_doc_assets_ready(req.doc_id)

    clean_q = sanitize_query(req.query)
    if not clean_q:
        raise HTTPException(400, "Invalid or empty query")

    result = await search(
        req.doc_id,
        clean_q,
        mode=req.mode,
        user_id=req.user_id,
        llm_variant=req.llm_variant,
    )
    if isinstance(result, dict) and isinstance(result.get("results"), list):
        breadcrumb_map = get_doc_breadcrumb_map(req.doc_id)
        subtopic_by_title = await _get_subtopic_by_title(req.doc_id)
        db = SessionLocal()
        doc = db.query(Document).filter(Document.doc_id == req.doc_id).first()
        filename = doc.filename if doc and doc.filename else req.doc_id
        db.close()
        normalized = []
        for item in result["results"]:
            normalized.append(_normalize_search_item(item, req.doc_id, filename, breadcrumb_map, subtopic_by_title))
        result["results"] = normalized
    await add_xp(req.user_id, "ask")
    return result


@router.get("/search/suggest/{doc_id}")
async def search_suggest(doc_id: str, q: str = Query("", min_length=1), limit: int = Query(8, ge=1, le=20)):
    """Autocomplete suggestions from indexed PDF vocabulary only."""
    _validate_doc_ready(doc_id)
    await _ensure_doc_assets_ready(doc_id)
    suggestions = suggest_autocomplete(q, doc_id, limit=limit)
    return {"doc_id": doc_id, "query": q, "suggestions": suggestions}


@router.get("/search/suggest/user/{user_id}")
async def search_suggest_user(user_id: str, q: str = Query("", min_length=1), limit: int = Query(5, ge=1, le=20)):
    """User-scoped autocomplete suggestions from all ready/partially_ready docs."""
    suggestions = suggest_autocomplete_user(q, user_id=user_id, limit=limit)
    return {"user_id": user_id, "query": q, "suggestions": suggestions}


@router.post("/search/user")
async def search_user_endpoint(req: UserSearchRequest):
    """User-scoped global search across all ready/partially_ready documents."""
    clean_q = sanitize_query(req.query)
    if not clean_q:
        raise HTTPException(400, "Invalid or empty query")

    db = SessionLocal()
    try:
        docs = db.query(Document).filter(
            Document.user_id == req.user_id,
            Document.status.in_(["ready", "partially_ready"]),
        ).order_by(Document.created_at.desc()).all()
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
            subtopic_by_title = await _get_subtopic_by_title(doc.doc_id)
            for it in r.get("results", []):
                normalized = _normalize_search_item(it, doc.doc_id, doc.filename or doc.doc_id, breadcrumb_map, subtopic_by_title)
                # Penalize partially_ready docs so they rank lower than fully indexed docs.
                if penalty != 1.0:
                    normalized["score"] = normalized.get("score", 0) * penalty
                merged.append(normalized)
        except Exception:
            logger.warning("[search/user] failed on doc=%s", doc.doc_id, exc_info=True)
            continue

    merged.sort(key=lambda x: x.get("score", 0), reverse=True)
    out = {
        "mode": req.mode,
        "query": clean_q,
        "user_id": req.user_id,
        "results": merged[: max(1, req.limit)],
    }
    if did_you_mean:
        out["did_you_mean"] = did_you_mean
        out["original_query"] = original_query
    await add_xp(req.user_id, "ask")
    return out


@router.get("/node_chunks/{doc_id}/{node_id}")
async def node_chunks(doc_id: str, node_id: str, user_id: str = Query("default_user")):
    """Read-only: return chunks belonging to a unified-hierarchy subtopic node.

    Used by the Search page inline reader to render exact chunk content.
    """
    # Minimal user-scope guard: ensure the doc belongs to this user.
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.doc_id == doc_id, Document.user_id == user_id).first()
        if not doc:
            raise HTTPException(404, "Document not found")
    finally:
        db.close()

    if not node_id:
        raise HTTPException(400, "Missing node_id")

    chunks_path = CHUNKS_DIR / f"{doc_id}.json"
    if not chunks_path.exists():
        return {"doc_id": doc_id, "node_id": node_id, "chunks": []}

    try:
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    except Exception:
        chunks = []

    subtopic_by_title = await _get_subtopic_by_title(doc_id)

    out = []
    for c in chunks or []:
        cid = c.get("chunk_id", "") or ""
        text = c.get("text", "") or ""
        page = int(c.get("page", 1) or 1)
        sec_title = (c.get("section", "") or "").strip()
        expected_title = _expected_subtopic_title(sec_title, subtopic_by_title)
        candidate = subtopic_by_title.get(expected_title, [])
        mapped_node_id = _pick_node_id(candidate, page) if expected_title else ""
        if mapped_node_id == node_id and cid:
            out.append({"chunk_id": cid, "text": text, "page": page, "node_id": node_id})

    return {"doc_id": doc_id, "node_id": node_id, "chunks": out}


# --- NEW: EVALUATION ---

@router.post("/evaluate/{doc_id}")
async def evaluate_document(doc_id: str):
    """Run evaluation pipeline on a document — metrics, ablation, latency."""
    _validate_doc_ready(doc_id)
    result = await run_evaluation(doc_id)
    return result


@router.post("/compare/{doc_id}")
async def compare_retrieval_endpoint(doc_id: str, query: str):
    """Compare vector-only vs hybrid retrieval for a query."""
    _validate_doc_ready(doc_id)
    result = await compare_retrieval(doc_id, query)
    return result


@router.post("/validate-reranker/{doc_id}")
async def validate_reranker_endpoint(doc_id: str, query: str):
    """Show before/after reranking for a query."""
    _validate_doc_ready(doc_id)
    chunks = await retrieve_for_task(doc_id, query, task_type="ask")
    result = await validate_reranker(doc_id, query, chunks)
    return result


@router.post("/comparison-report/{doc_id}")
async def comparison_report_endpoint(doc_id: str):
    """Run retrieval comparison for standard test queries."""
    _validate_doc_ready(doc_id)
    test_queries = [
        "What is machine learning?",
        "How does gradient descent work?",
        "Compare supervised and unsupervised learning",
        "What causes overfitting?",
        "Explain backpropagation",
    ]
    result = await retrieval_comparison_report(doc_id, test_queries)
    return {"report": result}


@router.get("/evaluation/report/{doc_id}")
async def get_evaluation_report(doc_id: str):
    """Get latest saved evaluation report from SQLite."""
    report = get_latest_report(doc_id)
    if not report:
        raise HTTPException(404, "No evaluation report found. Run POST /api/evaluate/{doc_id} first.")
    return report


@router.get("/chunk-quality/{doc_id}")
async def get_chunk_quality(doc_id: str):
    """Validate chunk quality for a document."""
    _validate_doc_ready(doc_id)
    return validate_chunks(doc_id)


@router.get("/system/report/{doc_id}")
async def get_system_report(doc_id: str):
    """Get complete system validation report — combines all metrics."""
    _validate_doc_ready(doc_id)
    return await generate_system_report(doc_id)


@router.post("/evaluate/stable/{doc_id}")
async def evaluate_stable(doc_id: str, runs: int = 3):
    """Run multi-run evaluation for statistical stability.

    Flow: run_evaluation x N → aggregate → stability check → final report.
    Proves results are consistent, not lucky.
    """
    _validate_doc_ready(doc_id)
    if runs < 3:
        raise HTTPException(400, "Minimum 3 runs required for statistical validity")

    stable_result = await run_multi_evaluation(doc_id, runs=runs)
    report = await generate_system_report(doc_id, stability_data=stable_result)

    return {
        "stability_evaluation": stable_result,
        "system_report": report,
    }


# --- NEW: PERSONALIZATION ---

@router.get("/weakness/{user_id}")
async def get_weakness_dashboard(user_id: str):
    """Get user's weak topics with AI-generated study insights."""
    weak_topics = get_weak_topics(user_id)
    all_topics = get_all_topic_scores(user_id)

    # Add advisor insights to each weak topic
    enriched_weak = []
    for topic in weak_topics:
        advice = generate_advice(
            topic["topic"],
            topic.get("accuracy", 0),
            topic.get("trend", {}),
        )
        enriched_weak.append({**topic, "advice": advice})

    # Generate overall study plan
    study_plan = generate_study_plan(weak_topics)

    subject_summary = {}
    for row in all_topics:
        subj = row.get("subject", "General Studies")
        if subj not in subject_summary:
            subject_summary[subj] = {"subject": subj, "total": 0, "weak": 0, "moderate": 0, "strong": 0}
        subject_summary[subj]["total"] += 1
        st = row.get("status", "moderate")
        if st not in ("weak", "moderate", "strong"):
            st = "moderate"
        subject_summary[subj][st] += 1

    return {
        "user_id": user_id,
        "weak_topics": enriched_weak,
        "all_topics": all_topics,
        "study_plan": study_plan,
        "subject_summary": list(subject_summary.values()),
    }


# --- NEW: CONTENT LIBRARY ---

@router.post("/library/add")
async def library_add(req: LibraryAddRequest):
    """Add a processed document to the content library."""
    _validate_doc_ready(req.doc_id)
    add_to_library(req.doc_id, req.subject, req.title)
    return {"status": "added", "doc_id": req.doc_id, "subject": req.subject}


@router.get("/library")
async def library_list():
    """List all subjects in the content library."""
    return {"subjects": get_subjects()}


@router.get("/library/hierarchy/{user_id}")
async def library_hierarchy(user_id: str):
    """Unified hierarchy for library folder view (subject→unit→topic→subtopic)."""
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(Document.user_id == user_id, Document.status == "ready").all()
        doc_ids = [d.doc_id for d in docs]
        # Backfill unified hierarchy for older docs that were processed before this feature.
        for d in docs:
            current = get_doc_hierarchy(d.doc_id)
            needs_backfill = (not current.get("structure")) or (len(current.get("node_content", {})) == 0)
            if needs_backfill:
                legacy = ensure_course_structure(d.doc_id)
                if legacy.get("structure"):
                    upsert_from_structure(d.doc_id, legacy.get("structure", []), subject="General Studies")
        data = get_user_library_hierarchy(doc_ids)
        title_map = {d.doc_id: (d.filename or d.doc_id) for d in docs}
        for subject in data.get("subjects", []):
            for doc in subject.get("documents", []):
                doc["title"] = title_map.get(doc.get("doc_id", ""), doc.get("doc_id", ""))
        return data
    finally:
        db.close()


@router.get("/library/{subject}")
async def library_subject_docs(subject: str):
    """List documents in a subject."""
    return {"subject": subject, "documents": get_subject_docs(subject)}


@router.post("/library/remove")
async def library_remove(req: LibraryRemoveRequest):
    """Remove a document from a subject in the library."""
    remove_from_library(req.doc_id, req.subject or None)
    return {"status": "removed", "doc_id": req.doc_id}


@router.post("/library/reclassify")
async def library_reclassify(req: dict):
    """Reclassify all ready documents for a user using LLM."""
    from app.core.classifier import classify_document
    user_id = req.get("user_id", "")
    if not user_id:
        raise HTTPException(400, "user_id required")

    db = SessionLocal()
    try:
        docs = db.query(Document).filter(
            Document.user_id == user_id,
            Document.status == "ready"
        ).all()

        results = []
        for doc in docs:
            try:
                await _ensure_doc_assets_ready(doc.doc_id)
                subject = await classify_document(doc.doc_id)
                final_subject = subject if subject else "General Studies"
                if final_subject == "General":
                    final_subject = "General Studies"
                title = doc.filename or doc.doc_id
                add_to_library(doc.doc_id, final_subject, title)
                update_subject_title(doc.doc_id, final_subject)
                results.append({"doc_id": doc.doc_id, "subject": final_subject, "title": title})
            except Exception as e:
                results.append({"doc_id": doc.doc_id, "error": str(e)})

        return {"status": "done", "classified": results}
    finally:
        db.close()


@router.get("/course/{doc_id}/structure")
async def get_course_structure(doc_id: str):
    """Return prebuilt hierarchical structure for course-style reading UI."""
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


@router.post("/course/action")
async def course_action(req: CourseActionRequest):
    """Run section-scoped AI actions: summarize/explain."""
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
        req.doc_id,
        f"course_{action}",
        prompt,
        f"Section: {node_heading}\n\nContent:\n{node_content}",
        llm_variant=req.llm_variant,
    )
    raw = result.get("answer", "")
    answer = _format_course_ai_output(raw, action, node_heading)
    return {"action": action, "node_id": req.node_id, "answer": answer}


@router.post("/course/chat")
async def course_chat(req: CourseChatRequest):
    """Context-aware mentor chat: section-first, then full document context."""
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


# --- EXISTING: LEADERBOARD, SCORE, DELETE, HEALTH ---

@router.get("/documents/{user_id}")
async def list_user_documents(user_id: str):
    """List all documents uploaded by a user."""
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(Document.user_id == user_id).order_by(Document.created_at.desc()).all()
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
        return {
            "queue": queue_stats(),
            "documents": items,
        }
    finally:
        db.close()


@router.get("/pdf/{doc_id}")
async def serve_pdf(doc_id: str):
    """Serve uploaded PDF for in-app viewing."""
    _validate_doc_ready(doc_id)
    # Find the file in uploads dir
    for ext in ALLOWED_EXTENSIONS:
        file_path = UPLOAD_DIR / f"{doc_id}{ext}"
        if file_path.exists():
            media = "application/pdf" if ext == ".pdf" else "application/octet-stream"
            return FileResponse(
                path=str(file_path),
                media_type=media,
                filename=f"{doc_id}{ext}",
                headers={
                    # Force browser to render in-viewer instead of downloading.
                    "Content-Disposition": f'inline; filename="{doc_id}{ext}"',
                },
            )
    raise HTTPException(404, "PDF file not found")

@router.get("/leaderboard")
async def leaderboard(limit: int = Query(20, ge=1, le=100)):
    return {"leaderboard": get_leaderboard(limit)}


@router.get("/score")
async def score(user_id: str = "default_user"):
    return await get_user_score(user_id)


@router.delete("/doc/{doc_id}")
async def delete_document(doc_id: str):
    """Delete document and all data."""
    await delete_vector_index(doc_id)
    delete_bm25_index(doc_id)
    await clear_cached(doc_id)

    async with doc_locks[doc_id]:
        keys_to_remove = [k for k in llm_cache if k[0] == doc_id]
        for k in keys_to_remove:
            del llm_cache[k]

    bm25_indexes.pop(doc_id, None)

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

    remove_from_library(doc_id)
    delete_course_structure(doc_id)
    delete_doc_hierarchy(doc_id)

    db = SessionLocal()
    try:
        db.query(Document).filter(Document.doc_id == doc_id).delete()
        db.query(Attempt).filter(Attempt.doc_id == doc_id).delete()
        db.commit()
    finally:
        db.close()

    return {"status": "deleted", "doc_id": doc_id}


@router.get("/health")
async def health_check():
    """System health check."""
    model_loaded = get_model() is not None
    db_ok = True
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_ok = False

    return {
        "status": "ok" if (model_loaded and db_ok) else "degraded",
        "model_loaded": model_loaded,
        "db_connected": db_ok,
        "faiss_ready": True,
        "docs_in_memory": len(faiss_indexes),
        "bm25_indexes": len(bm25_indexes),
        "cached_generations": len(generated_cache),
    }


def _validate_doc_ready(doc_id: str):
    """Check that a document exists and is ready."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.doc_id == doc_id).first()
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc.status == "processing":
            raise HTTPException(202, "Document is still processing. Please wait.")
        if doc.status == "failed":
            raise HTTPException(500, f"Document processing failed: {doc.error_message}")
    finally:
        db.close()
