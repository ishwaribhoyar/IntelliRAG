"""Content Library module — service layer."""
import logging

from app.shared.schemas.library import LibraryAddRequest, LibraryRemoveRequest
from app.shared.database import SessionLocal, Document
from app.shared.utils.doc_utils import _validate_doc_ready, _ensure_doc_assets_ready
from app.core.library import add_to_library, get_subjects, get_subject_docs, remove_from_library
from app.core.course_structure import ensure_course_structure
from app.core.unified_hierarchy import (
    get_user_library_hierarchy, upsert_from_structure, update_subject_title,
)

logger = logging.getLogger(__name__)


async def handle_library_add(req: LibraryAddRequest) -> dict:
    _validate_doc_ready(req.doc_id)
    add_to_library(req.doc_id, req.subject, req.title)
    return {"status": "added", "doc_id": req.doc_id, "subject": req.subject}


async def handle_library_list() -> dict:
    return {"subjects": get_subjects()}


async def handle_library_hierarchy(user_id: str) -> dict:
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(Document.user_id == user_id, Document.status == "ready").all()
        doc_ids = [d.doc_id for d in docs]
        from app.core.unified_hierarchy import get_doc_hierarchy
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


async def handle_library_subject(subject: str) -> dict:
    return {"subject": subject, "documents": get_subject_docs(subject)}


async def handle_library_remove(req: LibraryRemoveRequest) -> dict:
    remove_from_library(req.doc_id, req.subject or None)
    return {"status": "removed", "doc_id": req.doc_id}


async def handle_library_reclassify(user_id: str) -> dict:
    from app.core.classifier import classify_document
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(
            Document.user_id == user_id, Document.status == "ready"
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
