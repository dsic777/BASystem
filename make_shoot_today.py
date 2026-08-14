"""오늘(2026-08-14) 당구장에서 찍을 것 → C:\\sc\\촬영T1.png · 촬영T2.png

    python c:\\Portfolio\\billiards\\make_shoot_today.py

사용자: '지금 당구장 갈건데 더 찍어야 할거 없나요. 기존 파이브엔하프도 다시 한번
        찍어볼까요. 2시반 최대로 3팁방향으로 50출발 10포인트 간격으로 한바퀴 등.
        또 못찍은 부분 등 이미지로 정리해서 주세요.'

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

SETS = [
    dict(title="A  47 / 48  —  그 배치 그대로", shots="10샷", file="A_4748.mp4",
         head=["", "샷 수", "무엇을 보나"],
         rows=[["빈쿠션 · 공 하나", "10샷", "3쿠션이 0 아래인가 4 쪽인가"]],
         w=[430, 170, 620]),
    dict(title="B  87% 두께 · 당점 찾기      ★ 오늘 제일 급하다", shots="15샷", file="B_87.mp4",
         head=["", "샷 수", "무엇을 보나"],
         rows=[["상단 1팁", "5샷", "앱은 61도라고 한다"],
               ["중단",     "5샷", "표는 70도라고 한다"],
               ["하단 1팁", "5샷", "표는 78도라고 한다"]],
         w=[430, 170, 620]),
    dict(title="C  파이브앤하프 한 바퀴  (2시30분 3팁 · 수구 50)", shots="25샷",
         file="C_5half.mp4",
         head=["1쿠션", "10", "20", "30", "40", "50"],
         rows=[["수구 50", "5샷", "5샷", "5샷", "5샷", "5샷"]],
         w=[280, 188, 188, 188, 188, 188]),
    dict(title="D+E  쿠션 감속 · 세기      ★ 한 번에 찍는다", shots="15샷",
         file="DE_roll.mp4",
         head=["", "약", "중", "강"],
         rows=[["공 하나 · 같은 자리 · 같은 방향", "5샷", "5샷", "5샷"]],
         w=[560, 200, 200, 240]),
]

LAY = [
    dict(name="A  47 / 48", cue=(394, 1000), aim=(915, 0),
         note=["좌측 위에서 하단 50 근처로", "9시30분 3팁 · 중"]),
    dict(name="B  87% 두께", cue=(1900, 300), aim=(1210, 505),
         note=["거의 정면 · 살짝 비켜", "두께 고정 · 당점만 바꾼다"]),
    dict(name="D+E  감속 · 세기", cue=(320, 300), aim=(2300, 1120),
         note=["50 에서 대각선 코너로", "멈추면 같은 자리에 다시", "무회전 · 세기만 바꾼다"]),
]


def table(p, s):
    p.h(s["title"] + "      " + s["shots"], HOT)
    p.grid(s)


def pageT1():
    p = Page("당구장 촬영 — 2026-08-14", "오늘 찍을 것 75샷")

    p.h("★ 오늘의 두 가지가 제일 급하다", RED)
    p.t("A  47에서 48을 치면 3쿠션이 어디로 오나   →  앱의 반사 모델이 맞는지 갈린다", INK, 30)
    p.t("B  87% 두께에서 어느 당점이 그 길을 내나  →  분리각 표가 맞는지 갈린다", INK, 30)

    p.rule()
    for s in SETS[:3]:
        table(p, s)
        p.gap(6)
    p.t("C 는 사용자가 말한 그것이다. 시스템 기준점이 이 다이에서 얼마나 어긋나는지 나온다.", DIM, 28)

    p.rule()
    for s in SETS[3:]:
        table(p, s)
        p.gap(6)
    p.t("D+E 는 배치를 안 정한다. 공 하나로 길게 돌리고 멈출 때까지 두면 셋 다 나온다 —", DIM, 28)
    p.t("   쿠션 손실(실측 0.43~0.60 vs 앱 0.80) · 바닥 마찰 · 약중강의 실제 속도.", DIM, 28)
    p.save("촬영T1.png")


def pageT2():
    p = Page("배치와 공통 조건", "촬영T1 의 A · B")

    y = p.y + 26
    for i, L in enumerate(LAY):
        mw = 388
        ox = 60 + i * (mw + 34)
        p.d.text((ox + mw / 2, y - 12), L["name"], font=f(28, True), fill=HOT, anchor="ms")
        m = Mini(p, ox, y + 16, mw)
        m.line([L["cue"], L["aim"]], HOT, 5)
        m.ball(*L["cue"], "#f2f0e8")
        m.label(L["cue"][0] + 210, L["cue"][1] - 50, "수구", INK, 24)
        if i == 1:
            m.ball(1150, 560, "#d8382e")
            m.label(1150, 730, "1적구", INK, 22)
        for j, ln in enumerate(L["note"]):
            p.d.text((ox + mw / 2, m.bottom + 22 + j*32), ln,
                     font=f(23, True), fill=INK, anchor="ma")
    p.y = y + 340

    p.rule()
    p.h("텍스트로 당점을 넣어 주십시오 (캡컷)", GRN)
    p.t("★ 다이 바깥 여백에 넣는다. 다이 안에 넣으면 흰 글씨를 공으로 잡아 추적이 깨진다.", HOT, 29)
    p.t("★ 그 당점으로 치는 동안 계속 떠 있게. 3초짜리 제목 카드면 놓친다.", HOT, 29)
    p.t("이름은 쓰시는 대로 — 12시 3팁 · 무팁 · 중단 · 6시 1팁 · 2시30분 3팁", INK, 28)

    p.rule()
    p.h("공통 — 지난번과 같다", BLU)
    p.t("① 카메라 고정 (우측하단). 네 코너가 다 보이게", INK, 29)
    p.t("② 한 샷이 완전히 멈춘 뒤 다음 샷. 구르는 중에 손이 들어오면 안 된다", INK, 29)
    p.t("③ B 는 공 두 개만 (수구 + 1적구). 세 번째 공이 있으면 두께를 못 잰다", INK, 29)
    p.t("④ 수구가 1적구까지 1미터 이상 굴러오게. 붙여 놓으면 충돌 직전 속도를 못 잰다", INK, 29)
    p.t("⑤ 숫자를 정확히 맞추려 애쓰지 않는다. 무리로 갈라지기만 하면 된다", INK, 29)

    p.rule()
    p.h("시간이 모자라면", RED)
    p.t("B → A → C → D+E  순서로. B 하나만 찍어 와도 오늘 것은 건진다.", INK, 30)
    p.save("촬영T2.png")


pageT1()
pageT2()
