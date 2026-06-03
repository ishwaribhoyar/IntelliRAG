"""Courses module — routes."""
import logging
from fastapi import APIRouter, HTTPException

from app.shared.schemas.course import CourseActionRequest, CourseChatRequest
from app.modules.courses.service import handle_course_structure, handle_course_action, handle_course_chat

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Courses"])


@router.get("/course/{doc_id}/structure")
async def get_course_structure(doc_id: str):
    """Return hierarchical structure for course-style reading UI."""
    return await handle_course_structure(doc_id)


@router.post("/course/action")
async def course_action(req: CourseActionRequest):
    """Run section-scoped AI actions: summarize/explain."""
    return await handle_course_action(req)


@router.post("/course/chat")
async def course_chat(req: CourseChatRequest):
    """Context-aware mentor chat: section-first, then full document context."""
    return await handle_course_chat(req)
