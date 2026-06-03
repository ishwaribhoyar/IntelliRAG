# 📋 FEATURE_OWNERSHIP_MAP.md — Feature & Agent Ownership Map

This document establishes the relationship between IntelliRAG's 14 top-level capabilities, their directory/file layout, and their assigned specialized subagents.

---

## 1. Top-Level Capabilities & File Mappings

Below is the mapping of IntelliRAG's features to their corresponding backend modules, frontend files, and core engine files.

| Capability | Backend Feature Directory | Core/Module Directory | Frontend Files |
| :--- | :--- | :--- | :--- |
| **grounded_rag** | `backend/app/features/grounded_rag` | `backend/app/rag/`, `backend/app/modules/ask_ai/` | `index.html`, `app.js` (Chat section) |
| **search_engine** | `backend/app/features/search_engine` | `backend/app/query/`, `backend/app/retrieval/`, `backend/app/modules/search_engine/` | `search.html`, `search.js`, `search.css` |
| **smart_reranker** | `backend/app/features/smart_reranker` | `backend/app/reranker/` | N/A (Backend service) |
| **quiz_engine** | `backend/app/features/quiz_engine` | `backend/app/generators/quiz.py`, `backend/app/modules/quizzes/` | `index.html`, `app.js` (Quiz section) |
| **weakness_detection** | `backend/app/features/weakness_detection` | `backend/app/personalization/`, `backend/app/modules/weaknesses/` | `index.html`, `app.js` (Dashboard section) |
| **content_library** | `backend/app/features/content_library` | `backend/app/core/library.py`, `backend/app/modules/content_library/` | `index.html`, `app.js` (Library section) |
| **gamification** | `backend/app/features/gamification` | `backend/app/gamification/`, `backend/app/modules/gamification/` | `index.html`, `app.js` (Leaderboard section) |
| **evaluation_engine** | `backend/app/features/evaluation_engine` | `backend/app/evaluation/`, `backend/app/modules/evaluation/` | `index.html` (Admin eval tab) |
| **llm_platform** | `backend/app/features/llm_platform` | `backend/app/modules/llm_router/` | N/A (Internal router layer) |
| **ingestion_pipeline** | `backend/app/features/ingestion_pipeline` | `backend/app/parser/`, `backend/app/chunking/`, `backend/app/indexing/`, `backend/app/modules/upload_pipeline/` | `index.html` (Upload forms) |
| **course_system** | `backend/app/features/course_system` | `backend/app/core/course_structure.py`, `backend/app/modules/courses/` | `course.html`, `course.js`, `course.css` |
| **analytics** | `backend/app/features/analytics` | `backend/app/modules/analytics/` | `index.html` (Analytics dashboard) |
| **trust_layer** | `backend/app/features/trust_layer` | `backend/app/llm/` | `app.js` (Citation rendering) |
| **shared** | `backend/app/features/shared` | `backend/app/shared/`, `backend/app/database.py`, `backend/app/config.py`, `backend/app/main.py` | `styles.css` (Shared styling system) |

---

## 2. Specialized Subagent Ownership Map

The system uses six specialized subagents. Each agent is responsible for a distinct set of features and capabilities.

### 1. Retrieval Architect Agent
*   **Role**: Responsible for matching user queries to relevant context with high accuracy, speed, and diversity.
*   **Owned Capabilities**:
    *   `grounded_rag` (Retrieval phase)
    *   `search_engine` (Lexical, dense, hybrid, query expansion)
    *   `smart_reranker` (Reranking models & score processing)
*   **Owned Code Paths**:
    *   `backend/app/chunking/`
    *   `backend/app/indexing/`
    *   `backend/app/query/`
    *   `backend/app/retrieval/`
    *   `backend/app/reranker/`
    *   `backend/app/features/smart_reranker/`
    *   `backend/app/features/search_engine/`
    *   `backend/app/features/grounded_rag/`
*   **Boundary Enforcement**:
    *   Must not modify LLM prompting/generation logic directly.
    *   Must not modify UI templates (except search-related JSON responses).

### 2. LLM Platform Agent
*   **Role**: Responsible for robust, cost-effective LLM token delivery, dynamic routing, fallbacks, and token tracking.
*   **Owned Capabilities**:
    *   `llm_platform` (Unified provider wrapper & router)
*   **Owned Code Paths**:
    *   `backend/app/modules/llm_router/`
    *   `backend/app/rag/llm_client.py`
    *   `backend/app/features/llm_platform/`
*   **Boundary Enforcement**:
    *   Must not modify indexing/chunking logic.
    *   Must expose a unified interface (`call_llm`, `generate_structured_json`) that features can consume.

### 3. Frontend UX Agent
*   **Role**: Responsible for visual excellence, modern aesthetics (glassmorphism, animations), responsive layouts, and interactive user journeys.
*   **Owned Capabilities**:
    *   All user interfaces and interactions (Search UX, Course view, PDF reader integration, Flashcards/Quizzes, Leaderboard view)
*   **Owned Code Paths**:
    *   `backend/frontend/` (all `.html`, `.css`, and `.js` files)
*   **Boundary Enforcement**:
    *   Must not alter backend algorithms, DB schemas, or API schemas.
    *   Can only modify API integration code in `app.js`, `course.js`, `search.js`.

### 4. Evaluation Agent
*   **Role**: Responsible for auditing accuracy, measuring metrics (Recall@k, MRR, hallucination rates), and conducting automated regression testing on system changes.
*   **Owned Capabilities**:
    *   `evaluation_engine`
*   **Owned Code Paths**:
    *   `backend/app/evaluation/`
    *   `backend/app/modules/evaluation/`
    *   `backend/app/features/evaluation_engine/`
    *   `storage/evaluation/`
*   **Boundary Enforcement**:
    *   Must remain read-only relative to production features (can only call them, not change them).
    *   Responsible for asserting quality gates before feature merges.

### 5. AI Feature Agent
*   **Role**: Responsible for high-level study aids (Quizzes, Summaries, Flashcards) and personalization engines.
*   **Owned Capabilities**:
    *   `quiz_engine`
    *   `weakness_detection`
    *   `course_system`
    *   `trust_layer` (Trust/citation logic)
    *   `analytics` (Feature analytics processing)
    *   `gamification` (Score calculations & leaderboards)
*   **Owned Code Paths**:
    *   `backend/app/generators/`
    *   `backend/app/personalization/`
    *   `backend/app/gamification/`
    *   `backend/app/core/classifier.py`
    *   `backend/app/core/course_structure.py`
    *   `backend/app/core/unified_hierarchy.py`
    *   `backend/app/features/quiz_engine/`
    *   `backend/app/features/weakness_detection/`
    *   `backend/app/features/course_system/`
    *   `backend/app/features/trust_layer/`
    *   `backend/app/features/analytics/`
    *   `backend/app/features/gamification/`
*   **Boundary Enforcement**:
    *   Must request context retrieval through the Retrieval Architect's services.
    *   Must request LLM completion through the LLM Platform's router.

### 6. Infrastructure Agent
*   **Role**: Responsible for scale, async operations, storage management, DB migrations, caching, multi-upload tasks, and thread safety.
*   **Owned Capabilities**:
    *   `ingestion_pipeline` (Parsing infrastructure, background workers, queues)
    *   `content_library` (Catalog DB mapping & classification trigger)
    *   `shared` (Database connections, caching mechanisms, app state, config)
*   **Owned Code Paths**:
    *   `backend/app/parser/`
    *   `backend/app/tasks/`
    *   `backend/app/shared/`
    *   `backend/app/modules/upload_pipeline/`
    *   `backend/app/modules/content_library/`
    *   `backend/app/database.py`
    *   `backend/app/state.py`
    *   `backend/app/config.py`
    *   `backend/app/main.py`
    *   `storage/uploads/`
    *   `storage/chunks/`
*   **Boundary Enforcement**:
    *   Must not modify features/business logic directly.
    *   Exposes APIs for worker queues, cache access, and database sessions.

---

## 3. Communication Matrix

When a subagent needs functionality outside its boundary:
*   **Retrieval Architect** <---> **LLM Platform** (Retrieval uses LLM Platform for queries/reranks if needed).
*   **AI Feature Agent** <---> **Retrieval Architect** (Quiz/flashcard generation gets context).
*   **AI Feature Agent** <---> **LLM Platform** (Generation requests completions).
*   **Frontend UX Agent** <---> **Infrastructure Agent** (Frontend uploads files to Ingestion Pipeline).
*   **Evaluation Agent** <---> **Retrieval Architect & LLM Platform** (Evals audit search and LLM prompts).
