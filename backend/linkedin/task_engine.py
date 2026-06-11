"""
TaskEngine - 异步任务队列引擎
职责：任务调度、状态管理、失败重试、进度上报
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    LOGIN = "login"
    SEARCH = "search"
    BATCH_CONNECT = "batch_connect"
    BATCH_MESSAGE = "batch_message"
    POST = "post"
    FULL_PIPELINE = "full_pipeline"  # 搜索→导入→连接 全流程


@dataclass
class Task:
    id: str
    type: TaskType
    params: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    progress: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "params": self.params,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
        }


class TaskEngine:
    """
    任务引擎：管理所有 LinkedIn 自动化任务
    - 异步任务队列
    - 状态机管理
    - 失败自动重试
    - 实时进度回调
    """

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._progress_callbacks: List[Callable] = []
        self._linkedin_ops = None  # 延迟初始化
        self._browser = None

    def set_ops(self, ops):
        """设置 LinkedInOps 实例"""
        self._linkedin_ops = ops

    def set_browser(self, browser):
        """设置 BrowserAdapter 实例"""
        self._browser = browser

    def on_progress(self, callback: Callable):
        """注册进度回调: callback(task: Task)"""
        self._progress_callbacks.append(callback)

    def _notify_progress(self, task: Task):
        for cb in self._progress_callbacks:
            try:
                cb(task)
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        return self._running

    # ── 任务管理 ────────────────────────────────────────────

    def submit(self, task_type: TaskType, params: Dict[str, Any] = None) -> Task:
        """提交任务到队列"""
        task = Task(
            id=str(uuid.uuid4())[:8],
            type=task_type,
            params=params or {},
        )
        self._tasks[task.id] = task
        self._queue.put_nowait(task)
        self._notify_progress(task)
        logger.info("[TaskEngine] 任务已提交: %s (%s)", task.type.value, task.id)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_all_tasks(self, limit: int = 50) -> List[Task]:
        """获取最近的任务列表"""
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def get_running_tasks(self) -> List[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            self._notify_progress(task)
            return True
        return False

    # ── 引擎生命周期 ────────────────────────────────────────

    async def start(self):
        """启动任务引擎"""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("[TaskEngine] 引擎已启动")

    async def stop(self):
        """停止任务引擎"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("[TaskEngine] 引擎已停止")

    async def _worker_loop(self):
        """任务消费循环"""
        while self._running:
            try:
                # 等待任务，超时1秒检查一次_running状态
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if task.status == TaskStatus.CANCELLED:
                continue

            await self._execute_task(task)

    async def _execute_task(self, task: Task):
        """执行单个任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now().isoformat()
        self._notify_progress(task)

        logger.info("[TaskEngine] 执行任务: %s (%s)", task.type.value, task.id)

        try:
            result = await self._dispatch(task)
            task.result = result
            task.status = TaskStatus.DONE
            task.completed_at = datetime.now().isoformat()
            logger.info("[TaskEngine] 任务完成: %s (%s)", task.id, task.type.value)

        except Exception as e:
            logger.error("[TaskEngine] 任务失败: %s (%s): %s", task.id, task.type.value, e)
            task.error = str(e)[:500]

            # 重试
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                task.progress = f"重试中 ({task.retry_count}/{task.max_retries})"
                logger.info("[TaskEngine] 重试任务: %s (第%d次)", task.id, task.retry_count)
                self._queue.put_nowait(task)
                self._notify_progress(task)
                return

            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now().isoformat()

        self._notify_progress(task)

        # 持久化任务结果到DB
        self._persist_task(task)

    async def _dispatch(self, task: Task) -> Dict[str, Any]:
        """根据任务类型分发执行"""
        ops = self._linkedin_ops
        if not ops:
            raise RuntimeError("LinkedInOps 未初始化")

        task_type = task.type
        params = task.params

        if task_type == TaskType.LOGIN:
            return await ops.ensure_logged_in(
                email=params.get("email", ""),
                password=params.get("password", ""),
            )

        elif task_type == TaskType.SEARCH:
            def on_search_progress(pct, detail):
                task.progress = detail
                self._notify_progress(task)

            return await ops.search_people(
                keywords=params["keywords"],
                market=params.get("market", "US"),
                max_results=params.get("max_results", 50),
            )

        elif task_type == TaskType.BATCH_CONNECT:
            return await ops.batch_connect(
                count=params.get("count", 5),
                note=params.get("note", ""),
                market=params.get("market", "US"),
            )

        elif task_type == TaskType.BATCH_MESSAGE:
            return await ops.batch_message(
                count=params.get("count", 5),
                message_template=params.get("message", ""),
            )

        elif task_type == TaskType.POST:
            return await ops.publish_post(content=params["content"])

        elif task_type == TaskType.FULL_PIPELINE:
            return await self._run_full_pipeline(task, params)

        else:
            raise ValueError(f"未知任务类型: {task_type}")

    async def _run_full_pipeline(self, task: Task, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        全流程：搜索 → 导入CRM → 发连接请求
        """
        ops = self._linkedin_ops
        results = {}

        # Step 1: 搜索
        task.progress = "步骤1/3: 搜索客户..."
        self._notify_progress(task)
        search_result = await ops.search_people(
            keywords=params["keywords"],
            market=params.get("market", "US"),
            max_results=params.get("max_results", 30),
        )
        results["search"] = search_result

        if not search_result.get("success") or not search_result.get("results"):
            return {"success": False, "error": "搜索未找到结果", "results": results}

        # Step 2: 导入CRM
        task.progress = f"步骤2/3: 导入 {len(search_result['results'])} 个客户到CRM..."
        self._notify_progress(task)
        imported = await self._import_to_crm(search_result["results"])
        results["imported"] = imported

        # Step 3: 发连接请求
        connect_count = min(params.get("connect_count", 5), imported)
        task.progress = f"步骤3/3: 发送 {connect_count} 个连接请求..."
        self._notify_progress(task)
        connect_result = await ops.batch_connect(
            count=connect_count,
            note=params.get("note", ""),
        )
        results["connect"] = connect_result

        return {
            "success": True,
            "found": len(search_result["results"]),
            "imported": imported,
            "connected": connect_result.get("sent", 0),
            "results": results,
        }

    async def _import_to_crm(self, profiles: List[Dict]) -> int:
        """将搜索结果导入CRM"""
        from backend.database import get_db_ctx
        imported = 0
        with get_db_ctx() as conn:
            for p in profiles:
                try:
                    # 去重：检查 LinkedIn URL 是否已存在
                    existing = conn.execute(
                        "SELECT id FROM customers WHERE linkedin_url = ?",
                        (p.get("url", ""),)
                    ).fetchone()
                    if existing:
                        continue

                    conn.execute(
                        """INSERT INTO customers (name, company, title, linkedin_url, status, source, created_at, updated_at)
                           VALUES (?, ?, ?, ?, 'new', 'linkedin_search', ?, ?)""",
                        (
                            p.get("name", ""),
                            p.get("company", ""),
                            p.get("title", ""),
                            p.get("url", ""),
                            datetime.now().isoformat(),
                            datetime.now().isoformat(),
                        )
                    )
                    imported += 1
                except Exception as e:
                    logger.debug("[Import] 导入失败 %s: %s", p.get("name"), e)
        return imported

    def _persist_task(self, task: Task):
        """持久化任务记录到数据库"""
        try:
            from backend.database import get_db_ctx
            with get_db_ctx() as conn:
                conn.execute(
                    """INSERT INTO linkedin_tasks 
                       (task_type, status, params, result, result_count, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        task.type.value,
                        task.status.value,
                        json.dumps(task.params, ensure_ascii=False),
                        json.dumps(task.result or {}, ensure_ascii=False, default=str),
                        len(task.result.get("results", [])) if task.result else 0,
                        task.created_at,
                    )
                )
        except Exception as e:
            logger.debug("[TaskEngine] 持久化任务失败: %s", e)

    # ── 统计 ────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取任务引擎统计"""
        total = len(self._tasks)
        by_status = {}
        for task in self._tasks.values():
            s = task.status.value
            by_status[s] = by_status.get(s, 0) + 1

        return {
            "total_tasks": total,
            "by_status": by_status,
            "is_running": self._running,
            "queue_size": self._queue.qsize(),
        }
