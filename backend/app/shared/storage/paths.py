"""Storage path registry — centralizes all file system path definitions.

All modules must import storage paths from here, not from config.py directly.
This is the single source of truth for the on-disk layout.

Layout:
  backend/storage/
  ├── uploads/          Raw uploaded files (PDFs, XLSX)
  ├── faiss_index/      FAISS .index files per document
  ├── chunks/           Chunked text JSON + BM25 JSON per document
  ├── library/          Content library catalog JSON
  ├── evaluation/       Evaluation report JSON files
  └── course_cache/     (Reserved) Pre-computed course structure caches
"""
from pathlib import Path

# Resolve the backend/ root (one level up from app/)
_APP_DIR   = Path(__file__).resolve().parent.parent
BASE_DIR   = _APP_DIR.parent   # backend/
STORAGE_DIR = BASE_DIR / "storage"

# Sub-directories
UPLOADS_DIR      = STORAGE_DIR / "uploads"
FAISS_INDEX_DIR  = STORAGE_DIR / "faiss_index"
CHUNKS_DIR       = STORAGE_DIR / "chunks"
LIBRARY_DIR      = STORAGE_DIR / "library"
EVAL_DIR         = STORAGE_DIR / "evaluation"
COURSE_CACHE_DIR = STORAGE_DIR / "course_cache"

# Ensure all directories exist at import time
for _d in [
    UPLOADS_DIR, FAISS_INDEX_DIR, CHUNKS_DIR,
    LIBRARY_DIR, EVAL_DIR, COURSE_CACHE_DIR,
]:
    _d.mkdir(parents=True, exist_ok=True)


def doc_upload_path(doc_id: str, ext: str) -> Path:
    """Canonical path for a raw uploaded file."""
    return UPLOADS_DIR / f"{doc_id}{ext}"


def doc_faiss_path(doc_id: str) -> Path:
    """Canonical path for a FAISS index file."""
    return FAISS_INDEX_DIR / f"{doc_id}.index"


def doc_chunks_path(doc_id: str) -> Path:
    """Canonical path for the JSON chunks file."""
    return CHUNKS_DIR / f"{doc_id}.json"


def doc_bm25_path(doc_id: str) -> Path:
    """Canonical path for the BM25 index JSON."""
    return CHUNKS_DIR / f"{doc_id}_bm25.json"


def eval_report_path(doc_id: str) -> Path:
    """Canonical path for the latest evaluation report."""
    return EVAL_DIR / f"{doc_id}_report.json"
