"""Shared schemas — Course."""
from pydantic import BaseModel
from typing import Optional


class CourseActionRequest(BaseModel):
    doc_id: str
    node_id: str
    action: str  # summarize | explain
    llm_variant: Optional[str] = "30b"


class CourseChatRequest(BaseModel):
    doc_id: str
    question: str
    node_id: str = ""
    user_id: str = "default_user"
    llm_variant: Optional[str] = "30b"
