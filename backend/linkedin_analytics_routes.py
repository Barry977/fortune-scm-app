"""
LinkedIn Analytics API routes.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional

from backend.auth import get_current_user
from backend.linkedin_analytics import (
    get_linkedin_overview,
    get_post_performance,
    get_daily_activity_trend,
    get_content_topics_analysis,
    update_post_engagement,
    get_top_performing_posts,
)

router = APIRouter(prefix="/api/linkedin-analytics", tags=["LinkedIn分析"])


@router.get("/overview")
async def analytics_overview(days: int = Query(30, ge=1, le=365), current_user=Depends(get_current_user)):
    """Get LinkedIn activity overview."""
    try:
        return get_linkedin_overview(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/posts")
async def post_performance(limit: int = Query(20, ge=1, le=100), current_user=Depends(get_current_user)):
    """Get post performance data."""
    try:
        return {"posts": get_post_performance(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trend")
async def activity_trend(days: int = Query(30, ge=1, le=365), current_user=Depends(get_current_user)):
    """Get daily activity trend."""
    try:
        return {"trend": get_daily_activity_trend(days=days)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topics")
async def topics_analysis(current_user=Depends(get_current_user)):
    """Get content topics analysis."""
    try:
        return get_content_topics_analysis()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-posts")
async def top_posts(limit: int = Query(5, ge=1, le=20), current_user=Depends(get_current_user)):
    """Get top performing posts."""
    try:
        return {"posts": get_top_performing_posts(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class EngagementUpdate(BaseModel):
    likes: int = Field(0, ge=0)
    comments: int = Field(0, ge=0)
    views: int = Field(0, ge=0)


@router.put("/posts/{post_id}/engagement")
async def update_engagement(post_id: int, req: EngagementUpdate, current_user=Depends(get_current_user)):
    """Update post engagement metrics."""
    try:
        success = update_post_engagement(post_id, req.likes, req.comments, req.views)
        if success:
            return {"message": "Engagement updated"}
        raise HTTPException(status_code=404, detail="Post not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
