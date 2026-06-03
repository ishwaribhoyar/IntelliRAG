"""Groq provider — stub. Set LLM_PROVIDER=groq + GROQ_API_KEY."""
from app.modules.llm_router.base import LLMProvider
from typing import Any

class GroqProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "groq"

    async def generate(self, doc_id, task_type, prompt, context, stream=False,
                       use_cache=True, temperature=None, max_tokens=None, llm_variant=None) -> dict[str, Any]:
        """TODO: Implement Groq API (OpenAI-compatible). Models: llama3-70b-8192, mixtral-8x7b."""
        raise NotImplementedError("Groq provider not yet implemented.")
