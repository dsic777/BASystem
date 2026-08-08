"""보정 — 실측 쿠션 반사표.

    입사각(쿠션 법선 기준) → 반사각

⚠️ 이 표는 **실제로 잰 값**이다. 공식으로 지어낸 값이 아니다.
   출처: 0808.mp4 (국내식 중대, 노란공 1개) 130샷 385접점, 당점 2시30분 3팁 고정.
   당구대나 당점이 바뀌면 이 표를 다시 재야 한다.

왜 입사각 하나만 쓰나 (데이터가 그렇게 말한다)
    속도    같은 입사각에서 0.6~3.0m/s 사이 차이가 없었다
    순번    50~59도에서 1·2·3·4쿠션이 +8.7/+8.1/+8.9/+9.2 로 같다
    레일    단쿠션이 조금 크게 나왔으나 표본이 치우쳐 확정 못 한다
    → 표본이 더 쌓이면 갈라도 된다. 지금 가르면 지어내는 것이 된다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "measured_bounce.json"


@lru_cache(maxsize=1)
def _table() -> tuple[tuple[float, float], ...]:
    doc = json.loads(DATA.read_text(encoding="utf-8"))
    return tuple((float(a), float(b)) for a, b, _n in doc["table"])


@lru_cache(maxsize=1)
def source() -> str:
    return json.loads(DATA.read_text(encoding="utf-8"))["_source"]


def reflect(incidence_deg: float) -> float:
    """입사각 → 반사각 (둘 다 쿠션 법선에서 잰 각, 도).

    표 사이는 직선으로 잇는다. 표 밖은 양 끝값을 늘여 쓴다 —
    0도(정면)와 90도(스치듯)는 잰 적이 없으니 지어내지 않는다.
    """
    t = _table()
    x = abs(float(incidence_deg))
    if x <= t[0][0]:
        return _extend(t[0], t[1], x)
    if x >= t[-1][0]:
        return _extend(t[-2], t[-1], x)
    for (a0, b0), (a1, b1) in zip(t, t[1:]):
        if a0 <= x <= a1:
            return b0 + (b1 - b0) * (x - a0) / (a1 - a0)
    return x                                    # 여기 올 일은 없다


def _extend(p0, p1, x: float) -> float:
    """양 끝 두 점의 기울기로 늘인다. 90도는 넘지 않는다."""
    (a0, b0), (a1, b1) = p0, p1
    y = b0 + (b1 - b0) * (x - a0) / (a1 - a0)
    return max(x, min(y, 89.9))                 # 반사각이 입사각보다 작아지진 않는다


def gain(incidence_deg: float) -> float:
    """반사각 − 입사각. 회전 때문에 벌어진 양."""
    return reflect(incidence_deg) - abs(float(incidence_deg))
