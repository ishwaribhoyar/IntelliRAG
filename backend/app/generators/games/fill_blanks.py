"""Fill in the Blanks game."""
from app.generators.content import generate_content


async def generate_fill_blanks(doc_id: str) -> dict:
    return await generate_content(doc_id, "fill_blanks")
