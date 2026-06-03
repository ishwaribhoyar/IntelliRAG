"""Shared storage package."""
from app.shared.storage.paths import (
    STORAGE_DIR, UPLOADS_DIR, FAISS_INDEX_DIR, CHUNKS_DIR,
    LIBRARY_DIR, EVAL_DIR, COURSE_CACHE_DIR,
    doc_upload_path, doc_faiss_path, doc_chunks_path, doc_bm25_path, eval_report_path,
)

__all__ = [
    "STORAGE_DIR", "UPLOADS_DIR", "FAISS_INDEX_DIR", "CHUNKS_DIR",
    "LIBRARY_DIR", "EVAL_DIR", "COURSE_CACHE_DIR",
    "doc_upload_path", "doc_faiss_path", "doc_chunks_path", "doc_bm25_path", "eval_report_path",
]
