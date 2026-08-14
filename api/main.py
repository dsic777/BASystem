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
from fastapi import FastAPI
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

DDL = """
CREATE TABLE IF NOT EXISTS verdict (
    id         BIGSERIAL PRIMARY KEY,
    at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    who        TEXT NOT NULL DEFAULT '',
    app        INTEGER,
    place_key  TEXT NOT NULL,
    route_key  TEXT NOT NULL,
    verdict    TEXT NOT NULL,
    balls      JSONB,
    info       JSONB,
    UNIQUE (who, place_key, route_key)
);
CREATE INDEX IF NOT EXISTS verdict_at_idx ON verdict (at DESC);
"""


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
INSERT INTO verdict (who, app, place_key, route_key, verdict, balls, info)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (who, place_key, route_key) DO UPDATE
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
def put_one(v: One) -> dict:
    with db() as c:
        c.execute(
            SQL_UP,
            (v.who, v.app, v.place_key, v.route_key, v.verdict, Json(v.balls), Json(v.info)),
        )
        c.commit()
    return {"ok": True}


@app.post("/api/verdicts")
def put_bulk(b: Bulk) -> dict:
    n = 0
    with db() as c:
        for pk, rec in (b.data or {}).items():
            balls = rec.get("balls")
            info = rec.get("info") or {}
            who = rec.get("who") or b.who
            for rk, val in (rec.get("v") or {}).items():
                c.execute(
                    SQL_UP,
                    (who, b.app, pk, rk, val, Json(balls), Json(info.get(rk))),
                )
                n += 1
        c.commit()
    return {"ok": True, "saved": n}


@app.get("/api/verdicts")
def get_all(limit: int = 2000) -> dict:
    with db() as c:
        rows = c.execute(
            "SELECT at, who, app, place_key, route_key, verdict, balls, info"
            " FROM verdict ORDER BY at DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return {"count": len(rows), "rows": rows}


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
    return {"by_verdict": by, "by_who": who, "layouts": places}
