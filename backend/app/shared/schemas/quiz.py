"""Shared schemas — Quiz."""
from pydantic import BaseModel
from typing import Optional


class QuizStartRequest(BaseModel):
    doc_id: str
    user_id: str = "default_user"
    quiz_type: str = "quiz"
    llm_variant: Optional[str] = "30b"
    refresh: bool = False
    previous_output: Optional[str] = None
    source_chunk_ids: Optional[list] = None


class QuizSubmitRequest(BaseModel):
    doc_id: str
    user_id: str = "default_user"
    questions: list
    answers: list[str]
    quiz_type: str = "quiz"
