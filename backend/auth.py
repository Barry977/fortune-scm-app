from datetime import datetime, timedelta
from typing import Optional, List
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.schemas import UserRole, UserStatus, UserInDB, UserCreate, UserUpdate, TokenPayload
from backend.database import get_db_ctx, init_db

# 配置
SECRET_KEY = "fortune-scm-secret-key-2024-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


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


def init_admin_user():
    """初始化管理员账号（如果不存在）"""
    with get_db_ctx() as conn:
        row = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if not row:
            hashed = get_password_hash("admin123")
            conn.execute(
                "INSERT INTO users (username, email, hashed_password, role, status) VALUES (?, ?, ?, ?, ?)",
                ("admin", "admin@fortune-scm.com", hashed, UserRole.ADMIN.value, UserStatus.ACTIVE.value)
            )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = decode_token(token)
    if token_data is None or token_data.sub is None:
        raise credentials_exception

    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (token_data.sub,)).fetchone()

    if row is None:
        raise credentials_exception

    if row["status"] != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用"
        )

    return UserInDB(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        role=row["role"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row["updated_at"], str) else row["updated_at"],
        created_by=row["created_by"],
    )


async def get_current_admin(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


def get_user_by_username(username: str) -> Optional[dict]:
    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_user(user_data: UserCreate, created_by: int) -> dict:
    if get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    hashed = get_password_hash(user_data.password)
    now = datetime.utcnow().isoformat()

    with get_db_ctx() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, email, hashed_password, role, status, created_at, updated_at, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_data.username, user_data.email, hashed, user_data.role.value, user_data.status.value, now, now, created_by)
        )
        user_id = cursor.lastrowid

    return get_user_by_id(user_id)


def update_user(user_id: int, user_data: UserUpdate) -> Optional[dict]:
    user = get_user_by_id(user_id)
    if not user:
        return None

    if user_data.username is not None:
        existing = get_user_by_username(user_data.username)
        if existing and existing["id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )

    now = datetime.utcnow().isoformat()
    sets = ["updated_at = ?"]
    params = [now]

    if user_data.username is not None:
        sets.append("username = ?")
        params.append(user_data.username)
    if user_data.email is not None:
        sets.append("email = ?")
        params.append(user_data.email)
    if user_data.password is not None:
        sets.append("hashed_password = ?")
        params.append(get_password_hash(user_data.password))
    if user_data.status is not None:
        sets.append("status = ?")
        params.append(user_data.status.value)

    params.append(user_id)

    with get_db_ctx() as conn:
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)

    return get_user_by_id(user_id)


def delete_user(user_id: int) -> bool:
    user = get_user_by_id(user_id)
    if not user:
        return False
    if user["role"] == UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能删除管理员账号"
        )
    with get_db_ctx() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return True


def list_users(skip_admin: bool = False) -> List[dict]:
    with get_db_ctx() as conn:
        if skip_admin:
            rows = conn.execute("SELECT * FROM users WHERE role != 'admin' ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]
