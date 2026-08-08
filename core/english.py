"""당점(잉글리시) 표기 — 시계 방향 + 팁수.

⚠️ 표기 전용이다. 경로 계산에 반영하지 않는다.
    "몇 도 각에서 몇 팁" 규칙을 아직 사용자에게 받지 못했다.
    받으면 core/correction.py 에 규칙으로 등록하고 그때 계산에 넣는다.

시계 방향
    12시 = 위(공 중심 기준), 3시 = 오른쪽, 6시 = 아래, 9시 = 왼쪽
팁수
    0 = 무회전(정중앙) … 4 = 미스큐 직전 맥시멈
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_FILE = DATA_DIR / "english.json"


@dataclass(frozen=True)
class English:
    """당점 하나."""

    clock: float          # 시계 방향 (0~12, 3.0 = 3시)
    tips: float           # 팁수 (0 ~ max_tips)

    def label(self, max_tips: float) -> str:
        if self.tips <= 0.01:
            return "무회전 (중앙)"
        hour = self.clock % 12
        if hour == 0:
            hour = 12
        # 30분 단위까지만 표기
        h = int(hour)
        m = round((hour - h) * 60 / 30) * 30
        if m == 60:
            h, m = h + 1, 0
        if h > 12:
            h -= 12
        stamp = f"{h}시" if m == 0 else f"{h}시 {m}분"
        return f"{stamp} {self.tips:g}팁" + ("  (맥시멈)" if self.tips >= max_tips else "")

    def mirrored(self) -> "English":
        """좌우 반전 (3시 ↔ 9시). 12시·6시는 그대로."""
        return English((12.0 - self.clock) % 12.0, self.tips)

    def offset(self, ball_radius: float, safe_ratio: float, max_tips: float) -> tuple[float, float]:
        """공 중심에서의 당점 위치 (mm). +x 오른쪽, +y 위쪽."""
        r = ball_radius * safe_ratio * (self.tips / max_tips if max_tips else 0.0)
        angle = math.radians(90.0 - self.clock * 30.0)     # 12시 = 90도
        return (r * math.cos(angle), r * math.sin(angle))


@dataclass(frozen=True)
class EnglishSpec:
    """당점 표기 규격 (data/english.json)."""

    max_tips: float
    safe_radius_ratio: float
    default: English
    tips_fixed: bool = True
    marker_radius: int = 14
    marker_push: float = 0.0        # 적색점 지름 기준, 당점 방향으로 밀어내는 비율

    @classmethod
    def load(cls, path: Path | str | None = None) -> "EnglishSpec":
        with open(Path(path) if path else DEFAULT_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        d = raw["default"]
        return cls(
            max_tips=float(raw["max_tips"]),
            safe_radius_ratio=float(raw["safe_radius_ratio"]),
            default=English(float(d["clock"]), float(d["tips"])),
            tips_fixed=bool(raw.get("tips_fixed", True)),
            marker_radius=int(raw.get("marker_radius", 14)),
            marker_push=float(raw.get("marker_push", 0.0)),
        )

    def marker_offset(self, english: "English", ball_radius: float) -> tuple[float, float]:
        """적색점을 그릴 위치 (공 중심 기준 오프셋).

        눈금상의 당점 위치에서 **당점 방향으로** marker_push 만큼 더 밀어낸다.
        무회전(중앙)이면 방향이 없으므로 그대로 둔다.
        """
        dx, dy = english.offset(ball_radius, self.safe_radius_ratio, self.max_tips)
        dist = math.hypot(dx, dy)
        if dist < 1e-6 or self.marker_push <= 0:
            return (dx, dy)
        push = self.marker_push * (2 * self.marker_radius)
        return (dx + dx / dist * push, dy + dy / dist * push)

    def for_side(self, left: bool) -> English:
        """좌/우 방향만 골라 준다. 팁수는 고정."""
        base = self.default
        return base.mirrored() if left else base
