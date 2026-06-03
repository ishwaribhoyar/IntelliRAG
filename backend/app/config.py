"""Central configuration for the IntelliRAG — Advanced RAG System.

Environment variables are read once at startup.
All feature modules import from here — never from .env directly.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
FAISS_INDEX_DIR = STORAGE_DIR / "faiss_index"
CHUNKS_DIR = STORAGE_DIR / "chunks"
UPLOAD_DIR = STORAGE_DIR / "uploads"
LIBRARY_DIR = STORAGE_DIR / "library"
EVAL_DIR = STORAGE_DIR / "evaluation"

for d in [STORAGE_DIR, FAISS_INDEX_DIR, CHUNKS_DIR, UPLOAD_DIR, LIBRARY_DIR, EVAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- Database ---
DATABASE_URL = f"sqlite:///{BASE_DIR / 'learning_engine.db'}"

# --- Universal LLM Router ---
# Set to: sarvam | openai | gemini | anthropic | groq | ollama | openrouter
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "sarvam")

# --- Sarvam (default provider) ---
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_API_URL = os.getenv("SARVAM_API_URL", "https://api.sarvam.ai/v1/chat/completions")
# Sarvam chat models — UI / requests use `llm_variant`: "105b" | "30b"
SARVAM_MODEL_105B = os.getenv("SARVAM_MODEL_105B", "sarvam-105b")
SARVAM_MODEL_30B = os.getenv("SARVAM_MODEL_30B", "sarvam-30b")
# Backward compat: single env still overrides the 105B slot default id
SARVAM_MODEL = os.getenv("SARVAM_MODEL", SARVAM_MODEL_105B)
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
# Slightly higher on explicit refresh/regenerate (variation without chaos)
LLM_REFRESH_TEMPERATURE = float(os.getenv("LLM_REFRESH_TEMPERATURE", "0.4"))

# --- Pipeline Feature Flags ---
# Set any of these to "false" in .env to disable the feature.
ENABLE_RERANKER = os.getenv("ENABLE_RERANKER", "true").lower() == "true"
ENABLE_MMR = os.getenv("ENABLE_MMR", "true").lower() == "true"
ENABLE_QUERY_EXPANSION = os.getenv("ENABLE_QUERY_EXPANSION", "true").lower() == "true"




def normalize_llm_variant(raw: str | None) -> str:
    """Normalize client `llm_variant` to ``105b`` or ``30b``."""
    v = (raw or "30b").strip().lower().replace(" ", "")
    if v in ("30b", "30", "sarvam-30b", "sarvam30b", "small", "fast"):
        return "30b"
    return "105b"


def sarvam_model_id_for_variant(variant: str | None) -> str:
    """Map toggle value to provider ``model`` string."""
    if normalize_llm_variant(variant) == "30b":
        return SARVAM_MODEL_30B
    return SARVAM_MODEL


# max_tokens (Sarvam 105B may use reasoning_content before content — budget both)
LLM_MAX_TOKENS_DEFAULT = int(os.getenv("LLM_MAX_TOKENS_DEFAULT", "8192"))
LLM_MAX_TOKENS_BY_TASK = {
    "quiz": int(os.getenv("LLM_MAX_TOKENS_QUIZ", "8192")),
    "mock_test": int(os.getenv("LLM_MAX_TOKENS_MOCK", "16384")),
    "flashcards": int(os.getenv("LLM_MAX_TOKENS_FLASH", "8192")),
    "summary": int(os.getenv("LLM_MAX_TOKENS_SUMMARY", "8192")),
    "slides": 8192,
    "ask": int(os.getenv("LLM_MAX_TOKENS_ASK", "8192")),
    "mentor": int(os.getenv("LLM_MAX_TOKENS_MENTOR", "8192")),
    "fun_facts": 4096,
    "rapid_fire": 4096,
    "true_false": 4096,
    "fill_blanks": 8192,
    "ask_user_library": int(os.getenv("LLM_MAX_TOKENS_ASK_USER_LIB", "4096")),
}
# Strict AI pipeline: hybrid → top-K chunks → dedupe/MMR → LLM
AI_RETRIEVAL_MAX_CHUNKS = int(os.getenv("AI_RETRIEVAL_MAX_CHUNKS", "5"))

# --- Embedding ---
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# --- RAG / Chunking ---
MAX_CONTEXT_TOKENS = 1500
FEATURE_TOKEN_BUDGETS = {
    "ask": {"context": 800, "output": 150},
    "quiz": {"context": 2500, "output": 800},
    "flashcard": {"context": 1500, "output": 400},
    "summary": {"context": 2000, "output": 300},
}
CHUNK_SIZE_WORDS = 350
CHUNK_OVERLAP_WORDS = 50
CHUNK_MIN_WORDS = 100      # Merge chunks below this
CHUNK_MAX_WORDS = 500      # Split chunks above this

# --- Hybrid Retrieval (RRF) ---
RRF_K_DEFAULT = 10          # RRF constant
DEFAULT_VECTOR_WEIGHT = 0.5
DEFAULT_BM25_WEIGHT = 0.5

# --- Reranker ---
RERANK_MIN_CANDIDATES = 5   # Min chunks before triggering reranker
RERANK_SCORE_GAP = 0.02     # Score gap threshold for triggering reranker

# --- MMR ---
MMR_LAMBDA = 0.7             # Relevance vs diversity tradeoff
MMR_SIMILARITY_THRESHOLD = 0.85  # Near-duplicate threshold

# --- Performance ---
MAX_DOCS_IN_MEMORY = 50
MAX_UPLOAD_SIZE_MB = 20
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
LLM_MAX_RETRIES = 2
LLM_RETRY_DELAY = 2.0
RATE_LIMIT_GAP_SECONDS = 0.5

# --- Ingestion queue / batching ---
MAX_INGEST_QUEUE_SIZE = 30
# Worker counts (lower on small PaaS instances to avoid OOM / startup failures)
PIPELINE_MIN_WORKERS = int(os.getenv("PIPELINE_MIN_WORKERS", "1"))
PIPELINE_DEFAULT_WORKERS = int(os.getenv("PIPELINE_DEFAULT_WORKERS", "3"))
PIPELINE_MAX_WORKERS = int(os.getenv("PIPELINE_MAX_WORKERS", "12"))
# Embedding micro-batching window (30–50ms target)
EMBED_BATCH_WINDOW_S = 0.05

# --- Gamification ---
XP_UPLOAD = 20
XP_ASK = 5
XP_QUIZ_COMPLETE = 50
XP_CORRECT_ANSWER = 10
XP_DAILY_STREAK = 30

# --- Prompt ---
PROMPT_VERSION = "v4"

# --- Allowed file types ---
ALLOWED_EXTENSIONS = {".pdf", ".xlsx"}

# --- Trust / Confidence ---
CONFIDENCE_FALLBACK_THRESHOLD = 0.25  # Below this, return fallback response
