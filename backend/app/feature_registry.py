"""
feature_registry.py
====================
Central Feature Registry — IntelliRAG Enterprise AI Learning Platform

Purpose
-------
- Register all top-level product capabilities as named features
- Declare inter-feature dependencies for dependency graph analysis
- Expose enable/disable flags for future plug-in architecture
- Serve as the single source of truth for platform architecture metadata

Usage
-----
    from app.feature_registry import FEATURE_REGISTRY, get_feature, list_enabled_features

    # Inspect a feature
    feature = get_feature("search_engine")
    print(feature["description"])
    print(feature["depends_on"])

    # List all active features
    for name, meta in list_enabled_features():
        print(name, "->", meta["category"])
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Feature Registry
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_REGISTRY: Dict[str, Dict[str, Any]] = {

    # ── 1. Grounded RAG ──────────────────────────────────────────────────────
    "grounded_rag": {
        "display_name": "Grounded RAG",
        "description": "Document-grounded question answering with hybrid retrieval, "
                       "citation tracking, confidence scoring, and hallucination control.",
        "category": "core_ai",
        "enabled": True,
        "depends_on": ["shared.retrieval_core", "shared.embedding_core", "trust_layer", "llm_platform"],
        "owned_by": "app.modules.ask_ai",
        "feature_path": "app.features.grounded_rag",
        "sub_features": [
            "ask_ai", "grounding", "retrieval", "citations", "confidence",
            "answer_generation", "query_understanding", "context_window", "hallucination_control",
        ],
        "api_prefix": "/api/ask",
        "version": "1.0",
    },

    # ── 2. Search Engine ──────────────────────────────────────────────────────
    "search_engine": {
        "display_name": "Search Engine",
        "description": "Multi-modal document search combining keyword (BM25), "
                       "vector (FAISS), and hybrid (RRF) search with typo correction and LLM reranking.",
        "category": "core_ai",
        "enabled": True,
        "depends_on": ["shared.retrieval_core", "shared.vector_core", "smart_reranker"],
        "owned_by": "app.modules.search_engine",
        "feature_path": "app.features.search_engine",
        "sub_features": [
            "keyword_search", "hybrid_search", "vector_search", "autocomplete",
            "typo_correction", "suggestions", "query_routing", "search_ranking", "indexing", "navigation",
        ],
        "api_prefix": "/api/search",
        "version": "1.0",
    },

    # ── 3. Smart Reranker ─────────────────────────────────────────────────────
    "smart_reranker": {
        "display_name": "Smart Reranker",
        "description": "Intelligent result reranking using LLM-based scoring, "
                       "score-gap conditional logic, and MMR diversity enforcement.",
        "category": "core_ai",
        "enabled": True,
        "depends_on": ["llm_platform"],
        "owned_by": "app.reranker",
        "feature_path": "app.features.smart_reranker",
        "sub_features": [
            "conditional_rerank", "score_gap_logic", "llm_reranking",
            "diversity", "mmr", "rerank_metrics", "latency_control",
        ],
        "api_prefix": None,  # internal — consumed by search_engine and grounded_rag
        "version": "1.0",
    },

    # ── 4. Quiz Engine ────────────────────────────────────────────────────────
    "quiz_engine": {
        "display_name": "Quiz Engine",
        "description": "Generate, grade, and track quizzes, MCQs, flashcards, "
                       "fill-in-the-blank, and rapid-fire games from document content.",
        "category": "learning",
        "enabled": True,
        "depends_on": ["shared.retrieval_core", "llm_platform", "gamification"],
        "owned_by": "app.modules.quizzes",
        "feature_path": "app.features.quiz_engine",
        "sub_features": [
            "quiz_generation", "question_generation", "mcq_generation", "grading",
            "scoring", "retry", "flashcards", "mock_tests", "summaries", "refresh", "analytics",
        ],
        "api_prefix": "/api/quiz",
        "version": "1.0",
    },

    # ── 5. Weakness Detection ─────────────────────────────────────────────────
    "weakness_detection": {
        "display_name": "Weakness Detection",
        "description": "Track learner performance, detect knowledge gaps, and provide "
                       "AI-powered personalized study guidance based on topic-level analysis.",
        "category": "learning",
        "enabled": True,
        "depends_on": ["shared.database", "llm_platform"],
        "owned_by": "app.modules.weaknesses",
        "feature_path": "app.features.weakness_detection",
        "sub_features": [
            "topic_tracking", "weak_topic_detection", "recommendation_engine",
            "learning_patterns", "progress_analysis", "study_guidance", "confidence_analysis",
        ],
        "api_prefix": "/api/weakness",
        "version": "1.0",
    },

    # ── 6. Content Library ────────────────────────────────────────────────────
    "content_library": {
        "display_name": "Content Library",
        "description": "Upload, classify, organize, and manage learning documents "
                       "with automatic subject/topic detection and hierarchical content structuring.",
        "category": "content",
        "enabled": True,
        "depends_on": ["ingestion_pipeline", "shared.database"],
        "owned_by": "app.modules.content_library",
        "feature_path": "app.features.content_library",
        "sub_features": [
            "uploads", "pdf_management", "auto_classification", "hierarchy_builder",
            "subject_detection", "topic_detection", "subtopic_mapping", "storage", "metadata", "deletion",
        ],
        "api_prefix": "/api/library",
        "version": "1.0",
    },

    # ── 7. Gamification ───────────────────────────────────────────────────────
    "gamification": {
        "display_name": "Gamification",
        "description": "Drive learner engagement through XP awards, level progression, "
                       "leaderboards, badges, and activity streak tracking.",
        "category": "engagement",
        "enabled": True,
        "depends_on": ["shared.database"],
        "owned_by": "app.gamification",
        "feature_path": "app.features.gamification",
        "sub_features": ["xp", "levels", "badges", "streaks", "leaderboard", "rewards", "activity_tracking"],
        "api_prefix": "/api/gamification",
        "version": "1.0",
    },

    # ── 8. Trust Layer ────────────────────────────────────────────────────────
    "trust_layer": {
        "display_name": "Trust Layer",
        "description": "Ensure answer reliability through confidence scoring, "
                       "hallucination detection, fallback logic, and grounding validation.",
        "category": "core_ai",
        "enabled": True,
        "depends_on": [],
        "owned_by": "app.llm.trust",
        "feature_path": "app.features.trust_layer",
        "sub_features": [
            "confidence", "hallucination_detection", "fallback_logic",
            "citation_validation", "answer_validation", "uncertainty_detection", "grounding_validation",
        ],
        "api_prefix": None,  # internal — consumed by grounded_rag
        "version": "1.0",
    },

    # ── 9. Evaluation Engine ──────────────────────────────────────────────────
    "evaluation_engine": {
        "display_name": "Evaluation Engine",
        "description": "Measure RAG system performance using Recall@K, MRR, hallucination rate, "
                       "latency benchmarks, ablation studies, and failure analysis reports.",
        "category": "platform",
        "enabled": True,
        "depends_on": ["grounded_rag", "search_engine"],
        "owned_by": "app.evaluation",
        "feature_path": "app.features.evaluation_engine",
        "sub_features": [
            "recall", "mrr", "hallucination", "latency", "ablation",
            "benchmarks", "failure_analysis", "reports", "logging", "metrics_storage",
        ],
        "api_prefix": "/api/evaluate",
        "version": "1.0",
    },

    # ── 10. LLM Platform ──────────────────────────────────────────────────────
    "llm_platform": {
        "display_name": "LLM Platform",
        "description": "Abstract and route LLM calls across multiple providers "
                       "(Gemini, OpenAI, Anthropic, Groq, Ollama, OpenRouter, Sarvam) "
                       "with fallback chain and prompt management.",
        "category": "platform",
        "enabled": True,
        "depends_on": [],
        "owned_by": "app.modules.llm_router",
        "feature_path": "app.features.llm_platform",
        "sub_features": [
            "providers", "model_router", "fallback", "streaming",
            "token_tracking", "cost_tracking", "prompt_management", "provider_metrics",
        ],
        "api_prefix": None,  # internal — consumed by all AI features
        "version": "1.0",
        "providers": ["gemini", "openai", "anthropic", "groq", "ollama", "openrouter", "sarvam"],
    },

    # ── 11. Ingestion Pipeline ────────────────────────────────────────────────
    "ingestion_pipeline": {
        "display_name": "Ingestion Pipeline",
        "description": "End-to-end document ingestion — PDF parsing, hierarchical chunking, "
                       "embedding, vector/BM25 indexing — with async background queue workers.",
        "category": "content",
        "enabled": True,
        "depends_on": ["shared.embedding_core", "shared.vector_core", "shared.database"],
        "owned_by": "app.modules.upload_pipeline",
        "feature_path": "app.features.ingestion_pipeline",
        "sub_features": [
            "pdf_parsing", "chunking", "indexing", "queue", "background", "validation", "storage",
        ],
        "api_prefix": "/api/upload",
        "version": "1.0",
    },

    # ── 12. Course System ─────────────────────────────────────────────────────
    "course_system": {
        "display_name": "Course System",
        "description": "Build, navigate, and track structured learning courses from document "
                       "content with automatic subject/topic/subtopic hierarchy generation.",
        "category": "learning",
        "enabled": True,
        "depends_on": ["content_library", "grounded_rag", "weakness_detection"],
        "owned_by": "app.modules.courses",
        "feature_path": "app.features.course_system",
        "sub_features": ["structure", "hierarchy", "routes", "progress"],
        "api_prefix": "/api/course",
        "version": "1.0",
    },

    # ── 13. Analytics ─────────────────────────────────────────────────────────
    "analytics": {
        "display_name": "Analytics",
        "description": "Track and expose platform-wide learning analytics including "
                       "session metrics, document usage, quiz performance, and engagement.",
        "category": "platform",
        "enabled": True,
        "depends_on": ["shared.database"],
        "owned_by": "app.modules.analytics",
        "feature_path": "app.features.analytics",
        "sub_features": ["routes", "metrics", "reports"],
        "api_prefix": "/api/analytics",
        "version": "1.0",
    },

    # ── 14. Shared (Cross-cutting Infrastructure) ─────────────────────────────
    "shared": {
        "display_name": "Shared Core Engine Layer",
        "description": "Cross-cutting infrastructure engines consumed by all features: "
                       "retrieval, embedding, vector store, ranking, caching, auth, database, logging.",
        "category": "infrastructure",
        "enabled": True,
        "depends_on": [],
        "owned_by": "app.shared",
        "feature_path": "app.features.shared",
        "sub_features": [
            "retrieval_core", "embedding_core", "vector_core", "ranking_core",
            "caching", "auth", "database", "logging", "utils",
        ],
        "api_prefix": None,
        "version": "1.0",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def get_feature(name: str) -> Dict[str, Any]:
    """Return metadata for a single feature by name."""
    if name not in FEATURE_REGISTRY:
        raise KeyError(f"Feature '{name}' not found in registry. Available: {list(FEATURE_REGISTRY)}")
    return FEATURE_REGISTRY[name]


def list_enabled_features() -> List[Tuple[str, Dict[str, Any]]]:
    """Return list of (name, metadata) tuples for all enabled features."""
    return [(name, meta) for name, meta in FEATURE_REGISTRY.items() if meta.get("enabled")]


def get_features_by_category(category: str) -> Dict[str, Dict[str, Any]]:
    """Return all features belonging to a specific category."""
    return {name: meta for name, meta in FEATURE_REGISTRY.items() if meta.get("category") == category}


def get_dependency_graph() -> Dict[str, List[str]]:
    """Return the inter-feature dependency graph as {feature_name: [dep1, dep2, ...]}."""
    return {name: meta.get("depends_on", []) for name, meta in FEATURE_REGISTRY.items()}


def get_api_routes() -> Dict[str, str]:
    """Return {feature_name: api_prefix} for features that expose HTTP endpoints."""
    return {
        name: meta["api_prefix"]
        for name, meta in FEATURE_REGISTRY.items()
        if meta.get("api_prefix") and meta.get("enabled")
    }


def is_enabled(name: str) -> bool:
    """Check if a feature is currently enabled."""
    return FEATURE_REGISTRY.get(name, {}).get("enabled", False)


# ─────────────────────────────────────────────────────────────────────────────
# Metadata
# ─────────────────────────────────────────────────────────────────────────────

PLATFORM_METADATA = {
    "name": "IntelliRAG — Enterprise AI Learning Platform",
    "version": "2.0.0",
    "architecture": "feature-centric hierarchical",
    "total_features": len(FEATURE_REGISTRY),
    "categories": list({meta["category"] for meta in FEATURE_REGISTRY.values()}),
}
