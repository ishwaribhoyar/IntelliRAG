"""BM25 keyword index — FIXED tokenization, per-document, with persistence."""
import json
import math
import re
import logging
from collections import Counter
from app.config import CHUNKS_DIR

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """FIXED tokenizer: lowercase → strip non-alphanumeric → remove stopwords."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9 ]', '', text)
    tokens = text.split()

    # Comprehensive stopword set
    stopwords = frozenset({
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "must",
        "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
        "this", "that", "these", "those", "it", "its",
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "they",
        "what", "which", "who", "whom", "how", "when", "where", "why",
        "if", "then", "than", "also", "just", "very", "too", "more",
        "each", "every", "all", "any", "some", "no", "only",
    })

    return [t for t in tokens if len(t) > 1 and t not in stopwords]


class BM25Index:
    """BM25 ranking for a single document's chunks.

    Parameters:
        k1: term frequency saturation (1.2–2.0 typical)
        b:  length normalisation (0.75 typical)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunk_ids: list[str] = []
        self.doc_freqs: dict[str, int] = {}
        self.term_freqs: list[dict[str, int]] = []
        self.doc_lengths: list[int] = []
        self.avg_dl: float = 0.0
        self.n_docs: int = 0

    def build(self, chunks: list[dict]):
        """Build BM25 index from chunk list."""
        self.chunk_ids = [c["chunk_id"] for c in chunks]
        self.n_docs = len(chunks)
        self.doc_freqs = {}
        self.term_freqs = []
        self.doc_lengths = []

        for chunk in chunks:
            tokens = _tokenize(chunk["text"])
            tf = Counter(tokens)
            self.term_freqs.append(dict(tf))
            self.doc_lengths.append(len(tokens))

            for term in set(tokens):
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        total_len = sum(self.doc_lengths)
        self.avg_dl = total_len / max(self.n_docs, 1)

        logger.info(
            f"BM25 index built: {self.n_docs} chunks, "
            f"{len(self.doc_freqs)} unique terms, "
            f"avg_dl={self.avg_dl:.1f}"
        )

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Search BM25 index. Returns list of (chunk_id, score) sorted descending."""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = []
        for i in range(self.n_docs):
            score = 0.0
            dl = self.doc_lengths[i]
            tf_dict = self.term_freqs[i]

            for term in query_tokens:
                if term not in self.doc_freqs:
                    continue

                tf = tf_dict.get(term, 0)
                if tf == 0:
                    continue

                df = self.doc_freqs[term]
                idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1.0)
                tf_norm = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
                )
                score += idf * tf_norm

            if score > 0:
                scores.append((self.chunk_ids[i], score))

        scores.sort(key=lambda x: x[1], reverse=True)

        # Debug log
        if scores:
            logger.debug(
                f"BM25 search '{query[:40]}' → {len(scores)} hits, "
                f"top={scores[0][1]:.4f}"
            )

        return scores[:top_k]

    def to_dict(self) -> dict:
        return {
            "k1": self.k1, "b": self.b,
            "chunk_ids": self.chunk_ids,
            "doc_freqs": self.doc_freqs,
            "term_freqs": self.term_freqs,
            "doc_lengths": self.doc_lengths,
            "avg_dl": self.avg_dl,
            "n_docs": self.n_docs,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BM25Index":
        idx = cls(k1=data["k1"], b=data["b"])
        idx.chunk_ids = data["chunk_ids"]
        idx.doc_freqs = data["doc_freqs"]
        idx.term_freqs = data["term_freqs"]
        idx.doc_lengths = data["doc_lengths"]
        idx.avg_dl = data["avg_dl"]
        idx.n_docs = data["n_docs"]
        return idx


# --- Persistence ---

def save_bm25_index(doc_id: str, index: BM25Index):
    path = CHUNKS_DIR / f"{doc_id}_bm25.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index.to_dict(), f, ensure_ascii=False)
    logger.info(f"Saved BM25 index for {doc_id}")


def load_bm25_index(doc_id: str) -> BM25Index | None:
    path = CHUNKS_DIR / f"{doc_id}_bm25.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded BM25 index for {doc_id}")
        return BM25Index.from_dict(data)
    except Exception as e:
        logger.error(f"Failed to load BM25 index for {doc_id}: {e}")
        return None


def delete_bm25_index(doc_id: str):
    path = CHUNKS_DIR / f"{doc_id}_bm25.json"
    if path.exists():
        path.unlink()
        logger.info(f"Deleted BM25 index for {doc_id}")
