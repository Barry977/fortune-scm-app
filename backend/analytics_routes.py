from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional

from backend.auth import get_current_user, get_current_admin
from backend.analytics import (
    get_customer_stats, get_pipeline_summary, get_recent_activities
)
from backend.crm_schemas import CustomerStats, PipelineSummary

router = APIRouter(prefix="/api/analytics", tags=["数据分析"])


@router.get("/overview")
async def get_overview(
    current_user=Depends(get_current_user)
):
    """数据概览"""
    stats = get_customer_stats()
    pipeline = get_pipeline_summary()
    
    return {
        "customers": {
            "total": stats.total_customers,
            "new_this_month": stats.new_this_month,
            "new_this_week": stats.new_this_week,
            "conversion_rate": stats.conversion_rate
        },
        "revenue": {
            "total": stats.total_revenue,
            "total_quotes": stats.total_quotes,
            "total_orders": stats.total_orders
        },
        "pipeline": {
            "total_leads": pipeline.total_leads,
            "total_value": pipeline.total_value,
            "overall_conversion": pipeline.overall_conversion,
            "avg_deal_size": pipeline.avg_deal_size,
            "avg_sales_cycle": pipeline.avg_sales_cycle
        },
        "status_distribution": stats.by_status,
        "source_distribution": stats.by_source,
        "priority_distribution": stats.by_priority,
        "country_distribution": stats.by_country
    }


@router.get("/funnel")
async def get_funnel(
    current_user=Depends(get_current_user)
):
    """转化漏斗"""
    pipeline = get_pipeline_summary()
    return {
        "stages": [
            {
                "stage": stage.stage,
                "count": stage.count,
                "value": stage.value,
                "conversion_rate": stage.conversion_rate,
                "avg_days": stage.avg_days
            }
            for stage in pipeline.stages
        ],
        "summary": {
            "total_leads": pipeline.total_leads,
            "total_value": pipeline.total_value,
            "overall_conversion": pipeline.overall_conversion,
            "avg_deal_size": pipeline.avg_deal_size,
            "avg_sales_cycle": pipeline.avg_sales_cycle
        }
    }


@router.get("/trends")
async def get_trends(
    days: int = 30,
    current_user=Depends(get_current_user)
):
    """趋势数据"""
    # 生成模拟趋势数据（实际应从数据库查询）
    from datetime import datetime, timedelta
    
    trends = []
    for i in range(days):
        date = datetime.utcnow() - timedelta(days=i)
        trends.append({
            "date": date.strftime("%Y-%m-%d"),
            "new_customers": max(0, 5 - i % 7),  # 模拟数据
            "active_customers": max(0, 50 - i),
            "revenue": max(0, 1000 - i * 10),
            "quotes": max(0, 10 - i % 5),
            "followups": max(0, 20 - i % 3)
        })
    
    return {
        "period": f"{days}天",
        "trends": list(reversed(trends))
    }


@router.get("/sources")
async def get_sources(
    current_user=Depends(get_current_user)
):
    """来源分析"""
    stats = get_customer_stats()
    
    source_labels = {
        "linkedin": "LinkedIn",
        "email": "邮件",
        "phone": "电话",
        "website": "网站",
        "referral": "推荐",
        "trade_show": "展会",
        "cold_call": "陌拜",
        "other": "其他"
    }
    
    sources = []
    for source, count in stats.by_source.items():
        sources.append({
            "source": source,
            "label": source_labels.get(source, source),
            "count": count,
            "percentage": round(count / stats.total_customers * 100, 2) if stats.total_customers > 0 else 0
        })
    
    return {
        "sources": sorted(sources, key=lambda x: x["count"], reverse=True),
        "total": stats.total_customers
    }


@router.get("/performance")
async def get_performance(
    current_user=Depends(get_current_user)
):
    """业绩分析"""
    stats = get_customer_stats()
    pipeline = get_pipeline_summary()
    
    return {
        "conversion": {
            "lead_to_contact": pipeline.stages[1].conversion_rate if len(pipeline.stages) > 1 else 0,
            "contact_to_quote": pipeline.stages[2].conversion_rate if len(pipeline.stages) > 2 else 0,
            "quote_to_won": pipeline.stages[4].conversion_rate if len(pipeline.stages) > 4 else 0,
            "overall": pipeline.overall_conversion
        },
        "efficiency": {
            "avg_sales_cycle": pipeline.avg_sales_cycle,
            "avg_deal_size": pipeline.avg_deal_size,
            "quotes_per_customer": round(stats.total_quotes / stats.total_customers, 2) if stats.total_customers > 0 else 0
        },
        "revenue": {
            "total": stats.total_revenue,
            "per_customer": round(stats.total_revenue / stats.total_customers, 2) if stats.total_customers > 0 else 0,
            "per_order": round(stats.total_revenue / stats.total_orders, 2) if stats.total_orders > 0 else 0
        }
    }


@router.get("/activities")
async def get_recent_activities_list(
    limit: int = 20,
    current_user=Depends(get_current_user)
):
    """最近活动"""
    activities = get_recent_activities(limit)
    return {
        "activities": activities,
        "total": len(activities)
    }
