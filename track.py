"""영상에서 공 궤적을 뽑아 쿠션별 번호와 입사/반사각을 출력한다.

    python track.py 영상.mp4
    python track.py 영상1.mp4 영상2.mp4 ...     여러 개 한꺼번에
    python track.py C:\\sc\\videos              폴더 통째로
    python track.py 영상.mp4 --out 폴더         결과 저장 위치
    python track.py 영상.mp4 --step 2           2프레임에 1번만 처리 (빠르게)
    python track.py 영상.mp4 --pick             ★ 당구대 코너 4개를 직접 찍어 저장
    python track.py 영상.mp4 --roll             ★ 끝까지 굴러간 데까지 남긴다 (아래 참고)

★ --roll  '공이 얼마나 굴러가나' 를 재는 촬영용 (2026-08-10 이후).
  기본값은 멈추기 직전의 느린 구간(8mm/프레임 미만이 8프레임)을 **떼어낸다** —
  접점 각도를 흔들림 없이 재려고 그렇게 해 두었다. 그래서 0808 은 마지막 쿠션에서
  공이 아직 살아 있는 샷이 72% 였다. 굴러간 거리를 재려면 이 옵션을 켠다.
  기준을 5mm 로 낮추고 꼬리를 살린다. **기존 분석에는 영향이 없다** (기본값 그대로).

★ 당구장에 당구대가 여러 대 보이면 자동 검출이 엉뚱한 사각형을 만든다.
  카메라가 삼각대로 고정돼 있으니 **--pick 으로 한 번만 찍어두면** 그 영상 내내 정확하다.
  찍은 값은 영상 옆에 <이름>_corners.json 으로 저장되고, 다음부터 자동으로 쓰인다.

★ 영상을 하나로 합칠 필요 없다. 여러 파일을 그대로 주면 된다.
  오히려 합치면 컷 지점에서 공이 튀어 추적이 끊길 수 있다.

촬영 조건 (사용자 확정)
    공 1개 / 당점 2시30분 3팁 / 5쿠션까지 자연스러운 세기
    삼각대 고정, 당구대 네 면이 모두 프레임 안에, 샷 사이 1~2초 정지
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import five_half as fh, geometry                          # noqa: E402
from core.orientation import Orientation                            # noqa: E402
from core.table import BOTTOM, RIGHT, TOP, Table                    # noqa: E402

RAIL_KR = {"bottom": "하단", "right": "우측", "top": "상단", "left": "좌측"}

# 공이 끝까지 굴러간 데까지 다 기록한다 (사용자 확정 2026-08-06).
# 다만 5쿠션까지가 자연스러운 세기고, 그 이상은 세게 친 것이라 포인트가 달라진다.
# 그래서 자르지 않고 '자연스러운 범위'만 표시해 둔다 — 나중에 걸러낼 수 있게.
NATURAL_CUSHIONS = 5
MAX_CUSHIONS = 8

# 실제 샷을 가리는 기준.
# ⚠️ 2026-08-07 촬영본(0807.mp4)은 삑사리와 손으로 옮긴 장면을 사용자가 모두
#    잘라내, 순수한 샷만 들어 있다 (사용자 확인). 그래서 속도로 걸러낼 것이
#    없다. 기준을 최대한 풀어 데이터를 살린다 — 버리는 판단은 하지 않는다.
#    (0806.mp4처럼 옮기는 장면이 섞인 영상은 MIN_SPEED를 1.5로 올려야 한다.)
MIN_POINTS = 40
MIN_SPEED = 0.8          # m/s — 추적이 끊겨 생긴 조각만 걸러낸다
MAX_SPEED = 4.0          # m/s — 이보다 빠르면 궤적이 튄 것 (사람이 낼 수 없는 속도)
MIN_DISTANCE = 1200.0    # mm
MIN_CONTACTS = 1         # 원뱅크·투뱅크도 데이터다 (사용자 요청)
# 각 레일에 붙어 있는 눈금 (기준 방향 기준)
RAIL_SCALE = {TOP: "first_cushion", BOTTOM: "third_cushion", RIGHT: "start"}


def read_number(table: Table, scales, orientation: Orientation, rail: str, point):
    """접점 → 그 레일 눈금으로 읽은 번호. 눈금이 없으면 None."""
    base_rail = orientation.rail(rail)          # 화면 레일 → 기준 방향 레일 (자기역함수)
    base_pt = orientation.apply(table, point)
    scale = scales.get(RAIL_SCALE.get(base_rail, ""))
    if scale is None:
        return None
    return scale.number_at_extrapolated(base_rail, fh.index_on_frame(table, base_rail, *base_pt))


def departure(table: Table, scales, cue, contact) -> dict | None:
    """출발선(큐선)에서 수구수와 1쿠션수를 읽는다.

    영상에서 잰 '1쿠션으로 들어가는 직선'이 곧 큐선이다. 이 선을
        앞으로 늘이면 → 1쿠션 프레임 포인트 → 1쿠션수
        뒤로 늘이면   → 등 뒤 레일        → 수구수
    시스템이 정의한 그대로다. 공이 허공에 떠 있어도 상관없다.
    """
    # ⚠️ 파이브앤하프 눈금은 1쿠션이 장쿠션일 때만 정의된다. 코너 방향으로 쳐서
    #    단쿠션을 먼저 맞히면 읽을 수 없다 — None 을 돌려주되 **샷은 버리지 않는다.**
    if contact.in_line is None or contact.rail not in (TOP, BOTTOM):
        return None
    (px, py), (dx, dy) = contact.in_line
    o = Orientation.from_aim(cue, contact.point)

    # 큐선을 1쿠션 프레임선까지 늘여 조준점을 얻는다 (기준 방향에서)
    bp = o.apply(table, (px, py))
    tip = o.apply(table, (px + dx, py + dy))
    bd = (tip[0] - bp[0], tip[1] - bp[1])
    _, _, _, y_top = fh.frame_bounds(table)
    aim = geometry.ray_hit_horizontal(bp, bd, y_top)
    if aim is None:
        return None

    first = scales["first_cushion"].number_at_extrapolated(
        TOP, fh.index_on_frame(table, TOP, *aim))
    reading = fh.read_cue_number(table, scales["start"], bp, aim)
    if first is None or reading is None:
        return None
    return {"orientation": o, "aim": o.apply(table, aim),
            "cue_number": reading.number, "first_number": first,
            "cue_rail": o.rail(reading.rail)}


VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}


def collect_videos(args: list[str]) -> list[Path]:
    """인자에서 영상 파일 목록을 모은다. 폴더면 안의 영상을 전부."""
    out: list[Path] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            out += sorted(q for q in p.iterdir() if q.suffix.lower() in VIDEO_EXT)
        elif p.suffix.lower() in VIDEO_EXT:
            out.append(p)
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    out_dir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else Path.cwd()
    step = int(argv[argv.index("--step") + 1]) if "--step" in argv else 1
    t_from = float(argv[argv.index("--from") + 1]) if "--from" in argv else 0.0
    t_to = float(argv[argv.index("--to") + 1]) if "--to" in argv else None
    # 영상에 쓴 공을 못 박는다. 손·큐대가 흰공으로 잡혀 궤적을 뺏어가는 것을 막는다.
    ball_kr = {"노란공": "yellow", "노랑": "yellow", "흰공": "white", "빨간공": "red"}
    only = None
    if "--ball" in argv:
        names = argv[argv.index("--ball") + 1].split(",")
        only = tuple(ball_kr.get(n.strip(), n.strip().lower()) for n in names)
    # ★ 공이 끝까지 굴러간 데까지 남긴다. 굴러간 거리를 재는 촬영용.
    roll = "--roll" in argv
    flags = {"--out", "--step", "--from", "--to", "--ball"}
    positional = [a for i, a in enumerate(argv)
                  if a not in flags and (i == 0 or argv[i - 1] not in flags)]

    videos = collect_videos(positional)
    if not videos:
        print("영상 파일을 못 찾았습니다.")
        return 1

    try:
        from vision import pick_corners
        from vision import track as vtrack
    except ImportError as e:
        print(f"OpenCV 가 필요합니다: {e}")
        return 1

    if "--pick" in argv:
        for v in videos:
            print(f"코너 찍기: {v.name}  (좌하 → 우하 → 우상 → 좌상, 쿠션 날 기준)")
            try:
                p = pick_corners.save(v, pick_corners.pick(v))
                print(f"  저장: {p}")
            except KeyboardInterrupt:
                print("  취소")
        return 0

    table = Table.load()
    scales = fh.load_scales()

    print(f"영상 {len(videos)}개\n")
    total = 0
    for v in videos:
        try:
            total += run_one(v, out_dir, step, table, scales, vtrack, pick_corners,
                             t_from, t_to, only, roll)
        except Exception as e:
            print(f"[{v.name}] 실패: {e}\n")
    print(f"전체 샷 {total}개")
    return 0


def run_one(video: Path, out_dir: Path, step: int, table, scales, vtrack, pick_corners,
            t_from: float = 0.0, t_to: float | None = None,
            only: tuple[str, ...] | None = None, roll: bool = False) -> int:
    import cv2

    print(f"=== {video.name} ===")
    quad = pick_corners.load(video)
    print("코너: " + ("사람이 찍어 둔 값 사용" if quad is not None else "자동 검출"))
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    f0 = int(t_from * 60 * fps)
    f1 = int(t_to * 60 * fps) if t_to is not None else None
    if f0 or f1:
        print(f"구간: {t_from:.1f}분 ~ {t_to if t_to is not None else '끝'}분")
    if roll:
        print("굴러간 끝까지 남긴다 (--roll): 멈춤 기준 8mm → 5mm, 느린 꼬리를 안 버린다")
    top, shots = vtrack.track_video(str(video), table.width, table.height,
                                    step=step, quad=quad,
                                    ball_diameter_mm=table.ball_diameter,
                                    first_frame=f0, last_frame=f1, only=only,
                                    min_move_mm=5.0 if roll else 8.0,
                                    keep_tail=roll)
    if only:
        print(f"추적 대상 공: {', '.join(only)}")
    print(f"당구대 검출 완료 — 상단뷰 {top.size}, 가로세로비 {top.aspect:.3f} (규격 2.000)")
    if abs(top.aspect - 2.0) > 0.03:
        print("  ⚠️ 비율 오차가 큽니다. 더 수직으로 찍으면 정확도가 올라갑니다.")
    print(f"샷 {len(shots)}개 검출\n")

    result, paths, frames = [], [], []
    dropped = {"느린 조각": 0, "궤적 튐": 0, "점 부족": 0, "짧음": 0, "쿠션 부족": 0}
    for n, shot in enumerate(shots, 1):
        # 실제 샷인지부터 가린다. 정지 상태에서 갑자기 빨라지는 것이 샷이다.
        v = shot.peak_speed / 1000.0
        p = np.array(shot.path)
        dist = float(np.sum(np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1])))) if len(p) > 1 else 0.0
        if v > MAX_SPEED:
            dropped["궤적 튐"] += 1
            continue
        if v < MIN_SPEED:
            dropped["느린 조각"] += 1
            continue
        if len(shot.points) < MIN_POINTS:
            dropped["점 부족"] += 1
            continue
        if dist < MIN_DISTANCE:
            dropped["짧음"] += 1
            continue

        contacts = vtrack.find_contacts(shot, table.width, table.height, table.ball_diameter)
        if len(contacts) < MIN_CONTACTS:
            dropped["쿠션 부족"] += 1
            print(f"[샷 {n}] 쿠션 접점 {len(contacts)}개 — 건너뜀  ({v:.2f}m/s, {dist:.0f}mm)")
            continue

        cue = shot.path[0]
        dep = departure(table, scales, cue, contacts[0])
        orientation = dep["orientation"] if dep else Orientation.from_aim(cue, contacts[0].point)

        print(f"[샷 {n}]  {shot.start_frame/30/60:5.2f}분  점 {len(shot.points)}개"
              f"  최고 {v:.2f}m/s  이동 {dist:.0f}mm  {orientation.label}")
        print(f"   수구 출발 ({cue[0]:7.1f}, {cue[1]:7.1f})")
        rec = {"shot": n, "minute": shot.start_frame / 30 / 60,
               "orientation": orientation.label, "cue": list(cue), "contacts": []}
        if dep:
            print(f"   큐선 판독:  수구수 {dep['cue_number']:.1f}"
                  f" ({RAIL_KR.get(dep['cue_rail'], '')})"
                  f"   1쿠션수 {dep['first_number']:.1f}")
            rec["cue_number"] = dep["cue_number"]
            rec["first_number"] = dep["first_number"]
        rec["strong"] = len(contacts) > NATURAL_CUSHIONS
        rec["peak_speed"] = v
        rec["distance"] = dist
        # 쿠션은 있는 대로 전부 기록한다 — 대회전·다뱅크 경로를 보려면 다 필요하다.
        for k, c in enumerate(contacts, 1):
            num = read_number(table, scales, orientation, c.rail, c.point)
            gain = c.spin_gain
            line = (f"   {k}쿠션 {RAIL_KR.get(c.rail, c.rail)}"
                    f" ({c.point[0]:7.1f}, {c.point[1]:7.1f})")
            if num is not None:
                line += f"  번호 {num:6.1f}"
            if c.incoming is not None and c.outgoing is not None:
                line += f"  입사 {c.incoming:5.1f}도 반사 {c.outgoing:5.1f}도 차이 {gain:+5.1f}도"
            if c.speed_in is not None:
                line += f"  속도 {c.speed_in/1000:4.2f}m/s"
                if c.speed_out is not None and c.speed_in > 0:
                    line += f"→{c.speed_out/1000:4.2f}"
            print(line)
            rec["contacts"].append({
                "n": k, "rail": c.rail, "point": list(c.point), "number": num,
                "incoming": c.incoming, "outgoing": c.outgoing, "spin_gain": gain,
                "speed_in": c.speed_in, "speed_out": c.speed_out,
            })

        result.append(rec)
        paths.append(shot.path)
        # ★ 프레임 단위 궤적. 접점만 남기면 **쿠션 사이에서 얼마나 휘는지**를 못 잰다
        #   (사용자: '4쿠션 후 좌측으로 굴러간다'). 0808 때 이게 없어서 못 쟀다.
        frames.append({"shot": n, "fps": shot.fps,
                       "points": [[f, round(x, 1), round(y, 1)] for f, x, y in shot.points]})
        print()

    print(f"제외: " + ", ".join(f"{k} {v}" for k, v in dropped.items() if v)
          + f"   →  유효 샷 {len(result)}개\n")

    stem = Path(video).stem
    js = out_dir / f"{stem}_track.json"
    js.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"결과 저장: {js}")

    pj = out_dir / f"{stem}_path.json"
    pj.write_text(json.dumps({"_desc": "프레임 단위 궤적 (쿠션 사이 휨·천 마찰을 재는 데 쓴다)",
                              "_columns": ["frame", "x_mm", "y_mm"], "shots": frames},
                             ensure_ascii=False), encoding="utf-8")
    print(f"궤적 저장: {pj}  ({sum(len(f['points']) for f in frames)}점)")

    csv_path = out_dir / f"{stem}_track.csv"
    write_csv(csv_path, result)
    print(f"표 저장: {csv_path}")

    png = out_dir / f"{stem}_track.png"
    cv2.imwrite(str(png), draw_overlay(top, shots, table))
    print(f"궤적 그림: {png}")

    shot_dir = out_dir / f"{stem}_shots"
    shot_dir.mkdir(exist_ok=True)
    for rec, path in zip(result, paths):
        cv2.imwrite(str(shot_dir / f"shot{rec['shot']:04d}.png"), draw_shot(rec, path, table))
    print(f"샷별 그림: {shot_dir}  ({len(result)}장)\n")
    return len(result)


def write_csv(path: Path, result: list[dict]) -> None:
    """엑셀에서 바로 볼 수 있는 표. **한 줄이 쿠션 터치 하나**다.

    실측값만 담는다. 공식으로 계산한 값이나 오차는 넣지 않는다 (사용자 확정).
    쿠션은 1·2·3·4·5·6·7… 있는 대로 전부 들어간다.
    """
    import csv

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["샷", "시각_분", "방향", "총쿠션수", "최고속도_ms", "이동거리_mm",
                     "수구x_mm", "수구y_mm", "수구수", "1쿠션수",
                     "쿠션순번", "레일", "x_mm", "y_mm", "레일번호",
                     "입사각", "반사각", "차이", "속도_들어올때_ms", "속도_나갈때_ms"])
        for r in result:
            n_total = len(r["contacts"])
            cue = r.get("cue") or [None, None]
            for c in r["contacts"]:
                wr.writerow([
                    r["shot"], _r(r.get("minute"), 2), r["orientation"], n_total,
                    _r(r.get("peak_speed"), 2), _r(r.get("distance"), 0),
                    _r(cue[0]), _r(cue[1]),
                    _r(r.get("cue_number")), _r(r.get("first_number")),
                    c["n"], RAIL_KR.get(c["rail"], c["rail"]),
                    _r(c["point"][0]), _r(c["point"][1]), _r(c["number"]),
                    _r(c["incoming"]), _r(c["outgoing"]), _r(c["spin_gain"]),
                    _r((c.get("speed_in") or 0) / 1000, 2) if c.get("speed_in") else "",
                    _r((c.get("speed_out") or 0) / 1000, 2) if c.get("speed_out") else "",
                ])


def _r(v, nd: int = 1):
    return "" if v is None else round(float(v), nd)


SCALE = 0.42            # mm → px
MARGIN = 70             # 도면 여백 (쿠션·다이아몬드 자리)


def _diagram(table: Table):
    """정확한 비율의 당구대 도면을 그린다.

    ⚠️ 원근보정한 **사진** 위에는 그리지 않는다. 사진을 자를 때 쿠션 날을 밝기로
       찾는데 그게 최대 190mm까지 어긋난다. 그 위에 좌표를 늘여 그리면 궤적이
       쿠션을 뚫고 프레임까지 나간 것처럼 보인다 (사용자 지적). 좌표는 공 자신을
       자로 삼아 맞춘 값이라 정확하므로, 도면 쪽을 정확히 그리는 것이 맞다.
    """
    import cv2
    import numpy as np

    w, h = table.width, table.height
    img = np.full((int(h * SCALE) + MARGIN * 2, int(w * SCALE) + MARGIN * 2, 3), 28, np.uint8)

    def px(p):
        return int(MARGIN + p[0] * SCALE), int(MARGIN + (h - p[1]) * SCALE)

    cv2.rectangle(img, px((0, 0)), px((w, h)), (95, 70, 45), -1)      # 천
    cv2.rectangle(img, px((0, 0)), px((w, h)), (235, 235, 235), 2)    # 쿠션 날
    for i in range(9):                                               # 장쿠션 8등분
        for y, dy in ((0, 20), (h, -20)):
            x, yy = px((w * i / 8, y))
            cv2.circle(img, (x, yy + dy), 3, (255, 255, 255), -1)
            cv2.putText(img, str(i), (x - 4, yy + (38 if dy > 0 else -28)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (190, 190, 190), 1)
    for i in range(5):                                               # 단쿠션 4등분
        for x, dx in ((0, 20), (w, -20)):
            xx, y = px((x, h * i / 4))
            cv2.circle(img, (xx + dx, y), 3, (255, 255, 255), -1)
    return img, px


def draw_overlay(top, shots, table: Table):
    """모든 샷을 한 장에 겹쳐 그린다 (전체 훑어보기용)."""
    import cv2
    import numpy as np

    img, px = _diagram(table)
    colors = [(80, 220, 255), (120, 255, 140), (255, 160, 80), (255, 120, 220)]
    for i, shot in enumerate(shots):
        pts = np.array([px((x, y)) for _, x, y in shot.points], np.int32)
        cv2.polylines(img, [pts], False, colors[i % len(colors)], 1)
    return img


def draw_shot(rec: dict, path, table: Table):
    """샷 하나를 그린다 — 수구 출발점, 각 쿠션 접점, 입사각·반사각."""
    import cv2
    import numpy as np

    img, px = _diagram(table)
    if path:
        cv2.polylines(img, [np.array([px(p) for p in path], np.int32)], False, (80, 220, 255), 2)
        for p in path:
            cv2.circle(img, px(p), 1, (255, 255, 255), -1)

    cue = rec.get("cue")
    if cue:
        cv2.circle(img, px(cue), 9, (255, 255, 255), 2)
        cv2.putText(img, "cue", (px(cue)[0] + 12, px(cue)[1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    for c in rec["contacts"]:
        p = px(c["point"])
        cv2.circle(img, p, 7, (70, 70, 255), 2)
        txt = f"{c['n']}"
        if c["number"] is not None:
            txt += f" [{c['number']:.0f}]"
        if c["incoming"] is not None and c["outgoing"] is not None:
            txt += f" {c['incoming']:.0f}>{c['outgoing']:.0f}"
        dy = -12 if c["point"][1] < table.height / 2 else 22
        cv2.putText(img, txt, (p[0] - 20, p[1] + dy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

    # cv2는 한글을 못 그린다 → 방향만 알파벳으로 (L/R 좌우, T/B 상하)
    side = "".join({"좌": "L", "우": "R", "상": "T", "하": "B"}.get(ch, "")
                   for ch in rec.get("orientation", ""))
    head = f"shot {rec['shot']}  {rec['minute']:.2f}min  from {side}"
    if rec.get("cue_number") is not None:
        head += f"  cue#{rec['cue_number']:.0f} -> 1st#{rec['first_number']:.0f}"
    cv2.putText(img, head, (MARGIN, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    return img


def vtrack_contacts(shot, table: Table):
    from vision import track as vtrack
    return vtrack.find_contacts(shot, table.width, table.height, table.ball_diameter)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
