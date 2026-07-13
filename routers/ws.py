"""
WebSocket ルーター
- /ws/participant : 参加者用 WebSocket
- /ws/host        : 司会者用 WebSocket (JWT 検証あり)
"""

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from auth import verify_token
from room import room_manager, RoomState

logger = logging.getLogger("uvicorn")

router = APIRouter()


# ------------------------------------------------------------------ #
# ブロードキャストヘルパー
# ------------------------------------------------------------------ #


async def _broadcast_participant_update(room: RoomState) -> None:
    """参加者リスト更新を全員に配信"""
    await room.manager.broadcast_all(
        {
            "type": "participant_update",
            "count": len(room.participants),
            "participants": list(room.participants.keys()),
        }
    )


async def _broadcast_result_update(room: RoomState) -> None:
    """現在の順位情報を全員に配信"""
    await room.manager.broadcast_all(
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
async def participant_ws(
    websocket: WebSocket,
    room_id: str = Query(...),
) -> None:
    room = room_manager.get_room(room_id)
    if not room:
        await websocket.accept()
        await websocket.send_text(
            json.dumps({"type": "join_ack", "success": False, "reason": "指定されたルームが存在しません"})
        )
        await websocket.close(code=4002)
        return

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
                    await room.manager.send_to_websocket(
                        websocket,
                        {"type": "join_ack", "success": False, "reason": reason},
                    )
                    continue

                participant_id = pid
                room.manager.register_participant(pid, websocket)

                await room.manager.send_to_websocket(
                    websocket,
                    {
                        "type": "join_ack",
                        "success": True,
                        "status": room.status,
                        "question_number": room.question_number,
                    },
                )
                await _broadcast_participant_update(room)

            # ---- press ----------------------------------------------
            elif event == "press":
                if participant_id is None:
                    continue

                rank = room.press(participant_id)
                if rank is not None:
                    await room.manager.send_to_participant(
                        participant_id,
                        {"type": "press_ack", "rank": rank},
                    )
                    # ホストにもリアルタイムで順位を反映
                    await room.manager.broadcast_hosts(
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
            room.manager.unregister_participant(participant_id)
            await _broadcast_participant_update(room)
    except Exception:
        if participant_id:
            room.leave(participant_id)
            room.manager.unregister_participant(participant_id)


# ------------------------------------------------------------------ #
# 司会者 WebSocket  (/ws/host?token=<JWT>)
# ------------------------------------------------------------------ #


@router.websocket("/host")
async def host_ws(websocket: WebSocket, token: str = Query(...)) -> None:
    # JWT 検証
    await websocket.accept()
    try:
        payload = verify_token(token)
        room_id = payload.get("sub")
        if not room_id or payload.get("role") != "host":
            raise Exception("Invalid token scope")
        room = room_manager.get_room(room_id)
        if not room:
            raise Exception("Room not found")
    except Exception:
        await websocket.send_text(
            json.dumps({"type": "auth_error", "message": "認証エラー: 再ログインしてください"})
        )
        await websocket.close(code=4001)
        return

    room.manager.register_host(websocket)

    # 初期状態を送信
    await room.manager.send_to_websocket(
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
            "room_id": room.room_id,
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
                await room.manager.broadcast_all(
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
                await room.manager.broadcast_all({"type": "status_change", "status": "closed"})
                await _broadcast_result_update(room)

            # ---- host_next_candidate --------------------------------
            elif event == "host_next_candidate":
                room.next_candidate()
                await _broadcast_result_update(room)

            # ---- host_reset -----------------------------------------
            elif event == "host_reset":
                room.reset()
                await room.manager.broadcast_all(
                    {
                        "type": "reset",
                        "question_number": room.question_number,
                        "status": "waiting",
                    }
                )

    except WebSocketDisconnect:
        room.manager.unregister_host(websocket)
    except Exception:
        room.manager.unregister_host(websocket)
