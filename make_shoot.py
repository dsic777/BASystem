"""오늘 촬영할 것을 그림으로 만든다 → C:\\sc\\촬영0~4.png

    python c:\\Portfolio\\billiards\\make_shoot.py

    촬영0  한 장 요약 (공통 세팅 · 순위표 · 찍고 와서 돌릴 명령)
    촬영1~4  순위별

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


# ────────────────────────────────────────────── 0 · 한 장 요약
im, d = page("오늘 촬영  ·  2026-08-10",
             "하나로 쭉 이어서 찍는다.  순서대로  1순위 → 2순위 → 3순위")

d.rounded_rectangle([60, 190, 950, 566], radius=18, fill="#1e2128", outline="#3a3f49", width=2)
d.text((92, 214), "공통 — 어떻게 찍나", font=f(36), fill="#ffd54a")
for i, t in enumerate([
        "삼각대 고정.  네 코너가 다 보이게.  중간에 옮기지 않는다",
        "★ 공을 잡지 않는다 — 완전히 멈출 때까지 둔다",
        "한 샷이 멈춘 뒤 다음 샷.  조명 일정하게",
        "손으로 옮기는 장면은 섞여도 된다 (걸러낸다)",
        "두께 · 당점은 적을 필요 없다 — 궤적에서 계산된다",
        "순위가 바뀔 때 카메라에 손가락으로 1 · 2 · 3"]):
    col = "#ffe98a" if t.startswith("★") else "#e8eaee"
    d.text((100, 278 + i * 46), "·", font=f(30), fill="#7f8898")
    d.text((126, 276 + i * 46), t, font=f(29), fill=col)

# 순위표
cols = [(60, "순위"), (250, "무엇을"), (760, "공"), (900, "샷"), (1040, "나오는 것")]
y = 650
d.text((60, y - 52), "오늘 찍을 것", font=f(36), fill="#ffd54a")
for x, lab in cols:
    d.text((x, y), lab, font=f(27), fill="#7f8898")
d.line([60, y + 42, 1940, y + 42], fill="#3a3f49", width=2)
rows = [("1", "충돌 후 속도  (두 공)", "2개", "30", "두께별로 수구가 남기는 속도. 지금 데이터 0", "#ffd54a"),
        ("2", "세기별 빈쿠션  (공 하나)", "1개", "20~30", "그 속도로 몇 쿠션 더 가나. 뒷부분이 잘려 없다", "#7fd8ff"),
        ("3", "상하 당점 → 쿠션 반사", "1개", "15", "가정이 맞는지. 틀리면 코드가 틀린 것", "#6eeb5a"),
        ("4", "역회전 빈쿠션 (시간 남으면)", "1개", "20", "실측표는 순회전만. 되돌아오기가 여기 걸림", "#9aa2b2")]
for i, (n, what, ball, shots, gives, col) in enumerate(rows):
    yy = y + 66 + i * 64
    d.text((72, yy), n, font=f(40), fill=col)
    d.text((250, yy + 6), what, font=f(31), fill="#e8eaee")
    d.text((770, yy + 6), ball, font=f(29), fill="#c8ccd4")
    d.text((905, yy + 6), shots, font=f(29), fill="#c8ccd4")
    d.text((1040, yy + 8), gives, font=f(27), fill="#9aa2b2")

d.rounded_rectangle([1000, 190, 1940, 566], radius=18, fill="#1e2128", outline="#3a3f49", width=2)
d.text((1032, 214), "1순위와 2순위는 한 쌍이다", font=f(36), fill="#ffd54a")
for i, t in enumerate([
        ("1순위", "충돌에서 수구가 얼마나 속도를 남기나", "#ffd54a"),
        ("2순위", "그 속도로 앞으로 몇 쿠션 더 굴러가나", "#7fd8ff")]):
    d.text((1032, 278 + i * 66), t[0], font=f(30), fill=t[2])
    d.text((1150, 280 + i * 66), t[1], font=f(27), fill="#e8eaee")
d.line([1032, 412, 1900, 412], fill="#3a3f49", width=2)
d.text((1032, 430), "둘을 합치면 어떤 배치든", font=f(28), fill="#9aa2b2")
d.text((1032, 470), "'여기서 몇 쿠션 더 간다' 가 계산된다", font=f(31), fill="#6eeb5a")
d.text((1032, 516), "= 경로를 어디까지 그릴지가 정해진다", font=f(28), fill="#9aa2b2")

d.rounded_rectangle([60, 1000, 1940, 1130], radius=16, fill="#2a1f22", outline="#a34a44", width=2)
d.text((92, 1018), "★ 1순위(두 공)는 수구와 1적구가 60~80cm 이상 떨어지게", font=f(34), fill="#ffb0aa")
d.text((92, 1062), "너무 붙으면 프로그램이 '충돌이 아니다' 로 보고 그 샷을 버립니다. 가까워지면 한 공만 옮기세요.",
       font=f(26), fill="#e0b8b4")
d.text((92, 1096), "두 공 영상은 이번이 처음이라, 돌아오시면 앞부분 몇 샷부터 확인하겠습니다.",
       font=f(26), fill="#e0b8b4")
im.save(OUT / "촬영0.png")

# ────────────────────────────────────────────── 1순위
im, d = page("1순위 · 충돌 후 속도  (두 공)",
             "공 두 개만.  두께 3단계 × 세기 3단계.  한 칸에 3~4샷이면 30샷 안팎.   ★ 배치를 다시 하지 않는다")
t = Table(im, 150, 260, 1000)
t.frame()
t.ball(1224, 612, "#d6342c", txt="1적구 (고정)", tf=f(26))
t.ball(500, 612, "#f6f5ee", txt="수구", tf=f(26))
for k, (lab, th) in enumerate([("얇게", .15), ("반두께", .5), ("두껍게", .8)]):
    off = (1 - th) * BALL * (1 if k != 1 else 1)
    t.line([(500, 612), (2300, 612 + off * (2300 - 500) / (1224 - 500))],
           ["#7fd8ff", "#ffd600", "#ff78be"][k], 3)
d.text((150, 900), "★ 배치를 다시 하지 않는다 — 공이 멈춘 자리에서 그대로 다음 샷", font=f(31), fill="#ffe98a")
d.text((150, 946), "★ 충돌 후 1초는 건드리지 않는다 — 직후 속도를 그때 잰다", font=f(31), fill="#ffe98a")
d.text((150, 992), "★ 두께를 눈으로 잴 필요가 없다 — collide.py 가 궤적에서 재준다", font=f(31), fill="#ffe98a")
d.text((150, 1042), "반두께를 큐선으로 잡고, 거기서 얇게 · 두껍게로 갈라 치면 된다", font=f(29), fill="#e8eaee")
d.text((150, 1086), "두께 3단계  얇게 · 반두께 · 두껍게      세기 3단계  약 · 중 · 강      30샷 안팎",
       font=f(29), fill="#e8eaee")
d.text((1300, 1000), "※ 두 공이 60~80cm 이상", font=f(30), fill="#ff9f9a")
d.text((1300, 1044), "떨어져 있어야 잡힙니다.", font=f(30), fill="#ff9f9a")
d.text((1300, 1088), "가까워지면 한 공만 옮기세요", font=f(28), fill="#e0b8b4")

# 두께 그림 (오른쪽)
cx, cy, R = 1560, 560, 150
d.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#d6342c", outline="#14161a", width=4)
d.text((cx, cy - R - 40), "1적구", font=f(30), fill="#ffb0aa", anchor="ms")
for lab, th, col in [("얇게", .15, "#7fd8ff"), ("반두께", .5, "#ffd600"),
                     ("두껍게", .8, "#ff78be")]:
    ox = (1 - th) * 2 * R
    d.ellipse([cx - ox - R, cy - R, cx - ox + R, cy + R], outline=col, width=6)
    d.text((cx - ox, cy + R + 46 + [.15, .5, .8].index(th) * 46), lab,
           font=f(30), fill=col, anchor="ms")
d.text((1300, 940), "겹치는 정도가 두께다", font=f(30), fill="#9aa2b2")
im.save(OUT / "촬영1.png")

# ────────────────────────────────────────────── 2순위
im, d = page("2순위 · 세기별 빈쿠션  (공 하나)",
             "수구 50 → 1쿠션 30 기본각에서 시작해 이어 친다.  약 · 중 · 강 각 7~10샷")
# 한 다이에 셋을 겹쳐 그리니 읽을 수가 없었다 (7.jpg) — 갈라 그린다.
# 경로는 거울반사가 아니라 **실측 반사표**로 굴린 것이다 (사용자 지적).
# ★ 사용자 확정 2026-08-10 — 재는 것은 '다이 휨' 이 아니라 **세기 → 몇 쿠션까지**.
#   '공의 속도에 따라 궤적을 얼마나 이어야 하는가를 판단할 목적으로.'
#   그래서 배치를 여러 개 만들 이유가 없다. 같은 기본각을 **세기만 바꿔** 친다.
#   ⚠️ 몇 쿠션까지 가는지는 **이번에 재는 값**이다. 아래 3·5·7 은 그림용 예시일 뿐이다.
_cue, _pts, _ = five_half_shot(50, 30, cushions=7)
for i, (lab, upto, col) in enumerate([("약", 3, "#7fd8ff"), ("중", 5, "#ffd600"),
                                      ("강", 7, "#ff78be")]):
    t = Table(im, 110 + i * 620, 290, 540)
    t.frame()
    t.line([_cue] + _pts[:upto], col, 4)
    t.ball(*_cue, "#f6f5ee")
    x = 110 + i * 620
    d.text((x, 620), lab + "하게", font=f(40), fill=col)
    d.text((x + 150, 634), "7~10샷", font=f(28), fill="#9aa2b2")

d.text((110, 690), "세 그림은 같은 배치다 — 세기만 다르다.  어디까지 가는지가 이번에 재는 값이라,",
       font=f(28), fill="#9aa2b2")
d.text((110, 734), "그림의 3 · 5 · 7쿠션은 예시일 뿐이다.", font=f(28), fill="#9aa2b2")

d.rounded_rectangle([110, 786, 1120, 884], radius=14, fill="#1e2128", outline="#3a3f49", width=2)
d.text((136, 804), "수구 50  →  1쿠션 30       당점 9시 30분 3팁", font=f(34), fill="#ffd54a")
d.text((136, 848), "여기서 시작해 멈춘 자리에서 이어 친다.  당점은 셋 다 같게 (0808 과 같은 조건)",
       font=f(24), fill="#9aa2b2")

d.rounded_rectangle([110, 906, 1940, 1010], radius=16, fill="#2a2418", outline="#a3822c", width=2)
d.text((140, 924), "★ 공을 잡지 않는다 — 완전히 멈출 때까지 둔다.  이번 촬영의 핵심이다",
       font=f(34), fill="#ffe98a")
d.text((140, 968), "★ 5 · 6 · 7쿠션이 화면 안에 온전히.  마지막 쿠션 이후 진행선이 끝까지 보여야 한다",
       font=f(30), fill="#ffe98a")

d.text((110, 1034), "※ 0808 은 접점 위치만 보려던 촬영이라, 마지막 쿠션에서 공이 아직 살아 있는 샷이 72% 였다",
       font=f(28), fill="#ff9f9a")
d.text((110, 1078), "   (4쿠션 78% · 5쿠션 76%).  '얼마나 굴러가나' 는 그때 미룬 절차고, 이번이 그 차례다.",
       font=f(28), fill="#9aa2b2")
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
im, d = page("4순위 · 역회전 빈쿠션  (시간 남으면)",
             "공 하나.  역회전으로 20샷.   ※ 세기별 · 대회전은 2순위에 흡수됐다")
t = Table(im, 150, 300, 1150)
t.frame()
t.line(bank((350, 300), 30, 3), "#7fd8ff", 5)
t.line([(350, 300), (1500, 950), (900, 1224)], "#ff78be", 5, dash=True)
t.ball(350, 300, "#f6f5ee")
d.text((160, 1010), "실선 = 순회전 (지금 실측표에 있는 것)", font=f(30), fill="#7fd8ff")
d.text((160, 1054), "점선 = 역회전 (표가 통째로 비어 있다)", font=f(30), fill="#ff78be")
d.text((160, 1098), "되돌아오기 · 리버스 샷이 전부 여기 걸려 있다. 당점판에서 역회전 쪽을 막아 둔 이유다.",
       font=f(27), fill="#9aa2b2")

d.rounded_rectangle([1420, 380, 1940, 700], radius=16, fill="#1e2128", outline="#3a3f49", width=2)
d.text((1450, 400), "더 있으면 좋은 것", font=f(32), fill="#ffd54a")
d.text((1450, 462), "아주 얕게 눕는 각  몇 샷", font=f(29), fill="#e8eaee")
d.text((1450, 506), "실측표가 8~73도까지밖에 없다.", font=f(25), fill="#9aa2b2")
d.text((1450, 544), "73도 넘는 쪽이 비어 있어서", font=f(25), fill="#9aa2b2")
d.text((1450, 582), "그 각은 지금 외삽으로 그린다.", font=f(25), fill="#9aa2b2")
d.text((1450, 634), "2·3순위 칠 때 섞어 주시면 된다", font=f(26), fill="#7fd8ff")
im.save(OUT / "촬영4.png")

print("만들었습니다:")
for n in range(0, 5):
    print("  ", OUT / f"촬영{n}.png")
