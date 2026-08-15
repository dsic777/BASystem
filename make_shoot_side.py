"""부호를 가리는 촬영 — 당점만 3시로 15샷 → C:\\sc\\촬영S1.png · 촬영S2.png

    python c:\\Portfolio\\billiards\\make_shoot_side.py

2026-08-15. 실측 영상 6편 408접점을 부호 있는 팁수(s) 하나의 축으로 모아 보니
표가 s 순서대로 안 늘어섰다 — 15~25도 칸에서 s=-3(역)이 +19.1도 벌어지는데
s=+2(순)는 -0.1도로 거울이다. 역이 순보다 더 벌어질 수는 없다.

두 영상이 같은 칸에서 반대로 말하고 있다. 가르는 방법은 하나 —
같은 배치에서 당점만 거울로 뒤집어 어느 쪽이 더 벌어지는지 본다.

⚠️ 그림 안에 ⚠️ 와 체크표시와 빼기표시를 쓰지 말 것. malgun.ttf 에 없어서 깨진다.
   ★ ※ ▶ ① → × · 는 잘 나온다.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_src = (HERE / "make_shoot.py").read_text(encoding="utf-8")
_head = _src[: _src.index("# ══════════════════════════════════════════════ 촬영0")]
exec(compile(_head, "make_shoot.py(head)", "exec"))          # noqa: S102

OUT = Path(r"C:\sc")

# ───────────────────────────────────────────── 배치는 촬영R2 와 똑같다
#   앱 좌표: 원점 좌하단 · 장축 x 2448 · 단축 y 1224
#   위아래로 뒤집어 그린다 — 카메라가 우측하단이고 사용자은 반대편에서 치신다.
#   ★ 바꾸는 것은 당점 하나다. 9시 2팁(찍어 온 것) → 3시 2팁(이번에 찍을 것).
LAY_A = dict(name="① 얕게", cue=(1400, 1074), aim=(900, 0), ain=25)
LAY_B = dict(name="② 눕게", cue=(2100, 924), aim=(800, 0), ain=55)

SET_G = dict(
    title="G  당점만 거울로 뒤집는다 — 3시 2팁", shots=15, file="G_3시.mp4",
    head=["", "약", "중", "강", "파일"],
    rows=[["① 얕게 (입사 25도) · 3시 2팁", "5샷", "5샷", "5샷", "G_3시.mp4"]],
    w=[520, 150, 150, 150, 200],
)
SET_H = dict(
    title="H  시간이 남으면 — 눕는 배치도 같이", shots=15, file="H_3시눕게.mp4",
    head=["", "약", "중", "강", "파일"],
    rows=[["② 눕게 (입사 55도) · 3시 2팁", "5샷", "5샷", "5샷", "H_3시눕게.mp4"]],
    w=[520, 150, 150, 150, 200],
)


def tipface(p, cx, cy, R, hour=3, tips=2, ring=None):
    """수구를 뒤에서 본 얼굴에 당점을 찍는다. 3팁 자리가 반지름의 0.72."""
    d = p.d
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#f2f0e8", outline="#8a93a0", width=3)
    d.line([cx - R, cy, cx + R, cy], fill="#c9ccd2", width=2)
    d.line([cx, cy - R, cx, cy + R], fill="#c9ccd2", width=2)
    step = R * 0.72 / 3
    ang = {3: (1, 0), 9: (-1, 0), 12: (0, -1), 6: (0, 1)}[hour]
    for k in (1, 2, 3):
        qx, qy = cx + ang[0] * step * k, cy + ang[1] * step * k
        d.ellipse([qx - 5, qy - 5, qx + 5, qy + 5], fill="#9aa4b2")
        d.text((qx, qy + 26), str(k), font=f(20), fill="#6d7684", anchor="mm")
    hx, hy = cx + ang[0] * step * tips, cy + ang[1] * step * tips
    d.ellipse([hx - 19, hy - 19, hx + 19, hy + 19],
              fill=(ring or RED), outline="#14161a", width=3)


def mini(p, L, ox, y, mw, tip_hour, col, lab):
    """배치 하나. 노란선이 치는 길, 색선이 예상 경로, 점선이 거울."""
    cx, cy = L["cue"]
    ax, ay = L["aim"]
    dx, dy = ax - cx, ay - cy
    p.d.text((ox + mw / 2, y - 14), lab, font=f(30, True), fill=col, anchor="ms")
    m = Mini(p, ox, y + 16, mw)
    m.line([L["aim"], (ax + dx * 0.95, ay - dy * 0.95)], DIM, 4, dash=True)     # 거울
    wide = 0.42 if tip_hour == 9 else 1.9                                       # 좁게 / 넓게
    m.line([L["aim"], (ax + dx * wide, ay - dy * 0.95)], col, 7)
    m.line([L["cue"], L["aim"]], HOT, 6)
    m.ball(cx, cy, "#f2f0e8")
    m.label(cx + 190, cy - 40, "수구", INK, 26)
    return m


# ══════════════════════════════════════════════ 촬영S1
def pageS1():
    p = Page("당구장 촬영 — 부호를 가린다", "2026-08-15 · 15샷이면 끝난다")

    p.h("왜 가나 — 실측 두 편이 서로 반대로 말한다", RED)
    p.t("영상 6편 408접점을 '부호 있는 팁수' 하나의 축으로 모았다. 순·역을 갈래로 치지 않고", INK, 29)
    p.t("팁수에 부호를 붙여 표 하나로 만들려는 것이다. 그런데 표가 순서대로 안 늘어선다.", INK, 29)
    p.gap(10)
    p.box(["입사 15~25도 칸",
           "     역 3팁 (원쿠션걸어치기 · 24접점)   거울보다 +19.1도 벌어진다",
           "     순 2팁 (역각25/55     · 21접점)   거울 그대로  -0.1도",
           "",
           "역이 순보다 더 벌어질 수는 없다. 둘 중 하나는 부호가 뒤집혀 있다."],
          col=RED, fill="#231a1a", sz=27)
    p.gap(10)
    p.t("어느 쪽이 뒤집혔는지는 표를 아무리 들여다봐도 안 나온다. 배치도 속도도 다 다르기 때문이다.", DIM, 27)
    p.t("가르는 방법은 하나다 ▶ 같은 배치에서 당점만 거울로 뒤집어 어느 쪽이 더 벌어지나 본다.", HOT, 30)

    p.rule()
    p.h("이미 찍어 오신 것이 절반이다", GRN)
    p.t("역각25.mp4 ▶ ① 얕게 배치 · 9시 2팁 · 1쿠션 27접점. 입사 26도 → 반사 18~25도 (좁아졌다)", INK, 29)
    p.t("이번에 찍을 것 ▶ 똑같은 배치 · 당점만 3시 2팁. 그것 하나만 바꾼다.", HOT, 30)
    p.gap(8)
    p.t("배치가 같으니 다이도 거리도 입사각도 다 고정이다. 움직이는 변수가 당점 하나뿐이라", DIM, 27)
    p.t("15샷이면 답이 나온다. 표를 만드는 촬영이 아니라 부호 하나를 가르는 촬영이다.", DIM, 27)

    p.rule()
    p.h("★ 판정 — 결과가 어느 쪽이든 그날로 끝난다", BLU)
    p.gap(4)
    p.box(["3시가 45도 언저리로 크게 벌어지면",
           "     → 내 부호가 맞다. 9시가 역회전이었던 것이 맞고, 원쿠션걸어치기 쪽이 뒤집혀 있다.",
           "",
           "3시가 20도 언저리로 좁아지면",
           "     → 내 부호가 뒤집혀 있다. 앱의 순·역이 통째로 반대였다는 뜻이다.",
           "",
           "3시가 26도 그대로 나오면",
           "     → 이 배치에서는 좌우 회전이 아예 안 먹는다. 그것도 답이다."],
          col=BLU, fill="#171d26", sz=27)
    p.gap(10)
    p.t("첫 샷 하나로 눈으로도 갈린다. 45도와 20도는 코너 하나 차이라 화면에서 바로 보인다.", HOT, 29)

    p.rule()
    table_g = SET_G
    p.h(table_g["title"] + "      " + str(table_g["shots"]) + "샷", HOT)
    p.grid(table_g)
    p.t("★ 당점은 15샷 내내 고정이다 ▶ 3시 2팁 · 높이는 중단. 촬영S2 그림 참고", HOT, 29)
    p.t("★ 공을 하나만 놓는다. 빈쿠션이라야 분리각이 안 섞인다.", HOT, 29)
    p.t("★ 멈출 때까지 손대지 않는다. 쿠션마다 남은 힘이 같이 잡힌다.", HOT, 29)

    p.gap(12)
    p.h(SET_H["title"] + "      " + str(SET_H["shots"]) + "샷", DIM)
    p.grid(SET_H)
    p.t("역각55.mp4 는 9시 2팁인데 입사 49도가 61도로 벌어졌다. 역회전인데 벌어진 것이라", DIM, 27)
    p.t("아직 설명이 없다. 같은 배치에 3시를 주면 그 수수께끼도 같이 갈린다. 시간 되실 때만.", DIM, 27)
    p.save("촬영S1.png")


# ══════════════════════════════════════════════ 촬영S2
def pageS2():
    p = Page("바꾸는 것은 당점 하나", "① 얕게 배치 · 빈쿠션 · 공 하나")

    p.h("찍어 오신 것 (9시)  ↔  이번에 찍을 것 (3시)", BLU)
    p.t("공은 하단 쿠션을 왼쪽으로 타고 흐른다. 9시는 그 반대로 미는 회전(역)이고", INK, 29)
    p.t("3시는 흐르는 쪽으로 미는 회전(순)이다. 거울로 딱 뒤집은 짝이다.", INK, 29)
    p.gap(24)

    ty = p.y + 118
    tipface(p, 210, ty, 96, hour=9, tips=2, ring="#8a93a0")
    p.d.text((210, ty + 132), "9시 2팁 · 이미 찍음", font=f(28, True), fill=DIM, anchor="ma")
    p.d.text((210, ty + 172), "역각25.mp4 · 27접점", font=f(24), fill=DIM, anchor="ma")

    p.d.text((470, ty - 8), "→", font=f(72, True), fill=HOT, anchor="mm")

    tipface(p, 730, ty, 96, hour=3, tips=2)
    p.d.text((730, ty + 132), "3시 2팁 · 이번 15샷", font=f(28, True), fill=RED, anchor="ma")
    p.d.text((730, ty + 172), "높이는 정확히 한가운데", font=f(24), fill=RED, anchor="ma")

    p.y = ty + 210
    p.gap(8)
    p.t("★ 좌우만 오른쪽으로 2팁. 3팁까지 주지 않는다 — 찍어 온 것이 2팁이라야 짝이 맞는다.", HOT, 29)
    p.t("★ 높이(상하)는 건드리지 않는다. 밀어치기도 끌어치기도 아닌 정확한 중단이다.", HOT, 29)
    p.t("   높이가 흔들리면 분리각이 섞여 15샷이 통째로 버려진다.", INK, 28)

    p.rule()
    p.h("배치는 그때 그대로 — 수구 자리만 맞추면 된다", GRN)
    p.gap(10)

    y = p.y + 20
    mw = 560
    mini(p, LAY_A, 120, y, mw, 9, "#8a93a0", "찍어 온 것 · 9시 2팁 → 좁아졌다 (26도 → 18~25도)")
    m = mini(p, LAY_A, 120 + mw + 140, y, mw, 3, RED, "이번 15샷 · 3시 2팁 → 얼마나 벌어지나")
    p.d.text((120 + mw / 2, m.bottom + 26),
             "노란선 치는 길   ·   점선 거울   ·   회색선 실제로 나온 길",
             font=f(23), fill=DIM, anchor="ma")
    p.d.text((120 + mw + 140 + mw / 2, m.bottom + 26),
             "빨간선은 부호가 맞을 때의 예상 — 45도 언저리",
             font=f(23), fill=RED, anchor="ma")
    p.y = y + 400

    p.rule()
    p.h("세기 세 가지 — 지난번과 똑같이", HOT)
    p.t("약 ▶ 3쿠션쯤에서 힘이 빠지게      중 ▶ 평소 세기      강 ▶ 다섯 쿠션 이상 살아 돌게", INK, 30)
    p.t("세기가 바뀔 때 카메라에 손가락으로 약 1 · 중 2 · 강 3", DIM, 27)
    p.t("역각은 속도로 뒤집힌다는 것을 이미 쟀다 (1.0m/s 에서 3% · 3.3m/s 에서 63%).", DIM, 27)
    p.t("그래서 세기를 갈라 두면 부호와 속도 곡선이 한 번에 나온다.", DIM, 27)

    p.rule()
    p.h("공통", GRN)
    p.t("① 카메라 고정 ▶ 우측하단. 네 코너가 다 보이게", INK, 29)
    p.t("② 한 샷이 완전히 멈춘 뒤 다음 샷", INK, 29)
    p.t("③ 공은 하나만. 빈쿠션이라야 분리각이 안 섞인다", INK, 29)
    p.t("④ 숫자를 정확히 맞추려 애쓰지 않는다. 배치와 당점만 고정이면 된다", INK, 29)
    p.save("촬영S2.png")


pageS1()
pageS2()
