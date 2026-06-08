from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from datetime import timedelta
from pathlib import Path
import os

from backend.schemas import (
    UserCreate, UserUpdate, UserResponse, UserLogin, Token,
    UserRole, UserStatus
)
from backend.auth import (
    init_admin_user, verify_password, create_access_token,
    get_current_user, get_current_admin, get_user_by_username,
    create_user, update_user, delete_user, list_users,
    ACCESS_TOKEN_EXPIRE_MINUTES, _users_db
)

# 导入各模块路由
from backend.linkedin_routes import router as linkedin_router
from backend.ai_config_routes import router as ai_config_router
from backend.crm_routes import router as crm_router
from backend.analytics_routes import router as analytics_router
from backend.email_routes import router as email_router

app = FastAPI(title="FORTUNE SCM", version="1.0.0")

# 注册路由
app.include_router(linkedin_router)
app.include_router(ai_config_router)
app.include_router(crm_router)
app.include_router(analytics_router)
app.include_router(email_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模板目录
PROJECT_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = os.path.join(PROJECT_DIR, "frontend", "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# 启动时初始化管理员
@app.on_event("startup")
async def startup():
    init_admin_user()

# ========== 认证接口 ==========

@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """用户登录"""
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user["status"] != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token, expire = create_access_token(
        data={"sub": str(user["id"]), "role": user["role"]},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(**user)
    )

@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(**current_user.dict())

# ========== 子账号管理接口（仅管理员） ==========

@app.post("/api/users", response_model=UserResponse)
async def create_subaccount(
    user_data: UserCreate,
    current_admin = Depends(get_current_admin)
):
    """创建子账号"""
    # 强制子账号角色
    user_data.role = UserRole.SUBACCOUNT
    user = create_user(user_data, current_admin.id)
    return UserResponse(**user)

@app.get("/api/users", response_model=list[UserResponse])
async def list_subaccounts(
    current_admin = Depends(get_current_admin)
):
    """列出所有子账号（不含管理员）"""
    users = list_users(skip_admin=True)
    return [UserResponse(**u) for u in users]

@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_subaccount(
    user_id: int,
    current_admin = Depends(get_current_admin)
):
    """获取子账号详情"""
    from backend.auth import get_user_by_id
    user = get_user_by_id(user_id)
    if not user or user["role"] == UserRole.ADMIN.value:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserResponse(**user)

@app.put("/api/users/{user_id}", response_model=UserResponse)
async def update_subaccount(
    user_id: int,
    user_data: UserUpdate,
    current_admin = Depends(get_current_admin)
):
    """更新子账号"""
    user = update_user(user_id, user_data)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserResponse(**user)

@app.delete("/api/users/{user_id}")
async def delete_subaccount(
    user_id: int,
    current_admin = Depends(get_current_admin)
):
    """删除子账号"""
    success = delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"message": "删除成功"}

# ========== 健康检查 ==========

@app.get("/api/health")
async def health():
    return {"status": "ok", "users_count": len(_users_db)}

# ========== 页面路由 ==========

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/linkedin", response_class=HTMLResponse)
async def linkedin_page(request: Request):
    return templates.TemplateResponse("linkedin.html", {"request": request})

@app.get("/ai_config", response_class=HTMLResponse)
async def ai_config_page(request: Request):
    return templates.TemplateResponse("ai_config.html", {"request": request})

@app.get("/crm", response_class=HTMLResponse)
async def crm_page(request: Request):
    return templates.TemplateResponse("crm.html", {"request": request})

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    return templates.TemplateResponse("analytics.html", {"request": request})

@app.get("/email", response_class=HTMLResponse)
async def email_page(request: Request):
    return templates.TemplateResponse("email.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    uvicorn.run(app, host="0.0.0.0", port=8000)
