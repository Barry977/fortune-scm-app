"""
Scheduler API routes.
GET    /api/scheduler/tasks              — list all tasks
POST   /api/scheduler/tasks/{id}/toggle  — toggle enabled/disabled
PUT    /api/scheduler/tasks/{id}/schedule — update schedule time
POST   /api/scheduler/run/{id}           — manual trigger
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional

from backend.auth import get_current_user
from backend.scheduler import list_tasks, get_task, toggle_task, manual_run, update_task_schedule

router = APIRouter(prefix="/api/scheduler", tags=["定时任务"])


class ScheduleUpdate(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour (0-23)")
    minute: int = Field(..., ge=0, le=59, description="Minute (0-59)")
    enabled: Optional[bool] = Field(None, description="Enable/disable task")


@router.get("/tasks")
async def get_all_tasks(current_user=Depends(get_current_user)):
    """Return all scheduled tasks with their config and last-run info."""
    tasks = list_tasks()
    return {"tasks": tasks}


@router.post("/tasks/{task_id}/toggle")
async def toggle_task_enabled(task_id: int, current_user=Depends(get_current_user)):
    """Toggle a task between enabled and disabled."""
    result = toggle_task(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": result}


@router.put("/tasks/{task_id}/schedule")
async def update_schedule(task_id: int, req: ScheduleUpdate, current_user=Depends(get_current_user)):
    """Update task schedule time."""
    result = update_task_schedule(
        task_id=task_id,
        hour=req.hour,
        minute=req.minute,
        enabled=req.enabled,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": result}


@router.post("/run/{task_id}")
async def run_task_now(task_id: int, current_user=Depends(get_current_user)):
    """Manually trigger a task immediately."""
    result = manual_run(task_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result
