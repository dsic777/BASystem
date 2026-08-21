"""천 갈고 나서 찍을 것 + 옛 천/새 천 차이 → C:\\sc\\촬영N1~N3.png

    python c:\\Portfolio\\billiards\\make_shoot_next.py

    촬영N1  한 장 요약 — 안 찍는 것 / 찍는 것 셋 / 뺀 것
    촬영N2  세기 촬영 배치 (제일 급한 것)
    촬영N3  0808 옛 천 → 0821 새 천, 무엇이 달라졌나

★ 2026-08-21 사장님: '촬영계획을 다시 세워주세요. 실제 필요한 것만 합시다.'
                     '장황한 설명보다 가능하면 그림으로 해 주세요.'
  → 옛 계획(촬영0~5)은 8월 11~17일 것이다. 이미 찍은 것·필요 없어진 것이 섞여 있다.
  → 이 그림과 촬영계획.md 가 같은 표를 쓴다. 하나만 고치면 안 된다.

⚠️ 그림 **안**에 ⚠ · ✓ · − 를 쓰지 말 것. malgun.ttf 에 없어서 □ 로 깨진다.
   ★ ※ ▶ ① → × · 는 잘 나온다.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_shoot import PW, PH, OUT, BG, INK, DIM, HOT, RED, GRN, BLU, f, Mini


class Page:
    def __init__(self, title, sub=""):
        self.im = Image.new("RGB", (PW, PH), BG)
        self.d = ImageDraw.Draw(self.im)
        self.d.rectangle([0, 0, PW, 150], fill="#1a2029")
        self.d.line([0, 150, PW, 150], fill=HOT, width=5)
        self.d.text((60, 48), title, font=f(58, True), fill=HOT)
        if sub:
            self.d.text((PW - 60, 66), sub, font=f(30), fill=DIM, anchor="ra")
        self.y = 195

    def gap(self, n=24):
        self.y += n

    def h(self, txt, col=INK, sz=38):
        self.gap(12)
        self.d.text((60, self.y), txt, font=f(sz, True), fill=col)
        self.y += sz + 18

    def t(self, txt, col=INK, sz=30, x=60, bold=False):
        self.d.text((x, self.y), txt, font=f(sz, bold), fill=col)
        self.y += sz + 12

    def rule(self):
        self.gap(8)
        self.d.line([60, self.y, PW - 60, self.y], fill="#2c333d", width=3)
        self.gap(14)

    def card(self, no, title, lines, col=HOT):
        h = len(lines) * 40 + 100
        self.d.rounded_rectangle([56, self.y, PW - 56, self.y + h],
                                 radius=18, fill="#1a2029", outline=col, width=3)
        self.d.ellipse([82, self.y + 22, 82 + 52, self.y + 22 + 52], fill=col)
        self.d.text((82 + 26, self.y + 22 + 26), no, font=f(32, True),
                    fill="#12151a", anchor="mm")
        self.d.text((162, self.y + 48), title, font=f(36, True), fill=col, anchor="lm")
        yy = self.y + 94
        for txt, c, sz in lines:
            self.d.text((162, yy), txt, font=f(sz), fill=c)
            yy += 40
        self.y += h + 20

    def grid(self, w, head, rows, sz=28, rh=None):
        rh = rh or sz + 26
        x0 = (PW - sum(w)) // 2
        y0 = self.y
        xs = [x0]
        for c in w:
            xs.append(xs[-1] + c)
        n = len(rows) + 1
        self.d.rectangle([x0, y0, xs[-1], y0 + rh], fill="#242c37")
        for j, txt in enumerate(head):
            if txt:
                self.d.text(((xs[j] + xs[j + 1]) / 2, y0 + rh / 2), txt,
                            font=f(sz - 2, True), fill=HOT, anchor="mm")
        for i, row in enumerate(rows):
            yy = y0 + rh * (i + 1)
            if i % 2:
                self.d.rectangle([x0, yy, xs[-1], yy + rh], fill="#171d25")
            for j, txt in enumerate(row):
                col = HOT if j == 0 else INK
                if txt == "·":
                    col = "#4a535f"
                if txt.endswith(".mp4") or txt.endswith(".jpg"):
                    col = GRN
                self.d.text(((xs[j] + xs[j + 1]) / 2, yy + rh / 2), txt,
                            font=f(sz - (4 if col == GRN else 0), j == 0),
                            fill=col, anchor="mm")
        for i in range(n + 1):
            yy = y0 + rh * i
            self.d.line([x0, yy, xs[-1], yy], fill="#3a4450", width=2)
        for x in xs:
            self.d.line([x, y0, x, y0 + rh * n], fill="#3a4450", width=2)
        self.d.rectangle([x0, y0, xs[-1], y0 + rh * n], outline=HOT, width=3)
        self.y = y0 + rh * n + 22

    def bars(self, title, a, b, unit="", full=None, note="", ncol=GRN):
        """옛 천(a) / 새 천(b) 막대 두 개."""
        full = full or max(a, b) * 1.25
        x0, w = 500, 640
        self.d.text((60, self.y + 30), title, font=f(32, True), fill=INK, anchor="lm")
        for i, (lb, v, col) in enumerate([("0808", a, "#5a6472"), ("0821", b, HOT)]):
            yy = self.y + 8 + i * 44
            self.d.text((x0 - 20, yy + 16), lb, font=f(24, True), fill=DIM, anchor="rm")
            self.d.rectangle([x0, yy, x0 + w, yy + 32], fill="#1a2029")
            self.d.rectangle([x0, yy, x0 + w * min(1, v / full), yy + 32], fill=col)
            self.d.text((x0 + w + 20, yy + 16), (f"{v:.2f}{unit}" if unit=="" else f"{v:g}{unit}"), font=f(26, True),
                        fill=INK, anchor="lm")
        if note:
            self.d.text((PW - 70, self.y + 52), note, font=f(28, True), fill=ncol, anchor="rm")
        self.y += 112

    def save(self, name):
        OUT.mkdir(parents=True, exist_ok=True)
        self.im.save(OUT / name)
        print(OUT / name)


# ══════════════════════════════════════════════ 촬영N1 — 한 장 요약
def page1():
    p = Page("촬영 계획  다시 세움", "2026-08-21 · 실제 필요한 것만")

    p.h("안 찍는다 — 0821 영상에서 이미 나왔다", GRN, 34)
    p.grid([400, 280, 260, 320],
           ["", "어디서", "표본", "상태"],
           [["쿠션 반사표", "0821", "240접점", "넣었다 v543"],
            ["쿠션에서 남는 몫", "0821", "307구간", "0.79 · 앱과 같다"],
            ["구름 저항", "0821", "195구간", "0.46 · 앱은 1.00"],
            ["파이브앤하프 보정", "0821", "46샷", "-2.11"],
            ["두께별 분리각", "사장님 제공", "·", "안 잰다"]],
           sz=26)

    p.rule()
    p.h("찍을 것 — 셋뿐이다", HOT, 38)

    p.card("1", "팁 위치   사진 2장   5초", [
        ("공 정면 뒤에서 팁을 공에 댄 채 접사", INK, 29),
        ("중심에서 옆으로 나간 거리 / 공 지름 으로 잰다", DIM, 27),
        ("비스듬히 찍으면 못 쓴다. 정면이라야 한다", RED, 27),
        ("나오는 것 : 실제 팁수 (2 인지 2.5 인지)", GRN, 27),
    ], col=HOT)

    p.card("2", "세기   15샷   지금 제일 급하다", [
        ("공 하나 · 빈쿠션 · 당점은 평소 그 자리 그대로", INK, 29),
        ("약 5샷 / 중 5샷 / 강 5샷 을 한 파일에 이어서", INK, 29),
        ("끝까지 굴러가게 둔다. 중간에 공을 잡지 않는다", RED, 27),
        ("나오는 것 : 강 중 약 버튼이 살아난다", GRN, 27),
    ], col=RED)

    p.card("3", "파이브앤하프 다시   천 안정 후", [
        ("0821 과 똑같이. 공 하나 · 빈쿠션 · 8월 28일 이후", INK, 29),
        ("0821 은 천 간 그날이라 임시 값이다", DIM, 27),
        ("나오는 것 : 반사표와 보정을 확정한다", GRN, 27),
    ], col=BLU)

    p.rule()
    p.h("뺀 것", DIM, 32)
    p.t("×  다른 다이 기준점 30샷      내 앱이다. 남의 다이는 안 본다", DIM, 26)
    p.t("×  두께별 분리각 45샷         사장님이 준 값을 쓴다. 안 잰다", DIM, 26)
    p.t("×  역회전 · 역각 30샷         쓰는 자리가 접시 하나뿐. 설계부터", DIM, 26)
    p.t("×  3팁 채우기 15샷            늘 같은 자리를 치신다. 못 찍는다", DIM, 26)
    p.t("×  상품화 캘리브레이션        나중", DIM, 26)

    p.save("촬영N1.png")


# ══════════════════════════════════════════════ 촬영N2 — 세기 배치
def page2():
    p = Page("세기 촬영   15샷", "제일 급한 것 · 공 하나 · 빈쿠션")

    p.h("배치 — 0821 과 같다. 편한 대로 치시면 된다", INK, 34)

    p.gap(60)
    m = Mini(p, 150, p.y, 1100)
    m.ball(320, 230, "#fffef9", txt="수구")
    m.line([(320, 230), (1080, 0), (2448, 460), (700, 1224), (0, 700), (900, 0)],
           HOT, 5)
    p.y = m.bottom + 40
    p.t("빈쿠션으로 4~5쿠션. 끝까지 굴러가게 둔다", HOT, 30)

    p.gap(20)
    p.h("무엇을 바꾸나 — 세기 하나뿐", HOT, 36)
    p.grid([280, 220, 320, 340],
           ["", "샷", "어느 정도", "파일"],
           [["약", "5샷", "3쿠션에서 선다", "C_세기.mp4"],
            ["중", "5샷", "평소 파이브앤하프", "C_세기.mp4"],
            ["강", "5샷", "5쿠션 이상 산다", "C_세기.mp4"]],
           sz=30)

    p.h("고정할 것", RED, 34)
    p.t("당점     평소 치시는 그 자리 (3시 · 9시 약간 위) 그대로", INK, 30)
    p.t("공       하나만. 적구가 있으면 두께가 섞인다", INK, 30)
    p.t("카메라   네 코너가 다 보이게. 중간에 옮기지 않는다", INK, 30)
    p.t("샷 사이  완전히 멈춘 뒤 손 넣기", INK, 30)

    p.rule()
    p.h("왜 이것부터인가", BLU, 34)
    p.t("앱의 강 중 약 버튼은 지금 그림만 바뀐다. 계산에 하나도 안 들어간다.", INK, 29)
    p.t("세기가 실제로 바꾸는 것 — 쿠션 반사각 · 역각 세기 · 굴러가는 거리 ·", DIM, 28)
    p.t("그래서 어느 경로가 되느냐. 이 15샷이 그 셋을 한꺼번에 채운다.", DIM, 28)

    p.save("촬영N2.png")


# ══════════════════════════════════════════════ 촬영N3 — 천 비교
def page3():
    p = Page("옛 천 → 새 천", "0808 385접점 · 0821 240접점")

    p.h("공은 더 잘 구른다. 다만 폭은 작다", GRN, 36)
    p.bars("구름 저항", 0.5, 0.46, full=0.7, note="-8%")
    p.bars("2 m/s 로 굴러가는 거리", 17.9, 19.4, unit=" m", full=22, note="+9%")

    p.rule()
    p.h("더 크게 변한 것은 쿠션이다", HOT, 36)
    p.bars("쿠션 반사 벌어짐 (40도)", 14.3, 15.7, unit="도", full=20, note="+10%")
    p.bars("쿠션에서 남는 몫", 0.80, 0.79, full=1.0, note="그대로", ncol=DIM)

    p.rule()
    p.h("앱과 견주면", BLU, 36)
    p.grid([420, 260, 260, 340],
           ["", "앱", "실측 0821", "어떻게 되나"],
           [["쿠션 반사표", "옛 천", "새 천", "넣었다 v543"],
            ["쿠션에서 남는 몫", "0.80", "0.79", "그대로 두면 된다"],
            ["구름 저항", "1.00", "0.46", "★ 승인 대기"]],
           sz=27)

    p.gap(6)
    p.card("★", "앱이 공을 두 배 빨리 세우고 있다", [
        ("2 m/s 로 치면  앱 8.9 m  ·  실제 19.4 m", INK, 30),
        ("맞춤오차도 확연하다 — 실측 85 · 앱 값 163 mm/s", DIM, 27),
        ("경로 길이가 바뀌면 추천이 바뀐다. 사장님 승인 사항이다", RED, 27),
    ], col=RED)

    p.t("잰 법 : 쿠션과 쿠션 사이 구간에서 쿠션 손실과 구름 저항을 같이 맞췄다.", DIM, 26)
    p.t("        접점 하나의 speed_out 은 눌린 값이라 쓰지 않았다.", DIM, 26)

    p.save("촬영N3.png")


for fn in (page1, page2, page3):
    fn()
