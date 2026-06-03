"""Course view structure builder and storage for uploaded documents."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.config import STORAGE_DIR, CHUNKS_DIR

logger = logging.getLogger(__name__)

COURSE_DIR = STORAGE_DIR / "course_structures"
COURSE_DIR.mkdir(parents=True, exist_ok=True)
_STRUCT_CACHE: dict[str, dict[str, Any]] = {}


def _level_num(level: str) -> int:
    mapping = {"h1": 1, "h2": 2, "h3": 3}
    return mapping.get((level or "").lower(), 3)


def _node_id(index: int) -> str:
    return f"n_{index:05d}"


def _structure_path(doc_id: str) -> Path:
    return COURSE_DIR / f"{doc_id}.json"


def _cache_put(doc_id: str, data: dict) -> None:
    path = _structure_path(doc_id)
    _STRUCT_CACHE[doc_id] = {
        "mtime": path.stat().st_mtime if path.exists() else None,
        "data": data,
    }


def build_course_structure(normalized: dict, doc_id: str | None = None) -> dict:
    """Build hierarchical tree from normalized sections (h1/h2/h3)."""
    current_doc_id = doc_id or normalized.get("doc_id", "")
    sections = normalized.get("sections", [])

    root_nodes: list[dict] = []
    stack: list[tuple[int, dict]] = []

    for i, sec in enumerate(sections):
        heading = (sec.get("heading") or "Untitled").strip()
        level = (sec.get("level") or "h3").lower()
        content = (sec.get("content") or "").strip()
        page = sec.get("page", 1)
        lvl_num = _level_num(level)

        node = {
            "id": _node_id(i + 1),
            "heading": heading,
            "level": level,
            "page": page,
            "content": content,
            "children": [],
        }

        while stack and stack[-1][0] >= lvl_num:
            stack.pop()

        if not stack:
            root_nodes.append(node)
        else:
            stack[-1][1]["children"].append(node)

        stack.append((lvl_num, node))

    if not root_nodes and sections:
        root_nodes = [{
            "id": _node_id(1),
            "heading": "Course Content",
            "level": "h1",
            "page": 1,
            "content": "",
            "children": [],
        }]
        for i, sec in enumerate(sections, start=1):
            root_nodes[0]["children"].append({
                "id": _node_id(i + 1),
                "heading": (sec.get("heading") or f"Section {i}").strip(),
                "level": "h2",
                "page": sec.get("page", 1),
                "content": (sec.get("content") or "").strip(),
                "children": [],
            })

    return {"doc_id": current_doc_id, "structure": root_nodes}


def save_course_structure(normalized: dict, doc_id: str | None = None) -> dict:
    """Build and persist course structure for a document."""
    data = build_course_structure(normalized, doc_id=doc_id)
    path = _structure_path(data["doc_id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _cache_put(data["doc_id"], data)
    logger.info("[%s] Saved course structure with %s roots", data["doc_id"], len(data.get("structure", [])))
    return data


def load_course_structure(doc_id: str) -> dict | None:
    """Load persisted course structure from disk."""
    path = _structure_path(doc_id)
    if not path.exists():
        return None
    try:
        current_mtime = path.stat().st_mtime
        cached = _STRUCT_CACHE.get(doc_id)
        if cached and cached.get("mtime") == current_mtime and cached.get("data"):
            return cached["data"]

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache_put(doc_id, data)
        return data
    except Exception as e:
        logger.error("[%s] Failed to load course structure: %s", doc_id, e)
        return None


def delete_course_structure(doc_id: str) -> None:
    """Delete persisted course structure, if present."""
    path = _structure_path(doc_id)
    if path.exists():
        path.unlink()
    _STRUCT_CACHE.pop(doc_id, None)


def ensure_course_structure(doc_id: str) -> dict:
    """Load structure, or create a minimal fallback from chunk sections."""
    existing = load_course_structure(doc_id)
    if existing:
        return existing

    chunks_path = Path(CHUNKS_DIR) / f"{doc_id}.json"
    section_texts: dict[str, list[str]] = {}
    if chunks_path.exists():
        try:
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            for ch in chunks:
                sec = (ch.get("section") or "").strip()
                txt = (ch.get("text") or "").strip()
                if not sec:
                    continue
                if sec not in section_texts:
                    section_texts[sec] = []
                if txt:
                    section_texts[sec].append(txt)
        except Exception:
            section_texts = {}

    nodes = [{
        "id": _node_id(i + 1),
        "heading": sec,
        "level": "h2",
        "page": 1,
        "content": "\n\n".join(parts[:4]),
        "children": [],
    } for i, (sec, parts) in enumerate(list(section_texts.items())[:200])]

    fallback = {
        "doc_id": doc_id,
        "structure": [{
            "id": "n_00000",
            "heading": "Course Content",
            "level": "h1",
            "page": 1,
            "content": "",
            "children": nodes,
        }],
    }

    path = _structure_path(doc_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fallback, f, ensure_ascii=False, indent=2)
    _cache_put(doc_id, fallback)
    return fallback


def find_node(structure: list[dict], node_id: str) -> dict | None:
    """Find a node by id in nested structure."""
    if not node_id:
        return None
    stack = list(structure or [])
    while stack:
        node = stack.pop()
        if node.get("id") == node_id:
            return node
        stack.extend(reversed(node.get("children", [])))
    return None


def split_structure_and_content(data: dict, max_content_chars: int = 12000) -> dict:
    """Return lightweight tree + node content map for faster client rendering."""
    node_content: dict[str, str] = {}

    def walk(nodes: list[dict]) -> list[dict]:
        out: list[dict] = []
        for node in nodes or []:
            node_id = node.get("id", "")
            raw_content = (node.get("content") or "").strip()
            if raw_content and node_id:
                node_content[node_id] = raw_content[:max_content_chars]
            out.append({
                "id": node_id,
                "heading": node.get("heading", ""),
                "level": node.get("level", "h3"),
                "page": node.get("page", 1),
                "children": walk(node.get("children", [])),
            })
        return out

    return {
        "doc_id": data.get("doc_id", ""),
        "structure": walk(data.get("structure", [])),
        "node_content": node_content,
    }
