from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional

from backend.auth import get_current_user, get_current_admin
from backend.analytics import (
    get_customer_stats, get_pipeline_summary, get_recent_activities, get_funnel
)

router = APIRouter(prefix="/api/analytics", tags=["数据分析"])


@router.get("/overview")
async def overview(current_user=Depends(get_current_user)):
    """数据概览"""
    stats = get_customer_stats()
    pipeline = get_pipeline_summary()
    return {
        "customers": {
            "total": stats["total_customers"],
            "new_this_month": stats["new_this_month"],
            "today_contacted": stats["today_contacted"],
        },
        "pipeline": pipeline["pipeline"],
        "status_distribution": stats["by_status"],
    }


@router.get("/funnel")
async def funnel(current_user=Depends(get_current_user)):
    """转化漏斗"""
    return get_funnel()


@router.get("/trends")
async def trends(days: int = 30, current_user=Depends(get_current_user)):
    """趋势数据"""
    from datetime import datetime, timedelta
    from backend.database import get_db_ctx

    trend_data = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        with get_db_ctx() as conn:
            new_c = conn.execute(
                "SELECT COUNT(*) as c FROM customers WHERE DATE(created_at) = ?", (d,)
            ).fetchone()["c"]
            try:
                contacted = conn.execute(
                    "SELECT COUNT(*) as c FROM customers WHERE DATE(last_contact) = ?", (d,)
                ).fetchone()["c"]
            except Exception:
                contacted = 0
        trend_data.append({"date": d, "new_customers": new_c, "contacted": contacted})

    return {"period": f"{days}天", "trends": list(reversed(trend_data))}


@router.get("/sources")
async def sources(current_user=Depends(get_current_user)):
    """来源分析"""
    stats = get_customer_stats()
    total = stats["total_customers"]
    by_status = stats["by_status"]

    items = []
    for status_name, count in by_status.items():
        items.append({
            "source": status_name,
            "count": count,
            "percentage": round(count / total * 100, 2) if total > 0 else 0,
        })
    return {"sources": sorted(items, key=lambda x: x["count"], reverse=True), "total": total}


@router.get("/performance")
async def performance(current_user=Depends(get_current_user)):
    """业绩分析"""
    stats = get_customer_stats()
    pipeline = get_pipeline_summary()
    total = stats["total_customers"]

    return {
        "total_customers": total,
        "new_this_month": stats["new_this_month"],
        "today_contacted": stats["today_contacted"],
        "pending_followups": stats["pending_followups"],
        "pipeline": pipeline["pipeline"],
    }


@router.get("/activities")
async def activities(limit: int = 20, current_user=Depends(get_current_user)):
    """最近活动"""
    acts = get_recent_activities(limit)
    return {"activities": acts, "total": len(acts)}
