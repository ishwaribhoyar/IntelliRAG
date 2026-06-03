"""Shared caching — in-memory state store.

This is the canonical location for all in-memory caches and locks.
app/state.py re-exports from here for backward compatibility.
"""
import asyncio
import threading
import time
import logging
from collections import defaultdict, OrderedDict
from app.config import MAX_DOCS_IN_MEMORY

logger = logging.getLogger(__name__)

# --- Granular Locks ---
doc_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
user_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
faiss_lock = threading.Lock()

# --- In-Memory Caches ---
faiss_indexes: OrderedDict = OrderedDict()       # {doc_id: faiss.Index}
chunk_store: OrderedDict = OrderedDict()          # {doc_id: [chunk_dicts]}
bm25_indexes: dict = {}                           # {doc_id: BM25Index}
generated_cache: dict = {}                        # {doc_id: {quiz:..., flashcards:...}}
llm_cache: dict = {}                              # {(doc_id, task_type, hash, ver): response}
user_ask_cache: OrderedDict = OrderedDict()       # sha256 key -> last response (LRU)
MAX_USER_ASK_CACHE = 500
user_xp_cache: dict = {}                          # {user_id: {xp, daily_xp, level}}
leaderboard_cache: dict = {}                      # {user_id: daily_xp}
pending_updates: list = []                        # Pending DB updates buffer
last_request_time: dict[str, float] = {}         # {doc_id: last_request_timestamp}
doc_access_times: OrderedDict = OrderedDict()     # {doc_id: last_access_time}


async def evict_if_needed(current_doc_id: str = ""):
    """Atomically evict least-recently-used document data when memory limit exceeded."""
    while len(faiss_indexes) > MAX_DOCS_IN_MEMORY:
        lru_doc_id = next(iter(faiss_indexes))
        if lru_doc_id == current_doc_id:
            if len(faiss_indexes) <= MAX_DOCS_IN_MEMORY + 1:
                break
            faiss_indexes.move_to_end(lru_doc_id)
            lru_doc_id = next(iter(faiss_indexes))

        async with doc_locks[lru_doc_id]:
            faiss_indexes.pop(lru_doc_id, None)
            chunk_store.pop(lru_doc_id, None)
            generated_cache.pop(lru_doc_id, None)
            doc_access_times.pop(lru_doc_id, None)
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
