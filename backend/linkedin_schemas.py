"""
LinkedIn automation schemas — shared Pydantic models for the API.
"""

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
    """LinkedIn search configuration"""
    keywords: str = Field(..., description="Search keywords (company name or job title)")
    market: str = Field("US", description="Target market: US, EU, ME")
    max_results: int = Field(50, ge=1, le=100, description="Max results to return")


class ConnectConfig(BaseModel):
    """Connection request configuration"""
    count: int = Field(5, ge=1, le=20, description="Number of connections to send")
    note: Optional[str] = Field(None, max_length=300, description="Connection request note")
    market: str = Field("US", description="Target market")


class MessageConfig(BaseModel):
    """Message sending configuration"""
    count: int = Field(5, ge=1, le=20, description="Number of messages to send")
    message: Optional[str] = Field(None, max_length=2000, description="Custom message template ({name} placeholder)")


class TaskCreate(BaseModel):
    """Create task request"""
    action: LinkedInAction
    config: Dict[str, Any] = Field(..., description="Action-specific parameters")
    scheduled_at: Optional[datetime] = None


class TaskResponse(BaseModel):
    """Task response"""
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
    """Daily usage quota"""
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
    """LinkedIn search result profile"""
    name: str
    vanity: Optional[str] = None
    url: str
    title: Optional[str] = None
    location: Optional[str] = None
    is_connected: bool = False


class CustomerStats(BaseModel):
    """Customer database stats"""
    total_customers: int = 0
    by_status: Dict[str, int] = {}
    today_new: int = 0
    today_contacted: int = 0


class QuotaItem(BaseModel):
    """Single quota action usage"""
    used: int = 0
    limit: int = 0
    remaining: int = 0


class QuotaResponse(BaseModel):
    """Full daily quota response"""
    date: str
    search: QuotaItem
    connect: QuotaItem
    message: QuotaItem


class LinkedInStatusResponse(BaseModel):
    """Status endpoint response"""
    is_logged_in: bool
    customer_stats: CustomerStats
    error: Optional[str] = None
