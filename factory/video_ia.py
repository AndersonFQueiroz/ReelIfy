"""Vídeo 1 "POV mulher apresentando": B-roll IA (HF grátis) + voz feminina.

Tenta image-to-video a partir da FOTO REAL (HF_TOKEN). Qualquer falha →
fallback POV cinematográfico puro (fotos + Ken Burns + voz). Nunca inventa produto.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from . import config as C
from . import render as R
from .video_cinetico import base_scene, clean_title, handle_footer, price_card, short_name

PROMPT_TPL = (
    "POV shot, a woman's hands {action} in a bright modern home, "
    "photorealistic, smooth natural motion, vertical video"
)


def _hf_clip(photo: Path, action: str, out: Path) -> bool:
    token = C.env("HF_TOKEN")
    if not token:
        return False
    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(token=token)
        with open(photo, "rb") as f:
            blob = f.read()
        video = client.image_to_video(
            blob, prompt=PROMPT_TPL.format(action=action),
            model=C.env("HF_VIDEO_MODEL", "Lightricks/LTX-Video-0.9.8-13B-distilled"))
        data = video if isinstance(video, bytes) else video.read()
        if len(data) < 50_000:
            return False
        out.write_bytes(data)
        return R.probe_dur(out) >= 2.0
    except Exception as exc:
        print(f"HF indisponível ({exc}) → fallback POV.")
        return False


def _photo_scene(photo: Path, seed: int, title_top: str | None = None) -> Image.Image:
    bg = base_scene(seed)
    y = 300
    if title_top:
        y = R.draw_center_text(bg, R.W // 2, y, title_top, 46, fill=R.WHITE, bold=True) + 30
    box_h = 980 if title_top else 1180
    bg.alpha_composite(R.fit_photo(photo, 880, box_h).convert("RGBA"), (100, y))
    handle_footer(bg)
    return bg


def build(offer: dict, outdir: Path) -> tuple[Path, str]:
    """Retorna (mp4, modo: 'ia' ou 'pov')."""
    outdir.mkdir(parents=True, exist_ok=True)
    name = short_name(offer["title"])
    ben = offer.get("benefits") or []
    photos = [Path(p) for p in offer["photos_local"]]
    b1 = ben[0] if len(ben) > 0 else f"{offer['discount_pct']}% de desconto hoje"
    b2 = ben[1] if len(ben) > 1 else "oferta verificada agora"

    work = outdir / "work"
    ai1, ai2 = work / "ai1.mp4", work / "ai2.mp4"
    use_ai = (_hf_clip(photos[0], f"holding and showing {clean_title(name)}", ai1)
              and _hf_clip(photos[-1], f"using {clean_title(name)}, close-up result", ai2))
    modo = "ia" if use_ai else "pov"

    scenes = []
    # S1 hook
    bg = base_scene(31)
    y = R.draw_display(bg, R.W // 2, 480, f"-{offer['discount_pct']}% HOJE", 110,
                       accent=f"{offer['discount_pct']}%")
    bg.alpha_composite(R.fit_photo(photos[0], 840, 640).convert("RGBA"), (120, y + 50))
    R.draw_center_text(bg, R.W // 2, y + 740, name, 44, fill=R.WHITE, bold=True)
    handle_footer(bg)
    p1 = outdir / "v1s1.png"
    bg.convert("RGB").save(p1)
    scenes.append((p1, f"{offer['hook']} {name}, com {offer['discount_pct']} por cento de desconto!",
                   f"🔥 -{offer['discount_pct']}% HOJE"))
    # S2/S3: clip IA ou foto
    for i, (txt, cap) in enumerate([
        (f"Olha só: {b1}.", "✓ " + b1[:34]),
        (f"E o melhor: {b2}.", b2[:36]),
    ]):
        if use_ai:
            png = outdir / f"v1s{i+2}.png"
            _photo_scene(photos[min(i, len(photos) - 1)], 32 + i).convert("RGB").save(png)
            scenes.append((png, txt, cap, [ai1, ai2][i]))
        else:
            png = outdir / f"v1s{i+2}.png"
            _photo_scene(photos[min(i, len(photos) - 1)], 32 + i).convert("RGB").save(png)
            scenes.append((png, txt, cap))
    # S4 preço + CTA
    bg = base_scene(34)
    y = R.draw_center_text(bg, R.W // 2, 420, f"De {offer['original_label']} por", 54, fill=R.MUTED, bold=True)
    y = price_card(bg, y + 10, offer["original_label"], offer["price_label"])
    R.draw_center_text(bg, R.W // 2, y + 40, "Link com desconto tá no canal,\ncorre que acaba!", 50, fill=R.WHITE)
    handle_footer(bg)
    p4 = outdir / "v1s4.png"
    bg.convert("RGB").save(p4)
    scenes.append((p4, f"De {offer['original_label']} por {offer['price_label']}. Link com desconto tá no canal, corre que acaba!",
                   offer["price_label"]))

    rendered = []
    for j, sc in enumerate(scenes):
        png, nar, cap = sc[0], sc[1], sc[2]
        mp3 = outdir / f"v1s{j+1}.mp3"
        R.tts_save(nar, mp3)
        item = {"png": png, "mp3": mp3, "caption": cap}
        if len(sc) == 4:
            item["clip"] = sc[3]
        rendered.append(item)
    out = outdir / "video1-pov.mp4"
    R.assemble(rendered, out, work)
    return out, modo
