"""오늘 촬영할 것을 그림으로 만든다 → C:\\sc\\촬영0~4.png

    python c:\\Portfolio\\billiards\\make_shoot.py

    촬영0  한 장 요약 (공통 · 오전에 채워진 것 / 빈 것 · 파일명)
    촬영1~4  순위별

★ 2026-08-11 오후판. 오전 촬영본을 분석해 **실제로 빈 칸**만 남겼다.
  1순위 상하 당점 15샷 · 2순위 역회전 20샷 · 3순위 충돌 양끝 10샷 · 4순위 여유

⚠️ 이 그림은 **촬영 안내용**이다. 경로가 정확한 계산 결과는 아니다 —
   '이런 식으로 치면 된다' 를 보여주는 것이 목적이라 궤적이 겹쳐도 상관없다
   (사용자 지시: '대충 궤적이 겹쳐도 됩니다').

⚠️ 그림 **안에** ⚠️ 와 ✓ 를 쓰지 말 것. malgun.ttf 에 없어서 □ 로 깨진다
   (7.jpg 에서 드러남. ⚠️ 는 U+26A0 + 변형선택자라 □ 가 두 개 나온다).
   ★ ※ ▶ ① → × · 는 잘 나온다 — 확인하고 쓴 것들이다.
"""
import math
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import bounce, five_half as fh          # noqa: E402
from core.table import Table as CoreTable         # noqa: E402

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


# ── 파이브앤하프 숫자로 실제 경로를 뽑는다 (2순위용) ────────────────────
# ⚠️ 아래 bank() 는 **거울반사**라 실제와 다르다 (사용자 지적: '그림처럼은 안 갈 텐데').
#    2순위는 data/measured_bounce.json 실측표로 굴린다 — 0808.mp4 130샷 385접점.
_T = CoreTable.load()
_S = fh.load_scales()
_BALL_R = _T.ball_diameter / 2


def five_half_shot(cue_number, first_number, cushions=6, flip=False):
    """수구수·1쿠션수 → (수구 자리, 쿠션 접점들, 1쿠션 입사각).

    수구 자리는 **되읽었을 때 그 수구수가 정확히 나오는 자리**를 찾아 쓴다.
    그래야 그림의 숫자와 실제로 놓을 자리가 어긋나지 않는다.

    flip  ★ 사용자 2026-08-10: '방향을 반대로 돌립시다 모두.'
          카메라가 좌측하단 위에 있어서, 수구가 아래쪽이면 치는 사람 몸이
          카메라와 다이 사이에 들어온다 (깊게가 제일 아래였다).
          상하로 뒤집으면 수구가 위로 가고 1쿠션이 하단 장쿠션이 된다.
          파이브앤하프 눈금은 조준 방향에 따라 접히므로 **숫자는 그대로**다.
    """
    aim = _S["first_cushion"].point_for_number(_T, first_number)
    lo, hi = _BALL_R, _T.height - _BALL_R
    for _ in range(60):                       # 우측 단쿠션을 따라 이분법으로 찾는다
        mid = (lo + hi) / 2
        rd = fh.read_cue_number(_T, _S["start"], (_T.width - _BALL_R, mid), aim)
        if rd is None:
            return None
        if rd.number < cue_number:
            lo = mid
        else:
            hi = mid
    cue = (_T.width - _BALL_R, (lo + hi) / 2)
    hits = bounce.path_from_aim(_T.width, _T.height, cue, aim, cushions=cushions)
    pts = [h.point for h in hits]
    if flip:
        cue = (cue[0], _T.height - cue[1])
        pts = [(x, _T.height - y) for x, y in pts]
    return cue, pts, hits[0].incoming


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



def tipboard(d, cx, cy, R, dy, label, col, side=0.0):
    """당점판 하나. dy = 위아래 (-1 12시 3팁 · 0 중단 · +1 6시 3팁), side = 좌우."""
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#f2f1ea", outline="#3c3e46", width=4)
    d.ellipse([cx - R * .78, cy - R * .78, cx + R * .78, cy + R * .78], outline="#be2820", width=3)
    px, py = cx + side * R * .585, cy + dy * R * .585
    d.ellipse([px - R * .17, py - R * .17, px + R * .17, py + R * .17], fill="#de342c")
    d.text((cx, cy + R + 40), label, font=f(32), fill=col, anchor="ms")


# ────────────────────────────────────────────── 0 · 한 장 요약
im, d = page("오늘 오후 촬영  ·  2026-08-11",
             "오전 촬영본을 분석해서 실제로 빈 칸만 남겼다.  다 합쳐 20분 안쪽")

d.rounded_rectangle([60, 186, 980, 556], radius=18, fill="#1e2128", outline="#3a3f49", width=2)
d.text((92, 208), "공통 — 오전과 똑같이", font=f(34), fill="#ffd54a")
for i, t in enumerate([
        "카메라 그대로.  다이가 몸에 가려도 상관없다",
        "★ 공을 잡지 않는다 — 완전히 멈출 때까지",
        "한 샷이 멈춘 뒤 다음 샷",
        "★ 파일명에 당점을 정확히 (오전엔 두 번 다 틀렸다)",
        "편집 방식은 오전 그대로. 바꿀 것 없다"]):
    col = "#ffe98a" if t.startswith("★") else "#e8eaee"
    d.text((100, 272 + i * 50), "·", font=f(30), fill="#7f8898")
    d.text((126, 270 + i * 50), t, font=f(29), fill=col)

d.rounded_rectangle([1010, 186, 1940, 556], radius=18, fill="#1e2128", outline="#3a3f49", width=2)
d.text((1042, 208), "오전에 채워진 것", font=f(34), fill="#6eeb5a")
for i, t in enumerate([
        ("충돌 (두 공)", "15개 · 두께 4~68%", "#6eeb5a"),
        ("세기별 빈쿠션", "32샷 · 2~5쿠션", "#6eeb5a"),
        ("역회전", "7샷 20접점 — 얇다", "#ffd54a"),
        ("상하 당점", "0샷 — 통째로 비었다", "#ff9f9a")]):
    d.text((1042, 272 + i * 62), t[0], font=f(30), fill=t[2])
    d.text((1330, 274 + i * 62), t[1], font=f(27), fill="#c8ccd4")
d.text((1042, 526), "수구수 판독은 26샷 전부 50.0 으로 나왔다 — 편집이 좋았다는 뜻",
       font=f(24), fill="#9aa2b2")

y = 620
d.text((60, y - 44), "오늘 찍을 것", font=f(36), fill="#ffd54a")
for x, lab in [(60, "순위"), (230, "무엇을"), (830, "샷"), (960, "당점"), (1400, "왜")]:
    d.text((x, y), lab, font=f(27), fill="#7f8898")
d.line([60, y + 40, 1940, y + 40], fill="#3a3f49", width=2)
rows = [("1", "상하 당점 (공 하나)", "15", "12시3팁 / 중단 / 6시3팁", "가정을 아직 안 재봤다", "#ffd54a"),
        ("2", "역회전 빈쿠션 (공 하나)", "20", "9시30분 3팁", "서서 들어가는 각이 13도 차이", "#7fd8ff"),
        ("3", "충돌 양끝 (두 공)", "10", "12시 2팁", "6/8·7/8 칸이 비었다", "#ff78be"),
        ("4", "여유 (시간 남으면)", "15", "9시30분 3팁", "세게 · 아주 얕게", "#9aa2b2")]
for i, (n, what, shots, tip, why, col) in enumerate(rows):
    yy = y + 64 + i * 66
    d.text((72, yy), n, font=f(40), fill=col)
    d.text((230, yy + 6), what, font=f(31), fill="#e8eaee")
    d.text((840, yy + 6), shots, font=f(29), fill="#c8ccd4")
    d.text((960, yy + 8), tip, font=f(27), fill="#c8ccd4")
    d.text((1400, yy + 8), why, font=f(26), fill="#9aa2b2")

d.rounded_rectangle([60, 950, 1940, 1128], radius=16, fill="#2a2418", outline="#a3822c", width=2)
d.text((92, 968), "★ 1순위는 파일을 당점별로 나눠 주세요 — 영상만 봐서는 당점을 알 수 없습니다",
       font=f(32), fill="#ffe98a")
for i, t in enumerate(["상하당점_12시3팁.mp4    상하당점_중단.mp4    상하당점_6시3팁.mp4",
                       "역회전_9시30분3팁.mp4    충돌추가_12시2팁.mp4"]):
    d.text((110, 1018 + i * 42), t, font=f(28), fill="#7fd8ff")
d.text((110, 1096), "※ 파일명의 당점이 곧 데이터 조건이다. 조건이 다른 표는 절대 섞을 수 없다.",
       font=f(25), fill="#c8ccd4")
im.save(OUT / "촬영0.png")

# ────────────────────────────────────────────── 1순위 · 상하 당점
im, d = page("1순위 · 상하 당점이 쿠션 반사를 바꾸는가  (공 하나)",
             "같은 자리에서 당점만 12시 3팁 / 중단 / 6시 3팁 으로.  각 5샷.   ★ 좌우 회전은 0")
_cue, _pts, _inc = five_half_shot(50, 30, cushions=5)
t = Table(im, 110, 240, 820)
t.frame()
t.line([_cue] + _pts, "#e8eaee", 5)
t.ball(*_cue, "#f6f5ee")
d.text((110, 712), "수구 50  →  1쿠션 30", font=f(38), fill="#ffd54a")
d.text((110, 766), "오전 2순위와 같은 자리다. 그대로 두고 당점만 바꾸면 된다", font=f(27), fill="#9aa2b2")

for i, (lab, dy, col) in enumerate([("12시 3팁", -1, "#7fd8ff"), ("중단", 0, "#ffd600"),
                                    ("6시 3팁", 1, "#ff78be")]):
    tipboard(d, 1320 + i * 210, 400, 92, dy, lab, col)

d.rounded_rectangle([1180, 560, 1940, 700], radius=16, fill="#2a1f22", outline="#a34a44", width=2)
d.text((1210, 580), "★ 좌우 회전은 0 이어야 한다", font=f(34), fill="#ffb0aa")
d.text((1210, 626), "3팁이 좌우로 조금이라도 들어가면 이 실험은 무효다.", font=f(25), fill="#e0b8b4")
d.text((1210, 660), "오전에 찍은 것이 그래서 못 쓰게 됐다 (역회전이 걸려 있었다).",
       font=f(25), fill="#e0b8b4")

d.text((110, 830), "무엇을 재나 — 셋이 같은 각으로 나오는가", font=f(34), fill="#e8eaee")
d.text((110, 886), "지금 프로그램은 '상하 당점은 분리각만, 좌우 회전은 쿠션 반사만 바꾼다' 고",
       font=f(28), fill="#9aa2b2")
d.text((110, 928), "가정하고 있다. 사용자가 그렇게 말해 주었지만 한 번도 재본 적이 없다.",
       font=f(28), fill="#9aa2b2")
d.text((110, 984), "셋이 같은 각이면  →  가정이 맞다. 그대로 간다", font=f(30), fill="#6eeb5a")
d.text((110, 1030), "다르면  →  지금 코드가 틀린 것이다. 상하 당점도 반사에 넣어야 한다",
       font=f(30), fill="#ff9f9a")
d.text((110, 1090), "※ 같은 자리·같은 세기로. 당점 말고는 아무것도 바꾸지 않는다",
       font=f(28), fill="#e8eaee")
im.save(OUT / "촬영1.png")

# ────────────────────────────────────────────── 2순위 · 역회전
im, d = page("2순위 · 역회전 빈쿠션  (공 하나)",
             "9시 30분 3팁 역회전.  20샷.   ★ 쿠션에 서서 들어가는 각(입사 10~30도) 위주로")

for i, (lab, cn, fn, col, note) in enumerate([
        ("서서 들어감", 60, 50, "#ff78be", "입사 10~30도  ← 여기가 급하다"),
        ("누워서 들어감", 90, 20, "#7fd8ff", "입사 60도 이상  ← 차이가 없다")]):
    cue, pts, inc = five_half_shot(cn, fn, cushions=4)
    tb = Table(im, 110 + i * 640, 250, 560)
    tb.frame()
    tb.line([cue] + pts, col, 4)
    tb.ball(*cue, "#f6f5ee")
    x = 110 + i * 640
    d.text((x, 620), lab, font=f(38), fill=col)
    d.text((x, 674), note, font=f(26), fill="#9aa2b2")

tipboard(d, 1560, 400, 110, 0, "9시 30분 3팁", "#ffd54a", side=-1.0)
d.text((1400, 566), "역회전 — 당점판 왼쪽", font=f(28), fill="#9aa2b2")

d.text((110, 760), "오전 7샷(20접점)에서 이미 나온 것", font=f(34), fill="#ffd54a")
d.line([110, 806, 1300, 806], fill="#3a3f49", width=2)
for i, (a, b, c2) in enumerate([("입사 11~23도  (서서)", "역회전이 순회전보다 13도 덜 벌어진다", "#ff78be"),
                                ("입사 60~62도  (누워서)", "순회전과 거의 같다 (1.7도)", "#7fd8ff")]):
    d.text((110, 826 + i * 50), a, font=f(29), fill=c2)
    d.text((560, 826 + i * 50), b, font=f(29), fill="#e8eaee")
d.text((110, 940), "한 접점은 입사 20.3도 → 반사 8.4도 로, 들어간 각보다 작게 나왔다.",
       font=f(28), fill="#9aa2b2")
d.text((110, 982), "역회전이 공을 되돌린 것이다 — 리버스가 숫자로 잡혔다.", font=f(28), fill="#9aa2b2")
d.text((110, 1042), "※ 실측 반사표(0808, 385접점)는 순회전 전용이라 역회전에 쓸 수 없다.",
       font=f(29), fill="#ff9f9a")
d.text((110, 1084), "   되돌아오기 · 리버스 샷이 통째로 여기 걸려 있다.", font=f(27), fill="#9aa2b2")
im.save(OUT / "촬영2.png")

# ────────────────────────────────────────────── 3순위 · 충돌 양끝
im, d = page("3순위 · 충돌 양끝 채우기  (두 공)",
             "아주 얇게 5샷 + 두껍게 5샷.  당점은 오전과 같은 12시 2팁.   배치는 다시 하지 않는다")
t = Table(im, 110, 250, 900)
t.frame()
t.ball(1224, 612, "#d6342c", txt="1적구", tf=f(26))
t.ball(500, 612, "#f6f5ee", txt="수구", tf=f(26))
for k, (lab, th, col) in enumerate([("아주 얇게", .1, "#7fd8ff"), ("두껍게", .85, "#ff78be")]):
    off = (1 - th) * BALL
    t.line([(500, 612), (2300, 612 + off * (2300 - 500) / (1224 - 500))], col, 4)

cx, cy, R = 1450, 430, 135
d.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#d6342c", outline="#14161a", width=4)
d.text((cx, cy - R - 34), "1적구", font=f(28), fill="#ffb0aa", anchor="ms")
for lab, th, col in [("아주 얇게", .1, "#7fd8ff"), ("두껍게", .85, "#ff78be")]:
    ox = (1 - th) * 2 * R
    d.ellipse([cx - ox - R, cy - R, cx - ox + R, cy + R], outline=col, width=6)
d.text((cx - 2 * R * .9, cy + R + 44), "아주 얇게", font=f(28), fill="#7fd8ff", anchor="ms")
d.text((cx - 2 * R * .15, cy + R + 86), "두껍게", font=f(28), fill="#ff78be", anchor="ms")

d.text((1700, 300), "오전에 잡힌 두께", font=f(30), fill="#ffd54a")
for i, (lab, n) in enumerate([("1/8", 1), ("2/8", 4), ("3/8", 3), ("4/8", 4),
                              ("5/8", 3), ("6/8", 0), ("7/8", 0)]):
    yy = 350 + i * 44
    col = "#ff9f9a" if n == 0 else ("#ffd54a" if n <= 1 else "#6eeb5a")
    d.text((1710, yy), lab, font=f(28), fill="#c8ccd4")
    d.rectangle([1780, yy + 6, 1780 + max(6, n * 18), yy + 26], fill=col)
    d.text((1796 + max(6, n * 18), yy), str(n), font=f(26), fill=col)
d.text((1700, 670), "6/8 · 7/8 이 비었고", font=f(26), fill="#ff9f9a")
d.text((1700, 706), "1/8 은 1샷뿐이다", font=f(26), fill="#ffd54a")

d.text((110, 800), "★ 최대 80% 로 치신 것이 있다고 했는데 잡힌 것은 68% 가 최대였다",
       font=f(32), fill="#ffe98a")
d.text((110, 852), "두껍게 5샷 · 아주 얇게 5샷이면 양끝이 채워진다. 가운데는 이미 충분하다.",
       font=f(28), fill="#9aa2b2")
d.text((110, 918), "※ 두 공이 60~80cm 이상 떨어지게. 너무 붙으면 버려진다",
       font=f(29), fill="#ff9f9a")
d.text((110, 962), "※ 충돌 후 1초는 건드리지 않는다", font=f(29), fill="#e8eaee")
d.text((110, 1006), "※ 두께를 눈으로 잴 필요 없다 — collide.py 가 궤적에서 재준다",
       font=f(29), fill="#e8eaee")
d.text((110, 1062), "당점은 오전과 같은 12시 2팁으로. 조건이 다르면 같은 표에 못 넣는다.",
       font=f(28), fill="#9aa2b2")
im.save(OUT / "촬영3.png")

# ────────────────────────────────────────────── 4순위 · 여유
im, d = page("4순위 · 시간 남으면  (공 하나)", "세게 5~10샷 · 아주 얕게 5샷.  당점 9시30분 3팁")
for i, (lab, cn, fn, col, why1, why2) in enumerate([
        ("세게", 50, 30, "#ff78be",
         "오전 32샷 중 2.5m/s 넘는 것이 1샷뿐이다.",
         "'내 힘으로 몇 쿠션까지' 의 위쪽 끝이 비어 있다"),
        ("아주 얕게 눕혀서", 100, 20, "#7fd8ff",
         "실측표가 입사 8~73도까지밖에 없다.",
         "73도 넘는 각은 지금 외삽으로 그린다")]):
    cue, pts, inc = five_half_shot(cn, fn, cushions=7 if i == 0 else 5)
    tb = Table(im, 110 + i * 940, 260, 800)
    tb.frame()
    tb.line([cue] + pts, col, 4)
    tb.ball(*cue, "#f6f5ee")
    x = 110 + i * 940
    d.text((x, 740), lab, font=f(40), fill=col)
    d.text((x, 800), why1, font=f(28), fill="#e8eaee")
    d.text((x, 842), why2, font=f(28), fill="#9aa2b2")
    d.text((x, 900), f"1쿠션 입사 {inc:.0f}도", font=f(26), fill="#7f8898")

d.rounded_rectangle([110, 970, 1940, 1120], radius=16, fill="#1e2128", outline="#3a3f49", width=2)
d.text((140, 990), "이 둘은 없어도 오늘 목표는 달성된다", font=f(32), fill="#ffd54a")
d.text((140, 1040), "1·2·3순위(45샷)가 먼저다. 시간이 남을 때만 하시면 된다.",
       font=f(28), fill="#9aa2b2")
d.text((140, 1080), "세게 치는 것은 2순위 역회전을 칠 때 몇 개 섞어도 된다.",
       font=f(28), fill="#9aa2b2")
im.save(OUT / "촬영4.png")

print("만들었습니다:")
for n in range(0, 5):
    print("  ", OUT / f"촬영{n}.png")
