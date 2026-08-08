"""파이브앤하프 계산.

확정된 공식
    수구수 − 1쿠션수 = 3쿠션수

    수구 → 1쿠션(상단 장쿠션, 노란색) → 돌아서 → 3쿠션(하단 장쿠션, 연두색)

    검증 예시 (사용자 제공)
        50 − 30 = 20
        80 − 60 = 20
        50 − 15 = 35   (8.jpg)

    ★ 전제 조건 (사용자 확정)
        이 공식은 **당점 3시 3팁** 에서 그대로 성립한다 (data/english.json 의 default).
        당점이 달라지면 보정이 필요하다. 보정 규칙은 core/correction.py 참조.

번호↔위치 매핑은 data/five_half_numbers.json 이 진실 원천이다.
여기서는 그 값을 읽어 보간할 뿐, 값을 만들어내지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from core import bounce, geometry
from core.orientation import BASE, Orientation  # noqa: F401  (ui 에서 재수출해 쓴다)
from core.table import BOTTOM, LEFT, RIGHT, TOP, Table

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_NUMBERS_FILE = DATA_DIR / "five_half_numbers.json"

START = "start"
FIRST_CUSHION = "first_cushion"
THIRD_CUSHION = "third_cushion"
SCALE_NAMES = (START, FIRST_CUSHION, THIRD_CUSHION)


class NumberTableMissing(RuntimeError):
    """레일 번호표가 아직 채워지지 않았다."""


# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScalePoint:
    rail: str
    index: float     # 다이아몬드 인덱스 (0.5 = 반다이아)
    number: float


FRAME = "frame"    # 레일 위 흰 점 (쿠션 노즈에서 frame_offset 바깥)
RAIL = "rail"      # 쿠션 날 (공이 실제로 닿는 면)


class Scale:
    """레일 위의 번호 눈금 하나 (수구수 / 1쿠션수 / 3쿠션수).

    눈금마다 기준선이 다르다 (reference):
        수구수·1쿠션수 = frame   (조준 기준)
        3쿠션수        = rail    (도착 기준)
    """

    def __init__(self, name: str, desc: str, color: tuple[int, int, int],
                 points: list[ScalePoint], reference: str = FRAME):
        self.name = name
        self.desc = desc
        self.color = color
        self.points = points
        self.reference = reference

        # 레일별로 index 오름차순 정렬
        self.by_rail: dict[str, list[ScalePoint]] = {}
        for p in points:
            self.by_rail.setdefault(p.rail, []).append(p)
        for rail in self.by_rail:
            self.by_rail[rail].sort(key=lambda p: p.index)

    def __bool__(self) -> bool:
        return bool(self.points)

    # ------------------------------------------------------------- 번호 → 위치

    def index_for_number(self, number: float) -> tuple[str, float] | None:
        """번호 → (레일, 다이아몬드 인덱스). 구간 사이는 선형 보간."""
        for rail, pts in self.by_rail.items():
            for a, b in zip(pts, pts[1:]):
                lo, hi = min(a.number, b.number), max(a.number, b.number)
                if lo <= number <= hi:
                    if b.number == a.number:
                        return (rail, a.index)
                    t = (number - a.number) / (b.number - a.number)
                    return (rail, a.index + t * (b.index - a.index))
        return None

    def position(self, table: Table, rail: str, index: float) -> tuple[float, float]:
        """이 눈금의 기준선 위 좌표 (frame 이면 프레임 포인트, rail 이면 쿠션 날)."""
        if self.reference == RAIL:
            return table.cushion_position(rail, index)
        return table.diamond_position(rail, index)

    def point_for_number(self, table: Table, number: float) -> tuple[float, float] | None:
        """번호 → 당구대 좌표 (mm). 이 눈금의 기준선 위 좌표다."""
        hit = self.index_for_number(number)
        if hit is None:
            return None
        rail, index = hit
        return self.position(table, rail, index)

    # ------------------------------------------------------------- 위치 → 번호

    def number_at_extrapolated(self, rail: str, index: float) -> float | None:
        """눈금 범위를 넘어가면 끝 구간의 기울기로 연장해서 읽는다.

        4쿠션처럼 전용 눈금이 없어 '코너 기준 감각'으로 보는 자리에 쓴다.
        """
        pts = self.by_rail.get(rail)
        if not pts:
            return None
        inside = self.number_at(rail, index)
        if inside is not None:
            return inside
        if len(pts) < 2:
            return None
        a, b = (pts[0], pts[1]) if index < pts[0].index else (pts[-2], pts[-1])
        if b.index == a.index:
            return None
        slope = (b.number - a.number) / (b.index - a.index)
        return a.number + slope * (index - a.index)

    def number_at(self, rail: str, index: float) -> float | None:
        """레일 위 다이아몬드 인덱스 → 번호. 구간 사이는 선형 보간."""
        pts = self.by_rail.get(rail)
        if not pts:
            return None
        for a, b in zip(pts, pts[1:]):
            if a.index <= index <= b.index:
                if b.index == a.index:
                    return a.number
                t = (index - a.index) / (b.index - a.index)
                return a.number + t * (b.number - a.number)
        return None


# ---------------------------------------------------------------------------


def load_scales(path: Path | str | None = None) -> dict[str, Scale]:
    """data/five_half_numbers.json 에서 세 눈금을 읽는다."""
    path = Path(path) if path else DEFAULT_NUMBERS_FILE
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    out: dict[str, Scale] = {}
    for name in SCALE_NAMES:
        spec = raw.get("scales", {}).get(name, {})
        pts = [
            ScalePoint(p["rail"], float(p["index"]), float(p["number"]))
            for p in spec.get("points", [])
        ]
        out[name] = Scale(
            name=name,
            desc=spec.get("_desc", name),
            color=tuple(spec.get("color", (255, 255, 255))),
            points=pts,
            reference=spec.get("reference", FRAME),
        )
    return out


def is_ready(scales: dict[str, Scale]) -> bool:
    """세 눈금이 모두 채워졌는가."""
    return all(scales.get(n) for n in SCALE_NAMES)


# --------------------------------------------------------------------- 공식


def third_cushion_number(start_number: float, first_cushion_number_: float) -> float:
    """3쿠션수 = 수구수 − 1쿠션수."""
    return start_number - first_cushion_number_


def first_cushion_number(start_number: float, third_cushion_number_: float) -> float:
    """1쿠션수 = 수구수 − 3쿠션수."""
    return start_number - third_cushion_number_


# ------------------------------------------------------- 수구수 읽기 (연장선)


def frame_line_value(table: Table, rail: str) -> float:
    """레일의 프레임 선 위치. 장쿠션이면 y값, 단쿠션이면 x값."""
    off = table.frame_offset
    return {
        BOTTOM: -off,
        TOP: table.height + off,
        LEFT: -off,
        RIGHT: table.width + off,
    }[rail]


def index_on_frame(table: Table, rail: str, x: float, y: float) -> float:
    """프레임 선 위의 점 → 다이아몬드 인덱스 (범위 밖도 그대로 반환)."""
    n = table.divisions(rail)
    if rail in (BOTTOM, TOP):
        return x / table.width * n
    return y / table.height * n


def rail_corner_slack(table: Table, rail: str) -> float:
    """레일 끝 너머로 허용할 인덱스 여유 (다이아 단위).

    프레임선은 레일마다 따로 있어서 코너에서 frame_offset 만큼 서로 어긋난다.
    그 틈으로 연장선이 빠져나가면 눈금 밖이 되므로, 틈 크기만큼만 코너로 당겨 읽는다.
    """
    n = table.divisions(rail)
    length = table.width if rail in (BOTTOM, TOP) else table.height
    return table.frame_offset * n / length


def read_number_on_rail(table: Table, scale: Scale, rail: str,
                        index: float) -> tuple[float, float, bool] | None:
    """레일 위 인덱스 → (번호, 실제로 읽은 인덱스, 코너로 당겨읽었는지)."""
    number = scale.number_at(rail, index)
    if number is not None:
        return (number, index, False)

    pts = scale.by_rail.get(rail)
    if not pts:
        return None
    lo, hi = pts[0].index, pts[-1].index
    slack = rail_corner_slack(table, rail)
    if not (lo - slack <= index <= hi + slack):
        return None

    snapped = min(max(index, lo), hi)
    number = scale.number_at(rail, snapped)
    return None if number is None else (number, snapped, True)


@dataclass(frozen=True)
class CueReading:
    """수구 중심 → 1쿠션 조준선을 뒤로 연장해 읽은 출발값."""

    number: float                 # 수구수
    rail: str                     # 등 뒤 레일
    index: float                  # 다이아몬드 인덱스
    point: tuple[float, float]    # 프레임 선 위의 교점 (mm)
    corner_snapped: bool = False  # 코너 틈으로 빠져 코너값으로 당겨 읽었는가


def read_cue_number(
    table: Table,
    scale: Scale,
    cue_ball: tuple[float, float],
    aim_point: tuple[float, float],
) -> CueReading | None:
    """수구위치 측정 (사용자 제공 방법).

        1. 수구 중심을 지나 목표 1쿠션 포인트로 직선을 긋는다
        2. 그 선을 **뒤로** 연장한다
        3. 등 뒤 프레임 포인트 선과 만나는 곳의 숫자 = 수구수

    aim_point 는 1쿠션 **프레임 포인트** 좌표여야 한다 (쿠션 노즈가 아니라).
    읽히는 눈금이 없으면 None.
    """
    cx, cy = cue_ball
    dx, dy = cx - aim_point[0], cy - aim_point[1]      # 뒤쪽 방향
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None

    best: tuple[float, CueReading] | None = None
    for rail in scale.by_rail:
        value = frame_line_value(table, rail)
        along = dy if rail in (BOTTOM, TOP) else dx
        if abs(along) < 1e-9:
            continue
        start = cy if rail in (BOTTOM, TOP) else cx
        t = (value - start) / along
        if t <= 0:                                     # 앞쪽은 조준 방향이라 제외
            continue

        px, py = cx + dx * t, cy + dy * t
        hit = read_number_on_rail(table, scale, rail, index_on_frame(table, rail, px, py))
        if hit is None:                                # 눈금 범위 밖
            continue
        number, index, snapped = hit
        if best is None or t < best[0]:
            best = (t, CueReading(number, rail, index, (px, py), snapped))

    return best[1] if best else None


# --------------------------------------------------------------- 경로 계산
#
# 경로: 수구 → 상단 장쿠션(1쿠션) → 좌측 단쿠션(2쿠션) → 하단 장쿠션(3쿠션)
#       사용자 설명 "상단 30으로 보내면 하단 20으로 온다" 의 그 경로.
#
# ★ 두 기준선을 나눠 쓴다 (13.jpg·14.jpg 로 검증)
#
#     반사(꺾임)  → **프레임 선**   (다이아몬드 점을 잇는 선, 노즈에서 frame_offset 바깥)
#     번호 읽기   → **쿠션 날**     (3쿠션수는 공이 실제로 닿는 면에서 읽는다)
#
#   즉 공은 프레임 선까지 들어갔다가 거기서 꺾여 나온다. 번호는 그 궤적이
#   쿠션 날을 지나는 자리에서 읽는다.
#
#   검증: 사용자가 "실제로 공이 가는 자리"에 놓은 노란공까지의 수직거리
#     13.jpg (1쿠션 30, 3쿠션 20)   쿠션날 반사 246.6mm 빗나감  →  프레임 반사  -9.9mm 명중
#     14.jpg (1쿠션  0, 3쿠션 50)   쿠션날 반사 187.2mm 빗나감  →  프레임 반사 -25.6mm 명중
#     (공 반지름 32.8mm 안이면 명중)


def frame_bounds(table: Table) -> tuple[float, float, float, float]:
    """프레임 사각형 (x0, y0, x1, y1) mm."""
    off = table.frame_offset
    return (-off, -off, table.width + off, table.height + off)


@dataclass(frozen=True)
class Shot:
    """한 번의 조준 결과.

    조준(aim)은 프레임 포인트를, 실제 공 궤적(c1·p2·p3)은 쿠션 날을 지난다.
    """

    cue: tuple[float, float]
    cue_number: float | None = None
    first_number: float | None = None
    third_number: float | None = None
    p1: tuple[float, float] | None = None      # 1쿠션 꺾임점 (상단 **프레임선**)
    c1: tuple[float, float] | None = None      # 1쿠션 실제 접점 (상단 쿠션 날)
    p2: tuple[float, float] | None = None      # 2쿠션 꺾임점 (좌측 **프레임선**)
    c2: tuple[float, float] | None = None      # 2쿠션 실제 접점 (좌측 쿠션 날)
    p3: tuple[float, float] | None = None      # 3쿠션 도착 (하단 쿠션 날 = 레일 포인트)
    bend3: tuple[float, float] | None = None   # 3쿠션 꺾임점 (하단 **프레임선**)
    p4: tuple[float, float] | None = None      # 3쿠션 이후 진행선 끝점 (적구로 가는 선)
    fourth_rail: str | None = None             # 4쿠션이 닿는 레일
    fourth_index: float | None = None          # 그 레일의 다이아몬드 인덱스
    fourth_number: float | None = None         # 그 레일에 있는 눈금으로 읽은 값
    orientation: Orientation = BASE            # 어느 코너에서 출발하는 배치인가
    note: str = ""                             # 계산이 끊긴 이유
    # 실측 반사표로 굴린 실제 경로 (수구 → 쿠션 접점들). 화면 좌표.
    # ⚠️ 위의 p1·c1·p2·c2·p3 는 **시스템 표대로 계산한 값**이고, 이건 **실제로
    #    굴러가는 경로**다. 둘은 다르다. 0808.mp4 130샷 채점에서 실측 경로가
    #    3쿠션 71mm, 시스템 기하 모델이 281mm 였다.
    real_path: tuple[tuple[float, float], ...] = ()

    @property
    def ok(self) -> bool:
        return self.p3 is not None

    def hits(self, ball: tuple[float, float], ball_diameter: float) -> float | None:
        """3쿠션 이후 진행선이 이 공을 맞히는가.

        반환값은 선과 공 중심 사이 거리(mm). 공 지름보다 작으면 맞는다.
        (수구 반지름 + 적구 반지름 = 공 지름)
        """
        if self.p3 is None or self.p4 is None:
            return None
        return geometry.distance_to_segment(ball, self.p3, self.p4)


def aim_first_cushion(table: Table, cue: tuple[float, float], cursor: tuple[float, float],
                      orientation: Orientation | None = None) -> tuple[float, float] | None:
    """수구에서 커서 방향으로 조준했을 때 1쿠션 장쿠션 프레임선과 만나는 점.

    어느 장쿠션이 1쿠션인지는 방향(orientation)이 정한다. 반환값은 화면 좌표.
    """
    o = orientation or Orientation.from_aim(cue, cursor)
    b_cue, b_cursor = o.apply(table, cue), o.apply(table, cursor)
    _, _, _, y_top = frame_bounds(table)
    direction = (b_cursor[0] - b_cue[0], b_cursor[1] - b_cue[1])
    hit = geometry.ray_hit_horizontal(b_cue, direction, y_top)
    return o.apply(table, hit)


def _second_cushion(table: Table, p1, p3):
    """1쿠션 꺾임점 → 3쿠션 레일점을 잇는 **좌측 프레임선** 위의 꺾임점.

    p1 은 상단 프레임선 위, p3 는 하단 쿠션 날 위. 그 둘을 잇되
    좌측 프레임선(x = -frame_offset)에서 꺾이도록 대칭점 방식으로 푼다.
    """
    x0, y0, _, y1 = frame_bounds(table)
    mirrored = geometry.mirror_x(p3, x0)
    direction = (mirrored[0] - p1[0], mirrored[1] - p1[1])
    hit = geometry.ray_hit_vertical(p1, direction, x0)
    if hit is None or not (y0 <= hit[1] <= y1):
        return None
    return hit


def _second_contact(table: Table, c1, p1, p2):
    """2쿠션 실제 접점 (좌측 쿠션 날 위).

    1쿠션에서 튕긴 자리 c1 에서 p1→p2 방향으로 나아가 x = 0 에 닿는 곳.
    구하지 못하면 프레임 꺾임점을 쿠션 날로 눌러 붙인다.
    """
    if p2 is None:
        return None
    if c1 is not None:
        hit = geometry.ray_hit_vertical(c1, (p2[0] - p1[0], p2[1] - p1[1]), 0.0)
        if hit is not None and 0.0 <= hit[1] <= table.height:
            return hit
    return (0.0, geometry.clamp(p2[1], 0.0, table.height))


def _third_bend(table: Table, p2, p3):
    """3쿠션 꺾임점 — 하단 **프레임선** 위. 궤적은 p3(쿠션 날)를 지나 여기까지 들어간다."""
    _, y0, _, _ = frame_bounds(table)
    direction = (p3[0] - p2[0], p3[1] - p2[1])
    return geometry.ray_hit_horizontal(p2, direction, y0)


def _extend_after_third(table: Table, p2, bend):
    """하단 프레임선에서 꺾여 나가는 방향으로 쿠션 날 경계까지 (4쿠션 방향)."""
    direction = (bend[0] - p2[0], -(bend[1] - p2[1]))   # 가로선 반사 → y 성분 반전
    candidates = [
        geometry.ray_hit_vertical(bend, direction, 0.0),
        geometry.ray_hit_vertical(bend, direction, table.width),
        geometry.ray_hit_horizontal(bend, direction, table.height),
    ]
    best = None
    for c in candidates:
        if c is None:
            continue
        if not (-1e-6 <= c[0] <= table.width + 1e-6 and -1e-6 <= c[1] <= table.height + 1e-6):
            continue
        d = geometry.distance(bend, c)
        if d > 1e-6 and (best is None or d < best[0]):
            best = (d, c)
    return best[1] if best else None


# 4쿠션에는 전용 눈금이 없다 (사용자 확정).
# 코너 기준으로 감각으로 보되, 그 레일에 이미 있는 눈금을 그대로 읽는다.
#   상단 장쿠션 -> 1쿠션수 / 하단 장쿠션 -> 3쿠션수 / 우측 단쿠션 -> 수구수
RAIL_SCALE = {TOP: FIRST_CUSHION, BOTTOM: THIRD_CUSHION, RIGHT: START}


def read_arrival(table: Table, scales: dict[str, Scale],
                 point: tuple[float, float]) -> tuple[str, float, float | None] | None:
    """도착점 → (레일, 다이아몬드 인덱스, 눈금값). 눈금이 없거나 범위 밖이면 값은 None."""
    x, y = point
    tol = 1.0
    if abs(y - table.height) < tol:
        rail = TOP
    elif abs(y) < tol:
        rail = BOTTOM
    elif abs(x - table.width) < tol:
        rail = RIGHT
    elif abs(x) < tol:
        rail = LEFT
    else:
        return None

    index = index_on_frame(table, rail, x, y)
    scale = scales.get(RAIL_SCALE.get(rail, ""))
    # 4쿠션은 전용 눈금이 없다 (사용자 확정). 코너 너머는 끝 구간 기울기로 연장해 읽는다.
    number = scale.number_at_extrapolated(rail, index) if scale else None
    return (rail, index, number)


def solve(table: Table, scales: dict[str, Scale], cue: tuple[float, float],
          first_point: tuple[float, float], orientation: Orientation | None = None,
          second_shift: float = 0.0) -> Shot:
    """수구 위치 + 1쿠션 조준점 → 수구수 / 1쿠션수 / 3쿠션수 / 경로.

    입력·출력 모두 **화면 좌표**다. 계산은 기준 방향(7.jpg)으로 접어서 하고
    결과를 다시 펴서 돌려준다. 그래서 번호표는 한 벌만 있으면 된다.
    """
    o = orientation or Orientation.from_aim(cue, first_point)
    disp = cue                                        # 화면 좌표 원본 (Shot 에 그대로 담는다)

    # 실제 경로는 접지 않고 화면 좌표에서 바로 굴린다. 실측 반사표는 좌우 대칭이라
    # 접을 이유가 없고, 접었다 펴면 오히려 헷갈린다.
    real = tuple([tuple(cue)] + [h.point for h in
                                 bounce.path_from_aim(table.width, table.height,
                                                      cue, first_point, cushions=5,
                                                      second_shift=second_shift)])

    cue = o.apply(table, cue)
    first_point = o.apply(table, first_point)

    def out(shot: Shot) -> Shot:
        """기준 방향에서 구한 점들을 화면 좌표로 되돌린다."""
        m = lambda p: o.apply(table, p)               # noqa: E731
        return replace(shot, cue=disp, p1=m(shot.p1), c1=m(shot.c1), p2=m(shot.p2),
                       c2=m(shot.c2), p3=m(shot.p3), bend3=m(shot.bend3), p4=m(shot.p4),
                       fourth_rail=o.rail(shot.fourth_rail) if shot.fourth_rail else None,
                       orientation=o, real_path=real)

    start, first, third = scales[START], scales[FIRST_CUSHION], scales[THIRD_CUSHION]

    reading = read_cue_number(table, start, cue, first_point)
    if reading is None:
        return out(Shot(cue, p1=first_point, note="수구수를 읽을 수 없음 (연장선이 눈금 밖)"))

    hit1 = read_number_on_rail(table, first, TOP, index_on_frame(table, TOP, *first_point))
    if hit1 is None:
        return out(Shot(cue, cue_number=reading.number, p1=first_point,
                        note="1쿠션 조준점이 1쿠션수 눈금 밖"))
    n1 = hit1[0]

    n3 = third_cushion_number(reading.number, n1)
    p3 = third.point_for_number(table, n3)             # 레일 포인트 (쿠션 날)
    if p3 is None:
        return out(Shot(cue, cue_number=reading.number, first_number=n1, third_number=n3,
                        p1=first_point, note=f"3쿠션수 {n3:g} 는 눈금 범위 밖"))

    # 조준선이 상단 쿠션 날을 지나는 곳 (표시용). 꺾임은 프레임선(first_point)에서 일어난다.
    c1 = geometry.ray_hit_horizontal(cue, (first_point[0] - cue[0], first_point[1] - cue[1]),
                                     table.height)

    # 2쿠션을 거치는 경로. 좌측 프레임선을 벗어나면 짧은 각이라 2쿠션 없이
    # 1쿠션에서 바로 3쿠션으로 간다.
    p2 = _second_cushion(table, first_point, p3)
    prev = p2 if p2 is not None else first_point
    note = "" if p2 is not None else "짧은 각 — 2쿠션 없이 1쿠션에서 바로 3쿠션"

    # 2쿠션 실제 접점 — 공이 1쿠션에서 튕긴 자리(c1)에서 출발해 좌측 쿠션 날에 닿는 곳.
    #
    # ⚠️ 프레임 점 p1 에서 출발시키면 안 된다. p1 은 천 바깥이라 1쿠션수가 코너에
    #    가까울 때 교점이 당구대 밖으로 나간다 (19.jpg 에서 드러난 버그).
    c2 = _second_contact(table, c1, first_point, p2)

    bend3 = _third_bend(table, prev, p3)
    if bend3 is None:
        return out(Shot(cue, reading.number, n1, n3, p1=first_point, c1=c1, p2=p2, c2=c2,
                        p3=p3, note="3쿠션 꺾임점을 구하지 못함"))

    p4 = _extend_after_third(table, prev, bend3)
    arrival = read_arrival(table, scales, p4) if p4 else None
    return out(Shot(cue, reading.number, n1, n3, first_point, c1, p2, c2, p3, bend3, p4,
                    *(arrival if arrival else (None, None, None)), note=note))
