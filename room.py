"""
ルーム状態管理モジュール
全参加者・押下記録・進行状態をインメモリで管理する
"""

import time
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Press:
    """1回の早押し記録"""

    participant_id: str
    timestamp_ns: int  # time.time_ns() — サーバー受信時刻


class RoomState:
    """クイズルームの状態を管理するシングルトン"""

    def __init__(self) -> None:
        self.status: Literal["waiting", "open", "closed"] = "waiting"
        self.question_number: int = 1
        # participant_id -> display_name (現時点では同じ値)
        self.participants: dict[str, str] = {}
        # 押下記録 (timestamp_ns でソート済み)
        self.presses: list[Press] = []
        # 司会者が現在フォーカスしている候補のインデックス (0-based)
        self.current_rank_index: int = 0

    # ------------------------------------------------------------------ #
    # 参加者管理
    # ------------------------------------------------------------------ #

    def join(self, participant_id: str) -> tuple[bool, str]:
        """
        参加者をルームに追加する。
        Returns:
            (success: bool, reason: str)
        """
        pid = participant_id.strip()
        if not pid:
            return False, "IDを入力してください"
        if pid in self.participants:
            return False, "このIDはすでに使用されています"
        self.participants[pid] = pid
        return True, ""

    def leave(self, participant_id: str) -> None:
        """参加者をルームから除去する (接続切断時)"""
        self.participants.pop(participant_id, None)
        # 押下記録は残す (順位発表への影響を避けるため)

    # ------------------------------------------------------------------ #
    # 司会者操作
    # ------------------------------------------------------------------ #

    def open_buzzer(self) -> None:
        """ボタン受付を開放する"""
        self.status = "open"
        self.presses = []
        self.current_rank_index = 0

    def close_buzzer(self) -> None:
        """ボタン受付を締め切る"""
        self.status = "closed"

    def next_candidate(self) -> bool:
        """次の候補者に移動する。移動できた場合 True"""
        if self.current_rank_index < len(self.presses) - 1:
            self.current_rank_index += 1
            return True
        return False

    def reset(self) -> None:
        """次の問題に進む (状態を初期化、問題番号をインクリメント)"""
        self.status = "waiting"
        self.presses = []
        self.current_rank_index = 0
        self.question_number += 1

    # ------------------------------------------------------------------ #
    # 参加者操作
    # ------------------------------------------------------------------ #

    def press(self, participant_id: str) -> Optional[int]:
        """
        早押しを記録する。
        Returns:
            rank (1-based) if accepted, None if rejected
        """
        if self.status != "open":
            return None
        # 二重押しを防ぐ
        if any(p.participant_id == participant_id for p in self.presses):
            return None

        new_press = Press(
            participant_id=participant_id,
            timestamp_ns=time.time_ns(),
        )
        self.presses.append(new_press)
        self.presses.sort(key=lambda p: p.timestamp_ns)

        # 自分のランク (1-based) を返す
        for i, p in enumerate(self.presses):
            if p.participant_id == participant_id:
                return i + 1
        return None  # unreachable

    # ------------------------------------------------------------------ #
    # 取得用ヘルパー
    # ------------------------------------------------------------------ #

    def get_ranking(self) -> list[str]:
        """押下順に並んだ参加者 ID リスト"""
        return [p.participant_id for p in self.presses]

    def get_current_candidate(self) -> Optional[str]:
        """現在フォーカス中の候補者 ID"""
        if self.presses and self.current_rank_index < len(self.presses):
            return self.presses[self.current_rank_index].participant_id
        return None

    def get_next_candidate(self) -> Optional[str]:
        """次の候補者 ID"""
        idx = self.current_rank_index + 1
        if self.presses and idx < len(self.presses):
            return self.presses[idx].participant_id
        return None


# シングルトンインスタンス
room = RoomState()
