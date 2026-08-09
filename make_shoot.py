"""내일 촬영할 것을 순위별 그림으로 만든다 → C:\\sc\\촬영1~4.png

    python c:\\Portfolio\\billiards\\make_shoot.py

⚠️ 이 그림은 **촬영 안내용**이다. 경로가 정확한 계산 결과는 아니다 —
   '이런 식으로 치면 된다' 를 보여주는 것이 목적이라 궤적이 겹쳐도 상관없다
   (사용자 지시: '대충 궤적이 겹쳐도 됩니다').
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 2448, 1224                       # 쿠션 안쪽 (mm)
BALL = 61.5
OUT = Path(r"C:\sc")
FONT = r"C:\Windows\Fonts\malgun.ttf"


def f(sz):
    return ImageFont.truetype(FONT, sz)


class Table:
    """mm → 픽셀. 레일 여백을 두고 그린다."""

    def __init__(self, im, x0, y0, w):
        self.d = ImageDraw.Draw(im)
        self.k = w / W
        self.x0, self.y0 = x0, y0

    def p(self, x, y):
        return (self.x0 + x * self.k, self.y0 + (H - y) * self.k)

    def frame(self):
        rail = 90 * self.k
        a, b = self.p(0, H), self.p(W, 0)
        self.d.rounded_rectangle([a[0] - rail, a[1] - rail, b[0] + rail, b[1] + rail],
                                 radius=rail * 0.5, fill="#2b2f36")
        self.d.rectangle([a, b], fill="#2f3640", outline="#8a93a0", width=2)
        for i in range(9):                       # 다이아몬드
            for yy in (0, H):
                q = self.p(W * i / 8, yy)
                o = rail * 0.55 * (1 if yy == 0 else -1)
                self.d.ellipse([q[0] - 5, q[1] + o - 5, q[0] + 5, q[1] + o + 5], fill="#e8eaee")
        for i in range(5):
            for xx in (0, W):
                q = self.p(xx, H * i / 4)
                o = rail * 0.55 * (1 if xx == 0 else -1)
                self.d.ellipse([q[0] - o - 5, q[1] - 5, q[0] - o + 5, q[1] + 5], fill="#e8eaee")

    def ball(self, x, y, col, r=BALL / 2, txt=None, tf=None):
        a, b = self.p(x - r, y + r), self.p(x + r, y - r)
        self.d.ellipse([a, b], fill=col, outline="#14161a", width=3)
        if txt:
            self.d.text((a[0] + (b[0] - a[0]) / 2, a[1] - 26), txt, font=tf,
                        fill="#ffe98a", anchor="ms")

    def line(self, pts, col, w=4, dash=False):
        for i in range(len(pts) - 1):
            p, q = self.p(*pts[i]), self.p(*pts[i + 1])
            if not dash:
                self.d.line([p, q], fill=col, width=w)
                continue
            n = max(2, int(math.dist(p, q) / 26))
            for k in range(n):
                if k % 2:
                    continue
                u, v = k / n, min(1, (k + 1) / n)
                self.d.line([(p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u),
                             (p[0] + (q[0] - p[0]) * v, p[1] + (q[1] - p[1]) * v)],
                            fill=col, width=w)


def bank(start, ang, n):
    """빈쿠션 경로를 거울반사로 대충 굴린다 (그림용)."""
    x, y = start
    dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    pts = [(x, y)]
    for _ in range(n):
        ts = []
        if dx > 0: ts.append(((W - x) / dx, "v"))
        if dx < 0: ts.append((-x / dx, "v"))
        if dy > 0: ts.append(((H - y) / dy, "h"))
        if dy < 0: ts.append((-y / dy, "h"))
        t, kind = min(ts)
        x, y = x + dx * t, y + dy * t
        pts.append((x, y))
        if kind == "v": dx = -dx
        else: dy = -dy
    return pts


def page(title, sub):
    im = Image.new("RGB", (2000, 1180), "#16181c")
    d = ImageDraw.Draw(im)
    d.text((60, 46), title, font=f(58), fill="#ffd54a")
    d.text((60, 122), sub, font=f(30), fill="#9aa2b2")
    return im, d


# ────────────────────────────────────────────── 1순위
im, d = page("1순위 · 충돌 후 속도  (두 공)",
             "공 두 개만. 두께를 1/8 → 7/8 까지 훑는다. 두께당 5~10샷, 같은 두께에서 약·중·강.  전부 50~70샷")
t = Table(im, 150, 260, 1000)
t.frame()
t.ball(1224, 612, "#d6342c", txt="1적구 (고정)", tf=f(26))
t.ball(500, 612, "#f6f5ee", txt="수구", tf=f(26))
for k, (lab, th) in enumerate([("1/8", .125), ("4/8", .5), ("7/8", .875)]):
    off = (1 - th) * BALL * (1 if k != 1 else 1)
    t.line([(500, 612), (2300, 612 + off * (2300 - 500) / (1224 - 500))],
           ["#7fd8ff", "#ffd600", "#ff78be"][k], 3)
d.text((150, 940), "수구는 한 자리에 두고  겨냥만  얇게 ↔ 두껍게 바꾼다", font=f(30), fill="#e8eaee")
d.text((150, 985), "두께는 따로 안 적어도 된다 — 궤적에서 계산된다", font=f(30), fill="#e8eaee")

# 두께 그림 (오른쪽)
cx, cy, R = 1560, 560, 150
d.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#d6342c", outline="#14161a", width=4)
d.text((cx, cy - R - 40), "1적구", font=f(30), fill="#ffb0aa", anchor="ms")
for lab, th, col in [("1/8  얇게", .125, "#7fd8ff"), ("4/8  반두께", .5, "#ffd600"),
                     ("7/8  두껍게", .875, "#ff78be")]:
    ox = (1 - th) * 2 * R
    d.ellipse([cx - ox - R, cy - R, cx - ox + R, cy + R], outline=col, width=6)
    d.text((cx - ox, cy + R + 46 + list([.125, .5, .875]).index(th) * 46), lab,
           font=f(30), fill=col, anchor="ms")
d.text((1300, 940), "겹치는 정도가 두께다", font=f(30), fill="#9aa2b2")
im.save(OUT / "촬영1.png")

# ────────────────────────────────────────────── 2순위
im, d = page("2순위 · 다이 보정  (공 하나)",
             "길게 도는 빈쿠션 20~30샷. 4쿠션 이상 가게. '4쿠션 후 좌측으로 휜다' 를 재는 것")
t = Table(im, 150, 260, 1700)
t.frame()
for st, ang, col in [((300, 200), 38, "#ffd600"), ((300, 900), -34, "#7fd8ff"),
                     ((2100, 300), 140, "#6eeb5a")]:
    t.line(bank(st, ang, 5), col, 4)
    t.ball(*st, "#f6f5ee")
d.text((150, 1060), "⚠️ 이번엔 프레임 단위 궤적을 저장한다 — 0808 때는 접점만 남겨 휨을 못 쟀다",
       font=f(30), fill="#ff9f9a")
im.save(OUT / "촬영2.png")

# ────────────────────────────────────────────── 3순위
im, d = page("3순위 · 상하 당점이 쿠션 반사를 바꾸는가  (공 하나)",
             "같은 자리에서 당점만 12시 / 중단 / 6시로 바꿔 각 5샷.  좌우 회전은 0")
t = Table(im, 150, 280, 1150)
t.frame()
t.line(bank((400, 250), 40, 4), "#e8eaee", 5)
t.ball(400, 250, "#f6f5ee")
d.text((160, 1010), "가정이 맞으면 셋이  같은 각  으로 나온다", font=f(30), fill="#e8eaee")
d.text((160, 1055), "다르면 지금 코드가 틀린 것이다 (상하는 분리각만 바꾼다고 가정 중)",
       font=f(30), fill="#ff9f9a")
for i, (lab, dy, col) in enumerate([("12시 3팁", -1, "#7fd8ff"), ("중단", 0, "#ffd600"),
                                    ("6시 3팁", 1, "#ff78be")]):
    cx, cy, R = 1560, 430 + i * 250, 92
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#f2f1ea", outline="#3c3e46", width=4)
    d.ellipse([cx - R * .78, cy - R * .78, cx + R * .78, cy + R * .78], outline="#be2820", width=3)
    py = cy + dy * R * .585
    d.ellipse([cx - 17, py - 17, cx + 17, py + 17], fill="#de342c")
    d.text((cx + R + 34, cy), lab, font=f(34), fill=col, anchor="lm")
im.save(OUT / "촬영3.png")

# ────────────────────────────────────────────── 4순위
im, d = page("4순위 · 시간 남으면", "역회전 20샷 · 세기별 15샷 · 대회전 10샷")
for i, (lab, why, col) in enumerate([
        ("역회전 빈쿠션 20샷", "실측표는 순회전만. 되돌아오기·리버스가 여기 걸려 있다", "#7fd8ff"),
        ("같은 자리 세기별 15샷", "속도가 분리각을 바꾼다는데 숫자가 없다 (약·중·강 5샷씩)", "#ffd600"),
        ("대회전 10샷", "내 힘으로 몇 쿠션까지 가는지", "#ff78be")]):
    x0 = 110 + i * 620
    t = Table(im, x0, 300, 540)
    t.frame()
    if i == 0:
        t.line(bank((300, 300), 30, 3), col, 4)
        t.line([(300, 300), (1100, 760), (700, 1100)], "#ff78be", 4, dash=True)
    elif i == 1:
        for n, a in [(2, 34), (3, 34), (5, 34)]:
            t.line(bank((300, 250), a, n), col, 3)
    else:
        t.line(bank((250, 200), 33, 7), col, 4)
    t.ball(300 if i < 2 else 250, 300 if i == 0 else (250 if i == 1 else 200), "#f6f5ee")
    d.text((x0, 830), lab, font=f(38), fill=col)
    d.text((x0, 890), why, font=f(24), fill="#9aa2b2")
im.save(OUT / "촬영4.png")

print("만들었습니다:")
for n in range(1, 5):
    print("  ", OUT / f"촬영{n}.png")
