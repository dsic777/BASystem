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

        # 가운데 픽셀 하나는 반사광·모션블러에 흔들린다. 덩어리 평균색을 쓴다.
        # ⚠️ HSV 를 평균내면 안 된다 — 빨강은 H가 0과 179 를 오가서 평균이 90(청록)이 된다.
        #    BGR 을 평균낸 뒤 그 색 하나를 HSV 로 바꾼다.
        blob = (labels == i).astype(np.uint8)
        bgr = tuple(int(v) for v in cv2.mean(top_image, mask=blob)[:3])
        one = np.uint8([[list(bgr)]])
        hsv_of = tuple(int(v) for v in cv2.cvtColor(one, cv2.COLOR_BGR2HSV)[0, 0])
        name, label = _classify(hsv_of, cfg["ball_colors"]["rules"], bgr)
        out.append(Ball(name, label, cx / w, 1.0 - cy / h, area, bgr, hsv_of))

    out.sort(key=lambda b: -b.area)
    return out


RED_BAND = 12          # 색상환에서 이 안쪽이면 빨강 (0 또는 179 근처)


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
        return (h <= RED_BAND or h >= 180 - RED_BAND) and s >= 60

    reds = [b for b in balls if is_red(b)]
    rest = [b for b in balls if not is_red(b)]
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
