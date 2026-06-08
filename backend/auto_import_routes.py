"""
Auto-import API routes.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.auth import get_current_user
from backend.auto_import import (
    auto_import_from_linkedin,
    auto_import_batch,
    get_auto_import_stats,
    sync_linkedin_activity,
)

router = APIRouter(prefix="/api/auto-import", tags=["自动导入"])


class LinkedInSearchImport(BaseModel):
    keywords: str = Field(..., description="Search keywords")
    market: str = Field("US", description="Target market: US, EU, ME")
    max_results: int = Field(50, ge=1, le=100, description="Max results to import")
    auto_connect: bool = Field(False, description="Automatically send connection requests")


class BatchImportConfig(BaseModel):
    searches: List[LinkedInSearchImport] = Field(..., description="List of search configurations")


@router.post("/linkedin")
async def import_from_linkedin(req: LinkedInSearchImport, current_user=Depends(get_current_user)):
    """
    Automatically search LinkedIn and import results to CRM.
    Searches for people matching keywords, imports to CRM, optionally sends connection requests.
    """
    try:
        result = await auto_import_from_linkedin(
            keywords=req.keywords,
            market=req.market,
            max_results=req.max_results,
            auto_connect=req.auto_connect,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/linkedin/batch")
async def batch_import(req: BatchImportConfig, current_user=Depends(get_current_user)):
    """
    Batch import from multiple LinkedIn searches.
    Run multiple searches and import all results to CRM.
    """
    try:
        configs = [s.dict() for s in req.searches]
        result = await auto_import_batch(configs)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def import_stats(current_user=Depends(get_current_user)):
    """Get auto-import statistics."""
    try:
        return get_auto_import_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-activity")
async def sync_activity(current_user=Depends(get_current_user)):
    """Sync LinkedIn activity data to analytics."""
    try:
        result = await sync_linkedin_activity()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
