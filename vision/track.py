"""영상에서 공 궤적을 뽑아낸다 (로드맵 0.5단계).

    영상 → 당구대 검출(한 번) → 프레임마다 공 추적 → 쿠션 접점 → 번호·각도

왜 영상인가
    2쿠션 위치는 눈으로 정확히 짚기 어렵다 (사용자 확인). 영상이면 프레임마다
    수백 개 점이 나오므로, 구간마다 **직선을 맞춰서** 접점을 교점으로 구할 수 있다.
    캡처 몇 장으로 재는 것보다 훨씬 정확하다.

카메라는 고정이라고 본다. 당구대 검출은 여러 프레임에서 해 중앙값을 쓴다.
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from dataclasses import dataclass, field

import cv2
import numpy as np

from vision import ball_detect, table_detect
from vision.table_detect import TopView, load_config, warp


@dataclass
class Contact:
    """공이 쿠션에 닿은 지점."""

    rail: str                        # bottom / right / top / left
    point: tuple[float, float]       # 접점 (mm, 쿠션 날 위)
    frame: int                       # 가장 가까웠던 프레임
    incoming: float | None = None    # 입사각 (쿠션 법선 기준, 도)
    outgoing: float | None = None    # 반사각
    speed_in: float | None = None    # 들어올 때 속도 (mm/s)
    speed_out: float | None = None   # 나갈 때 속도 (mm/s)
    # 들어오는 직선 (지나는 점, 단위방향). 1쿠션의 이 선이 곧 '큐선'이라
    # 앞뒤로 늘이면 수구수와 1쿠션수를 그대로 읽어낼 수 있다.
    in_line: tuple[tuple[float, float], tuple[float, float]] | None = None

    @property
    def spin_gain(self) -> float | None:
        """반사각 − 입사각. 회전 때문에 벌어진 양."""
        if self.incoming is None or self.outgoing is None:
            return None
        return self.outgoing - self.incoming


@dataclass
class Track:
    """한 번의 샷."""

    start_frame: int
    end_frame: int
    points: list[tuple[int, float, float]] = field(default_factory=list)  # (frame, x, y) mm
    contacts: list[Contact] = field(default_factory=list)
    fps: float = 30.0
    # 이 궤적이 어느 공인가 (white/yellow/red). 검출된 색의 다수결.
    # ★ 사용자 확정 2026-08-10: 흰공 = 수구, 빨간공 = 1적구.
    #   색을 알면 '먼저 움직인 쪽이 수구' 라고 추측할 필요가 없다.
    ball: str | None = None

    @property
    def path(self) -> list[tuple[float, float]]:
        return [(x, y) for _, x, y in self.points]

    @property
    def peak_speed(self) -> float:
        """이 샷의 최고 속도 (mm/s). 손으로 옮긴 것과 실제로 친 것을 가르는 값."""
        best = 0.0
        for a, b in zip(self.points, self.points[1:]):
            df = b[0] - a[0]
            if df <= 0:
                continue
            v = float(np.hypot(b[1] - a[1], b[2] - a[2])) / df * self.fps
            best = max(best, v)
        return best

    def speed(self, i: int, j: int) -> float | None:
        """구간 [i, j] 의 평균 속도 (mm/s). 속도에 따라 각이 달라지므로 같이 잰다."""
        if j <= i or j >= len(self.points):
            return None
        dist = sum(float(np.hypot(b[1] - a[1], b[2] - a[2]))
                   for a, b in zip(self.points[i:j], self.points[i + 1:j + 1]))
        frames = self.points[j][0] - self.points[i][0]
        return dist / frames * self.fps if frames > 0 else None


# --------------------------------------------------------------------- 검출


def table_from_quad(cap: cv2.VideoCapture, quad: np.ndarray, cfg: dict) -> TopView:
    """사람이 찍어 둔 코너로 상단뷰를 만든다 (자동 검출보다 확실)."""
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError("첫 프레임을 못 읽었다")
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    # 사람이 쿠션 날을 직접 찍은 코너다. 밝기로 날을 다시 찾을 필요가 없다.
    return warp(frame, np.asarray(quad, dtype=np.float32), cfg, find_nose=False)


def detect_table(cap: cv2.VideoCapture, cfg: dict, samples: int = 9) -> TopView:
    """여러 프레임에서 당구대를 잡아 중앙값 코너를 쓴다 (사람·큐대 가림에 강하게)."""
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    quads, frame0 = [], None
    for k in range(samples):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (k + 0.5) / samples))
        ok, frame = cap.read()
        if not ok:
            continue
        if frame0 is None:
            frame0 = frame
        try:
            quads.append(table_detect.find_corners(frame, cfg))
        except table_detect.TableNotFound:
            continue
    if not quads:
        raise table_detect.TableNotFound("영상 어느 프레임에서도 당구대를 못 찾았다")

    quad = np.median(np.stack(quads), axis=0).astype(np.float32)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    return table_detect.warp(frame0, quad, cfg)


def _warp_frame(frame: np.ndarray, top: TopView) -> np.ndarray:
    """같은 호모그래피로 프레임을 펴고 쿠션 날 안쪽만 잘라낸다."""
    h, w = top.full.shape[:2]
    full = cv2.warpPerspective(frame, top.homography, (w, h))
    left, up, right, down = top.inset
    return full[up:down, left:right]


KNOWN = ("white", "yellow", "red")


def track_video(path: str, table_width: float, table_height: float,
                cfg: dict | None = None, max_jump_mm: float = 900.0,
                min_move_mm: float = 8.0, step: int = 1,
                relost_frames: int = 6,
                quad: np.ndarray | None = None,
                verbose: bool = True,
                ball_diameter_mm: float | None = None,
                first_frame: int = 0,
                last_frame: int | None = None,
                only: tuple[str, ...] | None = None,
                keep_tail: bool = False,
                max_traces: int = 6,
                max_detections: int | None = None) -> tuple[TopView, list[Track]]:
    """영상 → (상단뷰, 샷 목록).

    공을 **전부** 따라가고, 그 중 실제로 움직인 것만 샷으로 남긴다.
    ⚠️ 큐대 검출에 기대면 안 된다. 실패하면 안 움직이는 공을 붙잡고
       영상 내내 그것만 따라가게 된다 (합성 영상 시험에서 드러난 문제).

    max_jump_mm  한 프레임에 이만큼 넘게 튀면 다른 공으로 본다
    min_move_mm  이보다 덜 움직이면 멈춘 것으로 본다
    """
    cfg = cfg or load_config()
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 못 열었다: {path}")

    top = table_from_quad(cap, quad, cfg) if quad is not None else detect_table(cap, cfg)

    # ⚠️ 첫 프레임에 공이 없을 수 있다 (촬영 시작 후 공을 놓는 경우).
    #    공이 나올 때까지 넘어가고, 중간에 새로 나타난 공도 새 궤적으로 잡는다.
    traces: list[list[tuple[int, float, float]]] = []
    tnames: list[Counter] = []          # 궤적별로 어느 색이 몇 번 잡혔나
    misses: list[int] = []
    extra_run = 0            # 공이 궤적 수보다 많이 보인 연속 프레임 수
    skipped_busy = 0         # 사람이 들어와 통째로 건너뛴 프레임 수

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    cap_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    # 상단뷰에서 공 하나가 몇 px 인지 — 크기 기준을 여기에 맞춘다
    ball_px = ball_diameter_mm / table_width * top.size[0] if ball_diameter_mm else None
    if verbose:
        print(f"  상단뷰 공 크기 {ball_px:.1f}px" if ball_px else "")
    t0 = time.time()

    stop_at = last_frame if last_frame is not None else total
    if first_frame:
        cap.set(cv2.CAP_PROP_POS_FRAMES, first_frame)
    idx = first_frame - 1
    while True:
        ok, frame = cap.read()
        if not ok or (stop_at and idx >= stop_at):
            break
        idx += 1
        if step > 1 and idx % step:
            continue
        if verbose and idx % 600 == 0 and total:
            el = time.time() - t0
            frac = max(idx / total, 1e-6)
            eta = el / frac - el
            sys.stdout.write(f"\r  추적 {idx:,}/{total:,} ({frac*100:5.1f}%)"
                             f"  경과 {el/60:4.1f}분  남은 {eta/60:4.1f}분"
                             f"  궤적 {len(traces)}개  ")
            sys.stdout.flush()
        # ⚠️ 손·큐대가 흰공으로 잡힌다 (채도 50 이하·밝기 190 이상이면 흰공 규칙에
        #    걸린다). 그 가짜 검출이 새 궤적을 만들고, 그 궤적이 진짜 공의 검출을
        #    뺏어가 샷이 중간에서 잘린다 (실촬영본: 4쿠션 샷이 2쿠션에서 끊김).
        #    영상에 쓴 공이 정해져 있으면 only 로 못 박는다.
        # ⚠️ 여기서 '공 중심은 쿠션 안쪽에 있을 수 없다'는 물리 제약을 걸면 안 된다.
        #    보정 전 좌표라 쿠션 근처가 몇십 mm 어긋나 있어서, 공이 쿠션에 닿는
        #    바로 그 순간을 통째로 버리게 된다. 제약은 보정 뒤에나 뜻이 있다.
        want = only or KNOWN
        det = [(top.to_mm(b.nx, b.ny, table_width, table_height), b.name)
               for b in ball_detect.detect(_warp_frame(frame, top), cfg, ball_px)
               if b.name in want]
        found = [q for q, _ in det]
        fname = [n for _, n in det]
        # ★ 손·팔이 들어온 프레임을 통째로 버린다 (사용자 지적 2026-08-10).
        #   공을 손으로 옮기는 장면에서 팔이 **흰공 여러 개**로 잡힌다 (한 프레임에
        #   10개까지 봤다). --ball 로 색을 못 박아도 소용없다 — 손이 '흰공' 이다.
        #   0808 은 그 장면을 사용자가 다 잘라내서 문제가 안 드러났다.
        #   공 개수를 아는 촬영(예: 두 공)에서는 그보다 많이 보이는 프레임이 곧
        #   '사람이 들어온 프레임' 이다. 건너뛰면 궤적은 놓친 것으로 처리된다.
        if max_detections is not None and len(found) > max_detections:
            found = []
            skipped_busy += 1
        if not traces:
            traces = [[(idx, *p)] for p in found[:max_traces]]
            tnames = [Counter([fname[i]]) for i in range(len(traces))]
            misses = [0] * len(traces)
            continue
        # ⚠️ 슬롯 순서대로 짝지으면 안 된다. 공이 다른 공 옆을 지날 때
        #    (합성 영상에서 3쿠션이 흰공과 92mm) 서로 뒤바뀐다.
        #    전체 쌍을 거리순으로 정렬해 가까운 것부터 확정한다.
        pairs = sorted(
            (float(np.hypot(p[0] - tr[-1][1], p[1] - tr[-1][2])), si, i)
            for si, tr in enumerate(traces) for i, p in enumerate(found)
        )
        used_slot: set[int] = set()
        used_det: set[int] = set()
        for d, si, i in pairs:
            if si in used_slot or i in used_det:
                continue
            # 오래 놓친 슬롯은 거리 제한을 풀어준다.
            # 영상을 이어붙인 경우 컷 지점에서 공이 확 튀는데, 그때 다시 붙잡으려면 필요하다.
            if d >= max_jump_mm and misses[si] < relost_frames:
                continue
            used_slot.add(si)
            used_det.add(i)
            traces[si].append((idx, *found[i]))
            tnames[si][fname[i]] += 1
        for si in range(len(traces)):
            misses[si] = 0 if si in used_slot else misses[si] + 1

        # ⚠️ 짝 못 찾은 검출을 곧바로 새 궤적으로 만들면 안 된다. 공이 잠깐
        #    안 보이다 멀리서 다시 나타나면 궤적이 조각나 가짜 샷이 생긴다.
        # ⚠️ 이미 따라가고 있는 공 **바로 옆**에 생긴 검출로 새 궤적을 만들어도
        #    안 된다. 공 하나를 궤적 여럿이 따라가면 매 프레임 검출을 서로
        #    뺏어가고, 뺏긴 궤적은 그 자리에서 끊긴다 (실촬영본: 공 하나에
        #    궤적 3개, 샷이 2쿠션에서 잘림).
        min_apart = (ball_diameter_mm or 60.0) * 3.0
        spare = [i for i in range(len(found)) if i not in used_det
                 and all(np.hypot(found[i][0] - tr[-1][1], found[i][1] - tr[-1][2]) > min_apart
                         for tr in traces)]
        extra_run = extra_run + 1 if spare else 0
        if spare and extra_run >= 5 and len(traces) < max_traces:
            traces.append([(idx, *found[spare[0]])])
            tnames.append(Counter([fname[spare[0]]]))
            misses.append(0)
            extra_run = 0
    cap.release()
    if verbose and total:
        sys.stdout.write(f"\r  추적 완료 {total:,}프레임  {(time.time()-t0)/60:.1f}분"
                         f"  궤적 {len(traces)}개{' ' * 20}\n")

    if ball_diameter_mm:
        calibrate(traces, table_width, table_height, ball_diameter_mm, verbose)

    fps = cap_fps if cap_fps > 1 else 30.0
    shots: list[Track] = []
    for tr, nm in zip(traces, tnames):
        ball = nm.most_common(1)[0][0] if nm else None
        for s in split_shots(tr, min_move_mm, fps, keep_tail=keep_tail):
            s.ball = ball
            shots.append(s)
    shots.sort(key=lambda s: s.start_frame)
    return top, shots


def calibrate(traces, w: float, h: float, ball_d: float, verbose: bool = True) -> bool:
    """공이 실제로 다닌 범위로 좌표를 다시 맞춘다.

    공은 영상 내내 네 쿠션을 모두 친다. 그러니 관측 좌표의 최소·최대가 곧
    '공 중심이 쿠션에 닿았을 때의 자리' = 반지름 / (변 − 반지름) 이다.

    ⚠️ 쿠션 날을 밝기로 찾는 방식은 어긋나기 쉽다 (실촬영본에서 상단이 190mm 어긋남).
       공 자신을 자로 쓰면 그 오차가 통째로 사라진다.
    """
    # 짧은 궤적은 잡음일 수 있으니 자로 쓰지 않는다
    solid = [tr for tr in traces if len(tr) >= 100] or traces
    pts = [(x, y) for tr in solid for _, x, y in tr]
    if len(pts) < 200:
        return False
    a = np.array(pts)
    r = ball_d / 2.0

    # 점 전체의 극값(백분위)으로 맞추면 안 된다. 공은 가운데에 오래 머물고 쿠션
    # 근처는 잠깐 스치므로 극값이 깎여 나가, 접점이 쿠션에서 멀찍이 찍힌다.
    # 대신 '되돌아 나온 자리'의 중앙값을 쓴다 — 그 자리가 곧 반지름 거리다.
    turn = {ri: [] for ri in range(4)}
    for tr in solid:
        path = [(x, y) for _, x, y in tr]
        for ri, i, _d in _turning_points(path, w, h, gate=min(w, h) * 0.12):
            turn[ri].append(path[i][1 - ri % 2])       # 장쿠션은 y, 단쿠션은 x

    fixed = []
    for axis, span in ((0, w), (1, h)):
        near_ri, far_ri = (3, 1) if axis == 0 else (0, 2)   # left/right, bottom/top
        lo_pts, hi_pts = turn[near_ri], turn[far_ri]
        if len(lo_pts) >= 5 and len(hi_pts) >= 5:
            lo, hi = float(np.median(lo_pts)), float(np.median(hi_pts))
            src = "튕긴 자리"
        else:
            lo, hi = np.percentile(a[:, axis], [0.3, 99.7])
            src = "관측 극값"
        if hi - lo < span * 0.6:                     # 한쪽 쿠션을 안 쳤으면 못 맞춘다
            if verbose:
                print(f"  보정 건너뜀 ({'x' if axis == 0 else 'y'}축 관측폭 {hi-lo:.0f}mm"
                      f" / {span:.0f}mm) — 공이 양쪽 쿠션을 다 치지 않았습니다")
            return False
        fixed.append((lo, hi, r, span - r, src))
    for tr in traces:
        for i, (f, x, y) in enumerate(tr):
            vals = []
            for axis, v in ((0, x), (1, y)):
                lo, hi, out_lo, out_hi, _src = fixed[axis]
                vals.append(out_lo + (v - lo) * (out_hi - out_lo) / (hi - lo))
            tr[i] = (f, vals[0], vals[1])
    if verbose:
        for axis, name in ((0, "가로"), (1, "세로")):
            lo, hi, out_lo, out_hi, src = fixed[axis]
            print(f"  공 기준 보정 {name}({src}): 관측 {lo:.0f}~{hi:.0f}mm"
                  f" → {out_lo:.1f}~{out_hi:.1f}mm")
    return True


RAILS = ("bottom", "right", "top", "left")


def _rail_distance(p, w: float, h: float) -> list[float]:
    """네 쿠션까지의 거리 (bottom, right, top, left 순)."""
    return [p[1], w - p[0], h - p[1], p[0]]


def _turning_points(pts, w: float, h: float, gate: float, amp: float = 40.0):
    """쿠션 쪽으로 갔다가 되돌아 나온 지점을 찾는다 = 실제로 쿠션을 친 자리.

    ⚠️ '쿠션에서 몇 mm 안'이라는 기준만으로 접점을 잡으면 안 된다. 보정이 몇 mm만
       어긋나도 한쪽 쿠션의 접점이 통째로 사라진다 (실촬영본: 상단 튕김 31개 중
       23개가 기준 밖). 되돌아 나온 것 자체가 접촉의 증거다.

    → [(레일번호, 최소점 인덱스, 그 거리), ...]
    """
    found = []
    n = len(pts)
    for ri in range(4):
        d = np.array([_rail_distance(p, w, h)[ri] for p in pts])
        for i in range(3, n - 3):
            if d[i] > gate:
                continue
            if d[i] > d[max(0, i - 8):i + 9].min():
                continue
            # 스치듯 닿으면 쿠션 쪽 성분이 느리다. 되돌아 나온 양은 넉넉한
            # 창으로 확인해야 그런 접촉을 놓치지 않는다.
            lo, hi = max(0, i - 20), min(n, i + 21)
            if d[lo:i].max(initial=0) - d[i] < amp or d[i + 1:hi].max(initial=0) - d[i] < amp:
                continue
            if found and found[-1][0] == ri and i - found[-1][1] < 8:
                if d[i] < found[-1][2]:         # 같은 접촉이면 더 가까운 점을 쓴다
                    found[-1] = (ri, i, float(d[i]))
                continue
            found.append((ri, i, float(d[i])))
    return found


def _fit_line(pts):
    """점들에 직선을 맞춘다 (총최소제곱). → (지나는 점, 단위방향)."""
    a = np.asarray(pts, dtype=float)
    c = a.mean(axis=0)
    _, _, vt = np.linalg.svd(a - c, full_matrices=False)
    return c, vt[0]


def _hit_rail(c, d, rail: str, w: float, h: float):
    """직선이 쿠션 날과 만나는 점."""
    value, axis = {"bottom": (0.0, 1), "top": (h, 1), "left": (0.0, 0), "right": (w, 0)}[rail]
    if abs(d[axis]) < 1e-9:
        return None
    tt = (value - c[axis]) / d[axis]
    return (float(c[0] + d[0] * tt), float(c[1] + d[1] * tt))


def _on_rail(p, rail: str, w: float, h: float) -> tuple[float, float]:
    """공 중심을 쿠션 날에 내린 수선의 발 = 접점."""
    if rail == "bottom":
        return (float(p[0]), 0.0)
    if rail == "top":
        return (float(p[0]), float(h))
    if rail == "left":
        return (0.0, float(p[1]))
    return (float(w), float(p[1]))


def _angle_from_normal(d, rail: str) -> float:
    """쿠션 법선에서 잰 각도 (0도 = 정면, 90도 = 스치듯)."""
    if rail in ("top", "bottom"):
        return float(np.degrees(np.arctan2(abs(d[0]), abs(d[1]))))
    return float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))


def find_contacts(track: Track, w: float, h: float, ball_diameter: float,
                  slack_mm: float = 18.0) -> list[Contact]:
    """궤적에서 쿠션 접점을 찾고, 구간마다 직선을 맞춰 정밀하게 교점을 구한다.

    접점을 '가장 가까웠던 한 점'으로 잡으면 노이즈에 흔들린다. 그래서
    쿠션 사이 **직선 구간에 선을 맞춘 뒤** 그 선과 쿠션의 교점을 접점으로 쓴다.
    """
    r = ball_diameter / 2.0
    pts = track.path
    if len(pts) < 6:
        return []

    # ⚠️ '쿠션에서 몇 mm 안'으로 접점을 잡으면 안 된다. 보정이 조금만 어긋나도
    #    한쪽 쿠션의 접점이 통째로 사라진다 (실촬영본: 상단 튕김 31개 중 23개가
    #    기준 밖). 쿠션 쪽으로 갔다가 **되돌아 나온 것** 자체를 접촉으로 본다.
    # ⚠️ 쿠션마다 따로 훑는다. 코너로 치면 1쿠션과 2쿠션이 거의 동시에 맞는데
    #    '가장 가까운 쿠션 하나'만 보면 하나로 뭉개진다 (사용자 지적).
    runs = []
    for ri, k, _d in _turning_points(pts, w, h, gate=r + slack_mm * 3.0):
        runs.append((RAILS[ri], k, k, k))
    runs.sort(key=lambda t: t[3])                 # 닿은 순서대로

    # 쿠션 가까이에서는 공이 휜다 (회전 때문). 그 구간을 직선 맞추기에 넣으면
    # 입사·반사각이 흐트러진다. 쿠션에서 공 지름의 몇 배 이상 떨어진 점만 쓴다.
    far = ball_diameter * 2.5

    # 샷 전 정지해 있던 프레임은 큐선이 아니다. 그 점들까지 넣고 직선을 맞추면
    # 제자리 흔들림이 방향을 정해버려 수구수가 엉뚱하게 나온다.
    step = np.hypot(np.diff([p[0] for p in pts]), np.diff([p[1] for p in pts]))
    moving = np.concatenate([[False], step > 5.0])

    out: list[Contact] = []
    for n, (rail, i, j, k) in enumerate(runs):
        ri = RAILS.index(rail)
        prev_end = min(runs[n - 1][2], i - 1) if n else 0
        next_start = max(runs[n + 1][1], j + 1) if n + 1 < len(runs) else len(pts) - 1

        def _far_only(lo, hi):
            sel = [m for m in range(lo, hi)
                   if moving[m] and _rail_distance(pts[m], w, h)[ri] > far]
            return sel if len(sel) >= 4 else []

        idx_in = _far_only(prev_end + 1, i)
        idx_out = _far_only(j + 1, next_start)
        seg_in = [pts[m] for m in idx_in]
        seg_out = [pts[m] for m in idx_out]
        # 속도도 같은 구간에서 잰다. 정지해 있던 프레임까지 넣으면 1쿠션 속도가
        # 실제보다 훨씬 낮게 나온다.
        v_in = track.speed(idx_in[0], idx_in[-1] + 1) if idx_in else None
        v_out = track.speed(idx_out[0], idx_out[-1] + 1) if idx_out else None

        # ⚠️ 직선을 못 맞춰 관측점을 그대로 쓸 때, 그건 **공 중심**이라 쿠션 날에서
        #    반지름만큼(그 이상) 떨어져 있다. 접점은 그 중심에서 쿠션에 내린 수선의
        #    발이다. 쿠션 쪽 좌표만 날 위치로 바꿔준다 (실촬영본에서 594개 중 110개가
        #    최대 69mm 밀려 있었다).
        point, a_in, a_out, line = _on_rail(pts[k], rail, w, h), None, None, None
        if len(seg_in) >= 3:
            c, d = _fit_line(seg_in)
            # 진행 방향으로 부호를 맞춘다 (뒤로 늘일 때 방향이 중요하다)
            if np.dot(np.array(seg_in[-1]) - np.array(seg_in[0]), d) < 0:
                d = -d
            hit = _hit_rail(c, d, rail, w, h)
            # 직선을 늘여 구한 교점이 당구대 밖이면 쓰지 않는다 (관측점을 그대로 쓴다)
            if hit is not None and -1 <= hit[0] <= w + 1 and -1 <= hit[1] <= h + 1:
                point = hit
            a_in = _angle_from_normal(d, rail)
            line = ((float(c[0]), float(c[1])), (float(d[0]), float(d[1])))
        if len(seg_out) >= 3:
            _, d = _fit_line(seg_out)
            a_out = _angle_from_normal(d, rail)
        out.append(Contact(rail, point, track.points[k][0], a_in, a_out, v_in, v_out, line))
    return out


def _split_on_jump(points, jump_mm: float = 150.0, max_gap: int = 20) -> list[list]:
    """한 프레임에 공이 갈 수 없는 거리를 건너뛰었으면 거기서 자른다.

    ⚠️ 편집 컷이다. 카메라가 고정이라 컷 전후 화면이 거의 같아 밝기 차이로는
       못 찾는다. 대신 공이 튄 것으로 찾는다 — 150mm/프레임은 4.5m/s로,
       사람이 큐로 낼 수 있는 속도를 넘는다.

    ★ 2026-08-11 — **반드시 프레임 간격으로 나눠서** 본다.
      궤적에는 빈 프레임이 있다 (사람에 가려 공을 놓친 구간). 두 점 사이 거리만
      보면 3프레임만 놓쳐도 1.5m/s 에서 150mm 를 넘어 **한 샷이 잘렸다.**
      9.3분 편집본이 147조각으로 쪼개지고, 앞 구간이 짧아 충돌 39쌍 중 7개만
      살아남던 원인이 이것이다.
    max_gap  이보다 오래 놓쳤으면 이어 붙이지 않는다 (20프레임 = 0.67초).
    """
    out, cur = [], [points[0]]
    for a, b in zip(points, points[1:]):
        df = max(1, b[0] - a[0])
        per_frame = float(np.hypot(b[1] - a[1], b[2] - a[2])) / df
        if per_frame > jump_mm or df > max_gap:
            out.append(cur)
            cur = [b]
        else:
            cur.append(b)
    out.append(cur)
    return [seg for seg in out if len(seg) >= 6]


def _split_on_accel(points, floor_mm: float = 15.0, ratio: float = 2.0) -> list[list]:
    """다시 빨라지는 자리에서 자른다 = 그 자리가 다음 샷의 시작이다.

    ⚠️ 앞 샷의 공이 아직 굴러가는 중에 다음 샷을 치면 두 샷이 하나로 붙는다
       (실촬영본: 8쿠션 한 샷에서 0.46m/s → 1.19m/s). **구르는 공은 저절로
       빨라지지 않으므로** 속도가 다시 올라간 것 자체가 새로 쳤다는 증거다.
    """
    if len(points) < 12:
        return [points]
    # ★ 2026-08-11 — 여기도 **프레임 간격으로 나눈다**. 안 나누면 공을 몇 프레임
    #   놓친 자리에서 '속도가 확 올랐다' 고 오판해 멀쩡한 샷을 잘랐다.
    d = np.hypot(np.diff([p[1] for p in points]), np.diff([p[2] for p in points]))
    df = np.maximum(1, np.diff([p[0] for p in points]))
    v = d / df
    k = np.ones(5) / 5.0
    v = np.convolve(v, k, mode="same")

    cuts, peak, lo, lo_i = [], -1.0, 0.0, 0
    for i, s in enumerate(v):
        if s >= peak:                       # 아직 빨라지는 중 (샷 시작)
            peak, lo, lo_i = s, s, i
        elif s < lo:
            lo, lo_i = s, i
        elif s > lo * ratio and s - lo > floor_mm:
            cuts.append(lo_i)
            peak, lo, lo_i = s, s, i

    if not cuts:
        return [points]
    out, prev = [], 0
    for c in cuts:
        out.append(points[prev:c + 1])
        prev = c
    out.append(points[prev:])
    return [seg for seg in out if len(seg) >= 6]


def _split_all(points) -> list[list]:
    """편집 컷(순간이동) 먼저 자르고, 그 다음 다시 빨라진 자리를 자른다."""
    return [seg for piece in _split_on_jump(points) for seg in _split_on_accel(piece)]


def split_shots(samples, min_move_mm: float, fps: float = 30.0,
                stop_run: int = 8, keep_tail: bool = False) -> list[Track]:
    """멈춰 있는 구간을 잘라 샷 단위로 나눈다.

    ⚠️ 한 프레임만 느려도 끊으면 안 된다. 공은 굴러가다 느려지는 구간이 있고,
       검출이 촘촘할수록 그 구간이 길게 잡혀 한 샷이 잘게 쪼개진다.
       **연속으로 stop_run 번 느려야** 멈춘 것으로 본다.

    keep_tail  ★ 사용자 2026-08-10 — '공의 속도에 따라 궤적을 얼마나 이어야 하는가를
               판단할 목적으로' 재는 촬영에서는 **마지막 느린 구간을 버리면 안 된다.**
               기본값은 그 구간을 떼어낸다(cur[:-slow]) — 접점 각도를 정확히 재려고
               멈추기 직전의 흔들림을 뺀 것이다. 굴러간 거리를 재려면 켠다.
    """
    shots: list[Track] = []
    cur: list[tuple[int, float, float]] = []
    slow = 0
    for a, b in zip(samples, samples[1:]):
        moved = float(np.hypot(b[1] - a[1], b[2] - a[2]))
        if moved >= min_move_mm:
            if not cur:
                cur = [a]
            cur.append(b)
            slow = 0
        elif cur:
            slow += 1
            cur.append(b)                       # 느린 구간도 궤적의 일부다
            if slow >= stop_run:
                keep = cur if keep_tail else cur[:-slow]
                for seg in _split_all(keep):
                    shots.append(Track(seg[0][0], seg[-1][0], seg, fps=fps))
                cur, slow = [], 0
    if len(cur) >= 6:
        for seg in _split_all(cur):
            shots.append(Track(seg[0][0], seg[-1][0], seg, fps=fps))
    return [s for s in shots if len(s.points) >= 6]
