"""LLM Router — dispatches to the configured provider with health checks and fallbacks.

Usage (in any feature module):
    from app.modules.llm_router.router import llm_router
    result = await llm_router.generate(doc_id, task_type, prompt, context)
"""
from __future__ import annotations

import logging
import os
import re
import time
import random
import json
import httpx
import numpy as np
from pathlib import Path
from typing import Any

from app.modules.llm_router.base import LLMProvider

logger = logging.getLogger(__name__)

# Paths for storing provider metrics
PROVIDER_METRICS_DIR = Path("storage/provider_metrics")
PROVIDER_METRICS_DIR.mkdir(parents=True, exist_ok=True)


class ProviderHealthScore:
    """Tracks latency, failure rates, and cooldowns for a provider to calculate health score."""
    def __init__(self, name: str):
        self.name = name
        self.failures = 0
        self.successes = 0
        self.total_latency = 0.0
        self.latency_count = 0
        self.last_failure_time = 0.0
        self.cooldown_seconds = 60.0
        self.load_metrics()

    def get_score(self) -> float:
        """Calculate health score between 0.0 (worst/dead) and 1.0 (perfect)."""
        now = time.time()
        # If in cooldown window after failure
        if self.last_failure_time > 0 and (now - self.last_failure_time) < self.cooldown_seconds:
            # Gradually recover score from 0.1 to 1.0 as time approaches cooldown end
            elapsed = now - self.last_failure_time
            recovery_ratio = elapsed / self.cooldown_seconds
            return max(0.1, recovery_ratio)
            
        total = self.failures + self.successes
        if total == 0:
            return 1.0  # default healthy
            
        failure_rate = self.failures / total
        score = 1.0 - (failure_rate * 0.8)
        
        # Factor in latency (if average latency is > 5s, reduce score)
        if self.latency_count > 0:
            avg_latency = self.total_latency / self.latency_count
            if avg_latency > 5.0:
                score -= min(0.2, (avg_latency - 5.0) * 0.04)
                
        return max(0.1, score)

    def record_success(self, latency: float):
        self.successes += 1
        self.total_latency += latency
        self.latency_count += 1
        # Gradually decay failures
        if self.failures > 0 and random.random() < 0.2:
            self.failures -= 1
        self.save_metrics()

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        self.save_metrics()

    def save_metrics(self):
        try:
            filepath = PROVIDER_METRICS_DIR / f"{self.name}.json"
            data = {
                "failures": self.failures,
                "successes": self.successes,
                "total_latency": self.total_latency,
                "latency_count": self.latency_count,
                "last_failure_time": self.last_failure_time
            }
            filepath.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass

    def load_metrics(self):
        try:
            filepath = PROVIDER_METRICS_DIR / f"{self.name}.json"
            if filepath.exists():
                data = json.loads(filepath.read_text(encoding="utf-8"))
                self.failures = data.get("failures", 0)
                self.successes = data.get("successes", 0)
                self.total_latency = data.get("total_latency", 0.0)
                self.latency_count = data.get("latency_count", 0)
                self.last_failure_time = data.get("last_failure_time", 0.0)
        except Exception:
            pass


def _load_provider(provider_name: str) -> LLMProvider:
    """Instantiate the provider class for the given name."""
    name = (provider_name or "sarvam").strip().lower()

    if name == "sarvam":
        from app.modules.llm_router.providers.sarvam import SarvamProvider
        return SarvamProvider()
    elif name == "openai":
        from app.modules.llm_router.providers.openai import OpenAIProvider
        return OpenAIProvider()
    elif name == "gemini":
        from app.modules.llm_router.providers.gemini import GeminiProvider
        return GeminiProvider()
    elif name == "deepseek":
        from app.modules.llm_router.providers.deepseek import DeepSeekProvider
        return DeepSeekProvider()
    elif name == "anthropic":
        from app.modules.llm_router.providers.anthropic import AnthropicProvider
        return AnthropicProvider()
    elif name == "groq":
        from app.modules.llm_router.providers.groq import GroqProvider
        return GroqProvider()
    elif name == "ollama":
        from app.modules.llm_router.providers.ollama import OllamaProvider
        return OllamaProvider()
    elif name == "openrouter":
        from app.modules.llm_router.providers.openrouter import OpenRouterProvider
        return OpenRouterProvider()
    else:
        logger.warning(
            "Unknown LLM_PROVIDER '%s'. Falling back to Sarvam.", name
        )
        from app.modules.llm_router.providers.sarvam import SarvamProvider
        return SarvamProvider()


class LLMRouter:
    """Universal LLM dispatch layer with dynamic health checks and tier-based routing."""

    def __init__(self):
        provider_name = os.getenv("LLM_PROVIDER", "sarvam")
        self._provider_name = provider_name.strip().lower()
        if self._provider_name not in ("balanced", "free", "premium"):
            self._provider: LLMProvider | None = _load_provider(self._provider_name)
        else:
            self._provider = None
        self.health_trackers: dict[str, ProviderHealthScore] = {}
        logger.info(
            "LLMRouter initialized with provider env: %s", self._provider_name
        )

    @property
    def provider(self) -> LLMProvider:
        if self._provider is None:
            return _load_provider("gemini")
        return self._provider

    def switch_provider(self, provider_name: str) -> None:
        """Hot-switch the provider at runtime."""
        name = provider_name.strip().lower()
        self._provider_name = name
        if name not in ("balanced", "free", "premium"):
            self._provider = _load_provider(name)
        else:
            self._provider = None
        logger.info("LLMRouter switched to provider: %s", self._provider_name)

    def _get_user_tier(self, doc_id: str | None) -> str:
        """Resolve user tier dynamically using doc_id or userlib prefix."""
        if not doc_id:
            return "free"
        
        from app.shared.database import SessionLocal, User, Document
        db = SessionLocal()
        try:
            # 1. If doc_id is userlib:user_xxx
            if str(doc_id).startswith("userlib:"):
                uid = str(doc_id).split(":", 1)[1]
                user = db.query(User).filter(User.id == uid).first()
                if user and user.tier:
                    return user.tier.strip().lower()
            
            # 2. Check if doc_id is a document
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if doc:
                user = db.query(User).filter(User.id == doc.user_id).first()
                if user and user.tier:
                    return user.tier.strip().lower()

            # 3. Check if doc_id is user_id itself (backward compatibility/tests)
            user = db.query(User).filter(User.id == doc_id).first()
            if user and user.tier:
                return user.tier.strip().lower()
        except Exception as e:
            logger.warning("[LLMROUTER] Error resolving user tier: %s", e)
        finally:
            db.close()
        return "free"

    def _resolve_user_id(self, doc_id: str | None) -> str:
        """Resolve user_id dynamically using doc_id or userlib prefix."""
        if not doc_id:
            return "default_user"
        
        doc_id_str = str(doc_id)
        if doc_id_str.startswith("userlib:"):
            return doc_id_str.split(":", 1)[1]
            
        from app.shared.database import SessionLocal, User, Document
        db = SessionLocal()
        try:
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if doc:
                return doc.user_id
            user = db.query(User).filter(User.id == doc_id).first()
            if user:
                return user.id
        except Exception as e:
            logger.warning("[LLMROUTER] Error resolving user ID: %s", e)
        finally:
            db.close()
        return doc_id_str

    def route_task(self, task_type: str, user_tier: str) -> str:
        """Map task_type and user_tier to the appropriate LLM provider name."""
        t = (task_type or "ask").strip().lower()
        user_tier = (user_tier or "free").strip().lower()
        
        # Reranker tasks always map to local_bge
        if t.startswith("rerank"):
            return "local_bge"
            
        if t in ("ask", "ask_user_library", "summary", "mentor"):
            # RAG & Summaries
            if user_tier == "premium":
                return "openai"  # Premium primary is GPT-5 Nano (OpenAI)
            else:
                return "gemini"  # Free primary is Gemini Flash-Lite (Gemini)
        elif t in ("quiz", "mock_test", "rapid_fire", "true_false", "fill_blanks", "flashcards", "weakness_advisor", "classify", "slides", "fun_facts"):
            # Quizzes & Flashcards & other cognitive content tasks
            if user_tier == "premium":
                return "gemini"  # Premium primary is Gemini 3.1 Flash-Lite (Gemini)
            else:
                return "openai"  # Free primary is GPT-5 Nano (OpenAI)
        else:
            return "gemini"  # Default fallback

    async def generate(
        self,
        doc_id: str,
        task_type: str,
        prompt: str,
        context: str,
        stream: bool = False,
        use_cache: bool = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
        llm_variant: str | None = None,
    ) -> dict[str, Any]:
        """Generate a response — dispatches to the active provider with a health-aware fallback chain."""
        # Determine the user's tier
        user_tier = self._get_user_tier(doc_id)
        
        if self._provider_name in ("balanced", "free", "premium"):
            active_tier = self._provider_name if self._provider_name in ("free", "premium") else user_tier
            primary_name = self.route_task(task_type, active_tier)
        else:
            primary_name = self._provider_name

        # Apply health checks to primary
        health_tracker = self.health_trackers.setdefault(primary_name, ProviderHealthScore(primary_name))
        health_score = health_tracker.get_score()
        
        # Dynamic degraded rebalancing: if health is low, route partial traffic to fallback
        if health_score < 1.0:
            fallback_candidate = ""
            if primary_name == "gemini":
                fallback_candidate = "openai"
            elif primary_name == "openai":
                fallback_candidate = "gemini"
            elif primary_name == "local_bge":
                fallback_candidate = "jina"
            elif primary_name == "jina":
                fallback_candidate = "local_bge"
                
            if fallback_candidate and random.random() > health_score:
                logger.info(
                    "[HEALTH ROUTER] Routing traffic to fallback '%s' because primary '%s' is degraded (health=%.2f)",
                    fallback_candidate, primary_name, health_score
                )
                primary_name = fallback_candidate

        # Build sequence of providers to try
        providers_to_try = [primary_name]
        
        t = (task_type or "ask").strip().lower()
        if t.startswith("rerank"):
            for fb in ["local_bge", "jina"]:
                if fb not in providers_to_try:
                    providers_to_try.append(fb)
        else:
            # General task fallback chain: try primary, then opposite, then others
            opposite = "openai" if primary_name == "gemini" else "gemini"
            if opposite not in providers_to_try:
                providers_to_try.append(opposite)
            for fallback in ["openai", "gemini", "sarvam", "deepseek"]:
                if fallback not in providers_to_try:
                    providers_to_try.append(fallback)

        last_error = None
        for provider_name in providers_to_try:
            t0 = time.time()
            try:
                # ── Handle Local BGE Scorer ──
                if provider_name == "local_bge":
                    query_part = ""
                    chunk_part = ""
                    if "Query:" in prompt and "Chunk:" in prompt:
                        parts = prompt.split("Query:")
                        if len(parts) > 1:
                            query_and_chunk = parts[1].split("Chunk:")
                            if len(query_and_chunk) > 1:
                                query_part = query_and_chunk[0].strip()
                                chunk_part = query_and_chunk[1].strip()
                    if not query_part or not chunk_part:
                        raise ValueError("Could not parse query/chunk from prompt")
                        
                    from app.rag.embedder import embed_single
                    q_emb = embed_single(query_part)
                    c_emb = embed_single(chunk_part)
                    similarity = float(np.dot(q_emb, c_emb))
                    # Map cosine similarity to 0-10 score
                    score = max(0.0, min(10.0, similarity * 10.0))
                    
                    self.health_trackers.setdefault("local_bge", ProviderHealthScore("local_bge")).record_success(time.time() - t0)
                    return {
                        "answer": f"{score:.2f}",
                        "source_chunks": [],
                        "cached": False,
                        "llm_model": "local_bge-ONNX-CPU",
                    }
                    
                # ── Handle Remote Jina Rerank API ──
                elif provider_name == "jina":
                    jina_key = os.getenv("JINA_API_KEY", "")
                    if not jina_key or jina_key == "dummy":
                        logger.warning("[LLMROUTER] Jina API key not set or dummy; falling back")
                        last_error = "Jina API key not set"
                        continue
                        
                    query_part = ""
                    chunk_part = ""
                    if "Query:" in prompt and "Chunk:" in prompt:
                        parts = prompt.split("Query:")
                        if len(parts) > 1:
                            query_and_chunk = parts[1].split("Chunk:")
                            if len(query_and_chunk) > 1:
                                query_part = query_and_chunk[0].strip()
                                chunk_part = query_and_chunk[1].strip()
                    if not query_part or not chunk_part:
                        raise ValueError("Could not parse query/chunk from prompt")
                        
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(
                            "https://api.jina.ai/v1/rerank",
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {jina_key}"
                            },
                            json={
                                "model": "jina-reranker-v2-base-multilingual",
                                "query": query_part,
                                "documents": [chunk_part]
                            }
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        relevance_score = data["results"][0]["relevance_score"]
                        score = max(0.0, min(10.0, float(relevance_score) * 10.0))
                        
                        self.health_trackers.setdefault("jina", ProviderHealthScore("jina")).record_success(time.time() - t0)
                        return {
                            "answer": f"{score:.2f}",
                            "source_chunks": [],
                            "cached": False,
                            "llm_model": "jina-reranker-v2-base",
                        }

                # ── Handle standard LLM providers ──
                provider = _load_provider(provider_name)
                
                # Determine dynamic tier-based variant
                target_variant = llm_variant
                if not target_variant:
                    if t in ("ask", "ask_user_library", "summary", "mentor"):
                        if provider_name == "gemini":
                            target_variant = "gemini-flash-lite" if user_tier == "free" else "gemini-3.1-flash-lite"
                        elif provider_name == "openai":
                            target_variant = "gpt-5-nano"
                    elif t in ("quiz", "mock_test", "rapid_fire", "true_false", "fill_blanks", "flashcards", "weakness_advisor", "classify", "slides", "fun_facts"):
                        if provider_name == "openai":
                            target_variant = "gpt-5-nano"
                        elif provider_name == "gemini":
                            target_variant = "gemini-3.1-flash-lite" if user_tier == "premium" else "gemini-flash-lite"
                
                logger.debug("[LLMROUTER] Attempting generation via '%s' (variant: %s)...", provider_name, target_variant)
                res = await provider.generate(
                    doc_id=doc_id,
                    task_type=task_type,
                    prompt=prompt,
                    context=context,
                    stream=stream,
                    use_cache=use_cache,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    llm_variant=target_variant,
                )
                ans = res.get("answer", "")
                if (
                    ans.startswith("Error:")
                    or ans.startswith("OpenAI call failed")
                    or ans.startswith("Gemini call failed")
                    or ans.startswith("DeepSeek call failed")
                ):
                    logger.warning("[LLMROUTER] Provider '%s' returned error: %s", provider_name, ans[:100])
                    self.health_trackers.setdefault(provider_name, ProviderHealthScore(provider_name)).record_failure()
                    last_error = ans
                    continue

                # Success, record metric
                self.health_trackers.setdefault(provider_name, ProviderHealthScore(provider_name)).record_success(time.time() - t0)
                
                # Track usage
                try:
                    from app.shared.utils.usage_tracker import track_user_usage
                    resolved_uid = self._resolve_user_id(doc_id)
                    model_used = res.get("llm_model") or target_variant or "default"
                    track_user_usage(
                        user_id=resolved_uid,
                        provider=provider_name,
                        model=model_used,
                        prompt=prompt,
                        response=res.get("answer") or "",
                        task_type=task_type,
                        prompt_tokens=res.get("prompt_tokens"),
                        completion_tokens=res.get("completion_tokens")
                    )
                except Exception as ex:
                    logger.warning("[LLMROUTER] Failed to track usage: %s", ex)

                return res
            except Exception as e:
                logger.warning("[LLMROUTER] Provider '%s' raised exception: %s", provider_name, e)
                self.health_trackers.setdefault(provider_name, ProviderHealthScore(provider_name)).record_failure()
                last_error = str(e)
                continue

        return {
            "answer": f"All LLM providers in fallback chain failed. Last error: {last_error}",
            "source_chunks": [],
            "cached": False,
            "llm_model": primary_name,
        }


# Singleton
llm_router = LLMRouter()

