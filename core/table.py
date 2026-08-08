"""당구대 규격 · 좌표계 · 다이아몬드 번호↔좌표.

좌표계
    단위 : mm
    원점 : 쿠션 노즈(공이 닿는 면)의 좌하단 코너
    x    : 장축(가로), 0 ~ width
    y    : 단축(세로), 0 ~ height

두 개의 사각형 (⚠️ 매우 중요)
    쿠션 노즈 사각형 : 공이 실제로 튕기는 면.  width × height
    프레임 사각형    : 레일 위 흰 점(프레임 포인트)을 잇는 선.
                       노즈에서 바깥으로 frame_offset 만큼 떨어져 있다.

    파이브앤하프 계산·조준선은 전부 **프레임 포인트** 기준이다.
    공은 프레임 포인트를 보고 움직인다. 쿠션 노즈는 반사면일 뿐이다.

다이아몬드 인덱스
    장쿠션(bottom / top) : 0 = 왼쪽 코너 … 8 = 오른쪽 코너   (x 증가 방향)
    단쿠션(left / right) : 0 = 아래 코너 … 4 = 위 코너       (y 증가 방향)
    인덱스는 float 을 허용한다 (2.5 = 반다이아 위치).

규격 값은 data/table_medium.json 에서 읽는다. 코드에 하드코딩하지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_TABLE_FILE = DATA_DIR / "table_medium.json"

BOTTOM = "bottom"
RIGHT = "right"
TOP = "top"
LEFT = "left"

RAILS = (BOTTOM, RIGHT, TOP, LEFT)
LONG_RAILS = (BOTTOM, TOP)
SHORT_RAILS = (LEFT, RIGHT)

# 각 레일의 바깥 방향 (쿠션 노즈 -> 프레임 포인트)
OUTWARD = {BOTTOM: (0.0, -1.0), TOP: (0.0, 1.0), LEFT: (-1.0, 0.0), RIGHT: (1.0, 0.0)}


@dataclass(frozen=True)
class Table:
    """쿠션 안쪽 규격과 다이아몬드 배치."""

    name: str
    width: float             # 장축 (mm) — 쿠션 노즈 기준
    height: float            # 단축 (mm) — 쿠션 노즈 기준
    long_divisions: int      # 장쿠션 등분 수
    short_divisions: int     # 단쿠션 등분 수
    ball_diameter: float     # mm
    frame_offset: float      # 쿠션 노즈 -> 프레임 포인트 수직거리 (mm)
    outer_width: float       # 당구대 전체 가로 (레일 바깥 끝, mm)
    outer_height: float      # 당구대 전체 세로 (mm)
    cushion_width: float     # 쿠션 노즈 -> 나무 레일 시작 (mm)

    # ---------------------------------------------------------------- 로딩

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Table":
        path = Path(path) if path else DEFAULT_TABLE_FILE
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        field = raw["playfield"]
        diamonds = raw["diamonds"]
        return cls(
            name=raw["name"],
            width=float(field["width"]),
            height=float(field["height"]),
            long_divisions=int(diamonds["long_rail_divisions"]),
            short_divisions=int(diamonds["short_rail_divisions"]),
            ball_diameter=float(raw["ball_diameter"]),
            frame_offset=float(raw["frame_offset"]),
            outer_width=float(raw["outer"]["width"]),
            outer_height=float(raw["outer"]["height"]),
            cushion_width=float(raw["cushion_width"]),
        )

    # ---------------------------------------------------------------- 사각형

    @property
    def rail_x(self) -> float:
        """장쿠션 방향 레일 두께 — 쿠션 노즈에서 레일 바깥 끝까지 (mm)."""
        return (self.outer_width - self.width) / 2.0

    @property
    def rail_y(self) -> float:
        """단쿠션 방향 레일 두께 (mm)."""
        return (self.outer_height - self.height) / 2.0

    @property
    def rail_thickness(self) -> float:
        """레일 두께 (두 축 중 큰 쪽). 화면 여백 계산용."""
        return max(self.rail_x, self.rail_y)

    @property
    def frame_size(self) -> tuple[float, float]:
        """프레임 사각형의 (가로, 세로) mm."""
        return (self.width + 2 * self.frame_offset, self.height + 2 * self.frame_offset)

    # ------------------------------------------------------------ 다이아몬드

    def divisions(self, rail: str) -> int:
        """해당 레일의 등분 수 (= 코너~코너 다이아몬드 인덱스 최대값)."""
        if rail in LONG_RAILS:
            return self.long_divisions
        if rail in SHORT_RAILS:
            return self.short_divisions
        raise ValueError(f"알 수 없는 레일: {rail!r}")

    def cushion_position(self, rail: str, index: float) -> tuple[float, float]:
        """레일 위 다이아몬드 인덱스 → **쿠션 노즈** 위의 대응점 (mm).

        공이 실제로 닿는 면 위의 좌표다. 계산 기준이 아니다.
        """
        n = self.divisions(rail)
        if not 0 <= index <= n:
            raise ValueError(f"{rail} 레일의 인덱스 범위는 0~{n} (받은 값: {index})")

        if rail == BOTTOM:
            return (self.width * index / n, 0.0)
        if rail == TOP:
            return (self.width * index / n, self.height)
        if rail == LEFT:
            return (0.0, self.height * index / n)
        if rail == RIGHT:
            return (self.width, self.height * index / n)
        raise ValueError(f"알 수 없는 레일: {rail!r}")

    def diamond_position(self, rail: str, index: float) -> tuple[float, float]:
        """레일 위 다이아몬드 인덱스 → **프레임 포인트** 좌표 (mm).

        쿠션 노즈 위 대응점에서 바깥으로 frame_offset 만큼 나간 지점.
        파이브앤하프 계산·조준선은 전부 이 좌표를 쓴다.
        """
        x, y = self.cushion_position(rail, index)
        ox, oy = OUTWARD[rail]
        return (x + ox * self.frame_offset, y + oy * self.frame_offset)

    def diamonds(self, rail: str) -> list[tuple[int, float, float]]:
        """레일의 정수 다이아몬드 전체를 [(index, x, y), …] 로 반환 (프레임 포인트, 코너 포함)."""
        out = []
        for i in range(self.divisions(rail) + 1):
            x, y = self.diamond_position(rail, i)
            out.append((i, x, y))
        return out

    # ---------------------------------------------------------------- 영역

    def contains(self, x: float, y: float) -> bool:
        """플레이 영역(쿠션 안쪽) 안의 좌표인가."""
        return 0.0 <= x <= self.width and 0.0 <= y <= self.height

    def clamp_ball_center(self, x: float, y: float) -> tuple[float, float]:
        """공 중심이 쿠션을 파고들지 않도록 반지름만큼 안쪽으로 제한한다."""
        r = self.ball_diameter / 2.0
        cx = min(max(x, r), self.width - r)
        cy = min(max(y, r), self.height - r)
        return (cx, cy)
