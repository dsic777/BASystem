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


# ★★ 사용자 2026-08-12 (1·2.jpg): '1 2 가 앞돌리기 기본궤적입니다.'
#   1 은 좌(단) → 하(장) → **상(장)** · 2 는 좌(단) → 하(장) → **우(단)**.
#   **둘 다 앞돌리기인데 3쿠션이 다르다.**
#   ⚠️ 나는 '도는 방향이 정해지면 쿠션 차례가 저절로 정해진다' 고 놓고
#      상→좌→하→우 고리를 강제했는데 그것이 틀렸다. 사용자가 준 조건은
#      **첫 쿠션 4 × 도는 방향 2** 뿐이고, 나머지 쿠션은 각도가 정한다.
def walk(p, ang, first, turn):
    """이 방향으로 3쿠션 굴린다. 첫 쿠션이 first 이고 거기서 도는 쪽이 turn 이어야 한다."""
    d, cur, pts = (math.cos(ang), math.sin(ang)), p, []
    for i in range(3):
        nx = next_rail(cur, d)
        if nx is None: return None
        if i == 0 and nx[0] != first: return None
        # ★ 2쿠션은 **반대 종류**로 간다 — 장 다음엔 단, 단 다음엔 장.
        #   같은 종류로 이어지면(상→하) 도는 것이 아니라 장쿠션 사이를 왔다 갔다 한 것이다.
        #   사용자 1·2.jpg 의 앞돌리기도 둘 다 단-장-… 로 시작한다.
        #   ⚠️ 3쿠션은 안 묶는다 — 1 은 단-장-**장**, 2 는 단-장-**단** 인데 둘 다 앞돌리기다.
        if i == 1 and ((nx[0] in LONG) == (first in LONG)): return None
        nd = mirror(d, nx[0])
        if i == 0:                                   # 첫 쿠션에서 꺾이는 쪽
            cr = d[0]*nd[1] - d[1]*nd[0]
            if abs(cr) < 1e-9: return None
            if (1 if cr > 0 else -1) != turn: return None
        pts.append(nx[1]); d = nd; cur = nx[1]
    nx = next_rail(cur, d)                     # 3쿠션 다음 방향 (2적구를 놓을 곳)
    end = nx[1] if nx else cur
    return pts, end, d


def solve(p, first, turn):
    """첫 쿠션·도는 쪽이 맞는 출발 방향을 찾는다. 제일 넓은 구간의 가운데."""
    ok = [a for a in [i*0.002 for i in range(int(2*math.pi/0.002))]
          if walk(p, a, first, turn)]
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
# 첫 쿠션이 **장**이면 옆·뒤돌리기 (수구 자리로 갈린다), **단**이면 앞돌리기.
CASES = []
for first in ('top', 'bottom', 'left', 'right'):
    for turn, tv in (('반시계', 1), ('시계', -1)):
        if first in LONG:
            CASES.append((first, turn, tv, '세로', '옆돌리기'))
            CASES.append((first, turn, tv, '가로', '뒤돌리기'))
        else:
            CASES.append((first, turn, tv, '가로', '앞돌리기'))

# 1적구 자리 — 회로마다 그 쿠션 쪽으로 나갈 수 있게 놓는다
OBJ = {'top': (1250, 780), 'bottom': (1250, 490), 'left': (760, 635), 'right': (1780, 635)}

# ★★ 사용자 2026-08-12: '옆돌리기 뒤돌리기 **수구의 위치를 정확하게** 놓아보세요.'
#   장-단-장 은 쿠션 차례가 같고 **수구 자리로만** 옆/뒤가 갈린다 (교본 ss1~ss4 확정) —
#     수구와 1적구가 **세로**(단쿠션과 평행)로 서면   옆돌리기
#     수구와 1적구가 **가로**(장쿠션과 평행)로 서면   뒤돌리기
#   전에는 조준선 뒤 640mm 에 기계적으로 놓아서 둘이 구분되지 않았다.
def place_cue(P, ang, mode):
    """1적구 P 와 나가는 방향 ang 이 주어졌을 때 수구를 어디에 놓아야 하나.

    mode '세로' 면 두 공이 세로로, '가로' 면 가로로 서게. 분리각이 그럴듯한
    자리 중에서 그 성질이 제일 뚜렷한 것을 고른다."""
    out = (math.cos(ang), math.sin(ang))
    best = None
    for gx in range(1, 40):
        for gy in range(1, 20):
            c = (W*gx/40.0, H*gy/20.0)
            dx, dy = P[0]-c[0], P[1]-c[1]
            d = math.hypot(dx, dy)
            if d < 420 or d > 1500: continue            # 너무 붙거나 너무 멀면 그림이 안 산다
            inc = (dx/d, dy/d)
            cross = inc[0]*out[1] - inc[1]*out[0]
            dot   = inc[0]*out[0] + inc[1]*out[1]
            deg   = math.degrees(math.atan2(abs(cross), dot))
            if not (18 <= deg <= 62): continue          # 실제로 칠 수 있는 분리각
            ratio = abs(dy) / max(abs(dx), 1e-6)        # 클수록 세로
            score = ratio if mode == '세로' else 1.0/max(ratio, 1e-6)
            if best is None or score > best[0]: best = (score, c, deg)
    return (None, None) if best is None else (best[1], best[2])

# ── 그리기 ─────────────────────────────────────────────────────────────
PAD, GAP, SCALE = 46, 30, 0.150
TW, TH = int(W*SCALE), int(H*SCALE)
COLS, ROWS = 3, 4
IW = PAD*2 + TW*COLS + GAP*(COLS-1)
IH = PAD*2 + (TH+62)*ROWS + GAP*(ROWS-1) + 92

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
       '첫 쿠션 4 × 도는 방향 2 = 8 회로.  장-단-장 은 수구 자리로 옆/뒤가 또 갈려 12 장.  '
       '먼저 치는 공 2 를 곱하면 16 칸.',
       font=F_S, fill='#8b93a0')

def which_rail(q):
    if abs(q[1] - H) < 1: return 'top'
    if abs(q[1]) < 1:     return 'bottom'
    if abs(q[0]) < 1:     return 'left'
    return 'right'
def next_rail_name(pts, k):
    return which_rail(pts[k])

def px(x, y, ox, oy):
    return (ox + x*SCALE, oy + (H - y)*SCALE)

for i, (first, turn, tv, mode, kind) in enumerate(CASES):
    c, r = i % COLS, i // COLS
    ox = PAD + c*(TW+GAP)
    oy = PAD + 92 + r*(TH+62+GAP)

    g.rectangle([ox-3, oy-3, ox+TW+3, oy+TH+3], fill='#2a2f36')
    g.rectangle([ox, oy, ox+TW, oy+TH], fill='#24272c')
    for k in range(1, 8):                                  # 다이아 격자
        x = ox + TW*k/8
        g.line([x, oy, x, oy+TH], fill='#31353c')
    for k in range(1, 4):
        y = oy + TH*k/4
        g.line([ox, y, ox+TW, y], fill='#31353c')

    P = OBJ[first]
    a = solve(P, first, tv)
    if a is None:
        g.text((ox+10, oy+10), '(안 나옴)', font=F_L, fill='#ff6a5e'); continue
    pts, end, _ = walk(P, a, first, tv)
    order = [nm for nm in (next_rail_name(pts, k) for k in range(3))]
    back, sep = place_cue(P, a, mode)
    if back is None:
        g.text((ox+10, oy+10), '(수구 자리 못 찾음)', font=F_L, fill='#ff6a5e'); continue

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

    g.text((ox, oy+TH+9), '%s   첫 쿠션 %s · %s' % (kind, KR[first], turn),
           font=F_L, fill='#f2f4f8')
    g.text((ox, oy+TH+34),
           '%s   %s   두 공 %s   분리각 %d도' %
           ('-'.join('장' if w in LONG else '단' for w in order),
            ' → '.join(KR[w] for w in order), mode, round(sep)),
           font=F_S, fill='#8b93a0')

g.text((PAD, IH-52),
       '★ 장-단-장 은 쿠션 차례가 같고 **수구 자리**로만 옆/뒤가 갈린다 — '
       '두 공이 세로면 옆돌리기, 가로면 뒤돌리기 (교본 ss1~ss4).',
       font=F_S, fill='#e0c46e')
g.text((PAD, IH-28),
       '★ 한 칸 안에서 **두께가 3쿠션을 가른다** — 사용자 1·3.jpg 는 같은 칸(좌·반시계)인데 '
       '얇게(21%) 치면 단-장-단, 두껍게(62%) 치면 단-장-장 이다. 그림은 넓은 쪽 하나만 그렸다.',
       font=F_S, fill='#e0c46e')

os.makedirs('C:/sc', exist_ok=True)
img.save('C:/sc/기본진로.png')
print('C:/sc/기본진로.png', img.size)
