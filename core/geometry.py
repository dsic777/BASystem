"""좌표 · 반사 · 경로 유틸 (순수 기하. 당구 이론은 여기 없다)."""

from __future__ import annotations

import math

Point = tuple[float, float]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def lerp(a: Point, b: Point, t: float) -> Point:
    """a→b 를 t(0~1) 비율로 보간."""
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def mirror_x(p: Point, x_line: float) -> Point:
    """세로선 x = x_line 에 대한 거울상."""
    return (2.0 * x_line - p[0], p[1])


def mirror_y(p: Point, y_line: float) -> Point:
    """가로선 y = y_line 에 대한 거울상."""
    return (p[0], 2.0 * y_line - p[1])


def ray_hit_vertical(origin: Point, direction: Point, x_line: float) -> Point | None:
    """origin 에서 direction 방향으로 나아갈 때 세로선 x = x_line 과 만나는 점 (앞쪽만)."""
    dx = direction[0]
    if abs(dx) < 1e-9:
        return None
    t = (x_line - origin[0]) / dx
    if t <= 0:
        return None
    return (x_line, origin[1] + direction[1] * t)


def ray_hit_horizontal(origin: Point, direction: Point, y_line: float) -> Point | None:
    """origin 에서 direction 방향으로 나아갈 때 가로선 y = y_line 과 만나는 점 (앞쪽만)."""
    dy = direction[1]
    if abs(dy) < 1e-9:
        return None
    t = (y_line - origin[1]) / dy
    if t <= 0:
        return None
    return (origin[0] + direction[0] * t, y_line)


def clip_segment(a: Point, b: Point, x0: float, y0: float, x1: float, y1: float):
    """선분 ab 를 사각형 안으로 자른다 (Liang-Barsky). 완전히 밖이면 None.

    계산은 프레임 선에서 하지만 공은 쿠션 날을 뚫고 들어가지 않는다.
    그래서 화면에 그릴 때만 이 함수로 잘라낸다.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return None
            t0 = max(t0, r)
        else:
            if r < t0:
                return None
            t1 = min(t1, r)
    if t0 > t1:
        return None
    return ((a[0] + dx * t0, a[1] + dy * t0), (a[0] + dx * t1, a[1] + dy * t1))


def distance_to_segment(p: Point, a: Point, b: Point) -> float:
    """점 p 에서 선분 ab 까지의 최단 거리."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    denom = dx * dx + dy * dy
    if denom < 1e-9:
        return distance(p, a)
    t = clamp(((p[0] - ax) * dx + (p[1] - ay) * dy) / denom, 0.0, 1.0)
    return distance(p, (ax + dx * t, ay + dy * t))


def segment_intersection(p1: Point, p2: Point, p3: Point, p4: Point) -> Point | None:
    """선분 p1p2 와 p3p4 의 교점. 만나지 않으면 None."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:          # 평행 또는 겹침
        return None

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / denom
    if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
        return None

    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
