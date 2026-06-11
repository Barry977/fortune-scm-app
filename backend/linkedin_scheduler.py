"""
LinkedIn Scheduler — automated daily posting and outreach
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Dict, Any, Optional

from backend.database import get_db_ctx
from backend.ai_content import (
    generate_linkedin_post,
    generate_outreach_email,
    generate_linkedin_connection_note,
)

logger = logging.getLogger(__name__)


async def daily_post_task():
    """
    Daily automated LinkedIn post:
    1. AI generates a post about logistics/supply chain
    2. Publishes to LinkedIn
    3. Saves to database
    """
    try:
        logger.info("[Scheduler] Starting daily LinkedIn post task")
        
        # Check if already posted today
        today = datetime.now().date().isoformat()
        with get_db_ctx() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM linkedin_posts WHERE DATE(published_at) = ? AND status = 'published'",
                (today,)
            ).fetchone()[0]
            
            if existing > 0:
                logger.info("[Scheduler] Already posted today, skipping")
                return {"skipped": True, "reason": "Already posted today"}
        
        # Generate content with AI
        from backend.ai_content import generate_linkedin_post
        
        # Vary the style each day
        styles = ["professional", "thought_leadership", "tips", "story"]
        day_of_week = datetime.now().weekday()
        style = styles[day_of_week % len(styles)]
        
        post_content = await generate_linkedin_post(style=style)
        logger.info("[Scheduler] Generated post: %s...", post_content[:100])
        
        # Publish to LinkedIn
        from backend.linkedin import get_ops
        ops = get_ops()
        
        result = await ops.publish_post(content=post_content)
        
        if result.get("success"):
            logger.info("[Scheduler] Post published successfully")
            return {
                "success": True,
                "post_id": result.get("post_id"),
                "content": post_content[:200],
            }
        else:
            logger.error("[Scheduler] Post failed: %s", result.get("message"))
            return {"success": False, "error": result.get("message")}
            
    except Exception as e:
        logger.error("[Scheduler] Daily post task failed: %s", e)
        return {"success": False, "error": str(e)}


async def daily_outreach_task():
    """
    Daily automated outreach:
    1. Find new customers in CRM
    2. AI generates personalized messages
    3. Send connection requests or messages
    """
    try:
        logger.info("[Scheduler] Starting daily outreach task")
        
        from backend.linkedin import get_ops
        ops = get_ops()
        
        # Send 5 connection requests with AI-generated notes
        connect_result = await ops.batch_connect(count=5)
        logger.info("[Scheduler] Connections: sent=%s, failed=%s", 
                    connect_result.get("sent"), connect_result.get("failed"))
        
        # Send 3 messages to connected customers
        message_result = await ops.batch_message(count=3)
        logger.info("[Scheduler] Messages: sent=%s, failed=%s",
                    message_result.get("sent"), message_result.get("failed"))
        
        return {
            "connections": connect_result,
            "messages": message_result,
        }
        
    except Exception as e:
        logger.error("[Scheduler] Daily outreach task failed: %s", e)
        return {"success": False, "error": str(e)}


async def generate_content_drafts(count: int = 5) -> list:
    """
    Pre-generate content drafts for review.
    """
    drafts = []
    
    for i in range(count):
        try:
            post = await generate_linkedin_post()
            drafts.append({
                "index": i + 1,
                "content": post,
                "status": "draft",
            })
        except Exception as e:
            drafts.append({
                "index": i + 1,
                "error": str(e),
                "status": "failed",
            })
    
    return drafts


def get_schedule_config() -> Dict[str, Any]:
    """Get the current posting schedule configuration."""
    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT key, value FROM settings WHERE key LIKE 'schedule_%'"
        ).fetchall()
    
    config = {row["key"]: row["value"] for row in rows}
    
    return {
        "post_enabled": config.get("schedule_post_enabled", "true") == "true",
        "post_time": config.get("schedule_post_time", "09:00"),
        "outreach_enabled": config.get("schedule_outreach_enabled", "true") == "true",
        "outreach_time": config.get("schedule_outreach_time", "10:00"),
        "timezone": config.get("schedule_timezone", "UTC"),
    }


def update_schedule_config(config: Dict[str, Any]) -> bool:
    """Update the posting schedule configuration."""
    try:
        with get_db_ctx() as conn:
            for key, value in config.items():
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (f"schedule_{key}", str(value))
                )
        return True
    except Exception as e:
        logger.error("Failed to update schedule config: %s", e)
        return False
