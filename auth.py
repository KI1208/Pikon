"""
JWT 認証モジュール
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from room import room_manager, RoomState

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


def authenticate_room_host(room_id: str, password: str) -> bool:
    """指定されたルームIDとパスワードが一致するか検証する"""
    room = room_manager.get_room(room_id)
    if not room:
        return False
    return room.password == password


async def get_current_room_host(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> RoomState:
    """Bearer トークンを検証し、該当する RoomState を返す FastAPI Dependency"""
    payload = verify_token(credentials.credentials)
    room_id = payload.get("sub")
    if not room_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なトークンです (ルームIDがありません)",
        )
    
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ルームが存在しないか、すでに削除されています",
        )
    return room
