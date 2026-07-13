"""
Hayaoshy - リアルタイム早押しクイズシステム
FastAPI エントリーポイント
"""

import os
import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from room import room_manager

load_dotenv()

from routers import host_api, ws as ws_router  # noqa: E402


async def clean_rooms_periodic():
    while True:
        try:
            await asyncio.sleep(3600)
            room_manager.clean_old_rooms()
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(clean_rooms_periodic())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Hayaoshy",
    description="リアルタイム早押しクイズシステム",
    lifespan=lifespan,
)

# 静的ファイルを /static で配信
app.mount("/static", StaticFiles(directory="static"), name="static")

# ルーターを登録
app.include_router(host_api.router, prefix="/api/host", tags=["host-api"])
app.include_router(ws_router.router, prefix="/ws", tags=["websocket"])


@app.get("/", response_class=HTMLResponse, summary="参加者画面")
async def participant_page():
    with open("static/participant/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/host/create", response_class=HTMLResponse, summary="司会者ルーム作成画面")
async def host_create_page():
    with open("static/host/create.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/host/login", response_class=HTMLResponse, summary="司会者ログイン画面")
async def host_login_page():
    with open("static/host/login.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/host", response_class=HTMLResponse, summary="司会者コントロール画面")
async def host_page():
    with open("static/host/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
