"""실측 반사표로 공 경로를 굴린다.

    출발점 + 방향 → 쿠션 접점들

기존 five_half.solve() 는 **프레임 선에서 거울반사**하는 기하 모델이다. 이 모듈은
그와 달리 **매 쿠션마다 실측 입사→반사 표를 적용**한다. 둘 중 어느 쪽이 실제 궤적에
가까운지는 130샷으로 채점해서 정한다 (지어내지 않는다).

반사는 쿠션 날(플레이필드 사각형)에서 일어난다고 본다.
접선 방향은 그대로 두고, 법선에서 잰 각만 표대로 바꾼다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import correction

# 쿠션별 안쪽을 향하는 법선
NORMAL = {"bottom": (0.0, 1.0), "top": (0.0, -1.0),
          "left": (1.0, 0.0), "right": (-1.0, 0.0)}


@dataclass
class Hit:
    rail: str
    point: tuple[float, float]
    incoming: float                  # 법선에서 잰 입사각 (도)
    outgoing: float                  # 법선에서 잰 반사각 (도)


def _next_rail(p, d, w: float, h: float, eps: float = 1e-6):
    """점 p 에서 방향 d 로 갈 때 처음 만나는 쿠션과 그 점."""
    best = None
    for rail, t in (("right", (w - p[0]) / d[0] if d[0] > eps else None),
                    ("left", (0.0 - p[0]) / d[0] if d[0] < -eps else None),
                    ("top", (h - p[1]) / d[1] if d[1] > eps else None),
                    ("bottom", (0.0 - p[1]) / d[1] if d[1] < -eps else None)):
        if t is None or t <= eps:
            continue
        if best is None or t < best[1]:
            best = (rail, t)
    if best is None:
        return None
    rail, t = best
    return rail, (p[0] + d[0] * t, p[1] + d[1] * t)


def _bend(d, rail: str, use_table: bool, reflect=None, n_th: int = 0,
          dist: float = 0.0) -> tuple[tuple[float, float], float, float]:
    """쿠션에서 방향을 꺾는다. → (새 방향, 입사각, 반사각)

    reflect  (입사각, 레일, 쿠션순번, 굴러온거리) → 반사각.
             없으면 correction.reflect 를 쓴다.
    """
    n = NORMAL[rail]
    tang = (-n[1], n[0])                                  # 쿠션을 따라가는 방향
    dn = d[0] * n[0] + d[1] * n[1]                        # 법선 성분 (들어갈 때 음수)
    dt = d[0] * tang[0] + d[1] * tang[1]                  # 접선 성분
    a_in = math.degrees(math.atan2(abs(dt), abs(dn)))
    if not use_table:
        a_out = a_in
    elif reflect is not None:
        a_out = reflect(a_in, rail, n_th, dist)
    else:
        a_out = correction.reflect(a_in)

    # 나갈 때: 법선 성분은 안쪽(+), 접선 성분은 부호 그대로
    r = math.radians(a_out)
    s = 1.0 if dt >= 0 else -1.0
    out = (n[0] * math.cos(r) + tang[0] * s * math.sin(r),
           n[1] * math.cos(r) + tang[1] * s * math.sin(r))
    return out, a_in, a_out


def run(start, direction, w: float, h: float, cushions: int = 5,
        use_table: bool = True, reflect=None, first_n: int = 2,
        dist0: float = 0.0) -> list[Hit]:
    """출발점에서 방향대로 굴려 쿠션 접점을 차례로 낸다.

    first_n  이 궤적에서 첫 접점이 몇 번째 쿠션인지 (순번별 표를 쓸 때 필요)
    dist0    출발점까지 이미 굴러온 거리 (회전이 죽는 정도를 보려면 필요)
    """
    n = math.hypot(*direction)
    if n < 1e-9:
        return []
    p, d = tuple(start), (direction[0] / n, direction[1] / n)
    run_mm = dist0
    hits: list[Hit] = []
    for i in range(cushions):
        nxt = _next_rail(p, d, w, h)
        if nxt is None:
            break
        rail, q = nxt
        run_mm += math.hypot(q[0] - p[0], q[1] - p[1])
        d, a_in, a_out = _bend(d, rail, use_table, reflect, first_n + i, run_mm)
        hits.append(Hit(rail, q, a_in, a_out))
        p = q
    return hits


# 보정 한 눈금(=1)이 몇 mm 인가.
#   다이아몬드 한 칸 = 눈금 10 (사용자 확정)
#   단쿠션 4칸 → 40 눈금 → 1224/40 = 30.6mm
#   장쿠션 8칸 → 80 눈금 → 2448/80 = 30.6mm
# 장·단이 같은 값이라 2쿠션이 어느 쿠션에 맞든 한 눈금이 한 눈금이다.
STEP_MM = 30.6


def path_from_aim(w: float, h: float, cue, aim, cushions: int = 5,
                  second_shift: float = 0.0) -> list[Hit]:
    """수구에서 조준점을 향해 친 공이 실제로 지나는 쿠션 접점들.

    조준점(aim)은 다이아몬드 = **프레임 포인트**라 쿠션 날보다 바깥에 있다.
    공은 그보다 앞서 쿠션 날에 닿으므로, 조준선이 날과 만나는 곳이 1쿠션이다.
    거기서부터 실측 반사표대로 굴린다.

    검증: 0808.mp4 130샷으로 반씩 갈라 채점 — 2쿠션 81mm, 3쿠션 71mm,
          4쿠션 77mm, 5쿠션 65mm (기존 프레임 거울반사는 158/281/468/380mm).

    second_shift  현장 보정 (눈금. 1 = 30.6mm, + 면 2쿠션이 위로 = 긴각)

    ⚠️ 보정을 '2쿠션 접점만 한 번 밀기'로 하면 안 된다. 실측표가 이 당구대에서
       안 맞는 것이라면 **모든 쿠션이 같이 안 맞는** 것이다 (다이가 미끄러우면
       1쿠션도 3쿠션도 다 길게 나온다). 그래서 보정은 반사 특성 자체에 건다 —
       매 쿠션 반사각에 같은 양(k도)을 더하고, k 는 2쿠션이 요청한 만큼
       움직이도록 역산한다. 1쿠션 **접점**은 큐선이 정하므로 그대로지만
       1쿠션 **반사각**은 같이 바뀌고, 그래서 뒤로 갈수록 차이가 쌓인다.
    """
    d = (aim[0] - cue[0], aim[1] - cue[1])
    n = math.hypot(*d)
    if n < 1e-9:
        return []
    d = (d[0] / n, d[1] / n)

    def roll(k: float) -> list[Hit]:
        if not k:
            return run(cue, d, w, h, cushions=cushions, use_table=True, first_n=1)
        ref = lambda a, rail, nth, dist: max(a, min(correction.reflect(a) + k, 89.9))  # noqa: E731
        return run(cue, d, w, h, cushions=cushions, use_table=True, reflect=ref, first_n=1)

    base = roll(0.0)
    if not second_shift or len(base) < 2:
        return base

    # 2쿠션이 '위'(진행 반대쪽)로 얼마나 갔는지 재는 자
    rail = base[1].rail
    nrm = NORMAL[rail]
    tang = (-nrm[1], nrm[0])
    v = (base[1].point[0] - base[0].point[0], base[1].point[1] - base[0].point[1])
    up = -1.0 if (v[0] * tang[0] + v[1] * tang[1]) >= 0 else 1.0
    axis = (tang[0] * up, tang[1] * up)
    p0 = base[1].point

    def offset(k: float) -> float | None:
        hits = roll(k)
        if len(hits) < 2 or hits[1].rail != rail:
            return None
        q = hits[1].point
        return (q[0] - p0[0]) * axis[0] + (q[1] - p0[1]) * axis[1]

    want = second_shift * STEP_MM
    lo, hi = -12.0, 12.0                      # 반사각 보정 범위 (도)
    if (offset(lo) or 0) > (offset(hi) or 0):
        lo, hi = hi, lo                       # offset 이 k 에 대해 늘어나도록
    for _ in range(40):
        mid = (lo + hi) / 2
        got = offset(mid)
        if got is None:
            break
        if got < want:
            lo = mid
        else:
            hi = mid
    k = (lo + hi) / 2
    out = roll(k)
    return out if len(out) >= 2 else base


def run_frame(start, direction, w: float, h: float, frame: float,
              cushions: int = 5) -> list[Hit]:
    """비교용 — 기존 방식. 프레임 선(쿠션 날에서 frame mm 밖)에서 거울반사한다.

    꺾이는 자리는 프레임 사각형, 접점을 읽는 자리는 쿠션 날이다.
    """
    n = math.hypot(*direction)
    if n < 1e-9:
        return []
    p, d = tuple(start), (direction[0] / n, direction[1] / n)
    W, H = w + 2 * frame, h + 2 * frame
    p = (p[0] + frame, p[1] + frame)                      # 프레임 좌표계로
    hits: list[Hit] = []
    for _ in range(cushions):
        nxt = _next_rail(p, d, W, H)
        if nxt is None:
            break
        rail, q = nxt
        # 쿠션 날 접점 = 같은 직선이 날과 만나는 점
        nose = _nose_cross(p, d, rail, w, h, frame)
        d2, a_in, a_out = _bend(d, rail, use_table=False)
        hits.append(Hit(rail, nose, a_in, a_out))
        p, d = q, d2
    return hits


def _nose_cross(p, d, rail: str, w: float, h: float, frame: float):
    """프레임 좌표계의 직선이 쿠션 날과 만나는 점 (쿠션 날 좌표계로 돌려준다)."""
    value, axis = {"bottom": (frame, 1), "top": (h + frame, 1),
                   "left": (frame, 0), "right": (w + frame, 0)}[rail]
    if abs(d[axis]) < 1e-9:
        return (p[0] - frame, p[1] - frame)
    t = (value - p[axis]) / d[axis]
    return (p[0] + d[0] * t - frame, p[1] + d[1] * t - frame)
