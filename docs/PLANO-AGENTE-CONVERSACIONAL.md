# Plano do agente conversacional do Reelify

## Resumo

Transformar o Reelify de um formulário fixo em um agente conversacional multimodal. O Gemini conversa naturalmente com o usuário, recupera regras e aprendizados no RAG, coleta o briefing, escolhe estilo e provedor, chama ferramentas controladas pela aplicação e dispara a produção somente quando o pedido estiver completo.

O Gemini suporta function calling, mas a aplicação executa as funções e valida seus argumentos. Veo não será tratado como gratuito: a documentação oficial informa que ele está no nível pago do Gemini API. APIs externas só poderão ser usadas quando houver quota gratuita explicitamente configurada.

Decisões: conversa livre global; `/novo_video` como início/reset; `/auto` e o formulário antigo deixam de ser o fluxo principal; RAG em SQLite local; somente aprendizados agregados; escolha do provedor em cada pedido; nunca cobrar automaticamente; ADB/YouTube Create preservado; sem foto oferece imagem IA, placeholder ou ausência de mídia; perguntar o destino do link.

## Arquitetura

- Criar `AgentService` e sessão por `chat_id`, aceitando texto, fotos e documentos em qualquer ordem.
- Armazenar o briefing estruturado (`CreativeBrief`) e estados `COLLECTING`, `WAITING_MEDIA_CHOICE`, `WAITING_PROVIDER`, `WAITING_LINK_DESTINATION`, `WAITING_REVIEW`, `SUBMITTED`, `COMPLETED`, `ABANDONED` e `FAILED`.
- Usar chamadas assíncronas do SDK `google.genai`, histórico da sessão e function calling com validação no lado Python.
- Ferramentas: `update_brief`, `request_missing_information`, `generate_product_image`, `select_video_provider`, `generate_script`, `regenerate_script`, `finalize_video_request`, `prepare_affiliate_copy` e `record_user_correction`.
- `finalize_video_request` só executa com produto, descrição/benefícios, público, decisão de mídia, estilo, provedor e link (ou recusa explícita) definidos.

## RAG e aprendizado

- Criar `data/agent.db` com documentos-base, estilos, aprendizados agregados, sessões temporárias, mensagens ativas e índice FTS5.
- Popular regras de personalidade, português brasileiro, CTA com link abaixo/descrição, transparência de imagem IA e estilos de vídeo.
- Após sessão concluída, abandonada ou com erro, sintetizar correções e padrões sem guardar conversa completa, URLs, IDs ou dados pessoais.
- Correções alteram imediatamente o briefing/roteiro atual e podem gerar regra generalizada para sessões futuras.
- Compactar ao atingir o limite definido: mesclar semelhantes, remover duplicados e reduzir a um conjunto de regras canônicas recentes e relevantes.

## Conteúdo e mídia

- Evoluir `ScriptData` para cenas com tempo, narração, direção visual, texto na tela e transições.
- Criar templates `pov`, `unboxing`, `before_after`, `product_demo`, `comparison`, `testimonial`, `problem_solution`, `offer` e `custom`.
- Criar `ImageProvider`; sem foto, oferecer geração IA, placeholder ou continuar sem mídia quando suportado, sempre informando se a imagem é sintética.
- CTA padrão: link abaixo, descrição ou comentário fixado conforme destino escolhido; nunca recomendar automaticamente “link na bio”.

## Provedores de vídeo

Criar a interface `VideoProvider` com `is_available`, `supports`, `submit`, `get_status`, `download_result` e `cancel`.

- `adb_youtube_create`: encapsula o worker atual.
- `local_ffmpeg`: alternativa local gratuita e independente de celular.
- `external_http_provider`: adaptador opcional, exibido apenas com quota gratuita configurada.
- Veo fica desabilitado sob `free_only`, sem promessa de gratuidade.

O `DeliveryService` receberá a conclusão, enviará o MP4 com mensagem natural, estilo, provedor e bloco copiável do link. Se o Gemini falhar, haverá mensagem determinística.

## Segurança e testes

- Validar todas as ferramentas, limitar arquivos, sessões e frequência, impedir caminhos arbitrários e nunca habilitar cobrança.
- Testar conversa livre, dados fora de ordem, fotos, ausência de foto, correções, estilos, RAG, poda, fallback do Gemini, provedores indisponíveis, ADB/mock, links para YouTube e cópia manual.
- Preservar a fila JSON atual e adicionar `schema_version`, `provider_id`, `style_id`, `media_source`, `link_destination`, `scenes` e `agent_session_id` para compatibilidade.
- Documentar novas variáveis de ambiente e manter os comandos `/start`, `/ajuda`, `/novo_video`, `/status`, `/pedidos` e `/cancelar`.
