"""요청·평가 메모를 읽고 답을 쓴다 (서버 DB 직접).

    python notes.py                안 답한 것부터 보여준다
    python notes.py --all          답한 것까지
    python notes.py 12 "답 내용"   #12 에 답을 쓴다

★ 사용자 2026-08-16 —
  '내가 요청을 등록을 하고, 지금 프롬프트에서 x 한자만 치면 당신은 요청사항이
   들어왔다고 판단을 하고 즉시 서버를 확인해서 답변을 하면 되겠네요.'
  → 프롬프트에 **x** 한 글자가 오면 이 파일을 인자 없이 돌려 새 요청을 읽는다.

왜 API 가 아니라 psql 인가
  답을 쓰는 창구를 API 로 열면 아무나 답을 쓸 수 있게 된다 (지금 API 에는 인증이 없다).
  답은 나만 쓰면 되고 나는 이미 ssh 로 들어간다. 그래서 인증 구멍을 안 만든다.

앱 쪽
  index.html 의 NOTE — 점수판 오른쪽 '말' 칸. 60초마다 GET /api/mynotes 로 답을 받아 온다.
"""
import json
import subprocess
import sys

SSH = ["ssh", "-o", "BatchMode=yes", "ubuntu@dspro.duckdns.org"]
PSQL = "docker exec -i portfolio-db psql -U basystem -d basystem -At -F'\t' -c"


def run(sql: str) -> str:
    out = subprocess.run(SSH + [f"{PSQL} \"{sql}\""],
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        raise SystemExit("서버 오류: " + (out.stderr or out.stdout))
    return out.stdout


def show(all_: bool) -> None:
    where = "" if all_ else " WHERE reply IS NULL"
    # ⚠️ 글에 줄바꿈이 들어가면 psql 한 줄 출력이 여러 줄로 쪼개져 표가 깨진다
    #    (2026-08-16 요청 #4 에서 실제로 깨졌다). 탭과 줄바꿈을 미리 바꿔 둔다.
    flat = "replace(replace({0}, chr(9), ' '), chr(10), ' / ')"
    sql = ("SELECT id, to_char(at,'MM-DD HH24:MI'), kind, ip, coalesce(app::text,''),"
           f" {flat.format('text')}, coalesce({flat.format('reply')},''),"
           " coalesce(place_key,''), coalesce(route_key,'')"
           f" FROM note{where} ORDER BY id")
    rows = [r.split("\t") for r in run(sql).splitlines() if r.strip()]
    if not rows:
        print("새 요청 없습니다.")
        return
    print(f"메모 {len(rows)}개\n")
    for r in rows:
        i, at, kind, ip, app, text, reply, pk, rk = (r + [""] * 9)[:9]
        mine = " (사장님)" if ip == "59.11.155.78" else f" ({ip})"
        print(f"── #{i}  {at}  [{kind}]{mine}  앱 v{app}")
        print(f"   {text}")
        if pk:
            print(f"   배치 {pk[:90]}")
        if rk:
            print(f"   경로 {rk[:90]}")
        if reply:
            print(f"   ↳ {reply}")
        print()


def reply(nid: str, text: str) -> None:
    t = text.replace("'", "''")
    run(f"UPDATE note SET reply='{t}', replied_at=now() WHERE id={int(nid)}")
    print(f"#{nid} 에 답을 썼습니다. 폰은 60초 안에 받습니다.")


def main(argv: list[str]) -> int:
    if argv and argv[0] not in ("--all",):
        if len(argv) < 2:
            print(__doc__)
            return 1
        reply(argv[0], " ".join(argv[1:]))
        return 0
    show("--all" in argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
