"""쿠션 반사를 **부호 있는 팁수** 하나의 축으로 모은다.

    python signed_tip.py 결과폴더 [결과폴더2 ...]
    python signed_tip.py 결과폴더 --write      data/measured_signed_tip.json 에 기록

왜 이렇게 보나 — 사용자 2026-08-15
    '앱에서 순 역으로 판정할 것이 아니라 팁수와 공의 방향을 합해서
     입사반사를 찾아낼 방법은 없을까요?'
    '이것도 많이 사용하는 길인데 공의 시작(1쿠션)은 역각입니다. 그런데 순각(2쿠션)으로
     바뀝니다. 이런 모든 경우를 고려하면 팁수에 따른 입사 반사각을 찾아야 합니다.'

    s = 팁수 × (회전이 미는 쪽) × (공이 쿠션을 따라 흐른 쪽)

        s > 0  순회전     s < 0  역회전     s = 0  무회전

    이러면 **순·역 판정이라는 것 자체가 없어진다.** 표 하나만 남는다 —
        나가는 각 = G(입사각, s, 속도)
    지금 앱(bend)은 갈래를 쳐서 서로 다른 공식 두 개를 쓴다. 그래서 s=0 근처에서
    값이 10~17도 튄다. 같은 무회전인데 좌우 부호만 뒤집으면 값이 달라진다.

부호 규칙 (물리)
    9시(좌) 당점 = 큐가 공의 왼쪽을 앞으로 민다 → 위에서 보면 시계방향 → ω < 0
    3시(우) 당점 = 반시계 → ω > 0
    쿠션 접점의 표면속도  v_s = ω ẑ × (−R n) = −ωR·tg
    마찰이 미는 쪽        = −v_s 방향 = sign(ω)·tg
    그래서  e = +1 (3시 쪽) · −1 (9시 쪽),  sIn = sign(d·tg)
    순회전 = e·sIn > 0

    ★ 검산 — 상단 쿠션을 오른쪽으로 흐르는 공은 3시가 순이다.
      파이브앤하프가 2시30분을 쓰는 자리가 바로 그 자리다. 규칙이 맞는다.

⚠️ 팁이 **샷 내내 고정**인 영상만 쓴다.
   원쿠션걸어치기 보정용.mp4 는 '앱 가이드대로 치는 영상' 이라 샷마다 당점이 다르다.
   그것을 하나로 묶었다가 2026-08-15 에 사용자에게 지적받았다 (9.jpg).
"""
import json
import sys
from pathlib import Path

import numpy as np

# 쿠션 안쪽 법선(안으로) 과 접선
NORMAL = {"bottom": (0, 1), "top": (0, -1), "left": (1, 0), "right": (-1, 0)}
TANGENT = {r: (-n[1], n[0]) for r, n in NORMAL.items()}

# ── 영상별 당점. 팁수 · e(+1 = 3시 쪽 · −1 = 9시 쪽) · 한 줄 설명
#    ⚠️ 여기 없는 영상은 안 쓴다. 팁을 모르면 이 축에 못 올린다.
TIPS = {
    "1순위_충돌_편집 12시 2팁":      (0.0, 0, "12시 — 좌우 무회전"),
    "2순위_빈쿠션_편집 9시30분 2팁": (2.0, -1, "9시30분 2팁 (좌)"),
    "3순위_당점_편집 2시30분 3팁":   (3.0, +1, "2시30분 3팁 (우)"),
    "역각25":                        (2.0, -1, "9시 2팁 (좌)"),
    "역각55":                        (2.0, -1, "9시 2팁 (좌)"),
    # ★★★ 0806·0807·0808 — 당점 **2시30분 확정** (사용자 2026-08-15: "'2시30분 고정'으로 맞아요")
    #   그런데 이 축으로 읽으면 1694접점 중 1475개가 **역회전**이다.
    #   확인한 것 — 이 촬영들의 흐름은 bottom→오른쪽 · top→왼쪽 · right→위 · left→아래.
    #   같은 다이의 2순위_빈쿠션(9시30분 2팁)이 **똑같은 쿠션을 똑같은 방향으로** 흐른다.
    #   같은 흐름에 당점만 반대다. 둘 중 하나는 순, 하나는 역일 수밖에 없다.
    #   물리로 따지면 top 쿠션을 왼쪽으로 흐르는 공은 **9시(좌)가 순**이다.
    #   → 2순위(좌)가 순이고 **0806·7·8(우)이 역**이다.
    #   ⚠️ 그러면 measured_bounce.json 의 핵심 표(385접점)는 '순회전 2팁 표준' 으로
    #      쓰이고 있는데 실은 **역회전** 자료라는 뜻이 된다. 자세한 것은 그 파일의
    #      ★_핵심표가_역회전일_수_있다_2026_08_15 항목에 적어 두었다.
    "0808": (2.0, +1, "2시30분 (우) — 0808 표의 원본"),
    "0807": (2.0, +1, "2시30분 (우) — 같은 촬영 회차"),
    "0806": (2.0, +1, "2시30분 (우) — 같은 촬영 회차"),
}

AIN_BANDS = [(0, 15), (15, 25), (25, 35), (35, 45), (45, 55), (55, 90)]
S_BANDS = [(-3.5, -2.5, "역3팁"), (-2.5, -1.5, "역2팁"), (-0.5, 0.5, "무회전"),
           (1.5, 2.5, "순2팁"), (2.5, 3.5, "순3팁")]
V_BANDS = [(0, 900, "0.9m/s 미만"), (900, 1600, "0.9~1.6"), (1600, 9999, "1.6 이상")]


def load(folders):
    rows = []
    for folder in folders:
        for f in sorted(Path(folder).glob("*_track.json")):
            stem = f.name[: -len("_track.json")]
            hit = next((k for k in TIPS if k in stem), None)
            if hit is None:
                print(f"  건너뜀 (팁을 모른다) — {stem}")
                continue
            tip, e, note = TIPS[hit]
            shots = json.load(f.open(encoding="utf-8"))
            n = 0
            for sh in shots:
                prev = sh.get("cue")
                for c in sh.get("contacts", []):
                    p, rail = c.get("point"), c.get("rail")
                    if not p or rail not in TANGENT or prev is None:
                        prev = p
                        continue
                    tg = TANGENT[rail]
                    dt = (p[0] - prev[0]) * tg[0] + (p[1] - prev[1]) * tg[1]
                    prev = p
                    ain, aout = c.get("incoming"), c.get("outgoing")
                    if ain is None or aout is None or abs(dt) < 1e-6:
                        continue
                    s_in = 1 if dt > 0 else -1
                    rows.append({"s": e * s_in * tip, "ain": ain, "aout": aout,
                                 "v": c.get("speed_in") or 0.0, "cush": c.get("n"),
                                 "src": stem, "note": note})
                    n += 1
            print(f"  {note:24s} {stem[:30]:32s} 접점 {n:5d}")
    return rows


def grid(rows, key, fmt="%+.1f"):
    """입사각 × 부호있는 팁수 표. key(r) 가 칸 값이다."""
    out = []
    head = "  입사구간  " + "".join("%15s" % lb for _, _, lb in S_BANDS)
    out.append(head)
    for lo, hi in AIN_BANDS:
        line = "  %2d~%2d도 " % (lo, hi)
        for slo, shi, _ in S_BANDS:
            q = [r for r in rows if lo <= r["ain"] < hi and slo <= r["s"] < shi]
            line += "%15s" % ("·" if len(q) < 3 else
                              (fmt + " (%d)") % (np.median([key(r) for r in q]), len(q)))
        out.append(line)
    return out


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    folders = [a for a in argv if not a.startswith("--")]
    rows = load(folders)
    if not rows:
        print("접점이 없다.")
        return 1
    print(f"\n총 {len(rows)} 접점\n")

    print("■ 거울에서 벗어난 각  (+ 벌어짐 · − 좁아짐)")
    for l in grid(rows, lambda r: r["aout"] - r["ain"]):
        print(l)

    print("\n■ 나가는 각 자체")
    for l in grid(rows, lambda r: r["aout"], "%.1f"):
        print(l)

    print("\n■ 역(s<0) 은 속도로 갈리나")
    for lo, hi in [(15, 25), (25, 35), (35, 50), (50, 90)]:
        for vlo, vhi, vl in V_BANDS:
            q = [r for r in rows if lo <= r["ain"] < hi and r["s"] < -0.5
                 and vlo <= r["v"] < vhi]
            if len(q) >= 3:
                print("   입사 %2d~%2d · %-11s  %4.1f→%4.1f  %+5.1f  (%d)" % (
                    lo, hi, vl, np.mean([r["ain"] for r in q]),
                    np.median([r["aout"] for r in q]),
                    np.median([r["aout"] - r["ain"] for r in q]), len(q)))

    print("\n■ 쿠션 순번으로 달라지나 (회전이 닳는가)")
    for cu in (1, 2, 3, 4, 5):
        for slo, shi, lb in S_BANDS:
            q = [r for r in rows if r["cush"] == cu and slo <= r["s"] < shi]
            if len(q) >= 5:
                print("   %d쿠션 %-6s  입사 %4.1f → %4.1f  %+5.1f  (%d)" % (
                    cu, lb, np.mean([r["ain"] for r in q]),
                    np.median([r["aout"] for r in q]),
                    np.median([r["aout"] - r["ain"] for r in q]), len(q)))

    if "--write" in argv:
        cells = []
        for lo, hi in AIN_BANDS:
            for slo, shi, lb in S_BANDS:
                q = [r for r in rows if lo <= r["ain"] < hi and slo <= r["s"] < shi]
                if len(q) < 3:
                    continue
                cells.append([f"{lo}~{hi}", lb,
                              round(float(np.mean([r["ain"] for r in q])), 1),
                              round(float(np.median([r["aout"] for r in q])), 1),
                              round(float(np.median([r["aout"] - r["ain"] for r in q])), 1),
                              len(q)])
        doc = {
            "_desc": "부호 있는 팁수 축으로 모은 쿠션 반사 실측",
            "_why": "순·역 갈래를 없애고 표 하나로 만들기 위한 것. signed_tip.py 가 만든다",
            "_source": "팁이 고정된 영상만. 자세한 것은 signed_tip.py 의 TIPS",
            "_부호": "s = 팁수 × (회전이 미는 쪽 e) × (흐른 쪽). e=+1 3시쪽 · −1 9시쪽",
            "_columns": ["입사구간", "부호있는팁", "입사평균", "나가는각", "거울에서벗어난각", "표본수"],
            "table": cells,
            "_접점수": len(rows),
        }
        p = Path("data/measured_signed_tip.json")
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n기록: {p}  ({len(cells)}칸 · {len(rows)}접점)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
