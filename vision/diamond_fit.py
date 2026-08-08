"""다이아몬드로 코너를 푼다.

⚠️ 천 경계로 잡은 코너는 믿을 수 없다. 조명·천 색·원근에 따라 흔들리고, 코너가
   흔들리면 **공은 제대로 찾아도 좌표가 통째로 밀린다** (2026-08-08 사진 15장에서
   해상도만 바꿔도 최대 280mm 이동).

영상에서는 공 자신이 자였다 (track.calibrate — 쿠션에서 되돌아 나온 자리의 중앙값이
곧 반지름 거리). 사진 한 장에는 그 자가 없다. 대신 **다이아몬드**가 있다.
다이아몬드는 규격상 장쿠션 8등분·단쿠션 4등분 자리, 노즈에서 바깥으로 frame_offset
만큼 나간 곳에 박혀 있다. 자리를 아는 점이 최대 18개다.

그래서 코너 4점을 미는 대신, **찾은 다이아몬드 전부로 호모그래피를 최소제곱으로 푼다.**
몇 개를 놓쳐도 나머지가 메운다.
"""

from __future__ import annotations

import cv2
import numpy as np


def expected_diamonds(table) -> list[tuple[float, float, str, int]]:
    """(x_mm, y_mm, rail, index) — 코너의 0·끝 번호는 뺀다 (두 레일이 겹쳐 애매하다)."""
    out = []
    for rail, n in (("bottom", table.long_divisions), ("top", table.long_divisions),
                    ("left", table.short_divisions), ("right", table.short_divisions)):
        for i in range(1, n):
            x, y = table.diamond_position(rail, i)
            out.append((float(x), float(y), rail, i))
    return out


def _dlt(src: np.ndarray, dst: np.ndarray) -> np.ndarray | None:
    """점 4쌍 이상 → 호모그래피 (최소제곱). src, dst 는 (N,2)."""
    n = len(src)
    if n < 4:
        return None
    # 수치 안정을 위해 각각 평균 0, 평균거리 √2 로 정규화한다 (Hartley)
    def norm(p):
        c = p.mean(axis=0)
        s = np.sqrt(2) / max(np.linalg.norm(p - c, axis=1).mean(), 1e-9)
        T = np.array([[s, 0, -s * c[0]], [0, s, -s * c[1]], [0, 0, 1]])
        q = (T @ np.hstack([p, np.ones((n, 1))]).T).T
        return q[:, :2], T

    a, Ta = norm(src)
    b, Tb = norm(dst)
    A = np.zeros((2 * n, 9))
    for i in range(n):
        x, y = a[i]
        u, v = b[i]
        A[2 * i] = [-x, -y, -1, 0, 0, 0, u * x, u * y, u]
        A[2 * i + 1] = [0, 0, 0, -x, -y, -1, v * x, v * y, v]
    _, _, vt = np.linalg.svd(A)
    H = vt[-1].reshape(3, 3)
    H = np.linalg.inv(Tb) @ H @ Ta
    return H / H[2, 2] if abs(H[2, 2]) > 1e-12 else None


def _apply(H: np.ndarray, pts: np.ndarray) -> np.ndarray:
    q = (H @ np.hstack([pts, np.ones((len(pts), 1))]).T).T
    return q[:, :2] / q[:, 2:3]


def _find_dot(gray: np.ndarray, cx: float, cy: float, win: int) -> tuple[float, float, float] | None:
    """(cx,cy) 둘레 win 안에서 제일 밝은 점의 무게중심. 대비가 약하면 None.

    다이아몬드는 어두운 나무 위의 흰 점이다. 창 안에서 밝기 상위만 남겨 무게중심을
    잡는다 — 이렇게 하면 점의 크기·모양이 달라도 중심이 흔들리지 않는다.
    """
    h, w = gray.shape
    x0, x1 = int(max(0, cx - win)), int(min(w, cx + win + 1))
    y0, y1 = int(max(0, cy - win)), int(min(h, cy + win + 1))
    if x1 - x0 < 5 or y1 - y0 < 5:
        return None
    patch = gray[y0:y1, x0:x1].astype(np.float32)
    lo, hi = float(patch.min()), float(patch.max())
    if hi - lo < 25:                                  # 나무와 구분이 안 된다
        return None
    thr = lo + (hi - lo) * 0.72
    m = patch >= thr
    if m.sum() < 3 or m.sum() > m.size * 0.5:         # 없거나, 창 전체가 밝으면 못 믿는다
        return None
    ys, xs = np.nonzero(m)
    wgt = patch[ys, xs] - thr
    s = float(wgt.sum())
    if s <= 0:
        return None
    return (x0 + float((xs * wgt).sum() / s),
            y0 + float((ys * wgt).sum() / s),
            (hi - lo))


PPMM = 0.5            # 편 그림 축척 (px per mm). 다이아몬드 간격 306mm → 153px
MARGIN_MM = 200.0     # 레일(프레임 90mm)이 다 들어오도록 사방 여유


def _flatten(img: np.ndarray, H: np.ndarray, table):
    """사진 → 당구대 mm 를 기준으로 편 흑백 그림. (그림, mm→그림px 변환) 을 준다.

    어디서나 1mm 가 같은 픽셀 수라 다이아몬드를 같은 기준으로 찾을 수 있다.
    """
    W = int((table.width + 2 * MARGIN_MM) * PPMM)
    Hh = int((table.height + 2 * MARGIN_MM) * PPMM)
    M = np.array([[PPMM, 0, MARGIN_MM * PPMM],
                  [0, -PPMM, (table.height + MARGIN_MM) * PPMM],   # mm 는 위가 +
                  [0, 0, 1]], np.float64)
    try:
        Hinv = np.linalg.inv(H)
    except np.linalg.LinAlgError:
        return None, M
    flat = cv2.warpPerspective(img, M @ Hinv, (W, Hh))
    return cv2.GaussianBlur(cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY), (3, 3), 0), M


def fit(img: np.ndarray, quad: np.ndarray, table,
        rounds: int = 3, keep_rails: tuple[str, ...] | None = None):
    """천 경계 코너(quad) → 다이아몬드로 다시 푼 코너.

    keep_rails 를 주면 그 레일의 다이아몬드만 쓴다 (교차검증용).
    반환: (새 quad, 쓴 점 수, 잔차 mm 중앙값) — 실패하면 (원래 quad, 0, None)
    """
    corners_mm = np.array([[0, 0], [table.width, 0],
                           [table.width, table.height], [0, table.height]], np.float64)
    H = _dlt(corners_mm, np.asarray(quad, np.float64))        # mm → 사진
    if H is None:
        return np.asarray(quad, np.float32), 0, None

    want = [d for d in expected_diamonds(table)
            if keep_rails is None or d[2] in keep_rails]
    if len(want) < 6:
        return np.asarray(quad, np.float32), 0, None
    want_mm = np.array([[d[0], d[1]] for d in want], np.float64)

    # ⚠️ 원본 사진에서 찾으면 안 된다. 먼 쪽은 창이 몇 px 이고 가까운 쪽은 수십 px 라
    #    같은 기준으로 못 찾는다. **편 그림**에서 찾으면 어디서나 1mm 가 같은 크기다.
    used_mm = used_px = None
    for _ in range(rounds):
        flat, M = _flatten(img, H, table)                      # mm → 편 그림 px
        if flat is None:
            break
        win = int(max(8, table.width / table.long_divisions * PPMM * 0.32))
        Minv = np.linalg.inv(M)

        hits_mm, hits_px = [], []
        for mx, my in want_mm:
            fx, fy = _apply(M, np.array([[mx, my]]))[0]
            got = _find_dot(flat, fx, fy, win)
            if got is None:
                continue
            # 예상 자리에서 너무 멀면 다른 것을 집은 것이다
            if np.hypot(got[0] - fx, got[1] - fy) > win * 0.7:
                continue
            back = _apply(Minv, np.array([[got[0], got[1]]]))[0]   # 편 그림 → mm
            px, py = _apply(H, np.array([[back[0], back[1]]]))[0]  # mm → 사진
            hits_mm.append([mx, my])
            hits_px.append([px, py])
        if len(hits_mm) < 6:
            break
        mm_a = np.array(hits_mm)
        px_a = np.array(hits_px)
        newH = _dlt(mm_a, px_a)
        if newH is None:
            break

        # ⚠️ 이상점을 안 걸러내면 안 된다. 나무 레일의 반사광이나 흰 쿠션 띠를
        #    다이아몬드로 잘못 집으면 그 한 점이 코너 전체를 끌고 간다
        #    (2026-08-08 191956: 잔차 15mm → 170mm 로 나빠졌다).
        for _ in range(2):
            try:
                inv = np.linalg.inv(newH)
            except np.linalg.LinAlgError:
                break
            back = _apply(inv, px_a)
            err = np.linalg.norm(back - mm_a, axis=1)
            med = float(np.median(err))
            keep = err <= max(20.0, med * 2.0)
            if keep.all() or keep.sum() < 6:
                break
            mm_a, px_a = mm_a[keep], px_a[keep]
            h2 = _dlt(mm_a, px_a)
            if h2 is None:
                break
            newH = h2

        used_mm, used_px, H = mm_a, px_a, newH

    if used_mm is None or len(used_mm) < 8:
        return np.asarray(quad, np.float32), 0, None

    # 잔차는 mm 로 잰다 (사진 px 는 자리마다 축척이 달라 비교가 안 된다)
    try:
        Hinv = np.linalg.inv(H)
    except np.linalg.LinAlgError:
        return np.asarray(quad, np.float32), 0, None
    back = _apply(Hinv, used_px)
    resid = float(np.median(np.linalg.norm(back - used_mm, axis=1)))
    if resid > 25.0:                     # 이만큼 안 맞으면 다이아몬드를 잘못 집은 것이다
        return np.asarray(quad, np.float32), 0, None
    new_quad = _apply(H, corners_mm)                          # mm 코너 → 사진 좌표
    return new_quad.astype(np.float32), len(used_mm), resid


def residual_mm(quad: np.ndarray, table, img: np.ndarray,
                rails: tuple[str, ...]) -> float | None:
    """주어진 코너로 만든 좌표계에서 그 레일 다이아몬드가 제자리에 있는지 (mm)."""
    corners_mm = np.array([[0, 0], [table.width, 0],
                           [table.width, table.height], [0, table.height]], np.float64)
    H = _dlt(corners_mm, np.asarray(quad, np.float64))
    if H is None:
        return None
    want = [d for d in expected_diamonds(table) if d[2] in rails]
    want_mm = np.array([[d[0], d[1]] for d in want], np.float64)
    flat, M = _flatten(img, H, table)
    if flat is None:
        return None
    Minv = np.linalg.inv(M)
    win = int(max(8, table.width / table.long_divisions * PPMM * 0.32))
    errs = []
    for mm in want_mm:
        fx, fy = _apply(M, np.array([[mm[0], mm[1]]]))[0]
        got = _find_dot(flat, fx, fy, win)
        if got is None or np.hypot(got[0] - fx, got[1] - fy) > win * 0.7:
            continue
        back = _apply(Minv, np.array([[got[0], got[1]]]))[0]
        errs.append(float(np.linalg.norm(back - mm)))
    return float(np.median(errs)) if len(errs) >= 3 else None
