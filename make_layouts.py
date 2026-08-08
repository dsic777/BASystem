"""정확도 측정용 배치도·촬영위치 그림을 만든다.

⚠️ 배치는 **사용자가 당구대에서 정확히 놓을 수 있는 자리**여야 한다. 임의의 mm 값은
   놓을 방법이 없어 정답 구실을 못 한다. 정확히 놓을 수 있는 자리는 셋뿐이다.
     1) 다이아몬드 교차점 — 장쿠션 8등분 · 단쿠션 4등분 = 306mm 격자
     2) 쿠션에 붙이고 다이아몬드에 맞추기 — 중심이 벽에서 정확히 반지름
     3) 코너에 붙이기 — 두 쿠션에 동시에 닿는 자리

    python c:\\Portfolio\\billiards\\make_layouts.py
"""
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"c:\Portfolio\billiards")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from core.table import Table                                     # noqa: E402

OUT = Path(r"C:\sc")
t = Table.load()
R = t.ball_diameter / 2
GX = t.width / t.long_divisions          # 306
GY = t.height / t.short_divisions        # 306

LAYOUTS = {
    "01": ("격자 3점", [
        ("white",  1 * GX, 1 * GY, "아래 다이아 1번 · 왼쪽 다이아 1번 교차"),
        ("yellow", 4 * GX, 2 * GY, "아래 다이아 4번 · 왼쪽 다이아 2번 교차 (한가운데)"),
        ("red",    6 * GX, 3 * GY, "아래 다이아 6번 · 왼쪽 다이아 3번 교차"),
    ]),
    "02": ("격자 대각", [
        ("white",  1 * GX, 3 * GY, "아래 다이아 1번 · 왼쪽 다이아 3번 교차"),
        ("yellow", 4 * GX, 1 * GY, "아래 다이아 4번 · 왼쪽 다이아 1번 교차"),
        ("red",    7 * GX, 2 * GY, "아래 다이아 7번 · 왼쪽 다이아 2번 교차"),
    ]),
    "03": ("쿠션 밀착", [
        ("white",  2 * GX, R, "아래 쿠션에 붙이고 아래 다이아 2번에 맞춤"),
        ("yellow", 6 * GX, t.height - R, "위 쿠션에 붙이고 위 다이아 6번에 맞춤"),
        ("red",    R, 2 * GY, "왼쪽 쿠션에 붙이고 왼쪽 다이아 2번에 맞춤"),
    ]),
    "04": ("코너 밀착", [
        ("white",  R, R, "왼쪽아래 코너 — 두 쿠션에 동시에 닿게"),
        ("yellow", t.width - R, t.height - R, "오른쪽위 코너 — 두 쿠션에 동시에 닿게"),
        ("red",    4 * GX, 2 * GY, "아래 다이아 4번 · 왼쪽 다이아 2번 교차 (한가운데)"),
    ]),
}

TONE = {"white": (246, 245, 238), "yellow": (240, 190, 40), "red": (214, 52, 44)}
NAME = {"white": "흰공", "yellow": "노란공", "red": "빨간공"}


def font(sz, bold=False):
    for p in (r"C:\Windows\Fonts\malgunbd.ttf" if bold else r"C:\Windows\Fonts\malgun.ttf",
              r"C:\Windows\Fonts\malgun.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except OSError:
            pass
    return ImageFont.load_default()


SC = 0.42                                  # mm → px
PAD = 210
RAIL = t.rail_x * SC


def table_image(title, note_lines, note_gap=34):
    W = int(t.outer_width * SC) + PAD * 2
    H = int(t.outer_height * SC) + PAD * 2 + 250 + note_gap
    im = Image.new("RGB", (W, H), (22, 24, 28))
    d = ImageDraw.Draw(im)
    ox, oy = PAD + t.rail_x * SC, PAD + t.rail_y * SC       # 노즈 좌하단
    d.rectangle([PAD, PAD, PAD + t.outer_width * SC, PAD + t.outer_height * SC],
                fill=(150, 112, 62))
    d.rectangle([ox, oy, ox + t.width * SC, oy + t.height * SC], fill=(38, 74, 190))

    def px(x, y):                                            # mm(왼쪽아래 원점) → 픽셀
        return (ox + x * SC, oy + (t.height - y) * SC)

    # 다이아몬드 + 번호
    f = font(20, True)
    for i in range(t.long_divisions + 1):
        for yy, dy in ((0, -1), (t.height, 1)):
            cx, cy = px(i * GX, yy)
            cy += dy * t.frame_offset * SC
            d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(242, 238, 224))
            d.text((cx, cy + dy * 22), str(i), font=f, fill=(255, 235, 120), anchor="mm")
    for j in range(t.short_divisions + 1):
        for xx, dx in ((0, -1), (t.width, 1)):
            cx, cy = px(xx, j * GY)
            cx += dx * t.frame_offset * SC
            d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(242, 238, 224))
            d.text((cx + dx * 24, cy), str(j), font=f, fill=(255, 235, 120), anchor="mm")

    # 격자선 (놓을 자리를 눈으로 잇게)
    for i in range(1, t.long_divisions):
        d.line([px(i * GX, 0), px(i * GX, t.height)], fill=(70, 105, 210), width=1)
    for j in range(1, t.short_divisions):
        d.line([px(0, j * GY), px(t.width, j * GY)], fill=(70, 105, 210), width=1)

    d.text((PAD, 46), title, font=font(38, True), fill=(240, 240, 245))
    y = PAD + t.outer_height * SC + note_gap
    for line, col in note_lines:
        d.text((PAD, y), line, font=font(23), fill=col)
        y += 34
    return im, d, px


for code, (name, balls) in LAYOUTS.items():
    notes = []
    for c, x, y, how in balls:
        notes.append((f"● {NAME[c]}   ({x:.0f}, {y:.0f}) mm   —   {how}", TONE[c]))
    notes.append(("", (0, 0, 0)))
    notes.append(("사진에 당구대 전체가 들어오게. 공을 놓은 뒤 손·큐대는 치울 것.",
                  (190, 195, 205)))
    im, d, px = table_image(f"배치 {code} — {name}", notes)
    rp = t.ball_diameter / 2 * SC
    for c, x, y, _how in balls:
        cx, cy = px(x, y)
        d.ellipse([cx - rp, cy - rp, cx + rp, cy + rp], fill=TONE[c],
                  outline=(20, 20, 24), width=2)
        d.text((cx, cy - rp - 16), f"{x:.0f},{y:.0f}", font=font(19, True),
               fill=(255, 255, 255), anchor="mm")
    p = OUT / f"배치{code}.png"
    im.save(p)
    print(f"{p}   {name}")

# ---------------------------------------------------------------- 촬영 위치
im, d, px = table_image("촬영 위치 — 배치마다 이 네 자리에서 한 장씩", [
    ("고정 삼각대를 쓸 수 없으니 실제로 서게 되는 자리로 정했다.", (190, 195, 205)),
    ("네 자리 모두 당구대 전체가 화면에 들어와야 한다.", (190, 195, 205)),
    ("", (0, 0, 0)),
    ("A  아래 장쿠션 한가운데 뒤 · 가슴 높이        (제일 흔한 자세)", (120, 220, 255)),
    ("B  A 와 같은 자리 · 팔을 위로 뻗어 내려찍기   (높이만 다르게)", (120, 255, 160)),
    ("C  오른쪽 단쿠션 뒤 · 가슴 높이               (긴 방향으로 보기)", (255, 210, 110)),
    ("D  왼쪽아래 모서리 뒤 · 가슴 높이             (대각선)", (255, 150, 190)),
], note_gap=200)
L, T = PAD, PAD                                   # 나무 바깥 왼쪽위
Rr, Bm = PAD + t.outer_width * SC, PAD + t.outer_height * SC
mid = px(t.width / 2, t.height / 2)
for lbl, cx, cy, col in (("A", (L + Rr) / 2 - 46, Bm + 82, (120, 220, 255)),
                         ("B", (L + Rr) / 2 + 46, Bm + 82, (120, 255, 160)),
                         ("C", Rr + 92, (T + Bm) / 2, (255, 210, 110)),
                         ("D", L - 92, Bm + 82, (255, 150, 190))):
    d.line([cx, cy, *mid], fill=col, width=2)
    d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=col, outline=(20, 20, 24), width=3)
    d.text((cx, cy), lbl, font=font(32, True), fill=(20, 20, 24), anchor="mm")
d.text(((L + Rr) / 2, Bm + 136), "A 는 가슴 높이 · B 는 같은 자리에서 더 높이",
       font=font(20), fill=(180, 185, 195), anchor="mm")
p = OUT / "촬영위치.png"
im.save(p)
print(f"{p}")
