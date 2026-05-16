"""
FastAPI router for DataFrame Agent endpoints.

Provides three endpoints:
  1. POST /df-agent/upload-file — Upload CSV/XLSX
  2. POST /df-agent/load-sheet — Load Google Sheet
  3. POST /df-agent/query — Query with natural language
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/df-agent", tags=["dataframe-agent"])
_agent_service = None


def get_agent_service():
    """Lazy-load the agent service singleton on first use."""
    global _agent_service
    if _agent_service is None:
        from agents.dataframe_agent import DataFrameAgentService
        _agent_service = DataFrameAgentService()
    return _agent_service


class LoadSheetRequest(BaseModel):
    """Request schema for loading a Google Sheet."""

    sheet_id: str = Field(..., description="Google Sheet ID from the share URL")
    session_id: str = Field(..., description="Unique session identifier")


class QueryRequest(BaseModel):
    """Request schema for querying a DataFrame."""

    question: str = Field(..., description="Natural-language question about the data")
    session_id: str = Field(..., description="Session ID of the cached DataFrame")


class LoadDefaultFileRequest(BaseModel):
    """Request schema for loading the configured default local spreadsheet."""

    session_id: str = Field(..., description="Unique session identifier")
    force_reload: bool = Field(
        default=False,
        description="When true, replace any cached session dataframe with fresh default sources",
    )


@router.post(
    "/upload-file",
    responses={400: {"description": "Invalid request or file loading failed"}},
)
async def upload_file(
    file: Annotated[UploadFile, File(...)],
    session_id: Annotated[Optional[str], Query()] = None,
):
    """Upload and load a CSV or XLSX file."""
    logger.info(f"Upload file request: filename={file.filename}, session_id={session_id}")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    try:
        file_bytes = await file.read()
        service = get_agent_service()
        result = await service.load_file_async(file_bytes, file.filename, session_id)
        if result["error"]:
            logger.error(f"File load error: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
        logger.info("File uploaded successfully")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Upload file exception")
        return {"session_id": session_id, "rows": 0, "columns": [], "error": str(e)}


@router.post(
    "/load-sheet",
    responses={400: {"description": "Invalid request or Google Sheet loading failed"}},
)
async def load_sheet(payload: LoadSheetRequest):
    """Load a Google Sheet by ID."""
    logger.info(f"Load sheet request: sheet_id={payload.sheet_id}, session_id={payload.session_id}")
    service = get_agent_service()
    result = await service.load_google_sheet_async(payload.sheet_id, payload.session_id)
    if result["error"]:
        logger.error(f"Sheet load error: {result['error']}")
        raise HTTPException(status_code=400, detail=result["error"])
    logger.info("Sheet loaded successfully")
    return result


@router.post(
    "/load-default-file",
    responses={400: {"description": "Invalid request or default file loading failed"}},
)
async def load_default_file(payload: LoadDefaultFileRequest):
    """Load the configured default local spreadsheet for a session."""
    logger.info(
        f"Load default file request: session_id={payload.session_id}, force_reload={payload.force_reload}"
    )
    service = get_agent_service()
    result = await service.load_default_file_async(payload.session_id, payload.force_reload)
    if result["error"]:
        logger.error(f"Default file load error: {result['error']}")
        raise HTTPException(status_code=400, detail=result["error"])
    logger.info("Default file loaded successfully")
    return result


@router.post(
    "/query",
    responses={400: {"description": "Invalid request or query execution failed"}},
)
async def query_dataframe(payload: QueryRequest):
    """Query a cached DataFrame with a natural-language question."""
    logger.info(f"Query request: session_id={payload.session_id}, question={payload.question[:50]}...")
    service = get_agent_service()
    result = await service.query_async(payload.question, payload.session_id)
    if result["error"]:
        logger.error(f"Query error: {result['error']}")
        raise HTTPException(status_code=400, detail=result["error"])
    logger.info("Query completed successfully")
    return result
