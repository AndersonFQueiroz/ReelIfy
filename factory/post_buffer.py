"""Auto-post IG + TikTok + YouTube via Buffer (plano grátis).

Requer BUFFER_API_KEY no .env (publish.buffer.com → API key) + canais
conectados 1x no painel do Buffer. Sem chave → exit 3 (pula, sem erro).
Kwai não tem suporte em nenhuma ferramenta → segue pack manual no Telegram.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import requests

from . import config as C

API = "https://api.buffer.com"
_TIMEOUT = 60
# 10h/15h/20h BRT = 13/18/23 UTC
SLOTS_UTC = [(13, 0), (18, 0), (23, 0)]
WANT = ("instagram", "tiktok", "youtube")


def _gql(token: str, query: str, variables: dict | None = None) -> dict:
    r = requests.post(API, json={"query": query, "variables": variables or {}},
                      headers={"Authorization": f"Bearer {token}",
                               "Content-Type": "application/json"},
                      timeout=_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(str(data["errors"][0].get("message")))
    return data["data"]


def channels(token: str) -> dict[str, str]:
    orgs = _gql(token, "query { account { organizations { id name } } }")
    org_list = ((orgs.get("account") or {}).get("organizations")) or []
    if not org_list:
        raise RuntimeError("sem organizações no Buffer")
    found: dict[str, str] = {}
    for org in org_list:
        chs = _gql(token, "query($o: OrganizationId!) { channels(input: {organizationId: $o}) { id name service } }",
                   {"o": org["id"]})
        for ch in (chs.get("channels") or []):
            svc = str(ch.get("service") or "").lower()
            for w in WANT:
                if w in svc and w not in found:
                    found[w] = ch["id"]
    return found


def create_post(token: str, svc: str, channel_id: str, text: str,
                video_url: str, due_at: str, title: str,
                first_comment: str = "") -> str:
    meta = {}
    if svc == "instagram":
        # firstComment é pago → links vão na legenda (copiar-colar)
        meta = {"instagram": {"type": "reel", "shouldShareToFeed": True}}
    elif svc == "youtube":
        meta = {"youtube": {"title": title, "categoryId": "22"}}
    variables = {"i": {"text": text, "channelId": channel_id,
                       "schedulingType": "automatic", "mode": "customScheduled",
                       "dueAt": due_at,
                       "assets": [{"video": {"url": video_url,
                                             "metadata": {"thumbnailOffset": 2000}}}]}}
    if meta:
        variables["i"]["metadata"] = meta
    q = """mutation($i: CreatePostInput!) {
      createPost(input: $i) {
        ... on PostActionSuccess { post { id dueAt } }
        ... on MutationError { message }
      } } """
    data = _gql(token, q, variables)
    res = (data.get("createPost") or {})
    post = res.get("post")
    if post:
        return post["id"]
    raise RuntimeError(res.get("message", "erro desconhecido"))


def main(day: str, only: list[str] | None = None) -> int:
    from . import upload_public
    token = C.env("BUFFER_API_KEY")
    if not token:
        print("SEM BUFFER_API_KEY — auto-post pulado (exit 3).")
        return 3
    keys = [k for k in ("v1", "v2", "v3") if not only or k in only]
    if not keys:
        print("Nada selecionado (--only vazio).")
        return 1
    day_dir = C.FACTORY_DATA / day
    pack = json.loads((day_dir / "pack.json").read_text(encoding="utf-8"))
    try:
        chans = channels(token)
    except Exception as exc:
        print(f"Buffer canais falhou: {exc}")
        return 1
    missing = [w for w in WANT if w not in chans]
    if missing:
        print(f"Buffer: canais não conectados: {missing} (conecte 1x no painel)")
    ok, fail = 0, 0
    for key in keys:
        h, m = SLOTS_UTC[{"v1": 0, "v2": 1, "v3": 2}[key]]
        # Instagram/YouTube aceitam catbox; TikTok exige HEAD honesto → host Telegram
        url_tt = upload_public.telegram_host(Path(pack["videos"][key]))
        url = upload_public.upload(Path(pack["videos"][key]))
        if not (url or url_tt):
            print(f"upload público falhou: {key}")
            fail += 3
            continue
        due = _dt.datetime(int(day[:4]), int(day[5:7]), int(day[8:10]), h, m,
                           tzinfo=_dt.timezone.utc).isoformat()
        for svc in WANT:
            if svc not in chans:
                continue
            text = pack["captions"][key] + "\n" + pack.get("cta", {}).get(svc, "")
            if svc == "tiktok":
                text = text.replace("\n", " ")
            vurl = url_tt or url  # Telegram: único host com HEAD honesto
            try:
                pid = create_post(token, svc, chans[svc], text[:2100], vurl, due,
                                  pack.get("titles", {}).get(key, f"ACHADINHOS DO DIA {day}"),
                                  pack.get("first_comments", {}).get(key, ""))
                print(f"Buffer OK {svc}/{key}: {pid} @ {due}")
                ok += 1
            except Exception as exc:
                print(f"Buffer FALHOU {svc}/{key}: {exc}")
                fail += 1
    (day_dir / "buffer.json").write_text(json.dumps({"ok": ok, "fail": fail}), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    _day = args[args.index("--date") + 1] if "--date" in args else args[0]
    _only = None
    if "--only" in args:
        _only = args[args.index("--only") + 1].split(",")
    if "--svc" in args:
        WANT = tuple(s for s in args[args.index("--svc") + 1].split(",") if s in WANT)
    if "--sim" not in args:
        print("TRAVADO: post no Buffer exige aprovação explícita do dono (--sim). Nada enviado.")
        raise SystemExit(3)
    raise SystemExit(main(_day, _only))
