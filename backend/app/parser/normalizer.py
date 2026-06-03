"""Normalizer — converts all parser outputs into the standard JSON schema.
Upgraded: heading level detection (h1/h2/h3), page number tracking,
improved table extraction.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_content(raw: dict, doc_id: str) -> dict:
    """Convert any parser output into the standardized schema:
    {
        "doc_id": str,
        "sections": [{
            "heading": str, "level": "h1|h2|h3",
            "content": str, "page": int,
            "tables": [], "metadata": {}
        }]
    }
    """
    content = raw.get("content", "")
    raw_type = raw.get("type", "markdown")
    pages_text = raw.get("pages_text", [])

    # For excel, sections are already split
    if raw_type == "excel" and "sections" in raw:
        sections = []
        for i, s in enumerate(raw["sections"]):
            sections.append({
                "heading": s.get("heading", "Sheet"),
                "level": "h1",
                "content": s.get("content", ""),
                "page": i + 1,
                "tables": _extract_tables(s.get("content", "")),
                "metadata": {"source_type": "excel"},
            })
        return {"doc_id": doc_id, "sections": sections}

    # For markdown / text content, split by headings
    sections = _split_by_headings(content, pages_text)

    if not sections:
        # No headings found, treat entire content as one section
        page = _estimate_page(content, pages_text)
        sections = [{
            "heading": "Document Content",
            "level": "h1",
            "content": content.strip(),
            "page": page,
            "tables": _extract_tables(content),
            "metadata": {"source_type": raw_type},
        }]
    else:
        for s in sections:
            s["tables"] = _extract_tables(s["content"])
            s["metadata"] = {"source_type": raw_type}

    return {"doc_id": doc_id, "sections": sections}


def _split_by_headings(text: str, pages_text: list[str] = None) -> list[dict]:
    """Split markdown-style text by headings (# ## ###) with level + page tracking."""
    if not text:
        return []

    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))

    if not matches:
        return []

    sections = []
    for i, match in enumerate(matches):
        level_str = match.group(1)
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        if not content:
            continue

        # Determine heading level
        depth = len(level_str)
        if depth == 1:
            level = "h1"
        elif depth == 2:
            level = "h2"
        else:
            level = "h3"

        # Estimate which page this section belongs to
        page = _estimate_page(content, pages_text) if pages_text else 1

        sections.append({
            "heading": heading,
            "level": level,
            "content": content,
            "page": page,
        })

    return sections


def _estimate_page(text: str, pages_text: list[str]) -> int:
    """Estimate which page a text chunk comes from by finding best overlap."""
    if not pages_text or not text:
        return 1

    # Use first 100 chars of text as a fingerprint
    snippet = text[:150].strip()
    if not snippet:
        return 1

    best_page = 1
    best_score = 0
    for i, page_text in enumerate(pages_text):
        # Count how many words from snippet appear in this page
        snippet_words = set(snippet.lower().split()[:15])
        page_words = set(page_text.lower().split())
        overlap = len(snippet_words & page_words)
        if overlap > best_score:
            best_score = overlap
            best_page = i + 1

    return best_page


def _extract_tables(text: str) -> list[list[list[str]]]:
    """Extract simple markdown tables from text."""
    tables = []
    current_table = []
    for line in text.split("\n"):
        stripped = line.strip()
        if "|" in stripped and stripped.startswith("|"):
            # Skip separator lines
            if re.match(r"^[\s\-:|]+$", stripped.replace("|", "")):
                continue
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            current_table.append(cells)
        else:
            if current_table and len(current_table) > 1:
                tables.append(current_table)
            current_table = []

    if current_table and len(current_table) > 1:
        tables.append(current_table)

    return tables
