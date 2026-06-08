"""
AI Content Generation API routes.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List

from backend.auth import get_current_user
from backend.ai_content import (
    generate_linkedin_post,
    generate_outreach_email,
    generate_reply,
    generate_linkedin_connection_note,
    generate_daily_content_plan,
)

router = APIRouter(prefix="/api/ai-content", tags=["AI内容生成"])


class PostRequest(BaseModel):
    topic: str = Field("", description="Specific topic for the post")
    style: str = Field("professional", description="Post style: professional, thought_leadership, tips, story")


class EmailRequest(BaseModel):
    company_name: str = Field("", description="Target company name")
    contact_title: str = Field("", description="Contact person's title")
    context: str = Field("", description="Additional context")


class ReplyRequest(BaseModel):
    original_message: str = Field(..., description="Original message to reply to")
    context: str = Field("", description="Additional context")
    tone: str = Field("professional", description="Reply tone")


class ConnectionNoteRequest(BaseModel):
    person_name: str = Field("", description="Person's name")
    person_title: str = Field("", description="Person's title")
    person_company: str = Field("", description="Person's company")


@router.post("/generate-post")
async def gen_post(req: PostRequest, current_user=Depends(get_current_user)):
    """Generate a LinkedIn post using AI."""
    try:
        content = await generate_linkedin_post(topic=req.topic, style=req.style)
        return {"content": content, "style": req.style}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-email")
async def gen_email(req: EmailRequest, current_user=Depends(get_current_user)):
    """Generate a cold outreach email using AI."""
    try:
        content = await generate_outreach_email(
            company_name=req.company_name,
            contact_title=req.contact_title,
            context=req.context,
        )
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-reply")
async def gen_reply(req: ReplyRequest, current_user=Depends(get_current_user)):
    """Generate a reply to a client message using AI."""
    try:
        content = await generate_reply(
            original_message=req.original_message,
            context=req.context,
            tone=req.tone,
        )
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-note")
async def gen_note(req: ConnectionNoteRequest, current_user=Depends(get_current_user)):
    """Generate a LinkedIn connection request note using AI."""
    try:
        content = await generate_linkedin_connection_note(
            person_name=req.person_name,
            person_title=req.person_title,
            person_company=req.person_company,
        )
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-plan")
async def get_daily_plan(current_user=Depends(get_current_user)):
    """Generate a full day's content plan using AI."""
    try:
        plan = await generate_daily_content_plan()
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
