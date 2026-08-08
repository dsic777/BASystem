"""사진 → 당구대 4코너 → 원근보정(호모그래피) → 상단뷰.

로드맵 0.5단계. 지금은 정지 화면(캡처/동영상 스틸)만 다룬다.

절차
    1. 천 색으로 당구대 영역을 딴다
    2. 볼록껍질로 사람·큐대 가림을 메운다
    3. 그 경계에서 직선을 뽑아 장쿠션 2개 / 단쿠션 2개로 나눈다
    4. 양 끝 직선끼리 교차시켜 4코너를 구한다   ← 코너 근사보다 가림에 강하다
    5. 호모그래피로 2:1 직사각형으로 편다
    6. 편 그림에서 밝기 단차를 찾아 쿠션 날 안쪽 영역을 잘라낸다

튜닝값은 data/vision.json 에 있다. 코드에 숫자를 박지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_CONFIG = DATA_DIR / "vision.json"


def load_config(path: Path | str | None = None) -> dict:
    with open(Path(path) if path else DEFAULT_CONFIG, encoding="utf-8") as f:
        return json.load(f)


class TableNotFound(RuntimeError):
    """사진에서 당구대를 찾지 못했다."""


@dataclass
class TopView:
    """원근보정 결과."""

    image: np.ndarray                  # 쿠션 날 안쪽만 잘라낸 상단뷰
    full: np.ndarray                   # 천 바깥까지 포함한 상단뷰 (디버그용)
    quad: np.ndarray                   # 원본 사진에서의 4코너 (좌하,우하,우상,좌상)
    homography: np.ndarray             # 원본 → full 변환
    inset: tuple[int, int, int, int]   # full 안에서 잘라낸 위치 (좌,상,우,하)

    @property
    def size(self) -> tuple[int, int]:
        """당구대가 차지하는 크기 (px). 그림 전체가 아니라 inset 안쪽이다."""
        left, up, right, down = self.inset
        return (int(right - left), int(down - up))

    @property
    def aspect(self) -> float:
        left, up, right, down = self.inset
        return (right - left) / (down - up) if down > up else 0.0

    def to_mm(self, nx: float, ny: float, width: float, height: float
              ) -> tuple[float, float]:
        """상단뷰 정규화 좌표(0~1, 아래가 0) → 당구대 mm.

        ⚠️ 그림 전체를 당구대로 보면 안 된다. 여유를 두고 폈으므로 당구대는
           그림 안쪽 inset 자리에만 있다. 그 자리를 기준으로 환산한다.
        """
        ih, iw = self.image.shape[:2]
        left, up, right, down = self.inset
        px, py = nx * iw, (1.0 - ny) * ih                    # 그림 픽셀 (위가 0)
        return ((px - left) / max(right - left, 1) * width,
                (down - py) / max(down - up, 1) * height)


# --------------------------------------------------------------------- 내부


def _cloth_mask(img: np.ndarray, cfg: dict) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lo = tuple(cfg["cloth_hsv"]["lower"])
    hi = tuple(cfg["cloth_hsv"]["upper"])
    mask = cv2.inRange(hsv, lo, hi)
    c = cfg["corner"]
    # ⚠️ OPEN 을 먼저 한다. CLOSE 를 먼저 하면 선수 옷(남색)이나 뒤쪽 당구대와
    #    가느다랗게 이어져 버리고, 그 뒤 OPEN 으로는 못 끊는다.
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            np.ones((c["open_kernel"],) * 2, np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            np.ones((c["close_kernel"],) * 2, np.uint8))
    return mask


def _line_of(seg) -> np.ndarray:
    """선분 → 정규화된 직선 (a, b, c),  ax + by + c = 0."""
    x1, y1, x2, y2 = seg
    a, b = y2 - y1, x1 - x2
    n = float(np.hypot(a, b))
    return np.array([a / n, b / n, -(a * x1 + b * y1) / n])


def _extreme_lines(lines: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """같은 방향 직선 무리에서 양쪽 끝 두 개를 평균으로 뽑는다."""
    ref = lines[0][:2]
    lines = [l if float(np.dot(l[:2], ref)) >= 0 else -l for l in lines]
    off = np.array([-l[2] for l in lines])
    k = max(1, len(off) // 4)
    lo = np.mean([lines[i] for i in np.argsort(off)[:k]], axis=0)
    hi = np.mean([lines[i] for i in np.argsort(off)[-k:]], axis=0)
    return lo, hi


def _intersect(l1: np.ndarray, l2: np.ndarray) -> list[float]:
    a1, b1, c1 = l1
    a2, b2, c2 = l2
    d = a1 * b2 - a2 * b1
    if abs(d) < 1e-9:
        raise TableNotFound("쿠션 직선이 평행해서 코너를 못 구했다")
    return [(b1 * c2 - b2 * c1) / d, (a2 * c1 - a1 * c2) / d]


def _rect_aspect(q, shape) -> float | None:
    """사진 속 사각형이 원래 직사각형이었다면 그 가로세로비가 얼마인가.

    ⚠️ 화면상 변 길이로 장쿠션을 고르면 안 된다. 비스듬히 가까이서 찍으면 먼 쪽
       장쿠션이 짜부라져 단쿠션보다 짧아 보인다 (2026-08-07 사진: 비율 1.00~1.10).
       그러면 당구대를 90도 눕혀서 펴게 되고 공이 타원이 된다.

    직사각형의 사진이라는 사실만으로 초점거리와 진짜 비를 풀 수 있다
    (Zhang & He, 2003). 주점은 화면 중앙, 픽셀은 정사각형이라고 본다.

    q  순환 순서 4점.  q0↔(0,0) q1↔(w,0) q2↔(w,h) q3↔(0,h)
    → q0→q1 변이 가로일 때의 가로/세로. 못 구하면 None.
    """
    u0, v0 = shape[1] / 2.0, shape[0] / 2.0
    m1 = np.array([q[0][0], q[0][1], 1.0])
    m2 = np.array([q[1][0], q[1][1], 1.0])
    m3 = np.array([q[3][0], q[3][1], 1.0])
    m4 = np.array([q[2][0], q[2][1], 1.0])

    d2 = np.dot(np.cross(m2, m4), m3)
    d3 = np.dot(np.cross(m3, m4), m2)
    if abs(d2) < 1e-9 or abs(d3) < 1e-9:
        return None
    k2 = np.dot(np.cross(m1, m4), m3) / d2
    k3 = np.dot(np.cross(m1, m4), m2) / d3
    n2 = k2 * m2 - m1
    n3 = k3 * m3 - m1

    den = n2[2] * n3[2]
    if abs(den) < 1e-12:
        return None
    f2 = -((n2[0] - n2[2] * u0) * (n3[0] - n3[2] * u0)
           + (n2[1] - n2[2] * v0) * (n3[1] - n3[2] * v0)) / den
    if not np.isfinite(f2) or f2 <= 1.0:
        return None

    inv = np.array([[1 / f2, 0, -u0 / f2],
                    [0, 1 / f2, -v0 / f2],
                    [-u0 / f2, -v0 / f2, (u0 * u0 + v0 * v0) / f2 + 1.0]])
    a = float(n2 @ inv @ n2)
    b = float(n3 @ inv @ n3)
    if a <= 0 or b <= 0:
        return None
    return float(np.sqrt(a / b))


def _order(pts: np.ndarray, shape=None) -> np.ndarray:
    """(좌하, 우하, 우상, 좌상) 순으로 정렬.

    ⚠️ 화면 사분면으로 나누면 안 된다. 당구대가 화면에서 많이 돌아가 있으면
       두 코너가 같은 사분면에 들어간다 (당구장 영상에서 드러난 문제).
       무게중심 기준 각도로 순환 정렬한 뒤, **긴 변**과 **카메라에 가까운 쪽**으로 정한다.
    """
    c = pts.mean(axis=0)
    order = np.argsort(np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0]))
    p = pts[order]                                   # 네 점이 순환 순서로 정렬됨

    # 어느 변쌍이 장쿠션인가 — 원근을 되돌린 진짜 비로 정한다.
    long_pair = None
    if shape is not None:
        ratio = _rect_aspect(p, shape)
        if ratio is not None and (ratio > 1.35 or ratio < 0.74):
            long_pair = 0 if ratio > 1.0 else 1
    if long_pair is None:                            # 못 구하면 화면상 길이로 (예전 방식)
        side = [float(np.linalg.norm(p[(i + 1) % 4] - p[i])) for i in range(4)]
        long_pair = 0 if side[0] + side[2] >= side[1] + side[3] else 1
    cand = [long_pair, long_pair + 2]
    # 긴 변 둘 중 화면 아래쪽(카메라에 가까운) 것을 '하단 장쿠션'으로 본다
    base = cand[int(np.argmax([(p[i][1] + p[(i + 1) % 4][1]) / 2 for i in cand]))]

    # ⚠️ 나머지 두 코너를 '거리 가까운 순'으로 정하면 안 된다. 원근이 심하면
    #    먼 쪽이 짜부라져 좌상이 우하에 더 가까워지고, 사각형이 나비넥타이처럼
    #    꼬인다 (2026-08-07 사진 9장 중 6장이 이 때문에 버려졌다).
    #    이미 무게중심 기준 순환 순서(p)가 있으니 그 순서를 그대로 따라간다 —
    #    순환 순서를 따르면 스스로 교차하는 사각형이 나올 수 없다.
    if p[base][0] > p[(base + 1) % 4][0]:            # 아래 변의 왼쪽 끝이 좌하다
        idx = [(base + 1) % 4, base, (base + 3) % 4, (base + 2) % 4]
    else:
        idx = [base, (base + 1) % 4, (base + 2) % 4, (base + 3) % 4]
    return np.array([p[i] for i in idx], np.float32)        # 좌하, 우하, 우상, 좌상


def _roundness(img: np.ndarray, quad: np.ndarray, cfg: dict) -> float:
    """이 코너 순서로 펴면 공이 얼마나 동그랗게 나오나. 작을수록 좋다.

    ⚠️ 어느 변이 장쿠션인지 화면상 길이나 원근 복원으로 정하면 자주 틀린다.
       (2026-08-07 사진: 길이로는 0.34~2.93, 복원으로는 2.5·1.6 처럼 벗어남)
       추측하지 말고 **두 방향으로 다 펴보고 공 모양을 본다** — 장단이 뒤바뀌면
       공이 2:1 타원이 되므로 답이 바로 드러난다.
    """
    w = int(cfg["warp"]["width_px"])
    h = w // 2
    dst = np.array([[0, h], [w, h], [w, 0], [0, 0]], np.float32)
    m = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    top = cv2.warpPerspective(img, m, (w, h))

    hsv = cv2.cvtColor(top, cv2.COLOR_BGR2HSV)
    cloth = cv2.inRange(hsv, tuple(cfg["cloth_hsv"]["lower"]),
                        tuple(cfg["cloth_hsv"]["upper"]))
    # 천 안쪽에서 천이 아닌 것 = 공. 쿠션·바깥은 천 영역을 채워서 한계 짓는다.
    inside = np.zeros_like(cloth)
    cnts, _ = cv2.findContours(cloth, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return 9.9
    cv2.drawContours(inside, [max(cnts, key=cv2.contourArea)], -1, 255, -1)
    blobs = cv2.bitwise_and(cv2.bitwise_not(cloth), inside)
    blobs = cv2.morphologyEx(blobs, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    n, _lab, st, _c = cv2.connectedComponentsWithStats(blobs, 8)
    ball = w / 2448.0 * 61.5                          # 상단뷰에서 공 지름 (px)
    scores = []
    for i in range(1, n):
        bw, bh = int(st[i, cv2.CC_STAT_WIDTH]), int(st[i, cv2.CC_STAT_HEIGHT])
        area = int(st[i, cv2.CC_STAT_AREA])
        if not (ball * 0.4 <= bw <= ball * 3.5 and ball * 0.4 <= bh <= ball * 3.5):
            continue
        if area < ball * ball * 0.2:
            continue
        scores.append(abs(np.log(bw / max(bh, 1))))
    if not scores:
        return 9.9
    return float(np.median(sorted(scores)[:3]))       # 큰 것 몇 개만 (잡티 제외)


def find_corners(img: np.ndarray, cfg: dict) -> np.ndarray:
    """사진 → 당구대 4코너 (좌하, 우하, 우상, 좌상).

    당구장에는 당구대가 여러 대 있고, 대상 당구대가 화면 밖으로 잘리기도 한다.
    그래서 천 덩어리를 큰 것부터 몇 개 시도하고, **잘리지 않은** 것을 고른다.
    """
    mask = _cloth_mask(img, cfg)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise TableNotFound("천 색 영역을 못 찾았다 (data/vision.json 의 cloth_hsv 확인)")

    reasons = []
    for cnt in sorted(cnts, key=cv2.contourArea, reverse=True)[:3]:
        if cv2.contourArea(cnt) < mask.size * 0.02:
            break                                   # 너무 작으면 당구대가 아니다
        try:
            quad = _corners_of(cnt, mask, img.shape, cfg)
        except TableNotFound as e:
            reasons.append(str(e))
            continue
        return _pick_orientation(img, quad, cfg)
    raise TableNotFound("쓸 만한 당구대를 못 찾았다 — " + " / ".join(reasons or ["후보 없음"]))


def _pick_orientation(img: np.ndarray, quad: np.ndarray, cfg: dict) -> np.ndarray:
    """장쿠션/단쿠션이 뒤바뀌지 않았는지 공 모양으로 확인하고, 뒤바뀌었으면 돌린다."""
    alt = np.array([quad[1], quad[2], quad[3], quad[0]], np.float32)   # 한 칸 돌리기
    s0, s1 = _roundness(img, quad, cfg), _roundness(img, alt, cfg)
    if s1 < s0 - 0.12:                                # 뚜렷하게 더 동그랄 때만 바꾼다
        return alt
    return quad


def _corners_of(cnt, mask: np.ndarray, shape, cfg: dict) -> np.ndarray:
    """천 덩어리 하나 → 4코너. 잘렸거나 모양이 이상하면 TableNotFound.

    먼저 **다각형 근사**로 시도한다. 천 경계가 깨끗하면 이쪽이 훨씬 정확하다.
    사람·큐대가 경계를 물어뜯어 4각형이 안 나오면 직선 맞추기로 넘어간다.
    """
    hull = cv2.convexHull(cnt)

    peri = cv2.arcLength(hull, True)
    for eps in np.arange(0.005, 0.08, 0.002):
        ap = cv2.approxPolyDP(hull, eps * peri, True)
        if len(ap) == 4:
            try:
                return _validate(_order(ap.reshape(-1, 2).astype(np.float32), shape), shape)
            except TableNotFound:
                break                                # 근사는 됐지만 모양이 이상 -> 직선 방식으로
    return _corners_by_lines(hull, mask, shape, cfg)


def _validate(quad: np.ndarray, shape) -> np.ndarray:
    """잘렸거나 당구대 모양이 아니면 거른다."""
    h, w = shape[:2]
    m = 4
    if not all(-m <= p[0] <= w + m and -m <= p[1] <= h + m for p in quad):
        raise TableNotFound("당구대가 화면 밖으로 잘렸다 (코너가 프레임을 벗어남)")
    long_ = (np.linalg.norm(quad[1] - quad[0]) + np.linalg.norm(quad[2] - quad[3])) / 2
    short = (np.linalg.norm(quad[3] - quad[0]) + np.linalg.norm(quad[2] - quad[1])) / 2
    if short < 1:
        raise TableNotFound("사각형이 찌그러졌다")

    # ⚠️ 화면 위 변 길이로 재면 안 된다. 비스듬히 가까이서 찍으면 먼 쪽 장쿠션이
    #    짜부라져 0.34~2.93 까지 흔들린다 (2026-08-07 사진 28장 실측).
    #    원근을 되돌린 진짜 비로 잰다 — 같은 사진들에서 1.6~2.06 으로 나온다.
    real = _rect_aspect(quad, shape)
    if real is not None:
        r = max(real, 1 / real)
        if not 1.4 <= r <= 2.8:
            raise TableNotFound(f"모양이 당구대 같지 않다 (복원한 비 {r:.2f}, 2:1 이어야 함)")
    elif not 1.2 <= long_ / short <= 6.0:            # 복원 실패 시에만 예전 방식
        raise TableNotFound(f"모양이 당구대 같지 않다 (변 비율 {long_ / short:.2f})")
    return quad


def _corners_by_lines(hull, mask: np.ndarray, shape, cfg: dict) -> np.ndarray:
    """쿠션 4직선을 뽑아 교차시켜 코너를 구한다 (가림에 강한 대안)."""
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, [hull], -1, 255, -1)
    edges = cv2.morphologyEx(filled, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))

    c = cfg["corner"]
    # 최소 길이를 화면 가로에 비례시킨다. 2560px 기준 250 이 1280px 영상엔 너무 길다.
    min_len = max(50, int(shape[1] * float(c.get("hough_min_length_ratio", 0.10))))
    raw = cv2.HoughLinesP(edges, 1, np.pi / 360, c["hough_threshold"],
                          minLineLength=min_len, maxLineGap=c["hough_max_gap"])
    if raw is None or len(raw) < 4:
        raise TableNotFound("쿠션 직선을 4개 이상 못 찾았다")
    raw = np.asarray(raw).reshape(-1, 4)

    angles = np.array([np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180
                       for x1, y1, x2, y2 in raw], np.float32)
    # 각도는 순환값이라 2θ 로 펼쳐서 두 무리(장쿠션/단쿠션)로 나눈다
    feat = np.stack([np.cos(np.radians(2 * angles)), np.sin(np.radians(2 * angles))], 1)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
    _, labels, _ = cv2.kmeans(feat, 2, None, crit, 10, cv2.KMEANS_PP_CENTERS)
    labels = labels.ravel()

    groups = [[_line_of(s) for s, l in zip(raw, labels) if l == g] for g in (0, 1)]
    if not all(groups):
        raise TableNotFound("쿠션 직선이 한 방향으로만 잡혔다")

    A1, A2 = _extreme_lines(groups[0])
    B1, B2 = _extreme_lines(groups[1])
    pts = np.array([_intersect(A1, B1), _intersect(A1, B2),
                    _intersect(A2, B2), _intersect(A2, B1)], np.float32)
    return _validate(_order(pts, shape), shape)


def _nose_offset(profile: np.ndarray, limit: int) -> int:
    """바깥에서 안쪽으로 훑어 밝기 단차가 가장 큰 지점 = 쿠션 날."""
    smooth = cv2.GaussianBlur(profile.reshape(-1, 1).astype(np.float32), (1, 9), 0).ravel()
    return int(np.argmax(np.abs(np.diff(smooth))[:limit])) + 1


def warp(img: np.ndarray, quad: np.ndarray, cfg: dict, find_nose: bool = True) -> TopView:
    """4코너 → 2:1 상단뷰.

    ⚠️ 당구대를 화면에 **딱 맞춰** 펴면 안 된다. 공이 쿠션에 붙어 있으면 공의 일부가
       천 경계 바깥으로 나오는데, 딱 맞춰 펴면 그 부분이 잘려 크기·모양 조건에
       걸려 공을 통째로 놓친다 (2026-08-07 사진 28장 중 여러 장이 이 때문).
       그래서 사방에 여유(quad_pad_ratio)를 두고 펴고, 당구대 사각형이 그림 안
       어디에 있는지를 rect 로 들고 다닌다. mm 환산은 to_mm() 이 rect 로 한다.

    find_nose 는 이제 쓰지 않는다. 밝기 단차로 쿠션 날을 찾는 방식이 최대 180mm
    까지 어긋나 공을 잃게 만들었다 (0808.mp4 하단 66px). 천 경계를 그대로 쓴다.
    """
    w = int(cfg["warp"]["width_px"])
    h = w // 2                                   # 당구대는 장:단 = 2:1
    pad = int(h * float(cfg["warp"].get("quad_pad_ratio", 0.0)))
    W, H = w + 2 * pad, h + 2 * pad
    dst = np.array([[pad, h + pad], [w + pad, h + pad], [w + pad, pad], [pad, pad]],
                   np.float32)
    M = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    full = cv2.warpPerspective(img, M, (W, H))
    return TopView(image=full, full=full, quad=quad, homography=M,
                   inset=(pad, pad, w + pad, h + pad))

def detect(img: np.ndarray, cfg: dict | None = None) -> TopView:
    """사진 한 장 → 상단뷰."""
    cfg = cfg or load_config()
    return warp(img, find_corners(img, cfg), cfg)


def detect_file(path: Path | str, cfg: dict | None = None) -> TopView:
    img = cv2.imread(str(path))
    if img is None:
        raise TableNotFound(f"이미지를 못 읽었다: {path}")
    return detect(img, cfg)
