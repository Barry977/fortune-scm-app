from datetime import datetime, timedelta
from typing import Optional, List, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.schemas import UserRole, UserStatus, UserInDB, UserCreate, UserUpdate, TokenPayload

# 配置
SECRET_KEY = "fortune-scm-secret-key-2024-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# 内存数据库（生产环境应使用真实数据库）
_users_db: Dict[int, dict] = {}
_user_id_counter = 0

def _get_next_id() -> int:
    global _user_id_counter
    _user_id_counter += 1
    return _user_id_counter

def init_admin_user():
    """初始化管理员账号"""
    global _users_db, _user_id_counter
    if not _users_db:
        admin_id = _get_next_id()
        _users_db[admin_id] = {
            "id": admin_id,
            "username": "admin",
            "email": "admin@fortune-scm.com",
            "hashed_password": pwd_context.hash("admin123"),
            "role": UserRole.ADMIN.value,
            "status": UserStatus.ACTIVE.value,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "created_by": None
        }

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, expire

def decode_token(token: str) -> Optional[TokenPayload]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return TokenPayload(
            sub=int(user_id),
            exp=datetime.fromtimestamp(payload.get("exp")),
            role=payload.get("role")
        )
    except JWTError:
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = decode_token(token)
    if token_data is None or token_data.sub is None:
        raise credentials_exception
    
    user = _users_db.get(token_data.sub)
    if user is None:
        raise credentials_exception
    
    if user["status"] != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用"
        )
    
    return UserInDB(**user)

async def get_current_admin(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user

# 用户CRUD操作
def get_user_by_username(username: str) -> Optional[dict]:
    for user in _users_db.values():
        if user["username"] == username:
            return user
    return None

def get_user_by_id(user_id: int) -> Optional[dict]:
    return _users_db.get(user_id)

def create_user(user_data: UserCreate, created_by: int) -> dict:
    # 检查用户名是否已存在
    if get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    user_id = _get_next_id()
    now = datetime.utcnow()
    user = {
        "id": user_id,
        "username": user_data.username,
        "email": user_data.email,
        "hashed_password": get_password_hash(user_data.password),
        "role": user_data.role.value,
        "status": user_data.status.value,
        "created_at": now,
        "updated_at": now,
        "created_by": created_by
    }
    _users_db[user_id] = user
    return user

def update_user(user_id: int, user_data: UserUpdate) -> Optional[dict]:
    user = _users_db.get(user_id)
    if not user:
        return None
    
    if user_data.username is not None:
        # 检查新用户名是否与其他用户冲突
        existing = get_user_by_username(user_data.username)
        if existing and existing["id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        user["username"] = user_data.username
    
    if user_data.email is not None:
        user["email"] = user_data.email
    
    if user_data.password is not None:
        user["hashed_password"] = get_password_hash(user_data.password)
    
    if user_data.status is not None:
        user["status"] = user_data.status.value
    
    user["updated_at"] = datetime.utcnow()
    return user

def delete_user(user_id: int) -> bool:
    if user_id not in _users_db:
        return False
    # 不能删除管理员
    if _users_db[user_id]["role"] == UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能删除管理员账号"
        )
    del _users_db[user_id]
    return True

def list_users(skip_admin: bool = False) -> List[dict]:
    users = list(_users_db.values())
    if skip_admin:
        users = [u for u in users if u["role"] != UserRole.ADMIN.value]
    return users
