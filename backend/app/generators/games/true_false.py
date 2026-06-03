"""True/False Streak game."""
from app.generators.content import generate_content


async def generate_true_false(doc_id: str) -> dict:
    return await generate_content(doc_id, "true_false")
