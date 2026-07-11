"""
司会者用 REST API ルーター
- POST /api/host/login  : ログイン・JWT 取得
- GET  /api/host/qr     : QR コード画像取得 (認証必須)
"""

import io

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import qrcode

from auth import authenticate_host, create_access_token, get_current_host

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login", summary="司会者ログイン")
async def login(body: LoginRequest):
    """ユーザー名とパスワードを検証し、JWT を返す"""
    if not authenticate_host(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが正しくありません",
        )
    token = create_access_token({"sub": body.username, "role": "host"})
    return {"token": token}


@router.get("/qr", summary="QR コード画像 (要認証)")
async def get_qr_code(
    request: Request,
    _host: dict = Depends(get_current_host),
):
    """参加者用 URL の QR コードを PNG で返す"""
    base_url = str(request.base_url).rstrip("/")
    participant_url = f"{base_url}/"

    img = qrcode.make(participant_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Cache-Control": "no-cache"},
    )
