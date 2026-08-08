"""큐대를 찾아 **수구가 어느 공인지** 가린다.

규칙 (사용자 확정)
    사람이 큐로 겨냥하고 있는 공이 수구다.
    큐대가 안 보이면 흰공을 수구로 본다.
    적색공은 어떤 경우에도 수구가 아니다.

찾는 법
    큐대는 당구대 모서리와 **다른 각도**로 뻗은 긴 직선이다.
    레일·쿠션선은 모서리와 나란하므로 각도로 걸러낼 수 있다.
    남은 직선 중 한쪽 끝이 공에 닿아 있으면 그 공을 겨냥한 것이다.

⚠️ 원본 사진에서 찾는다. 원근보정된 상단뷰는 쿠션 안쪽만 남기므로
   큐대가 잘려나가 보이지 않는다.
"""

from __future__ import annotations

import cv2
import numpy as np

from vision.ball_detect import Ball
from vision.table_detect import TopView, load_config

# 수구가 될 수 있는 공 (적색공은 언제나 적구)
CUE_CANDIDATES = ("white", "yellow")


def _angle(dx: float, dy: float) -> float:
    """직선의 방향각 (0~180도)."""
    return float(np.degrees(np.arctan2(dy, dx)) % 180.0)


def _angle_gap(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def ball_positions_in_original(top: TopView, balls: list[Ball]) -> list[tuple[Ball, tuple[float, float]]]:
    """상단뷰 정규화 좌표 → 원본 사진 픽셀 좌표."""
    left, up, right, down = top.inset
    inv = np.linalg.inv(top.homography)
    out = []
    for b in balls:
        wx = left + b.nx * (right - left)
        wy = up + (1.0 - b.ny) * (down - up)
        p = inv @ np.array([wx, wy, 1.0])
        out.append((b, (float(p[0] / p[2]), float(p[1] / p[2]))))
    return out


def find_aimed_ball(image: np.ndarray, top: TopView, balls: list[Ball],
                    cfg: dict | None = None) -> Ball | None:
    """큐대가 겨냥하고 있는 공. 못 찾으면 None."""
    cfg = cfg or load_config()
    scfg = cfg["cue_stick"]

    targets = [(b, p) for b, p in ball_positions_in_original(top, balls)
               if b.name in CUE_CANDIDATES]
    if not targets:
        return None

    quad = top.quad
    rail_angles = [_angle(quad[(i + 1) % 4][0] - quad[i][0],
                          quad[(i + 1) % 4][1] - quad[i][1]) for i in range(4)]
    table_px = float(np.hypot(quad[1][0] - quad[0][0], quad[1][1] - quad[0][1]))
    min_len = table_px * float(scfg["min_length_ratio"])
    tip_max = table_px * float(scfg["tip_distance_ratio"])
    margin = float(scfg["rail_angle_margin_deg"])

    lo, hi = scfg["canny"]
    edges = cv2.Canny(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), int(lo), int(hi))
    raw = cv2.HoughLinesP(edges, 1, np.pi / 360, int(scfg["hough_threshold"]),
                          minLineLength=int(min_len), maxLineGap=int(scfg["max_gap_px"]))
    if raw is None:
        return None

    best = None                                  # (선 길이, 공)
    for x1, y1, x2, y2 in np.asarray(raw).reshape(-1, 4):
        a = _angle(x2 - x1, y2 - y1)
        if min(_angle_gap(a, r) for r in rail_angles) < margin:
            continue                             # 레일과 나란함 -> 큐대 아님
        length = float(np.hypot(x2 - x1, y2 - y1))
        for ball, (cx, cy) in targets:
            tip = min(np.hypot(cx - x1, cy - y1), np.hypot(cx - x2, cy - y2))
            if tip <= tip_max and (best is None or length > best[0]):
                best = (length, ball)

    return best[1] if best else None
