# Requisitos atuais do ReelIfy

**Status:** implementação em uso no Telegram
**Runtime:** Python 3.10+
**Persistência:** JSON para a fila e SQLite/FTS5 para sessões e RAG

## Objetivo

Permitir que uma pessoa crie vídeos curtos de produtos por uma conversa natural no Telegram. O agente coleta o mínimo necessário, analisa texto e imagens, gera uma prévia copiável e só envia a produção para a fila após aprovação explícita.

## Requisitos funcionais

### RF01 — Acesso

O bot deve aceitar apenas chats autorizados por `ALLOWED_CHAT_IDS`, autorização persistente ou `/liberar PALAVRA`. `/autorizar` e `/revogar` são administrativos e não aparecem na ajuda do usuário comum.

### RF02 — Conversa livre

O usuário pode iniciar com `/novo_video` e enviar mensagens, links, fotos ou documentos de imagem em qualquer ordem. O agente deve manter uma sessão por chat e aceitar correções durante a conversa.

### RF03 — Visão multimodal

Quando uma imagem real for enviada, o arquivo deve ser encaminhado ao Gemini como conteúdo multimodal. O agente deve tentar ler nome, marca, rótulos e textos legíveis, sem perguntar novamente algo que já foi identificado.

### RF04 — Coleta mínima

Produto e benefícios são os dados essenciais. Público, estilo e destino do link devem ser inferidos ou receber defaults seguros quando não forem necessários. A produção usa exclusivamente YouTube Create via ADB. A ausência de foto deve seguir com placeholder, salvo escolha diferente do usuário.

### RF05 — Roteiro

O Gemini deve gerar `ScriptData` em JSON com `hook`, `problem`, `solution`, `proof`, `cta` e `full_text`. O prompt deve respeitar português brasileiro, naturalidade, fatos fornecidos e CTA com link abaixo, descrição ou comentário fixado.

### RF06 — Revisão obrigatória

Antes de criar um job, o bot deve enviar a prévia completa no chat, incluindo o texto corrido para cópia. O usuário pode:

- aprovar e colocar na fila;
- escrever uma correção;
- regenerar uma versão;
- cancelar.

Nenhuma confirmação implícita ou falha do Gemini pode criar job automaticamente.

### RF07 — RAG e aprendizado

O sistema deve consultar regras de persona, qualidade, gramática, CTA e mídia no RAG SQLite. Ao concluir ou abandonar uma sessão, correções devem ser anonimizadas, generalizadas, deduplicadas e adicionadas quando forem úteis. A base deve podar aprendizados antigos quando atingir o limite.

### RF08 — Fallback

Sem chave, com erro 503 ou timeout do Gemini, o agente deve manter a sessão e usar respostas locais. O timeout conversacional não deve bloquear indefinidamente o Telegram.

### RF09 — Fila

Um job aprovado deve guardar produto, imagens, roteiro, estilo, mídia, destino do link, provedor e chat de origem em `data/queue.json`, iniciando em `PENDING`.

### RF10 — Automação e entrega

O worker deve processar jobs pela fila, transferir imagens via ADB, operar o YouTube Create, aguardar até cinco minutos, baixar o MP4, atualizar o status e entregar o vídeo no Telegram. Em modo mock, o fluxo deve ser testável sem hardware.

### RF11 — Operação

O usuário dispõe de `/start`, `/novo_video`, `/status`, `/pedidos`, `/ajuda` e `/cancelar`. O dashboard de terminal deve listar jobs, detalhes, logs, acessos, autorizações, revogações e limpeza de pedidos expirados.

## Requisitos não funcionais

- Segredos ficam em `.env` e nunca no Git.
- Arquivos recebidos ficam em `data/media/inputs`; saídas em `data/media/outputs`.
- Toda rede, Gemini e ADB devem ter tratamento de exceção e logging contextual.
- O código deve funcionar em Debian/Termux sem interface gráfica quando o hardware e as dependências estiverem disponíveis.
- O bot e o worker devem poder ser executados separadamente.
- O YouTube Create via ADB é o único caminho de produção. Não há APIs externas ou renderização local de vídeo habilitadas.

## Critérios de aceite

1. Uma mensagem contendo produto e benefícios pode gerar a prévia sem formulário rígido.
2. Uma foto com o nome legível é enviada ao Gemini e pode preencher o produto.
3. O job não existe antes da aprovação.
4. Uma correção gera nova versão e fica disponível no RAG após a sessão.
5. Gemini indisponível não perde o briefing nem cria job indevido.
6. `pytest -q` passa sem celular conectado.
