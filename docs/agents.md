# Guia para Agentes de IA & Desenvolvedores (agents.md)
**Projeto:** ReelIfy  
**Versão:** 1.0.0 (MVP)  
**Propósito:** Este documento serve como referência e alinhamento de contexto para sessões futuras de agentes de IA (Antigravity, Claude Code, etc.) e desenvolvedores que atuarem neste repositório.

---

## 1. Contexto Essencial do Projeto
- **Objetivo do Negócio:** Criar vídeos curtos (~20 segundos) automatizados para divulgação de produtos por afiliados (ReelIfy).
- **Usuária Principal:** Irmã do criador do projeto (afiliada).
- **Interface do Usuário:** Bot do Telegram (envia foto, dados do produto e link de afiliado; recebe o vídeo final pronto).
- **Geração de Conteúdo:** Google Gemini API (`gemini-1.5-flash` / `gemini-2.0-flash`), 100% gratuita via Google AI Studio com cota de 1.500 req/dia e 1M tokens de contexto, gerando roteiros persuasivos (Gancho, Problema, Solução, Prova Social, CTA).
- **Geração de Vídeo:** Aplicativo **YouTube Create** (disponível exclusivamente para Android/iOS, sem versão desktop), rodando em um celular Android físico dedicado controlado via comandos ADB a partir de um script Python.

---

## 2. Decisões de Arquitetura & Racionais

### 2.1. Desacoplamento Total entre Bot e Automação
- **Decisão:** Separar a pasta `/bot` da pasta `/automation`.
- **Por quê?** O bot precisa estar sempre online (hospedado no Render, VPS ou rodando como serviço) para atender a usuária no Telegram a qualquer hora. O script de automação depende do PC físico ligado e do celular conectado via USB/Wi-Fi. Eles se comunicam exclusivamente através de uma fila (`queue.json` ou endpoints HTTP no modo distribuído).

### 2.2. Fila em JSON com Schema Relacional
- **Decisão:** Iniciar o MVP usando um arquivo `data/queue.json` bem estruturado, com camada de abstração (`QueueService`).
- **Por quê?** Facilita o desenvolvimento inicial sem necessidade de configurar bancos externos. O schema foi desenhado para ser 100% intercambiável com SQLite ou PostgreSQL via SQLAlchemy/Tortoise sem mexer na lógica do bot ou do worker.

### 2.3. Isolamento de Coordenadas de Tela (`coordinates.yaml`)
- **Decisão:** Proibido manter coordenadas de toque `(x, y)` ou nomes fixos de pacotes dentro dos scripts Python. Tudo reside em `config/coordinates.yaml`.
- **Por quê?** O usuário pode trocar de aparelho celular, alterar resolução da tela ou o app YouTube Create sofrer atualizações na UI. A calibração deve ser feita apenas editando o arquivo YAML de coordenadas, sem tocar no código-fonte.

### 2.4. Modo Mock Obrigatório (`MOCK_DEVICE=True`)
- **Decisão:** A automação deve obrigatoriamente suportar execução em modo simulado.
- **Por quê?** Grande parte do desenvolvimento ocorre em ambientes sem o celular físico conectado (ex: terminal Debian/Termux ou servidores remotos). O mock emula cliques ADB, gera vídeos fictícios de teste e permite validar o pipeline de ponta a ponta sem o hardware físico.

### 2.5. Estratégia de Inspeção de Tela
- **Decisão:** Priorizar a inspeção da árvore de acessibilidade (`adb shell uiautomator dump`) em vez de reconhecimento de imagem/OCR puro.
- **Por quê?** O dump XML retorna os textos exatos dos botões e seus estados (`enabled="true"`, `clickable="true"`), sendo imune a variações de escala, modo escuro/claro e iluminação. OCR e Template Matching permanecem apenas como fallback.

---

## 3. Convenções de Código e Padrões

1. **Linguagem:** Python 3.10+.
2. **Tipagem Estrita:** Uso de `typing` (`Optional`, `Dict`, `List`, `Union`) e Dataclasses / Pydantic para validação do payload de jobs.
3. **Assincronismo:** O bot do Telegram deve ser estritamente assíncrono (`async` / `await`) utilizando `python-telegram-bot` v20+.
4. **Gerenciamento de Segredos:** Nunca comitar tokens ou dados sensíveis. Carregar de `.env` usando `python-dotenv`. Manter `.env.example` atualizado.
5. **Tratamento de Exceções:** Toda chamada ADB ou de rede deve ser encapsulada em blocos `try/except` com logging contextualizado contendo o `job_id`. Em caso de erro irrecuperável, o usuário do Telegram deve sempre receber uma mensagem explicativa.
6. **Logging:**
   - Usar `logger = logging.getLogger(__name__)`.
   - Níveis adequados: `DEBUG` para payloads e coordenadas de toques; `INFO` para mudanças de status do pedido; `ERROR` para falhas com stacktrace completo.

---

## 4. Instruções para Agentes de IA em Sessões Futuras

Quando um novo agente iniciar uma sessão neste projeto, deve seguir este protocolo:

1. **Checar o Status dos Arquivos:**
   - Verificar `/docs/requirements.md` e `/docs/specs.md` para entender as definições vigentes.
   - Verificar se o usuário já está com o celular físico em mãos ou se continua trabalhando em ambiente simulado.

2. **Ordem de Implementação Definida:**
   - **Etapa 1:** Configurações e modelos de dados (`config/settings.py`, `config/coordinates.yaml`, schema do Job).
   - **Etapa 2:** Serviço de IA (`bot/services/gemini_service.py`) com gerador de roteiro de 20s.
   - **Etapa 3:** Serviço de Fila (`bot/services/queue_service.py`) com persistência em JSON.
   - **Etapa 4:** Handlers do Telegram Bot (`/start`, `/novo_video`, `/status`).
   - **Etapa 5:** Wrapper ADB com Mock (`automation/adb/device.py` e `automation/mock/mock_device.py`).
   - **Etapa 6:** Orquestrador do YouTube Create e Worker de Polling (`automation/worker.py`).
   - **Etapa 7:** Calibração final das coordenadas quando o hardware físico estiver conectado.

3. **Como Rodar Testes sem Hardware Físico:**
   - Definir `MOCK_DEVICE=True` no ambiente.
   - Executar os testes automatizados da pasta `tests/`.
