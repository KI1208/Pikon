"""
WebSocket ルーター
- /ws/participant : 参加者用 WebSocket
- /ws/host        : 司会者用 WebSocket (JWT 検証あり)
"""

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from auth import verify_token
from connection_manager import manager
from room import room

logger = logging.getLogger("uvicorn")

router = APIRouter()


# ------------------------------------------------------------------ #
# ブロードキャストヘルパー
# ------------------------------------------------------------------ #


async def _broadcast_participant_update() -> None:
    """参加者リスト更新を全員に配信"""
    await manager.broadcast_all(
        {
            "type": "participant_update",
            "count": len(room.participants),
            "participants": list(room.participants.keys()),
        }
    )


async def _broadcast_result_update() -> None:
    """現在の順位情報を全員に配信"""
    await manager.broadcast_all(
        {
            "type": "result_update",
            "ranking": room.get_ranking(),
            "current_id": room.get_current_candidate(),
            "next_id": room.get_next_candidate(),
            "current_rank_index": room.current_rank_index,
        }
    )


# ------------------------------------------------------------------ #
# 参加者 WebSocket  (/ws/participant)
# ------------------------------------------------------------------ #


@router.websocket("/participant")
async def participant_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    participant_id: str | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data: dict = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = data.get("type", "")

            # ---- join -----------------------------------------------
            if event == "join":
                pid = str(data.get("participant_id", "")).strip()
                success, reason = room.join(pid)

                if not success:
                    await manager.send_to_websocket(
                        websocket,
                        {"type": "join_ack", "success": False, "reason": reason},
                    )
                    continue

                participant_id = pid
                manager.register_participant(pid, websocket)

                await manager.send_to_websocket(
                    websocket,
                    {
                        "type": "join_ack",
                        "success": True,
                        "status": room.status,
                        "question_number": room.question_number,
                    },
                )
                await _broadcast_participant_update()

            # ---- press ----------------------------------------------
            elif event == "press":
                if participant_id is None:
                    continue

                rank = room.press(participant_id)
                if rank is not None:
                    await manager.send_to_participant(
                        participant_id,
                        {"type": "press_ack", "rank": rank},
                    )
                    # ホストにもリアルタイムで順位を反映
                    await manager.broadcast_hosts(
                        {
                            "type": "result_update",
                            "ranking": room.get_ranking(),
                            "current_id": room.get_current_candidate(),
                            "next_id": room.get_next_candidate(),
                            "current_rank_index": room.current_rank_index,
                        }
                    )

    except WebSocketDisconnect:
        if participant_id:
            room.leave(participant_id)
            manager.unregister_participant(participant_id)
            await _broadcast_participant_update()
    except Exception:
        if participant_id:
            room.leave(participant_id)
            manager.unregister_participant(participant_id)


# ------------------------------------------------------------------ #
# 司会者 WebSocket  (/ws/host?token=<JWT>)
# ------------------------------------------------------------------ #


@router.websocket("/host")
async def host_ws(websocket: WebSocket, token: str = Query(...)) -> None:
    # JWT 検証
    await websocket.accept()
    try:
        verify_token(token)
    except Exception:
        await websocket.send_text(
            json.dumps({"type": "auth_error", "message": "認証エラー: 再ログインしてください"})
        )
        await websocket.close(code=4001)
        return

    manager.register_host(websocket)

    # 初期状態を送信
    await manager.send_to_websocket(
        websocket,
        {
            "type": "init",
            "status": room.status,
            "question_number": room.question_number,
            "participants": list(room.participants.keys()),
            "ranking": room.get_ranking(),
            "current_id": room.get_current_candidate(),
            "next_id": room.get_next_candidate(),
            "current_rank_index": room.current_rank_index,
        },
    )

    try:
        while True:
            raw = await websocket.receive_text()
            logger.debug(f"[WS Host] Received raw message: {raw}")
            try:
                data: dict = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"[WS Host] Failed to decode JSON from: {raw}")
                continue

            event = data.get("type", "")
            logger.info(f"[WS Host] Processing event: {event}")

            # ---- host_open ------------------------------------------
            if event == "host_open":
                logger.info("[WS Host] Opening buzzer...")
                room.open_buzzer()
                await manager.broadcast_all(
                    {
                        "type": "status_change",
                        "status": "open",
                        "question_number": room.question_number,
                    }
                )
                logger.info("[WS Host] Broadcasted status_change: open")

            # ---- host_close -----------------------------------------
            elif event == "host_close":
                room.close_buzzer()
                await manager.broadcast_all({"type": "status_change", "status": "closed"})
                await _broadcast_result_update()

            # ---- host_next_candidate --------------------------------
            elif event == "host_next_candidate":
                room.next_candidate()
                await _broadcast_result_update()

            # ---- host_reset -----------------------------------------
            elif event == "host_reset":
                room.reset()
                await manager.broadcast_all(
                    {
                        "type": "reset",
                        "question_number": room.question_number,
                        "status": "waiting",
                    }
                )

    except WebSocketDisconnect:
        manager.unregister_host(websocket)
    except Exception:
        manager.unregister_host(websocket)
