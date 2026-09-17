# Reforma: ReelIfy como fábrica de vídeos do CaçaOfertas

**Status:** planejado e aprovado pelo dono em 17/09/2026. Implementação pendente.
**Duplicata eliminada:** a pasta `video-afiliados-automacao/` (clone idêntico
do mesmo commit) foi removida — o canônico é este repo (`ReelIfy`).

## Objetivo

Transformar o ReelIfy na fábrica automática de vídeos curtos (15–25 s,
1080×1920) das ofertas do canal **Caça Ofertas Oficial**
(`t.me/cacaofertasofcBR`), para TikTok/Reels/Shorts/Kwai. Ritmo: 1–3 vídeos/dia.

## Decisões aprovadas (não reabrir sem motivo)

1. **Aprovação manual:** todo vídeo passa por revisão no Telegram antes de liberar.
2. **Custo zero:** narração IA gratuita (**Edge-TTS**, vozes neurais PT-BR, sem
   chave). Roteiro por template a partir dos dados (sem custo de LLM);
   Gemini fica opcional só para variar ganchos.
3. **ADB/YouTube Create mantido como opcional** (`MOCK_DEVICE` segue nos testes).
   O padrão passa a ser render headless no servidor.

## Fases

### A — Higiene (feito)
- [x] Remover `video-afiliados-automacao/` (duplicata exata, mesmo commit).
- [x] Congelar ADB como backend opcional.

### B — Render headless `automation/render/`
- [ ] Slideshow ffmpeg 1080×1920: foto do produto + cards De/Por/%OFF (Pillow) + logo.
- [ ] Narração Edge-TTS PT-BR + música de fundo livre + mux MP4 final.
- [ ] Template fixo: hook de preço (0–2 s) → produto → CTA Telegram.
- [ ] Testes com mocks (roteiro, montagem, MP4 válido).

### C — Alimentação pelo CaçaOfertas
- [ ] Conector **somente-leitura** no SQLite do CaçaOfertas (`posts`/`products`
      com status ready/published) → jobs na fila (título, preços, %OFF, imagem, cupom).
- [ ] Seleção: maior %OFF, frete grátis e selo 30 dias primeiro; nunca repetir `product_id`.
- [ ] Aprovação no Telegram (fluxo `/aprovar` existente); entrega = MP4 + legenda
      pronta + aviso no privado. **Postagem nas plataformas é manual**
      (auto-post fora de escopo: risco de ban).

### D — Operação
- [ ] Render **neste Debian/servidor** (ffmpeg + TTS). O LG segue só com o bot
      (fraco demais para render 1080p).
- [ ] Ritmo 1–3 vídeos/dia dos top descontos.

## Regras

- Nada pago sem aprovação explícita (`VIDEO_PROVIDER_POLICY=free_only` por padrão).
- Sem segredos no git (`.env`, chaves, cookies). Testes offline primeiro.
- Respeitar termos de afiliado Shopee/ML nas legendas (sem alegação falsa).
