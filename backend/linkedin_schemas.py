from typing import Optional, Dict, List, Any
from datetime import datetime, date
from pydantic import BaseModel, Field
from enum import Enum

class LinkedInAction(str, Enum):
    SEARCH = "search"
    CONNECT = "connect"
    MESSAGE = "message"

class LinkedInStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class SearchConfig(BaseModel):
    """LinkedIn搜索配置"""
    keywords: str = Field(..., description="搜索关键词，如公司名称或职位")
    location: Optional[str] = Field(None, description="地理位置筛选")
    industry: Optional[str] = Field(None, description="行业筛选")
    company_size: Optional[str] = Field(None, description="公司规模")
    max_results: int = Field(50, ge=1, le=100, description="最大结果数")

class ConnectConfig(BaseModel):
    """加好友配置"""
    profile_urls: List[str] = Field(..., description="目标个人主页URL列表")
    note: Optional[str] = Field(None, max_length=300, description="好友请求附言")
    max_daily: int = Field(20, ge=1, le=50, description="每日加好友上限")

class MessageConfig(BaseModel):
    """发消息配置"""
    connection_ids: List[str] = Field(..., description="已连接好友ID列表")
    message: str = Field(..., max_length=2000, description="消息内容")
    max_daily: int = Field(50, ge=1, le=100, description="每日发消息上限")

class TaskCreate(BaseModel):
    """创建任务请求"""
    action: LinkedInAction
    config: Dict[str, Any] = Field(..., description="具体配置参数")
    scheduled_at: Optional[datetime] = None

class TaskResponse(BaseModel):
    """任务响应"""
    id: str
    action: LinkedInAction
    status: LinkedInStatus
    config: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DailyQuota(BaseModel):
    """每日额度"""
    date: date
    search_count: int = 0
    search_limit: int = 100
    connect_count: int = 0
    connect_limit: int = 20
    message_count: int = 0
    message_limit: int = 50
    
    @property
    def search_remaining(self) -> int:
        return max(0, self.search_limit - self.search_count)
    
    @property
    def connect_remaining(self) -> int:
        return max(0, self.connect_limit - self.connect_count)
    
    @property
    def message_remaining(self) -> int:
        return max(0, self.message_limit - self.message_count)

class LinkedInProfile(BaseModel):
    """LinkedIn个人资料"""
    linkedin_id: Optional[str] = None
    name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    company: Optional[str] = None
    profile_url: str
    is_connected: bool = False
    connection_degree: Optional[str] = None  # "1st", "2nd", "3rd"
    notes: Optional[str] = None
