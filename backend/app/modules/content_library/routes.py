"""Content Library module — routes."""
import logging
from fastapi import APIRouter, HTTPException

from app.shared.schemas.library import LibraryAddRequest, LibraryRemoveRequest
from app.modules.content_library.service import (
    handle_library_add, handle_library_list, handle_library_hierarchy,
    handle_library_subject, handle_library_remove, handle_library_reclassify,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Content Library"])


@router.post("/library/add")
async def library_add(req: LibraryAddRequest):
    """Add a processed document to the content library."""
    return await handle_library_add(req)


@router.get("/library")
async def library_list():
    """List all subjects in the content library."""
    return await handle_library_list()


@router.get("/library/hierarchy/{user_id}")
async def library_hierarchy(user_id: str):
    """Unified hierarchy for library folder view."""
    return await handle_library_hierarchy(user_id)


@router.get("/library/{subject}")
async def library_subject_docs(subject: str):
    """List documents in a subject."""
    return await handle_library_subject(subject)


@router.post("/library/remove")
async def library_remove(req: LibraryRemoveRequest):
    """Remove a document from a subject."""
    return await handle_library_remove(req)


@router.post("/library/reclassify")
async def library_reclassify(req: dict):
    """Reclassify all ready documents for a user using LLM."""
    user_id = req.get("user_id", "")
    if not user_id:
        raise HTTPException(400, "user_id required")
    return await handle_library_reclassify(user_id)
