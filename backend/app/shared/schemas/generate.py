"""Shared schemas — Generate (flashcards, summary, slides, etc.)."""
from pydantic import BaseModel
from typing import Optional


class GenerateRequest(BaseModel):
    doc_id: str
    content_type: str
    user_id: str = "default_user"
    query: str = ""
    llm_variant: Optional[str] = "30b"
    refresh: bool = False
    previous_output: Optional[str] = None
    source_chunk_ids: Optional[list] = None
