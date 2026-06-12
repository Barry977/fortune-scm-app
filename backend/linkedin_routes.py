"""
LinkedIn 自动化 API 路由（新架构）
接入 BrowserAdapter + LinkedInOps + TaskEngine
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from backend.auth import get_current_user
from backend.linkedin.task_engine import TaskType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/linkedin", tags=["LinkedIn自动化"])


# ── 请求模型 ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str = Field("", description="LinkedIn 邮箱")
    password: str = Field("", description="LinkedIn 密码")


class SearchRequest(BaseModel):
    keywords: str = Field(..., description="搜索关键词")
    market: str = Field("US", description="目标市场: US/EU/ME/ASIA")
    max_results: int = Field(50, ge=1, le=100)


class ConnectRequest(BaseModel):
    count: int = Field(5, ge=1, le=20, description="连接请求数量")
    note: str = Field("", description="连接备注")
    market: str = Field("US")


class MessageRequest(BaseModel):
    count: int = Field(5, ge=1, le=20, description="消息数量")
    message: str = Field("", description="消息模板 ({name} 为占位符)")


class PostRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=3000)


class PipelineRequest(BaseModel):
    keywords: str = Field(..., description="搜索关键词")
    market: str = Field("US")
    max_results: int = Field(30, ge=1, le=100)
    connect_count: int = Field(5, ge=0, le=20, description="搜索后自动发送的连接请求数")
    note: str = Field("", description="连接备注")


class ProxyConfig(BaseModel):
    proxy_url: str = Field("", description="代理地址，留空禁用")


# ── 辅助函数 ────────────────────────────────────────────────

def _get_linkedin():
    """获取 LinkedIn 模块实例"""
    from backend.linkedin import get_ops, get_engine, get_browser
    return get_ops(), get_engine(), get_browser()


# ── 状态接口 ────────────────────────────────────────────────

@router.get("/status")
async def get_status(current_user=Depends(get_current_user)):
    """获取 LinkedIn 自动化状态"""
    try:
        ops, engine, browser = _get_linkedin()
        from backend.linkedin.linkedin_ops import _load_selectors
        
        # 浏览器状态
        browser_running = browser.is_running
        
        # 登录状态
        login_status = await ops.check_login_status()
        
        # 任务统计
        task_stats = engine.get_stats()
        
        # CRM 统计
        from backend.crm import get_customer_stats
        stats = get_customer_stats()

        return {
            "browser": {
                "running": browser_running,
                "proxy": browser.proxy or "自动检测",
            },
            "login": login_status,
            "tasks": task_stats,
            "customers": stats,
            "selectors_version": _load_selectors().get("_updated", "unknown"),
        }
    except Exception as e:
        return {
            "browser": {"running": False, "proxy": ""},
            "login": {"logged_in": False, "status": f"状态检查失败: {str(e)[:100]}"},
            "tasks": {"total_tasks": 0, "by_status": {}},
            "customers": {"total_customers": 0, "by_status": {}},
        }


# ── 登录接口 ────────────────────────────────────────────────

@router.post("/login")
async def linkedin_login(req: LoginRequest, current_user=Depends(get_current_user)):
    """登录 LinkedIn（兼容旧接口，实际走手动登录）"""
    try:
        ops, engine, browser = _get_linkedin()
        result = await ops.login_manual()
        return result
    except Exception as e:
        return {"success": False, "status": "error", "message": str(e)[:300]}


@router.post("/login-manual")
async def linkedin_login_manual(current_user=Depends(get_current_user)):
    """手动登录：打开 LinkedIn 登录页，等用户自己登录"""
    try:
        ops, engine, browser = _get_linkedin()
        result = await ops.login_manual()
        return result
    except Exception as e:
        return {"success": False, "status": "error", "message": str(e)[:300]}


@router.get("/login-status")
async def linkedin_login_status(current_user=Depends(get_current_user)):
    """查询登录状态（前端轮询用）"""
    try:
        ops, engine, browser = _get_linkedin()
        if not browser.is_running:
            return {"logged_in": False, "status": "browser_closed"}
        result = await ops.check_login_status()
        return result
    except Exception as e:
        return {"logged_in": False, "status": f"检查失败: {str(e)[:100]}"}


# ── 搜索接口 ────────────────────────────────────────────────

@router.post("/search")
async def search_linkedin(req: SearchRequest, current_user=Depends(get_current_user)):
    """搜索 LinkedIn 用户"""
    try:
        ops, engine, browser = _get_linkedin()
        result = await ops.search_people(
            keywords=req.keywords,
            market=req.market,
            max_results=req.max_results,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


# ── 连接接口 ────────────────────────────────────────────────

@router.post("/connect")
async def connect_linkedin(req: ConnectRequest, current_user=Depends(get_current_user)):
    """批量发送连接请求（从CRM取新客户）"""
    try:
        ops, engine, browser = _get_linkedin()
        result = await ops.batch_connect(count=req.count, note=req.note, market=req.market)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


# ── 消息接口 ────────────────────────────────────────────────

@router.post("/message")
async def send_linkedin_message(req: MessageRequest, current_user=Depends(get_current_user)):
    """批量发送消息（从CRM取已连接客户）"""
    try:
        ops, engine, browser = _get_linkedin()
        result = await ops.batch_message(count=req.count, message_template=req.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


# ── 发帖接口 ────────────────────────────────────────────────

@router.post("/post")
async def publish_post(req: PostRequest, current_user=Depends(get_current_user)):
    """发布 LinkedIn 帖子"""
    try:
        ops, engine, browser = _get_linkedin()
        result = await ops.publish_post(content=req.content)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


# ── 全流程接口 ──────────────────────────────────────────────

@router.post("/pipeline")
async def run_pipeline(req: PipelineRequest, current_user=Depends(get_current_user)):
    """
    启动全流程：搜索 → 导入CRM → 发连接请求
    异步执行，通过任务引擎管理
    """
    try:
        ops, engine, browser = _get_linkedin()
        
        # 确保浏览器和登录
        login_result = await ops.ensure_logged_in()
        if not login_result.get("success"):
            return {
                "success": False, 
                "message": "请先登录LinkedIn",
                "login_required": True,
            }
        
        # 提交全流程任务
        task = engine.submit(
            TaskType.FULL_PIPELINE,
            params={
                "keywords": req.keywords,
                "market": req.market,
                "max_results": req.max_results,
                "connect_count": req.connect_count,
                "note": req.note,
            }
        )
        
        return {
            "success": True,
            "task_id": task.id,
            "message": f"全流程任务已启动 (ID: {task.id})",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


# ── 任务管理接口 ────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(limit: int = 50, current_user=Depends(get_current_user)):
    """获取任务列表"""
    _, engine, _ = _get_linkedin()
    tasks = engine.get_all_tasks(limit=limit)
    return {"tasks": [t.to_dict() for t in tasks], "stats": engine.get_stats()}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, current_user=Depends(get_current_user)):
    """获取单个任务详情"""
    _, engine, _ = _get_linkedin()
    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, current_user=Depends(get_current_user)):
    """取消任务"""
    _, engine, _ = _get_linkedin()
    success = engine.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="任务无法取消")
    return {"message": "任务已取消"}


# ── 代理配置 ────────────────────────────────────────────────

@router.get("/config")
async def get_config(current_user=Depends(get_current_user)):
    """获取当前配置"""
    _, _, browser = _get_linkedin()
    return {
        "proxy": browser.proxy or "(自动检测)",
        "browser_running": browser.is_running,
    }


@router.post("/config/proxy")
async def set_proxy(req: ProxyConfig, current_user=Depends(get_current_user)):
    """设置代理"""
    _, _, browser = _get_linkedin()
    browser.set_proxy(req.proxy_url)
    return {"message": "代理已更新", "proxy": req.proxy_url or "(禁用)"}


# ── 浏览器控制 ──────────────────────────────────────────────

@router.post("/stop")
async def stop_browser(current_user=Depends(get_current_user)):
    """关闭浏览器"""
    try:
        from backend.linkedin import shutdown
        await shutdown()
        return {"message": "浏览器已关闭"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


# ── 引擎控制 ────────────────────────────────────────────────

@router.post("/engine/start")
async def start_engine(current_user=Depends(get_current_user)):
    """启动任务引擎"""
    _, engine, _ = _get_linkedin()
    await engine.start()
    return {"message": "任务引擎已启动"}


@router.post("/engine/stop")
async def stop_engine(current_user=Depends(get_current_user)):
    """停止任务引擎"""
    _, engine, _ = _get_linkedin()
    await engine.stop()
    return {"message": "任务引擎已停止"}
