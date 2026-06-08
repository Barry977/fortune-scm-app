from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from backend.auth import get_current_user
from backend.linkedin import get_linkedin, close_linkedin, LinkedInAutomation
from backend.linkedin_schemas import (
    SearchConfig, ConnectConfig, MessageConfig, TaskCreate
)

router = APIRouter(prefix="/api/linkedin", tags=["LinkedIn自动化"])


@router.get("/status")
async def get_status(current_user=Depends(get_current_user)):
    """获取 LinkedIn 自动化状态"""
    try:
        li = await get_linkedin()
        return {
            "is_running": li.browser is not None and li.browser.is_connected(),
            "is_logged_in": li.is_logged_in,
            "has_tasks": len(li._tasks) > 0,
            "total_tasks": len(li._tasks)
        }
    except Exception:
        return {"is_running": False, "is_logged_in": False, "total_tasks": 0}


@router.get("/quota")
async def get_quota(current_user=Depends(get_current_user)):
    """获取每日额度"""
    try:
        li = await get_linkedin()
        return await li.get_quota()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def linkedin_login(
    email: str = "",
    password: str = "",
    current_user=Depends(get_current_user)
):
    """启动 LinkedIn 浏览器并登录"""
    try:
        li = await get_linkedin()
        await li.start(headless=False)
        if email and password:
            success = await li.login(email, password)
            return {"success": success, "message": "登录成功" if success else "登录失败"}
        return {"success": True, "message": "浏览器已启动，请手动登录"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_linkedin(
    config: SearchConfig,
    current_user=Depends(get_current_user)
):
    """搜索 LinkedIn 用户"""
    try:
        li = await get_linkedin()
        if not li.is_logged_in:
            raise HTTPException(status_code=400, detail="请先登录 LinkedIn")
        results = await li.search_people(config)
        return {"results": [r.dict() for r in results], "count": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connect")
async def connect_linkedin(
    config: ConnectConfig,
    current_user=Depends(get_current_user)
):
    """发送连接请求"""
    try:
        li = await get_linkedin()
        if not li.is_logged_in:
            raise HTTPException(status_code=400, detail="请先登录 LinkedIn")
        result = await li.connect_people(config)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message")
async def send_linkedin_message(
    config: MessageConfig,
    current_user=Depends(get_current_user)
):
    """发送消息"""
    try:
        li = await get_linkedin()
        if not li.is_logged_in:
            raise HTTPException(status_code=400, detail="请先登录 LinkedIn")
        result = await li.send_messages(config)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def list_tasks(current_user=Depends(get_current_user)):
    """获取任务列表"""
    try:
        li = await get_linkedin()
        return {"tasks": [t.dict() for t in li._tasks.values()], "total": len(li._tasks)}
    except Exception as e:
        return {"tasks": [], "total": 0}


@router.post("/stop")
async def stop_automation(current_user=Depends(get_current_user)):
    """停止自动化"""
    try:
        await close_linkedin()
        return {"message": "自动化已停止"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
