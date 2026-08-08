"""pygame 당구대 화면 — 당구대 · 다이아몬드 · 파이브앤하프 번호표 · 공 클릭 배치.

조작 (모바일 기준 — 전부 화면 버튼)
    색 버튼 → 다이 누르기    그 자리에 그 공을 놓는다
    끌기                     이미 놓인 공을 잡아서 옮긴다
    수구변경 버튼            흰공 ↔ 노란공
    R 버튼                   공 전부 지우기
    N          파이브앤하프 번호표 표시 on/off
    D          다이아몬드 인덱스 표시 on/off
    R          공 전부 지우기
    ESC        종료
"""

from __future__ import annotations

import math
from pathlib import Path

import pygame

from core import five_half
from core.english import EnglishSpec
from core.table import BOTTOM, LEFT, RAILS, RIGHT, TOP, Table

WINDOW_SIZE = (1440, 940)
FPS = 60

BG = (24, 26, 30)
RAIL_FACE = (150, 112, 62)
RAIL_EDGE = (92, 66, 34)
CLOTH = (38, 74, 190)
CUSHION = (30, 60, 158)         # 천 덮인 쿠션 (플레이 면보다 살짝 어둡게)
CLOTH_EDGE = (14, 40, 120)
DIAMOND = (242, 238, 224)
TEXT = (232, 232, 238)
TEXT_DIM = (146, 149, 158)
INDEX_TEXT = (120, 124, 134)

FRAME_LINE = (255, 255, 255, 70)   # 프레임 포인트를 잇는 선
# ★ 2026-08-08 부터 모든 화면 기준은 **모바일**이다 (사용자 확정).
#   당구대가 화면을 가득 채우고, 설명 글씨는 두지 않는다. 작은 글씨는 폰에서
#   어차피 안 보인다. 눈금 숫자는 레일 위에 얹고, 당점·버튼은 다이 안으로 넣는다.
MARGIN = 6
PAD_TOP = 0
PAD_BOTTOM = 0
PAD_SIDE = 0
INFO_H = 0

CLOCK_R = 58                    # 당점 시계판 반지름 (px)
CLOCK_BALL = (240, 240, 234)
CLOCK_RING = (168, 170, 180)
CLOCK_AXIS = (120, 122, 132)
CLOCK_MARK = (222, 52, 44)

PATH_AIM = (250, 250, 250)      # 수구 -> 1쿠션
PATH_1_2 = (255, 214, 0)        # 1쿠션 -> 2쿠션
PATH_2_3 = (110, 235, 90)       # 2쿠션 -> 3쿠션
PATH_AFTER = (235, 240, 250)    # 3쿠션 이후 — 적구로 가는 선 (공식의 일부)
PATH_HIT = (255, 120, 190)      # 적구를 맞히는 경우
PATH_FAIL = (220, 80, 70)
PATH_REAL = (90, 190, 255)      # 실측 반사표로 굴린 실제 경로

BALL_CUE = ("cue", "수구", (246, 245, 238))
BALL_OBJ1 = ("obj1", "적구1", (240, 190, 40))
BALL_OBJ2 = ("obj2", "적구2", (214, 52, 44))
BALLS = (BALL_CUE, BALL_OBJ1, BALL_OBJ2)

# 검출된 공 색 이름 → 화면에 그릴 색. 역할이 아니라 **실제 공 색**을 따라간다.
BALL_TONE = {"white": BALL_CUE[2], "yellow": BALL_OBJ1[2], "red": BALL_OBJ2[2]}


def _font(size: int, bold: bool = False) -> pygame.font.Font:
    path = pygame.font.match_font("malgungothic,malgun gothic,gulim,dotum,batang")
    font = pygame.font.Font(path, size) if path else pygame.font.SysFont(None, size)
    font.set_bold(bold)
    return font


def _point_to_segment(p, a, b) -> float:
    """점에서 선분까지 거리 (mm)."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    t = 0.0 if ll < 1e-9 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ll))
    return float(((px - ax - dx * t) ** 2 + (py - ay - dy * t) ** 2) ** 0.5)


def _outlined(font: pygame.font.Font, text: str, color, outline=(16, 16, 20)):
    """검은 테두리를 두른 글자 표면 (7.jpg 표기 스타일)."""
    base = font.render(text, True, color)
    w, h = base.get_size()
    surf = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
    edge = font.render(text, True, outline)
    for dx, dy in ((0, 0), (4, 0), (0, 4), (4, 4), (2, 0), (0, 2), (4, 2), (2, 4)):
        surf.blit(edge, (dx, dy))
    surf.blit(base, (2, 2))
    return surf


class Layout:
    """mm 좌표 ↔ 화면 픽셀 변환."""

    def __init__(self, table: Table, surface_size: tuple[int, int]):
        w, h = surface_size
        self.table = table

        total_mm_w = table.outer_width      # 실제 당구대 전체 크기
        total_mm_h = table.outer_height

        avail_w = max(w - 2 * MARGIN - 2 * PAD_SIDE, 1)
        avail_h = max(h - INFO_H - 2 * MARGIN - PAD_TOP - PAD_BOTTOM, 1)
        self.scale = min(avail_w / total_mm_w, avail_h / total_mm_h)

        rail_w = total_mm_w * self.scale
        rail_h = total_mm_h * self.scale
        rail_left = (w - rail_w) / 2
        rail_top = MARGIN + PAD_TOP + (avail_h - rail_h) / 2

        self.rail_rect = pygame.Rect(round(rail_left), round(rail_top), round(rail_w), round(rail_h))

        pad_x = table.rail_x * self.scale       # 장쿠션 방향 레일 두께 (px)
        pad_y = table.rail_y * self.scale       # 단쿠션 방향 레일 두께 (px)
        self.rail_px = max(pad_x, pad_y)

        self.cloth_rect = pygame.Rect(
            round(rail_left + pad_x),
            round(rail_top + pad_y),
            round(table.width * self.scale),
            round(table.height * self.scale),
        )
        # 쿠션(천) 바깥 경계 = 노즈에서 cushion_width 만큼 바깥
        cw = table.cushion_width * self.scale
        self.cushion_rect = self.cloth_rect.inflate(round(cw * 2), round(cw * 2))

        self.ox = rail_left + pad_x
        self.oy = rail_top + pad_y + table.height * self.scale

    def to_px(self, x: float, y: float) -> tuple[float, float]:
        return (self.ox + x * self.scale, self.oy - y * self.scale)

    def to_mm(self, px: float, py: float) -> tuple[float, float]:
        return ((px - self.ox) / self.scale, (self.oy - py) / self.scale)

    @property
    def ball_radius_px(self) -> int:
        return max(4, round(self.table.ball_diameter / 2 * self.scale))


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("파이브앤하프 계산기 — 번호표 검증")

        self.table = Table.load()
        self.scales = five_half.load_scales()
        self.english_spec = EnglishSpec.load()
        self.side_manual: bool | None = None   # None = 진행방향 자동 / True = 좌 / False = 우
        self.screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        self.f_tiny = _font(13)
        self.f_num = _font(17, bold=True)
        self.f_info = _font(16)
        self.f_title = _font(17, bold=True)
        self.f_start = _font(25, bold=True)   # 수구수·1쿠션수 (2단계 크게)
        self.f_third = _font(21, bold=True)   # 3쿠션수 (1단계 크게)

        self.positions: dict[str, tuple[float, float]] = {}
        # 역할(수구/적구1/적구2) → 그 자리에 있는 공의 색.
        # 수구를 바꾸면 위치와 색을 같이 바꿔서 화면이 실제 공과 맞게 한다.
        self.ball_color: dict[str, tuple[int, int, int]] = {k: c for k, _, c in BALLS}
        self.mouse_mm: tuple[float, float] | None = None
        self.show_numbers = True
        self.show_index = False
        self.frozen_aim: tuple[float, float] | None = None   # SPACE 로 조준 고정
        self.dragging: str | None = None                     # 지금 잡아 끄는 공
        # 현장 보정 — 2쿠션 접점을 진행 방향으로 몇 포인트 밀 것인가.
        # 다이를 청소하면 각이 길어지는 등 당구대 상태로 달라지는 몫이다.
        # 기준값(실측 반사표)은 손대지 않는다. 0 버튼을 누를 때까지 유지된다.
        self.correction: float = 0.0
        self.buttons: list[tuple[pygame.Rect, str]] = []
        # 공 배치 — 색 버튼을 누른 뒤 다이를 누르면 그 자리에 그 공이 놓인다.
        self.place_mode: str | None = None      # white / yellow / red
        self.cue_is_white: bool = True          # 수구가 흰공인가 (누르면 노란공)
        self.aim: tuple[float, float] | None = None   # 프레임 위 조준점 (탭해서 정한다)
        self.aiming = False                           # 프레임을 잡고 끄는 중인가
        self.last_aim: tuple[float, float] | None = None   # R 로 되살릴 조준점
        # R 버튼 — 누를 때마다 하는 일이 바뀐다 (사용자 확정)
        #   0 궤적만 지우기 → 1 모두 지우기 → 2 모두 복원 → 다시 0
        self.r_mode = 0
        self.backup: dict | None = None
        self.shot: five_half.Shot | None = None
        self.capture_path: str | None = None                 # 마지막으로 읽은 캡처
        self.capture_note = ""
        self._band: pygame.Surface | None = None             # 공 두께 궤적용 반투명 레이어
        self.running = True

    def band_surface(self) -> pygame.Surface:
        """공 두께 궤적을 그릴 반투명 레이어 (화면 크기 바뀌면 새로 만든다)."""
        size = self.screen.get_size()
        if self._band is None or self._band.get_size() != size:
            self._band = pygame.Surface(size, pygame.SRCALPHA)
        self._band.fill((0, 0, 0, 0))
        return self._band

    # -------------------------------------------------------------- 캡처

    def _note(self, text: str) -> None:
        """안내문. 화면 설명칸을 없앴으므로 콘솔에도 남긴다 (원인 추적용)."""
        self.capture_note = text
        print(f"[안내] {text}", flush=True)

    def load_capture(self, path: str) -> None:
        """사진 한 장 → 원근보정 → 공 위치 자동 배치 (로드맵 0.5단계).

        OpenCV 는 이 기능에서만 쓴다. 없으면 나머지는 그대로 돌아간다.
        """
        self.capture_path = path
        try:
            import cv2

            from vision import ball_detect, cue_detect, table_detect
        except ImportError as e:
            self._note(f"OpenCV 없음 ({e})")
            return

        try:
            import numpy as _np
            # ⚠️ cv2.imread 는 윈도우에서 한글 경로를 못 읽는다. 바이트로 읽어 디코드한다.
            image = cv2.imdecode(_np.fromfile(path, dtype=_np.uint8), cv2.IMREAD_COLOR)
            top = table_detect.detect(image)
            balls = ball_detect.resolve(ball_detect.detect(
                top.image, None, top.size[0] / self.table.width * self.table.ball_diameter))
            aimed = cue_detect.find_aimed_ball(image, top, balls)
        except Exception as e:                       # 검출 실패는 앱을 죽이지 않는다
            self._note(f"검출 실패: {e}")
            return

        found = ball_detect.assign(balls, aimed)
        if not found:
            self._note(f"공을 못 찾음 (덩어리 {len(balls)}개)")
            return

        # ⚠️ 사진을 읽어와도 궤적은 만들지 않는다 (사용자 확정). 공만 놓고
        #    조준은 사람이 프레임을 눌러 정한다.
        self.positions.clear()
        self.ball_color = {}
        self.aim = None
        self.frozen_aim = None
        for key, ball in found.items():
            x, y = top.to_mm(ball.nx, ball.ny, self.table.width, self.table.height)
            self.positions[key] = self.table.clamp_ball_center(x, y)
            self.ball_color[key] = BALL_TONE.get(ball.name, BALL_CUE[2])

        how = f"큐대 겨냥 → {aimed.label}" if aimed else "큐대 없음 → 흰공"
        self._note(f"{Path(path).name}  공 {len(found)}개  "
                   f"{'수구 있음' if BALL_CUE[0] in found else '★수구 없음'}  {how}")
        self.capture_note = (f"{Path(path).name}  비율 {top.aspect:.3f}  "
                             f"공 {len(found)}개  수구: {how}")

    def swap_cue(self, other: str) -> None:
        """수구를 다른 공과 맞바꾼다. 색도 같이 바꿔서 화면이 실제와 맞게 한다.

        3구는 흰공·노란공 중 어느 쪽이 내 수구인지 사진만으로 알 수 없다.
        그래서 사용자가 직접 고를 수 있어야 한다.

        ⚠️ 적색공은 무조건 적구다. 수구가 될 수 없다 (사용자 확정).
        """
        cue = BALL_CUE[0]
        if other == cue or self.ball_color.get(other) == BALL_OBJ2[2]:
            return
        # ⚠️ 한 칸씩 옮기면 안 된다. 한쪽만 놓여 있을 때 방금 넣은 값을 바로
        #    다시 지워버린다. 두 값을 먼저 빼놓고 통째로 맞바꾼다.
        for table in (self.positions, self.ball_color):
            a, b = table.pop(cue, None), table.pop(other, None)
            if b is not None:
                table[cue] = b
            if a is not None:
                table[other] = a

    # -------------------------------------------------------------- 당점

    @property
    def english(self):
        """현재 당점. 팁수는 고정이고 좌/우 방향만 바뀐다 (사용자 확정).

        기본 2시 30분 3팁(우회전). 공이 왼쪽으로 진행하면 9시 30분 3팁(좌회전).
        """
        left = self.going_left if self.side_manual is None else self.side_manual
        return self.english_spec.for_side(left)

    @property
    def hit_ball(self) -> tuple[str, float] | None:
        """3쿠션 이후 **실측 궤적**이 맞히는 적구 — (이름, 중심까지 거리 mm).

        ⚠️ 파이브앤하프 공식 경로가 아니라 실측 경로로 판정한다. 공식 경로는
           3쿠션에서 281mm 벗어나 맞고 안 맞고가 뒤집힌다 (130샷 채점).
        """
        s = self.shot
        if s is None or len(s.real_path) < 5:          # 3쿠션 뒤 구간이 있어야 한다
            return None
        d = self.table.ball_diameter
        best = None
        for key, name, _ in (BALL_OBJ1, BALL_OBJ2):
            pos = self.positions.get(key)
            if pos is None:
                continue
            for a, b in zip(s.real_path[3:], s.real_path[4:]):
                dist = _point_to_segment(pos, a, b)
                if dist < d and (best is None or dist < best[1]):
                    best = (name, dist)
        return best

    @property
    def going_left(self) -> bool:
        """수구가 1쿠션을 향해 왼쪽으로 진행하는가.

        ⚠️ 옛 파이브앤하프 경로(p1)가 아니라 **실측 궤적**의 첫 구간으로 본다.
           화면에 그리는 궤적이 실측 쪽이니 당점도 그것을 따라가야 한다
           (사용자 지적: 궤적에 따라 당점이 바뀌어야 한다).
        """
        s = self.shot
        if s is None or len(s.real_path) < 2:
            return False
        return s.real_path[1][0] < s.real_path[0][0]

    # -------------------------------------------------------------- 계산

    def update_shot(self, cursor_mm: tuple[float, float]) -> None:
        """수구 + 조준점 → 경로 계산.

        ⚠️ 마우스를 따라 자동으로 그리지 않는다 (사용자 확정). 수구를 놓은 뒤
           **프레임을 눌러야** 그때 궤적이 생긴다. 프레임을 다시 누르거나 끌면
           조준점이 따라 움직인다. 폰에서 손가락이 지나갈 때마다 궤적이
           춤추면 못 쓴다.
        """
        cue = self.positions.get(BALL_CUE[0])
        target = self.aim
        if cue is None or target is None:
            self.shot = None
            return
        p1 = five_half.aim_first_cushion(self.table, cue, target)
        self.shot = (five_half.solve(self.table, self.scales, cue, p1,
                                     second_shift=self.correction) if p1 else None)

    # ------------------------------------------------------------- 이벤트

    def handle_event(self, event, layout: Layout) -> None:
        if event.type == pygame.QUIT:
            self.running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_r:
                self.positions.clear()
            elif event.key == pygame.K_n:
                self.show_numbers = not self.show_numbers
            elif event.key == pygame.K_d:
                self.show_index = not self.show_index
            elif event.key == pygame.K_SPACE:
                pass                    # 조준은 프레임 탭으로만 정한다
            elif event.key == pygame.K_t:
                self.side_manual = None             # 진행방향 자동으로 되돌림
            elif event.key == pygame.K_l and self.capture_path:
                self.load_capture(self.capture_path)        # 캡처 다시 읽기
            elif event.key == pygame.K_2:
                self.swap_cue(BALL_OBJ1[0])                 # 흰공 ↔ 노란공 (적색공은 제외)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.hit_button(event.pos):
                return
            if event.button == 1 and self.set_english_from_click(event.pos):
                return
            # 이미 놓인 공을 집었으면 옮기기로 들어간다. 새로 놓는 것보다 우선한다 —
            # 안 그러면 공을 미세조정하려 할 때마다 엉뚱한 자리에 다시 놓게 된다.
            grabbed = self.ball_at(layout, event.pos)
            if grabbed is not None:
                self.dragging = grabbed
                return
            if self.place_mode:                      # 색 버튼을 눌러둔 상태면 그 공을 놓는다
                x, y = layout.to_mm(*event.pos)
                if self.table.contains(x, y):
                    self.positions[self.role_of(self.place_mode)] =                         self.table.clamp_ball_center(x, y)
                    self.ball_color[self.role_of(self.place_mode)] =                         BALL_TONE[self.place_mode]
                    self.place_mode = None
                return
            # 프레임을 누르면 그 자리가 조준점이 되고, 잡고 끌면 따라온다.
            f = self.frame_at(layout, event.pos)
            if f is not None:
                self.aim = self.last_aim = f
                self.aiming = True
            # ⚠️ 예전에는 좌클릭=수구 / 우클릭=적구1 / 휠클릭=적구2 로 놓았는데
            #    없앴다 (사용자 확정). 폰에는 우클릭도 휠클릭도 없다.
            #    공은 **색 버튼을 누른 뒤 다이를 눌러서** 놓는다.

        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = None
            self.aiming = False

        elif event.type == pygame.MOUSEMOTION and self.aiming:
            f = self.frame_at(layout, event.pos)
            if f is not None:
                self.aim = self.last_aim = f

        elif event.type == pygame.MOUSEMOTION and self.dragging:
            x, y = layout.to_mm(*event.pos)
            # ⚠️ 궤적을 지우지 않는다 (사용자 확정). 조준점은 프레임에 그대로 두고
            #    수구가 움직이면 경로만 다시 계산돼 따라온다.
            self.positions[self.dragging] = self.table.clamp_ball_center(x, y)

    def frame_at(self, layout: Layout, pos) -> tuple[float, float] | None:
        """누른 자리가 프레임(레일 나무 부분)이면 그 위의 조준점 (mm).

        천 안쪽이면 None. 천 바깥이면 가장 가까운 프레임 선으로 끌어당긴다.
        """
        if layout.cloth_rect.collidepoint(pos) or not layout.rail_rect.collidepoint(pos):
            return None
        t = self.table
        x, y = layout.to_mm(*pos)
        off = t.frame_offset
        # 네 프레임 선 중 가장 가까운 곳으로
        cand = [(abs(y - (t.height + off)), (min(max(x, 0), t.width), t.height + off)),
                (abs(y + off), (min(max(x, 0), t.width), -off)),
                (abs(x + off), (-off, min(max(y, 0), t.height))),
                (abs(x - (t.width + off)), (t.width + off, min(max(y, 0), t.height)))]
        return min(cand)[1]

    R_LABELS = ("L", "A", "R")   # Line 만 / All 전부 / Restore 되돌리기

    def do_reset(self) -> None:
        """R 버튼 — 누를 때마다 하는 일이 바뀐다."""
        if self.r_mode == 0:                       # L — 궤적만
            self.aim = None
        elif self.r_mode == 1:                     # A — 전부 (되돌릴 수 있게 담아둔다)
            self.backup = {"pos": dict(self.positions),
                           "col": dict(self.ball_color), "aim": self.last_aim}
            self.positions.clear()
            self.aim = None
        elif self.backup:                          # R — 되돌리기 (궤적도 같이)
            self.positions.update(self.backup["pos"])
            self.ball_color.update(self.backup["col"])
            self.aim = self.backup["aim"]
        self.place_mode = None
        self.r_mode = (self.r_mode + 1) % 3

    def role_of(self, color: str) -> str:
        """공 색 → 역할. 수구가 흰공이냐 노란공이냐에 따라 갈린다."""
        if color == "red":
            return BALL_OBJ2[0]
        cue_color = "white" if self.cue_is_white else "yellow"
        return BALL_CUE[0] if color == cue_color else BALL_OBJ1[0]

    def ball_at(self, layout: Layout, pos) -> str | None:
        """그 자리에 놓인 공이 있으면 그 역할 이름. 여러 개면 위에 그려진 것부터."""
        r = layout.ball_radius_px + 4
        for key in reversed([k for k, _, _ in BALLS]):
            p = self.positions.get(key)
            if p is None:
                continue
            px, py = layout.to_px(*p)
            if (px - pos[0]) ** 2 + (py - pos[1]) ** 2 <= r * r:
                return key
        return None

    # ------------------------------------------------------------- 렌더링

    def draw_table(self, layout: Layout) -> None:
        # 나무 레일 -> 천 덮인 쿠션 -> 플레이 면
        pygame.draw.rect(self.screen, RAIL_FACE, layout.rail_rect, border_radius=6)
        pygame.draw.rect(self.screen, RAIL_EDGE, layout.rail_rect, width=2, border_radius=6)
        pygame.draw.rect(self.screen, CUSHION, layout.cushion_rect)
        pygame.draw.rect(self.screen, CLOTH_EDGE, layout.cushion_rect, width=2)
        pygame.draw.rect(self.screen, CLOTH, layout.cloth_rect)
        pygame.draw.rect(self.screen, CLOTH_EDGE, layout.cloth_rect, width=2)

    def draw_diamonds(self, layout: Layout) -> None:
        """프레임 포인트(레일 위 흰 점)를 실제 좌표에 찍는다. 계산 기준선이다."""
        t = self.table

        # 프레임 포인트를 잇는 사각형 — 파이브앤하프 계산이 일어나는 격자
        fx0, fy0 = layout.to_px(-t.frame_offset, -t.frame_offset)
        fx1, fy1 = layout.to_px(t.width + t.frame_offset, t.height + t.frame_offset)
        frame_rect = pygame.Rect(round(fx0), round(fy1), round(fx1 - fx0), round(fy0 - fy1))
        pygame.draw.rect(self.screen, (206, 196, 168), frame_rect, width=1)

        idx_off = {BOTTOM: (0, 16), TOP: (0, -16), LEFT: (-15, 0), RIGHT: (15, 0)}
        for rail in RAILS:
            lx, ly = idx_off[rail]
            for index, x, y in t.diamonds(rail):
                px, py = layout.to_px(x, y)
                c = (round(px), round(py))
                pygame.draw.circle(self.screen, DIAMOND, c, 4)
                pygame.draw.circle(self.screen, RAIL_EDGE, c, 4, 1)
                if self.show_index:
                    s = self.f_tiny.render(str(index), True, INDEX_TEXT)
                    self.screen.blit(s, s.get_rect(center=(px + lx, py + ly)))

    # 레일 바깥 방향 (화면 픽셀 기준). 번호는 늘 레일 바깥쪽에 적는다.
    _OUTWARD_PX = {BOTTOM: (0, 1), TOP: (0, -1), LEFT: (-1, 0), RIGHT: (1, 0)}

    def number_orientation(self) -> five_half.Orientation:
        """번호표를 어느 방향으로 접을 것인가.

        ⚠️ 궤적이 있을 때만 접으면 안 된다. 수구를 바꾸거나 옮기면 그 즉시
           번호표도 따라 뒤집혀야 한다 (사용자 지적: 노란공이 수구가 되어
           우측 상단에 있으면 그 모서리가 50 이어야 한다).
           그래서 조준 전에는 **수구가 어느 모서리에 있는지**로 정한다.
        """
        if self.shot is not None:
            return self.shot.orientation
        cue = self.positions.get(BALL_CUE[0])
        if cue is None:
            return five_half.Orientation()
        # 기준(7.jpg)은 수구수 50 이 우하단 코너다. 수구가 있는 모서리로 접는다.
        return five_half.Orientation(flip_x=cue[0] < self.table.width / 2,
                                     flip_y=cue[1] > self.table.height / 2)

    def draw_numbers(self, layout: Layout) -> None:
        """파이브앤하프 번호표. 수구 위치에 따라 좌우/상하가 통째로 뒤집힌다.

        번호표는 한 벌(7.jpg 기준)뿐이고, 좌표만 접어서 네 방향을 만든다.
        """
        # ★ 모바일 기준 — 숫자를 제자리(기준선) 위에 얹고 크게 쓴다.
        #   다이아몬드 흰 점을 덮어도 된다 (사용자 확정: 점 위치는 이미 다 안다).
        # ⚠️ 기준선을 헷갈리면 안 된다 (사용자 지적):
        #      수구수 · 1쿠션수 = **프레임** 포인트 (쿠션 날에서 90mm 바깥)
        #      3쿠션수         = **레일** (쿠션 날)
        #   하단에는 둘이 같이 오는데, 프레임과 날이 90mm 떨어져 있어 자연히 갈린다.
        #   3쿠션수만 살짝 바깥으로 밀어 천 위로 올라오지 않게 한다.
        o = self.number_orientation()
        for scale in self.scales.values():
            third = scale.name == five_half.THIRD_CUSHION
            font = self.f_third if third else self.f_start

            # 화면 좌표로 먼저 펼친다
            items = []
            for p in scale.points:
                x, y = scale.position(self.table, p.rail, p.index)   # 기준선 위 좌표
                x, y = o.apply(self.table, (x, y))                   # 화면 방향으로 접기
                ox, oy = self._OUTWARD_PX[o.rail(p.rail)]
                d = 15 if third else 0                               # 3쿠션수만 살짝 바깥
                px, py = layout.to_px(x, y)
                items.append([p.number, px + ox * d, py + oy * d, ox, oy])

            # ⚠️ 코너(똥창)에서는 두 레일의 눈금이 같은 번호로 겹친다 — 수구수 50 이
            #    하단 끝과 우측 끝에 각각 있어 50 이 두 번 보인다 (사용자 지적).
            #    같은 번호가 가까이 있으면 하나로 합쳐 **코너 대각선 바깥**에 찍는다.
            merged, used = [], set()
            for i, a in enumerate(items):
                if i in used:
                    continue
                same = [j for j in range(i + 1, len(items))
                        if j not in used and items[j][0] == a[0]
                        and math.hypot(items[j][1] - a[1], items[j][2] - a[2]) < 140]
                if same:
                    j = same[0]
                    used.add(j)
                    b = items[j]
                    merged.append((a[0], (a[1] + b[1]) / 2 + (a[3] + b[3]) * 8,
                                   (a[2] + b[2]) / 2 + (a[4] + b[4]) * 8))
                else:
                    merged.append((a[0], a[1], a[2]))

            for number, px, py in merged:
                surf = _outlined(font, f"{number:g}", scale.color)
                self.screen.blit(surf, surf.get_rect(center=(px, py)))

    def draw_path(self, layout: Layout) -> None:
        """실측 반사표로 굴린 공 궤적.

        ⚠️ 예전에는 파이브앤하프 공식(수구수 − 1쿠션수 = 3쿠션수)으로 계산한 경로도
           같이 그렸는데, 130샷으로 채점하니 3쿠션에서 281mm 벗어났다 (실측표는
           71mm). 사용자가 영상으로 확인한 결과도 실측 쪽이 맞았다. 그래서 공식
           경로는 지우고 **실측 경로 하나만** 그린다. 번호(수구수·1쿠션수)는 읽기용
           으로 그대로 둔다.
        """
        shot = self.shot
        if shot is None or not shot.real_path or len(shot.real_path) < 2:
            return

        band = self.band_surface()
        band_w = max(3, round(self.table.ball_diameter * layout.scale))

        def seg(a, b, color, width=3, thick=False):
            pa, pb = layout.to_px(*a), layout.to_px(*b)
            if thick:
                pygame.draw.line(band, (*color, 70), pa, pb, band_w)
                r = band_w // 2
                for q in (pa, pb):                     # 꺾이는 곳을 둥글게 이어준다
                    pygame.draw.circle(band, (*color, 70), (round(q[0]), round(q[1])), r)
            else:
                pygame.draw.line(self.screen, color, pa, pb, width)

        # 구간 색 — 수구→1쿠션, 1→2, 2→3, 그 뒤
        end_color = PATH_HIT if self.hit_ball else PATH_AFTER
        colors = [PATH_AIM, PATH_1_2, PATH_2_3, end_color, end_color, end_color, end_color]

        # 그리는 것은 **공 중심**의 자취다. 접점은 쿠션 날 위에 있으므로 반지름만큼
        # 안쪽으로 밀어야 띠가 쿠션을 파고들지 않는다.
        pts = [self.table.clamp_ball_center(*p) for p in shot.real_path]
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            seg(a, b, colors[min(i, len(colors) - 1)], thick=True)
        self.screen.blit(band, (0, 0))
        for i, (a, b) in enumerate(zip(pts, pts[1:])):     # 중심선을 띠 위에 다시
            seg(a, b, colors[min(i, len(colors) - 1)])

        # 쿠션 접점 — 쿠션 날 위의 원래 자리에 찍는다 (중심 자취가 아니라 접점)
        for i, p in enumerate(shot.real_path[1:], start=1):
            px, py = layout.to_px(*p)
            col = colors[min(i, len(colors) - 1)]
            pygame.draw.circle(self.screen, col, (round(px), round(py)), 7)
            pygame.draw.circle(self.screen, (20, 20, 24), (round(px), round(py)), 7, 2)

    # ------------------------------------------------------------ 보정 버튼

    BTN_W, BTN_H, BTN_GAP = 62, 62, 10
    STEP = 0.5          # 버튼 한 번에 움직이는 눈금 (1 눈금 = 30.6mm)
    ROW_GAP = 14        # 보정 줄 ↔ 공 배치 줄 사이
    GROUP_GAP = 22      # 수구변경(1번) 과 색 버튼(2·3·4) 사이 구분

    def button_rects(self, layout: Layout) -> list[tuple[pygame.Rect, str]]:
        """+ / 0 / − 버튼 자리. 공·궤적을 피해 네 귀퉁이 중 빈 곳에 놓는다.

        ⚠️ 모바일에서는 키보드가 없다. 처음부터 버튼으로 만들어 둔다 (사용자 방침).
        """
        w = self.BTN_W * 5 + self.BTN_GAP * 4 + self.GROUP_GAP
        h = self.BTN_H * 2 + self.ROW_GAP
        pad = 14
        cr = layout.cloth_rect
        spots = [(cr.right - pad - w, cr.bottom - pad - h),     # 우하
                 (cr.left + pad, cr.bottom - pad - h),          # 좌하
                 (cr.right - pad - w, cr.top + pad),            # 우상
                 (cr.left + pad, cr.top + pad)]                 # 좌상

        busy = []
        for p in self.positions.values():
            px, py = layout.to_px(*p)
            r = layout.ball_radius_px + 6
            busy.append(pygame.Rect(px - r, py - r, r * 2, r * 2))
        # ⚠️ 궤적은 덮어도 된다 (사용자 확정). **공만** 피한다.
        #    당점 그림도 피한다 — 자리가 밀리면 보정표가 가려진다.
        cx, cy = self.clock_center()
        busy.append(pygame.Rect(cx - CLOCK_R - 8, cy - CLOCK_R - 8,
                                CLOCK_R * 2 + 16, CLOCK_R * 2 + 16))

        best = spots[0]
        for x, y in spots:
            box = pygame.Rect(x, y, w, h)
            if not any(box.colliderect(b) for b in busy):
                best = (x, y)
                break
        x, y = best
        out = []
        for i, label in enumerate(("-", "0", "+", "cam")):        # 윗줄 — 보정
            out.append((pygame.Rect(x + i * (self.BTN_W + self.BTN_GAP), y,
                                    self.BTN_W, self.BTN_H), label))
        y2 = y + self.BTN_H + self.ROW_GAP                        # 아랫줄 — 공 배치
        for i, label in enumerate(("swap", "white", "yellow", "red", "reset")):
            gap = self.GROUP_GAP if i >= 1 else 0                 # 수구변경만 살짝 떼어놓는다
            out.append((pygame.Rect(x + i * (self.BTN_W + self.BTN_GAP) + gap, y2,
                                    self.BTN_W, self.BTN_H), label))
        return out

    def hit_button(self, pos) -> bool:
        for rect, label in self.buttons:
            if rect.collidepoint(pos):
                if label == "+":
                    self.correction += self.STEP
                elif label == "-":
                    self.correction -= self.STEP
                elif label == "cam":
                    self.shoot_photo()
                elif label == "swap":
                    self.cue_is_white = not self.cue_is_white
                    self.swap_cue(BALL_OBJ1[0])          # 수구 자리와 색을 같이 바꾼다
                elif label in ("white", "yellow", "red"):
                    # 한 번 더 누르면 해제 (실수로 놓는 것을 막는다)
                    self.place_mode = None if self.place_mode == label else label
                elif label == "reset":
                    self.do_reset()
                else:
                    self.correction = 0.0
                return True
        return False

    def draw_buttons(self, layout: Layout) -> None:
        """[−] [값] [+]  — 버튼 모양은 그대로 두고 **숫자 색**으로 방향을 알린다.

        ⚠️ 부호(+/−)를 숫자에 붙이면 글자가 작아져 모바일에서 안 보인다 (사용자 지적).
           긴각 = 흰색, 짧은각 = 핑크. 가운데 버튼이 현재 보정값이자 리셋이다.
        """
        self.buttons = self.button_rects(layout)
        big = _font(34, bold=True)
        for rect, label in self.buttons:
            pygame.draw.rect(self.screen, (44, 48, 56), rect, border_radius=10)
            pygame.draw.rect(self.screen, (188, 196, 210), rect, width=2, border_radius=10)
            if label == "cam":
                self.draw_camera_icon(rect)
                continue
            if label in ("swap", "white", "yellow", "red", "reset"):
                self.draw_place_button(rect, label)
                continue
            if label == "0":
                ink = ((246, 248, 252) if self.correction > 0 else
                       PATH_HIT if self.correction < 0 else (150, 156, 166))
                text = f"{abs(self.correction):g}"
            else:
                ink, text = (222, 228, 238), label
            surf = big.render(text, True, ink)
            self.screen.blit(surf, surf.get_rect(center=rect.center))

    # 데스크톱 시험용 사진 — 모바일에서는 이 자리에 카메라가 붙는다.
    # 어제(2026-08-07) 당구장에서 찍은 것 중 검출이 되는 것들.
    TEST_PHOTOS = ["20260807_193227", "20260807_194043", "20260807_194516",
                   "20260807_194930", "20260807_195527", "20260807_200236"]
    _photo_i = 0

    def shoot_photo(self) -> None:
        """카메라 버튼. 모바일에서는 촬영 → 이 화면으로 돌아와 공을 배치한다.

        지금(데스크톱)은 촬영 대신 어제 찍은 사진을 하나씩 돌려가며 읽는다.
        """
        from pathlib import Path as _P
        folder = _P(r"C:\DSLINE\영상편집 당구")
        for _ in range(len(self.TEST_PHOTOS)):
            name = self.TEST_PHOTOS[self._photo_i % len(self.TEST_PHOTOS)]
            self._photo_i += 1
            f = folder / f"{name}.jpg"
            if f.exists():
                self.load_capture(str(f))
                return
        self._note("시험용 사진을 못 찾았습니다")

    def draw_place_button(self, rect: pygame.Rect, label: str) -> None:
        """공 배치 줄 — 수구변경 / 흰공 / 노란공 / 빨간공 / 리셋."""
        armed = self.place_mode == label
        pygame.draw.rect(self.screen, (60, 96, 150) if armed else (44, 48, 56),
                         rect, border_radius=10)
        pygame.draw.rect(self.screen, (255, 236, 150) if armed else (188, 196, 210),
                         rect, width=3 if armed else 2, border_radius=10)
        cx, cy = rect.center
        r = int(rect.h * 0.28)

        if label == "reset":
            surf = _font(20, bold=True).render(self.R_LABELS[self.r_mode], True,
                                               (232, 150, 140))
            self.screen.blit(surf, surf.get_rect(center=(cx, cy)))
            return

        if label == "swap":
            # 지금 수구인 색을 보여준다. 누르면 흰공 ↔ 노란공 으로 뒤집힌다.
            tone = BALL_CUE[2] if self.cue_is_white else BALL_OBJ1[2]
            pygame.draw.circle(self.screen, tone, (cx, cy), r)
            pygame.draw.circle(self.screen, (255, 236, 150), (cx, cy), r + 5, 3)
            return

        pygame.draw.circle(self.screen, BALL_TONE[label], (cx, cy), r)
        pygame.draw.circle(self.screen, (28, 30, 36), (cx, cy), r, 2)
        if label == ("white" if self.cue_is_white else "yellow"):
            pygame.draw.circle(self.screen, (255, 236, 150), (cx, cy), r + 5, 2)

    def draw_camera_icon(self, rect: pygame.Rect) -> None:
        """카메라 그림 — 글꼴 이모지는 안 나오는 환경이 있어 직접 그린다."""
        cx, cy = rect.center
        w, h = int(rect.w * 0.56), int(rect.h * 0.40)
        body = pygame.Rect(0, 0, w, h)
        body.center = (cx, cy + 3)
        hump = pygame.Rect(0, 0, int(w * 0.34), int(h * 0.30))
        hump.midbottom = (cx - int(w * 0.16), body.top + 2)
        pygame.draw.rect(self.screen, (222, 228, 238), hump, border_radius=3)
        pygame.draw.rect(self.screen, (222, 228, 238), body, border_radius=5)
        pygame.draw.circle(self.screen, (44, 48, 56), (cx, body.centery), int(h * 0.30))
        pygame.draw.circle(self.screen, (222, 228, 238), (cx, body.centery),
                           int(h * 0.30), 2)

    def draw_balls(self, layout: Layout) -> None:
        r = layout.ball_radius_px
        for key, _name, _default in BALLS:
            pos = self.positions.get(key)
            if pos is None:
                continue
            px, py = layout.to_px(*pos)
            c = (round(px), round(py))
            pygame.draw.circle(self.screen, self.ball_color.get(key, _default), c, r)
            pygame.draw.circle(self.screen, (20, 20, 24), c, r, 2)
            if key == BALL_CUE[0]:                     # 수구 표시
                pygame.draw.circle(self.screen, (255, 255, 255), c, r + 5, 2)

    # ------------------------------------------------------------ 당점 시계판

    def clock_center(self) -> tuple[int, int]:
        """당점 시계판 자리 — 다이 안쪽 좌상단 (모바일 기준)."""
        r = Layout(self.table, self.screen.get_size()).cloth_rect
        return (r.right - CLOCK_R - 18, r.centery)

    def draw_english(self) -> None:
        """당점(잉글리시) 시계판. 8.jpg 의 그림과 같은 형태."""
        cx, cy = self.clock_center()
        spec = self.english_spec
        safe = CLOCK_R * spec.safe_radius_ratio

        pygame.draw.circle(self.screen, CLOCK_BALL, (cx, cy), CLOCK_R)
        pygame.draw.circle(self.screen, (60, 62, 70), (cx, cy), CLOCK_R, 2)

        # 팁 링 (1팁 ~ 맥시멈)
        for t in range(1, int(spec.max_tips) + 1):
            pygame.draw.circle(self.screen, CLOCK_RING, (cx, cy),
                               round(safe * t / spec.max_tips), 1)
        # 12/3/6/9 축
        pygame.draw.line(self.screen, CLOCK_AXIS, (cx - CLOCK_R, cy), (cx + CLOCK_R, cy))
        pygame.draw.line(self.screen, CLOCK_AXIS, (cx, cy - CLOCK_R), (cx, cy + CLOCK_R))
        for hour, (ox, oy) in ((12, (0, -1)), (3, (1, 0)), (6, (0, 1)), (9, (-1, 0))):
            s = self.f_tiny.render(str(hour), True, (70, 72, 80))
            self.screen.blit(s, s.get_rect(center=(cx + ox * (CLOCK_R - 11),
                                                   cy + oy * (CLOCK_R - 11))))

        # 현재 당점 — 한눈에 보이도록 크게, 당점 방향으로 조금 더 밀어서
        dx, dy = spec.marker_offset(self.english, CLOCK_R)
        mx, my = round(cx + dx), round(cy - dy)          # 화면 y는 아래가 +
        r = spec.marker_radius
        pygame.draw.circle(self.screen, CLOCK_MARK, (mx, my), r)
        pygame.draw.circle(self.screen, (255, 255, 255), (mx, my), r, 2)

        # ★ 모바일 기준 — 당점은 **그림만** 둔다 (사용자 확정). 팁수·방향 설명은
        #   작은 글씨라 폰에서 안 보이고, 자리만 차지해 보정 버튼을 가린다.

    def set_english_from_click(self, pos: tuple[int, int]) -> bool:
        """시계판 안을 클릭했으면 좌/우를 바꾸고 True. 팁수는 고정이라 안 바뀐다."""
        cx, cy = self.clock_center()
        dx, dy = pos[0] - cx, cy - pos[1]
        if (dx * dx + dy * dy) ** 0.5 > CLOCK_R:
            return False
        self.side_manual = dx < 0                # 왼쪽을 누르면 좌회전
        return True

    def draw_info(self, layout: Layout) -> None:
        w, h = self.screen.get_size()
        top = h - INFO_H
        pygame.draw.line(self.screen, (56, 58, 66), (0, top), (w, top))

        t = self.table
        self.screen.blit(
            self.f_title.render(
                f"{t.name} · 쿠션 노즈 {t.width:.0f} × {t.height:.0f} mm · "
                f"프레임 오프셋 {t.frame_offset:.0f} mm (계산 기준) · "
                f"장쿠션 {t.long_divisions}등분 / 단쿠션 {t.short_divisions}등분",
                True, TEXT),
            (MARGIN, top + 8))

        legend = [
            ("수구수", self.scales[five_half.START].color),
            ("1쿠션수", self.scales[five_half.FIRST_CUSHION].color),
            ("3쿠션수", self.scales[five_half.THIRD_CUSHION].color),
        ]
        x = MARGIN
        for name, color in legend:
            pygame.draw.rect(self.screen, color, pygame.Rect(x, top + 36, 12, 12))
            s = self.f_info.render(name, True, TEXT)
            self.screen.blit(s, (x + 18, top + 33))
            x += 18 + s.get_width() + 22
        self.screen.blit(self.f_info.render("수구수 - 1쿠션수 = 3쿠션수", True, TEXT_DIM), (x + 10, top + 33))

        # 계산 결과
        s = self.shot
        if s is None:
            line = "수구를 좌클릭으로 놓고 마우스로 1쿠션을 겨냥하세요"
            color = TEXT_DIM
        elif s.ok:
            line = (f"수구수 {s.cue_number:.1f}  -  1쿠션수 {s.first_number:.1f}"
                    f"  =  3쿠션수 {s.third_number:.1f}")
            color = TEXT
            rail_kr = {"top": "상단", "bottom": "하단", "left": "좌측", "right": "우측"}
            line = f"[{s.orientation.label}]  " + line
            if s.fourth_number is not None:
                line += f"   →  4쿠션 {s.fourth_number:.1f} ({rail_kr.get(s.fourth_rail, '')})"
            elif s.fourth_index is not None:
                line += (f"   →  4쿠션 {rail_kr.get(s.fourth_rail, '')} "
                         f"다이아 {s.fourth_index:.1f} (눈금 밖)")
            hit = self.hit_ball
            if hit:
                line += f"      ★ {hit[0]} 명중 ({hit[1]:.0f}mm)"
                color = PATH_HIT
            if s.note:
                line += f"      [{s.note}]"
        else:
            line = f"계산 불가 - {s.note}"
            if s.cue_number is not None:
                line += f"   (수구수 {s.cue_number:.1f})"
            color = PATH_FAIL
        self.screen.blit(self.f_info.render(line, True, color), (MARGIN, top + 58))

        frozen = "  [조준 고정]" if self.frozen_aim else ""
        self.screen.blit(
            self.f_tiny.render(
                "좌클릭 수구  우클릭 적구1  휠클릭 적구2  공을 끌어서 옮김  2 수구바꾸기  SPACE 조준고정  "
                "N 번호표  D 다이아인덱스  T 당점좌우자동  R 지우기  ESC 종료" + frozen,
                True, TEXT_DIM),
            (MARGIN, top + 84))
        note = self.capture_note or "당점 2시30분 3팁 고정 (좌회전이면 9시30분)"
        if self.capture_path:
            note = f"캡처: {note}   [L 다시읽기]"
        self.screen.blit(self.f_tiny.render(note, True, TEXT_DIM), (MARGIN, top + 110))

    # ---------------------------------------------------------------- 루프

    def render(self, layout: Layout) -> None:
        self.screen.fill(BG)
        self.draw_table(layout)
        self.draw_diamonds(layout)
        if self.show_numbers:
            self.draw_numbers(layout)
        self.draw_path(layout)
        self.draw_balls(layout)
        self.draw_buttons(layout)
        self.draw_english()

    def run(self) -> None:
        while self.running:
            layout = Layout(self.table, self.screen.get_size())
            for event in pygame.event.get():
                self.handle_event(event, layout)

            # 공을 끄는 중에는 조준을 건드리지 않는다 — 마우스가 곧 공 자리라
            # 그대로 두면 조준선이 자기 자신을 겨눠 궤적이 무너진다.
            if not self.dragging:
                self.mouse_mm = layout.to_mm(*pygame.mouse.get_pos())
            self.update_shot(self.mouse_mm)
            self.render(layout)
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()


def run(capture: str | None = None) -> None:
    app = App()
    if capture:
        app.load_capture(capture)
    app.run()
