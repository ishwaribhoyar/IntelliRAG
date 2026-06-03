"""FAISS vector index — per-document index management with persistence and lazy loading.
Refactored from rag/vector_store.py for the new indexing module.
"""
import json
import logging
import numpy as np
import faiss
from pathlib import Path
from app.config import FAISS_INDEX_DIR, CHUNKS_DIR
from app.state import (
    faiss_indexes, chunk_store, faiss_lock,
    doc_locks, evict_if_needed, touch_doc
)
from app.rag.embedder import embed_texts, embed_texts_async

logger = logging.getLogger(__name__)


async def build_vector_index(doc_id: str, chunks: list[dict]):
    """Build FAISS index from chunks, save to disk, and cache in memory."""
    if not chunks:
        logger.warning(f"No chunks to index for {doc_id}")
        return

    texts = [c["text"] for c in chunks]
    try:
        embeddings = await embed_texts_async(texts)
    except Exception:
        embeddings = embed_texts(texts)
    embeddings = np.array(embeddings, dtype="float32")

    # Build FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)

    # Save to disk
    index_path = str(FAISS_INDEX_DIR / f"{doc_id}.index")
    chunks_path = str(CHUNKS_DIR / f"{doc_id}.json")

    with faiss_lock:
        faiss.write_index(index, index_path)
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)

    # Cache in memory
    async with doc_locks[doc_id]:
        await evict_if_needed(doc_id)
        faiss_indexes[doc_id] = index
        chunk_store[doc_id] = chunks
        touch_doc(doc_id)

    logger.info(f"Built FAISS index for {doc_id} ({len(chunks)} chunks, dim={dimension})")


async def load_vector_index(doc_id: str) -> bool:
    """Lazy-load from disk into memory. Returns True if loaded."""
    if doc_id in faiss_indexes and doc_id in chunk_store:
        touch_doc(doc_id)
        return True

    index_path = FAISS_INDEX_DIR / f"{doc_id}.index"
    chunks_path = CHUNKS_DIR / f"{doc_id}.json"

    if not index_path.exists() or not chunks_path.exists():
        logger.warning(f"No stored index/chunks found for {doc_id}")
        return False

    try:
        with faiss_lock:
            index = faiss.read_index(str(index_path))

        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        async with doc_locks[doc_id]:
            await evict_if_needed(doc_id)
            faiss_indexes[doc_id] = index
            chunk_store[doc_id] = chunks
            touch_doc(doc_id)

        logger.info(f"Loaded FAISS index for {doc_id} from disk")
        return True
    except Exception as e:
        logger.error(f"Failed to load index for {doc_id}: {e}")
        return False


async def search_vector(doc_id: str, query_embedding: np.ndarray, top_k: int = 5) -> list[dict]:
    """Search FAISS index. Returns chunks with scores."""
    if doc_id not in faiss_indexes:
        loaded = await load_vector_index(doc_id)
        if not loaded:
            return []

    index = faiss_indexes[doc_id]
    chunks = chunk_store[doc_id]
    touch_doc(doc_id)

    query_vec = np.array([query_embedding], dtype="float32")
    faiss.normalize_L2(query_vec)

    k = min(top_k, index.ntotal)
    scores, indices = index.search(query_vec, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if 0 <= idx < len(chunks):
            chunk = chunks[idx].copy()
            chunk["score"] = float(score)
            results.append(chunk)

    return results


async def delete_vector_index(doc_id: str):
    """Delete a document's index from disk and memory."""
    async with doc_locks[doc_id]:
        faiss_indexes.pop(doc_id, None)
        chunk_store.pop(doc_id, None)

    index_path = FAISS_INDEX_DIR / f"{doc_id}.index"
    chunks_path = CHUNKS_DIR / f"{doc_id}.json"

    with faiss_lock:
        if index_path.exists():
            index_path.unlink()
        if chunks_path.exists():
            chunks_path.unlink()

    logger.info(f"Deleted vector index for {doc_id}")


def vector_index_exists(doc_id: str) -> bool:
    """Check if FAISS index and chunks exist on disk."""
    return (
        (FAISS_INDEX_DIR / f"{doc_id}.index").exists()
        and (CHUNKS_DIR / f"{doc_id}.json").exists()
    )
