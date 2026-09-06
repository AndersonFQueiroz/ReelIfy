# Requisitos do Sistema (requirements.md)
**Projeto:** ReelIfy  
**Versão:** 1.0.0 (MVP)  
**Status:** Em Revisão / Planejamento  

---

## 1. Visão Geral do Produto
O sistema tem como objetivo automatizar a produção de vídeos curtos (~20 segundos) para divulgação de links de produtos por afiliados. A solução utiliza o **Telegram** como canal de entrada e saída para o usuário, a **Google Gemini API** (modelo `gemini-1.5-flash` ou `gemini-2.0-flash`, gratuita via Google AI Studio com cota de 1.500 requisições/dia e contexto de 1 milhão de tokens) para criar roteiros persuasivos e uma **estação de automação local (PC + Celular Android físico)** controlada via **ADB (Android Debug Bridge)** para operar o aplicativo **YouTube Create**.

O sistema é desenhado de forma desacoplada para permitir que:
1. O usuário solicite o vídeo de qualquer lugar via celular/Telegram.
2. A automação no PC físico processe os vídeos na fila de forma assíncrona e resiliente.
3. Não haja dependência direta do hardware durante o desenvolvimento da camada de bot e regras de negócio.

---

## 2. Requisitos Funcionais (RF)

### 2.1. Módulo Bot do Telegram (Interface & Orquestração)
- **RF01 - Recepção de Pedidos:** O bot deve permitir que o usuário inicie um pedido de criação de vídeo coletando:
  - Nome do produto.
  - Descrição / principais benefícios / diferenciais.
  - Público-alvo (opcional ou guiado).
  - Link de afiliado (para inclusão no CTA / metadados).
  - Foto do produto em alta resolução (enviada como imagem ou documento).
- **RF02 - Whitelist e Controle de Acesso:** O bot deve permitir execução apenas de IDs do Telegram previamente autorizados (`ALLOWED_CHAT_IDS`), rejeitando interações não autorizadas para proteger cotas de API e recursos de hardware.
- **RF03 - Geração de Roteiro com IA:** Ao receber os dados completos, o bot deve invocar a **Google Gemini API** (modelo gratuito `gemini-1.5-flash` ou `gemini-2.0-flash`) com um prompt estruturado para gerar um roteiro de exatamente 20 segundos, contendo:
  - *Gancho (0-3s):* Chamada de atenção impactante.
  - *Problema (3-8s):* Ponto de dor do público-alvo.
  - *Solução (8-14s):* Apresentação do produto.
  - *Prova Social / Benefício Extra (14-17s).*
  - *Chamada para Ação / CTA (17-20s):* Indicação para clicar no link da bio/descrição.
- **RF04 - Enfileiramento de Pedidos:** Os pedidos gerados devem ser salvos em uma fila persistente com status inicial `PENDING`, armazenando identificador único (`job_id`), dados do produto, texto do roteiro, identificador/caminho da imagem e metadados de data/hora.
- **RF05 - Consulta de Status:** O usuário deve poder consultar o status do seu pedido a qualquer momento via comando `/status` ou `/pedidos`, recebendo mensagens como: *Na fila (posição X)*, *Em processamento no celular*, *Vídeo concluído* ou *Falha com motivo*.
- **RF06 - Notificação de Entrega:** Quando a automação finalizar a extração do vídeo, o bot deve enviar o arquivo de vídeo diretamente no chat do usuário (`sendVideo` ou `sendDocument` caso exceda 50 MB), acompanhado do roteiro em texto e do link de afiliado formatado.
- **RF07 - Notificação de Falha:** Em caso de erro irrecuperável na automação (ex: falha de renderização, app travado, timeout), o usuário deve receber um aviso detalhado e amigável, e o status na fila deve ser atualizado para `FAILED`.

### 2.2. Módulo de Automação Local (PC + Celular Android via ADB)
- **RF08 - Polling da Fila de Trabalho:** O script de automação no PC deve verificar periodicamente (intervalo configurável, ex: a cada 30 segundos) a existência de pedidos com status `PENDING`.
- **RF09 - Trava de Concorrência (Locking):** Ao selecionar um pedido para execução, o worker deve alterar imediatamente seu status para `PROCESSING` para evitar duplicidade de processamento.
- **RF10 - Preparação do Dispositivo Android:** Antes de interagir com o app, o script deve validar a conectividade ADB, acordar a tela do aparelho caso esteja apagada e destrancar a tela.
- **RF11 - Transferência de Mídia (adb push):** A imagem do produto referente ao pedido deve ser transferida do PC para o armazenamento interno do celular (ex: `/sdcard/Download/reelify_temp/`) com nome previsível.
- **RF12 - Controle do Aplicativo YouTube Create:** O script deve acionar os passos necessários no app:
  - Iniciar o app via intent (`monkey` ou `am start`).
  - Navegar até o criador de projetos / Shorts.
  - Selecionar a foto transferida no seletor de mídia.
  - Inserir/colar o texto do roteiro gerado no campo apropriado de narração/geração.
  - Acionar o botão de geração/renderização.
- **RF13 - Monitoramento de Renderização:** O worker deve checar continuamente o progresso da geração (polling de tela com timeout de segurança de até 5 minutos).
- **RF14 - Exportação e Resgate do Vídeo (adb pull):** Após a conclusão da geração, o worker deve acionar a exportação no app, aguardar a gravação no disco do celular, copiar o vídeo para o PC via `adb pull` e verificar a integridade do arquivo baixado (tamanho > 0 bytes).
- **RF15 - Limpeza e Reset:** O worker deve remover a foto temporária e o vídeo exportado do celular para evitar esgotamento de armazenamento, e fechar o app (`am force-stop`) preparando o aparelho para a próxima execução.

---

## 3. Requisitos Não-Funcionais (RNF)

- **RNF01 - Desacoplamento Arquitetural:** O Bot (que recebe as solicitações) e o Worker de Automação (que controla o celular) devem ser sistemas autônomos. A comunicação deve ser feita por interface padronizada (API REST ou arquivo/banco compartilhado), permitindo que o bot rode em nuvem (ex: Render) ou na mesma máquina local sem alterações na lógica central.
- **RNF02 - Parametrização de Coordenadas de Tela:** Nenhuma coordenada física de clique (`(x, y)`) ou seletor visual deve ser inserida como valor fixo (*hardcoded*) no código Python. Todas as coordenadas devem ser carregadas a partir de um arquivo de configuração externo (`coordinates.yaml` / `.json`), permitindo calibrar qualquer resolução de tela facilmente.
- **RNF03 - Modo de Simulação / Mock para Desenvolvimento:** A automação deve possuir uma flag (`MOCK_DEVICE=True`) que emula as etapas do ADB (criação de arquivos fictícios, delays controlados e sucesso/falha simulados) para permitir desenvolvimento e testes de fluxo em qualquer máquina (incluindo Linux/Termux), sem a necessidade do celular ou do PC Windows estarem conectados.
- **RNF04 - Estrutura de Logging e Rastreabilidade:** Todos os componentes devem registrar logs estruturados com timestamp, nível (DEBUG, INFO, WARNING, ERROR) e identificador do pedido (`job_id`). Em caso de erro na tela do celular, o sistema deve tirar automaticamente um screenshot de diagnóstico e salvá-lo localmente para auditoria.
- **RNF05 - Resiliência a Conexões e Quedas:** O worker deve tolerar desconexões temporárias do cabo USB ou ADB wireless, tentando restabelecer o servidor ADB (`adb kill-server && adb start-server`) antes de abortar uma tarefa.
- **RNF06 - Segurança de Segredos:** Tokens do Telegram, chave de API do Google Gemini (`GEMINI_API_KEY`) e senhas devem ser lidos obrigatoriamente de variáveis de ambiente (`.env`), nunca commitados no repositório.

---

## 4. Dependências Externas & Pré-Requisitos

### 4.1. Serviços e Contas
- **Google Gemini API (Google AI Studio):** Chave de API 100% gratuita gerada em `aistudio.google.com` (sem necessidade de cartão de crédito). Oferece cota gratuita de 15 requisições por minuto (RPM) e até 1.500 requisições por dia (RPD), além de uma janela de contexto gigante de 1 Milhão de tokens — garantindo folga total para o volume diário de vídeos.
- **Telegram BotFather:** Bot criado com token de API válido e comandos registrados (`/start`, `/novo_video`, `/status`, `/ajuda`).
- **Conta Google:** Conta logada no app YouTube Create no celular Android dedicado.

### 4.2. Hardware Físico (Ambiente de Produção)
- **Celular Android Dedicado (Slave):**
  - Sistema Android 9.0 ou superior.
  - Modo de Desenvolvedor ativado.
  - Opção **Depuração USB** ativada.
  - Opção **Permanecer ativo enquanto carrega** ativada (para a tela não desligar durante o trabalho).
  - Bloqueio de tela (PIN/Padrão) desativado ou configurado para não trancar durante a sessão.
- **PC / Notebook de Automação (Host):**
  - Sistema operacional Windows (ou Linux com ADB configurado).
  - Android Platform Tools (`adb`) instalado e no `PATH` do sistema.
  - Cabo USB confiável com suporte a dados e energia.

---

## 5. Limitações Conhecidas & Riscos Mitigados

| Risco / Limitação | Impacto | Mitigação no Projeto |
| :--- | :--- | :--- |
| **Atualizações na interface do YouTube Create** | Botões mudam de posição ou estilo, quebrando cliques. | Coordenadas e seletores isolados em arquivo de configuração (`coordinates.yaml`); uso preferencial de identificadores de árvore (`uiautomator`) antes de coordenadas cegas; screenshots automáticos salvos em falhas. |
| **Suspensão / Hibernação no Render Free** | O Render hiberna após 15 min sem tráfego HTTP. | Estrutura de fila com suporte a API REST leve para acordar sob demanda, ou modo de execução unificado no próprio PC host caso o usuário prefira não depender da nuvem. |
| **Esgotamento de Memória / Armazenamento no Celular** | O celular trava após dezenas de vídeos gerados. | Rotina de limpeza mandatória (`adb shell rm`) executada ao final de cada ciclo (`finally`), garantindo limpeza de arquivos temporários e encerramento forçado do app (`force-stop`). |
| **Cotas ou lentidão na IA do YouTube Create** | A geração de vídeo pode demorar mais que o previsto ou exibir avisos de cota. | Timeout elástico com checagem periódica do estado da tela, com teto máximo (ex: 5 minutos). Caso atinja o teto, aborta com status claro e notifica o usuário no Telegram. |
| **Conexão USB instável** | O ADB pode perder a comunicação no meio de um comando. | Wrapper Python com retry exponencial e validação prévia de `adb devices` antes de iniciar qualquer ciclo de trabalho. |
