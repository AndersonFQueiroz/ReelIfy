"""Helpers de render: identidade CaçaOfertas + TTS + Ken Burns + legendas PIL.

Tudo local exceto Edge-TTS (grátis). Sem libass: legendas são PNGs sobrepostos.
"""
from __future__ import annotations

import math
import random
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config as C

W, H = 1080, 1920          # layout PIL (textos nítidos)
OUT_W, OUT_H = 720, 1280  # mp4 final (re-encode cabe; Reels aceita 720p)
FPS = 30
SCENE_PAD = 0.7  # respiro após cada narração
NAVY_TOP = (13, 27, 62)
NAVY_BOT = (6, 12, 34)
CYAN = (34, 211, 238)
WHITE = (255, 255, 255)
MUTED = (148, 163, 184)
SAFE_TOP, SAFE_BOT = 250, 1760

# Poppins/Archivo não têm glifos emoji → troca por equivalentes seguros.
_EMOJI_FIX = {"👇": "»", "⚡": "", "🔥": "", "✓": "»", "★": "*", "👀": "",
              "✅": "»", "📲": "", "📌": "", "⚠️": "!", "🎬": ""}
_EMOJI_RE = __import__("re").compile(r"[\U0001F000-\U0001FAFF☀-➿⬅-⬏]+")


def safe_text(text: str) -> str:
    for k, v in _EMOJI_FIX.items():
        text = text.replace(k, v)
    text = _EMOJI_RE.sub("", text)
    return " ".join(text.split())


def sanitize_narration(text: str) -> str:
    """Texto que a voz vai ler: sem emoji, URL ou formatação."""
    text = safe_text(text)
    text = __import__("re").sub(r"https?://\S+", "", text)
    return " ".join(text.split())


def fonts(display_size: int, text_size: int, bold: bool = False):
    disp = ImageFont.truetype(str(C.FONT_DISPLAY), display_size)
    txt = ImageFont.truetype(str(C.FONT_TEXT_BOLD if bold else C.FONT_TEXT), text_size)
    return disp, txt


def make_bg(seed: int = 7) -> Image.Image:
    rnd = random.Random(seed)
    bg = Image.new("RGB", (W, H))
    px = bg.load()
    for y in range(H):
        t = y / H
        px_line = tuple(int(NAVY_TOP[i] + (NAVY_BOT[i] - NAVY_TOP[i]) * t) for i in range(3))
        for x in range(W):
            diag = (x / W) * 0.12
            px[x, y] = tuple(max(0, min(255, int(c - diag * 40))) for c in px_line)
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for _ in range(7):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        r = rnd.randint(300, 560)
        col = CYAN if rnd.random() < 0.6 else (99, 102, 241)
        gd.ellipse([x - r, y - r, x + r, y + r], fill=tuple(c // 2 for c in col))
    bg = Image.blend(bg, Image.composite(glow, Image.new("RGB", (W, H)),
                                         glow.convert("L").point(lambda v: int(v * 0.8))), 1.0)
    bg = bg.filter(ImageFilter.GaussianBlur(60))
    # vinheta
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-W // 3, -H // 4, W + W // 3, H + H // 5], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120)).point(lambda v: 110 + int(v * 0.57))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(bg, black, vig)


def paste_logo(base: Image.Image, cx: int, cy: int, size: int) -> None:
    """Logo centralizada. Se não houver alpha, aplica máscara circular."""
    logo = Image.open(C.LOGO).convert("RGBA").resize((size, size), Image.LANCZOS)
    alpha = logo.getchannel("A")
    if alpha.getextrema()[0] > 250:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([8, 8, size - 8, size - 8], fill=255)
        logo.putalpha(mask)
    base.alpha_composite(logo, (cx - size // 2, cy - size // 2))


def shear_text_layer(layer: Image.Image, angle_deg: float = 12) -> Image.Image:
    """Itálico falso: cisalha a camada de texto."""
    m = math.tan(math.radians(angle_deg))
    w, h = layer.size
    shift = abs(int(m * h))
    big = Image.new("RGBA", (w + 2 * shift, h), (0, 0, 0, 0))
    big.paste(layer, (shift, 0))
    return big.transform((w + 2 * shift, h), Image.AFFINE, (1, m, -m * h / 2, 0, 1, 0),
                         resample=Image.BICUBIC)


def draw_display(base: Image.Image, cx: int, y: int, text: str, size: int,
                 fill=WHITE, accent: str | None = None) -> int:
    """Título Archivo Black itálico centralizado. Retorna y final."""
    text = safe_text(text)
    disp, _ = fonts(size, 40)
    seq: list[tuple[str, tuple]] = []
    if accent and accent in text:
        pre, _, post = text.partition(accent)
        seq = [(pre, WHITE), (accent, CYAN), (post, WHITE)]
    else:
        seq = [(text, WHITE if isinstance(fill, tuple) else WHITE)]
    widths, layer_h = [], 0
    tmp = Image.new("RGBA", (10, 10))
    td = ImageDraw.Draw(tmp)
    for p, _c in seq:
        if not p:
            widths.append(0)
            continue
        bb = td.textbbox((0, 0), p, font=disp)
        widths.append(bb[2] - bb[0])
        layer_h = max(layer_h, bb[3] - bb[1])
    total = sum(widths)
    layer = Image.new("RGBA", (total + 40, layer_h + 40), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    x = 20
    for (p, col), wdt in zip(seq, widths):
        if p:
            for off in [(2, 2), (-2, 2), (2, -2), (-2, -2)]:
                ld.text((x + off[0], 20 + off[1]), p, font=disp, fill=(6, 12, 34, 255))
            ld.text((x, 20), p, font=disp, fill=col + (255,))
        x += wdt
    sheared = shear_text_layer(layer)
    base.alpha_composite(sheared, (cx - sheared.width // 2, y))
    return y + sheared.height


def draw_center_text(base: Image.Image, cx: int, y: int, text: str, size: int,
                     fill=MUTED, bold: bool = False, max_w: int = 940) -> int:
    text = safe_text(text)
    _, txt = fonts(60, size, bold=bold)
    lines = []
    for para in text.split("\n"):
        lines += textwrap.wrap(para, width=max(8, max_w // (size // 2))) or [""]
    d = ImageDraw.Draw(base)
    for line in lines:
        bb = d.textbbox((0, 0), line, font=txt)
        lw = bb[2] - bb[0]
        d.text((cx - lw / 2, y), line, font=txt, fill=fill)
        y += (bb[3] - bb[1]) + 8
    return y


def kicker(base: Image.Image, cx: int, y: int, text: str) -> int:
    """Pílula cyan com padding medido."""
    text = safe_text(text)
    _, txt = fonts(40, 40, bold=True)
    d = ImageDraw.Draw(base)
    bb = d.textbbox((0, 0), text, font=txt)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad_x, pad_y = 34, 18
    d.rounded_rectangle([cx - tw / 2 - pad_x, y, cx + tw / 2 + pad_x, y + th + pad_y * 2],
                        radius=30, fill=CYAN + (255,) if base.mode == "RGBA" else CYAN)
    d.text((cx - tw / 2, y + pad_y), text, font=txt, fill=(6, 12, 34))
    return int(y + th + pad_y * 2)


def fit_photo(photo: Path, box_w: int, box_h: int, radius: int = 36) -> Image.Image:
    im = Image.open(photo).convert("RGB")
    im.thumbnail((box_w * 2, box_h * 2), Image.LANCZOS)
    w, h = im.size
    scale = max(box_w / w, box_h / h)
    im = im.resize((int(w * scale) + 1, int(h * scale) + 1), Image.LANCZOS)
    x = (im.width - box_w) // 2
    y = (im.height - box_h) // 2
    im = im.crop((x, y, x + box_w, y + box_h))
    mask = Image.new("L", (box_w, box_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, box_w, box_h], radius=radius, fill=255)
    out = Image.new("RGB", (box_w, box_h), (6, 12, 34))
    out.paste(im, (0, 0), mask)
    return out


def ff(*args: str) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {r.stderr[-500:]}")


def probe_dur(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-hide_banner", "-loglevel", "error",
                        "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def tts_save(text: str, out: Path, voice: str | None = None) -> float:
    """TTS Edge → mp3. Retorna duração. Tenta vozes em cascata."""
    text = sanitize_narration(text)
    Path(out).with_suffix(".txt").write_text(text, encoding="utf-8")
    voices = [voice or C.VOICE_MAIN, *C.VOICE_FALLBACKS]
    last: Exception | None = None
    for v in dict.fromkeys(voices):
        try:
            subprocess.run(
                ["python3", "-m", "edge_tts", "--voice", v, "--rate=-5%",
                 "--text", text, "--write-media", str(out)],
                capture_output=True, text=True, timeout=120, check=True)
            if out.exists() and out.stat().st_size > 1000:
                return probe_dur(out)
        except Exception as exc:
            last = exc
    raise RuntimeError(f"TTS indisponível: {last}")


def caption_png(text: str, out: Path) -> None:
    text = safe_text(text)
    _, txt = fonts(40, 46, bold=True)
    lines = textwrap.wrap(text, width=26) or [""]
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w = max(tmp.textbbox((0, 0), l, font=txt)[2] for l in lines) + 60
    h = sum(tmp.textbbox((0, 0), l, font=txt)[3] + 12 for l in lines) + 40
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=24, fill=(4, 8, 22, 255))
    y = 22
    for l in lines:
        bb = d.textbbox((0, 0), l, font=txt)
        d.text(((w - (bb[2] - bb[0])) / 2, y), l, font=txt, fill=WHITE + (255,))
        y += (bb[3] - bb[1]) + 12
    img.save(out)


def assemble(scenes: list[dict], out: Path, workdir: Path) -> Path:
    """Monta vídeo: cenas (png+mp3) → zoom leve → concat → legendas → áudio.

    scenes: [{png, mp3, caption}] caption aparece durante a cena.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    durs = [probe_dur(Path(sc["mp3"])) + SCENE_PAD for sc in scenes]
    n = len(scenes)
    # 1) cenas → clips (encode rápido; concat depois é stream-copy)
    clip_paths = []
    for i, sc in enumerate(scenes):
        dur = durs[i]
        clip = workdir / f"clip{i}.mp4"
        # PNG 1080p decodificado 1x → JPG pequeno (decode por frame fica barato)
        small = workdir / f"sc{i}.jpg"
        if not sc.get("clip"):
            ff("-i", str(sc["png"]), "-vf", "scale=800:1422", "-q:v", "3", str(small))
            src = str(small)
        else:
            src = None
        if sc.get("clip") and Path(sc["clip"]).exists():
            ff("-stream_loop", "2", "-i", str(sc["clip"]),
               "-vf", f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
                      f"crop={OUT_W}:{OUT_H},setsar=1,format=yuv420p,fps={FPS}",
               "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "superfast",
               "-crf", "23", "-an", str(clip))
        else:
            total = max(1, int(dur * FPS))
            kb = ("crop=w='800/(1+0.12*n/%d)':h='1422/(1+0.12*n/%d)':"
                  "x='(in_w-out_w)/2':y='(in_h-out_h)/2',"
                  f"scale={OUT_W}:{OUT_H},setsar=1,format=yuv420p,fps={FPS}" % (total, total))
            ff("-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.2f}", "-i", src,
               "-vf", kb,
               "-c:v", "libx264", "-preset", "superfast", "-crf", "23", str(clip))
        clip_paths.append(clip)
        png = workdir / f"cap{i}.png"
        caption_png(sc.get("caption") or "» @cacaofertasofcbr", png)
    # 2) concat sem re-encode
    lst = workdir / "concat.txt"
    lst.write_text("".join(f"file '{c}'\n" for c in clip_paths))
    vcat = workdir / "vcat.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(vcat))
    # 3) legendas + áudio (único encode final)
    cap_inputs = []
    for i in range(n):
        cap_inputs += ["-i", str(workdir / f"cap{i}.png")]
    audios = []
    for sc in scenes:
        audios += ["-i", str(sc["mp3"])]
    vparts, t0 = [], 0.0
    for i in range(n):
        pos = f"overlay=(720-w)/2:1280-h-200:enable='between(t,{t0:.2f},{t0 + durs[i]:.2f})'"
        prev = "[0:v]" if i == 0 else f"[v{i - 1}]"
        vparts.append(f"[{1 + i}:v]format=rgba,scale=600:-1[cap{i}];{prev}[cap{i}]{pos}[v{i}]")
        t0 += durs[i]
    base = 1 + n
    t0 = 0.0
    aparts = []
    for i in range(n):
        ms = int(t0 * 1000)
        aparts.append(f"[{base + i}:0]adelay={ms}|{ms}[a{i}]")
        t0 += durs[i]
    afilter = ";".join(aparts) + ";" + "".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0[aout]"
    cmd = ["-i", str(vcat), *cap_inputs, *audios,
           "-filter_complex", ";".join(vparts) + f";[v{n - 1}]null[vcat];{afilter}",
           "-map", "[vcat]", "-map", "[aout]", "-threads", "8",
           "-c:v", "libx264", "-preset", "superfast", "-crf", "23",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
           "-movflags", "+faststart", str(out)]
    ff(*cmd)
    return out
