# ⚠️ RISK_ANALYSIS.md — System Risk & Mitigation Analysis

This document identifies the critical paths, latency hotspots, unsafe dependencies, merge risks, and stability boundaries of the IntelliRAG platform.

---

## 1. Core Latency Hotspots

### A. Rerank Chunks Sequential Overhead
*   **Risk**: Scoring 8 chunks sequentially in `backend/app/reranker/llm_reranker.py` takes up to **2.5s–4s** on cache misses.
*   **Mitigation**: Run LLM queries concurrently using `asyncio.gather`. 
*   **Critical Guard**: Must wrap concurrent requests in an `asyncio.Semaphore(max_concurrency)` to avoid overloading third-party APIs (e.g., rate limits/concurrency exhaustion).

### B. CPU-Bound Parsing in Background Workers
*   **Risk**: Background text extraction via heavy libraries like `Docling` or `PDFMiner` runs on the main async event loop thread if not offloaded. This blocks the API from responding to health checks/other requests.
*   **Mitigation**: Offload CPU-bound parsing tasks to a `ThreadPoolExecutor` or `ProcessPoolExecutor`.

---

## 2. Dependency & Code Coupling Risks

### A. Circular Imports & Monolith Routes
*   **Risk**: `backend/app/api/routes.py` is a 1,600+ line monolithic file importing from many sub-modules, which then import from routes or utilities.
*   **Mitigation**: Keep imports localized inside service functions where possible, or move utilities out of routes into shared layers (completed for `doc_utils.py`).

### B. LLM Provider Lock-in
*   **Risk**: All generative features (quizzes, flashcards, RAG answering) directly import from `app.rag.llm_client.call_llm` instead of using the `llm_router`.
*   **Mitigation**: Implement real providers inside `app.modules.llm_router.providers` (Gemini, OpenAI, DeepSeek) and update `call_llm` as a compatibility shim redirecting calls to `llm_router.generate()`.

---

## 3. Concurrency & Scale Risks

### A. SQLite Concurrency (Database Locks)
*   **Risk**: SQLite uses file-level locking. High concurrency of document uploads, user answers, and gamification writes can cause `sqlite3.OperationalError: database is locked`.
*   **Mitigation**: Enable Write-Ahead Logging (WAL) mode for the database and set query timeouts. Ensure sessions are strictly scoped using `try/finally` or context managers.

### B. Queue Collapse under 1000+ Concurrent Users
*   **Risk**: The in-memory task queue in `tasks/pipeline_queue.py` holds tasks in memory. If the server crashes or restarts, all queued document jobs are lost.
*   **Mitigation**: Add status tracking in SQLite so tasks are marked as `pending` and can be recovered/resumed upon worker startup.

---

## 4. Frontend & Visual Stability Risks

### A. Search -> PDF Jump Offset Alignment
*   **Risk**: Highlighting searched chunks in `pdf-viewer.html` fails or scrolls to the wrong position if the coordinate math is incorrect or the page is still rendering.
*   **Mitigation**: Validate the PDF viewer loading sequence. Ensure coordinates are rendered and scrolled only after the page canvas is fully initialized.

### B. LLM Response Parse Failure
*   **Risk**: Quiz/Flashcard generation expects structured JSON. If the LLM returns unstructured text, JSON parsing throws an exception, leading to a broken UI state.
*   **Mitigation**: Use strict JSON schema generation prompts, schema-enforcing provider capabilities, and robust schema-recovery fallbacks in `quiz.py` and `content.py`.
