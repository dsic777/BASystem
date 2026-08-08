"""당구대 방향 (4방향 대칭).

파이브앤하프 번호표는 **수구가 있는 코너**를 기준으로 붙는다.
data/five_half_numbers.json 에 적힌 번호표는 한 방향(7.jpg = 수구수 50이 우하단 코너)
기준이고, 나머지 세 방향은 그 번호표를 좌우/상하로 뒤집어서 쓴다.

    기준 방향 (flip 없음)
        수구수 50  = 우하단 코너,  좌측 단쿠션 위로 안 감
        1쿠션      = 상단 장쿠션
        2쿠션      = 좌측 단쿠션
        3쿠션      = 하단 장쿠션

    flip_x  수구가 왼쪽에서 출발  (2쿠션이 우측 단쿠션이 된다)
    flip_y  수구가 위쪽에서 출발  (1쿠션이 하단, 3쿠션이 상단이 된다)

좌표만 뒤집으면 프레임 포인트(음수 좌표)까지 한꺼번에 맞는다.
    flip_x:  x' = width  - x     (-90 ↔ width+90)
    flip_y:  y' = height - y

번호표를 네 벌 만들지 않고 좌표만 접는 이유가 이것이다. 진실 원천은 한 벌뿐이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.table import BOTTOM, LEFT, RIGHT, TOP, Table

Point = tuple[float, float]


@dataclass(frozen=True)
class Orientation:
    """기준 방향에서 좌우/상하로 뒤집혔는지."""

    flip_x: bool = False
    flip_y: bool = False

    # 뒤집기는 자기 역함수라 base→display 와 display→base 가 같은 연산이다.
    def apply(self, table: Table, p: Point | None) -> Point | None:
        if p is None:
            return None
        x, y = p
        if self.flip_x:
            x = table.width - x
        if self.flip_y:
            y = table.height - y
        return (x, y)

    def rail(self, rail: str) -> str:
        """기준 방향의 레일 → 화면에서 보이는 레일."""
        if self.flip_x and rail in (LEFT, RIGHT):
            return RIGHT if rail == LEFT else LEFT
        if self.flip_y and rail in (TOP, BOTTOM):
            return BOTTOM if rail == TOP else TOP
        return rail

    @property
    def label(self) -> str:
        h = "좌" if self.flip_x else "우"
        v = "상" if self.flip_y else "하"
        return f"{h}{v}단 출발"

    @classmethod
    def from_aim(cls, cue: Point, aim: Point) -> "Orientation":
        """수구 위치와 조준 방향으로 방향을 정한다.

        기준 방향에서는 수구가 오른쪽에 있고 위쪽(상단 장쿠션)을 친다.
            조준이 아래를 향하면      -> 1쿠션이 하단이므로 flip_y
            공이 오른쪽으로 진행하면  -> 좌우가 뒤집힌 배치이므로 flip_x
        """
        return cls(flip_x=aim[0] > cue[0], flip_y=aim[1] < cue[1])


BASE = Orientation()
