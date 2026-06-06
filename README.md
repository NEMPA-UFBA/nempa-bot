# Nempa-bot

Projeto em Python: um bot para Discord com cogs modulares e armazenamento local.

## Visão geral

Este repositório contém um bot para Discord organizado em módulos (cogs) e um pequeno servidor HTTP para healthcheck. O bot usa `discord.py` (ou forks compatíveis), `aiohttp` para o healthcheck e `python-dotenv` para carregar variáveis de ambiente.

## Estrutura do projeto

- `main.py` — ponto de entrada do bot; carrega cogs, inicia servidor HTTP e inicia o bot.
- `requirements.txt` — dependências do projeto.
- `cogs/` — diretório com extensões (cogs) separados por responsabilidade:
  - `checkin.py`
  - `daily_challenge.py`
  - `leveling.py`
  - `math_tools.py`
  - `security.py`
- `database/` — módulos relacionados a perguntas, respostas e usuários:
  - `daily_challenge_answers.py`
  - `daily_questions.py`
  - `questions.py`
  - `users.py`

## Variáveis de ambiente necessárias

Duplique o arquivo `.env.sample` na raiz do projeto, nomeando a cópia de `.env` e atribua as variáveis da forma abaixo (exemplo):

DISCORD_TOKEN=
WELCOME_CHANNEL_ID=
ID_CHANNEL_DAILY_CHALLENGE=
ID_CHANNEL_DAILY_CHALLENGE_LOG=
GROQ_API_KEY=
TEAM_ROLE_ID=

Observações:
- `DISCORD_TOKEN` é obrigatório para que o bot consiga se autenticar.
- `WELCOME_CHANNEL_ID` deve ser o ID do canal onde mensagens de boas-vindas serão enviadas.

## Como rodar localmente

1. Crie e ative um ambiente virtual (recomendado):

```bash
python -m venv .venv
source .venv/bin/activate  # Linux / macOS
.venv\Scripts\activate     # Windows PowerShell
```

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Configure o `.env` com as variáveis descritas acima.

4. Inicie o bot:

```bash
python main.py
```

O bot irá carregar automaticamente todos os arquivos `.py` em `cogs/` e iniciar um pequeno servidor HTTP em `0.0.0.0:$PORT` (por padrão `8080`) para healthchecks.

## Endpoints / Comandos

- Healthcheck HTTP: `GET /` → responde `ok` (útil para Uptime monitoring / hostings).
- Comando de exemplo registrado no `main.py`:
  - `/ping` — responde com `Pong!` (comando de aplicação de árvore de comandos)

### Exemplos dos comandos por cog

Abaixo seguem exemplos de uso dos comandos expostos pelos cogs presentes em `cogs/`. Os exemplos são escritos em formato humanizado para você copiar/colar no Discord (slash commands):

- `cogs/daily_challenge.py` (principal conjunto de comandos para gestão e respostas de desafios diários):
  - `/answer_challenge question_id:123 answer: "Minha resposta aqui"`
    - Uso: responder a um desafio que foi publicado; o bot tentará validar automaticamente.
  - `/add_question question:"Texto ou LaTeX" answer:"gabarito" target_date:25/03/2026 team:@Equipe channel:#daily scheduled_time:08:00 is_latex:false image_url:"" limit_reward:3`
    - Uso: (equipe) adiciona uma questão agendada para publicação futura.
  - `/edit_question question_id:123 question:"Novo texto" answer:"novo gabarito"`
    - Uso: (equipe) edita uma questão existente.
  - `/delete_question question_id:123`
    - Uso: (equipe) remove uma questão do banco.
  - `/list_questions team:@Equipe` — lista questões com paginação (apenas equipe/admin).
  - `/send_question_now question_id:123` — envia imediatamente a questão especificada para o canal configurado.

- `cogs/leveling.py` (sistema de XP e ranks):
  - `/give_xp member:@Fulano amount:500` — uso administrativo para doar XP a um membro.
  - `/rank [member:@Fulano]` — mostra nível e XP do membro (ou seu próprio se não informar membro).
  - `/leaderboard` — mostra os top players por XP.

- `cogs/math_tools.py` (ferramentas matemáticas / LaTeX):
  - `/latex formula: $x^2 + 2x + 1 = 0$ size:Normal` — gera uma imagem com o LaTeX renderizado.
    - Observação: use `$...$` para math inline; texto fora de `$` será tratado como texto normal.

- `cogs/security.py` (listeners de segurança / introdução — sem comandos slash):
  - Não expõe slash commands. Comportamento principal:
    - Verifica mensagens no canal de introdução, valida template e comprimento, atribui/remover cargos (`Visitor` → `Member`) automaticamente.

#### Comandos sem utilização

- `cogs/checkin.py` (módulo com funcionalidades de check-in / gerenciamento de perguntas):
  - Atualmente muitos comandos estão presentes como código comentado (ex.: `/checkin`, `/add_question`, `/see_questions`, `/publish_question`).
    - `/checkin senha: "resposta"` — (quando habilitado) faz check-in com senha (responde e atribui cargo).
    - `/see_questions` — (admin) lista perguntas internas com paginação.

## Notas e recomendações

- Garanta que o bot tenha permissões adequadas no servidor (membros, envio de mensagens, gestão de cargos se necessário).
- Para deploy em serviços que exigem porta: deixe a variável `PORT` configurada e permita tráfego TCP na porta para o healthcheck.

## Contribuição

Se quiser contribuir, abra uma issue descrevendo a sugestão ou envie um pull request com pequenas alterações e testes quando aplicável.

---