# TEMPLATE VITRINE — congelado ✅

Padrão oficial dos 3 vídeos/dia. Mudar só: produtos, fotos, narração, preços.

## Estrutura (5 cenas, ~30s, 720×1280, H264+AAC)
1. **Capa:** pílula cyan `EDIÇÃO #N` + "ACHADINHOS DO DIA" + `PARTE X DE 3` +
   data por extenso (`SEXTA-FEIRA • 19 DE SETEMBRO`) + **logo 480px** + handle.
   Narração fala dia e parte. Edição incrementa só em ofertas novas
   (`edicao.json`; 19/09 = #1).
2. **3 cards produto:**
   - Nome em caps espaçadas (Poppins SemiBold, encolhe até caber 920px)
   - Pílula creme `#FAF3E4`: preço Archivo Black 72 marinho + "LINK NO CANAL"
   - Foto 860×820 com sombra, do fim da pílula até perto do `@`
   - **SEM legenda queimada no card** (preço/nome já estão no layout)
3. **Final:** "ENTRA NO CANAL" + QR `t.me/cacaofertasofcBR` + "Aponta a câmera. É de graça!"

## Regras duras
- Foto nunca invade zona de legenda/rodapé (fundo ≤ y1450 em 1920).
- Legenda queimada: só capa/cards-finais e final (nunca sobre foto).
- Emojis só no pack Telegram, nunca no render (`safe_text`).
- 9 produtos/dia distintos (`usados.json`), 9 links distintos (QC barra).
- Narração feminina −5%, ≤40 palavras/cena, sem emoji/URL (`sanitize_narration`).

## Infra
- Oferta: Shopee API (top desconto) → fallback canal. ML direto fora (403).
- Host de vídeo: Telegram `sendVideo→getFile→deleteMessage` (HEAD honesto;
  catbox mente `content-length: 0` e o TikTok rejeita).
- Post: Buffer GraphQL — IG `metadata.instagram={type:reel}`,
  YT `metadata.youtube={title,categoryId:22}`. Slots 13/18/23 UTC (10h/15h/20h BRT).
## 1º comentário padrão (travado)
👇 CANAL GRÁTIS NO TELEGRAM: copia esse link → t.me/cacaofertasofcBR
As ofertas saem primeiro lá! 🔥 + 3 links numerados.
IG tenta automático (`firstComment`; se o Free rejeitar, segue na legenda).
TikTok/Kwai: sem API de comentário — colar na mão (texto no pack).
YouTube: links na DESCRIÇÃO (campo descrição, nunca título!) — https:// vira
clicável sozinho. Título curto sempre.
- Kwai: manual via pack Telegram. Nenhuma ferramenta suporta.
