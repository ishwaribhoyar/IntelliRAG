"""Normalizer — converts all parser outputs into the standard JSON schema.
Upgraded: heading level detection (h1/h2/h3), page number tracking,
improved table extraction, robust multi-pattern heading parsing.
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
    """Split markdown or document text by headings (markdown #, bold titles, numbered chapters)."""
    if not text:
        return []

    # 1. First attempt: standard Markdown headings (#, ##, ###)
    md_heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    md_matches = list(md_heading_re.finditer(text))

    matches = []
    if md_matches:
        for m in md_matches:
            d = len(m.group(1))
            lvl = "h1" if d == 1 else ("h2" if d == 2 else "h3")
            title = m.group(2).strip()
            matches.append((lvl, title, m.start(), m.end()))
    else:
        # 2. Second attempt: Bold headings from pymupdf4llm / structured text
        # Patterns like: **1. Introduction to Python**, **3.1 Immutable Types**, **Chapter 1: ...**
        bold_re = re.compile(r"^\*\*(.+?)\*\*\s*$", re.MULTILINE)
        skip_words = {
            "example", "output", "note", "syntax", "explanation", "solution",
            "code", "tip", "warning", "important", "key concepts", "core concepts",
            "definition", "preview", "details", "overview"
        }
        for m in bold_re.finditer(text):
            raw_t = m.group(1).strip()
            t_clean = raw_t.rstrip(':').strip()
            if t_clean.lower() in skip_words:
                continue
            if len(t_clean) < 3 or len(t_clean) > 85:
                continue
            num_m = re.match(r"^(\d+(?:\.\d+)*)\.?\s*(.+)$", t_clean)
            if num_m:
                dots = num_m.group(1).count('.')
                lvl = "h1" if dots == 0 else ("h2" if dots == 1 else "h3")
                matches.append((lvl, t_clean, m.start(), m.end()))
            elif t_clean.isupper() or t_clean.istitle() or re.match(r"^(?:Chapter|Unit|Module|Section|Lesson)\b", t_clean, re.I):
                matches.append(("h2", t_clean, m.start(), m.end()))
            elif len(t_clean.split()) <= 6 and not t_clean.endswith('.'):
                matches.append(("h3", t_clean, m.start(), m.end()))

        # 3. Third attempt: Numbered lines in plain text e.g. "1. Introduction" or "1.1 Overview"
        if not matches:
            plain_re = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+([A-Z][A-Za-z0-9\s,\(\)/_-]{2,60})\s*$", re.MULTILINE)
            for m in plain_re.finditer(text):
                t = m.group(0).strip()
                dots = m.group(1).count('.')
                lvl = "h1" if dots == 0 else ("h2" if dots == 1 else "h3")
                matches.append((lvl, t, m.start(), m.end()))

    if not matches:
        return []

    sections = []
    for i, (lvl, heading, start, end_pos) in enumerate(matches):
        next_start = matches[i + 1][2] if i + 1 < len(matches) else len(text)
        content = text[end_pos:next_start].strip()

        # Estimate which page this section belongs to
        page = _estimate_page(content, pages_text) if pages_text else 1

        sections.append({
            "heading": heading,
            "level": lvl,
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
