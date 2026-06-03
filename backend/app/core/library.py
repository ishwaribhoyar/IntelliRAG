"""Content library — subject-based document storage and pre-indexed content."""
import json
import logging
from pathlib import Path
from app.config import STORAGE_DIR

logger = logging.getLogger(__name__)

LIBRARY_DIR = STORAGE_DIR / "library"
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)

# In-memory catalog: {subject: [doc_id, ...]}
_catalog: dict[str, list[str]] = {}


def _entry_doc_id(entry) -> str:
    """Read a doc id from legacy string entries or dict-based entries."""
    return entry.get("doc_id", "") if isinstance(entry, dict) else entry


def _prune_empty_subjects() -> bool:
    """Drop subject folders that no longer contain any documents."""
    empty_subjects = [subject for subject, docs in _catalog.items() if not docs]
    for subject in empty_subjects:
        del _catalog[subject]
    return bool(empty_subjects)


def _load_catalog():
    """Load library catalog from disk."""
    global _catalog
    catalog_path = LIBRARY_DIR / "catalog.json"
    if catalog_path.exists():
        with open(catalog_path, "r", encoding="utf-8") as f:
            _catalog = json.load(f)
        if _prune_empty_subjects():
            _save_catalog()
        logger.info(f"Loaded library catalog: {len(_catalog)} subjects")
    else:
        _catalog = {}


def _save_catalog():
    """Save library catalog to disk."""
    catalog_path = LIBRARY_DIR / "catalog.json"
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(_catalog, f, ensure_ascii=False, indent=2)


def add_to_library(doc_id: str, subject: str, title: str = ""):
    """Add a processed document to the content library under a subject."""
    if subject not in _catalog:
        _catalog[subject] = []

    entry = {"doc_id": doc_id, "title": title}
    # Avoid duplicates
    existing_ids = [_entry_doc_id(entry) for entry in _catalog[subject]]
    if doc_id not in existing_ids:
        _catalog[subject].append(entry)
        _save_catalog()
        logger.info(f"Added doc {doc_id} to library under '{subject}'")


def get_subjects() -> list[dict]:
    """Get all subjects and their document counts."""
    return [
        {"subject": subj, "doc_count": len(docs)}
        for subj, docs in _catalog.items()
    ]


def get_subject_docs(subject: str) -> list[dict]:
    """Get all documents in a subject."""
    docs = _catalog.get(subject, [])
    return [d if isinstance(d, dict) else {"doc_id": d, "title": ""} for d in docs]


def remove_from_library(doc_id: str, subject: str = None):
    """Remove a document from the library."""
    changed = False
    if subject:
        if subject in _catalog:
            _catalog[subject] = [
                d for d in _catalog[subject]
                if _entry_doc_id(d) != doc_id
            ]
            changed = True
    else:
        # Remove from all subjects
        for subj in list(_catalog):
            _catalog[subj] = [
                d for d in _catalog[subj]
                if _entry_doc_id(d) != doc_id
            ]
            changed = True

    if changed:
        _prune_empty_subjects()
        _save_catalog()


# Load catalog on module import
_load_catalog()
