"""Granular concurrency primitives and in-memory caches.

AUTHORITATIVE SOURCE — all modules import from here.
shared/caching/memory_store.py re-exports everything from this module for the
new modular architecture; keeping them in sync is not required since both point
to the same Python objects at runtime.
"""
import asyncio
import threading
import time
import logging
from collections import defaultdict, OrderedDict
from app.config import MAX_DOCS_IN_MEMORY

logger = logging.getLogger(__name__)

# --- Granular Locks ---
# Per-document async lock (for cache reads/writes scoped to a doc)
doc_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

# Per-user async lock (for XP/gamification scoped to a user)
user_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

# Threading lock ONLY for FAISS disk I/O (blocking ops)
faiss_lock = threading.Lock()

# --- In-Memory Caches ---
# FAISS indexes per document  {doc_id: faiss.Index}
faiss_indexes: OrderedDict = OrderedDict()

# Chunk store per document  {doc_id: [chunk_dicts]}
chunk_store: OrderedDict = OrderedDict()

# BM25 indexes per document  {doc_id: BM25Index}
bm25_indexes: dict = {}

# Generated content cache  {doc_id: {"quiz": ..., "flashcards": ..., ...}}
generated_cache: dict = {}

# LLM response cache  {(doc_id, task_type, context_hash, prompt_version): response}
llm_cache: dict = {}

# User-library /ask cache: sha256 key -> last response payload (LRU via OrderedDict)
user_ask_cache: OrderedDict = OrderedDict()
MAX_USER_ASK_CACHE = 500

# User XP cache  {user_id: {"xp": int, "daily_xp": int, "level": int, ...}}
user_xp_cache: dict = {}

# Leaderboard cache  {user_id: daily_xp}
leaderboard_cache: dict = {}

# Pending DB updates buffer
pending_updates: list = []

# Rate limiting tracker  {doc_id: last_request_timestamp}
last_request_time: dict[str, float] = {}

# LRU access tracking  {doc_id: last_access_time}
doc_access_times: OrderedDict = OrderedDict()


async def evict_if_needed(current_doc_id: str = ""):
    """Atomically evict least-recently-used document data when memory limit exceeded."""
    while len(faiss_indexes) > MAX_DOCS_IN_MEMORY:
        # Find LRU doc (first item in OrderedDict)
        lru_doc_id = next(iter(faiss_indexes))
        if lru_doc_id == current_doc_id:
            # Don't evict the doc we're currently working with
            if len(faiss_indexes) <= MAX_DOCS_IN_MEMORY + 1:
                break
            # Move it to the end and try the next one
            faiss_indexes.move_to_end(lru_doc_id)
            lru_doc_id = next(iter(faiss_indexes))

        async with doc_locks[lru_doc_id]:
            # Atomic removal of ALL related data
            faiss_indexes.pop(lru_doc_id, None)
            chunk_store.pop(lru_doc_id, None)
            generated_cache.pop(lru_doc_id, None)
            doc_access_times.pop(lru_doc_id, None)
            # Remove LLM cache entries for this doc
            keys_to_remove = [k for k in llm_cache if k[0] == lru_doc_id]
            for k in keys_to_remove:
                del llm_cache[k]
            logger.info(f"Evicted doc {lru_doc_id} from memory (LRU)")


def touch_doc(doc_id: str):
    """Mark a document as recently accessed for LRU tracking."""
    doc_access_times[doc_id] = time.time()
    if doc_id in faiss_indexes:
        faiss_indexes.move_to_end(doc_id)
    if doc_id in chunk_store:
        chunk_store.move_to_end(doc_id)
