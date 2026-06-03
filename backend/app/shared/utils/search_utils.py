"""Shared utilities — search result normalization helpers.

Extracted from api/routes.py into a shared utility module.
Logic is 100% identical to the original.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.database import SessionLocal, CourseNode

logger = logging.getLogger(__name__)

# Module-level cache so we don't re-query on every search request
_SUBTOPIC_BY_TITLE_CACHE: dict[str, dict[str, list[dict]]] = {}
_SUBTOPIC_BY_TITLE_CACHE_LOCK: asyncio.Lock = asyncio.Lock()


async def get_subtopic_by_title(doc_id: str) -> dict[str, list[dict]]:
    """Build {subtopic_title: [node...]} lookup for a doc (cached)."""
    if doc_id in _SUBTOPIC_BY_TITLE_CACHE:
        return _SUBTOPIC_BY_TITLE_CACHE[doc_id]

    db = SessionLocal()
    try:
        rows = (
            db.query(CourseNode)
            .filter(CourseNode.doc_id == doc_id, CourseNode.level == "subtopic")
            .order_by(CourseNode.sort_order.asc())
            .all()
        )
    finally:
        db.close()

    by_title: dict[str, list[dict]] = {}
    for r in rows:
        t = (r.title or "").strip()
        by_title.setdefault(t, []).append(
            {"node_id": r.node_id, "title": t, "page": int(r.page or 1)}
        )

    async with _SUBTOPIC_BY_TITLE_CACHE_LOCK:
        _SUBTOPIC_BY_TITLE_CACHE[doc_id] = by_title
    return by_title


def expected_subtopic_title(section_title: str, by_title: dict[str, list[dict]]) -> str:
    """Map chunk.section heading → the unified-hierarchy subtopic title."""
    def _norm_title(s: str) -> str:
        return " ".join((s or "").strip().lower().split())

    def _match_title(raw: str) -> str:
        if not raw:
            return ""
        if raw in by_title:
            return raw
        nr = _norm_title(raw)
        for k in by_title.keys():
            if _norm_title(k) == nr:
                return k
        return ""

    sec = (section_title or "").strip()
    if not sec:
        return ""

    details_raw = f"{sec} Details"
    sec_match = _match_title(sec)
    details_match = _match_title(details_raw)

    if details_match and not sec_match:
        return details_match
    if sec_match:
        return sec_match
    if details_match:
        return details_match
    return details_raw


def pick_node_id(candidates: list[dict], page: int) -> str:
    if not candidates:
        return ""
    for c in candidates:
        if int(c.get("page", 1)) == int(page):
            return c["node_id"]
    return candidates[0]["node_id"]


def normalize_search_item(
    item: dict,
    doc_id: str,
    filename: str,
    breadcrumb_map: dict[str, str],
    subtopic_by_title: dict[str, list[dict]],
) -> dict:
    """Normalize a raw search result chunk into the standard UI-ready format."""
    section = (item.get("section", "") or "").strip()
    page = int(item.get("page", 1) or 1)

    exp_title = expected_subtopic_title(section, subtopic_by_title)
    node_id = pick_node_id(subtopic_by_title.get(exp_title, []), page) if exp_title else ""
    hierarchy_path = breadcrumb_map.get(
        exp_title, breadcrumb_map.get(section, item.get("hierarchy_path", section))
    )

    return {
        "doc_id": doc_id,
        "node_id": node_id,
        "chunk_id": item.get("chunk_id", ""),
        "page": page,
        "section_path": hierarchy_path,
        "snippet": item.get("text", "") or item.get("snippet", ""),
        "title": exp_title or section or filename or doc_id,
        "score": item.get("score", 0),
        # backward-compatible keys for existing UI
        "text": item.get("text", "") or item.get("snippet", ""),
        "section": section,
        "hierarchy_path": hierarchy_path,
        "filename": filename or doc_id,
    }


def format_course_ai_output(answer: str, action: str, heading: str) -> str:
    """Normalize summarize/explain outputs into readable structured markdown."""
    text = (answer or "").strip()
    if not text:
        return "No response generated. Please try again."

    def _clean_lines(src: str) -> list[str]:
        raw_lines = [ln.strip() for ln in src.splitlines() if ln.strip()]
        return [
            ln.replace("**", "").replace("__", "").strip()
            for ln in raw_lines
            if ln.strip()
        ]

    lines = _clean_lines(text)
    if not lines:
        return text

    if action == "summarize":
        has_expected = (
            "## Quick Summary" in text
            and "## Important Terms" in text
            and "## Key Takeaways" in text
        )
        if has_expected:
            return text

        bullets = [f"- {ln.lstrip('- ').strip()}" for ln in lines[:8]]
        return (
            f"## Quick Summary\n"
            f"Section: **{heading}**\n\n"
            + "\n".join(bullets)
            + "\n\n## Important Terms\n- Add key terms from this section with one-line meanings."
            + "\n\n## Key Takeaways\n- Focus on the core definition, process, and examples."
        )

    # explain format
    has_expected = (
        "## Concept Overview" in text
        and "## Step-by-Step Explanation" in text
        and "## Worked Intuition / Example" in text
        and "## Common Mistakes" in text
        and "## Revision Points" in text
    )
    if has_expected:
        return text

    brief = lines[:3]
    details = lines[3:10] if len(lines) > 3 else []
    out = [
        "## Concept Overview",
        f"Section: **{heading}**",
        "",
        *brief,
        "",
        "## Step-by-Step Explanation",
    ]
    if details:
        out.extend([f"- {ln.lstrip('- ').strip()}" for ln in details])
    else:
        out.append("- Expand each idea with definitions, logic, and examples.")
    out.extend([
        "",
        "## Worked Intuition / Example",
        "- Connect this concept to one practical or exam-style scenario.",
        "",
        "## Common Mistakes",
        "- Confusing definition with implementation details.",
        "- Skipping assumptions and constraints in the section.",
        "- Memorizing terms without understanding flow/logic.",
        "",
        "## Revision Points",
        "- Remember the core definition.",
        "- Recall the main steps/process.",
        "- Keep one practical example in mind.",
    ])
    return "\n".join(out)
