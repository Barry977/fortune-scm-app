from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CustomerCreate(BaseModel):
    name: str
    company: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = "new"
    notes: Optional[str] = None


class Customer(CustomerCreate):
    id: int
    created_at: Optional[str] = None


class MaterialCreate(BaseModel):
    title: str
    content: str
    type: Optional[str] = "text"
    tags: Optional[str] = ""


class Material(MaterialCreate):
    id: int
    created_at: Optional[str] = None


class PostCreate(BaseModel):
    content: str


class Post(BaseModel):
    id: int
    content: str
    status: str
    published_at: Optional[str] = None
    engagement_stats: Optional[str] = "{}"


class LinkedinSearch(BaseModel):
    keywords: str
    location: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    limit: Optional[int] = 25


class LinkedinConnect(BaseModel):
    profile_url: str
    message: Optional[str] = None


class LinkedinMessage(BaseModel):
    profile_url: str
    message: str


class ContentGenerate(BaseModel):
    material_ids: Optional[list[int]] = None
    prompt: Optional[str] = None
    tone: Optional[str] = "professional"
    count: Optional[int] = 1


class EmailConfigure(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_from: str


class EmailSend(BaseModel):
    to: str
    subject: str
    body: str
    html: Optional[bool] = False


class SettingsUpdate(BaseModel):
    ai_provider: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    ai_base_url: Optional[str] = None
    post_time: Optional[str] = None
    post_enabled: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
