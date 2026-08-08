"""영상의 당구대 코너를 사람이 한 번만 찍어 저장한다.

카메라가 삼각대로 고정돼 있으면 코너는 영상 내내 그대로다. 그래서 한 번만
찍어 두면 모든 프레임이 정확해진다.

자동 검출은 당구장에 당구대가 여러 대 있으면 엉뚱한 사각형을 만든다
(2026-08-06 촬영본에서 확인). 수동으로 찍는 쪽이 훨씬 확실하다.

찍는 순서
    좌하 → 우하 → 우상 → 좌상   (당구대 기준. 화면 기준이 아니다)
    **쿠션 날(천이 시작되는 안쪽 모서리)** 을 찍는다. 나무 레일이 아니다.

화면은 pygame 으로 띄운다. 설치된 OpenCV 가 headless 라 cv2.imshow 를 못 쓴다.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pygame

ORDER = ["좌하", "우하", "우상", "좌상"]
MAX_W, MAX_H = 1600, 860
ZOOM_SRC = 150               # 확대 모드에서 보여줄 원본 영역 크기 (px). 작을수록 크게 보인다.


def corners_path(video: str | Path) -> Path:
    p = Path(video)
    return p.with_name(p.stem + "_corners.json")


def load(video: str | Path) -> np.ndarray | None:
    """저장해 둔 코너가 있으면 읽는다."""
    p = corners_path(video)
    if not p.exists():
        return None
    return np.array(json.loads(p.read_text(encoding="utf-8"))["quad"], dtype=np.float32)


def save(video: str | Path, quad: np.ndarray) -> Path:
    p = corners_path(video)
    p.write_text(json.dumps({"_desc": "쿠션 날 코너 (좌하, 우하, 우상, 좌상)",
                             "video": Path(video).name,
                             "quad": [[float(x), float(y)] for x, y in quad]},
                            ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _font(size: int, bold: bool = False) -> pygame.font.Font:
    path = pygame.font.match_font("malgungothic,malgun gothic,gulim,dotum,batang")
    f = pygame.font.Font(path, size) if path else pygame.font.SysFont(None, size)
    f.set_bold(bold)
    return f


def _frame(video: str | Path, at: float) -> np.ndarray:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 못 열었다: {video}")
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * at))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("프레임을 못 읽었다")
    return frame


def pick(video: str | Path, at: float = 0.2) -> np.ndarray:
    """화면을 띄우고 코너 4개를 클릭받는다. 원본 이미지 좌표로 돌려준다.

    두 번 클릭한다. 먼저 대충 찍으면 그 자리가 크게 확대되고, 거기서 정확히 찍는다.
    1280px 영상에서 쿠션 날은 몇 픽셀이라 한 번에 찍기 어렵다.
    """
    frame = _frame(video, at)
    h, w = frame.shape[:2]
    scale = min(MAX_W / w, MAX_H / h)
    vw, vh = int(w * scale), int(h * scale)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    full = pygame.image.frombuffer(np.ascontiguousarray(rgb), (w, h), "RGB")
    view = pygame.transform.smoothscale(full, (vw, vh))

    pygame.init()
    screen = pygame.display.set_mode((vw, vh + 46))
    pygame.display.set_caption(f"코너 찍기 — {Path(video).name}")
    f_msg, f_tag = _font(18, True), _font(17, True)
    clock = pygame.time.Clock()

    pts: list[tuple[float, float]] = []            # 원본 좌표
    zoom_at: tuple[float, float] | None = None     # 확대 중심 (원본 좌표)
    done = False

    def zoom_rect() -> pygame.Rect:
        r = pygame.Rect(0, 0, ZOOM_SRC, ZOOM_SRC)
        r.center = (int(zoom_at[0]), int(zoom_at[1]))
        return r.clamp(pygame.Rect(0, 0, w, h))

    while not done:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.display.quit()
                raise KeyboardInterrupt("취소됨")
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if zoom_at is not None:
                        zoom_at = None                      # 확대만 취소
                    else:
                        pygame.display.quit()
                        raise KeyboardInterrupt("취소됨")
                if e.key in (pygame.K_r, pygame.K_BACKSPACE):
                    pts.clear()
                    zoom_at = None
                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and len(pts) == 4:
                    done = True
            if e.type == pygame.MOUSEBUTTONDOWN and e.pos[1] < vh:
                if e.button == 3:
                    zoom_at = None                          # 우클릭 = 확대 취소
                elif e.button == 1 and len(pts) < 4:
                    if zoom_at is None:
                        zoom_at = (e.pos[0] / scale, e.pos[1] / scale)
                    else:
                        r = zoom_rect()
                        pts.append((r.x + e.pos[0] / vw * r.w, r.y + e.pos[1] / vh * r.h))
                        zoom_at = None

        mx, my = pygame.mouse.get_pos()
        screen.fill((18, 18, 22))

        if zoom_at is None:
            screen.blit(view, (0, 0))
            to_px = lambda p: (round(p[0] * scale), round(p[1] * scale))   # noqa: E731
            if my < vh and len(pts) < 4:
                pygame.draw.line(screen, (255, 220, 0), (mx, 0), (mx, vh))
                pygame.draw.line(screen, (255, 220, 0), (0, my), (vw, my))
        else:
            r = zoom_rect()
            screen.blit(pygame.transform.scale(full.subsurface(r), (vw, vh)), (0, 0))
            to_px = lambda p: (round((p[0] - r.x) / r.w * vw),             # noqa: E731
                               round((p[1] - r.y) / r.h * vh))
            pygame.draw.line(screen, (255, 60, 60), (mx - 26, my), (mx + 26, my), 2)
            pygame.draw.line(screen, (255, 60, 60), (mx, my - 26), (mx, my + 26), 2)
            pygame.draw.circle(screen, (255, 60, 60), (mx, my), 3)

        for i, p in enumerate(pts):
            q = to_px(p)
            if -50 < q[0] < vw + 50 and -50 < q[1] < vh + 50:
                pygame.draw.circle(screen, (255, 220, 0), q, 7)
                pygame.draw.circle(screen, (0, 0, 0), q, 7, 2)
                screen.blit(f_tag.render(ORDER[i], True, (255, 220, 0)), (q[0] + 12, q[1] - 24))
        if len(pts) >= 2:
            pygame.draw.lines(screen, (255, 60, 60), len(pts) == 4, [to_px(p) for p in pts], 2)

        if len(pts) == 4:
            msg = "ENTER 저장   R 다시   ESC 건너뛰기"
        elif zoom_at is None:
            msg = f"{len(pts)}/4  {ORDER[len(pts)]} 쪽을 대충 클릭 → 확대됩니다"
        else:
            msg = f"{len(pts)}/4  {ORDER[len(pts)]} 쿠션 날 모서리를 정확히 클릭   (우클릭/ESC 취소)"
        screen.blit(f_msg.render(msg, True, (235, 235, 240)), (12, vh + 12))
        pygame.display.flip()
        clock.tick(60)

    pygame.display.quit()
    return np.array(pts, dtype=np.float32)
