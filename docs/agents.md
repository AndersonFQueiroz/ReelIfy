# Guia para agentes e desenvolvedores

Este documento descreve o comportamento atual do ReelIfy. O código é a fonte de verdade quando houver divergência.

## Visão atual

O sistema possui dois processos independentes:

- `python3 -m bot.main`: bot assíncrono do Telegram.
- `python3 -m automation.worker`: worker que consome `data/queue.json` e automatiza o YouTube Create via ADB.

O bot recebe texto, links, fotos e documentos de imagem em qualquer ordem. O `AgentService` mantém uma sessão por chat, usa Gemini com function calling e visão multimodal quando há imagem, consulta o RAG local e só cria um job depois da aprovação do roteiro.

## Fluxo do agente

1. `/novo_video` inicia ou reinicia a sessão.
2. O usuário conversa livremente; o agente extrai produto, benefícios, público, estilo, mídia, link e destino.
3. Escolhas opcionais recebem defaults seguros: público genérico, demonstração, cópia manual do link, provedor disponível único e placeholder quando não há foto.
4. O agente pergunta apenas o que for indispensável.
5. Uma prévia completa é exibida no Telegram, incluindo texto corrido copiável.
6. O usuário pode aprovar, corrigir escrevendo, regenerar ou cancelar.
7. Somente a aprovação cria um `Job` `PENDING` na fila.

Quando Gemini falha, fica sem chave ou excede o timeout conversacional, o fallback local preserva a sessão e não enfileira automaticamente. Correções aprovadas são transformadas em regras gerais e gravadas no RAG SQLite.

## Arquivos principais

| Arquivo | Responsabilidade |
|---|---|
| `bot/main.py` | Registra comandos, mensagens, fotos e callbacks de revisão |
| `bot/handlers/start.py` | `/start`, `/ajuda`, autorização e revogação |
| `bot/handlers/agent.py` | Entrada multimodal e botões de aprovar/corrigir/regenerar |
| `bot/services/agent_service.py` | Sessão, briefing, RAG, visão, prévia e aprovação |
| `bot/services/gemini_service.py` | Geração estruturada do roteiro e fallback local |
| `bot/services/queue_service.py` | Persistência e estados dos jobs em JSON |
| `bot/services/image_providers.py` | Imagem Gemini opcional e fallback placeholder |
| `bot/services/video_providers.py` | Registro do motor YouTube Create via ADB |
| `automation/worker.py` | Processamento ADB/mock e entrega do MP4 |
| `tools/reelify_dashboard.py` | Dashboard de terminal para fila, acessos e logs |

## RAG

O banco `data/agent.db` contém sessões temporárias, documentos-base e índice FTS5. Regras de persona, gramática, CTA e mídia são semeadas na primeira execução. Ao concluir ou cancelar uma sessão, correções são anonimizadas, generalizadas, deduplicadas e submetidas à poda quando o limite é atingido.

Não guardar tokens, URLs privadas, IDs de chat ou dados pessoais no RAG. Não permitir que o modelo execute ações diretamente: a aplicação valida toda chamada de ferramenta.

## Acesso e operação

- `ALLOWED_CHAT_IDS`: acessos fixos no `.env`.
- `MAGIC_WORD`: libera um chat permanentemente em `authorized_chat_ids.json`.
- `ADMIN_CHAT_IDS`: chats que podem usar `/autorizar` e `/revogar`.
- `/status` e `/pedidos`: consulta de jobs do próprio chat.
- Dashboard: `python3 -m tools.reelify_dashboard`.

## Provedores

O único caminho de produção é ADB + YouTube Create. MOCK_DEVICE=True permite testar o fluxo sem aparelho físico; em produção, MOCK_DEVICE=False exige o celular conectado e autorizado no ADB.

## Regras para alterações

- Preservar o fluxo de aprovação obrigatória.
- Manter mensagens simples e naturais para o usuário final.
- Não perguntar novamente algo presente no texto ou legível na imagem.
- Escapar texto dinâmico nas mensagens Markdown.
- Não comitar `.env`, banco real, fila real ou mídias do usuário.
- Rodar `pytest -q` e `git diff --check` antes do commit.
