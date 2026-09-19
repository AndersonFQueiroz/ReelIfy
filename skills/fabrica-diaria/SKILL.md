# SKILL — Fábrica diária: 3 vídeos CaçaOfertas

## Triggers (qualquer variação vale)
`3 videos` · `3 vídeos` · `está na hora de fazer os 3 vídeos` · qualquer frase com "3 vídeos/vídeos".

Ao receber o trigger: **executar direto, sem perguntas**. Orquestrador: `python3 -m factory.run_diaria`.

## Pipeline (ordem fixa)
1. `factory/oferta_do_dia.py` → escolhe o produto do dia (maior desconto ML/Shopee) + **gera os links de afiliado**. Sai `data/factory/<AAAA-MM-DD>/offer.json`.
2. `factory/video_ia.py` → **Vídeo 1 "POV mulher apresentando"** (roteiro §Roteiro V1).
3. `factory/video_cinetico.py` → **Vídeo 2 "Oferta relâmpago"** + **Vídeo 3 "Top achadinho"** (100% locais).
4. `factory/pack_redes.py` → valida e monta `pack.json` (legendas, hashtags, link afiliado, 1º comentário, capas).
5. `factory/qc.py` → **PORTÃO OBRIGATÓRIO**: specs mp4, narração auditada, oferta ≥5% + afiliado. Falhou = nada é enviado.
6. `factory/pack_telegram.py` → entrega no privado do dono (salva `message_id` p/ apagar reprovado).
7. **Buffer SÓ com aprovação explícita do dono aqui no chat** (`post_buffer --only v1,v3`). Nunca automático.

## Fluxo de aprovação (travado)
- "3 videos" → gero e mando **só no Telegram**. Nada no Buffer.
- Dono revisa e fala aqui: "aprovado v1 v3, refaz v2 sem X".
- Reprovado: apago do chat (`deleteMessage` via `telegram_msg_ids`) e refaço.
- Aprovado: posto no Buffer + dono posta no Kwai na mão.

## Setup único do dono (5 min, 1x)
Conta grátis no buffer.com (3 canais) → conectar Instagram + TikTok + YouTube
(login normal, sem review/auditoria) → Settings → API → New key →
colar como `BUFFER_API_KEY` no `.env`. A fábrica sobe o mp4 no Catbox
e agenda 10h/15h/20h (BRT) sozinha.

## Regras duras (nunca violar)
- **NENHUM pack sai sem link de afiliado válido.** Se `affiliate_url` vier vazio, o pipeline PARA e avisa (não gera vídeo mudo de link).
- **NUNCA produto inventado:** vídeo 1 usa image-to-video a partir da FOTO REAL do anúncio; vídeos 2–3 usam as fotos do anúncio.
- **NUNCA commitar segredos:** `.env`, tokens, cookies. Só `offer.json`/`pack.json` (sem tokens).
- Specs: layout 1080×1920 (PIL), **mp4 720×1280** (x264 software nesta máquina
  não dá conta de 1080p; Reels/Shorts/TikTok aceitam 720p), 25–30s, H264 + AAC,
  ≤90s, legenda queimada sempre. Ken Burns via crop animado (zoompan é lento em ARM).
- CTA final de todo vídeo: `👇 @cacaofertasofcbr` (texto puro, sem botão desenhado).

## Identidade visual (travada 18/09)
- Display/títulos/CTA: **Archivo Black + itálico ~12°** (`assets/fonts/ArchivoBlack.ttf`), palavra-chave cyan com glow.
- Textos: **Poppins** Regular/Medium/SemiBold (`assets/fonts/`).
- Fundo: gradiente diagonal marinho-profundo + blobs glow cyan/indigo + ruído + vinheta; texto branco, muted cinza-azulado, destaque cyan.
- Faixa segura: conteúdo entre y=250 e y=1760. Kicker com padding medido (nunca chutar).

## Fontes da oferta (realidade de rede 18/09)
- **Shopee API primeiro** (requer `SHOPEE_APP_ID`/`SECRET` no `.env`).
- **Fallback: canal** (`t.me/s/cacaofertasofcBR`) — reaproveita post real do bot.
- ML direto FORA do v1 (`api.mercadolibre.com` = 403 desta rede).
- IPv6 desta rede pendura conexões → `factory/config.py` força IPv4.

## Vídeo 1 — modo real (18/09)
- HF Inference **sem créditos grátis** (402) → V1 sai em modo **POV cinematográfico**
  por padrão; tenta o clip IA só se `HF_TOKEN` com crédito existir.
- Emojis NUNCA no render PIL (tofu) → `render.safe_text()`; emojis só na legenda do pack.

## Roteiro V1 — "POV mulher apresentando" (~28s)
| Tempo | Visual | Narração (voz feminina `pt-BR-FranciscaNeural`) | Tela |
|---|---|---|---|
| 0–3s | Zoom na foto real + flash | "Para tudo que eu achei isso aqui!" | 🔥 −{DESCONTO}% HOJE |
| 3–10s | Clip IA (image-to-video): mãos femininas usando o produto, POV | Nome + 2 benefícios reais do anúncio | ✓ bullets |
| 10–17s | Clip IA 2: close resultado/em uso | Benefício de uso ("aqui em casa virou...") | palavra-chave cyan |
| 17–23s | Card preço: riscado → atual gigante | "De {DE} por {POR} — menor preço que eu já vi." | R$ DE → **R$ POR** |
| 23–28s | Logo + glow | "Link com desconto tá no canal, corre que acaba!" | 👇 @cacaofertasofcbr |

Prompts IA sempre em inglês, sempre ancorados na foto real. Sem rosto falando (fora do tier grátis).

## Roteiro V2 — "Oferta relâmpago" (~26s)
Flash "⚡ OFERTA RELÂMPAGO" → foto Ken Burns + zoom pulsante, preço riscado→atual → urgência ("só enquanto durar o estoque") + CTA.

## Roteiro V3 — "Top achadinho" (~28s)
"ACHADINHO DO DIA 🔥" → 2–3 fotos alternando (frente/detalhe/em uso) + bullets surgindo → menor preço + CTA.

## Fallbacks (automáticos, sem avisar o dono salvo falha total)
- HF sem crédito/erro → V1 vira POV cinematográfico puro (fotos + voz + partículas).
- Edge-TTS fora → tenta `pt-BR-ThalitaMultilingualNeural`, depois voz `pt-BR-AntonioNeural`.
- Fotos do anúncio inacessíveis → usa a melhor disponível; se zero fotos, PARA e avisa.
- Telegram fora → salva pack em `data/factory/<data>/` e avisa no próximo contato.

## Voz
- V1/V2/V3: `pt-BR-FranciscaNeural` (apresentadora). Fallback: `pt-BR-ThalitaMultilingualNeural` → `pt-BR-AntonioNeural`.
- Ritmo: `+0%`; legendas fatiadas por frase (SRT→ASS, Fonte 20, Alignment 2, MarginV 210).
