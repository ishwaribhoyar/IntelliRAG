# IntelliRAG — System Flows

## Data Flow (Upload to Index)

```
User uploads PDF/Excel
       │
       ▼
  File Validation (type, size, hash)
       │
       ▼
  Parser Router (heuristic scoring)
       │
  ┌────┴────┐
  ▼         ▼
PyMuPDF  Docling/OCR/Excel
  └────┬────┘
       ▼
  Normalizer (→ standard JSON: heading, level, page, content)
       │
       ▼
  Hierarchical Chunker
  ├── Parent chunks (section summaries)
  ├── Child chunks (paragraphs, 200-350 words, adaptive)
  └── Table chunks (Entity→Attribute→Value format)
       │
       ▼
  Dual Indexing
  ├── FAISS IndexFlatIP (cosine similarity)
  └── BM25 Index (keyword inverted index)
       │
       ▼
  Persisted to disk + cached in memory
  Status: READY
```

---

## User Flow (Query to Answer)

```
User types question
       │
       ▼
  Query Classifier (factual/analytical/procedural/comparison)
       │
       ▼
  Query Router (decides weights: vector vs BM25, top-k, rerank need)
       │
       ▼
  Query Expander (3 weighted variants)
       │
       ▼
  Hybrid Retrieval
  ├── FAISS vector search (per variant)
  ├── BM25 keyword search (per variant)
  └── RRF Fusion (reciprocal rank fusion)
       │
       ▼
  Conditional Reranker (Sarvam-M, only when scores are close)
       │
       ▼
  MMR Filter (remove duplicates, ensure diversity)
       │
       ▼
  Context Filter (token-safe truncation, best-chunk selection)
       │
       ▼
  Confidence Check (retrieval scores + chunk count)
  ├── Low confidence → Fallback: "Not found in document"
  └── OK → Continue
       │
       ▼
  Sarvam-M LLM (answer generation with source grounding)
       │
       ▼
  Response: {answer, sources, confidence, cached}
```

---

## System Flow (Background Pipeline)

```
Upload accepted → BackgroundTask started
       │
  ┌────┴────────────────────────────────┐
  │   Stage 1: PARSING                  │
  │   ├── Route parser (heuristic)      │
  │   ├── Extract content               │
  │   └── Update stage: "parsed"        │
  │                                      │
  │   Stage 2: STRUCTURING              │
  │   ├── Normalize to JSON schema      │
  │   └── Update stage: "structured"    │
  │                                      │
  │   Stage 3: CHUNKING + EMBEDDING     │
  │   ├── Hierarchical chunking         │
  │   └── Update stage: "embedded"      │
  │                                      │
  │   Stage 4: DUAL INDEXING            │
  │   ├── Build FAISS index             │
  │   ├── Build BM25 index              │
  │   ├── Persist both to disk          │
  │   └── Update stage: "indexed"       │
  │                                      │
  │   Status: READY ✓                   │
  └─────────────────────────────────────┘
```

---

## Search Engine Modes

```
Mode 1: KEYWORD (BM25 only)
  Query → BM25 search → Ranked chunks → Return

Mode 2: HYBRID (RRF fusion)
  Query → FAISS + BM25 → RRF → MMR → Ranked chunks → Return

Mode 3: AI (full pipeline)
  Query → FAISS + BM25 → RRF → Rerank → MMR → Filter
       → Confidence check → Sarvam-M → Answer + Sources
```
