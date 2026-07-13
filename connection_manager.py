"""
WebSocket 接続管理モジュール
参加者・司会者の全 WebSocket 接続を追跡し、
ブロードキャストや個別送信を提供する
"""

import asyncio
import json

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # participant_id -> WebSocket
        self.participants: dict[str, WebSocket] = {}
        # 司会者の接続リスト (複数タブを許容)
        self.host_connections: list[WebSocket] = []

    # ------------------------------------------------------------------ #
    # 接続管理
    # ------------------------------------------------------------------ #

    def register_participant(self, participant_id: str, websocket: WebSocket) -> None:
        self.participants[participant_id] = websocket

    def unregister_participant(self, participant_id: str) -> None:
        self.participants.pop(participant_id, None)

    def register_host(self, websocket: WebSocket) -> None:
        self.host_connections.append(websocket)

    def unregister_host(self, websocket: WebSocket) -> None:
        try:
            self.host_connections.remove(websocket)
        except ValueError:
            pass

    # ------------------------------------------------------------------ #
    # 送信ヘルパー
    # ------------------------------------------------------------------ #

    async def _send(self, websocket: WebSocket, data: dict) -> None:
        """単一 WebSocket へ JSON を送信する。失敗しても例外を握りつぶす"""
        try:
            await websocket.send_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    async def send_to_participant(self, participant_id: str, data: dict) -> None:
        ws = self.participants.get(participant_id)
        if ws:
            await self._send(ws, data)

    async def send_to_websocket(self, websocket: WebSocket, data: dict) -> None:
        await self._send(websocket, data)

    async def broadcast_all(self, data: dict) -> None:
        """全参加者 + 全司会者にブロードキャスト"""
        targets = list(self.participants.values()) + list(self.host_connections)
        await asyncio.gather(*[self._send(ws, data) for ws in targets], return_exceptions=True)

    async def broadcast_participants(self, data: dict) -> None:
        """参加者全員にブロードキャスト"""
        targets = list(self.participants.values())
        await asyncio.gather(*[self._send(ws, data) for ws in targets], return_exceptions=True)

    async def broadcast_hosts(self, data: dict) -> None:
        """司会者全員にブロードキャスト"""
        targets = list(self.host_connections)
        await asyncio.gather(*[self._send(ws, data) for ws in targets], return_exceptions=True)


