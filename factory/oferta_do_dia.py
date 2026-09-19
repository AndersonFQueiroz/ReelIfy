"""Oferta do dia: TOP 9 distintos (3 vídeos × 3 produtos). Nunca repete (usados.json).

Fontes: Shopee Affiliate API (ordenado por desconto) → fallback canal (posts distintos).
ML direto fora (403 desta rede).
Uso: python3 -m factory.oferta_do_dia [--date AAAA-MM-DD]
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import html as _html
import json
import re
import sys
import time
from pathlib import Path

import requests

from . import config as C

_TIMEOUT = 25
_CHANNEL = C.env("TELEGRAM_CHANNEL_PREVIEW", "cacaofertasofcBR")
_PRICE_RE = re.compile(r"R\$\s*([\d.]+)")
_LINK_RE = re.compile(r"https?://[^\s)>\]]+")
NEED = 9


def _day_dir(day: str) -> Path:
    d = C.FACTORY_DATA / day
    d.mkdir(parents=True, exist_ok=True)
    return d


def _usados_path() -> Path:
    return C.FACTORY_DATA / "usados.json"


def next_edition() -> int:
    """Incrementa só quando gera ofertas novas (rebuild do mesmo dia não conta)."""
    p = C.FACTORY_DATA / "edicao.json"
    try:
        n = int(json.loads(p.read_text(encoding="utf-8")).get("n", 0))
    except Exception:
        n = 0
    # 19/09 (primeira vitrine) conta como #1
    n = n + 1
    p.write_text(json.dumps({"n": n}), encoding="utf-8")
    return n


def current_edition() -> int:
    try:
        return int(json.loads((C.FACTORY_DATA / "edicao.json").read_text(encoding="utf-8")).get("n", 1))
    except Exception:
        return 1


def load_usados() -> set[str]:
    try:
        return set(json.loads(_usados_path().read_text(encoding="utf-8")))
    except Exception:
        return set()


def mark_usados(keys: list[str]) -> None:
    u = load_usados()
    u.update(keys)
    _usados_path().write_text(json.dumps(sorted(u), ensure_ascii=False, indent=1), encoding="utf-8")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "ReelifyFactory/1.0"})
    return s


def _benefits_shopee(n: dict) -> list[str]:
    out = []
    try:
        r = float(n.get("ratingStar") or 0)
        if r >= 4.5:
            out.append(f"Nota {f'{r:.1f}'.replace('.', ',')} de avaliação")
    except (TypeError, ValueError):
        pass
    try:
        sales = int(n.get("sales") or 0)
        if sales >= 100:
            out.append(f"+{sales:,}".replace(",", ".") + " vendidos")
    except (TypeError, ValueError):
        pass
    return out[:2]


def _shopee_candidates(s: requests.Session, need: int, usados: set[str]) -> list[dict]:
    app_id, secret = C.env("SHOPEE_APP_ID"), C.env("SHOPEE_SECRET")
    base = C.env("SHOPEE_API_BASE", "https://open-api.affiliate.shopee.com.br")
    if not (app_id and secret):
        print("Shopee: sem credenciais")
        return []
    fields = "productName itemId priceMin priceMax imageUrl productLink offerLink ratingStar sales"
    scored = []
    for page in (1, 2):
        body = json.dumps({"query":
            "{ productOfferV2(page: %d, limit: 50) { nodes { %s } } }" % (page, fields)})
        ts = int(time.time())
        sign = hashlib.sha256((app_id + str(ts) + body + secret).encode()).hexdigest()
        try:
            r = s.post(base.rstrip("/") + "/graphql", data=body.encode(),
                       headers={"Content-Type": "application/json",
                                "Authorization": f"SHA256 Credential={app_id}, Signature={sign}, Timestamp={ts}"},
                       timeout=_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if data.get("errors"):
                print(f"Shopee erro: {data['errors'][0].get('message')}")
                break
            nodes = ((data.get("data", {}).get("productOfferV2") or {}).get("nodes")) or []
        except Exception as exc:
            print(f"Shopee falhou p{page}: {exc}")
            break
        for n in nodes:
            try:
                lo, hi = float(n.get("priceMin") or 0), float(n.get("priceMax") or 0)
            except (TypeError, ValueError):
                continue
            if not lo or not hi or hi <= lo or not n.get("offerLink") or not n.get("imageUrl"):
                continue
            disc = 1 - lo / hi
            if disc < 0.05 or str(n["offerLink"]) in usados:
                continue
            scored.append((disc, lo, {
                "marketplace": "shopee", "external_id": str(n.get("itemId")),
                "title": str(n.get("productName") or "Oferta Shopee")[:90],
                "price": lo, "original_price": hi, "discount_pct": round(disc * 100),
                "affiliate_url": str(n["offerLink"]), "photos": [str(n["imageUrl"])],
                "benefits": _benefits_shopee(n)}))
        if len(scored) >= need * 2:
            break
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    out, seen = [], set()
    for _, _, o in scored:
        if o["affiliate_url"] in seen:
            continue
        seen.add(o["affiliate_url"])
        out.append(o)
        if len(out) == need:
            break
    return out


def _channel_candidates(s: requests.Session, need: int, usados: set[str]) -> list[dict]:
    try:
        r = s.get(f"https://t.me/s/{_CHANNEL}", timeout=_TIMEOUT)
        r.raise_for_status()
        page = r.text
    except Exception as exc:
        print(f"Canal indisponível: {exc}")
        return []
    blocks = re.findall(
        r'<div class="tgme_widget_message_wrap[^>]*>(.*?)<span class="tgme_widget_message_meta">',
        page, re.S)
    cands = []
    for block in reversed(blocks[-20:]):
        text_m = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', block, re.S)
        if not text_m:
            continue
        raw = re.sub(r"<br\s*/?>", "\n", text_m.group(1))
        text = _html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
        links = [l for l in _LINK_RE.findall(text + " " + block)
                 if "t.me/" not in l and "telegram" not in l]
        photo_m = re.search(r"background-image:url\('([^']+)'\)", block)
        prices = [float(p.replace(".", "")) for p in _PRICE_RE.findall(text)]
        if not (links and photo_m and len(prices) >= 1):
            continue
        price, orig = min(prices), max(prices) if len(prices) >= 2 else min(prices)
        disc = round((1 - price / orig) * 100) if orig > price else 0
        if disc < 5 or links[0] in usados:
            continue
        title = next((l.strip() for l in text.splitlines() if len(l.strip()) > 12), "Oferta do canal")[:90]
        market = "mercadolivre" if "mercadolivre" in links[0] or "meli." in links[0] else "shopee"
        if any(c["affiliate_url"] == links[0] for _, c in cands):
            continue
        cands.append((disc, {
            "marketplace": market, "external_id": f"canal-{hash(links[0]) & 0xffff}",
            "title": title, "price": price, "original_price": orig, "discount_pct": disc,
            "affiliate_url": links[0], "photos": [_html.unescape(photo_m.group(1))], "benefits": []}))
        if len(cands) == need:
            break
    cands.sort(key=lambda t: t[0], reverse=True)
    return [c for _, c in cands]


def _download(s: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = s.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return dest.stat().st_size > 5000
    except Exception:
        return False


def _brl(v: float) -> str:
    return f"R$ {v:,.0f}".replace(",", ".")


def main(argv: list[str]) -> int:
    day = argv[0] if argv and len(argv[0]) == 10 else _dt.date.today().isoformat()
    outdir = _day_dir(day)
    if "--fresh" not in argv and (outdir / "offers_day.json").exists():
        print(f"Ofertas de {day} já existem — reuse (use --fresh p/ trocar).")
        return 0
    s = _session()
    usados = load_usados()

    offers = _shopee_candidates(s, NEED, usados)
    origem = "shopee-api"
    if len(offers) < 3:
        print(f"Shopee rendeu {len(offers)} → completando com canal.")
        got = {o["affiliate_url"] for o in offers}
        for c in _channel_candidates(s, NEED, usados | got):
            offers.append(c)
            if len(offers) >= NEED:
                break
        origem = "mista" if offers else "canal"
    if len(offers) < 3:
        print("FALHA: menos de 3 ofertas distintas.", file=sys.stderr)
        return 1

    offers = offers[:NEED]
    for i, o in enumerate(offers):
        dest = outdir / f"foto{i+1}.jpg"
        if _download(s, o["photos"][0], dest):
            o["photos_local"] = [str(dest)]
        else:
            o["photos_local"] = []
    offers = [o for o in offers if o["photos_local"]]
    if len(offers) < 3:
        print("FALHA: fotos insuficientes.", file=sys.stderr)
        return 1
    for o in offers:
        o.update({"day": day, "price_label": _brl(o["price"]),
                  "original_label": _brl(o["original_price"])})
    mark_usados([o["affiliate_url"] for o in offers])
    groups = {"v1": offers[0:3], "v2": offers[3:6], "v3": offers[6:9]}
    groups = {k: v for k, v in groups.items() if len(v) == 3}
    if not groups:
        print("FALHA: sem trio completo.", file=sys.stderr)
        return 1
    (outdir / "offers_day.json").write_text(
        json.dumps({"day": day, "origem": origem, "edition": next_edition(),
                    "groups": groups}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    for k, v in groups.items():
        print(f"{k}: " + " | ".join(f"{o['title'][:30]} -{o['discount_pct']}%" for o in v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
