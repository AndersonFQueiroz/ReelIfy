<![CDATA[<div align="center">

# 🎬 ReelIfy

**Transforme produtos em vídeos virais — automaticamente.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-AI-4285F4?logo=google&logoColor=white)](https://aistudio.google.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Custo](https://img.shields.io/badge/Custo-R%24%200%2C00-brightgreen)]()

</div>

---

**ReelIfy** é um sistema open-source que automatiza a produção de vídeos curtos (~20 segundos) para afiliados. Envie uma foto do produto pelo **Telegram**, e a IA do **Google Gemini** cria um roteiro magnético de alta conversão. O vídeo é então gerado automaticamente no **YouTube Create**, rodando em um celular Android dedicado controlado via **ADB** — tudo sem intervenção manual.

> **100% gratuito.** Sem custos de API, sem assinaturas, sem cartão de crédito.

---

## ✨ Funcionalidades

| Recurso | Descrição |
|:---|:---|
| 🤖 **Bot Telegram** | Interface conversacional para solicitar vídeos a qualquer hora, de qualquer lugar |
| 🧠 **Roteiros com IA** | Google Gemini gera roteiros persuasivos de 20s (Gancho → Problema → Solução → Prova Social → CTA) |
| 📱 **Automação ADB** | Controla o YouTube Create em um celular Android físico via comandos ADB |
| 🔄 **Dois modos** | `/novo_video` (interativo com aprovação) ou `/auto` (enfileira direto) |
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
              1. Envia foto + dados do produto
              7. Recebe vídeo MP4 (20s)
                            ▼
              ┌─────────────────────────────┐
              │   ReelIfy Bot (Telegram)    │
              │     (Async / Polling)       │
              └──────┬──────────────┬───────┘
                     │              │
   2. Gera Roteiro   │              │  3. Enfileira Job
                     ▼              ▼
   ┌──────────────────────┐  ┌──────────────────────┐
   │  Google Gemini API   │  │  Fila de Jobs (JSON) │
   │  (Flash — Gratuito)  │  │  (Persistente)       │
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
│   │   ├── order.py           # Conversação guiada (/novo_video e /auto)
│   │   └── status.py          # Consulta de pedidos (/status)
│   └── services/
│       ├── gemini_service.py  # Geração de roteiro de 20s com Google Gemini
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

| Variável | Onde obter | Custo |
|:---|:---|:---|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) no Telegram → `/newbot` | Gratuito |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) → Get API Key | Gratuito |

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

---

## 🧪 Testes

Execute todos os testes automatizados (funciona sem hardware físico):

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

## 💰 Custo Total: R$ 0,00

| Componente | Custo | Detalhes |
|:---|:---:|:---|
| Google Gemini API | **Grátis** | 1.500 req/dia via [AI Studio](https://aistudio.google.com) — sem cartão de crédito |
| Telegram Bot | **Grátis** | Via [@BotFather](https://t.me/BotFather) |
| YouTube Create | **Grátis** | App oficial do Google para Android |
| ADB (Android Debug Bridge) | **Grátis** | Utilitário open-source do Google |
| Fila Local (JSON) | **Grátis** | Persistência em disco — sem banco em nuvem |

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
]]>
