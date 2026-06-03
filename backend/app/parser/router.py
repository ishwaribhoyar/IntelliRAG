"""Intelligent parser router — heuristic-based document type detection."""
import re
import logging

logger = logging.getLogger(__name__)


def compute_complexity_score(text: str, page_count: int = 1) -> dict:
    """Fast heuristic scoring (<10ms) to decide parser route.

    Returns dict with scores and recommended parser.
    """
    if not text or not text.strip():
        return {"has_text": False, "parser": "ocr", "score": 0}

    lines = text.split("\n")
    non_empty_lines = [l for l in lines if l.strip()]
    word_count = len(text.split())

    # Heuristic signals
    text_length = len(text)
    line_density = len(non_empty_lines) / max(page_count, 1)
    avg_line_length = text_length / max(len(non_empty_lines), 1)

    # Table patterns (pipes, tabs, repeated delimiters)
    table_pattern = re.compile(r"(\|.*\|)|(\t.*\t)|(_{3,})|(─{3,})|(┌|┐|└|┘|├|┤)")
    table_matches = len(table_pattern.findall(text))

    # Excessive line breaks (sign of complex layout)
    empty_line_ratio = (len(lines) - len(non_empty_lines)) / max(len(lines), 1)

    # Complexity score
    complexity = 0
    if table_matches > 3:
        complexity += 40
    if avg_line_length < 30:
        complexity += 15  # may be columnar layout
    if empty_line_ratio > 0.4:
        complexity += 10
    if line_density > 80:
        complexity += 10

    # Route decision
    if complexity >= 40:
        parser = "docling"
    else:
        parser = "pymupdf"

    return {
        "has_text": True,
        "parser": parser,
        "score": complexity,
        "word_count": word_count,
        "table_matches": table_matches,
        "line_density": line_density,
    }


def route_parser(text: str, page_count: int = 1) -> str:
    """Return parser name: 'ocr', 'docling', or 'pymupdf'."""
    result = compute_complexity_score(text, page_count)
    logger.info(f"Router decision: {result['parser']} (score={result['score']})")
    return result["parser"]
