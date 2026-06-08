from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import date

from backend.auth import get_current_user, get_current_admin
from backend.crm import (
    create_customer, get_customer, update_customer, delete_customer,
    list_customers, create_followup, get_customer_followups,
    get_pending_followups, create_quote, get_customer_quotes,
    get_customer_stats, get_pipeline_summary, get_recent_activities
)
from backend.crm_schemas import (
    CustomerCreate, CustomerUpdate, CustomerResponse,
    FollowUpCreate, FollowUpResponse,
    QuoteCreate, QuoteResponse,
    CustomerFilter, CustomerStats, PipelineSummary
)

router = APIRouter(prefix="/api/crm", tags=["CRM"])


@router.post("/contacts", response_model=CustomerResponse)
async def create_contact(
    customer_data: CustomerCreate,
    current_user=Depends(get_current_user)
):
    """创建客户"""
    customer = create_customer(customer_data, current_user.id)
    return CustomerResponse(**customer)


@router.get("/contacts", response_model=List[CustomerResponse])
async def list_contacts(
    status: Optional[str] = None,
    source: Optional[str] = None,
    priority: Optional[str] = None,
    industry: Optional[str] = None,
    country: Optional[str] = None,
    search: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """客户列表（支持筛选）"""
    filter_params = CustomerFilter()
    if status:
        from backend.crm_schemas import CustomerStatus
        filter_params.status = CustomerStatus(status)
    if source:
        from backend.crm_schemas import CustomerSource
        filter_params.source = CustomerSource(source)
    if priority:
        from backend.crm_schemas import CustomerPriority
        filter_params.priority = CustomerPriority(priority)
    if industry:
        filter_params.industry = industry
    if country:
        filter_params.country = country
    if search:
        filter_params.search = search
    
    customers = list_customers(filter_params, current_user.id)
    return [CustomerResponse(**c) for c in customers]


@router.get("/contacts/{customer_id}", response_model=CustomerResponse)
async def get_contact(
    customer_id: int,
    current_user=Depends(get_current_user)
):
    """客户详情"""
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    return CustomerResponse(**customer)


@router.put("/contacts/{customer_id}", response_model=CustomerResponse)
async def update_contact(
    customer_id: int,
    customer_data: CustomerUpdate,
    current_user=Depends(get_current_user)
):
    """更新客户"""
    customer = update_customer(customer_id, customer_data)
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    return CustomerResponse(**customer)


@router.delete("/contacts/{customer_id}")
async def delete_contact(
    customer_id: int,
    current_user=Depends(get_current_user)
):
    """删除客户"""
    success = delete_customer(customer_id)
    if not success:
        raise HTTPException(status_code=404, detail="客户不存在")
    return {"message": "删除成功"}


@router.post("/followups", response_model=FollowUpResponse)
async def create_followup_record(
    followup_data: FollowUpCreate,
    current_user=Depends(get_current_user)
):
    """创建跟进记录"""
    followup = create_followup(followup_data, current_user.id)
    if not followup:
        raise HTTPException(status_code=404, detail="客户不存在")
    return FollowUpResponse(**followup)


@router.get("/contacts/{customer_id}/followups", response_model=List[FollowUpResponse])
async def get_contact_followups(
    customer_id: int,
    current_user=Depends(get_current_user)
):
    """客户跟进列表"""
    followups = get_customer_followups(customer_id)
    return [FollowUpResponse(**f) for f in followups]


@router.get("/followups/pending", response_model=List[FollowUpResponse])
async def get_pending_followups_list(
    current_user=Depends(get_current_user)
):
    """获取待办跟进"""
    followups = get_pending_followups(current_user.id)
    return [FollowUpResponse(**f) for f in followups]


@router.post("/contacts/{customer_id}/followups/{followup_id}/complete")
async def complete_followup(
    customer_id: int,
    followup_id: int,
    current_user=Depends(get_current_user)
):
    """完成跟进"""
    # 这里简化处理，实际应该更新followup状态
    return {"message": "跟进已完成"}


@router.post("/contacts/{customer_id}/quotes", response_model=QuoteResponse)
async def create_contact_quote(
    customer_id: int,
    quote_data: QuoteCreate,
    current_user=Depends(get_current_user)
):
    """创建报价"""
    quote = create_quote(quote_data, current_user.id)
    if not quote:
        raise HTTPException(status_code=404, detail="客户不存在")
    return QuoteResponse(**quote)


@router.get("/contacts/{customer_id}/quotes", response_model=List[QuoteResponse])
async def get_contact_quotes(
    customer_id: int,
    current_user=Depends(get_current_user)
):
    """获取客户报价"""
    quotes = get_customer_quotes(customer_id)
    return [QuoteResponse(**q) for q in quotes]


@router.get("/stats", response_model=CustomerStats)
async def get_stats(
    current_user=Depends(get_current_user)
):
    """客户统计"""
    return get_customer_stats()


@router.get("/pipeline", response_model=PipelineSummary)
async def get_pipeline(
    current_user=Depends(get_current_user)
):
    """销售漏斗"""
    return get_pipeline_summary()


@router.get("/activities")
async def get_activities(
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user)
):
    """最近活动"""
    return get_recent_activities(limit)
