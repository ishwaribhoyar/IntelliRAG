# 🏗️ SYSTEM_TREE.md — IntelliRAG Enterprise AI Learning Platform

> **Architecture**: Feature-Centric Hierarchical  
> **Version**: 2.0.0  
> **Last Updated**: 2026-05-21  

---

## 📐 Architecture Layers

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (feature tree)                           │
│   grounded_rag │ search_engine │ quiz_engine │ content_library │ ...     │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ HTTP / REST
┌────────────────────────────▼─────────────────────────────────────────────┐
│                    FEATURE HIERARCHY (app.features)                      │
│  14 top-level capabilities, each owning its sub-features                 │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ re-exports (thin wrappers)
┌────────────────────────────▼─────────────────────────────────────────────┐
│                    MODULE LAYER (app.modules)                            │
│  Routes + Services per feature — the preferred API layer                │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ calls
┌────────────────────────────▼─────────────────────────────────────────────┐
│                    CORE ENGINE LAYER (app.*)                             │
│  rag │ retrieval │ search │ reranker │ query │ evaluation │ ...          │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ uses
┌────────────────────────────▼─────────────────────────────────────────────┐
│                    SHARED INFRASTRUCTURE (app.shared)                    │
│  database │ caching │ schemas │ storage │ utils                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🌳 Full Feature Tree

### 🧠 1. GROUNDED RAG (`app.features.grounded_rag`)
**Category**: `core_ai` | **API**: `/api/ask`

```
grounded_rag/
├── ask_ai/              → app.modules.ask_ai          (HTTP routes + handlers)
├── query_understanding/ → app.query                   (classify, expand, route)
├── retrieval/           → app.retrieval               (hybrid FAISS+BM25+RRF)
├── answer_generation/   → app.rag + app.generators    (LLM generation)
├── hallucination_control→ app.llm.trust               (trust scoring)
├── grounding/           → app.retrieval               (context filtering)
├── context_window/      → app.rag.user_ask            (retrieval pipeline)
├── citations/           → (metadata from retrieval)
└── confidence/          → app.llm.trust               (confidence compute)
```

**Depends on**: `shared.retrieval_core` → `shared.embedding_core` → `trust_layer` → `llm_platform`

---

### 🔍 2. SEARCH ENGINE (`app.features.search_engine`)
**Category**: `core_ai` | **API**: `/api/search`

```
search_engine/
├── keyword_search/  → app.search.engine         (BM25 search)
├── hybrid_search/   → app.retrieval.hybrid      (FAISS+BM25+RRF)
├── vector_search/   → app.rag.vector_store      (FAISS dense)
├── typo_correction/ → app.search.spell          (spell suggestion)
├── autocomplete/    → app.search.spell          (autocomplete)
├── query_routing/   → app.query.router          (intent routing)
├── search_ranking/  → app.reranker              (LLM reranking)
├── indexing/        → app.indexing              (index building)
├── suggestions/     → (stub — future)
└── navigation/      → (stub — future)
```

**Depends on**: `shared.retrieval_core` → `shared.vector_core` → `smart_reranker`

---

### 🎯 3. SMART RERANKER (`app.features.smart_reranker`)
**Category**: `core_ai` | **API**: _(internal)_

```
smart_reranker/
├── llm_reranking/      → app.reranker.llm_reranker  (LLM-based reranking)
├── mmr/                → app.retrieval.mmr          (Maximal Marginal Relevance)
├── conditional_rerank/ → app.reranker               (score-gap logic)
├── score_gap_logic/    → app.reranker               (gap-based triggering)
├── diversity/          → app.retrieval.mmr          (diversity enforcement)
├── rerank_metrics/     → (stub — future telemetry)
└── latency_control/    → (stub — future)
```

**Depends on**: `llm_platform`

---

### 📝 4. QUIZ ENGINE (`app.features.quiz_engine`)
**Category**: `learning` | **API**: `/api/quiz`

```
quiz_engine/
├── quiz_generation/     → app.generators.quiz       (quiz + MCQ generation)
├── question_generation/ → app.generators.content    (content generation)
├── mcq_generation/      → app.generators.games      (game-style MCQs)
├── flashcards/          → app.modules.flashcards    (flashcard feature)
├── mock_tests/          → app.generators.games      (rapid-fire, true/false)
├── summaries/           → app.generators.content    (summary generation)
├── scoring/             → app.gamification.engine   (XP scoring)
├── analytics/           → app.modules.analytics     (quiz analytics)
├── grading/             → (stub — future LLM grading)
├── retry/               → (stub — future)
└── refresh/             → (stub — future)
```

**Depends on**: `shared.retrieval_core` → `llm_platform` → `gamification`

---

### 📊 5. WEAKNESS DETECTION (`app.features.weakness_detection`)
**Category**: `learning` | **API**: `/api/weakness`

```
weakness_detection/
├── topic_tracking/         → app.personalization.tracker  (per-topic recording)
├── weak_topic_detection/   → app.personalization.tracker  (gap detection)
├── recommendation_engine/  → app.personalization.advisor  (AI recommendations)
├── learning_patterns/      → app.personalization.tracker  (trend analysis)
├── progress_analysis/      → app.personalization.tracker  (progress metrics)
├── study_guidance/         → app.personalization.advisor  (study plans)
└── confidence_analysis/    → (stub — future)
```

**Depends on**: `shared.database` → `llm_platform`

---

### 📚 6. CONTENT LIBRARY (`app.features.content_library`)
**Category**: `content` | **API**: `/api/library`

```
content_library/
├── uploads/            → app.modules.upload_pipeline   (PDF upload)
├── pdf_management/     → app.parser                    (PDF extraction)
├── auto_classification/→ app.core.classifier           (subject/topic classify)
├── hierarchy_builder/  → app.core.unified_hierarchy    (hierarchy building)
├── subject_detection/  → app.core.classifier           (subject-level detect)
├── topic_detection/    → app.core.classifier           (topic-level detect)
├── subtopic_mapping/   → app.core.unified_hierarchy    (subtopic mapping)
├── storage/            → app.shared.storage            (file paths)
├── metadata/           → app.core.library              (catalog)
└── deletion/           → app.modules.upload_pipeline   (doc deletion)
```

**Depends on**: `ingestion_pipeline` → `shared.database`

---

### 🏆 7. GAMIFICATION (`app.features.gamification`)
**Category**: `engagement` | **API**: `/api/gamification`

```
gamification/
├── xp/               → app.gamification.engine      (XP awards)
├── levels/           → app.gamification.levels      (level thresholds)
├── leaderboard/      → app.gamification.leaderboard (leaderboard)
├── activity_tracking/→ app.gamification.engine      (activity log)
├── badges/           → (stub — future)
├── streaks/          → (stub — future)
└── rewards/          → (stub — future)
```

**Depends on**: `shared.database`

---

### 🛡️ 8. TRUST LAYER (`app.features.trust_layer`)
**Category**: `core_ai` | **API**: _(internal)_

```
trust_layer/
├── confidence/            → app.llm.trust  (compute_confidence)
├── hallucination_detection→ app.llm.trust  (heuristic detection)
├── fallback_logic/        → app.llm.trust  (should_fallback)
├── answer_validation/     → app.llm.trust  (quality checks)
├── uncertainty_detection/ → app.llm.trust  (low confidence)
├── citation_validation/   → (stub — future)
└── grounding_validation/  → (stub — future)
```

**Depends on**: _(standalone)_

---

### 📈 9. EVALUATION ENGINE (`app.features.evaluation_engine`)
**Category**: `platform` | **API**: `/api/evaluate`

```
evaluation_engine/
├── recall/          → app.evaluation.metrics          (Recall@K)
├── mrr/             → app.evaluation.metrics          (MRR)
├── hallucination/   → app.evaluation.metrics          (hallucination rate)
├── benchmarks/      → app.evaluation.runner           (eval runner)
├── failure_analysis/→ app.evaluation.failure_analysis (failure cases)
├── reports/         → app.evaluation.final_report     (report gen)
├── latency/         → (stub — future)
├── ablation/        → (stub — future)
├── logging/         → (stub — future)
└── metrics_storage/ → (stub — future)
```

**Depends on**: `grounded_rag` → `search_engine`

---

### 🤖 10. LLM PLATFORM (`app.features.llm_platform`)
**Category**: `platform` | **API**: _(internal)_

```
llm_platform/
├── providers/        → app.modules.llm_router.providers  (7 providers)
├── model_router/     → app.modules.llm_router.router     (LLMRouter)
├── prompt_management/→ app.generators.prompts            (13 prompt templates)
├── fallback/         → app.modules.llm_router            (fallback chain)
├── streaming/        → (stub — future)
├── token_tracking/   → (stub — future)
├── cost_tracking/    → (stub — future)
└── provider_metrics/ → (stub — future)
```

**Providers**: Gemini · OpenAI · Anthropic · Groq · Ollama · OpenRouter · Sarvam  
**Depends on**: _(standalone — no feature dependencies)_

---

### ⚙️ 11. INGESTION PIPELINE (`app.features.ingestion_pipeline`)
**Category**: `content` | **API**: `/api/upload`

```
ingestion_pipeline/
├── pdf_parsing/ → app.parser              (extractors, normalizer, router)
├── chunking/    → app.chunking            (hierarchical chunker + validator)
├── indexing/    → app.indexing            (FAISS + BM25 index building)
├── queue/       → app.tasks.pipeline_queue(async job queue)
├── background/  → app.tasks.background   (flush workers)
├── validation/  → app.chunking.validator  (chunk quality)
└── storage/     → app.shared.storage     (path utilities)
```

**Depends on**: `shared.embedding_core` → `shared.vector_core` → `shared.database`

---

### 📖 12. COURSE SYSTEM (`app.features.course_system`)
**Category**: `learning` | **API**: `/api/course`

```
course_system/
├── structure/ → app.core.course_structure   (course generation)
├── hierarchy/ → app.core.unified_hierarchy  (topic tree)
├── routes/    → app.modules.courses         (HTTP routes)
└── progress/  → app.personalization.tracker (progress tracking)
```

**Depends on**: `content_library` → `grounded_rag` → `weakness_detection`

---

### 📊 13. ANALYTICS (`app.features.analytics`)
**Category**: `platform` | **API**: `/api/analytics`

```
analytics/
├── routes/  → app.modules.analytics.routes  (HTTP endpoints)
├── metrics/ → (stub — future aggregation)
└── reports/ → (stub — future reporting)
```

**Depends on**: `shared.database`

---

### 🔧 14. SHARED ENGINE LAYER (`app.features.shared`)
**Category**: `infrastructure` | **API**: _(internal)_

```
shared/
├── retrieval_core/ → app.retrieval        (hybrid FAISS+BM25+RRF, MMR, context filter)
├── embedding_core/ → app.rag.embedder     (sentence-transformer, warmup)
├── vector_core/    → app.rag.vector_store (FAISS index operations)
├── ranking_core/   → app.reranker         (LLM reranking)
├── caching/        → app.shared.caching   (in-memory doc cache)
├── auth/           → app.modules.auth     (JWT authentication)
├── database/       → app.shared.database  (SQLAlchemy models + session)
├── logging/        → app.core.logging     (structured logging)
└── utils/          → app.shared.utils     (doc + search utilities)
```

---

## 🔗 Feature Dependency Graph

```
                 ┌──────────────────┐
                 │   llm_platform   │ ◄── (all AI features)
                 └────────┬─────────┘
                          │
          ┌───────────────┼──────────────────┐
          ▼               ▼                  ▼
   ┌─────────────┐ ┌────────────┐   ┌──────────────┐
   │ grounded_rag│ │quiz_engine │   │smart_reranker│
   └──────┬──────┘ └────────────┘   └──────────────┘
          │                                  ▲
          │ uses                             │ used by
          ▼                                  │
   ┌─────────────────────────────────────────┴──────┐
   │            shared.retrieval_core               │
   │  (hybrid_retrieve │ mmr_filter │ filter_context)│
   └────────────────────────────────────────────────┘

   ┌───────────────────┐     ┌──────────────────────┐
   │ content_library   │────►│ ingestion_pipeline   │
   └───────────────────┘     └──────────────────────┘
          │                          │
          ▼                          ▼
   ┌────────────┐           ┌────────────────┐
   │course_system│          │shared.embedding│
   └────────────┘           │shared.vector   │
                            └────────────────┘

   ┌─────────────────────┐
   │  evaluation_engine  │──► (consumes grounded_rag + search_engine output)
   └─────────────────────┘

   ┌─────────────────────┐     ┌───────────────┐
   │ weakness_detection  │────►│  gamification │
   └─────────────────────┘     └───────────────┘
          Both depend on: shared.database
```

---

## 🖥️ Frontend Feature Tree

```
frontend/features/
├── grounded_rag/
│   ├── components/   (UI components for ask-AI interface)
│   ├── pages/        (Ask AI page logic)
│   ├── styles/       (feature-specific CSS)
│   ├── state/        (local state management)
│   └── services/     (API call wrappers → /api/ask)
├── search_engine/
│   ├── components/   (search bar, results, autocomplete)
│   ├── pages/        (search page logic)
│   ├── styles/
│   ├── state/
│   └── services/     (→ /api/search)
├── quiz_engine/
│   ├── components/   (quiz cards, flashcards, games)
│   ├── pages/        (quiz page logic)
│   ├── styles/
│   ├── state/
│   └── services/     (→ /api/quiz)
├── content_library/
│   ├── components/   (library cards, upload UI)
│   ├── pages/        (library page logic)
│   ├── styles/
│   ├── state/
│   └── services/     (→ /api/library, /api/upload)
├── weaknesses/
│   ├── components/   (weakness dashboard, topic charts)
│   ├── pages/
│   ├── styles/
│   ├── state/
│   └── services/     (→ /api/weakness)
├── gamification/
│   ├── components/   (XP bar, leaderboard, badges)
│   ├── pages/
│   ├── styles/
│   ├── state/
│   └── services/     (→ /api/gamification)
├── courses/
│   ├── components/   (course tree, chapter cards)
│   ├── pages/
│   ├── styles/
│   ├── state/
│   └── services/     (→ /api/course)
└── analytics/
    ├── components/   (charts, dashboards)
    ├── pages/
    ├── styles/
    ├── state/
    └── services/     (→ /api/analytics)
```

---

## 📁 Full Backend File Tree

```
backend/
├── app/
│   ├── feature_registry.py          ← Central feature registry (NEW)
│   │
│   ├── features/                    ← Feature hierarchy layer (NEW)
│   │   ├── grounded_rag/
│   │   ├── search_engine/
│   │   ├── smart_reranker/
│   │   ├── quiz_engine/
│   │   ├── weakness_detection/
│   │   ├── content_library/
│   │   ├── gamification/
│   │   ├── trust_layer/
│   │   ├── evaluation_engine/
│   │   ├── llm_platform/
│   │   ├── ingestion_pipeline/
│   │   ├── course_system/
│   │   ├── analytics/
│   │   └── shared/
│   │
│   ├── modules/                     ← Module layer (existing — UNCHANGED)
│   │   ├── ask_ai/         (routes + service)
│   │   ├── auth/           (routes + service)
│   │   ├── analytics/      (routes)
│   │   ├── content_library/(routes + service)
│   │   ├── courses/        (routes + service)
│   │   ├── evaluation/     (routes)
│   │   ├── flashcards/     (routes + service)
│   │   ├── gamification/   (routes)
│   │   ├── llm_router/     (providers, router, base)
│   │   ├── quizzes/        (routes + service)
│   │   ├── search_engine/  (routes + service)
│   │   ├── upload_pipeline/(routes + service)
│   │   └── weaknesses/     (routes + service)
│   │
│   ├── shared/                      ← Shared infra (existing — UNCHANGED)
│   │   ├── caching/
│   │   ├── database/
│   │   ├── schemas/
│   │   ├── storage/
│   │   └── utils/
│   │
│   ├── core/                        ← Core engines (existing — UNCHANGED)
│   │   ├── classifier.py
│   │   ├── course_structure.py
│   │   ├── library.py
│   │   ├── unified_hierarchy.py
│   │   ├── exceptions/
│   │   └── logging/
│   │
│   ├── rag/          (embedder, retriever, llm_client, vector_store, user_ask)
│   ├── retrieval/    (hybrid, mmr, context_filter)
│   ├── search/       (engine, spell)
│   ├── reranker/     (llm_reranker)
│   ├── query/        (classifier, expander, router)
│   ├── evaluation/   (metrics, runner, failure_analysis, final_report)
│   ├── generators/   (quiz, content, prompts, games, cache)
│   ├── gamification/ (engine, leaderboard, levels)
│   ├── personalization/ (tracker, advisor)
│   ├── chunking/     (hierarchical, validator)
│   ├── indexing/     (bm25_index, builder, vector_index)
│   ├── parser/       (extractors, normalizer, router)
│   ├── llm/          (trust)
│   ├── tasks/        (background, pipeline_queue)
│   ├── api/          (routes — legacy backward-compat)
│   ├── main.py       (FastAPI app entry point)
│   ├── config.py
│   ├── database.py
│   └── state.py
│
└── frontend/
    ├── features/                    ← Frontend feature tree (NEW)
    │   ├── grounded_rag/  (components/pages/styles/state/services)
    │   ├── search_engine/
    │   ├── quiz_engine/
    │   ├── content_library/
    │   ├── weaknesses/
    │   ├── gamification/
    │   ├── courses/
    │   └── analytics/
    │
    ├── components/    (existing shared components — UNCHANGED)
    ├── pages/         (existing page modules — UNCHANGED)
    ├── services/      (existing API services — UNCHANGED)
    ├── index.html
    ├── app.js
    └── styles.css
```

---

## ✅ Architecture Validation Checklist

| Principle | Status |
|---|---|
| Every capability is a top-level feature | ✅ 14 features |
| Every feature owns its sub-modules | ✅ Via re-export `__init__.py` |
| No mixed responsibilities | ✅ Clean boundaries |
| Shared engines reused (not duplicated) | ✅ `features.shared` layer |
| Frontend mirrors backend structure | ✅ 8 frontend features |
| Architecture visually understandable | ✅ This document |
| Scalable for future enterprise growth | ✅ Registry + stub sub-features |
| Existing APIs continue working | ✅ Zero changes to `main.py` |
| Existing code untouched | ✅ 100% additive overlay |

---

## 🏆 Evolution

```
Before: Advanced RAG Project
        └── modules/ (technically modular)

After:  Enterprise AI Learning Platform
        └── features/ (business capability tree)
            └── modules/ (implementation)
                └── core engines (shared infrastructure)
```

> **FAANG Principle**: Systems should be organized by **business capability**, not just by technical utility.
