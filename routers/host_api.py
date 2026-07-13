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

from auth import authenticate_room_host, create_access_token, get_current_room_host
from room import room_manager, RoomState

router = APIRouter()


class CreateRoomRequest(BaseModel):
    room_id: str | None = None


@router.post("/room/create", summary="新規ルーム作成")
async def create_room(body: CreateRoomRequest):
    """新しいルームを作成し、管理者用パスワードを返す"""
    room = room_manager.create_room(body.room_id)
    return {
        "room_id": room.room_id,
        "password": room.password,
    }


class LoginRequest(BaseModel):
    room_id: str
    password: str


@router.post("/login", summary="司会者ログイン")
async def login(body: LoginRequest):
    """ルームIDとパスワードを検証し、JWT を返す"""
    if not authenticate_room_host(body.room_id, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ルームIDまたはパスワードが正しくありません",
        )
    token = create_access_token({"sub": body.room_id, "role": "host"})
    return {"token": token, "room_id": body.room_id}


@router.get("/qr", summary="QR コード画像 (要認証)")
async def get_qr_code(
    request: Request,
    room: RoomState = Depends(get_current_room_host),
):
    """参加者用 URL の QR コードを PNG で返す"""
    base_url = str(request.base_url).rstrip("/")
    participant_url = f"{base_url}/?room={room.room_id}"

    img = qrcode.make(participant_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Cache-Control": "no-cache"},
    )
