"""
LinkedIn 自动化模块
- BrowserAdapter: 浏览器管理（反检测、崩溃恢复、Cookie持久化）
- LinkedInOps: LinkedIn 操作（搜索、连接、消息、发帖）
- TaskEngine: 任务引擎（队列、状态机、重试）
"""

from typing import Optional
from backend.linkedin.browser_adapter import BrowserAdapter
from backend.linkedin.linkedin_ops import LinkedInOps
from backend.linkedin.task_engine import TaskEngine, TaskType, TaskStatus

# 全局单例
_browser: Optional[BrowserAdapter] = None
_ops: Optional[LinkedInOps] = None
_engine: Optional[TaskEngine] = None


def get_browser() -> BrowserAdapter:
    global _browser
    if _browser is None:
        _browser = BrowserAdapter()
    return _browser


def get_ops() -> LinkedInOps:
    global _ops
    if _ops is None:
        _ops = LinkedInOps(get_browser())
    return _ops


def get_engine() -> TaskEngine:
    global _engine
    if _engine is None:
        _engine = TaskEngine()
        _engine.set_ops(get_ops())
        _engine.set_browser(get_browser())
    return _engine


async def shutdown():
    """关闭所有资源"""
    global _browser, _ops, _engine
    if _engine:
        await _engine.stop()
    if _browser:
        await _browser.close()
    _browser = None
    _ops = None
    _engine = None
