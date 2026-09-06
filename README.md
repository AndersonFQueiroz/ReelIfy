<div align="center">

# 🎬 ReelIfy

**Transforme produtos em vídeos virais — automaticamente.**

<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://github.com/AndersonFQueiroz/ReelIfy/actions/workflows/ci.yml"><img src="https://github.com/AndersonFQueiroz/ReelIfy/actions/workflows/ci.yml/badge.svg" alt="CI Tests"></a>
  <a href="https://core.telegram.org/bots"><img src="https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white" alt="Telegram Bot"></a>
  <a href="https://aistudio.google.com"><img src="https://img.shields.io/badge/AI%20Engine-Google%20Gemini-4285F4?logo=google&logoColor=white" alt="Google Gemini"></a>
  <a href="#-arquitetura"><img src="https://img.shields.io/badge/Pipeline-Autonomous%2024%2F7-blueviolet?logo=speedtest&logoColor=white" alt="Pipeline"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
</p>

</div>

---

**ReelIfy** é uma solução de automação ponta a ponta para vídeos curtos (~20 segundos). Pelo **Telegram**, o usuário conversa com um agente de IA, envia texto, links e imagens em qualquer ordem, revisa o roteiro no chat e aprova a produção. O worker produz o vídeo via **ADB** no **YouTube Create** e devolve o MP4 ao Telegram.

> **Automação Escalonável & Alta Eficiência:** Arquitetura robusta de ponta a ponta, projetada para renderizar criativos virais com velocidade e máxima qualidade visual.

---

## ✨ Funcionalidades

| Recurso | Descrição |
|:---|:---|
| 🤖 **Agente Telegram** | Conversa livre para coletar briefing, mídia, estilo e destino do link |
| 🧠 **Gemini com ferramentas** | O agente usa RAG, function calling e gera roteiros adaptados ao estilo solicitado |
| 📱 **Automação ADB** | Controla o YouTube Create em um celular Android físico via comandos ADB |
| 🧠 **Memória RAG** | SQLite local com aprendizados agregados, correções e compactação periódica |
| 🎨 **Estilos flexíveis** | POV, unboxing, antes/depois, demonstração, comparação e outros |
| 📊 **Fila persistente** | Jobs organizados com status (Pendente → Processando → Concluído/Falhou) |
| 🧪 **Modo Mock** | Teste o pipeline inteiro sem celular físico conectado |
| 🔒 **Whitelist** | Controle de acesso por ID do Telegram |

---

## 🏗️ Arquitetura

```
              ┌─────────────────────────────┐
              │     Usuário Afiliado        │
              │       (App Telegram)        │
              └─────────────┬───────────────┘
                            │
              1. Conversa, envia texto e/ou imagem
              7. Recebe vídeo MP4 (20s)
                            ▼
              ┌─────────────────────────────┐
              │   ReelIfy Bot (Telegram)    │
              │     (Async / Polling)       │
              └──────┬──────────────┬───────┘
                     │              │
   2. Analisa e mostra prévia       │  3. Enfileira após aprovação
                     ▼              ▼
   ┌──────────────────────┐  ┌──────────────────────┐
   │  Google Gemini API   │  │  Fila de Jobs (JSON) │
   │ (texto, visão, tools)│  │ (persistente)        │
   └──────────────────────┘  └──────────┬───────────┘
                                        │
                          4. Polling / Fetch Job
                                        ▼
              ┌─────────────────────────────────────┐
              │     ReelIfy Worker (Python)         │
              │     (Notebook 24/7)                 │
              └──────────────────┬──────────────────┘
                                 │
                   5. Comandos ADB (USB/Wi-Fi)
                   6. Pull do vídeo gerado
                                 ▼
              ┌─────────────────────────────────────┐
              │   Celular Android Físico (Slave)    │
              │       App: YouTube Create           │
              └─────────────────────────────────────┘
```

---

## 📁 Estrutura do Projeto

```
ReelIfy/
├── config/
│   ├── settings.py            # Configurações centrais (variáveis de ambiente)
│   └── coordinates.yaml       # Calibração de coordenadas de tela (YouTube Create)
├── bot/
│   ├── main.py                # Ponto de entrada do Bot Telegram
│   ├── handlers/
│   │   ├── start.py           # Boas-vindas e verificação de whitelist
│   │   ├── agent.py            # Conversa livre multimodal
│   │   └── status.py          # Consulta de pedidos (/status)
│   └── services/
│       ├── gemini_service.py  # Geração de roteiro contextual
│       ├── agent_service.py   # Sessões, RAG e function calling
│       ├── image_providers.py # Imagem IA opcional e fallback
│       ├── video_providers.py # Registro de motores sem cobrança automática
│       └── queue_service.py   # Gerenciamento atômico da fila de jobs
├── automation/
│   ├── worker.py              # Polling e orquestração da automação
│   ├── adb/
│   │   └── device.py          # Wrapper ADB (dispositivo físico / mock)
│   └── mock/
│       └── mock_device.py     # Emulador de celular para testes sem hardware
├── data/
│   ├── queue.json             # Fila de pedidos persistente
│   ├── media/inputs/          # Fotos enviadas pelos usuários
│   ├── media/outputs/         # Vídeos finais renderizados
│   └── logs/                  # Logs rotativos de execução
├── tests/                     # Testes automatizados (unitários + integração)
├── docs/                      # Documentação técnica detalhada
├── .env.example               # Template de variáveis de ambiente
├── requirements.txt           # Dependências Python
└── README.md
```

---

## 🚀 Instalação & Configuração

### Pré-requisitos

- **Python 3.10+**
- **pip** (gerenciador de pacotes)

### 1. Clone o repositório

```bash
git clone https://github.com/AndersonFQueiroz/ReelIfy.git
cd ReelIfy
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure as credenciais

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas chaves:

| Variável | Origem | Finalidade |
|:---|:---|:---|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) no Telegram (`/newbot`) | Interface conversacional do bot 24/7 |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) | Motor de inteligência generativa e roteirização |
| `GEMINI_IMAGE_MODEL` | Google AI Studio, opcional | Modelo de imagem; se ausente ou indisponível, usa placeholder |
| `AGENT_DB_PATH` | Local | Banco SQLite do agente e RAG |
| `VIDEO_PROVIDER_POLICY` | Local | `free_only` impede uso automático de provedores pagos |

> **Dica:** Deixe `MOCK_DEVICE=True` para testar sem celular físico conectado.

---

## ▶️ Como Executar

### Iniciar o Bot do Telegram

```bash
python3 -m bot.main
```

### Iniciar o Worker de Automação

```bash
python3 -m automation.worker
```

> ⚠️ **O Worker só produzirá vídeos reais** quando o celular Android estiver conectado e `MOCK_DEVICE=False`. Em modo mock, o pipeline é simulado de ponta a ponta.

### Conversa com o agente

Depois de autorizado, envie qualquer mensagem comum para iniciar uma conversa. Você pode mandar produto, benefícios, público, link e fotos em qualquer ordem. O `/novo_video` reinicia a sessão atual. O agente infere escolhas opcionais seguras, pergunta apenas o necessário e mostra o roteiro completo para copiar, corrigir, regenerar ou aprovar antes de criar o job.

---

## Dashboard de operacao

Para abrir o painel completo no terminal:

```bash
python3 -m tools.reelify_dashboard
```

O menu permite listar e filtrar pedidos, abrir detalhes por ID, consultar roteiros e arquivos, ver usuarios e IDs, autorizar, revogar, consultar logs e limpar pedidos expirados. Para consultas diretas:

```bash
python3 -m tools.reelify_dashboard --once
python3 -m tools.reelify_dashboard --status PENDING
python3 -m tools.reelify_dashboard --pedido ID_OU_PREFIXO
```

## 🧪 Testes

Execute todos os testes automatizados (funciona sem hardware físico):

- ✅ Conversa livre com texto e fotos em qualquer ordem
- ✅ Correções e aprendizados agregados no RAG local
- ✅ Seleção segura de estilo, mídia e provedor

```bash
pytest tests/ -v
```

Os testes incluem:
- ✅ Geração de roteiro via IA (modo fallback offline)
- ✅ Fila persistente (criação, polling, conclusão, falha)
- ✅ Fluxo completo do Worker com MockDevice
- ℹ️ Status informativo sobre disponibilidade de hardware

---

## 📱 Setup do Hardware (Produção)

<details>
<summary><strong>📋 Checklist — Configuração do Celular Android (Slave)</strong></summary>

1. **Habilitar Opções do Desenvolvedor:**
   - `Configurações` → `Sobre o telefone` → Toque 7x em `Número da versão`
2. **Ativar Depuração USB:**
   - `Opções do desenvolvedor` → `Depuração USB` → ✅
3. **Manter tela ligada:**
   - `Opções do desenvolvedor` → `Permanecer ativo enquanto carrega` → ✅
4. **Desativar bloqueio de tela** (PIN/Padrão)
5. **Instalar YouTube Create** pela Play Store e fazer login
6. **Conectar via USB** ao notebook e autorizar a depuração

</details>

<details>
<summary><strong>🖥️ Checklist — Notebook 24/7 (Host)</strong></summary>

1. **Instalar Android Platform Tools** (`adb` no PATH)
2. **Verificar conexão:** `adb devices` deve listar o aparelho
3. **Configurar `.env`:**
   ```env
   MOCK_DEVICE=False
   ```

</details>

<details>
<summary><strong>🎯 Calibração de Coordenadas</strong></summary>

1. No celular, ative `Opções do desenvolvedor` → `Localização do ponteiro`
2. Abra o **YouTube Create** e execute manualmente o fluxo de criar um vídeo
3. Anote as coordenadas `[X, Y]` de cada botão na barra superior
4. Atualize `config/coordinates.yaml` com os valores reais
5. Inicie o worker: `python3 -m automation.worker`

</details>

---

## ⚡ Stack Tecnológica & Arquitetura

| Camada | Tecnologia | Papel no Pipeline |
|:---|:---:|:---|
| **Inteligência Artificial** | Google Gemini (Flash) | Geração do roteiro magnético persuasivo em segundos |
| **Interface do Usuário** | Telegram Bot API (Async) | Recepção de pedidos, aprovação e entrega de mídia |
| **Motor de Renderização** | YouTube Create (Google) | Edição nativa, legendagem automática e efeitos visuais |
| **Ponte de Automação** | Android Debug Bridge (ADB) | Controle de hardware 100% autônomo sem intervenção manual |
| **Fila & Armazenamento** | Atomic Storage Engine | Fila de jobs com retenção programada de 24h e auto-limpeza |

---

## 🗺️ Roadmap

- [x] Bot Telegram com fluxo interativo e autônomo
- [x] Geração de roteiros com Google Gemini (fallback offline)
- [x] Fila persistente com schema migratável (JSON → SQLite)
- [x] Worker de automação com MockDevice para testes
- [x] Testes automatizados sem dependência de hardware
- [ ] Calibração final com celular físico
- [ ] Deploy do bot em VPS/Render (24/7)
- [ ] API REST para modo distribuído (Bot remoto ↔ Worker local)
- [ ] Dashboard web para monitoramento de jobs
- [ ] Suporte a múltiplos celulares (pool de devices)

---

## 🤝 Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/minha-feature`)
3. Commit suas alterações (`git commit -m 'feat: adiciona minha feature'`)
4. Push para a branch (`git push origin feature/minha-feature`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<div align="center">

**Feito com ☕ e automação por [Anderson F. Queiroz](https://github.com/AndersonFQueiroz)**

*Transformando afiliados em criadores de conteúdo — sem esforço.*

</div>
