"""Oferta do dia: escolhe 1 produto + links de afiliado (independente do bot/LG).

Fontes:
1. Shopee Affiliate Open API (productOfferV2) → offerLink pronto. (requer SHOPEE_APP_ID/SECRET)
2. Fallback: canal t.me/s/cacaofertasofcBR → reaproveita post real do bot (foto + link + preços).

ML direto: api.mercadolibre.com retorna 403 desta rede → fora do v1.

REGRA DURA: sem affiliate_url válido o pipeline PARA (exit 2).
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


def _day_dir(day: str) -> Path:
    d = C.FACTORY_DATA / day
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "ReelifyFactory/1.0"})
    return s


# ---------------- Shopee ----------------

def _shopee_graphql(s: requests.Session, query: str) -> dict:
    app_id, secret = C.env("SHOPEE_APP_ID"), C.env("SHOPEE_SECRET")
    base = C.env("SHOPEE_API_BASE", "https://open-api.affiliate.shopee.com.br")
    if not (app_id and secret):
        raise RuntimeError("sem credenciais Shopee")
    body = json.dumps({"query": query})
    ts = int(time.time())
    sign = hashlib.sha256((app_id + str(ts) + body + secret).encode()).hexdigest()
    r = s.post(base.rstrip("/") + "/graphql", data=body.encode(),
               headers={"Content-Type": "application/json",
                        "Authorization": f"SHA256 Credential={app_id}, Signature={sign}, Timestamp={ts}"},
               timeout=_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(str(data["errors"][0].get("message")))
    return data.get("data", {})


def _shopee_candidate(s: requests.Session) -> dict | None:
    fields = "productName itemId priceMin priceMax imageUrl productLink offerLink ratingStar sales"
    try:
        data = _shopee_graphql(
            s, "{ productOfferV2(page: 1, limit: 50) { nodes { %s } } }" % fields)
    except Exception as exc:
        print(f"Shopee indisponível: {exc}")
        return None
    nodes = ((data.get("productOfferV2") or {}).get("nodes")) or []
    best: dict | None = None
    for n in nodes:
        try:
            lo, hi = float(n.get("priceMin") or 0), float(n.get("priceMax") or 0)
        except (TypeError, ValueError):
            continue
        if not lo or not hi or hi <= lo or not n.get("offerLink") or not n.get("imageUrl"):
            continue
        disc = 1 - lo / hi
        if disc < 0.05:
            continue
        if best is None or disc > best["_disc"]:
            best = {"_disc": disc, "node": n, "price": lo, "orig": hi}
    if not best:
        return None
    n = best["node"]
    sales = n.get("sales") or 0
    benefits = []
    try:
        r = float(n.get("ratingStar") or 0)
        if r >= 4.5:
            benefits.append(f"Nota {f'{r:.1f}'.replace('.', ',')} de avaliação")
    except (TypeError, ValueError):
        pass
    if sales and int(sales) >= 100:
        benefits.append(f"+{int(sales):,}".replace(",", ".") + " vendidos")
    return {
        "marketplace": "shopee", "external_id": str(n.get("itemId")),
        "title": str(n.get("productName") or "Oferta Shopee"),
        "price": best["price"], "original_price": best["orig"],
        "discount_pct": round(best["_disc"] * 100),
        "affiliate_url": str(n["offerLink"]),
        "photos": [str(n["imageUrl"])], "benefits": benefits[:3],
    }


# ---------------- Fallback: canal ----------------

def _channel_candidate(s: requests.Session) -> dict | None:
    try:
        r = s.get(f"https://t.me/s/{_CHANNEL}", timeout=_TIMEOUT)
        r.raise_for_status()
        page = r.text
    except Exception as exc:
        print(f"Canal indisponível: {exc}")
        return None
    blocks = re.findall(
        r'<div class="tgme_widget_message_wrap[^>]*>(.*?)<span class="tgme_widget_message_meta">',
        page, re.S)
    for block in reversed(blocks[-15:]):
        text_m = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', block, re.S)
        if not text_m:
            continue
        raw = re.sub(r"<br\s*/?>", "\n", text_m.group(1))
        raw = re.sub(r"<[^>]+>", "", raw)
        text = _html.unescape(raw).strip()
        links = [l for l in _LINK_RE.findall(text + " " + block)
                 if "t.me/" not in l and "telegram" not in l]
        photo_m = re.search(r"background-image:url\('([^']+)'\)", block)
        prices = [float(p.replace(".", "")) for p in _PRICE_RE.findall(text)]
        if not (links and photo_m and len(prices) >= 1):
            continue
        price = min(prices)
        orig = max(prices) if len(prices) >= 2 else price
        disc = round((1 - price / orig) * 100) if orig > price else 0
        if disc < 5:
            continue  # sem desconto real → próximo post
        title = next((l.strip() for l in text.splitlines() if len(l.strip()) > 12), "Oferta do canal")[:90]
        market = "mercadolivre" if "mercadolivre" in links[0] or "meli." in links[0] else "shopee"
        return {
            "marketplace": market, "external_id": f"canal-{hash(links[0]) & 0xffff}",
            "title": title, "price": price, "original_price": orig,
            "discount_pct": disc, "affiliate_url": links[0],
            "photos": [_html.unescape(photo_m.group(1))], "benefits": [],
        }
    return None


# ---------------- main ----------------

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
    s = _session()

    offer = _shopee_candidate(s)
    origem = "shopee-api"
    if not offer:
        print("Shopee sem oferta válida → fallback canal.")
        offer = _channel_candidate(s)
        origem = "canal"
    if not offer:
        print("FALHA: nenhuma oferta (Shopee + canal).", file=sys.stderr)
        return 1
    if not offer.get("affiliate_url"):
        print("FALHA DURA: oferta sem link de afiliado — pipeline parado.", file=sys.stderr)
        return 2

    photos_local: list[str] = []
    for i, url in enumerate(offer["photos"][:3]):
        dest = outdir / f"foto{i+1}.jpg"
        if _download(s, url, dest):
            photos_local.append(str(dest))
    if not photos_local:
        print("FALHA: nenhuma foto pôde ser baixada.", file=sys.stderr)
        return 1

    offer.update({"photos_local": photos_local, "day": day, "origem": origem,
                  "price_label": _brl(offer["price"]),
                  "original_label": _brl(offer["original_price"]),
                  "hook": "Para tudo que eu achei isso aqui!"})
    (outdir / "offer.json").write_text(json.dumps(offer, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": True, "origem": origem, "title": offer["title"][:60],
                      "discount": offer["discount_pct"], "marketplace": offer["marketplace"],
                      "affiliate": offer["affiliate_url"][:70]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
