"""Query classifier — rule-based query type detection for routing."""
import re
import logging

logger = logging.getLogger(__name__)


# Query types
FACTUAL = "factual"        # what, who, when, define, name
ANALYTICAL = "analytical"  # why, how, explain, compare
PROCEDURAL = "procedural"  # how to, steps, process
COMPARISON = "comparison"  # vs, difference, compare X and Y


# Pattern rules (order matters — first match wins)
_RULES = [
    (COMPARISON, [
        r'\bvs\.?\b', r'\bdifference\b', r'\bcompare\b', r'\bcompar',
        r'\bbetween\b.*\band\b', r'\bversus\b',
    ]),
    (PROCEDURAL, [
        r'\bhow\s+to\b', r'\bsteps?\s+(for|to)\b', r'\bprocess\b',
        r'\bprocedure\b', r'\bimplementa?t?\b',
    ]),
    (ANALYTICAL, [
        r'\bwhy\b', r'\bhow\s+does\b', r'\bhow\s+is\b', r'\bexplain\b',
        r'\banalyse\b', r'\banalyze\b', r'\bcause\b', r'\breason\b',
        r'\bimpact\b', r'\beffect\b', r'\brelation\b',
    ]),
    (FACTUAL, [
        r'\bwhat\b', r'\bwho\b', r'\bwhen\b', r'\bwhere\b', r'\bwhich\b',
        r'\bdefine\b', r'\bdefinition\b', r'\bname\b', r'\blist\b',
        r'\bis\b', r'\bare\b',
    ]),
]


def classify_query(query: str) -> str:
    """Classify a query into a type using rule-based pattern matching.

    Returns: 'factual' | 'analytical' | 'procedural' | 'comparison'
    """
    q_lower = query.lower().strip()

    for qtype, patterns in _RULES:
        for pattern in patterns:
            if re.search(pattern, q_lower):
                logger.debug(f"Query classified as {qtype}: '{query[:60]}'")
                return qtype

    # Default to factual for short queries, analytical for long
    word_count = len(q_lower.split())
    default = FACTUAL if word_count <= 5 else ANALYTICAL
    logger.debug(f"Query classified as {default} (default): '{query[:60]}'")
    return default


def get_query_complexity(query: str) -> str:
    """Estimate query complexity: 'simple' | 'moderate' | 'complex'."""
    words = query.split()
    if len(words) <= 4:
        return "simple"
    elif len(words) <= 12:
        return "moderate"
    else:
        return "complex"
