from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
import sqlite3
import os
import json
import re

# 配置
SECRET_KEY = "fortune-scm-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# 角色枚举
class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"
    VIEWER = "viewer"

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

app = FastAPI(title="Fortune SCM 客户开发系统")

# 静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "fortune_scm.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 用户表 - 使用 role 字段
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'sales',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 检查旧表结构，如果有 is_admin 字段则迁移
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'is_admin' in columns and 'role' not in columns:
        # 迁移：is_admin -> role
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'sales'")
        cursor.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
        cursor.execute("UPDATE users SET role = 'sales' WHERE is_admin = 0 OR is_admin IS NULL")
    
    conn.commit()
    
    # 创建默认管理员账号
    admin_password = pwd_context.hash("admin123")
    cursor.execute("""
        INSERT OR IGNORE INTO users (username, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, ("admin", "admin@fortune-scm.com", admin_password, "admin"))
    
    conn.commit()
    conn.close()


# 初始化数据库
init_db()


# ============ Pydantic 模型 ============

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.SALES


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserPasswordUpdate(BaseModel):
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class CustomerCreate(BaseModel):
    name: str
    company: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None


class AIConfigCreate(BaseModel):
    provider: str
    model_name: str
    api_key: str
    base_url: Optional[str] = None


class EmailConfigCreate(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    use_tls: bool = True
    from_name: Optional[str] = None
    from_email: Optional[str] = None


class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body: str
    variables: Optional[str] = None


class FollowUpCreate(BaseModel):
    customer_id: int
    content: str
    follow_up_date: Optional[str] = None


# ============ 辅助函数 ============

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    return dict(user)


def get_current_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def get_current_manager_or_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or admin access required")
    return current_user


def check_user_permission(current_user: dict, target_user_id: int):
    """检查当前用户是否有权限操作目标用户的数据"""
    if current_user.get("role") == "admin":
        return True
    if current_user.get("id") == target_user_id:
        return True
    return False


# ============ 页面路由 ============

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/users")
async def users_page(request: Request):
    return templates.TemplateResponse("users.html", {"request": request})


# ============ 认证路由 ============

@app.post("/api/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (user_data.username,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not verify_password(user_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    if not user["is_active"]:
        raise HTTPException(status_code=401, detail="User is disabled")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["id"]), "role": user["role"]}, 
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "email": current_user["email"],
        "role": current_user["role"],
        "is_active": current_user["is_active"]
    }


@app.post("/api/auth/refresh")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """刷新 JWT Token"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(current_user["id"]), "role": current_user["role"]}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/auth/change-password")
async def change_password(
    password_data: UserPasswordUpdate,
    current_user: dict = Depends(get_current_user)
):
    """修改当前用户密码"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    new_password_hash = get_password_hash(password_data.password)
    cursor.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_password_hash, current_user["id"])
    )
    conn.commit()
    conn.close()
    
    return {"message": "Password changed successfully"}


# ============ 用户管理路由（管理员权限） ============

@app.post("/api/users")
async def create_user(user: UserCreate, current_user: dict = Depends(get_current_admin)):
    """创建子账号（仅管理员）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 验证用户名格式
    if not re.match(r'^[a-zA-Z0-9_]{3,50}$', user.username):
        conn.close()
        raise HTTPException(status_code=400, detail="Username must be 3-50 characters, alphanumeric and underscore only")
    
    # 检查用户名是否已存在
    cursor.execute("SELECT id FROM users WHERE username = ?", (user.username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # 检查邮箱是否已存在（如果提供了邮箱）
    if user.email:
        cursor.execute("SELECT id FROM users WHERE email = ?", (user.email,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Email already exists")
    
    password_hash = get_password_hash(user.password)
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, role, is_active)
        VALUES (?, ?, ?, ?, ?)
    """, (user.username, user.email, password_hash, user.role.value, True))
    
    conn.commit()
    user_id = cursor.lastrowid
    
    # 获取创建的用户信息
    cursor.execute("SELECT id, username, email, role, is_active, created_at FROM users WHERE id = ?", (user_id,))
    new_user = cursor.fetchone()
    conn.close()
    
    return {
        "id": new_user["id"],
        "username": new_user["username"],
        "email": new_user["email"],
        "role": new_user["role"],
        "is_active": new_user["is_active"],
        "created_at": new_user["created_at"],
        "message": "User created successfully"
    }


@app.get("/api/users")
async def list_users(current_user: dict = Depends(get_current_admin)):
    """列出所有用户（仅管理员）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, role, is_active, created_at, updated_at 
        FROM users 
        ORDER BY created_at DESC
    """)
    users = cursor.fetchall()
    conn.close()
    
    return {"users": [dict(user) for user in users]}


@app.get("/api/users/{user_id}")
async def get_user(user_id: int, current_user: dict = Depends(get_current_user)):
    """获取单个用户信息"""
    # 只有管理员或用户本人可以查看
    if not check_user_permission(current_user, user_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, role, is_active, created_at, updated_at 
        FROM users WHERE id = ?
    """, (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return dict(user)


@app.put("/api/users/{user_id}")
async def update_user(
    user_id: int, 
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """更新用户信息（仅管理员）"""
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot modify yourself via this endpoint")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查用户是否存在
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    # 构建更新字段
    updates = []
    params = []
    
    if user_update.email is not None:
        # 检查邮箱是否已被其他用户使用
        cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?", (user_update.email, user_id))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Email already exists")
        updates.append("email = ?")
        params.append(user_update.email)
    
    if user_update.role is not None:
        updates.append("role = ?")
        params.append(user_update.role.value)
    
    if user_update.is_active is not None:
        updates.append("is_active = ?")
        params.append(user_update.is_active)
    
    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="No fields to update")
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(user_id)
    
    cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    
    # 获取更新后的用户信息
    cursor.execute("""
        SELECT id, username, email, role, is_active, created_at, updated_at 
        FROM users WHERE id = ?
    """, (user_id,))
    updated_user = cursor.fetchone()
    conn.close()
    
    return {
        "user": dict(updated_user),
        "message": "User updated successfully"
    }


@app.put("/api/users/{user_id}/password")
async def reset_user_password(
    user_id: int,
    password_data: UserPasswordUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """重置用户密码（仅管理员）"""
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Use /api/auth/change-password to change your own password")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    new_password_hash = get_password_hash(password_data.password)
    cursor.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_password_hash, user_id)
    )
    conn.commit()
    conn.close()
    
    return {"message": "Password reset successfully"}


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, current_user: dict = Depends(get_current_admin)):
    """删除用户（仅管理员）"""
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查用户是否存在
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    # 删除用户（关联数据由外键约束处理，或手动清理）
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    return {"message": "User deleted successfully"}


@app.put("/api/users/{user_id}/toggle")
async def toggle_user_status(user_id: int, current_user: dict = Depends(get_current_admin)):
    """切换用户启用/禁用状态（仅管理员）"""
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot disable yourself")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    new_status = not user["is_active"]
    cursor.execute(
        "UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, user_id)
    )
    conn.commit()
    conn.close()
    
    return {
        "message": f"User {'enabled' if new_status else 'disabled'} successfully",
        "is_active": new_status
    }


# ============ 客户管理路由 ============

@app.post("/api/customers")
async def create_customer(customer: CustomerCreate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO customers (user_id, name, company, title, email, phone, linkedin_url, tags, notes, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (current_user["id"], customer.name, customer.company, customer.title,
          customer.email, customer.phone, customer.linkedin_url, customer.tags,
          customer.notes, customer.source))
    conn.commit()
    customer_id = cursor.lastrowid
    conn.close()
    
    return {"id": customer_id, "message": "Customer created successfully"}


@app.get("/api/customers")
async def list_customers(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if current_user["role"] == "admin":
        cursor.execute("SELECT * FROM customers ORDER BY created_at DESC")
    else:
        cursor.execute("SELECT * FROM customers WHERE user_id = ? ORDER BY created_at DESC", (current_user["id"],))
    
    customers = cursor.fetchall()
    conn.close()
    
    return {"customers": [dict(customer) for customer in customers]}


@app.get("/api/customers/{customer_id}")
async def get_customer(customer_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    customer = cursor.fetchone()
    conn.close()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if current_user["role"] != "admin" and customer["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return dict(customer)


@app.put("/api/customers/{customer_id}")
async def update_customer(customer_id: int, customer: CustomerCreate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if current_user["role"] != "admin" and existing["user_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Access denied")
    
    cursor.execute("""
        UPDATE customers SET name = ?, company = ?, title = ?, email = ?, phone = ?,
        linkedin_url = ?, tags = ?, notes = ?, source = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (customer.name, customer.company, customer.title, customer.email,
          customer.phone, customer.linkedin_url, customer.tags, customer.notes,
          customer.source, customer_id))
    conn.commit()
    conn.close()
    
    return {"message": "Customer updated successfully"}


@app.delete("/api/customers/{customer_id}")
async def delete_customer(customer_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if current_user["role"] != "admin" and existing["user_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Access denied")
    
    cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    
    return {"message": "Customer deleted successfully"}


# ============ AI 配置路由 ============

@app.post("/api/ai-configs")
async def create_ai_config(config: AIConfigCreate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ai_configs (user_id, provider, model_name, api_key, base_url)
        VALUES (?, ?, ?, ?, ?)
    """, (current_user["id"], config.provider, config.model_name, config.api_key, config.base_url))
    conn.commit()
    config_id = cursor.lastrowid
    conn.close()
    
    return {"id": config_id, "message": "AI config created successfully"}


@app.get("/api/ai-configs")
async def list_ai_configs(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, provider, model_name, base_url, is_active, created_at 
        FROM ai_configs WHERE user_id = ?
    """, (current_user["id"],))
    configs = cursor.fetchall()
    conn.close()
    
    return {"configs": [dict(config) for config in configs]}


# ============ 邮件配置路由 ============

@app.post("/api/email-configs")
async def create_email_config(config: EmailConfigCreate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO email_configs (user_id, smtp_host, smtp_port, smtp_user, smtp_password, use_tls, from_name, from_email)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (current_user["id"], config.smtp_host, config.smtp_port, config.smtp_user,
          config.smtp_password, config.use_tls, config.from_name, config.from_email))
    conn.commit()
    config_id = cursor.lastrowid
    conn.close()
    
    return {"id": config_id, "message": "Email config created successfully"}


@app.get("/api/email-configs")
async def list_email_configs(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, smtp_host, smtp_port, smtp_user, use_tls, from_name, from_email, is_active, created_at 
        FROM email_configs WHERE user_id = ?
    """, (current_user["id"],))
    configs = cursor.fetchall()
    conn.close()
    
    return {"configs": [dict(config) for config in configs]}


# ============ 邮件模板路由 ============

@app.post("/api/email-templates")
async def create_email_template(template: EmailTemplateCreate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO email_templates (user_id, name, subject, body, variables)
        VALUES (?, ?, ?, ?, ?)
    """, (current_user["id"], template.name, template.subject, template.body, template.variables))
    conn.commit()
    template_id = cursor.lastrowid
    conn.close()
    
    return {"id": template_id, "message": "Email template created successfully"}


@app.get("/api/email-templates")
async def list_email_templates(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM email_templates WHERE user_id = ?", (current_user["id"],))
    templates_list = cursor.fetchall()
    conn.close()
    
    return {"templates": [dict(template) for template in templates_list]}


# ============ 跟进记录路由 ============

@app.post("/api/follow-ups")
async def create_follow_up(follow_up: FollowUpCreate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO follow_ups (user_id, customer_id, content, follow_up_date, status)
        VALUES (?, ?, ?, ?, ?)
    """, (current_user["id"], follow_up.customer_id, follow_up.content,
          follow_up.follow_up_date, "pending"))
    conn.commit()
    follow_up_id = cursor.lastrowid
    conn.close()
    
    return {"id": follow_up_id, "message": "Follow-up created successfully"}


@app.get("/api/follow-ups")
async def list_follow_ups(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.*, c.name as customer_name 
        FROM follow_ups f
        JOIN customers c ON f.customer_id = c.id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC
    """, (current_user["id"],))
    follow_ups = cursor.fetchall()
    conn.close()
    
    return {"follow_ups": [dict(follow_up) for follow_up in follow_ups]}


# ============ 分析数据路由 ============

@app.get("/api/analytics/summary")
async def get_analytics_summary(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    user_filter = "" if current_user["role"] == "admin" else "AND user_id = ?"
    params = [] if current_user["role"] == "admin" else [current_user["id"]]
    
    # 客户统计
    cursor.execute(f"SELECT COUNT(*) as total FROM customers WHERE 1=1 {user_filter}", params)
    total_customers = cursor.fetchone()["total"]
    
    cursor.execute(f"SELECT COUNT(*) as new FROM customers WHERE status = 'new' {user_filter}", params)
    new_customers = cursor.fetchone()["new"]
    
    cursor.execute(f"SELECT COUNT(*) as contacted FROM customers WHERE status = 'contacted' {user_filter}", params)
    contacted_customers = cursor.fetchone()["contacted"]
    
    cursor.execute(f"SELECT COUNT(*) as converted FROM customers WHERE status = 'converted' {user_filter}", params)
    converted_customers = cursor.fetchone()["converted"]
    
    # 跟进统计
    cursor.execute(f"SELECT COUNT(*) as total FROM follow_ups WHERE 1=1 {user_filter}", params)
    total_follow_ups = cursor.fetchone()["total"]
    
    cursor.execute(f"SELECT COUNT(*) as pending FROM follow_ups WHERE status = 'pending' {user_filter}", params)
    pending_follow_ups = cursor.fetchone()["pending"]
    
    conn.close()
    
    return {
        "customers": {
            "total": total_customers,
            "new": new_customers,
            "contacted": contacted_customers,
            "converted": converted_customers
        },
        "follow_ups": {
            "total": total_follow_ups,
            "pending": pending_follow_ups
        }
    }


@app.get("/api/analytics/funnel")
async def get_conversion_funnel(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    user_filter = "" if current_user["role"] == "admin" else "AND user_id = ?"
    params = [] if current_user["role"] == "admin" else [current_user["id"]]
    
    statuses = ["new", "contacted", "qualified", "proposal", "negotiation", "converted"]
    funnel = []
    
    for status in statuses:
        cursor.execute(f"SELECT COUNT(*) as count FROM customers WHERE status = ? {user_filter}", [status] + params)
        count = cursor.fetchone()["count"]
        funnel.append({"status": status, "count": count})
    
    conn.close()
    
    return {"funnel": funnel}


# ============ 健康检查 ============

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
