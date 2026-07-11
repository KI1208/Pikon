"""
JWT 認証モジュール
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

SECRET_KEY: str = os.getenv("SECRET_KEY", "insecure-dev-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

HOST_USERNAME: str = os.getenv("HOST_USERNAME", "host")
HOST_PASSWORD: str = os.getenv("HOST_PASSWORD", "password")

_security = HTTPBearer()


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """JWT アクセストークンを生成する"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """JWT を検証してペイロードを返す。無効な場合は HTTPException を送出"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効または期限切れのトークンです",
        ) from exc


def authenticate_host(username: str, password: str) -> bool:
    """ホスト認証情報を検証する"""
    return username == HOST_USERNAME and password == HOST_PASSWORD


async def get_current_host(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    """Bearer トークンを検証する FastAPI Dependency"""
    return verify_token(credentials.credentials)
