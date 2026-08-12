# -*- coding: utf-8 -*-
"""기본 진로표 그림 — 1순위(빈쿠션 0개)의 회로들.

사용자 2026-08-12 구조 그대로 —
  한 회로 = (먼저 치는 공, 1적구를 맞은 뒤 **첫 쿠션**, 그 쿠션에서 **도는 방향**)
  첫 쿠션 4 × 도는 방향 2 = 8 가지 모양.  먼저 치는 공 2 를 곱해 16 칸.
  (먼저 치는 공은 **자리**만 다르고 모양은 같으므로 그림은 8 장이다)

★ 여기서 드러나는 것 —
  다이를 한 방향으로 돌면 쿠션 차례가 자동으로 정해진다.
     반시계  상 → 좌 → 하 → 우 → 상
     시계    상 → 우 → 하 → 좌 → 상
  그래서 8 가지는 전부 **앞돌리기(단-장-단)** 아니면 **옆·뒤돌리기(장-단-장)** 다.
  횡단샷(장-장-장)·종단샷(단-단-단)은 여기 안 들어온다 — 도는 것이 아니라
  같은 두 쿠션 사이를 왔다 갔다 하는 것이라서다.

만드는 것:  C:/sc/기본진로.png
"""
import math, os
from PIL import Image, ImageDraw, ImageFont

W, H = 2540.0, 1270.0                      # 중대 쿠션 안쪽 (data/table_medium.json)
BALL = 61.5

RAILS = {'top': (0, -1), 'bottom': (0, 1), 'left': (1, 0), 'right': (-1, 0)}
KR    = {'top': '상', 'bottom': '하', 'left': '좌', 'right': '우'}
LONG  = ('top', 'bottom')                  # 장쿠션
CCW   = ['top', 'left', 'bottom', 'right']  # 반시계로 도는 차례
CW    = ['top', 'right', 'bottom', 'left']  # 시계


def next_rail(p, d):
    """지금 자리에서 이 방향으로 갈 때 먼저 닿는 쿠션과 그 자리."""
    best = None
    for name, n in RAILS.items():
        if name == 'top':    t = (H - p[1]) / d[1] if d[1] > 1e-9 else None
        elif name == 'bottom': t = (0 - p[1]) / d[1] if d[1] < -1e-9 else None
        elif name == 'right':  t = (W - p[0]) / d[0] if d[0] > 1e-9 else None
        else:                  t = (0 - p[0]) / d[0] if d[0] < -1e-9 else None
        if t is None or t < 1e-6: continue
        q = (p[0] + d[0]*t, p[1] + d[1]*t)
        if best is None or t < best[0]: best = (t, name, q)
    return None if best is None else (best[1], best[2])


def mirror(d, rail):
    n = RAILS[rail]
    dot = d[0]*n[0] + d[1]*n[1]
    return (d[0] - 2*dot*n[0], d[1] - 2*dot*n[1])


def walk(p, ang, want):
    """이 방향으로 굴려서 쿠션 차례가 want 와 같으면 접점들을 돌려준다."""
    d, cur, pts = (math.cos(ang), math.sin(ang)), p, []
    for r in want:
        nx = next_rail(cur, d)
        if nx is None or nx[0] != r: return None
        pts.append(nx[1]); d = mirror(d, r); cur = nx[1]
    nx = next_rail(cur, d)                     # 3쿠션 다음 방향 (2적구를 놓을 곳)
    end = nx[1] if nx else cur
    return pts, end, d


def solve(p, want):
    """쿠션 차례가 want 가 되는 출발 방향을 찾는다. 제일 넓은 구간의 가운데."""
    ok = [a for a in [i*0.002 for i in range(int(2*math.pi/0.002))] if walk(p, a, want)]
    if not ok: return None
    runs, cur = [], [ok[0]]
    for a in ok[1:]:
        if a - cur[-1] < 0.005: cur.append(a)
        else: runs.append(cur); cur = [a]
    runs.append(cur)
    best = max(runs, key=len)
    return best[len(best)//2]


# ── 여덟 가지 회로 ──────────────────────────────────────────────────────
# 첫 쿠션과 도는 방향이 정해지면 나머지 두 쿠션은 저절로 정해진다.
CASES = []
for first in ('top', 'bottom', 'left', 'right'):
    for turn, order in (('반시계', CCW), ('시계', CW)):
        i = order.index(first)
        want = [order[(i+j) % 4] for j in range(3)]
        CASES.append((first, turn, want))

# 1적구 자리 — 회로마다 그 쿠션 쪽으로 나갈 수 있게 놓는다
OBJ = {'top': (1250, 780), 'bottom': (1250, 490), 'left': (760, 635), 'right': (1780, 635)}

# ── 그리기 ─────────────────────────────────────────────────────────────
PAD, GAP, SCALE = 46, 34, 0.185
TW, TH = int(W*SCALE), int(H*SCALE)
COLS, ROWS = 2, 4
IW = PAD*2 + TW*COLS + GAP*(COLS-1)
IH = PAD*2 + (TH+62)*ROWS + GAP*(ROWS-1) + 78

img = Image.new('RGB', (IW, IH), '#14161a')
g = ImageDraw.Draw(img)

def font(sz, bold=True):
    for nm in ('malgunbd.ttf' if bold else 'malgun.ttf', 'malgun.ttf'):
        try: return ImageFont.truetype(nm, sz)
        except Exception: pass
    return ImageFont.load_default()

F_T, F_L, F_S = font(30), font(21), font(17, False)

g.text((PAD, 24), '기본 진로표 · 1순위 (빈쿠션 0개 — 수구가 직접 1적구를 친다)', font=F_T, fill='#f2f4f8')
g.text((PAD, 62),
       '첫 쿠션 4 × 도는 방향 2 = 8 가지 모양.  먼저 치는 공 2 를 곱해 16 칸.',
       font=F_S, fill='#8b93a0')

def px(x, y, ox, oy):
    return (ox + x*SCALE, oy + (H - y)*SCALE)

for i, (first, turn, want) in enumerate(CASES):
    c, r = i % COLS, i // COLS
    ox = PAD + c*(TW+GAP)
    oy = PAD + 78 + r*(TH+62+GAP)

    g.rectangle([ox-3, oy-3, ox+TW+3, oy+TH+3], fill='#2a2f36')
    g.rectangle([ox, oy, ox+TW, oy+TH], fill='#24272c')
    for k in range(1, 8):                                  # 다이아 격자
        x = ox + TW*k/8
        g.line([x, oy, x, oy+TH], fill='#31353c')
    for k in range(1, 4):
        y = oy + TH*k/4
        g.line([ox, y, ox+TW, y], fill='#31353c')

    P = OBJ[first]
    a = solve(P, want)
    if a is None:
        g.text((ox+10, oy+10), '(안 나옴)', font=F_L, fill='#ff6a5e'); continue
    pts, end, _ = walk(P, a, want)

    # 수구 — 1적구 뒤쪽에서 오게 놓는다
    back = (P[0] - math.cos(a)*640, P[1] - math.sin(a)*640)
    back = (min(max(back[0], 90), W-90), min(max(back[1], 90), H-90))

    line = [back, P] + list(pts) + [end]
    cols = ['#fafafa', '#ffd600', '#6eeb5a', '#ebf0fa']
    for j in range(len(line)-1):
        g.line([px(*line[j], ox, oy), px(*line[j+1], ox, oy)],
               fill=cols[min(j, 3)], width=5)
    for j, q in enumerate(pts):                            # 쿠션 접점
        x, y = px(*q, ox, oy)
        g.ellipse([x-6, y-6, x+6, y+6], fill='#ffffff')
        g.text((x+9, y-11), str(j+1), font=F_S, fill='#cfd6e0')

    for q, col in ((back, '#f4f4f2'), (P, '#e8342a'), (end, '#f2c500')):
        x, y = px(*q, ox, oy)
        g.ellipse([x-11, y-11, x+11, y+11], fill=col, outline='#101216', width=2)

    kind = '앞돌리기' if want[0] not in LONG else '옆·뒤돌리기'
    g.text((ox, oy+TH+9),
           '첫 쿠션 %s · %s   →   %s   (%s)' %
           (KR[first], turn, '-'.join('장' if w in LONG else '단' for w in want), kind),
           font=F_L, fill='#f2f4f8')
    g.text((ox, oy+TH+36), '쿠션 차례  ' + ' → '.join(KR[w] for w in want),
           font=F_S, fill='#8b93a0')

g.text((PAD, IH-46),
       '★ 여덟 가지가 전부 앞돌리기(단-장-단) 아니면 옆·뒤돌리기(장-단-장) 다.  '
       '횡단샷(장-장-장)·종단샷(단-단-단)은 도는 것이 아니라 왔다 갔다 하는 것이라 여기 없다.',
       font=F_S, fill='#e0c46e')

os.makedirs('C:/sc', exist_ok=True)
img.save('C:/sc/기본진로.png')
print('C:/sc/기본진로.png', img.size)
