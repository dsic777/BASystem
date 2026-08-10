"""두 공 촬영본 → **두께별 충돌 후 속도** 표를 뽑는다.

    python collide.py 영상.mp4
    python collide.py 영상.mp4 --out 폴더 --step 2
    python collide.py 영상.mp4 --from 0 --to 12      1순위 구간만 (분 단위)
    python collide.py 영상.mp4 --ball 흰공,빨간공    쓴 공을 못 박는다
    python collide.py 영상.mp4 --gap 6               두 공이 가까운 배치까지 잡는다

★ 하나로 쭉 이어 찍은 영상이면 `--from/--to` 로 1순위 구간만 잘라 돌린다
  (2026-08-10 촬영 방식. 순위가 바뀔 때 카메라에 손가락으로 1·2·3 을 찍어 두었다).

내일(2026-08-11) 촬영 1순위가 이것이다. 시연화면과 키스 판정이 여기서 막혀 있다
(data/speed.json 의 ⚠️_못_잰_것 참고).

무엇을 재나
    충돌 직전 수구 속도  /  직후 수구 속도  /  직후 1적구 속도  /  그때의 두께
    → 두께별 속도비 표가 나오면 두 공의 **시간표**를 동시에 그릴 수 있다.

왜 track.py 로 안 되나
    track.py 는 샷마다 **쿠션 접점**만 뽑는다. 두 공이 같이 움직여도 그냥
    샷 두 개로 센다. 여기서는 시간이 겹치는 두 궤적을 **한 샷으로 묶어**
    충돌 순간을 찾는다.

⚠️ 두께는 따로 안 적어도 된다 — 궤적에서 계산된다.
   촬영은 C:/sc/촬영1.png 참고.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.table import Table                      # noqa: E402
from vision import pick_corners                   # noqa: E402
from vision import track as vtrack                # noqa: E402

MIN_SPEED = 0.25        # m/s. 이보다 느리면 손으로 옮긴 것으로 본다
MIN_POINTS = 6
PRE, POST = 8, 10       # 충돌 앞뒤로 몇 프레임을 속도 재는 데 쓰나
# ★ 충돌 프레임에서 이만큼 앞으로 물러나 '충돌 직전' 을 잡는다.
#   1적구가 움직였다고 잡히는 순간은 이미 접촉 뒤라, 그때 두 공 사이가 90~200mm 다
#   (지름 61.5mm). 수구는 이미 접촉점을 1~3프레임 지나쳤다는 뜻이다.
#   물러나지 않으면 진행 방향을 **충돌 뒤 구간**으로 재게 되고, 그러면 1적구가
#   그 선에서 지름보다 멀리 떨어져 두께가 0% 로 나온다 (17개 중 7개가 그랬다).
BACKOFF = 3
# 충돌 후 속도를 재는 두 창 (프레임). 사용자 설명대로 '잠깐 멈춤 → 다시 전진' 을 가른다.
NOW = 4                 # 충돌 직후 1~4프레임 (0.13초) — 거의 멈추는 구간
ROLL0, ROLL1 = 9, 20    # 9~20프레임 (0.3~0.67초) — 전진회전이 되살린 뒤
GAP = 12                # 두 궤적의 시작 프레임이 이만큼 안에서 갈리면 같은 샷


def seg_speed(pts, i0, i1, fps):
    """구간 평균 속도 (m/s). pts = [(frame, x, y)] mm"""
    i0, i1 = max(0, i0), min(len(pts) - 1, i1)
    if i1 <= i0:
        return None
    d = sum(math.dist(pts[i][1:], pts[i + 1][1:]) for i in range(i0, i1))
    df = pts[i1][0] - pts[i0][0]
    return d / (df / fps) / 1000.0 if df > 0 else None


def run_after(pts, i0):
    """i0 이후 실제로 굴러간 거리 (mm). 순간속도보다 훨씬 안정적이다.

    ★ 2026-08-11 — 30fps 로는 '잠깐 멈췄다 다시 전진' 을 못 잰다. 그 현상이
      0.05~0.1초인데 한 프레임이 0.033초이고 충돌 프레임 자체가 ±2프레임 흔들린다.
      그런데 우리가 알고 싶은 것은 '여기서 몇 쿠션 더 가나' 이므로,
      **끝까지 굴러간 거리**를 재면 된다. 그건 프레임률과 무관하게 정확하다.
    """
    return sum(math.dist(pts[i][1:], pts[i + 1][1:]) for i in range(max(0, i0), len(pts) - 1))


def fit_dir(pts, i0, i1):
    """구간에 직선을 맞춰 진행 방향(단위벡터)을 낸다."""
    i0, i1 = max(0, i0), min(len(pts) - 1, i1)
    if i1 - i0 < 1:
        return None
    a = np.array([p[1:] for p in pts[i0:i1 + 1]], float)
    c = a.mean(axis=0)
    u, s, vt = np.linalg.svd(a - c)
    d = vt[0]
    if np.dot(a[-1] - a[0], d) < 0:
        d = -d
    return d / (np.linalg.norm(d) or 1)


def pair_shots(shots, fps, ball_d, gap: int = GAP):
    """시간이 겹치는 (흰공, 빨간공) 궤적을 묶는다.

    ★ 사용자 확정 2026-08-10: **흰공 = 수구, 빨간공 = 1적구.**
      전에는 '먼저 움직이기 시작한 쪽이 수구' 로 추측했다. 검출 잡음 때문에
      시작 프레임이 ±3 흔들려 어느 쪽이 수구인지 뒤집히곤 했다.
      색을 알면 추측할 필요가 없다.

    gap  두 궤적이 시간으로 이만큼도 안 겹치면 한 샷이 아니다.
    """
    ok = [s for s in shots
          if len(s.points) >= MIN_POINTS and s.peak_speed / 1000.0 >= MIN_SPEED]
    cue_all = sorted((s for s in ok if s.ball == "white"), key=lambda s: s.start_frame)
    obj_all = sorted((s for s in ok if s.ball == "red"), key=lambda s: s.start_frame)
    if not cue_all or not obj_all:
        print(f"  ⚠️ 색이 안 붙었다 — 흰공 궤적 {len(cue_all)}개, 빨간공 궤적 {len(obj_all)}개")
        return []
    used, out = set(), []
    for a in cue_all:                       # 흰공 = 수구
        best, best_ov = None, 0
        for j, b in enumerate(obj_all):     # 빨간공 = 1적구
            if j in used:
                continue
            ov = min(a.end_frame, b.end_frame) - max(a.start_frame, b.start_frame)
            if ov > best_ov:
                best, best_ov = j, ov
        if best is not None and best_ov >= gap:
            used.add(best)
            out.append((a, obj_all[best]))
    return out


MAX_MISS_MM = 400.0     # 두 궤적이 이보다 가까워진 적이 없으면 충돌이 아니다


def contact_frame(cue, obj, ball_d, fps):
    """충돌 순간과, 그때 두 공이 얼마나 가까웠나.

    1적구가 **움직이기 시작한 프레임**을 충돌로 본다. split_shots 가 움직이기
    직전 점부터 궤적에 넣으므로, `obj.points[0]` 이 곧 **멈춰 있던 자리**다.

    ⚠️ '두 중심이 지름 거리까지 가까워지는 프레임' 으로 잡아 보았지만 못 쓴다.
       실측하니 그 최소거리가 90~200mm 였다 (지름 61.5mm). 1적구가 이미 몇십 mm
       움직인 뒤에야 궤적이 시작되기 때문이다. 지름 기준으로 걸면 전부 버려진다.
    ★ 두께는 충돌 프레임을 정확히 몰라도 된다 — 1적구 중심에서 수구 진행 **선**
      까지의 수선거리이고, 그 값은 선 위 어느 점을 잡든 같다.
      충돌 프레임은 v_in / v_out 을 가르는 데만 쓴다.
    """
    op = {f: (x, y) for f, x, y in obj.points}
    near = min((math.dist((x, y), op[f]) for f, x, y in cue.points if f in op),
               default=None)
    if near is None or near > MAX_MISS_MM:
        return None, near
    return obj.start_frame, near


def measure(cue, obj, fps, ball_d):
    """한 쌍에서 두께와 속도 셋을 뽑는다."""
    fc, _gapmm = contact_frame(cue, obj, ball_d, fps)   # 두 공이 가장 가까워진 프레임
    if fc is None:
        return None
    cp = cue.points
    k = next((n for n, p in enumerate(cp) if p[0] >= fc), None)
    if k is None or k < 2 or k > len(cp) - 3:
        return None

    # 확실히 충돌 앞쪽으로.
    # ⚠️ 여유가 없을 때 kb = max(2, k - BACKOFF) 로 봐주면 안 된다. 그러면 개수는
    #    17개로 늘지만 **표가 무너진다** — 앞 구간이 2~3점밖에 없어 진행 방향이
    #    엉뚱하게 잡히고, 같은 샷의 두께가 30% → 91% 로 튀었다.
    #    수구가 남기는 비율도 두께 순서를 잃었다 (0.686/0.658/0.643/0.774/0.842).
    #    개수보다 정확도다. 앞 구간이 모자란 샷은 버린다.
    kb = k - BACKOFF
    if kb < 2:
        return None
    d = fit_dir(cp, kb - PRE, kb)              # 충돌 직전 진행 방향
    if d is None:
        return None
    # 두께 — 1적구 중심이 수구 진행선에서 얼마나 비켜 있나
    #        thick = (지름 − 수선거리) / 지름   (정면 1.0 · 반두께 0.5 · 스침 0)
    # 1적구가 멈춰 있던 자리 = 그 궤적의 첫 점
    oi = 0
    if len(obj.points) < 3:
        return None
    c0 = np.array(cp[kb][1:], float)
    ob = np.array(obj.points[oi][1:], float)
    # ⚠️ np.cross 는 numpy 2 에서 2차원 벡터를 안 받는다. 직접 쓴다.
    perp = abs(d[0] * (ob[1] - c0[1]) - d[1] * (ob[0] - c0[0]))
    thick = max(0.0, min(1.0, (ball_d - perp) / ball_d))

    # ★ 사용자 2026-08-11: '수구 정중앙으로 100% 두께로 맞히면 수구는 거의 정지한다.
    #   **상단을 주고 치면 잠깐 멈춘 후 다시 전진**한다. 6시면 잠깐 멈춘 후 뒤로 온다.'
    #   → 충돌 후 속도는 **언제 재느냐에 따라 다른 값**이다. 0.33초 평균 하나로
    #     뭉개면 '멈춘 구간' 과 '되살아난 구간' 이 섞여 두께와 무관하게 평평해진다
    #     (실제로 그랬다 — 두께 1/8~5/8 이 전부 0.49~0.59).
    #   두 번 잰다. 이번 촬영은 12시 2팁이라 되살아나는 쪽이다.
    v_in = seg_speed(cp, kb - PRE, kb, fps)
    v_now = seg_speed(cp, k + 1, k + NOW, fps)          # 충돌 직후 (거의 멈추는 구간)
    v_roll = seg_speed(cp, k + ROLL0, k + ROLL1, fps)   # 전진회전이 되살린 뒤
    v_obj = seg_speed(obj.points, oi, oi + POST, fps)
    if not (v_in and v_obj):
        return None
    v_out = v_roll or v_now
    if not v_out:
        return None
    return {"frame": fc, "minute": fc / fps / 60,
            "thick": round(thick, 3),
            "cue_in": round(v_in, 3),
            "cue_now": round(v_now, 3) if v_now else None,    # 직후
            "cue_roll": round(v_roll, 3) if v_roll else None,  # 되살아난 뒤
            "cue_out": round(v_out, 3),
            "obj_out": round(v_obj, 3),
            "keep_now": round(v_now / v_in, 3) if v_now else None,
            "keep_roll": round(v_roll / v_in, 3) if v_roll else None,
            "cue_keep": round(v_out / v_in, 3),      # 수구가 남긴 비율
            "obj_take": round(v_obj / v_in, 3),      # 1적구가 받아간 비율
            # ★ 충돌 뒤 **실제로 굴러간 거리** — '몇 쿠션 더 가나' 의 직접 재료
            "cue_after_mm": round(run_after(cp, k), 0),
            "obj_after_mm": round(run_after(obj.points, oi), 0)}


def report(rows):
    if not rows:
        print("\n충돌을 하나도 못 잡았습니다.")
        print("  · 공이 두 개만 있는지, 한 샷이 끝난 뒤 다음 샷을 쳤는지 확인하세요.")
        print("  · 손으로 공을 옮기는 장면이 많으면 MIN_SPEED 를 올려 보세요.")
        return
    print(f"\n충돌 {len(rows)}개\n")
    print(f"{'두께':>8} {'개수':>5} {'충돌전 수구':>11} {'수구 더 굴러감':>13}"
          f" {'1적구 굴러감':>12} {'직후 남김':>9} {'1적구 받아감':>12}")
    print("-" * 78)
    bins = [(0, .1875, "1/8"), (.1875, .3125, "2/8"), (.3125, .4375, "3/8"),
            (.4375, .5625, "4/8"), (.5625, .6875, "5/8"), (.6875, .8125, "6/8"),
            (.8125, 1.01, "7/8")]
    table = []
    for lo, hi, lab in bins:
        g = [r for r in rows if lo <= r["thick"] < hi]
        if not g:
            print(f"{lab:>8} {0:5d}          —          —             —")
            continue
        med = lambda key: (float(np.median([r[key] for r in g if r.get(key) is not None]))
                           if any(r.get(key) is not None for r in g) else None)
        now, roll = med("keep_now"), med("keep_roll")
        take = float(np.median([r["obj_take"] for r in g]))
        vin = float(np.median([r["cue_in"] for r in g]))
        f2 = lambda v: f"{v:8.3f}" if v is not None else f"{'—':>8}"
        cue_mm = float(np.median([r["cue_after_mm"] for r in g]))
        obj_mm = float(np.median([r["obj_after_mm"] for r in g]))
        print(f"{lab:>8} {len(g):5d} {vin:10.2f}m/s {cue_mm:9.0f}mm {obj_mm:9.0f}mm"
              f" {f2(now)} {take:9.3f}")
        table.append([lab, round(np.mean([r['thick'] for r in g]), 3), len(g),
                      round(cue_mm), round(obj_mm),
                      None if now is None else round(now, 3), round(take, 3)])

    # ★ 사용자 2026-08-11: '수구 속도에 따라 충돌 후 수구의 경로, 1적구의 경로,
    #   이동거리까지만 나오면 될 것 같은데요. 또 두께에 따라.'
    #   → 두께별(위)과 속도별(아래) 둘 다 낸다. 실제로 거리는 속도가 더 크게 가른다.
    print(f"\n{'충돌전 속도':>12} {'개수':>5} {'평균두께':>9} {'수구 더 굴러감':>14} {'1적구 굴러감':>13}")
    print("-" * 58)
    speed_rows = []
    for lo, hi, lab in [(0, 1.0, "~1.0"), (1.0, 1.5, "1.0~1.5"), (1.5, 2.0, "1.5~2.0"),
                        (2.0, 2.5, "2.0~2.5"), (2.5, 99, "2.5~")]:
        g = [r for r in rows if lo <= r["cue_in"] < hi]
        if not g:
            print(f"{lab:>12} {0:5d}         —              —             —")
            continue
        th = float(np.mean([r["thick"] for r in g]))
        cm = float(np.median([r["cue_after_mm"] for r in g]))
        om = float(np.median([r["obj_after_mm"] for r in g]))
        print(f"{lab:>12} {len(g):5d} {th*100:8.1f}% {cm:12.0f}mm {om:11.0f}mm")
        speed_rows.append([lab, len(g), round(th, 3), round(cm), round(om)])

    print("\n  ★ 굴러간 거리 = 충돌 뒤 공이 멈출 때까지 실제로 지나간 길이.")
    print("    순간속도와 달리 30fps 로도 정확하다 — 이것이 '몇 쿠션 더 가나' 의 재료다.")
    print("  직후 남김 = 충돌 뒤 1~4프레임(0.13초) 수구속도 ÷ 직전 수구속도")
    print("  ⚠️ '잠깐 멈췄다 다시 전진' 은 30fps 로 못 잰다 (0.05~0.1초 현상, 한 프레임 0.033초).")
    print("     사용자 확인: 오늘 촬영엔 그럴 만큼 두껍게 친 공이 없다.")
    return table, speed_rows


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    video = Path(argv[0])
    out_dir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)
    step = int(argv[argv.index("--step") + 1]) if "--step" in argv else 1
    gap = int(argv[argv.index("--gap") + 1]) if "--gap" in argv else GAP
    t_from = float(argv[argv.index("--from") + 1]) if "--from" in argv else 0.0
    t_to = float(argv[argv.index("--to") + 1]) if "--to" in argv else None
    ball_kr = {"노란공": "yellow", "노랑": "yellow", "흰공": "white", "빨간공": "red"}
    only = None
    if "--ball" in argv:
        only = tuple(ball_kr.get(n.strip(), n.strip().lower())
                     for n in argv[argv.index("--ball") + 1].split(","))
    table = Table.load()

    import cv2
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()

    print(f"=== {video.name} ===  {fps:.1f}fps")
    quad = pick_corners.load(video)
    print("코너: " + ("사람이 찍어 둔 값" if quad is not None else "자동 검출"))
    f0 = int(t_from * 60 * fps)
    f1 = int(t_to * 60 * fps) if t_to is not None else None
    if f0 or f1:
        print(f"구간: {t_from:.1f}분 ~ {t_to if t_to is not None else '끝'}분")
    if only:
        print(f"추적 대상 공: {', '.join(only)}")
    if gap != GAP:
        print(f"출발 간격 기준: {gap}프레임 ({gap/fps:.2f}초)")
    # ★ 두 공 촬영이다 — 궤적을 2개로 묶는다 (사용자 지적 2026-08-10).
    #   손·팔이 흰공 여러 개로 잡혀 궤적이 6개까지 늘어나고, 그 조각들이 서로
    #   짝지어져 두께 0%·'수구 남김 16배' 같은 값이 나왔다.
    # ⚠️ max_detections 로 프레임을 통째로 버리면 안 된다. 치는 동안은 팔이 화면에
    #   있어서 충돌 **전** 구간이 통째로 날아가고, 두 궤적이 같은 프레임에서
    #   시작해 버린다 (그러면 어느 쪽이 수구인지도 못 가린다).
    top, shots = vtrack.track_video(str(video), table.width, table.height,
                                    step=step, quad=quad,
                                    ball_diameter_mm=table.ball_diameter,
                                    first_frame=f0, last_frame=f1, only=only,
                                    max_traces=2)
    print(f"궤적 {len(shots)}개 검출")

    pairs = pair_shots(shots, fps, table.ball_diameter, gap)
    print(f"두 공이 같이 움직인 쌍 {len(pairs)}개")

    rows = []
    for a, b in pairs:
        m = measure(a, b, fps, table.ball_diameter)
        if m:
            rows.append(m)
            print(f"  {m['minute']:5.2f}분  두께 {m['thick']*100:5.1f}%  "
                  f"수구 {m['cue_in']:.2f} → {m['cue_out']:.2f} m/s  "
                  f"1적구 {m['obj_out']:.2f} m/s")

    tbl, spd = report(rows) if rows else (None, None)
    js = out_dir / f"{video.stem}_collide.json"
    js.write_text(json.dumps({"_desc": "두께별 충돌 후 속도 (collide.py)",
                              "_source": video.name, "fps": fps,
                              "_columns": ["두께", "평균두께", "표본수", "수구 더 굴러감mm",
                                           "1적구 굴러감mm", "직후 남김", "1적구 받아감"],
                              "_by_speed_columns": ["충돌전 속도", "표본수", "평균두께",
                                                    "수구 더 굴러감mm", "1적구 굴러감mm"],
                              "table": tbl, "by_speed": spd, "shots": rows},
                             ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
