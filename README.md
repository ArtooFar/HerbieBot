# HERBIE

Assistente pessoal no Discord para agenda, tarefas, notificações, cronogramas e integração com Google Calendar/Google Tasks.
É um LLM Agêntico baseado na estrutura do Gemini.

## Aviso importante sobre o escopo do projeto

Este projeto é **focado para uso pessoal**.

Ele **não foi estruturado para múltiplos usuários ao mesmo tempo**. A arquitetura atual herda a base de um projeto conversacional cujo objetivo era manter um **"cérebro único"** para lidar com as mensagens, então a memória e parte do estado do agente são **compartilhados**.

Na prática, isso significa que publicar o bot para várias pessoas pode causar comportamento incorreto, mistura de contexto, memória compartilhada entre conversas e decisões inadequadas do assistente.

Se a ideia for transformar isso em um bot multiusuário de verdade, o projeto precisa ser refatorado para isolar contexto, memória, preferências, arquivos e estado por usuário/sessão.

## O que ele faz

- conversa com você por DM ou menção no Discord;
- cria, lista, edita e remove eventos do Google Calendar;
- cria, lista, atualiza e conclui tarefas do Google Tasks;
- suporta múltiplas contas Google (por exemplo: pessoal e institucional);
- sincroniza eventos/tarefas para notificações por DM;
- gera cronogramas visuais em imagem;
- mantém um resumo persistido da conversa para continuidade.

## Stack

- Python 3.13
- `discord.py`
- Gemini via `google-genai`
- Google Calendar API
- Google Tasks API
- `python-dotenv`

## Estrutura do projeto

```text
core/
  internals/          # núcleo do agente
  tools/              # ferramentas de agenda, tarefas, notificações, contas Google e cronogramas
  notifications/      # runtime de notificações e sync com Google
  output_handlers/    # saída para Discord/console
  visual/             # renderer de cronogramas
prompts/              # prompts do sistema e resumo
credentials/          # credenciais OAuth e tokens Google (não subir)
data/                 # arquivos gerados em runtime (não subir)
discord_bot.py        # ponto de entrada do bot
```

## Pré-requisitos

- Python 3.13 instalado
- uma aplicação/bot no Discord com token
- um projeto no Google Cloud com:
  - Google Calendar API ativada
  - Google Tasks API ativada
  - credenciais OAuth Desktop App criadas
- conta com acesso para testar o bot por DM

## Instalação

### 1. Clonar o projeto

```bash
git clone https://github.com/ArtooFar/HerbieBot.git
cd <PASTA_DO_PROJETO>
```

### 2. Criar ambiente virtual

No Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

No Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Criar pastas necessárias

```text
credentials/
credentials/google_tokens/
data/
data/cronogramas/
data/discord_media/
```

### 5. Criar o arquivo `.env`

Use um `.env` local. Não suba esse arquivo para o GitHub.

Exemplo:

```env
GEMINI_API_KEY= #Preencher
DISCORD_TOKEN= #Preencher
MODEL_NAME=gemini-2.5-flash
SUMMARY_MODEL_NAME=gemini-2.5-flash-lite
SEARCH_MODEL_NAME=gemini-2.5-flash

GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_PROJECT_ID=
GOOGLE_OAUTH_REDIRECT_URI=http://localhost

GOOGLE_OAUTH_CREDENTIALS_PATH= #Criar arquivos -> Sugestão: ./credentials/google_credentials.json
GOOGLE_OAUTH_TOKEN_PATH= #Criar arquivos -> Sugestão: ./credentials/google_token.json
GOOGLE_DEFAULT_TIMEZONE=America/Bahia
GOOGLE_CALENDAR_PRIMARY_ID=primary

DISCORD_DM_USER_ID= #Preencher (Preferencialmente)

# opcional:
# DISCORD_DM_CHANNEL_ID=ID_DO_CANAL_DM
HERBIE_NOTIFICATION_STORE_PATH=./data/herbie_notifications.json
HERBIE_NOTIFICATION_POLL_SECONDS=15
HERBIE_GOOGLE_SYNC_INTERVAL_SECONDS=180
HERBIE_GOOGLE_SYNC_LOOKAHEAD_DAYS=14
HERBIE_SYNC_CALENDAR_IDS=primary
HERBIE_SYNC_TASK_LIST_IDS=
HERBIE_TASK_REMINDER_HOUR=9
HERBIE_TASK_REMINDER_MINUTE=0
```

## Arquivos que você precisa criar/configurar

### Obrigatórios

- `.env`
- `credentials/google_credentials.json`
- `credentials/google_tokens/` (pasta)
- `data/`
- `data/cronogramas/`
- `data/discord_media/`

### Gerados em runtime

- `credentials/google_token.json`
- `credentials/google_accounts.json`
- `credentials/google_tokens/*.json`
- `data/herbie_notifications.json`
- `data/conversation_summary.txt`
- `discord.log`

## Como configurar o Google

1. Vá ao Google Cloud Console.
2. Ative:
   - Google Calendar API
   - Google Tasks API
3. Crie credenciais OAuth do tipo **Desktop App**.
4. Baixe o JSON e salve como:

```text
./credentials/google_credentials.json
```

5. Na primeira vez que o bot tentar acessar Calendar/Tasks, o fluxo OAuth será aberto no navegador.
6. O token autorizado será salvo localmente na pasta `credentials/`.

## Como rodar

```bash
python discord_bot.py
```

## Como usar

- fale com o bot por DM no Discord; ou
- mencione o bot em um servidor.

Exemplos de pedidos:

- “marca dentista terça às 10”
- “me lembra de pagar a fatura amanhã”
- “lista meus eventos da semana”
- “cria um cronograma de estudo até sexta”
- “conecta minha conta institucional do Google”

## Recursos principais

### Agenda

- criar eventos
- listar agenda
- editar compromissos
- remover eventos
- lidar com recorrência
- sugerir horários e detectar conflitos

### Tarefas

- criar tarefas
- listar tarefas
- atualizar status
- definir prazo
- sincronizar vencimentos com notificações

### Notificações

- lembretes por DM no Discord
- sincronização com Google Calendar e Google Tasks
- armazenamento local deduplicado

### Múltiplas contas Google

- conectar várias contas
- definir conta padrão
- usar conta pessoal e institucional no mesmo bot

### Cronogramas

- gerar cronogramas estruturados
- renderizar imagem em tabela/grade

## Limitações atuais

- o projeto é voltado para **uso pessoal**, não para operação com vários usuários ao mesmo tempo;
- a memória do agente e parte do estado são **compartilhados**, por causa da arquitetura herdada de um projeto com lógica de “cérebro único”;
- depende de execução local contínua para enviar notificações;
- tokens e estado ficam em arquivos locais;
- o primeiro fluxo OAuth exige navegador no ambiente onde o bot está rodando;
- o bot usa estado local para DM padrão, então a primeira interação por DM ajuda a “amarrar” o destino das notificações.
