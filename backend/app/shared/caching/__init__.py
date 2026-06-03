"""Shared caching package init."""
from app.shared.caching.memory_store import (
    doc_locks, user_locks, faiss_lock,
    faiss_indexes, chunk_store, bm25_indexes,
    generated_cache, llm_cache, user_ask_cache,
    MAX_USER_ASK_CACHE, user_xp_cache, leaderboard_cache,
    pending_updates, last_request_time, doc_access_times,
    evict_if_needed, touch_doc,
)

__all__ = [
    "doc_locks", "user_locks", "faiss_lock",
    "faiss_indexes", "chunk_store", "bm25_indexes",
    "generated_cache", "llm_cache", "user_ask_cache",
    "MAX_USER_ASK_CACHE", "user_xp_cache", "leaderboard_cache",
    "pending_updates", "last_request_time", "doc_access_times",
    "evict_if_needed", "touch_doc",
]
