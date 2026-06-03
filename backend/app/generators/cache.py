"""Generated content cache — per-doc async-safe caching."""
import logging
from app.state import generated_cache, doc_locks

logger = logging.getLogger(__name__)


async def get_cached(doc_id: str, content_type: str):
    """Get cached generated content. Returns None if not cached."""
    async with doc_locks[doc_id]:
        doc_cache = generated_cache.get(doc_id, {})
        return doc_cache.get(content_type)


async def set_cached(doc_id: str, content_type: str, content):
    """Cache generated content for a document."""
    async with doc_locks[doc_id]:
        if doc_id not in generated_cache:
            generated_cache[doc_id] = {}
        generated_cache[doc_id][content_type] = content
        logger.info(f"Cached {content_type} for doc {doc_id}")


async def clear_cached(doc_id: str):
    """Clear all cached content for a document."""
    async with doc_locks[doc_id]:
        generated_cache.pop(doc_id, None)
