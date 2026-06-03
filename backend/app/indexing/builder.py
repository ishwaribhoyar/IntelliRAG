"""Unified index builder — builds both FAISS + BM25 indexes for a document."""
import logging
from app.indexing.vector_index import build_vector_index, load_vector_index
from app.indexing.bm25_index import BM25Index, save_bm25_index, load_bm25_index
from app.state import bm25_indexes

logger = logging.getLogger(__name__)


async def build_indexes(doc_id: str, chunks: list[dict]):
    """Build both FAISS vector index and BM25 keyword index for a document.

    Args:
        doc_id: Document identifier
        chunks: List of chunk dicts from the hierarchical chunker
    """
    if not chunks:
        logger.warning(f"No chunks to index for {doc_id}")
        return

    # 1. Build FAISS vector index
    await build_vector_index(doc_id, chunks)

    # 2. Build BM25 keyword index
    bm25 = BM25Index()
    bm25.build(chunks)
    save_bm25_index(doc_id, bm25)
    bm25_indexes[doc_id] = bm25

    logger.info(f"Built dual indexes (FAISS + BM25) for {doc_id}: {len(chunks)} chunks")


async def load_indexes(doc_id: str) -> bool:
    """Load both indexes from disk into memory. Returns True if both loaded."""
    # Load FAISS
    vector_ok = await load_vector_index(doc_id)

    # Load BM25
    if doc_id not in bm25_indexes:
        bm25 = load_bm25_index(doc_id)
        if bm25:
            bm25_indexes[doc_id] = bm25
        else:
            logger.warning(f"No BM25 index found for {doc_id}")

    bm25_ok = doc_id in bm25_indexes

    if vector_ok and bm25_ok:
        logger.info(f"Loaded dual indexes for {doc_id}")
    elif vector_ok:
        logger.info(f"Loaded FAISS only for {doc_id} (no BM25)")

    return vector_ok
