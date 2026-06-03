"""Upload Pipeline module — routes."""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query

from app.modules.upload_pipeline.service import (
    handle_single_upload, handle_multi_upload, get_doc_status,
    get_user_status, retry_failed_doc,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Upload Pipeline"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form("default_user"),
):
    """Upload and process a document."""
    return await handle_single_upload(file, user_id)


@router.post("/upload/multi")
async def upload_documents_multi(
    files: list[UploadFile] = File(default_factory=list),
    files_array: list[UploadFile] = File(default_factory=list, alias="files[]"),
    user_id: str = Form("default_user"),
):
    """Queue many PDFs/Excels with per-file status and real pipeline stages."""
    incoming_files = files if files else files_array
    if not incoming_files:
        raise HTTPException(400, "No files uploaded")
    return await handle_multi_upload(incoming_files, user_id)


@router.get("/status/{doc_id}")
async def get_document_status(doc_id: str):
    """Get document processing status."""
    return await get_doc_status(doc_id)


@router.get("/status/user/{user_id}")
async def get_user_processing_status(user_id: str):
    """Per-user processing overview with real stage/progress."""
    return await get_user_status(user_id)


@router.post("/retry/{doc_id}")
async def retry_document(doc_id: str):
    """Retry a failed ingestion job by re-queuing it."""
    return await retry_failed_doc(doc_id)


@router.get("/documents/{user_id}")
async def list_user_documents(user_id: str):
    """List all documents uploaded by a user."""
    from app.modules.upload_pipeline.service import list_docs_for_user
    return await list_docs_for_user(user_id)


@router.get("/pdf/{doc_id}")
async def serve_pdf(doc_id: str):
    """Serve uploaded PDF for in-app viewing."""
    from app.modules.upload_pipeline.service import serve_pdf_file
    return await serve_pdf_file(doc_id)


@router.delete("/doc/{doc_id}")
async def delete_document(doc_id: str):
    """Delete document and all associated data (indexes, chunks, DB rows)."""
    from app.modules.upload_pipeline.service import delete_document_all
    return await delete_document_all(doc_id)
