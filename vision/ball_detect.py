"""상단뷰 → 공 위치.

천 색이 아닌 덩어리를 찾아 크기·모양으로 거른 뒤, 색으로 흰공/노란공/빨간공을 가른다.
위치는 **정규화 좌표**(0~1)로 돌려준다 — 사진 속 당구대 크기와 무관하게 쓰려고.
    x: 0 = 왼쪽 쿠션, 1 = 오른쪽 쿠션
    y: 0 = 아래쪽 쿠션, 1 = 위쪽 쿠션   (화면 y와 반대. core/table.py 와 같은 방향)
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np

from vision.table_detect import load_config


@dataclass(frozen=True)
class Ball:
    name: str                      # white / yellow / red / unknown
    label: str                     # 흰공 / 노란공 / 빨간공
    nx: float                      # 정규화 x (0~1)
    ny: float                      # 정규화 y (0~1, 아래가 0)
    area: int
    bgr: tuple[int, int, int]      # 덩어리 평균 색
    hsv: tuple[int, int, int]      # 같은 색의 HSV (판정에 쓴 값)

    # ⚠️ 여기서 mm 로 바꾸면 안 된다. 상단뷰는 여유를 두고 편 그림이라 그림 전체가
    #    당구대가 아니다. 환산은 TopView.to_mm(nx, ny, w, h) 이 한다.


def _rule_mask(hsv_img: np.ndarray, rule: dict) -> np.ndarray:
    """규칙 하나를 HSV 이미지에 적용해 마스크를 만든다."""
    lo = (int(rule.get("h_min", 0)), int(rule.get("s_min", 0)), int(rule.get("v_min", 0)))
    hi = (int(rule.get("h_max", 179)), int(rule.get("s_max", 255)), int(rule.get("v_max", 255)))
    return cv2.inRange(hsv_img, lo, hi)


def ball_mask(hsv_img: np.ndarray, rules) -> np.ndarray:
    """공 색만 남긴 마스크.

    ⚠️ '천이 아닌 것' 으로 찾으면 큐대·쿠션 띠·사람이 공에 들러붙어 한 덩어리가 된다
       (실촬영본에서 검출 실패의 72%가 이것). 공 색으로 직접 찾으면 안 붙는다.
    """
    out = np.zeros(hsv_img.shape[:2], np.uint8)
    for rule in rules:
        out = cv2.bitwise_or(out, _rule_mask(hsv_img, rule))
    return out


def _classify(hsv, rules, bgr=None) -> tuple[str, str]:
    """HSV 로 공 색을 가른다. 규칙에 없는 항목은 검사하지 않는다.

    ⚠️ 흰공과 노란공은 채도만으로 못 가른다. 조명에 따라 흰공 채도가 71 까지,
       노란공이 90 까지 내려와 겹친다 (2026-08-07 사진). 파랑/빨강 비(B/R)를
       같이 본다 — 흰공 0.93~0.97, 노란공 0.23~0.73 으로 확실히 갈린다.
    """
    h, s, v = hsv
    br = (bgr[0] / bgr[2]) if bgr and bgr[2] else None
    for rule in rules:
        if s < rule.get("s_min", 0) or s > rule.get("s_max", 255):
            continue
        if v < rule.get("v_min", 0) or v > rule.get("v_max", 255):
            continue
        if not (rule.get("h_min", 0) <= h <= rule.get("h_max", 179)):
            continue
        if br is not None:
            if br < rule.get("br_min", 0.0) or br > rule.get("br_max", 9.9):
                continue
        return (rule["name"], rule["label"])
    return ("unknown", "미상")



def _split_touching(blob: np.ndarray, ball_px: float) -> list[np.ndarray]:
    """붙어 있는 공 덩어리를 나눈다.

    ⚠️ 3구는 공이 붙는 배치가 흔하다. 한 덩어리로 두면 크기·모양 조건에 걸려
       **둘 다 사라진다** (2026-08-08 사진 15장 중 6장이 이 경우).

    거리변환의 봉우리가 곧 공 중심이다. 봉우리를 씨앗으로 분수령을 돌려 가른다.
    """
    dist = cv2.distanceTransform(blob, cv2.DIST_L2, 5)
    r = ball_px / 2.0
    # 봉우리 = 반지름의 절반 이상 떨어진 곳. 공 하나면 하나, 둘이면 둘이 나온다.
    _, peaks = cv2.threshold(dist, r * 0.55, 255, cv2.THRESH_BINARY)
    peaks = peaks.astype(np.uint8)
    n, seeds = cv2.connectedComponents(peaks)
    if n <= 2:                                       # 배경 + 봉우리 하나 = 안 붙었다
        return [blob]

    markers = seeds.astype(np.int32) + 1
    markers[blob == 0] = 1                           # 배경
    rgb = cv2.cvtColor(blob * 255, cv2.COLOR_GRAY2BGR)
    cv2.watershed(rgb, markers)

    out = []
    for k in range(2, n + 1):
        part = np.where(markers == k, 1, 0).astype(np.uint8)
        if int(part.sum()) >= ball_px ** 2 * 0.25:
            out.append(part)
    return out or [blob]


def detect(top_image: np.ndarray, cfg: dict | None = None,
           ball_px: float | None = None) -> list[Ball]:
    """상단뷰(쿠션 날 안쪽) → 공 목록. 큰 것부터.

    ball_px  상단뷰에서 공 하나가 몇 px 인지. 주면 크기 기준을 여기에 맞춘다.
             ⚠️ 절대 픽셀로 박아두면 해상도·원근에 따라 다 걸러진다
                (실촬영본에서 공이 전부 탈락한 원인).
    """
    cfg = cfg or load_config()
    bcfg = cfg["ball"]
    h, w = top_image.shape[:2]

    if ball_px and ball_px > 4:
        # 원근으로 늘어나고, 조준 중에는 큐대가 붙어 한 덩어리가 된다.
        # 그런 프레임은 어차피 샷이 아니므로 넉넉히 받아두고 뒤에서 걸러낸다.
        lo_s, hi_s = ball_px * 0.45, ball_px * 3.3
        lo_a, hi_a = ball_px ** 2 * 0.25, ball_px ** 2 * 7.0
        open_k = 3
    else:
        lo_s, hi_s = bcfg["min_size"], bcfg["max_size"]
        lo_a, hi_a = bcfg["min_area"], bcfg["max_area"]
        open_k = 3

    hsv = cv2.cvtColor(top_image, cv2.COLOR_BGR2HSV)
    blobs = ball_mask(hsv, cfg["ball_colors"]["rules"])
    blobs = cv2.morphologyEx(blobs, cv2.MORPH_OPEN, np.ones((open_k,) * 2, np.uint8))
    blobs = cv2.morphologyEx(blobs, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    n, labels, stats, centroids = cv2.connectedComponentsWithStats(blobs, 8)
    margin = int(bcfg["border_margin"])
    out: list[Ball] = []

    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        bw = int(stats[i, cv2.CC_STAT_WIDTH])
        bh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if not (lo_a <= area <= hi_a):
            continue
        if not (lo_s <= bw <= hi_s and lo_s <= bh <= hi_s):
            continue
        if not 0.4 <= bw / bh <= 2.5:               # 원근·모션블러로 타원이 된다
            continue

        cx, cy = centroids[i]
        if not (margin < cx < w - margin and margin < cy < h - margin):
            continue                                 # 가장자리 = 쿠션 잔상
        blob = (labels == i).astype(np.uint8)

        # 가운데 픽셀 하나는 반사광·모션블러에 흔들린다. 덩어리 평균색을 쓴다.
        # ⚠️ HSV 를 평균내면 안 된다 — 빨강은 H가 0과 179 를 오가서 평균이 90(청록)이 된다.
        #    BGR 을 평균낸 뒤 그 색 하나를 HSV 로 바꾼다.
        bgr = tuple(int(v) for v in cv2.mean(top_image, mask=blob)[:3])
        one = np.uint8([[list(bgr)]])
        hsv_of = tuple(int(v) for v in cv2.cvtColor(one, cv2.COLOR_BGR2HSV)[0, 0])
        name, label = _classify(hsv_of, cfg["ball_colors"]["rules"], bgr)
        out.append(Ball(name, label, cx / w, 1.0 - cy / h, area, bgr, hsv_of))

    out.sort(key=lambda b: -b.area)
    return out


def _quad_mask(shape, quad: np.ndarray, pad: float) -> np.ndarray:
    """당구대 사각형 안쪽만 남기는 마스크. pad 만큼 바깥으로 넓힌다.

    옆 당구대·바닥 타일·사람 옷이 공 색에 걸리므로 먼저 잘라낸다.
    쿠션에 붙은 공은 중심이 안쪽이어도 몸통이 사각형 밖으로 나가므로 조금 넓힌다.
    """
    q = np.asarray(quad, np.float64)
    c = q.mean(axis=0)
    big = c + (q - c) * (1.0 + pad)
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillConvexPoly(m, big.astype(np.int32), 255)
    return m


def _local_ball_px(H: np.ndarray, Hinv: np.ndarray, p, ball_full_px: float) -> float:
    """사진의 그 자리에서 공이 몇 px 로 보이는지.

    공은 구(球)라 사진에서 언제나 동그랗게 나온다. 크기는 거리로만 정해진다.
    상단뷰에서 공 지름만큼 떨어진 두 방향을 사진으로 되돌려 재고, **긴 쪽**을 쓴다
    (짧은 쪽은 원근으로 눌린 깊이 방향이라 공의 겉보기 크기가 아니다).
    """
    def fwd(pt, M):
        v = M @ np.array([pt[0], pt[1], 1.0])
        return np.array([v[0] / v[2], v[1] / v[2]])

    q = fwd(p, H)
    a = fwd(q + np.array([ball_full_px, 0.0]), Hinv)
    b = fwd(q + np.array([0.0, ball_full_px]), Hinv)
    return float(max(np.hypot(*(a - p)), np.hypot(*(b - p))))


def detect_photo(photo: np.ndarray, top, cfg: dict | None = None,
                 ball_mm: float = 61.5, table_mm: float = 2448.0) -> list[Ball]:
    """원본 사진에서 공을 찾아 중심점만 상단뷰 좌표로 옮긴다.

    ⚠️ 상단뷰에서 찾으면 안 된다. 카메라가 낮으면 먼 쪽 쿠션이 심하게 눌려 있고,
       그걸 펴면 공이 3배로 늘어난 타원이 되어 크기·모양 조건에 전부 걸린다
       (2026-08-08 당구장 사진 15장 중 7장이 이것). 원본에서는 공이 동그랗다.
       늘어나지 않는 것은 **점 하나**뿐이므로 중심만 옮긴다.
    """
    cfg = cfg or load_config()
    bcfg = cfg["ball"]
    H = np.asarray(top.homography, np.float64)
    Hinv = np.linalg.inv(H)

    left, up, right, down = top.inset
    ball_full = ball_mm / table_mm * (right - left)          # 상단뷰에서의 공 지름

    hsv = cv2.cvtColor(photo, cv2.COLOR_BGR2HSV)
    # ⚠️ 여유를 넓히면 쿠션 나무가 더 들어와 빨간공 자리를 뺏는다
    #    (0.06 으로 키웠더니 15장 중 15→13 으로 나빠졌다).
    inside = _quad_mask(photo.shape, top.quad, 0.02)
    k = np.ones((5, 5), np.uint8)
    ih, iw = top.image.shape[:2]
    margin = int(bcfg["border_margin"])
    out: list[Ball] = []

    # ★ 색깔별로 따로 찾는다. 한 마스크에 다 넣으면 빨간공과 노란공이 닿아 있을 때
    #    (특히 초점이 나간 사진) 한 덩어리가 되어 크기 조건에 걸려 둘 다 사라진다
    #    (2026-08-08 191852). 3구는 색이 셋 다 다르므로 색으로 먼저 가르는 게 맞다.
    groups: dict[str, list[dict]] = {}
    for rule in cfg["ball_colors"]["rules"]:
        groups.setdefault(rule["name"], []).append(rule)

    parts: list[tuple[np.ndarray, bool]] = []
    for rules in groups.values():
        blobs = cv2.bitwise_and(ball_mask(hsv, rules), inside)
        blobs = cv2.morphologyEx(blobs, cv2.MORPH_OPEN, k)
        blobs = cv2.morphologyEx(blobs, cv2.MORPH_CLOSE, k)
        n, labels, stats, cents = cv2.connectedComponentsWithStats(blobs, 8)
        for i in range(1, n):
            d = _local_ball_px(H, Hinv,
                               (float(cents[i][0]), float(cents[i][1])), ball_full)
            area = int(stats[i, cv2.CC_STAT_AREA])
            if d < 4 or area < d * d * 0.2:
                continue
            one = (labels == i).astype(np.uint8)
            if area > d * d * 1.1:                       # 같은 색끼리 붙었을 수도
                cut = _split_touching(one, d)
                parts.extend((c, len(cut) > 1) for c in cut)
            else:
                parts.append((one, False))

    for m, was_split in parts:
        ys, xs = np.nonzero(m)
        if not len(xs):
            continue
        cx, cy = float(xs.mean()), float(ys.mean())
        d = _local_ball_px(H, Hinv, (cx, cy), ball_full)
        if d < 4:
            continue
        area = int(m.sum())
        bw = int(xs.max() - xs.min()) + 1
        bh = int(ys.max() - ys.min()) + 1
        # 나뉜 조각은 이미 공 크기를 기준으로 갈랐으므로 조건을 조금 푼다.
        # 안 그러면 붙었던 공 중 한쪽만 살아남는다 (2026-08-08 191852).
        hi_a, hi_s, hi_r = (4.0, 2.6, 2.6) if was_split else (3.0, 2.2, 2.0)
        if not (d * d * 0.2 <= area <= d * d * hi_a):
            continue
        if not (d * 0.4 <= bw <= d * hi_s and d * 0.4 <= bh <= d * hi_s):
            continue
        if not 1.0 / hi_r <= bw / bh <= hi_r:                # 사진 속 공은 동그랗다
            continue

        v = H @ np.array([cx, cy, 1.0])                      # 상단뷰(full)로 옮긴다
        fx, fy = v[0] / v[2], v[1] / v[2]
        if not (margin < fx < iw - margin and margin < fy < ih - margin):
            continue
        # 공 중심은 쿠션 날에서 최소 반지름만큼 안쪽에 있다. 그보다 밖이면 쿠션 나무다.
        # ⚠️ 여기를 지름만큼 풀고 안으로 끌어당겨 봤더니 나무가 통과해 코너에
        #    공으로 붙었다 (2026-08-09). 밖으로 나간 것은 그냥 버린다.
        tx = (fx - left) / max(right - left, 1)
        ty = (fy - up) / max(down - up, 1)
        rx = ball_mm / 2 / table_mm * 0.2
        ry = rx * (right - left) / max(down - up, 1)
        if not (rx < tx < 1 - rx and ry < ty < 1 - ry):
            continue

        bgr = tuple(int(x) for x in cv2.mean(photo, mask=m)[:3])
        one = np.uint8([[list(bgr)]])
        hsv_of = tuple(int(x) for x in cv2.cvtColor(one, cv2.COLOR_BGR2HSV)[0, 0])
        name, label = _classify(hsv_of, cfg["ball_colors"]["rules"], bgr)
        out.append(Ball(name, label, fx / iw, 1.0 - fy / ih, area, bgr, hsv_of))

    out.sort(key=lambda b: -b.area)
    return _merge_near(out, ball_full / max(iw, 1))


def _merge_near(balls: list[Ball], nd: float) -> list[Ball]:
    """공 지름 안에 겹쳐 잡힌 것들은 한 공으로 본다. 큰 쪽을 남긴다.

    초점이 나가거나 반사광이 있으면 공 하나가 두 덩어리로 갈라지고, 갈라진 조각은
    평균색이 달라져 서로 다른 색으로 판정되기도 한다. 그래서 **색은 안 본다.**
    ⚠️ 붙어 있는 두 공은 중심이 정확히 지름만큼 떨어져 있으므로 기준은 그보다 작아야 한다.
    """
    kept: list[Ball] = []
    for b in balls:                                      # 큰 것부터 들어온다
        if any(np.hypot(a.nx - b.nx, (a.ny - b.ny) / 2) < nd * 0.75 for a in kept):
            continue
        kept.append(b)
    return kept



# 빨강으로 볼 색상(H) 범위. ⚠️ data/vision.json 의 red 규칙과 반드시 같아야 한다.
#    규칙은 0~9 / 160~179 인데 여기만 0~12 / 168~179 였다가, H=164 인 빨간공이
#    그 틈에 빠져 노란공이 되었다 (2026-08-08 192102).
RED_LO = 9             # 이 이하면 빨강
RED_HI = 160           # 이 이상이면 빨강


def resolve(balls: list[Ball]) -> list[Ball]:
    """검출된 덩어리들을 **서로 비교해서** 흰공/노란공/빨간공으로 가른다.

    ⚠️ '채도 50 이하면 흰공' 같은 절대 기준은 조명이 바뀌면 통째로 깨진다
       (2026-08-07 사진: 흰공 채도가 12~71 로 흔들려 6장에서 흰공이 사라짐).
       사람 눈이 하는 대로 셋을 서로 견준다 — 제일 덜 물든 것이 흰공,
       제일 진한 것이 노란공. 조명이 어떻든 순서는 안 바뀐다.

    빨간공은 색상(H)만으로 확실히 갈리므로 먼저 빼낸다.
    """
    if not balls:
        return balls

    def is_red(b):
        h, s, _v = b.hsv
        return (h <= RED_LO or h >= RED_HI) and s >= 60

    # 3구는 흰·노·빨 하나씩이다. 반사광이나 큐대로 조각이 더 잡히면 큰 것만 남긴다.
    reds = sorted((b for b in balls if is_red(b)), key=lambda b: -b.area)[:1]
    rest = sorted((b for b in balls if not is_red(b)), key=lambda b: -b.area)[:2]
    out = [replace(b, name="red", label="빨간공") for b in reds]

    if len(rest) >= 2:
        rest.sort(key=lambda b: b.hsv[1])              # 채도 낮은 순
        out.append(replace(rest[0], name="white", label="흰공"))
        for b in rest[1:]:
            out.append(replace(b, name="yellow", label="노란공"))
    elif len(rest) == 1:
        b = rest[0]
        white = b.hsv[1] < 85                          # 견줄 상대가 없으면 절대 기준
        out.append(replace(b, name="white" if white else "yellow",
                           label="흰공" if white else "노란공"))
    return sorted(out, key=lambda b: -b.area)


def assign(balls: list[Ball], cue: Ball | None = None) -> dict[str, Ball]:
    """검출된 공을 수구/적구1/적구2 로 배정한다.

    cue 를 주면 그 공이 수구다 (큐대가 겨냥하고 있는 공).
    안 주면 흰공을 수구로 본다 — 사용자 확정 규칙.
    ⚠️ 적색공은 어떤 경우에도 수구가 아니다.
    """
    if cue is not None and cue.name == "red":
        cue = None

    out: dict[str, Ball] = {}
    rest = list(balls)                               # 이미 큰 것부터 정렬돼 있다

    if cue is not None:
        out["cue"] = cue
        rest = [b for b in rest if b is not cue]
    else:
        for b in rest:
            if b.name == "white":
                out["cue"] = b
                rest = [x for x in rest if x is not b]
                break

    for key in ("obj1", "obj2"):
        for b in rest:
            if b.name in ("white", "yellow", "red"):
                out[key] = b
                rest = [x for x in rest if x is not b]
                break
    return out
