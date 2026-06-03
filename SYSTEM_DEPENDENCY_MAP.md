# IntelliRAG — System Dependency Map

> Auto-generated audit. Do not edit manually. Regenerate after restructuring.

---

## 1. Feature → Files Used

| Feature | Backend Files | Frontend Files |
|---|---|---|
| **Upload Pipeline** | `api/routes.py` (upload, upload/multi, retry), `tasks/background.py`, `tasks/pipeline_queue.py`, `indexing/builder.py`, `indexing/vector_index.py`, `indexing/bm25_index.py`, `parser/router.py`, `parser/extractors.py`, `parser/normalizer.py`, `chunking/hierarchical.py` | `app.js` (uploadFile, handleUpload, pollStatus) |
| **Ask AI** | `api/routes.py` (ask, mentor), `rag/user_ask.py`, `rag/llm_client.py`, `retrieval/hybrid.py`, `retrieval/mmr.py`, `retrieval/context_filter.py`, `reranker/llm_reranker.py`, `query/expander.py`, `llm/trust.py`, `generators/prompts.py` | `app.js` (askAI, renderAnswer, mentorChat) |
| **Search Engine** | `api/routes.py` (search, search/suggest, search/user), `search/engine.py`, `search/spell.py`, `retrieval/hybrid.py`, `core/unified_hierarchy.py` | `search.js`, `app.js` |
| **Quiz** | `api/routes.py` (quiz/start, quiz/submit), `generators/quiz.py`, `generators/prompts.py`, `retrieval/hybrid.py`, `retrieval/mmr.py`, `personalization/tracker.py`, `rag/llm_client.py` | `app.js` (startQuiz, renderQuiz, submitQuiz) |
| **Flashcards** | `api/routes.py` (generate with content_type=flashcards), `generators/content.py`, `generators/prompts.py`, `retrieval/hybrid.py`, `rag/llm_client.py` | `app.js` (generateFlashcards, renderFlashcards) |
| **Summary** | `api/routes.py` (generate with content_type=summary), `generators/content.py`, `generators/prompts.py` | `app.js` |
| **Mock Test** | `api/routes.py` (generate with content_type=mock_test), `generators/quiz.py`, `generators/games/` | `app.js` |
| **Course View** | `api/routes.py` (course/structure, course/action, course/chat), `core/course_structure.py`, `core/unified_hierarchy.py`, `rag/llm_client.py`, `retrieval/hybrid.py` | `course.html`, `course.js`, `course.css` |
| **Content Library** | `api/routes.py` (library/*), `core/library.py`, `core/classifier.py`, `core/unified_hierarchy.py` | `app.js` (library tab) |
| **Weakness Dashboard** | `api/routes.py` (weakness), `personalization/tracker.py`, `personalization/advisor.py` | `app.js` (weaknessTab) |
| **Evaluation** | `api/routes.py` (evaluate/*, compare/*, system/report), `evaluation/runner.py`, `evaluation/metrics.py`, `evaluation/failure_analysis.py`, `evaluation/final_report.py` | none (API only) |
| **Gamification** | `api/routes.py` (leaderboard, score), `gamification/engine.py`, `gamification/leaderboard.py`, `gamification/levels.py` | `app.js` (XP display, leaderboard) |
| **Auth** | `api/routes.py` (register, login), `database.py` (User model) | `app.js` (login/register forms) |
| **PDF Viewer** | `api/routes.py` (pdf/{doc_id}), upload dir | `pdf-viewer.html` |
| **Trust Layer** | `llm/trust.py` | none |
| **Ingestion Queue** | `tasks/pipeline_queue.py` | none |

---

## 2. Tightly Coupled Modules (Problems)

### 2a. Circular Import Risk
```
rag/user_ask.py
  └── imports _ensure_doc_assets_ready from api/routes.py
      └── api/routes.py imports ask_user_library_ai from rag/user_ask.py
```
**Status**: Currently avoided only because `_ensure_doc_assets_ready` is imported inside the function body (`from app.api.routes import _ensure_doc_assets_ready`), not at module top level. This is fragile.

### 2b. Business Logic in Routes (routes.py)
- `_ensure_doc_assets_ready` — 50-line recovery orchestration
- `_ensure_auto_classified` — classification trigger logic
- `upload_document` — 150 lines including file hash, clone logic, queue management
- `search_endpoint` — search + breadcrumb normalization
- `course_action` — prompt construction inline
- `library_reclassify` — classification loop

### 2c. Retrieval Logic Duplicated
| Module | How it retrieves | Problem |
|---|---|---|
| `generators/quiz.py` | calls `retrieve_for_task()` | ✅ Uses shared core |
| `generators/content.py` | calls `retrieve_for_task()` | ✅ Uses shared core |
| `rag/user_ask.py` | calls `hybrid_retrieve()` directly with custom weights | ⚠️ Bypasses `retrieve_for_task()` |
| `search/engine.py` | calls `hybrid_retrieve()` directly | ⚠️ Bypasses `retrieve_for_task()` |
| `api/routes.py` (course_chat) | calls `retrieve_for_task()` | ✅ Uses shared core |

### 2d. LLM Provider Lock-In
All modules import `call_llm` from `rag/llm_client.py` which is 100% Sarvam-specific:
- `generators/quiz.py`
- `generators/content.py`
- `rag/user_ask.py`
- `api/routes.py` (course_action, course_chat)
- `reranker/llm_reranker.py`
- `core/classifier.py`
- `evaluation/runner.py`

---

## 3. Dead Code / Unused Items

| File | Issue |
|---|---|
| `generators/games/fill_blanks.py` | 195 bytes — nearly empty (contains only `# TODO`) |
| `generators/games/rapid_fire.py` | 211 bytes — nearly empty |
| `generators/games/true_false.py` | 192 bytes — nearly empty |
| `rag/chunker.py` | 1,605 bytes — thin wrapper; may be unused (background.py uses `chunking/hierarchical.py` directly) |
| `rag/vector_store.py` | May be superseded by `indexing/vector_index.py` |
| `rag/retriever.py` | May be superseded by `retrieval/hybrid.py` |

---

## 4. Conflicting Responsibilities

| Module | Primary Role | Also Does (Should Not) |
|---|---|---|
| `api/routes.py` | HTTP routing | Business logic, prompt building, cache management, document recovery, Pydantic model definitions |
| `generators/quiz.py` | Quiz generation | Retrieval, fallback answer building, JSON parsing |
| `rag/user_ask.py` | Ask AI orchestration | Retrieval strategy, reranking, caching, query normalization |
| `tasks/background.py` | Pipeline orchestration | Classification, library addition, hierarchy building |
| `core/unified_hierarchy.py` | Hierarchy storage | Also drives course structure migration/backfill |

---

## 5. All Files Inventory

### Backend (`backend/app/`)
```
main.py                       FastAPI app + lifespan
config.py                     All config (125 lines)
state.py                      In-memory caches + locks (90 lines)
database.py                   ORM models + init_db (206 lines)

api/routes.py                 ALL endpoints — 1628 lines ⚠️ MONOLITH

parser/router.py              Parser type selector
parser/extractors.py          PyMuPDF / Docling / Excel extractors
parser/normalizer.py          Text cleaning + section builder

chunking/hierarchical.py      Hierarchical chunker (9246 bytes)
chunking/validator.py         Chunk quality scorer (5983 bytes)

rag/embedder.py               MiniLM-L6-v2 embedding
rag/llm_client.py             Sarvam API client ⚠️ PROVIDER LOCK-IN
rag/user_ask.py               Ask AI orchestration ⚠️ CIRCULAR IMPORT RISK
rag/vector_store.py           FAISS store helpers (may be unused)
rag/retriever.py              Old retrieval shim (may be unused)
rag/chunker.py                Old chunking shim (may be unused)

indexing/builder.py           Index build + load orchestration
indexing/vector_index.py      FAISS build/search/delete
indexing/bm25_index.py        BM25 build/search/delete

retrieval/hybrid.py           RRF fusion (241 lines)
retrieval/mmr.py              MMR diversity filter
retrieval/context_filter.py   Token-budget context selection

query/classifier.py           Query type classifier
query/expander.py             Multi-query expansion
query/router.py               Strategy selection by query type

reranker/llm_reranker.py      BGE-style LLM reranker (5212 bytes)

llm/trust.py                  Confidence scoring + citations (6534 bytes)

evaluation/runner.py          Full eval pipeline (21889 bytes)
evaluation/metrics.py         Recall@k, MRR, hallucination
evaluation/failure_analysis.py  Failure patterns
evaluation/final_report.py    Combined system report
evaluation/test_dataset.json  80-query test dataset

generators/prompts.py         Prompt templates v4 (8586 bytes)
generators/quiz.py            Quiz + mock test generator (18629 bytes)
generators/content.py         Flashcards/summary/slides generator (11422 bytes)
generators/cache.py           Generated content cache cleaner
generators/games/fill_blanks.py  ⚠️ NEAR-EMPTY
generators/games/rapid_fire.py   ⚠️ NEAR-EMPTY
generators/games/true_false.py   ⚠️ NEAR-EMPTY

personalization/tracker.py    Topic accuracy tracker (10344 bytes)
personalization/advisor.py    Advice + study plan generator (4394 bytes)

gamification/engine.py        XP award system (3284 bytes)
gamification/leaderboard.py   Leaderboard cache (2389 bytes)
gamification/levels.py        Level thresholds (481 bytes)

search/engine.py              Search orchestration (5664 bytes)
search/spell.py               Autocomplete + spell suggest (7706 bytes)

core/classifier.py            LLM-based doc subject classifier (11315 bytes)
core/course_structure.py      Legacy course structure (7011 bytes)
core/library.py               Subject library manager (3143 bytes)
core/unified_hierarchy.py     Unified hierarchy CRUD (13130 bytes)

tasks/background.py           Full pipeline (12292 bytes)
tasks/pipeline_queue.py       Async worker pool (6093 bytes)
```

### Frontend (`backend/frontend/`)
```
index.html       SPA shell (24715 bytes) — all views
app.js           Full app logic (96985 bytes) ⚠️ MONOLITH
styles.css       Premium UI (43661 bytes)
course.html      Course reader
course.js        Course reader logic (15605 bytes)
course.css       Course reader styles (4314 bytes)
search.html      Search page
search.js        Search logic (9744 bytes) ✅ already separated
search.css       Search styles (896 bytes)
pdf-viewer.html  PDF viewer (12145 bytes)
favicon.svg
app-icon.svg
vercel.json
```
