from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class CustomerStatus(str, Enum):
    LEAD = "lead"           # 潜在客户
    CONTACTED = "contacted" # 已联系
    QUOTED = "quoted"       # 已报价
    NEGOTIATING = "negotiating" # 谈判中
    WON = "won"             # 成交
    LOST = "lost"           # 流失
    HOLD = "hold"           # 搁置

class CustomerSource(str, Enum):
    LINKEDIN = "linkedin"
    EMAIL = "email"
    PHONE = "phone"
    WEBSITE = "website"
    REFERRAL = "referral"
    TRADE_SHOW = "trade_show"
    COLD_CALL = "cold_call"
    OTHER = "other"

class CustomerPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class CustomerBase(BaseModel):
    """客户基础信息"""
    name: str = Field(..., min_length=1, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    country: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    industry: Optional[str] = Field(None, max_length=50)
    source: CustomerSource = CustomerSource.OTHER
    status: CustomerStatus = CustomerStatus.LEAD
    priority: CustomerPriority = CustomerPriority.MEDIUM
    tags: Optional[List[str]] = Field(None)
    notes: Optional[str] = Field(None, max_length=2000)
    assigned_to: Optional[int] = Field(None, description="分配给的子账号ID")
    linkedin_url: Optional[str] = Field(None)
    website: Optional[str] = Field(None)

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    country: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    industry: Optional[str] = Field(None, max_length=50)
    source: Optional[CustomerSource] = None
    status: Optional[CustomerStatus] = None
    priority: Optional[CustomerPriority] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = Field(None, max_length=2000)
    assigned_to: Optional[int] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None

class CustomerInDB(CustomerBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: int
    last_contact_at: Optional[datetime] = None
    total_quotes: int = 0
    total_orders: int = 0
    total_revenue: float = 0.0

class CustomerResponse(CustomerInDB):
    class Config:
        from_attributes = True

class FollowUpType(str, Enum):
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    LINKEDIN = "linkedin"
    QUOTE = "quote"
    NOTE = "note"
    OTHER = "other"

class FollowUpBase(BaseModel):
    customer_id: int
    type: FollowUpType
    content: str = Field(..., max_length=5000)
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    outcome: Optional[str] = Field(None, max_length=500)
    next_action: Optional[str] = Field(None, max_length=500)
    next_action_date: Optional[date] = None

class FollowUpCreate(FollowUpBase):
    pass

class FollowUpInDB(FollowUpBase):
    id: int
    created_at: datetime
    created_by: int

class FollowUpResponse(FollowUpInDB):
    class Config:
        from_attributes = True

class QuoteItem(BaseModel):
    description: str
    quantity: int = Field(1, ge=1)
    unit_price: float = Field(..., ge=0)
    total: float = 0.0

class QuoteBase(BaseModel):
    customer_id: int
    quote_number: str = Field(..., max_length=50)
    items: List[QuoteItem]
    currency: str = Field("USD", max_length=3)
    subtotal: float = 0.0
    tax_rate: float = Field(0.0, ge=0, le=100)
    tax_amount: float = 0.0
    total: float = 0.0
    valid_until: Optional[date] = None
    notes: Optional[str] = None
    status: str = Field("draft", max_length=20)  # draft/sent/accepted/rejected/expired

class QuoteCreate(QuoteBase):
    pass

class QuoteInDB(QuoteBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: int

class QuoteResponse(QuoteInDB):
    class Config:
        from_attributes = True

class CustomerFilter(BaseModel):
    """客户筛选条件"""
    status: Optional[CustomerStatus] = None
    source: Optional[CustomerSource] = None
    priority: Optional[CustomerPriority] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    assigned_to: Optional[int] = None
    tags: Optional[List[str]] = None
    created_after: Optional[date] = None
    created_before: Optional[date] = None
    search: Optional[str] = None

class CustomerStats(BaseModel):
    """客户统计"""
    total_customers: int
    by_status: Dict[str, int]
    by_source: Dict[str, int]
    by_priority: Dict[str, int]
    by_country: Dict[str, int]
    new_this_month: int
    new_this_week: int
    conversion_rate: float
    total_revenue: float
    total_quotes: int
    total_orders: int

class PipelineStage(BaseModel):
    """销售漏斗阶段"""
    stage: str
    count: int
    value: float
    conversion_rate: float
    avg_days: float

class PipelineSummary(BaseModel):
    """销售漏斗汇总"""
    stages: List[PipelineStage]
    total_leads: int
    total_value: float
    overall_conversion: float
    avg_deal_size: float
    avg_sales_cycle: float
