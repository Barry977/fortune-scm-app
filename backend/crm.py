from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
import json

from backend.crm_schemas import (
    CustomerCreate, CustomerUpdate, CustomerInDB, CustomerResponse,
    FollowUpCreate, FollowUpInDB, FollowUpResponse,
    QuoteCreate, QuoteInDB, QuoteResponse,
    CustomerFilter, CustomerStats, PipelineStage, PipelineSummary,
    CustomerStatus, CustomerSource, CustomerPriority
)

# 内存数据库
_customers_db: Dict[int, dict] = {}
_followups_db: Dict[int, dict] = {}
_quotes_db: Dict[int, dict] = {}

_customer_id_counter = 0
_followup_id_counter = 0
_quote_id_counter = 0

def _get_next_customer_id() -> int:
    global _customer_id_counter
    _customer_id_counter += 1
    return _customer_id_counter

def _get_next_followup_id() -> int:
    global _followup_id_counter
    _followup_id_counter += 1
    return _followup_id_counter

def _get_next_quote_id() -> int:
    global _quote_id_counter
    _quote_id_counter += 1
    return _quote_id_counter

# ========== 客户管理 ==========

def create_customer(customer_data: CustomerCreate, created_by: int) -> dict:
    """创建客户"""
    customer_id = _get_next_customer_id()
    now = datetime.utcnow()
    
    customer = {
        "id": customer_id,
        "name": customer_data.name,
        "company": customer_data.company,
        "email": customer_data.email,
        "phone": customer_data.phone,
        "country": customer_data.country,
        "city": customer_data.city,
        "industry": customer_data.industry,
        "source": customer_data.source.value,
        "status": customer_data.status.value,
        "priority": customer_data.priority.value,
        "tags": customer_data.tags or [],
        "notes": customer_data.notes,
        "assigned_to": customer_data.assigned_to,
        "linkedin_url": customer_data.linkedin_url,
        "website": customer_data.website,
        "created_at": now,
        "updated_at": now,
        "created_by": created_by,
        "last_contact_at": None,
        "total_quotes": 0,
        "total_orders": 0,
        "total_revenue": 0.0
    }
    
    _customers_db[customer_id] = customer
    return customer

def get_customer(customer_id: int) -> Optional[dict]:
    """获取客户"""
    return _customers_db.get(customer_id)

def update_customer(customer_id: int, customer_data: CustomerUpdate) -> Optional[dict]:
    """更新客户"""
    customer = _customers_db.get(customer_id)
    if not customer:
        return None
    
    update_data = customer_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            if hasattr(value, 'value'):
                customer[key] = value.value
            else:
                customer[key] = value
    
    customer["updated_at"] = datetime.utcnow()
    return customer

def delete_customer(customer_id: int) -> bool:
    """删除客户"""
    if customer_id not in _customers_db:
        return False
    
    # 删除相关跟进记录和报价
    followups_to_delete = [fid for fid, f in _followups_db.items() if f["customer_id"] == customer_id]
    for fid in followups_to_delete:
        del _followups_db[fid]
    
    quotes_to_delete = [qid for qid, q in _quotes_db.items() if q["customer_id"] == customer_id]
    for qid in quotes_to_delete:
        del _quotes_db[qid]
    
    del _customers_db[customer_id]
    return True

def list_customers(filter_params: Optional[CustomerFilter] = None, user_id: Optional[int] = None) -> List[dict]:
    """列出客户"""
    customers = list(_customers_db.values())
    
    # 非管理员只能看到分配给自己的客户
    if user_id is not None:
        customers = [c for c in customers if c["assigned_to"] == user_id or c["created_by"] == user_id]
    
    if filter_params:
        if filter_params.status:
            customers = [c for c in customers if c["status"] == filter_params.status.value]
        if filter_params.source:
            customers = [c for c in customers if c["source"] == filter_params.source.value]
        if filter_params.priority:
            customers = [c for c in customers if c["priority"] == filter_params.priority.value]
        if filter_params.industry:
            customers = [c for c in customers if c["industry"] == filter_params.industry]
        if filter_params.country:
            customers = [c for c in customers if c["country"] == filter_params.country]
        if filter_params.assigned_to:
            customers = [c for c in customers if c["assigned_to"] == filter_params.assigned_to]
        if filter_params.tags:
            customers = [c for c in customers if any(tag in c.get("tags", []) for tag in filter_params.tags)]
        if filter_params.created_after:
            customers = [c for c in customers if c["created_at"].date() >= filter_params.created_after]
        if filter_params.created_before:
            customers = [c for c in customers if c["created_at"].date() <= filter_params.created_before]
        if filter_params.search:
            search = filter_params.search.lower()
            customers = [c for c in customers if 
                        search in c["name"].lower() or 
                        search in (c.get("company") or "").lower() or
                        search in (c.get("email") or "").lower()]
    
    # 按优先级和更新时间排序
    priority_order = {"high": 0, "medium": 1, "low": 2}
    customers.sort(key=lambda c: (priority_order.get(c["priority"], 1), c["updated_at"]), reverse=True)
    
    return customers

# ========== 跟进记录 ==========

def create_followup(followup_data: FollowUpCreate, created_by: int) -> dict:
    """创建跟进记录"""
    # 检查客户是否存在
    if followup_data.customer_id not in _customers_db:
        return None
    
    followup_id = _get_next_followup_id()
    now = datetime.utcnow()
    
    followup = {
        "id": followup_id,
        "customer_id": followup_data.customer_id,
        "type": followup_data.type.value,
        "content": followup_data.content,
        "scheduled_at": followup_data.scheduled_at,
        "completed_at": followup_data.completed_at,
        "outcome": followup_data.outcome,
        "next_action": followup_data.next_action,
        "next_action_date": followup_data.next_action_date,
        "created_at": now,
        "created_by": created_by
    }
    
    _followups_db[followup_id] = followup
    
    # 更新客户最后联系时间
    _customers_db[followup_data.customer_id]["last_contact_at"] = now
    _customers_db[followup_data.customer_id]["updated_at"] = now
    
    return followup

def get_customer_followups(customer_id: int) -> List[dict]:
    """获取客户的跟进记录"""
    followups = [f for f in _followups_db.values() if f["customer_id"] == customer_id]
    followups.sort(key=lambda f: f["created_at"], reverse=True)
    return followups

def get_pending_followups(user_id: Optional[int] = None) -> List[dict]:
    """获取待办跟进"""
    now = datetime.utcnow()
    
    # 获取有scheduled_at且未完成的跟进
    pending = [f for f in _followups_db.values() 
               if f["scheduled_at"] and not f["completed_at"] and f["scheduled_at"] >= now]
    
    # 获取next_action_date在今天或之前的跟进
    today = date.today()
    action_pending = [f for f in _followups_db.values()
                     if f["next_action_date"] and f["next_action_date"] <= today and not f["completed_at"]]
    
    # 合并去重
    all_pending = {f["id"]: f for f in pending + action_pending}
    
    # 过滤用户
    if user_id:
        result = []
        for f in all_pending.values():
            customer = _customers_db.get(f["customer_id"])
            if customer and (customer["assigned_to"] == user_id or customer["created_by"] == user_id):
                result.append(f)
        return sorted(result, key=lambda f: f.get("scheduled_at") or f.get("next_action_date") or datetime.min)
    
    return sorted(all_pending.values(), key=lambda f: f.get("scheduled_at") or f.get("next_action_date") or datetime.min)

# ========== 报价管理 ==========

def create_quote(quote_data: QuoteCreate, created_by: int) -> dict:
    """创建报价"""
    if quote_data.customer_id not in _customers_db:
        return None
    
    quote_id = _get_next_quote_id()
    now = datetime.utcnow()
    
    # 计算金额
    subtotal = sum(item.unit_price * item.quantity for item in quote_data.items)
    tax_amount = subtotal * (quote_data.tax_rate / 100)
    total = subtotal + tax_amount
    
    # 更新item totals
    items = []
    for item in quote_data.items:
        items.append({
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total": item.quantity * item.unit_price
        })
    
    quote = {
        "id": quote_id,
        "customer_id": quote_data.customer_id,
        "quote_number": quote_data.quote_number,
        "items": items,
        "currency": quote_data.currency,
        "subtotal": subtotal,
        "tax_rate": quote_data.tax_rate,
        "tax_amount": tax_amount,
        "total": total,
        "valid_until": quote_data.valid_until,
        "notes": quote_data.notes,
        "status": quote_data.status,
        "created_at": now,
        "updated_at": now,
        "created_by": created_by
    }
    
    _quotes_db[quote_id] = quote
    
    # 更新客户统计
    _customers_db[quote_data.customer_id]["total_quotes"] += 1
    _customers_db[quote_data.customer_id]["updated_at"] = now
    
    return quote

def get_customer_quotes(customer_id: int) -> List[dict]:
    """获取客户报价"""
    quotes = [q for q in _quotes_db.values() if q["customer_id"] == customer_id]
    quotes.sort(key=lambda q: q["created_at"], reverse=True)
    return quotes

# ========== 统计报表 ==========

def get_customer_stats() -> CustomerStats:
    """获取客户统计"""
    customers = list(_customers_db.values())
    
    by_status = defaultdict(int)
    by_source = defaultdict(int)
    by_priority = defaultdict(int)
    by_country = defaultdict(int)
    
    now = datetime.utcnow()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_week_start = now - timedelta(days=now.weekday())
    this_week_start = this_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    new_this_month = 0
    new_this_week = 0
    total_revenue = 0.0
    total_quotes = 0
    total_orders = 0
    
    for c in customers:
        by_status[c["status"]] += 1
        by_source[c["source"]] += 1
        by_priority[c["priority"]] += 1
        if c["country"]:
            by_country[c["country"]] += 1
        
        if c["created_at"] >= this_month_start:
            new_this_month += 1
        if c["created_at"] >= this_week_start:
            new_this_week += 1
        
        total_revenue += c.get("total_revenue", 0)
        total_quotes += c.get("total_quotes", 0)
        total_orders += c.get("total_orders", 0)
    
    # 计算转化率
    total_leads = len(customers)
    won = by_status.get("won", 0)
    conversion_rate = (won / total_leads * 100) if total_leads > 0 else 0
    
    return CustomerStats(
        total_customers=len(customers),
        by_status=dict(by_status),
        by_source=dict(by_source),
        by_priority=dict(by_priority),
        by_country=dict(by_country),
        new_this_month=new_this_month,
        new_this_week=new_this_week,
        conversion_rate=round(conversion_rate, 2),
        total_revenue=round(total_revenue, 2),
        total_quotes=total_quotes,
        total_orders=total_orders
    )

def get_pipeline_summary() -> PipelineSummary:
    """获取销售漏斗"""
    customers = list(_customers_db.values())
    
    stages = [
        {"stage": "lead", "label": "潜在客户"},
        {"stage": "contacted", "label": "已联系"},
        {"stage": "quoted", "label": "已报价"},
        {"stage": "negotiating", "label": "谈判中"},
        {"stage": "won", "label": "成交"},
        {"stage": "lost", "label": "流失"}
    ]
    
    pipeline_stages = []
    total_value = 0.0
    
    for stage_info in stages:
        stage = stage_info["stage"]
        stage_customers = [c for c in customers if c["status"] == stage]
        count = len(stage_customers)
        value = sum(c.get("total_revenue", 0) for c in stage_customers)
        
        # 计算转化率（相对于前一阶段）
        prev_stage_idx = stages.index(stage_info) - 1
        if prev_stage_idx >= 0:
            prev_stage = stages[prev_stage_idx]["stage"]
            prev_count = len([c for c in customers if c["status"] == prev_stage])
            conversion = (count / prev_count * 100) if prev_count > 0 else 0
        else:
            conversion = 100.0
        
        # 计算平均停留天数
        avg_days = 0.0
        if stage_customers:
            days = [(datetime.utcnow() - c["created_at"]).days for c in stage_customers]
            avg_days = sum(days) / len(days)
        
        pipeline_stages.append(PipelineStage(
            stage=stage_info["label"],
            count=count,
            value=round(value, 2),
            conversion_rate=round(conversion, 2),
            avg_days=round(avg_days, 1)
        ))
        
        total_value += value
    
    total_leads = len(customers)
    won = len([c for c in customers if c["status"] == "won"])
    overall_conversion = (won / total_leads * 100) if total_leads > 0 else 0
    
    won_customers = [c for c in customers if c["status"] == "won"]
    avg_deal_size = (total_value / len(won_customers)) if won_customers else 0
    
    # 计算平均销售周期
    sales_cycles = []
    for c in won_customers:
        # 简化为从创建到成交的天数
        # 实际应该用第一次接触到成交的时间
        days = (datetime.utcnow() - c["created_at"]).days
        sales_cycles.append(days)
    avg_sales_cycle = sum(sales_cycles) / len(sales_cycles) if sales_cycles else 0
    
    return PipelineSummary(
        stages=pipeline_stages,
        total_leads=total_leads,
        total_value=round(total_value, 2),
        overall_conversion=round(overall_conversion, 2),
        avg_deal_size=round(avg_deal_size, 2),
        avg_sales_cycle=round(avg_sales_cycle, 1)
    )

def get_recent_activities(limit: int = 20) -> List[Dict]:
    """获取最近活动"""
    activities = []
    
    # 客户创建
    for c in _customers_db.values():
        activities.append({
            "type": "customer_created",
            "description": f"创建客户: {c['name']}",
            "timestamp": c["created_at"],
            "customer_id": c["id"],
            "user_id": c["created_by"]
        })
    
    # 跟进记录
    for f in _followups_db.values():
        activities.append({
            "type": "followup",
            "description": f"跟进: {f['type']}",
            "timestamp": f["created_at"],
            "customer_id": f["customer_id"],
            "user_id": f["created_by"]
        })
    
    # 报价创建
    for q in _quotes_db.values():
        activities.append({
            "type": "quote_created",
            "description": f"创建报价: {q['quote_number']}",
            "timestamp": q["created_at"],
            "customer_id": q["customer_id"],
            "user_id": q["created_by"]
        })
    
    activities.sort(key=lambda a: a["timestamp"], reverse=True)
    return activities[:limit]
