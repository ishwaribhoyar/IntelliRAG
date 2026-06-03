# IntelliRAG — System Overview

## What Is This System?

IntelliRAG is a **production-ready Advanced AI Document Retrieval + Learning System**. It transforms raw documents (PDF/Excel) into an intelligent, searchable, testable knowledge base — powered by hybrid search, AI-driven Q&A, and adaptive learning.

**Positioning:** This is a **retrieval system**, not a chatbot. Every answer is grounded in uploaded document content. The AI never hallucinate beyond what the document contains.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  IntelliRAG ARCHITECTURE                   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Upload → Parse → Normalize → Chunk → Index (FAISS+BM25) │
│                                                          │
│  Query → Classify → Route → Hybrid Search (RRF)         │
│       → Rerank → MMR Filter → Context Filter             │
│       → Sarvam-M LLM → Trust Score → Response           │
│                                                          │
│  Quiz → Evaluate → Track Topics → Detect Weakness        │
│       → Recommend → Adaptive Learning                    │
│                                                          │
│  Library → Subject-based → Pre-indexed → Instant Load    │
│                                                          │
│  Search Engine: Keyword | Hybrid | AI (3 modes)          │
│                                                          │
│  Gamification: XP → Levels → Leaderboard → Engagement   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Design Decisions

| Decision | Rationale |
|---|---|
| **MiniLM over BGE** | 80MB vs 1.3GB — fast startup, low memory, good enough for retrieval |
| **Pure-Python BM25** | No external dependency, ~100 lines, per-document indexes |
| **RRF over learned fusion** | Simple, effective, no training data needed |
| **LLM reranker (not model)** | Uses existing Sarvam-M API — no new model download |
| **SQLite only** | Single-file DB, no server, deployment-simple |
| **Hierarchical chunking** | Parent (section-level) + child (paragraph-level) improves retrieval precision |
| **Write-behind XP cache** | Instant UX feedback, DB writes batched every 15s |
| **Stage-based pipeline** | Resumable processing — crash recovery without data loss |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn (async) |
| LLM | Sarvam-M (OpenAI-compatible API) |
| Embeddings | all-MiniLM-L6-v2 (384-dim) |
| Vector DB | FAISS (IndexFlatIP, cosine) |
| Keyword Search | Pure-Python BM25 |
| Fusion | Reciprocal Rank Fusion (RRF) |
| Database | SQLite + SQLAlchemy |
| Frontend | Vanilla HTML/JS/CSS |
