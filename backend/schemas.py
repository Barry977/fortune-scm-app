from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    SUBACCOUNT = "subaccount"

class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    role: UserRole = UserRole.SUBACCOUNT
    status: UserStatus = UserStatus.ACTIVE

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    status: Optional[UserStatus] = None

class UserInDB(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None

class UserResponse(UserInDB):
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class TokenPayload(BaseModel):
    sub: Optional[int] = None
    exp: Optional[datetime] = None
    role: Optional[str] = None
