# Especificação Técnica (specs.md)
**Projeto:** ReelIfy  
**Versão:** 1.0.0 (MVP)  
**Status:** Em Revisão / Planejamento  

---

## 1. Arquitetura do Sistema

```
                      +-----------------------------+
                      |       Usuário Afiliado      |
                      |        (App Telegram)       |
                      +--------------+--------------+
                                     |
                       1. Envia foto + dados do produto
                       7. Recebe vídeo final (20s)
                                     v
                      +-----------------------------+
                      |      Bot Telegram (Async)   |
                      |  (Hospedado no Render / PC) |
                      +-------+--------------+------+
                              |              |
      2. Gera Roteiro (20s)   |              | 3. Enfileira Job
                              v              v
               +-------------------------+    +-------------------------+
               |    Google Gemini API    |    | Fila de Pedidos (Jobs)  |
               | (Gemini Flash - Grátis) |    | (JSON / SQLite / API)   |
               +-------------------------+    +------------+------------+
                                                   |
                                     4. Polling / Fetch Job
                                                   v
                      +-----------------------------------------+
                      |       Worker de Automação Local         |
                      |          (Python no PC Host)            |
                      +--------------------+--------------------+
                                           |
                              5. Comandos ADB (USB/Wi-Fi)
                              6. Pull do vídeo gerado
                                           v
                      +-----------------------------------------+
                      |      Celular Android Físico (Slave)     |
                      |         App: "YouTube Create"           |
                      +-----------------------------------------+
```

---

## 2. Estrutura de Diretórios do Projeto

```
ReelIfy/
├── config/
│   ├── settings.py            # Carregador de variáveis de ambiente (.env)
│   └── coordinates.yaml       # Mapeamento de coordenadas (X, Y) e seletores UI
├── docs/
│   ├── requirements.md        # Requisitos de produto e técnicos
│   ├── specs.md               # Esta especificação técnica
│   └── agents.md              # Convenções para agentes de IA e desenvolvedores
├── bot/
│   ├── __init__.py
│   ├── main.py                # Ponto de entrada do Bot Telegram
│   ├── handlers/              # Handlers de comandos (/start, /novo_video, /status)
│   │   ├── __init__.py
│   │   ├── start.py
│   │   ├── order.py           # Fluxo guiado de criação do pedido
│   │   └── status.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini_service.py  # Integração com Google Gemini API (gratuito)
│   │   └── queue_service.py   # Gerenciamento da fila (JSON/SQLite)
│   └── api/                   # Mini-API HTTP opcional para workers remotos
│       ├── __init__.py
│       └── routes.py
├── automation/
│   ├── __init__.py
│   ├── worker.py              # Loop de polling e orquestração do trabalho
│   ├── adb/
│   │   ├── __init__.py
│   │   ├── device.py          # Wrapper de comandos ADB (com suporte a Mock)
│   │   ├── screen_parser.py   # Leitura de UI (uiautomator dump e OCR fallback)
│   │   └── yt_create.py       # Fluxo passo a passo específico do YouTube Create
│   └── mock/                  # Emulador de celular para testes sem hardware
│       ├── __init__.py
│       └── mock_device.py
├── data/
│   ├── queue.json             # Fila persistente em formato JSON (MVP)
│   ├── media/                 # Armazenamento temporário de fotos e vídeos
│   │   ├── inputs/            # Imagens recebidas dos usuários
│   │   └── outputs/           # Vídeos baixados do celular prontos para envio
│   └── logs/                  # Logs rotativos da aplicação
├── tests/
│   ├── test_bot.py
│   ├── test_gemini_service.py
│   └── test_adb_flow.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 3. Estrutura de Dados da Fila (Schema JSON / SQLite)

A fila é modelada de maneira compatível para transição direta entre arquivo JSON e tabelas relacionais (SQLite / PostgreSQL).

### 3.1. Definição dos Status do Job
- `PENDING`: Pedido recebido e roteiro gerado; aguardando worker do PC.
- `PROCESSING`: Worker iniciou o trabalho com o celular Android.
- `COMPLETED`: Vídeo gerado, transferido para o PC e entregue ao usuário no Telegram.
- `FAILED`: Ocorreu uma falha no fluxo de automação ou geração.

### 3.2. Schema do Job (JSON)
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "chat_id": 123456789,
  "user_name": "afiliada_maria",
  "product": {
    "name": "Fritadeira Elétrica Air Fryer X",
    "description": "Cozinha sem óleo, 4.5L, painel digital, fácil de limpar",
    "target_audience": "Mães ocupadas e pessoas práticas",
    "affiliate_link": "https://shopee.com.br/link-afiliado-exemplo",
    "photo_local_path": "data/media/inputs/9b1deb4d_produto.jpg",
    "photo_telegram_file_id": "AgACAgEAAxkBAAI..."
  },
  "script": {
    "full_text": "Você ainda perde tempo limpando panela cheia de gordura? Conheça a Air Fryer X! Com 4.5 litros e painel digital, ela prepara suas refeições na metade do tempo e sem uma gota de óleo. Mais de 10 mil pessoas já trocaram o fogão por ela. Garanta a sua com desconto exclusivo no link da minha bio agora mesmo!",
    "hook": "Você ainda perde tempo limpando panela cheia de gordura?",
    "problem": "Ninguém merece ficar esfregando panela gordurosa depois de um dia cansativo.",
    "solution": "Com a Air Fryer X você faz tudo na metade do tempo e sem óleo.",
    "proof": "Mais de 10 mil clientes já aprovaram.",
    "cta": "Clique agora no link da bio e aproveite a promoção limitada!"
  },
  "status": "PENDING",
  "attempts": 0,
  "max_attempts": 3,
  "created_at": "2026-09-06T10:30:00Z",
  "started_at": null,
  "completed_at": null,
  "output_video_path": null,
  "error_details": null
}
```

---

## 4. Contrato de Comunicação entre Bot e Automação

O sistema prevê dois modos de operação idênticos em interface:

### Modo A: Standalone / Unificado (Ideal para desenvolvimento e MVP)
- O Bot e o Worker rodam no mesmo ambiente (ou compartilham a pasta `data/`).
- O serviço `QueueService` lê e grava diretamente em `data/queue.json` com lock de arquivo (`filelock`).

### Modo B: Distribuído (Bot no Render + Worker no PC Windows)
O Bot no Render expõe endpoints REST protegidos por token de segurança (`WORKER_API_SECRET`):
- `GET /api/jobs/next`: Retorna o próximo job `PENDING` e o transiciona para `PROCESSING`.
- `GET /api/jobs/{job_id}/photo`: Faz o download do arquivo de imagem do produto.
- `POST /api/jobs/{job_id}/complete`: Envia metadados e o arquivo de vídeo concluído (ou notifica conclusão para o bot disparar o envio ao Telegram).
- `POST /api/jobs/{job_id}/fail`: Reporta falha com detalhes para notificação ao usuário.

---

## 5. Especificação da Geração de Roteiro (Google Gemini API - Gratuito)

### 5.1. Configuração do Modelo e Limites Gratuitos
- **Provedor:** Google AI Studio (chave gratuita sem cartão).
- **Modelo:** `gemini-1.5-flash` ou `gemini-2.0-flash` (latência ultrabaixa e geração instantânea).
- **Cota Gratuita:** 15 RPM (requisições por minuto) e até 1.500 RPD (requisições por dia).
- **Janela de Contexto:** 1.000.000 tokens (permite enviar descrições extensas de produtos e até a imagem em alta resolução diretamente no payload multimodal).
- **Formato de Resposta Obrigatório:** `application/json` nativo via `response_mime_type="application/json"` ou Pydantic schema, eliminando riscos de parsing ou markdown indesejado.
- **Temperatura:** 0.7.

### 5.2. System Instruction e Diretrizes do Prompt
```text
Você é um copywriter de elite especializado em roteiros de alta conversão para vídeos curtos de 20 segundos (YouTube Shorts, Reels, TikTok) para produtos de afiliados.
Sua missão é criar um roteiro magnético, persuasivo, dinâmico e natural para ser narrado ou exibido no vídeo do produto.

REGRAS RÍGIDAS DE DURAÇÃO:
- O roteiro completo deve ter entre 45 e 55 palavras faladas no total (ritmo perfeito para exatamente 20 segundos de fala natural).
- Português brasileiro fluente, persuasivo e sem clichês vazios.

ESTRUTURA OBRIGATÓRIA (EM 5 PARTES):
1. Gancho / Hook (0 a 3s): Pergunta provocativa ou afirmação impactante que interrompe o scroll imediatamente.
2. Problema (3 a 8s): Apresentação vívida da dor ou frustração diária do público-alvo.
3. Solução (8 a 14s): Apresentação do produto e seu benefício principal transformador.
4. Prova Social / Diferencial (14 a 17s): Validação de autoridade, economia, praticidade ou satisfação de clientes.
5. Chamada para Ação / CTA (17 a 20s): Ordem clara para clicar no link de afiliado disponível na bio/descrição.

SCHEMA JSON DE RESPOSTA:
{
  "hook": "string",
  "problem": "string",
  "solution": "string",
  "proof": "string",
  "cta": "string",
  "full_text": "string (texto corrido completo unificado pronto para narração)"
}
```

---

## 6. Mapeamento e Sequência de Comandos ADB

### 6.1. Variáveis e Mapeamento de Coordenadas (`coordinates.yaml`)
As coordenadas são parametrizadas de acordo com a resolução do celular slave (exemplo de baseline 1080x2400):

```yaml
device:
  resolution: "1080x2400"
  package_name: "com.google.android.apps.youtube.creator"
  temp_phone_dir: "/sdcard/Download/reelify_temp/"

coordinates:
  # Telas e botões do YouTube Create (placeholders a serem calibrados)
  btn_new_project: [540, 2200]       # Botão "+" de criar novo projeto
  tab_images: [350, 400]             # Aba de Fotos no seletor de mídia
  first_image_thumbnail: [180, 550]  # Miniatura da foto mais recente
  btn_import_media: [900, 2250]      # Botão Importar / Avançar
  btn_add_voice_or_ai: [800, 1800]   # Botão de ferramenta de narração/IA
  input_text_script: [540, 1200]     # Caixa de texto do prompt/roteiro
  btn_generate: [540, 2100]          # Botão "Gerar Vídeo / Concluir"
  btn_export_menu: [1000, 150]       # Três pontinhos ou botão Exportar no topo
  btn_export_confirm: [540, 1900]    # Confirmação de qualidade/exportação

ui_selectors:
  btn_export_text: "Exportar"
  btn_done_text: "Concluído"
  generation_progress_id: "com.google.android.apps.youtube.creator:id/progress_bar"
```

### 6.2. Sequência de Comandos Executados pelo Worker
1. **Acordar e destravar:**
   ```bash
   adb shell input keyevent KEYCODE_WAKEUP
   adb shell wm dismiss-keyguard
   adb shell svc power stayon true
   ```
2. **Transferir a foto do produto:**
   ```bash
   adb shell mkdir -p /sdcard/Download/reelify_temp/
   adb push data/media/inputs/order_123.jpg /sdcard/Download/reelify_temp/product.jpg
   # Forçar reescaneamento de mídia para a foto aparecer imediatamente na galeria do app
   adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Download/reelify_temp/product.jpg
   ```
3. **Iniciar o app YouTube Create:**
   ```bash
   adb shell am force-stop com.google.android.apps.youtube.creator
   adb shell monkey -p com.google.android.apps.youtube.creator -c android.intent.category.LAUNCHER 1
   ```
4. **Inserção de Roteiro:**
   - Enviar texto do roteiro via área de transferência ou digitação rápida com caractere de escape:
   ```bash
   # Alternativa segura para textos longos e com acentuação:
   adb shell am broadcast -a clipper.set -e text "TEXTO_DO_ROTEIRO"  # caso app clipper esteja instalado
   # Ou via adb shell input text tratando espaços e acentos
   ```
5. **Monitoramento do Término da Geração:**
   - O worker executa a cada 5 segundos:
   ```bash
   adb shell uiautomator dump /sdcard/window_dump.xml
   adb shell cat /sdcard/window_dump.xml
   ```
   - O parser busca pela string "Concluído", "Salvo" ou pelo sumiço do `progress_bar`.
6. **Download do Vídeo:**
   ```bash
   adb pull /sdcard/Movies/YouTubeCreate/video_final.mp4 data/media/outputs/order_123.mp4
   ```
7. **Limpeza do Celular:**
   ```bash
   adb shell rm -f /sdcard/Download/reelify_temp/product.jpg
   adb shell rm -f /sdcard/Movies/YouTubeCreate/video_final.mp4
   adb shell am force-stop com.google.android.apps.youtube.creator
   ```

---

## 7. Tratamento de Erros, Timeouts e Diagnóstico

- **Timeout Máximo de Renderização:** 300 segundos (5 minutos). Caso a tela de conclusão não seja detectada dentro do tempo limite, o processo é abortado.
- **Screenshot de Falha:** Em qualquer exceção, o worker captura a tela atual:
  ```bash
  adb exec-out screencap -p > data/logs/error_<job_id>.png
  ```
- **Fallback de Retry:** O sistema tenta até 2 vezes reprocessar o pedido caso o erro seja classificado como transiente (ex: app fechou sozinho). Se falhar novamente, o status passa para `FAILED` e a notificação é disparada.
