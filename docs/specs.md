# Especificação técnica atual

## 1. Componentes

```text
Telegram
   |
bot/main.py
   |-- start.py: acesso, /start e /ajuda
   |-- agent.py: texto, imagem e callbacks de revisão
   v
AgentService
   |-- Gemini: conversa, function calling e visão multimodal
   |-- SQLite/FTS5: sessões e RAG
   |-- QueueService: cria Job somente após aprovação
   v
data/queue.json ---> automation.worker ---> ADB/Mock ---> YouTube Create ---> MP4/Telegram
```

O bot e o worker são processos separados, mas compartilham a pasta `data/`.

## 2. Entradas e comandos

O `bot/main.py` registra:

- `/start`: verifica acesso e mostra a identidade atual do bot via `get_me()`.
- `/ajuda`: guia do usuário comum.
- `/liberar PALAVRA`: autorização persistente por palavra mágica.
- `/novo_video`: inicia/reset a sessão conversacional.
- `/status` e `/pedidos`: consulta pedidos.
- `/cancelar`: abandona a sessão atual e registra aprendizado quando aplicável.
- `/autorizar ID` e `/revogar ID`: administração restrita.

Mensagens de texto, fotos e documentos de imagem são recebidos por handlers globais quando o usuário está autorizado.

## 3. Sessão do agente

`agent_sessions` usa `chat_id` como chave e guarda `state`, `brief_json`, `history_json`, `created_at` e `updated_at`.

Estados utilizados:

- `COLLECTING`: coleta e interpretação do briefing.
- `WAITING_APPROVAL`: prévia enviada; aguarda aprovar, corrigir, regenerar ou cancelar.

O briefing pode conter `product_name`, `benefits`, `target_audience`, `affiliate_link`, `style`, `media_source`, `media_paths`, `provider_id`, `link_destination`, `variation_index` e `script`.

## 4. Gemini e visão

`AgentService._gemini_turn` envia ao Gemini o histórico, briefing, regras recuperadas do RAG e as ferramentas de atualização. Quando existem imagens `.jpg`, `.jpeg`, `.png` ou `.webp` com até 10 MB, elas são anexadas como `Part.from_bytes` com MIME adequado.

Ferramentas declaradas:

- `update_brief`
- `record_user_correction`
- `generate_product_image`
- `select_video_provider`
- `finalize_video_request` (informativa; a aprovação real é validada pela aplicação)

O modelo não cria jobs diretamente. A aplicação valida provedor, mídia e estado antes de qualquer efeito externo. A chamada conversacional tem limite de 12 segundos; falhas usam o fallback local.

## 5. Prévia e aprovação

Quando produto e benefício estão disponíveis, escolhas opcionais recebem defaults. O serviço chama `GeminiService.generate_script`, salva o resultado na sessão e envia:

- gancho, problema, solução, diferencial e CTA;
- texto completo para copiar;
- informação sobre estilo e origem visual;
- botões de aprovação, correção, regeneração e cancelamento.

Correção escrita gera nova versão e incrementa `variation_index`. Aprovação por texto ou botão chama `AgentService.approve`, que transforma a prévia em `Job` e remove a sessão. A prévia original permanece no histórico do Telegram.

## 6. RAG

O banco `data/agent.db` possui:

- `agent_sessions` para estado temporário;
- `rag_documents` para regras e aprendizados;
- `rag_search` como índice FTS5.

O RAG inicial define persona, qualidade, gramática para públicos como pais, CTA sem link na bio por padrão e transparência de imagens sintéticas. Correções são convertidas em regras gerais, deduplicadas e podadas quando a base ultrapassa `MAX_RAG_ITEMS`.

## 7. Job e worker

Campos relevantes do job:

```json
{
  "job_id": "uuid",
  "chat_id": 123,
  "product": {"name": "...", "description": "...", "target_audience": "...", "affiliate_link": "...", "photos_local_paths": []},
  "script": {"hook": "...", "problem": "...", "solution": "...", "proof": "...", "cta": "...", "full_text": "..."},
  "status": "PENDING",
  "provider_id": "adb_youtube_create",
  "style_id": "product_demo",
  "media_source": "real_photo",
  "link_destination": "manual_copy"
}
```

O worker marca `PROCESSING`, valida ADB quando `MOCK_DEVICE=False`, transfere imagens, abre o YouTube Create, insere `full_text`, espera no máximo 300 segundos, exporta, baixa o MP4 e marca `COMPLETED` ou `FAILED`. Em erro, grava diagnóstico e notifica o chat quando possível.

## 8. Provedores

`bot/services/video_providers.py` registra `adb_youtube_create` e `local_ffmpeg` quando disponíveis. O caminho de produção implementado no worker é ADB/YouTube Create; `local_ffmpeg` ainda não é uma rota completa de renderização. APIs HTTP externas exigem um adaptador específico, autenticação, contrato de status e integração no worker.

## 9. Configuração e execução

Variáveis principais: `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_IMAGE_MODEL`, `ALLOWED_CHAT_IDS`, `ADMIN_CHAT_IDS`, `MAGIC_WORD`, `AGENT_DB_PATH`, `QUEUE_FILE_PATH`, `MOCK_DEVICE`, `ADB_DEVICE_SERIAL` e `VIDEO_PROVIDER_POLICY`.

```bash
python3 -m bot.main
python3 -m automation.worker
python3 -m tools.reelify_dashboard
pytest -q
```

O `.env`, a fila real, o banco real e mídias de usuários não devem ser commitados.
