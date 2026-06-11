"""
LinkedIn automation API routes.
Wraps real Playwright browser automation via backend.linkedin_service.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List

from backend.auth import get_current_user
from backend.linkedin_service import (
    search_people,
    send_connections,
    send_messages,
    get_customer_stats,
    get_quota,
    is_logged_in,
    login,
    close_browser,
    configure_proxy,
    get_config,
    create_post,
    get_posts,
    update_post_stats,
    delete_post,
)

router = APIRouter(prefix="/api/linkedin", tags=["LinkedIn自动化"])


# ── Request schemas ─────────────────────────────────────────────────

class SearchRequest(BaseModel):
    keywords: str = Field(..., description="Search keywords (company name, job title, etc.)")
    market: str = Field("US", description="Target market: US, EU, ME")
    max_results: int = Field(50, ge=1, le=100, description="Max results to return")


class ConnectRequest(BaseModel):
    count: int = Field(5, ge=1, le=20, description="Number of connections to send")
    note: Optional[str] = Field(None, max_length=300, description="Connection request note")
    market: str = Field("US", description="Target market")


class MessageRequest(BaseModel):
    count: int = Field(5, ge=1, le=20, description="Number of messages to send")
    message: Optional[str] = Field(None, max_length=2000, description="Custom message (use {name} placeholder)")


class LoginRequest(BaseModel):
    email: str = Field("", description="LinkedIn email (falls back to env)")
    password: str = Field("", description="LinkedIn password (falls back to env)")


class PostRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=3000, description="Post text content")
    image_paths: Optional[List[str]] = Field(None, description="Local image file paths to attach")


class PostStatsRequest(BaseModel):
    likes: int = Field(0, ge=0)
    comments: int = Field(0, ge=0)
    views: int = Field(0, ge=0)


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/status")
async def get_status(current_user=Depends(get_current_user)):
    """Get LinkedIn automation status: browser state + customer stats."""
    try:
        from backend.linkedin_service import is_browser_running, HAS_PLAYWRIGHT
        browser_alive = is_browser_running()
        from backend.crm import get_customer_stats
        stats = get_customer_stats()

        # Determine detailed status
        if not HAS_PLAYWRIGHT:
            status_detail = "playwright_missing"
            status_text = "Playwright 未安装"
        elif not browser_alive:
            status_detail = "disconnected"
            status_text = "浏览器未启动"
        else:
            status_detail = "connected"
            status_text = "浏览器运行中"

        return {
            "is_logged_in": browser_alive and HAS_PLAYWRIGHT,
            "status_detail": status_detail,
            "status_text": status_text,
            "has_playwright": HAS_PLAYWRIGHT,
            "customer_stats": stats,
        }
    except Exception as e:
        return {
            "is_logged_in": False,
            "status_detail": "error",
            "status_text": f"状态检查失败: {str(e)[:100]}",
            "has_playwright": False,
            "customer_stats": {"total_customers": 0, "by_status": {}},
        }


@router.get("/quota")
async def get_daily_quota(current_user=Depends(get_current_user)):
    """Get today's daily usage and remaining quota for search/connect/message."""
    try:
        return get_quota()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def linkedin_login(req: LoginRequest = LoginRequest(), current_user=Depends(get_current_user)):
    """Launch browser and log in to LinkedIn."""
    try:
        result = await login(email=req.email, password=req.password)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)[:300]}


@router.post("/search")
async def search_linkedin(req: SearchRequest, current_user=Depends(get_current_user)):
    """Search LinkedIn people by keywords and market."""
    try:
        results = await search_people(
            keywords=req.keywords,
            market=req.market,
            max_results=req.max_results,
        )
        return {"results": results, "count": len(results)}
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connect")
async def connect_linkedin(req: ConnectRequest, current_user=Depends(get_current_user)):
    """Send connection requests to pending customers in the CRM."""
    try:
        result = await send_connections(count=req.count, note=req.note, market=req.market)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message")
async def send_linkedin_message(req: MessageRequest, current_user=Depends(get_current_user)):
    """Send messages to connected customers in the CRM."""
    try:
        result = await send_messages(count=req.count, message=req.message)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_automation(current_user=Depends(get_current_user)):
    """Shut down the browser session."""
    try:
        await close_browser()
        return {"message": "Browser closed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ProxyConfig(BaseModel):
    proxy_url: str = Field("", description="Proxy URL, e.g. socks5://127.0.0.1:1081. Empty to disable.")


@router.get("/config")
async def get_linkedin_config(current_user=Depends(get_current_user)):
    """Get current LinkedIn configuration (proxy, profile dir, etc.)."""
    return get_config()


@router.post("/config/proxy")
async def set_proxy(req: ProxyConfig, current_user=Depends(get_current_user)):
    """Set or clear the proxy for LinkedIn browser sessions."""
    configure_proxy(req.proxy_url)
    return {"message": "Proxy updated", "proxy": req.proxy_url or "(disabled)"}


# ── Post endpoints ─────────────────────────────────────────────────

@router.post("/post")
async def publish_post(req: PostRequest, current_user=Depends(get_current_user)):
    """Publish a LinkedIn post with optional images."""
    try:
        result = await create_post(
            content=req.content,
            image_paths=req.image_paths,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/posts")
async def list_posts(status: Optional[str] = None, limit: int = 50, current_user=Depends(get_current_user)):
    """List LinkedIn posts with optional status filter."""
    try:
        posts = get_posts(status=status, limit=limit)
        return {"posts": posts, "count": len(posts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/posts/{post_id}/stats")
async def update_stats(post_id: int, req: PostStatsRequest, current_user=Depends(get_current_user)):
    """Update engagement stats for a post."""
    try:
        update_post_stats(post_id, req.likes, req.comments, req.views)
        return {"message": "Stats updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/posts/{post_id}")
async def remove_post(post_id: int, current_user=Depends(get_current_user)):
    """Delete a post record."""
    try:
        success = delete_post(post_id)
        if success:
            return {"message": "Post deleted"}
        raise HTTPException(status_code=404, detail="Post not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
