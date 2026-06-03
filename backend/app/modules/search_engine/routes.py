"""Search Engine module — routes."""
import logging
from fastapi import APIRouter, HTTPException, Query

from app.shared.schemas.search import SearchRequest, UserSearchRequest
from app.modules.search_engine.service import handle_search, handle_user_search, handle_suggest, handle_user_suggest, handle_node_chunks

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Search Engine"])


@router.post("/search")
async def search_endpoint(req: SearchRequest):
    """Search with keyword/hybrid/AI modes."""
    return await handle_search(req)


@router.get("/search/suggest/{doc_id}")
async def search_suggest(doc_id: str, q: str = Query("", min_length=1), limit: int = Query(8, ge=1, le=20)):
    """Autocomplete suggestions from indexed PDF vocabulary."""
    return await handle_suggest(doc_id, q, limit)


@router.get("/search/suggest/user/{user_id}")
async def search_suggest_user(user_id: str, q: str = Query("", min_length=1), limit: int = Query(5, ge=1, le=20)):
    """User-scoped autocomplete suggestions from all ready docs."""
    return await handle_user_suggest(user_id, q, limit)


@router.post("/search/user")
async def search_user_endpoint(req: UserSearchRequest):
    """User-scoped global search across all ready documents."""
    return await handle_user_search(req)


@router.get("/node_chunks/{doc_id}/{node_id}")
async def node_chunks(doc_id: str, node_id: str, user_id: str = Query("default_user")):
    """Return chunks belonging to a unified-hierarchy subtopic node."""
    return await handle_node_chunks(doc_id, node_id, user_id)
