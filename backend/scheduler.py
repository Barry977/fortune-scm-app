"""
In-process task scheduler for Fortune SCM.
Uses APScheduler (BackgroundScheduler) to run recurring automation tasks.
Task configs are persisted in the scheduler_tasks SQLite table.
"""

import asyncio
import json
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.database import get_db_ctx

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync context, handling both cases:
    - Inside running event loop (FastAPI request): use new thread
    - Outside event loop (APScheduler thread): use asyncio.run()
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=120)
    else:
        return asyncio.run(coro)

# ---------------------------------------------------------------------------
# Singleton scheduler instance
# ---------------------------------------------------------------------------
_scheduler: Optional[BackgroundScheduler] = None


def _ensure_table():
    """Create the scheduler_tasks table if it doesn't exist."""
    with get_db_ctx() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scheduler_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                schedule_cron TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run TEXT,
                last_result TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)


# ---------------------------------------------------------------------------
# Task implementations
# ---------------------------------------------------------------------------

def _task_linkedin_connect():
    """Daily LinkedIn batch connection requests."""
    logger.info("[Scheduler] Running LinkedIn batch connect")
    try:
        from backend.linkedin_service import send_connections
        result = _run_async(send_connections(count=5))
        return {"success": True, "result": result}
    except Exception as e:
        logger.error("[Scheduler] LinkedIn connect failed: %s", e)
        return {"success": False, "error": str(e)}


def _task_linkedin_message():
    """Daily LinkedIn batch messaging."""
    logger.info("[Scheduler] Running LinkedIn batch message")
    try:
        from backend.linkedin_service import send_messages
        result = _run_async(send_messages(count=5))
        return {"success": True, "result": result}
    except Exception as e:
        logger.error("[Scheduler] LinkedIn message failed: %s", e)
        return {"success": False, "error": str(e)}


def _task_linkedin_daily_post():
    """Daily AI-generated LinkedIn post."""
    logger.info("[Scheduler] Running daily LinkedIn post")
    try:
        from backend.linkedin_scheduler import daily_post_task
        result = _run_async(daily_post_task())
        return result
    except Exception as e:
        logger.error("[Scheduler] Daily post failed: %s", e)
        return {"success": False, "error": str(e)}


def _task_auto_import():
    """Daily auto-import from LinkedIn searches."""
    logger.info("[Scheduler] Running auto-import")
    try:
        from backend.auto_import import auto_import_batch
        
        # Default search configurations for different markets
        search_configs = [
            {"keywords": "logistics manager", "market": "US", "max_results": 30},
            {"keywords": "supply chain director", "market": "US", "max_results": 30},
            {"keywords": "procurement manager", "market": "EU", "max_results": 30},
            {"keywords": "shipping coordinator", "market": "ME", "max_results": 20},
        ]
        
        result = _run_async(auto_import_batch(search_configs))
        return result
    except Exception as e:
        logger.error("[Scheduler] Auto-import failed: %s", e)
        return {"success": False, "error": str(e)}


def _task_cold_email():
    """Daily cold email batch — emails customers with status 'new' that have an email."""
    logger.info("[Scheduler] Running cold email batch")
    try:
        from backend.email_smtp import (
            send_batch_emails, get_default_smtp_config, list_templates,
        )
        from backend.email_schemas import SendEmailBatchRequest, EmailRecipient

        config = get_default_smtp_config()
        if not config:
            return {"success": False, "error": "No SMTP config found"}

        # Pick the first active template as the cold-email template
        templates = list_templates()
        if not templates:
            return {"success": False, "error": "No email templates found"}
        template_id = templates[0]["id"]

        # Gather customers with email and status 'new'
        with get_db_ctx() as conn:
            rows = conn.execute(
                """SELECT id, name, email FROM customers
                   WHERE email IS NOT NULL AND email != ''
                     AND status IN ('new', '新线索')
                   ORDER BY created_at DESC LIMIT 50"""
            ).fetchall()

        if not rows:
            return {"success": True, "sent": 0, "message": "No new customers with email"}

        recipients = [
            EmailRecipient(email=r["email"], name=r["name"], variables={"name": r["name"]})
            for r in rows
        ]

        request = SendEmailBatchRequest(
            template_id=template_id,
            recipients=recipients,
            batch_size=50,
            delay_seconds=2,
        )
        result = send_batch_emails(request, user_id=0)

        # Update status of emailed customers
        with get_db_ctx() as conn:
            for r in rows:
                conn.execute(
                    "UPDATE customers SET status = '已发邮件', updated_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), r["id"]),
                )

        return {"success": True, "result": result}
    except Exception as e:
        logger.error("[Scheduler] Cold email failed: %s\n%s", e, traceback.format_exc())
        return {"success": False, "error": str(e)}


def _task_daily_stats():
    """Daily stats report — just logs the current stats."""
    logger.info("[Scheduler] Generating daily stats report")
    try:
        from backend.analytics import get_customer_stats
        stats = get_customer_stats()
        logger.info("[Scheduler] Daily stats: %s", json.dumps(stats, ensure_ascii=False))
        return {"success": True, "result": stats}
    except Exception as e:
        logger.error("[Scheduler] Daily stats failed: %s", e)
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Built-in task definitions
# ---------------------------------------------------------------------------

BUILTIN_TASKS: List[Dict[str, Any]] = [
    {
        "name": "auto_import",
        "display_name": "自动导入客户 (LinkedIn搜索)",
        "cron_hour": 8,
        "cron_minute": 0,
        "func": _task_auto_import,
    },
    {
        "name": "linkedin_daily_post",
        "display_name": "LinkedIn 每日自动发帖 (AI生成)",
        "cron_hour": 9,
        "cron_minute": 0,
        "func": _task_linkedin_daily_post,
    },
    {
        "name": "linkedin_connect",
        "display_name": "LinkedIn 批量添加好友",
        "cron_hour": 10,
        "cron_minute": 0,
        "func": _task_linkedin_connect,
    },
    {
        "name": "linkedin_message",
        "display_name": "LinkedIn 批量发送消息",
        "cron_hour": 15,
        "cron_minute": 0,
        "func": _task_linkedin_message,
    },
    {
        "name": "cold_email",
        "display_name": "冷邮件批量发送",
        "cron_hour": 16,
        "cron_minute": 0,
        "func": _task_cold_email,
    },
    {
        "name": "daily_stats",
        "display_name": "每日统计报告",
        "cron_hour": 23,
        "cron_minute": 0,
        "func": _task_daily_stats,
    },
]


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def _run_task_wrapper(task_name: str, func: Callable):
    """Wrapper that runs a task, captures result, and updates the DB."""
    logger.info("[Scheduler] Executing task: %s", task_name)
    result = func()
    result_json = json.dumps(result, ensure_ascii=False, default=str)
    now = datetime.now().isoformat()
    with get_db_ctx() as conn:
        conn.execute(
            "UPDATE scheduler_tasks SET last_run = ?, last_result = ?, updated_at = ? WHERE name = ?",
            (now, result_json, now, task_name),
        )
    logger.info("[Scheduler] Task %s finished: %s", task_name, result_json[:200])


def _seed_builtin_tasks():
    """Insert built-in tasks into the DB if they don't already exist."""
    now = datetime.now().isoformat()
    with get_db_ctx() as conn:
        for t in BUILTIN_TASKS:
            cron_expr = f"{t['cron_minute']} {t['cron_hour']} * * *"
            conn.execute(
                """INSERT OR IGNORE INTO scheduler_tasks
                   (name, display_name, schedule_cron, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, 1, ?, ?)""",
                (t["name"], t["display_name"], cron_expr, now, now),
            )


def _sync_jobs():
    """Read task configs from DB and (re)register APScheduler jobs."""
    global _scheduler
    if _scheduler is None:
        return

    func_map = {t["name"]: t["func"] for t in BUILTIN_TASKS}

    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM scheduler_tasks").fetchall()

    existing_jobs = {j.id for j in _scheduler.get_jobs()}

    for row in rows:
        task_name = row["name"]
        enabled = bool(row["enabled"])

        if task_name not in func_map:
            continue

        if not enabled:
            # Remove job if it exists but is disabled
            if task_name in existing_jobs:
                _scheduler.remove_job(task_name)
                logger.info("[Scheduler] Removed disabled task: %s", task_name)
            continue

        # Parse cron: "MM HH * * *"
        parts = row["schedule_cron"].split()
        if len(parts) < 2:
            continue
        minute, hour = parts[0], parts[1]

        trigger = CronTrigger(hour=hour, minute=minute)

        _scheduler.add_job(
            _run_task_wrapper,
            trigger=trigger,
            id=task_name,
            args=[task_name, func_map[task_name]],
            replace_existing=True,
            name=row["display_name"],
        )
        logger.info("[Scheduler] Scheduled task: %s at %s:%s", task_name, hour, minute)


def init_scheduler() -> BackgroundScheduler:
    """Initialize and start the background scheduler. Call once at app startup."""
    global _scheduler

    _ensure_table()
    _seed_builtin_tasks()

    _scheduler = BackgroundScheduler(
        timezone="Asia/Shanghai",
        job_defaults={"coalesce": True, "max_instances": 1},
    )

    _sync_jobs()
    _scheduler.start()
    logger.info("[Scheduler] Started with %d jobs", len(_scheduler.get_jobs()))
    return _scheduler


def shutdown_scheduler():
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Shut down")
        _scheduler = None


# ---------------------------------------------------------------------------
# Helpers for API routes
# ---------------------------------------------------------------------------

def list_tasks() -> List[Dict[str, Any]]:
    """Return all scheduler tasks from the DB."""
    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT * FROM scheduler_tasks ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM scheduler_tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return dict(row) if row else None


def toggle_task(task_id: int) -> Optional[Dict[str, Any]]:
    """Toggle a task's enabled flag and reschedule."""
    task = get_task(task_id)
    if not task:
        return None
    new_enabled = 0 if task["enabled"] else 1
    now = datetime.now().isoformat()
    with get_db_ctx() as conn:
        conn.execute(
            "UPDATE scheduler_tasks SET enabled = ?, updated_at = ? WHERE id = ?",
            (new_enabled, now, task_id),
        )
    # Re-sync APScheduler jobs
    _sync_jobs()
    return get_task(task_id)


def update_task_schedule(task_id: int, hour: int, minute: int, enabled: Optional[bool] = None) -> Optional[Dict[str, Any]]:
    """Update a task's schedule time and optionally toggle enabled state."""
    task = get_task(task_id)
    if not task:
        return None
    
    cron_expr = f"{minute} {hour} * * *"
    now = datetime.now().isoformat()
    
    with get_db_ctx() as conn:
        if enabled is not None:
            conn.execute(
                "UPDATE scheduler_tasks SET schedule_cron = ?, enabled = ?, updated_at = ? WHERE id = ?",
                (cron_expr, 1 if enabled else 0, now, task_id),
            )
        else:
            conn.execute(
                "UPDATE scheduler_tasks SET schedule_cron = ?, updated_at = ? WHERE id = ?",
                (cron_expr, now, task_id),
            )
    
    # Re-sync APScheduler jobs
    _sync_jobs()
    return get_task(task_id)


def manual_run(task_id: int) -> Dict[str, Any]:
    """Trigger a task immediately (in a background thread)."""
    task = get_task(task_id)
    if not task:
        return {"success": False, "error": "Task not found"}

    func_map = {t["name"]: t["func"] for t in BUILTIN_TASKS}
    func = func_map.get(task["name"])
    if not func:
        return {"success": False, "error": f"No implementation for task '{task['name']}'"}

    # Run and capture actual result
    try:
        result = func()
        result_json = json.dumps(result, ensure_ascii=False, default=str) if result else "{}"
        now = datetime.now().isoformat()
        with get_db_ctx() as conn:
            conn.execute(
                "UPDATE scheduler_tasks SET last_run = ?, last_result = ?, updated_at = ? WHERE name = ?",
                (now, result_json, now, task["name"]),
            )
        if result and not result.get("success", True):
            return {"success": False, "error": result.get("error", "任务执行失败"), "task": get_task(task_id)}
        return {"success": True, "message": _format_task_result(task["name"], result), "task": get_task(task_id)}
    except Exception as e:
        error_msg = str(e)[:300]
        logger.error("Manual run failed for %s: %s", task["name"], e)
        now = datetime.now().isoformat()
        with get_db_ctx() as conn:
            conn.execute(
                "UPDATE scheduler_tasks SET last_run = ?, last_result = ?, updated_at = ? WHERE name = ?",
                (now, json.dumps({"success": False, "error": error_msg}), now, task["name"]),
            )
        return {"success": False, "error": error_msg, "task": get_task(task_id)}


def _format_task_result(task_name: str, result: Any) -> str:
    """Format task result into a human-readable message."""
    if not result:
        return "执行完成"
    if isinstance(result, dict):
        if result.get("error"):
            return f"失败: {result['error'][:100]}"
        if task_name == "linkedin_connect":
            return f"已发送 {result.get('sent', 0)} 个连接请求，失败 {result.get('failed', 0)}"
        if task_name == "linkedin_message":
            return f"已发送 {result.get('sent', 0)} 条消息，失败 {result.get('failed', 0)}"
        if task_name == "cold_email":
            sent = result.get("sent", result.get("result", {}).get("sent", 0))
            return f"已发送 {sent} 封邮件"
        if result.get("message"):
            return result["message"][:100]
    return "执行完成"
