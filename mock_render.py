"""index.html 이 계산한 실제 좌표로 화면을 다시 그려 본다 (배포 전 확인용).

⚠️ 캔버스 그림을 파이썬으로 흉내내는 것이라 완전히 같지는 않다. 배치·크기·색을
   눈으로 확인하는 용도다.

    python c:\\Portfolio\\billiards\\mock_render.py
"""
import io
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(r"c:\Portfolio\billiards")

app = re.findall(r"<script>(.*?)</script>",
                 (ROOT / "index.html").read_text(encoding="utf-8"), re.S)[1]
num = json.loads((ROOT / "data" / "five_half_numbers.json").read_text(encoding="utf-8"))
bo = json.loads((ROOT / "data" / "measured_bounce.json").read_text(encoding="utf-8"))
scales = [{"name": k, "reference": v.get("reference", "frame"),
           "color": "rgb(%d,%d,%d)" % tuple(v["color"]), "points": v["points"]}
          for k, v in num["scales"].items()]

BODY = r"""
const stubEl=new Proxy({},{get:(o,k)=>k==='style'?{}:
 k==='getContext'?(()=>new Proxy({},{get:()=>(()=>({}))})):
 k==='getBoundingClientRect'?(()=>({width:0,height:0})):(()=>{})});
globalThis.document={getElementById:()=>stubEl,createElement:()=>stubEl,addEventListener(){}};
globalThis.addEventListener=()=>{};globalThis.setInterval=()=>0;
globalThis.location={search:'',reload(){}};globalThis.fetch=()=>Promise.reject(new Error('x'));
globalThis.performance={now:()=>0};globalThis.devicePixelRatio=1;globalThis.window=globalThis;
globalThis.log=()=>{};globalThis.visualViewport=null;globalThis.Image=function(){return stubEl;};
process.on('unhandledRejection',()=>{});
const api=new Function(APPJS + "; return {buttonRects, clockCenter, clockR, systemNumbers,"
  +" pathFromAim, toPx, railPoint, orientation, fold, foldRail, ro(){return READOUT;},"
  +" setAll(t,sc,bo,l,p,s){T=t;SCALES=sc;BOUNCE=bo;L=l;PANEL=p;Object.assign(S,s);}};")();
const cw=2340, ch=1080, ow=2720, oh=1500;
const sc=Math.min((cw-3-260)/ow,(ch-2)/oh);
const rw=ow*sc, rh=oh*sc, rl=1, rt=1;
const T={width:2448,height:1224,outer_width:ow,outer_height:oh,rail_x:136,rail_y:138,
        ball_diameter:61.5,cushion_width:37,frame_offset:87,long_divisions:8,short_divisions:4};
const L={sc, rail:{x:rl,y:rt,w:rw,h:rh},
        cloth:{x:rl+136*sc,y:rt+138*sc,w:2448*sc,h:1224*sc},
        ox:rl+136*sc, oy:rt+138*sc+1224*sc};
const P={x:rl+rw+4, y:rt, w:Math.max(cw-(rl+rw)-8,40), h:rh};
const balls={cue:{p:[300,1050],color:'white'},
             obj1:{p:[2050,1130],color:'yellow'},
             obj2:{p:[2380,700],color:'red'}};
api.setAll(T,SC,BO,L,P,{balls, aim:[1120,-87], corr:0, cueWhite:true, place:null, rMode:0});
const hits=api.pathFromAim(balls.cue.p, [1120,-87], 0);
const o=api.orientation();
const dia=[];
for (const [rail,n] of [['bottom',8],['top',8],['left',4],['right',4]])
  for (let i=0;i<=n;i++){
    const t=i/n;
    const mm = rail==='bottom'?[T.width*t,-T.frame_offset]
             : rail==='top'?[T.width*t,T.height+T.frame_offset]
             : rail==='left'?[-T.frame_offset,T.height*t]:[T.width+T.frame_offset,T.height*t];
    dia.push(api.toPx(mm[0],mm[1]));
  }
const nums=[];
for (const s2 of SC) for (const pt of s2.points){
  let mm=api.railPoint(s2,pt.rail,pt.index);
  const rr=api.foldRail(o,pt.rail); mm=api.fold(o,mm);
  let q=api.toPx(mm[0],mm[1]);
  if (rr==='left'||rr==='right')
    q=[rr==='right'?(L.cloth.x+L.cloth.w+L.rail.x+L.rail.w)/2:(L.rail.x+L.cloth.x)/2, q[1]];
  nums.push({n:pt.number, x:q[0], y:q[1], c:s2.color, small:s2.name==='third_cushion'});
}
console.log(JSON.stringify({cw,ch,rail:L.rail,cloth:L.cloth,panel:P,sc,
  clock:api.clockCenter(), R:api.clockR(), btn:api.buttonRects(), readout:api.ro(),
  balls:Object.entries(balls).map(([k,b])=>({k,c:b.color,p:api.toPx(b.p[0],b.p[1])})),
  path:[balls.cue.p,...hits.map(h=>h.p)].map(q=>api.toPx(q[0],q[1])),
  dia, nums, sys:api.systemNumbers(), ballR:Math.max(5,T.ball_diameter/2*sc)}));
"""

js = ROOT / "peek" / "_mock.js"
js.parent.mkdir(exist_ok=True)
js.write_text("const APPJS=" + json.dumps(app) + ";\nconst SC=" +
              json.dumps(scales, ensure_ascii=False) + ";\nconst BO=" +
              json.dumps([[r[0], r[1]] for r in bo["table"]]) + ";\n" + BODY,
              encoding="utf-8")
run = subprocess.run(["node", str(js)], capture_output=True, text=True,
                     encoding="utf-8", errors="replace")
if run.returncode:
    print(run.stderr[:2000])
    sys.exit(1)
d = json.loads(run.stdout.strip().splitlines()[-1])

K = 0.62
W, H = int(d["cw"] * K), int(d["ch"] * K)
im = Image.new("RGB", (W, H), (14, 15, 18))
dr = ImageDraw.Draw(im, "RGBA")


def font(sz, italic=False):
    names = ["malgunbd.ttf", "arialbd.ttf"]
    if italic:
        names = ["ariali.ttf"] + names
    for nm in names:
        try:
            return ImageFont.truetype(r"C:\Windows\Fonts" + "\\" + nm, max(6, int(sz)))
        except OSError:
            pass
    return ImageFont.load_default()


def box(o):
    return [o["x"] * K, o["y"] * K, (o["x"] + o["w"]) * K, (o["y"] + o["h"]) * K]


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vgrad(x0, y0, x1, y1, stops):
    for i in range(int(y1 - y0)):
        t = i / max(1, y1 - y0)
        col = stops[-1][1]
        for j in range(len(stops) - 1):
            if stops[j][0] <= t <= stops[j + 1][0]:
                u = (t - stops[j][0]) / max(1e-6, stops[j + 1][0] - stops[j][0])
                col = mix(stops[j][1], stops[j + 1][1], u)
                break
        dr.line([x0, y0 + i, x1, y0 + i], fill=col)


TONE = {"white": (246, 245, 238), "yellow": (240, 190, 40), "red": (214, 52, 44)}

# ── 레일 ──────────────────────────────────────────────────────────────
r0 = box(d["rail"])
vgrad(r0[0], r0[1], r0[2], r0[3],
      [(0, (74, 78, 85)), (0.16, (43, 46, 52)), (0.84, (33, 36, 41)), (1, (58, 62, 69))])
for i in range(1, 34):
    yy = r0[1] + (r0[3] - r0[1]) * i / 34
    dr.line([r0[0], yy, r0[2], yy], fill=(201, 210, 224, 18))
dr.rectangle(r0, outline=(13, 15, 18), width=2)

# ── 천 ────────────────────────────────────────────────────────────────
c = d["cloth"]
cx0, cy0 = c["x"] * K, c["y"] * K
cw_, chh = c["w"] * K, c["h"] * K
cut = min(cw_, chh) * 0.055
cwp = 37 * d["sc"] * K
dr.rectangle([cx0 - cwp, cy0 - cwp, cx0 + cw_ + cwp, cy0 + chh + cwp], fill=(21, 23, 26))
felt = Image.new("RGB", (int(cw_), int(chh)))
fd = ImageDraw.Draw(felt)
mx, my, rad = cw_ / 2, chh * 0.42, cw_ * 0.62
for yy in range(int(chh)):
    for xx in range(0, int(cw_), 3):
        t = min(1.0, math.hypot(xx - mx, yy - my) / rad)
        col = (mix((49, 53, 60), (36, 39, 44), t / 0.55) if t < 0.55
               else mix((36, 39, 44), (21, 23, 26), (t - 0.55) / 0.45))
        fd.rectangle([xx, yy, xx + 3, yy], fill=col)
poly = [(cut, 0), (cw_ - cut, 0), (cw_, cut), (cw_, chh - cut),
        (cw_ - cut, chh), (cut, chh), (0, chh - cut), (0, cut)]
mask = Image.new("L", (int(cw_), int(chh)), 0)
ImageDraw.Draw(mask).polygon(poly, fill=255)
im.paste(felt, (int(cx0), int(cy0)), mask)

# ── 궤적 ──────────────────────────────────────────────────────────────
pts = [(p[0] * K, p[1] * K) for p in d["path"]]
cols = [(250, 250, 250), (255, 214, 0), (110, 235, 90),
        (235, 240, 250), (235, 240, 250), (235, 240, 250)]
bw = max(3, 61.5 * d["sc"] * K)
for i in range(len(pts) - 1):
    col = cols[min(i, len(cols) - 1)]
    dr.line([pts[i], pts[i + 1]], fill=col + (72,), width=int(bw))
    dr.line([pts[i], pts[i + 1]], fill=col, width=3)
for p in pts[1:]:
    dr.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6],
               fill=(110, 235, 90), outline=(20, 20, 26), width=2)

# ── 다이아몬드 · 눈금 ─────────────────────────────────────────────────
rd = max(4, c["h"] * 0.017) * K
for x, y in d["dia"]:
    dr.ellipse([x * K - rd, y * K - rd, x * K + rd, y * K + rd],
               fill=(253, 253, 250), outline=(13, 15, 18), width=2)
for n in d["nums"]:
    f = font(c["h"] * (0.055 if n["small"] else 0.065) * K)
    col = tuple(int(v) for v in n["c"][4:-1].split(","))
    for ox in (-2, 0, 2):
        for oy in (-2, 0, 2):
            dr.text((n["x"] * K + ox, n["y"] * K + oy), str(n["n"]),
                    font=f, fill=(16, 16, 20), anchor="mm")
    dr.text((n["x"] * K, n["y"] * K), str(n["n"]), font=f, fill=col, anchor="mm")

# ── 공 ────────────────────────────────────────────────────────────────
br = d["ballR"] * K
for b in d["balls"]:
    x, y = b["p"][0] * K, b["p"][1] * K
    base = TONE[b["c"]]
    dr.ellipse([x - br * 0.83, y - br * 0.12, x + br * 1.07, y + br * 0.72],
               fill=(0, 0, 0, 115))
    for i in range(int(br), 0, -1):
        t = 1 - i / br
        col = (mix((255, 255, 255), base, t / 0.30) if t < 0.30
               else mix(base, tuple(int(v * 0.42) for v in base), (t - 0.30) / 0.70))
        dr.ellipse([x - i, y - i, x + i, y + i], fill=col)
    if b["k"] == "cue":
        dr.ellipse([x - br * 1.28, y - br * 1.28, x + br * 1.28, y + br * 1.28],
                   outline=(255, 221, 51), width=max(2, int(br * 0.22)))

# ── 당점 ──────────────────────────────────────────────────────────────
ex, ey, RR = d["clock"][0] * K, d["clock"][1] * K, d["R"] * K
dr.ellipse([ex - RR, ey - RR, ex + RR, ey + RR],
           fill=(240, 240, 234), outline=(60, 62, 70), width=2)
dr.ellipse([ex + RR * 0.40, ey - RR * 0.84, ex + RR * 0.84, ey - RR * 0.40],
           fill=(222, 52, 44))

# ── 보정 바 ───────────────────────────────────────────────────────────
cb = [b for b in d["btn"] if b["lb"] in ("-", "0", "+")]
if len(cb) == 3:
    x0 = min(b["x"] for b in cb) * K
    x1 = max(b["x"] + b["w"] for b in cb) * K
    y0, hh = cb[0]["y"] * K, cb[0]["h"] * K
    pad = hh * 0.14
    vgrad(x0 - pad, y0 - pad, x1 + pad, y0 + hh + pad,
          [(0, (233, 237, 243)), (0.5, (185, 192, 203)), (1, (143, 151, 164))])
    dr.rounded_rectangle([x0 - pad, y0 - pad, x1 + pad, y0 + hh + pad],
                         radius=hh * 0.30, outline=(15, 17, 20),
                         width=max(2, int(hh * 0.07)))

# ── 버튼 ──────────────────────────────────────────────────────────────
for b in d["btn"]:
    bx = box(b)
    u = min(bx[2] - bx[0], bx[3] - bx[1])
    mx2, my2 = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
    lb = b["lb"]
    if lb in ("-", "0", "+"):
        dr.rounded_rectangle(bx, radius=u * 0.26, fill=(255, 255, 255, 140),
                             outline=(15, 17, 20, 140), width=max(1, int(u * 0.035)))
        dr.text((mx2, my2), lb, font=font(u * 0.62), fill=(30, 33, 38), anchor="mm")
        continue
    rnd = max(bx[2]-bx[0], bx[3]-bx[1]) * 0.5 if lb == "cam" else u * 0.22
    top, bot = (((242, 245, 249), (152, 161, 175)) if lb == "cam"
                else ((244, 246, 250), (207, 213, 223)))
    face = Image.new("RGB", (int(bx[2] - bx[0]), int(bx[3] - bx[1])))
    ImageDraw.Draw(face)
    for i in range(face.height):
        ImageDraw.Draw(face).line([0, i, face.width, i], fill=mix(top, bot, i / face.height))
    m2 = Image.new("L", face.size, 0)
    ImageDraw.Draw(m2).rounded_rectangle([0, 0, face.width - 1, face.height - 1],
                                         radius=rnd, fill=255)
    im.paste(face, (int(bx[0]), int(bx[1])), m2)
    dr.rounded_rectangle(bx, radius=rnd, outline=(15, 17, 20), width=max(2, int(u * 0.06)))
    if lb == "swap" or lb in TONE:
        col = TONE["white"] if lb == "swap" else TONE[lb]
        rr = u * 0.30
        dr.ellipse([mx2 - rr, my2 - rr, mx2 + rr, my2 + rr], fill=col,
                   outline=(20, 22, 26), width=max(2, int(u * 0.07)))
        if lb == "swap":
            rr = u * 0.39
            dr.ellipse([mx2 - rr, my2 - rr, mx2 + rr, my2 + rr],
                       outline=(200, 147, 26), width=max(2, int(u * 0.055)))
    elif lb == "cam":
        u2 = u * 0.86
        w2, bh = u2 * 0.62, u2 * 0.42
        x, y = mx2 - w2 / 2, my2 - bh / 2 + u2 * 0.04
        dr.rounded_rectangle([x + w2 * 0.24, y - u2 * 0.10, x + w2 * 0.54, y + u2 * 0.02],
                             radius=u2 * 0.045, fill=(247, 249, 252),
                             outline=(20, 22, 26), width=max(2, int(u2 * 0.055)))
        dr.rounded_rectangle([x, y, x + w2, y + bh], radius=u2 * 0.09, fill=(247, 249, 252),
                             outline=(20, 22, 26), width=max(2, int(u2 * 0.055)))
        rr = bh * 0.31
        dr.ellipse([mx2 - rr, y + bh / 2 - rr, mx2 + rr, y + bh / 2 + rr],
                   fill=(201, 210, 222), outline=(20, 22, 26), width=max(2, int(u2 * 0.055)))
        rr = bh * 0.15
        dr.ellipse([mx2 - rr, y + bh / 2 - rr, mx2 + rr, y + bh / 2 + rr], fill=(20, 22, 26))
        rr = u2 * 0.035
        dr.ellipse([x + w2 * 0.13 - rr, y + bh * 0.26 - rr,
                    x + w2 * 0.13 + rr, y + bh * 0.26 + rr], fill=(20, 22, 26))
        rr = u * 0.075
        dr.ellipse([mx2 - rr, my2 + u * 0.40 - rr, mx2 + rr, my2 + u * 0.40 + rr],
                   fill=(216, 50, 43), outline=(15, 17, 20), width=2)
    else:
        txt = {"reset": "L", "exit": "X"}.get(lb, lb)
        col = {"reset": (232, 96, 127), "exit": (224, 90, 82)}.get(lb, (242, 244, 248))
        f = font(u * (0.66 if lb == "reset" else 0.60))
        for ox in (-2, 0, 2):
            for oy in (-2, 0, 2):
                dr.text((mx2 + ox, my2 + oy), txt, font=f, fill=(20, 22, 26), anchor="mm")
        dr.text((mx2, my2), txt, font=f, fill=col, anchor="mm")

# ── 판독창 ────────────────────────────────────────────────────────────
ro = box(d["readout"])
hh = ro[3] - ro[1]
vgrad(ro[0], ro[1], ro[2], ro[3], [(0, (42, 46, 53)), (1, (21, 24, 28))])
dr.rounded_rectangle(ro, radius=hh * 0.14, outline=(15, 17, 20), width=max(2, int(hh * 0.06)))
dr.rounded_rectangle(ro, radius=hh * 0.14, outline=(214, 222, 234, 140),
                     width=max(1, int(hh * 0.022)))
sysv = d["sys"] or {}
for i, (lb, key) in enumerate((("수구수", "start"), ("1쿠션", "first"), ("3쿠션", "third"))):
    v = sysv.get(key)
    cx2 = ro[0] + (ro[2] - ro[0]) * (i + 0.5) / 3
    dr.text((cx2, ro[1] + hh * 0.10), lb, font=font(hh * 0.24),
            fill=(214, 222, 234, 190), anchor="ma")
    dr.text((cx2, ro[1] + hh * 0.95), "—" if v is None else str(round(v)),
            font=font(hh * 0.50), fill=(244, 247, 251), anchor="ms")
    if i < 2:
        xx = ro[0] + (ro[2] - ro[0]) * (i + 1) / 3
        dr.line([xx, ro[1] + hh * 0.18, xx, ro[1] + hh * 0.82],
                fill=(214, 222, 234, 80), width=2)

# ── 제품명 ────────────────────────────────────────────────────────────
P = d["panel"]
top = min(b["y"] for b in d["btn"] if b["x"] >= P["x"]) * K
room = top - P["y"] * K
fs = min(room / 4.2, P["w"] * K * 0.15)
for i, t in enumerate(["BILLIARDS", "ASSISTANT", "SYSTEM"]):
    dr.text((P["x"] * K + P["w"] * K / 2, P["y"] * K + room * 0.60 + (i - 1) * fs * 1.16),
            t, font=font(fs, italic=True), fill=(236, 241, 249, 235), anchor="mm")

out = ROOT / "peek" / "mock_dark.png"
im.save(out)
print(f"저장 {out}  {im.size}")
