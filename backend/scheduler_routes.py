"""
Scheduler API routes.
GET  /api/scheduler/tasks          — list all tasks
POST /api/scheduler/tasks/{id}/toggle — toggle enabled/disabled
POST /api/scheduler/run/{id}       — manual trigger
"""

from fastapi import APIRouter, HTTPException
from backend.scheduler import list_tasks, get_task, toggle_task, manual_run

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/tasks")
async def get_all_tasks():
    """Return all scheduled tasks with their config and last-run info."""
    tasks = list_tasks()
    return {"tasks": tasks}


@router.post("/tasks/{task_id}/toggle")
async def toggle_task_enabled(task_id: int):
    """Toggle a task between enabled and disabled."""
    result = toggle_task(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": result}


@router.post("/run/{task_id}")
async def run_task_now(task_id: int):
    """Manually trigger a task immediately."""
    result = manual_run(task_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result
