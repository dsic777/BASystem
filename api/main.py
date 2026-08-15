"""BASystem 평가 창구 — 추천 경로 판정을 서버 DB 에 쌓는다.

사용자 2026-08-14:
  '내 의도는 자료를 DB화 하라는 겁니다. 서버에 저장을 하고 그것을 당신이 꺼내보면서
   프로그램 개선을 하자는 의도입니다. 이미 우리 서버에 다 있는데 저장을 못할수 있나요.'

왜 필요한가
  판정(상·중·하)이 폰 안에만 쌓이면 Claude 가 못 본다. 클립보드로 옮기는 것은
  혼자 쓸 때만 견딜 만하고, 지인들에게 부탁하면 아무도 안 옮긴다.
  서버에 쌓으면 판정하는 순간 바로 모인다.

붙는 자리 (기존 chocolate-api 와 같은 방식)
  portfolio-nginx  /basystem/api/  →  basystem-api:8000/api/
  portfolio-db     basystem 데이터베이스

⚠️ 이 서버는 SaaS 세 개가 같이 돈다. 다른 컨테이너를 건드리지 않는다.
"""
from __future__ import annotations

import os
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg.types.json import Json
from pydantic import BaseModel

DSN = os.environ.get(
    "BASYSTEM_DSN",
    "postgresql://basystem:1234@portfolio-db:5432/basystem",
)

app = FastAPI(title="BASystem 평가 창구")
# 앱은 같은 도메인에서 열리지만, 시험 중에 다른 데서 부를 수 있으므로 열어 둔다.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ★ 사용자 2026-08-14: '수집에 ip를 넣어주세요. 우리집ip 59.11.155.78 입니다.
#   추천 판정 테스트는 집에서만 하면 됩니다. 이러면 일부 지인에게 줘도 됩니다.
#   내 ip만 프로그램에 반영을 하고, 그외 수집자료는 상황을 봐서 검증 후 반영을 결정하겠습니다.'
#   → 판정마다 보낸 곳의 IP 를 남긴다. 사장님 것과 남의 것을 나중에 가려야 하기 때문이다.
#   ⚠️ 열쇠에도 IP 를 넣는다. 안 넣으면 지인과 사장님이 같은 배치를 판정할 때 **서로 덮어쓴다.**
OWNER_IP = "59.11.155.78"

DDL = """
CREATE TABLE IF NOT EXISTS verdict (
    id         BIGSERIAL PRIMARY KEY,
    at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    ip         TEXT NOT NULL DEFAULT '',
    who        TEXT NOT NULL DEFAULT '',
    app        INTEGER,
    place_key  TEXT NOT NULL,
    route_key  TEXT NOT NULL,
    verdict    TEXT NOT NULL,
    balls      JSONB,
    info       JSONB,
    UNIQUE (ip, who, place_key, route_key)
);
CREATE INDEX IF NOT EXISTS verdict_at_idx ON verdict (at DESC);
CREATE INDEX IF NOT EXISTS verdict_ip_idx ON verdict (ip);

-- ★ 요청·평가 메모 (사용자 2026-08-16)
--   '화면을 보고 수정사항 등을 캡처해서 프롬프트에서 치려니 불편해서 그런겁니다.'
--   앱에서 바로 쓰고, 앱에서 답을 받는다. 지금 보고 있는 배치·경로가 통째로 붙어 오므로
--   Claude 가 그 화면을 그대로 재현할 수 있다.
--   ⚠️ 답(reply)은 API 로 안 쓴다. 인증 구멍을 안 만들려고 일부러 뺐다 —
--      psql 로 직접 쓴다 (notes.py 참고).
CREATE TABLE IF NOT EXISTS note (
    id         BIGSERIAL PRIMARY KEY,
    at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    ip         TEXT NOT NULL DEFAULT '',
    who        TEXT NOT NULL DEFAULT '',
    app        INTEGER,
    kind       TEXT NOT NULL DEFAULT '요청',
    text       TEXT NOT NULL,
    place_key  TEXT,
    route_key  TEXT,
    balls      JSONB,
    info       JSONB,
    reply      TEXT,
    replied_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS note_at_idx ON note (at DESC);
CREATE INDEX IF NOT EXISTS note_ip_idx ON note (ip);
"""


def client_ip(req: Request) -> str:
    """nginx 뒤에 있으므로 X-Real-IP 를 먼저 본다 (내가 넣은 헤더다)."""
    h = req.headers
    return (h.get("x-real-ip")
            or (h.get("x-forwarded-for") or "").split(",")[0].strip()
            or (req.client.host if req.client else ""))


def db():
    return psycopg.connect(DSN, row_factory=dict_row)


@app.on_event("startup")
def setup() -> None:
    with db() as c:
        c.execute(DDL)
        c.commit()


class One(BaseModel):
    who: str = ""
    app: int | None = None
    place_key: str
    route_key: str
    verdict: str
    balls: Any = None
    info: Any = None


class Bulk(BaseModel):
    who: str = ""
    app: int | None = None
    # 앱의 localStorage 모양 그대로 — {배치키: {at, who, balls, v:{경로키:판정}, info:{}}}
    data: dict[str, Any]


SQL_UP = """
INSERT INTO verdict (ip, who, app, place_key, route_key, verdict, balls, info)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (ip, who, place_key, route_key) DO UPDATE
   SET verdict = EXCLUDED.verdict,
       balls   = EXCLUDED.balls,
       info    = EXCLUDED.info,
       app     = EXCLUDED.app,
       at      = now()
"""


@app.get("/api/health")
def health() -> dict:
    with db() as c:
        n = c.execute("SELECT count(*) AS n FROM verdict").fetchone()["n"]
    return {"ok": True, "rows": n}


@app.post("/api/verdict")
def put_one(v: One, req: Request) -> dict:
    ip = client_ip(req)
    with db() as c:
        c.execute(
            SQL_UP,
            (ip, v.who, v.app, v.place_key, v.route_key, v.verdict,
             Json(v.balls), Json(v.info)),
        )
        c.commit()
    return {"ok": True, "ip": ip, "mine": ip == OWNER_IP}


@app.post("/api/verdicts")
def put_bulk(b: Bulk, req: Request) -> dict:
    ip = client_ip(req)
    n = 0
    with db() as c:
        for pk, rec in (b.data or {}).items():
            balls = rec.get("balls")
            info = rec.get("info") or {}
            who = rec.get("who") or b.who
            for rk, val in (rec.get("v") or {}).items():
                c.execute(
                    SQL_UP,
                    (ip, who, b.app, pk, rk, val, Json(balls), Json(info.get(rk))),
                )
                n += 1
        c.commit()
    return {"ok": True, "saved": n}


@app.get("/api/verdicts")
def get_all(limit: int = 2000, ip: str | None = None, mine: bool = False) -> dict:
    """mine=1 이면 사장님 집 IP 것만. ip= 로 직접 지정할 수도 있다."""
    want = OWNER_IP if mine else ip
    with db() as c:
        if want:
            rows = c.execute(
                "SELECT at, ip, who, app, place_key, route_key, verdict, balls, info"
                " FROM verdict WHERE ip = %s ORDER BY at DESC LIMIT %s",
                (want, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT at, ip, who, app, place_key, route_key, verdict, balls, info"
                " FROM verdict ORDER BY at DESC LIMIT %s",
                (limit,),
            ).fetchall()
    return {"count": len(rows), "owner_ip": OWNER_IP, "rows": rows}


class Note(BaseModel):
    who: str = ""
    app: int | None = None
    kind: str = "요청"
    text: str
    place_key: str | None = None
    route_key: str | None = None
    balls: Any = None
    info: Any = None


@app.post("/api/note")
def put_note(v: Note, req: Request) -> dict:
    """앱에서 쓴 요청·평가를 받는다. 지금 화면(배치·경로)이 통째로 같이 온다."""
    ip = client_ip(req)
    txt = (v.text or "").strip()
    if not txt:
        return {"ok": False, "why": "빈 글"}
    with db() as c:
        row = c.execute(
            "INSERT INTO note (ip, who, app, kind, text, place_key, route_key, balls, info)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (ip, v.who, v.app, v.kind, txt[:4000], v.place_key, v.route_key,
             Json(v.balls), Json(v.info)),
        ).fetchone()
        c.commit()
    return {"ok": True, "id": row["id"], "ip": ip, "mine": ip == OWNER_IP}


@app.get("/api/notes")
def get_notes(limit: int = 50, mine: bool = False, ip: str | None = None) -> dict:
    """내가 쓴 것과 그 답. 앱은 **자기 IP 것만** 본다 (인자를 안 주면 그렇게 된다).

    ⚠️ 사용자 2026-08-16: '요청은 내 ip만 답변하면 됩니다.'
       남의 IP 것은 쌓이기만 하고 답이 안 붙는다. 여기서 막는 것이 아니라
       답을 안 쓰는 것으로 그렇게 된다.
    """
    want = OWNER_IP if mine else ip
    with db() as c:
        if want:
            rows = c.execute(
                "SELECT id, at, kind, text, reply, replied_at, place_key, route_key, app"
                " FROM note WHERE ip = %s ORDER BY id DESC LIMIT %s", (want, limit)).fetchall()
        else:
            rows = c.execute(
                "SELECT id, at, kind, text, reply, replied_at, place_key, route_key, app, ip"
                " FROM note ORDER BY id DESC LIMIT %s", (limit,)).fetchall()
    return {"count": len(rows), "rows": rows}


@app.get("/api/mynotes")
def my_notes(req: Request, limit: int = 50) -> dict:
    """부르는 폰의 IP 것만. 앱이 이걸 쓴다 — IP 를 앱이 몰라도 된다."""
    ip = client_ip(req)
    with db() as c:
        rows = c.execute(
            "SELECT id, at, kind, text, reply, replied_at, place_key, route_key"
            " FROM note WHERE ip = %s ORDER BY id DESC LIMIT %s", (ip, limit)).fetchall()
    return {"count": len(rows), "ip": ip, "mine": ip == OWNER_IP, "rows": rows}


@app.get("/api/stat")
def stat() -> dict:
    with db() as c:
        by = c.execute(
            "SELECT verdict, count(*) AS n FROM verdict GROUP BY verdict ORDER BY n DESC"
        ).fetchall()
        who = c.execute(
            "SELECT who, count(*) AS n FROM verdict GROUP BY who ORDER BY n DESC"
        ).fetchall()
        places = c.execute(
            "SELECT count(DISTINCT place_key) AS n FROM verdict"
        ).fetchone()["n"]
        by_ip = c.execute(
            "SELECT ip, count(*) AS n, count(DISTINCT place_key) AS layouts"
            " FROM verdict GROUP BY ip ORDER BY n DESC"
        ).fetchall()
    for r in by_ip:
        r["mine"] = r["ip"] == OWNER_IP
    return {"by_verdict": by, "by_who": who, "by_ip": by_ip,
            "layouts": places, "owner_ip": OWNER_IP}
