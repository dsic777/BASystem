"""오늘 찍을 것을 그림으로 만든다 → C:\\sc\\촬영0~5.png

    python c:\\Portfolio\\billiards\\make_shoot.py

    촬영0  순서 + 네 세트 격자 한눈에 + 공통 조건 + 파일명
    촬영1  A 당점 x 두께      45샷
    촬영2  B 역회전           20샷
    촬영3  C 세기             15샷
    촬영4  D 기준점(다른 다이) 30샷
    촬영5  아직 못 잰 것 전체 목록

★ 2026-08-11. 사용자 지시: '이렇게 구체적으로 넣어주세요. 모든 파일 공통.
  해석의 차이가 생기지 않게. 또 가능하면 그림으로.'
  → 세트마다 **칸마다 샷 수가 적힌 격자**를 그린다. 글로 풀어 쓰지 않는다.
  → 같은 격자가 촬영계획.md 에도 그대로 있다. 둘이 어긋나면 안 된다.

⚠️ 그림 **안**에 ⚠️ 와 ✓ 와 − 를 쓰지 말 것. malgun.ttf 에 없어서 □ 로 깨진다
   (7.jpg 에서 드러남). 원문자는 ⑮ 까지만 있다 — ⑯ 부터 깨진다.
   ★ ※ ▶ ① → × · 는 잘 나온다 — 확인하고 쓴 것들이다.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

PW, PH = 1400, 1980
OUT = Path(r"C:\sc")
FONT = r"C:\Windows\Fonts\malgun.ttf"
FONTB = r"C:\Windows\Fonts\malgunbd.ttf"

BG = "#12151a"
INK = "#e8ecf2"
DIM = "#9aa4b2"
HOT = "#ffd400"
RED = "#e8503a"
GRN = "#5ec07a"
BLU = "#5aa9e6"


def f(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


# ───────────────────────────────────────────── 격자 정의 (진실 원천)
# ★ 이 표가 촬영계획.md 와 그림의 **공통 원본**이다. 여기만 고친다.
SETS = {
    "A": dict(
        title="A  당점 x 두께", shots=45, file="A_12시 / A_중단 / A_6시 .mp4",
        head=["", "얇게", "반두께", "두껍게", "파일"],
        rows=[["12시 3팁", "5샷", "5샷", "5샷", "A_12시.mp4"],
              ["중단", "5샷", "5샷", "5샷", "A_중단.mp4"],
              ["6시 3팁", "5샷", "5샷", "5샷", "A_6시.mp4"]],
        w=[260, 175, 175, 175, 335],
    ),
    "B": dict(
        title="B  역회전", shots=20, file="B_역회전.mp4",
        head=["", "얕게", "중간", "깊게", "파일"],
        rows=[["9시30분 3팁", "7샷", "7샷", "6샷", "B_역회전.mp4"]],
        w=[260, 175, 175, 175, 335],
    ),
    "C": dict(
        title="C  세기", shots=15, file="C_세기.mp4",
        head=["", "약", "중", "강", "파일"],
        rows=[["중단 · 반두께", "5샷", "5샷", "5샷", "C_세기.mp4"]],
        w=[260, 175, 175, 175, 335],
    ),
    "D": dict(
        title="D  기준점 — 다른(좋은) 다이", shots=30, file="D_기준점.mp4",
        head=["", "1쿠션 10", "1쿠션 20", "1쿠션 30", "1쿠션 40", "1쿠션 50"],
        rows=[["수구 50", "3샷", "3샷", "3샷", "3샷", "·"],
              ["수구 40", "·", "3샷", "3샷", "·", "·"],
              ["수구 60", "·", "·", "3샷", "3샷", "·"],
              ["수구 70", "·", "·", "·", "3샷", "3샷"]],
        w=[220, 210, 210, 210, 210, 210],
    ),
}


class Page:
    def __init__(self, title, sub=""):
        self.im = Image.new("RGB", (PW, PH), BG)
        self.d = ImageDraw.Draw(self.im)
        self.d.rectangle([0, 0, PW, 150], fill="#1d232c")
        self.d.line([0, 150, PW, 150], fill=HOT, width=5)
        self.d.text((60, 48), title, font=f(58, True), fill=HOT)
        if sub:
            self.d.text((PW - 60, 66), sub, font=f(30), fill=DIM, anchor="ra")
        self.y = 200

    def gap(self, n=28):
        self.y += n

    def h(self, txt, col=INK):
        self.gap(18)
        self.d.text((60, self.y), txt, font=f(40, True), fill=col)
        self.y += 62

    def t(self, txt, col=INK, sz=32, x=60, bold=False):
        self.d.text((x, self.y), txt, font=f(sz, bold), fill=col)
        self.y += sz + 14

    def rule(self):
        self.gap(10)
        self.d.line([60, self.y, PW - 60, self.y], fill="#2c333d", width=3)
        self.gap(18)

    def box(self, lines, col=HOT, fill="#1a2029", sz=32):
        h = len(lines) * (sz + 14) + 40
        self.d.rounded_rectangle([56, self.y - 10, PW - 56, self.y + h - 10],
                                 radius=16, fill=fill, outline=col, width=3)
        self.y += 12
        for ln in lines:
            self.d.text((84, self.y), ln, font=f(sz), fill=INK)
            self.y += sz + 14
        self.y += 28

    def grid(self, spec, sz=32, rh=None):
        """칸마다 샷 수가 적힌 표. 해석의 여지를 없애는 것이 목적이다."""
        w, head, rows = spec["w"], spec["head"], spec["rows"]
        rh = rh or sz + 34
        x0 = (PW - sum(w)) // 2
        y0 = self.y
        xs = [x0]
        for c in w:
            xs.append(xs[-1] + c)
        n = len(rows) + 1
        # 머리줄
        self.d.rectangle([x0, y0, xs[-1], y0 + rh], fill="#242c37")
        for j, txt in enumerate(head):
            if txt:
                self.d.text(((xs[j] + xs[j + 1]) / 2, y0 + rh / 2), txt,
                            font=f(sz - 2, True), fill=HOT, anchor="mm")
        # 몸통
        for i, row in enumerate(rows):
            yy = y0 + rh * (i + 1)
            if i % 2:
                self.d.rectangle([x0, yy, xs[-1], yy + rh], fill="#171d25")
            for j, txt in enumerate(row):
                col = INK if j else HOT
                fnt = f(sz - (6 if j == len(row) - 1 and txt.endswith(".mp4") else 0),
                        j == 0)
                if txt == "·":
                    col = "#4a535f"
                if j == len(row) - 1 and txt.endswith(".mp4"):
                    col = GRN
                self.d.text(((xs[j] + xs[j + 1]) / 2, yy + rh / 2), txt,
                            font=fnt, fill=col, anchor="mm")
        # 줄
        for i in range(n + 1):
            yy = y0 + rh * i
            self.d.line([x0, yy, xs[-1], yy], fill="#3a4450", width=2)
        for x in xs:
            self.d.line([x, y0, x, y0 + rh * n], fill="#3a4450", width=2)
        self.d.rectangle([x0, y0, xs[-1], y0 + rh * n], outline=HOT, width=3)
        self.y = y0 + rh * n + 30

    def save(self, name):
        OUT.mkdir(parents=True, exist_ok=True)
        self.im.save(OUT / name)
        print(OUT / name)


# ───────────────────────────────────────────── 작은 당구대 그림
class Mini:
    W, H = 2448.0, 1224.0

    def __init__(self, page, x0, y0, w):
        self.d = page.d
        self.k = w / self.W
        self.x0, self.y0 = x0, y0
        rail = 80 * self.k
        a, b = self.p(0, self.H), self.p(self.W, 0)
        self.d.rounded_rectangle([a[0] - rail, a[1] - rail, b[0] + rail, b[1] + rail],
                                 radius=rail * 0.5, fill="#2b2f36")
        self.d.rectangle([a, b], fill="#2f3640", outline="#8a93a0", width=2)
        for i in range(9):
            for yy in (0, self.H):
                q = self.p(self.W * i / 8, yy)
                o = rail * 0.55 * (1 if yy == 0 else -1)
                self.d.ellipse([q[0] - 4, q[1] + o - 4, q[0] + 4, q[1] + o + 4], fill="#e8eaee")
        for i in range(5):
            for xx in (0, self.W):
                q = self.p(xx, self.H * i / 4)
                o = rail * 0.55 * (1 if xx == 0 else -1)
                self.d.ellipse([q[0] - o - 4, q[1] - 4, q[0] - o + 4, q[1] + 4], fill="#e8eaee")
        self.bottom = self.p(0, 0)[1] + rail

    def p(self, x, y):
        return (self.x0 + x * self.k, self.y0 + (self.H - y) * self.k)

    def ball(self, x, y, col, r=30.75, txt=None, tcol=HOT):
        a, b = self.p(x - r, y + r), self.p(x + r, y - r)
        self.d.ellipse([a, b], fill=col, outline="#14161a", width=3)
        if txt:
            self.d.text(((a[0] + b[0]) / 2, a[1] - 12), txt, font=f(24, True),
                        fill=tcol, anchor="ms")

    def line(self, pts, col, w=4, dash=False):
        for i in range(len(pts) - 1):
            p, q = self.p(*pts[i]), self.p(*pts[i + 1])
            if not dash:
                self.d.line([p, q], fill=col, width=w)
                continue
            n = max(2, int(((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5 / 22))
            for k in range(0, n, 2):
                u, v = k / n, min(1, (k + 1) / n)
                self.d.line([(p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u),
                             (p[0] + (q[0] - p[0]) * v, p[1] + (q[1] - p[1]) * v)],
                            fill=col, width=w)

    def label(self, x, y, txt, col=INK, sz=26, anchor="mm"):
        self.d.text(self.p(x, y), txt, font=f(sz, True), fill=col, anchor=anchor)


# ══════════════════════════════════════════════ 촬영0
def page0():
    p = Page("오늘 촬영 — 한 장 요약", "2026-08-11 · 110샷")
    p.t("칸에 적힌 수가 그 칸에서 칠 샷 수다. 빈칸(·)은 안 친다.", DIM, 30)
    p.t("시간이 모자라면 D → C → B 순서로 버린다. A 는 끝까지.", DIM, 30)
    for k in ("A", "B", "C", "D"):
        s = SETS[k]
        p.gap(24)
        p.d.text((60, p.y), f'{s["title"]}    {s["shots"]}샷', font=f(34, True), fill=HOT)
        p.y += 52
        p.grid(s, sz=28)

    p.rule()
    p.h("공통 조건 다섯", HOT)
    p.t("① 수구가 1적구까지 1미터 이상 굴러오게  (A 세트)", INK, 31)
    p.t("② 두 공 다 화면 안에. 카메라는 지금 자리 그대로", INK, 31)
    p.t("③ 공이 완전히 멈춘 뒤에 손 넣기. 샷 사이 1초 여유", INK, 31)
    p.t("④ 두께·각도·숫자는 눈대중이면 충분. 실제 값은 영상에서 계산한다", INK, 31)
    p.t("⑤ 1적구가 쿠션에 닿아도 괜찮다. 쿠션 전 구간만 쓴다", INK, 31)
    p.save("촬영0.png")


# ══════════════════════════════════════════════ 촬영1 — A
def page1():
    s = SETS["A"]
    p = Page(s["title"], f'{s["shots"]}샷')
    p.box(["※ 공은 두 개만 놓는다",
           "   3번째 공이 있으면 1적구가 거기 부딪혀 속도가 섞인다"],
          col=RED, fill="#2a1c1c")
    p.grid(s)
    p.t("좌우 회전은 0 (12시·6시를 정확히) · 세기는 '중' 하나로 고정", HOT, 32)
    p.t("파일은 당점별로 갈라 주세요. 파일 안에서 두께가 섞이는 건 괜찮습니다.", DIM, 29)

    m = Mini(p, 300, p.y + 20, 800)
    m.ball(2100, 300, "#f2f4f8", txt="수구")
    m.ball(900, 620, "#e0392b", txt="1적구")
    m.line([(2100, 300), (900, 620)], BLU, 4, dash=True)
    m.label(1500, 170, "1미터 이상", HOT, 26)
    p.y = m.bottom + 40

    p.h("두께 잡는 법", HOT)
    p.t("반두께를 큐선으로 잡고, 거기서 확실히 얇게 · 확실히 두껍게.", INK, 32)
    p.t("정확히 맞추려 하지 마세요. 세 무리로 갈라지기만 하면 됩니다.", DIM, 29)
    p.t("6시 3팁 + 두껍게처럼 잘 안 되는 칸은 3샷만 하고 넘어가세요.", DIM, 29)
    p.t("칸을 통째로 비우는 것만 피하면 됩니다.", DIM, 29)

    p.rule()
    p.h("여기서 나오는 것", GRN)
    p.t("① 상하 당점이 분리각을 얼마나 바꾸나  (두께마다 다르다)", INK, 31)
    p.t("② 충돌 직후 수구·1적구 속도  (지금 전혀 없다)", INK, 31)
    p.save("촬영1.png")


# ══════════════════════════════════════════════ 촬영2 — B
def page2():
    s = SETS["B"]
    p = Page(s["title"], f'{s["shots"]}샷')
    p.box(["빈쿠션 · 공 하나 · 9시30분 3팁 (좌회전)"])
    p.grid(s)
    p.t("얕게 = 입사 10도쯤 · 중간 = 20도쯤 · 깊게 = 30도쯤", HOT, 32)
    p.t("각도는 눈대중. 세 무리로 흩어지기만 하면 됩니다.", DIM, 29)

    m = Mini(p, 300, p.y + 20, 800)
    m.ball(2280, 950, "#f2f4f8", txt="수구")
    m.line([(2280, 950), (300, 0), (0, 120), (700, 1224)], GRN, 4)
    p.y = m.bottom + 40

    p.h("왜 필요한가", HOT)
    p.t("지금 있는 역회전 자료는 7샷 · 20접점뿐입니다.", INK, 32)
    p.t("그래서 33.jpg 처럼 2쿠션값이 큰 배치에서 '—' 가 뜹니다.", INK, 32)
    p.t("순회전은 130샷 385접점이라 충분한데 역회전만 비어 있습니다.", DIM, 29)

    p.rule()
    p.h("찍는 법", HOT)
    p.t("수구를 우측 단쿠션 근처에 놓고 좌측으로 보냅니다.", INK, 32)
    p.t("공이 멈출 때까지 찍습니다.", INK, 32)
    p.save("촬영2.png")


# ══════════════════════════════════════════════ 촬영3 — C
def page3():
    s = SETS["C"]
    p = Page(s["title"], f'{s["shots"]}샷')
    p.box(["공 두 개 · 중단 당점 · 반두께로 고정하고 세기만 바꾼다"])
    p.grid(s)
    p.t("두께와 당점을 고정해야 세기 축만 남습니다.", DIM, 29)

    p.rule()
    p.h("무엇에 쓰나", HOT)
    p.t("앱의 세기 버튼(약·중·강)에 실제 숫자를 붙입니다.", INK, 32)
    p.t("세기에 따라 궤적을 어디까지 그릴지가 갈립니다.", INK, 32)
    p.gap(16)
    p.t("어제 15개 충돌에서 '두께별 이동거리' 는 나왔습니다.", DIM, 29)
    p.t("세기 축이 아직 비어 있습니다.", DIM, 29)

    p.rule()
    p.h("여유가 없으면", DIM)
    p.t("D 다음으로 버리세요. A · B 가 우선입니다.", INK, 32)
    p.save("촬영3.png")


# ══════════════════════════════════════════════ 촬영4 — D
def page4():
    s = SETS["D"]
    p = Page(s["title"], f'{s["shots"]}샷')
    p.box(["빈쿠션 · 공 하나 · 파일 D_기준점.mp4",
           "3쿠션 도착점이 화면에 보이게"])
    p.grid(s, sz=30)
    p.t("숫자를 정확히 맞추려 애쓰지 마세요. 실제로 어디서 어디로 쳤는지는", DIM, 29)
    p.t("영상에서 읽습니다. 그 언저리로 골고루 흩어지기만 하면 됩니다.", DIM, 29)

    p.rule()
    p.h("왜 필요한가", HOT)
    p.t("말씀하신 대로 지금 다이는 각이 짧게 떨어집니다.", INK, 32)
    p.t("계산으로도 확인됐습니다 — 우리 실측표로 굴리면 시스템", INK, 32)
    p.t("기대값보다 0.6 ~ 7.0 포인트 짧게 옵니다. (아주 얕은 각 하나는 반대)", INK, 32)

    p.gap(14)
    p.h("한 샷으로 전체를 보정할 수 있나 → 안 됩니다", RED)
    p.t("각 배치를 기대값에 맞추는 데 필요한 보정을 뽑아 보면", INK, 31)
    p.t("   수구 30 · 1쿠션 10  ...  10.9도  (반대쪽으로)", DIM, 29)
    p.t("   수구 50 · 1쿠션 30  ...   9.6도", DIM, 29)
    p.t("   수구 50 · 1쿠션 10  ...  13.7도", DIM, 29)
    p.t("보정은 '모든 쿠션에 같은 각도를 더하는' 손잡이 하나입니다.", INK, 31)
    p.t("틀어짐이 각도마다 다르고 부호까지 바뀌니 한 숫자로 못 덮습니다.", INK, 31)
    p.save("촬영4.png")


# ══════════════════════════════════════════════ 촬영5
def page5():
    p = Page("아직 못 잰 것 · 모르는 것", "전체")

    p.h("영상으로 풀리는 것", GRN)
    p.t("①  충돌 후 속도            오늘 A     키스 판정의 마지막 조각", INK, 30)
    p.t("②  상하 당점 → 분리각      오늘 A     표는 있으나 실측이 아니다", INK, 30)
    p.t("③  역회전 반사             오늘 B     7샷뿐", INK, 30)
    p.t("④  세기 → 이동거리         오늘 C", INK, 30)
    p.t("⑤  다이별 보정             오늘 D", INK, 30)
    p.t("⑥  쿠션 사이 휨            0808 재분석", INK, 30)
    p.t("      접점만 남기고 프레임 궤적을 버려서 다시 돌려야 한다.", DIM, 26)
    p.t("      공 반 개를 가르는 부분이라고 하셨던 그것.", DIM, 26)
    p.t("⑦  천 마찰 · 쿠션 손실 분리   ⑥과 같이", INK, 30)

    p.rule()
    p.h("사용자가 값을 줘야 하는 것", HOT)
    p.t("①  리버스 시스템 번호표      유튜브 캡처 주시기로 한 것", INK, 30)
    p.t("②  대회전 번호표", INK, 30)
    p.t("      1·3쿠션이 단쿠션이라 지금 눈금 자체가 없다.", DIM, 26)
    p.t("③  2뱅크 2쿠션값 2 미만 · 4 초과를 쓰는지", INK, 30)
    p.t("④  2뱅크 출발값 4 초과 (수구가 코너 너머일 때)", INK, 30)
    p.t("⑤  2뱅크로 못 푸는 배치 (적용 조건)", INK, 30)
    p.t("⑥  하쿠 / 하꼬 가 같은 말인지", INK, 30)

    p.rule()
    p.h("프로그램", BLU)
    p.t("①  경로 추천 — 360도 훑기 + 묶기        ★ 승인 대기", INK, 30)
    p.t("②  6칸 리스트 UI (5개 + 직접조준)", INK, 30)
    p.t("③  키스 판정", INK, 30)
    p.t("④  시뮬레이션 (8번 버튼)   영상①이 있어야 시간이 맞는다", INK, 30)
    p.save("촬영5.png")


for fn in (page0, page1, page2, page3, page4, page5):
    fn()
