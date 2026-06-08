"""
数据分析模块 - 从 SQLite 读取真实数据
"""
from datetime import datetime, date, timedelta
from typing import Dict, Any, List
from backend.database import get_db_ctx


def get_customer_stats() -> Dict[str, Any]:
    """获取客户统计"""
    with get_db_ctx() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM customers").fetchone()["c"]

        # 按状态统计
        status_rows = conn.execute(
            "SELECT status, COUNT(*) as c FROM customers GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["c"] for r in status_rows}

        # 本月新增
        month_start = date.today().replace(day=1).isoformat()
        new_this_month = conn.execute(
            "SELECT COUNT(*) as c FROM customers WHERE created_at >= ?", (month_start,)
        ).fetchone()["c"]

        # 今日联系 - 兼容没有 last_contact 列的情况
        today = date.today().isoformat()
        try:
            today_contacted = conn.execute(
                "SELECT COUNT(*) as c FROM customers WHERE DATE(last_contact) = ?", (today,)
            ).fetchone()["c"]
        except Exception:
            today_contacted = 0

        # 待跟进
        pending_followups = conn.execute(
            "SELECT COUNT(*) as c FROM follow_ups WHERE status = 'pending'"
        ).fetchone()["c"]

        # 已转化
        converted = by_status.get("converted", 0) + by_status.get("已发消息", 0)

    return {
        "total_customers": total,
        "by_status": by_status,
        "new_this_month": new_this_month,
        "today_contacted": today_contacted,
        "pending_followups": pending_followups,
        "converted": converted,
    }


def get_pipeline_summary() -> Dict[str, Any]:
    """获取销售管道概要"""
    stages = ["new", "contacted", "qualified", "proposal", "negotiation", "converted",
              "新线索", "已连接", "已发消息", "已发邮件"]

    pipeline = []
    with get_db_ctx() as conn:
        for stage in stages:
            count = conn.execute(
                "SELECT COUNT(*) as c FROM customers WHERE status = ?", (stage,)
            ).fetchone()["c"]
            if count > 0:
                pipeline.append({"stage": stage, "count": count})

    return {"pipeline": pipeline}


def get_recent_activities(limit: int = 10) -> List[Dict[str, Any]]:
    """获取最近活动"""
    activities = []
    with get_db_ctx() as conn:
        # 最近添加的客户
        rows = conn.execute(
            """SELECT name, company, status, created_at, 'customer' as type
            FROM customers ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        for r in rows:
            activities.append({
                "id": f"customer_{r['name']}",
                "type": "customer",
                "description": f"新客户: {r['name']}" + (f" ({r['company']})" if r["company"] else ""),
                "time": r["created_at"],
                "status": r["status"],
            })

        # 最近跟进
        rows = conn.execute(
            """SELECT f.content, f.created_at, f.status, c.name as customer_name
            FROM follow_ups f
            LEFT JOIN customers c ON f.customer_id = c.id
            ORDER BY f.created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        for r in rows:
            activities.append({
                "id": f"followup_{r['customer_name']}",
                "type": "followup",
                "description": f"跟进 {r['customer_name']}: {r['content'][:50]}",
                "time": r["created_at"],
                "status": r["status"],
            })

    # 按时间排序
    activities.sort(key=lambda x: x.get("time", ""), reverse=True)
    return activities[:limit]


def get_overview() -> Dict[str, Any]:
    """获取总览数据（给 analytics_routes 用）"""
    stats = get_customer_stats()
    pipeline = get_pipeline_summary()
    activities = get_recent_activities(5)
    return {
        "stats": stats,
        "pipeline": pipeline,
        "recent_activities": activities,
    }


def get_funnel() -> Dict[str, Any]:
    """获取转化漏斗"""
    stages_order = ["新线索", "已连接", "已发消息", "已发邮件", "converted"]
    funnel = []
    with get_db_ctx() as conn:
        for stage in stages_order:
            count = conn.execute(
                "SELECT COUNT(*) as c FROM customers WHERE status = ?", (stage,)
            ).fetchone()["c"]
            funnel.append({"stage": stage, "count": count})
    return {"funnel": funnel}
