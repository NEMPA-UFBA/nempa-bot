"""
cogs/daily_challenge.py

- Loop a cada minuto envia questões agendadas automaticamente
- /answer_challenge  → membros respondem
- /dc_add /dc_edit /dc_delete /dc_list /dc_send_now → gestão pela equipe

Renderização LaTeX via QuickLaTeX (render_latex de cogs.math_tools).
Verificação de respostas via Groq (gratuito).
"""

import io
import os
import json
from datetime import datetime
import discord
from discord.ext import commands, tasks
from discord import app_commands
from cogs.math_tools import render_latex
from database.daily_challenge_answers import db_daily_challenge_answer
from database.daily_questions import db_daily_question, DailyQuestionDbManager
import pytz
import groq
from cogs.leveling import add_xp, RANKS

# ── Configuração ──────────────────────────────────────────────────────────────
BAHIA_TZ = pytz.timezone("America/Bahia")

ID_CHANNEL_DAILY_CHALLENGE     = int(os.getenv("ID_CHANNEL_DAILY_CHALLENGE"))
ID_CHANNEL_DAILY_CHALLENGE_LOG = int(os.getenv("ID_CHANNEL_DAILY_CHALLENGE_LOG"))
ID_CHANNEL_LOG = int(os.getenv("ID_CHANNEL_LOG", "1478507673459753053"))  # canal genérico de logs (fallback)

MEMBER_ROLE_ID = int(os.getenv("MEMBER_ROLE_ID", "1466191571266572371"))
TEAM_ROLE_ID   = [int(rid) for rid in os.getenv("TEAM_ROLE_ID", "").split(",") if rid.strip().isdigit()]

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = groq.Client(
    api_key=GROQ_API_KEY,
)


# ── Verificação de resposta via GROQ ────────────────────────────────────────

async def check_answer(question: str, expected: str, given: str) -> tuple[bool, str]:
    """
    Usa o GROQ para verificar se `given` é uma resposta correta para `question`,
    considerando `expected` como gabarito.

    Retorna (is_correct: bool, feedback: str).
    Em caso de erro na API, retorna (None, mensagem_de_erro) — o caller decide o que fazer.
    """
    prompt = f"""
    Question:
    {question}

    Expected answer (gabarito):
    {expected}

    Student's answer:
    {given}
    """

    system_instruction = """
    You are an automated, strict, but fair math and logic grading assistant. Your sole purpose is to compare a student's answer against an expected answer and output a JSON evaluation.

### ABSOLUTE CONSTRAINTS (CRITICAL)
1. NEVER reveal, hint at, or state the expected answer.
2. NEVER explain the logic, steps, or formulas used in the expected answer.
3. NEVER provide examples of correct answers.
4. Do not attempt to solve the problem yourself; treat the provided expected answer as the absolute truth.
5. If the answer is wrong, your feedback must be purely generic, focusing only on the fact that the answer is incorrect, without correcting it.

### EVALUATION RULES
- MARK TRUE: If the student's answer is mathematically equivalent or a valid example that satisfies the question (e.g., "50,000,003" is equivalent to "50 000 003"; or "7 and 3" when any valid pair is acceptable).
- MARK FALSE: If the student's answer is wrong, incomplete, vague, or does not perfectly satisfy the question. Be strict.

### FEEDBACK GUIDELINES (WHEN INCORRECT)
To ensure no leakage of the solution, use generic feedback. 
- GOOD FEEDBACK EXAMPLES: "Your final calculation is incorrect.", "The answer does not satisfy all conditions of the problem.", "Check your unit conversions or formatting.", "Incomplete answer."
- BAD FEEDBACK EXAMPLES (NEVER DO THIS): "You forgot to divide by 2.", "Your answer is 4, but it should be higher.", "The correct answer is 5.", "You need to use the Pythagorean theorem."

### OUTPUT FORMAT
Respond in the SAME LANGUAGE as the question, Portuguese/BR or English.
Respond ONLY with a valid JSON object. Do not include markdown formatting like ```json or any text outside the JSON structure. Use this exact schema:

{
  "correct": boolean,
  "feedback": "string (empty if correct; strictly generic and safe explanation if false)"
}
"""


    try:
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": system_instruction,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
            max_completion_tokens=400,
            reasoning_effort="low",
            stream=False,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "answer_check",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "correct": {"type": "boolean"},
                            "feedback": {"type": "string"},
                        },
                        "required": ["correct", "feedback"],
                        "additionalProperties": False,
                    }
                }
            }
        )
        try:
            print(f"[Groq] Resposta bruta: {response}")
            print(f"[Groq] Resposta text: {response.choices[0].message.content}")

            result = json.loads(response.choices[0].message.content or "{}")
        
        except json.JSONDecodeError as e:
            print(f"[Groq] Erro ao parsear JSON: {e} — raw: {response.choices[0].message.content!r}")
            return None, f"Erro ao interpretar resposta do Groq: {e}"

        return result['correct'], result['feedback']

    except (json.JSONDecodeError, KeyError) as e:
        print(f"[Groq] Falha ao parsear resposta: {e} — raw: {response.choices[0].message.content!r}")
        return None, "Não foi possível verificar a resposta automaticamente."
    except Exception as e:
        print(f"[Groq] Erro inesperado: {e}")
        return None, "Erro inesperado ao verificar a resposta."


# ── Builders de embed ─────────────────────────────────────────────────────────

async def _build_question_embeds(
    q_id: int,
    q_text: str,
    is_latex: bool,
    image_url: str | None,
) -> tuple[list[discord.Embed], list[discord.File]]:
    """
    Retorna (embeds, files) prontos para channel.send(embeds=..., files=...).

    Casos:
      texto            → 1 embed,  0 files
      texto + imagem   → 1 embed,  0 files  (set_image com URL externa)
      latex            → 1 embed,  1 file
      latex + imagem   → 2 embeds, 1 file
    """
    footer = f"Use /answer_challenge to answer  •  ID: {q_id}"
    files: list[discord.File] = []

    main = discord.Embed(title="🧩 New Challenge", color=discord.Color.orange())
    main.set_footer(text=footer)

    if is_latex:
        result = await render_latex(q_text)
        if isinstance(result, str):
            main.description = f"⚠️ Failed to render LaTeX:\n{result}\n\n```{q_text}```"
        else:
            file = discord.File(fp=io.BytesIO(result), filename="question.png")
            files.append(file)
            main.description = ""
            main.set_image(url="attachment://question.png")
    else:
        main.description = q_text.replace("\\n", "\n")
        if image_url:
            main.set_image(url=image_url)

    embeds = [main]

    if is_latex and image_url:
        img_embed = discord.Embed(color=discord.Color.orange())
        img_embed.set_image(url=image_url)
        img_embed.set_footer(text=footer)
        embeds.append(img_embed)

    return embeds, files


async def _build_answer_embed(
    question_id: int,
    author: discord.Member,
    timestamp: datetime,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"📝 Answer to challenge #{question_id}",
        color=discord.Color.green(),
        timestamp=timestamp,
    )
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    return embed


# ── Helpers gerais ────────────────────────────────────────────────────────────
def _parse_date_br(value: str) -> str | None:
    try:
        return datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None

def _format_date_br(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return value

def _now_bahia() -> datetime:
    return datetime.now(BAHIA_TZ)

def _has_team_role(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    return any(r.id in TEAM_ROLE_ID for r in interaction.user.roles)

def _has_member_role(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    return any(r.id in (MEMBER_ROLE_ID, TEAM_ROLE_ID) for r in interaction.user.roles)

# ── View de revisão manual ───────────────────────────────────────────────────

class ReviewView(discord.ui.View):
    """
    Botões de ✅ Correto / ❌ Errado exibidos no log quando a IA não conseguiu
    verificar a resposta automaticamente. Só a equipe/admin pode clicar.
    """
    def __init__(self, member: discord.Member, answer_record_id: int, role_id: int):
        super().__init__(timeout=None)  # persiste até ser clicado
        self.member           = member
        self.answer_record_id = answer_record_id
        self.role_id          = role_id

    def _is_team(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        return any(r.id == self.role_id for r in interaction.user.roles)

    async def _resolve(self, interaction: discord.Interaction, correct: bool):
        if not self._is_team(interaction):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        # Atualiza o embed do log para refletir a decisão
        embed = interaction.message.embeds[0]
        embed.colour = discord.Color.green() if correct else discord.Color.red()
        embed.title  = f"{'✅' if correct else '❌'} Manual revision — {embed.title.split('—', 1)[-1].strip()}"

        for i, field in enumerate(embed.fields):
            if field.name == "Correct?":
                embed.set_field_at(i, name="Correct?",
                                   value=f"{'✅ Yes' if correct else '❌ No'} (reviewed by {interaction.user.mention})",
                                   inline=True)
                break

        # Notifica o membro sobre a decisão
        try:
            if correct:
                await self.member.send(
                    f"✅ Your pending answer has been reviewed and marked as **correct** by the team!")
            else:
                db_daily_challenge_answer.delete_answers_by_id(self.answer_record_id)
                await self.member.send(
                    f"❌ Your pending answer has been reviewed and marked as **incorrect** by the team.")
        except discord.Forbidden:
            pass  # DMs fechadas

        # Desativa os botões após a decisão
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✅ Correct", style=discord.ButtonStyle.success)
    async def mark_correct(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._resolve(interaction, correct=True)

    @discord.ui.button(label="❌ Incorrect", style=discord.ButtonStyle.danger)
    async def mark_wrong(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._resolve(interaction, correct=False)


# ── Paginador ─────────────────────────────────────────────────────────────────

class QuestionPaginator(discord.ui.View):
    PER_PAGE = 5

    def __init__(self, db: DailyQuestionDbManager, team_id: str = None):
        super().__init__(timeout=180)
        self.db = db
        self.page = 0
        self.total = db.count_by_team(team_id) if team_id else db.count()
        self.max_pages = max(1, (self.total - 1) // self.PER_PAGE + 1)
        self.team_id = team_id

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="📋 Questions", color=0xFE6C00)
        rows = ()
        if self.team_id:
            print(f"[QuestionPaginator] Fetching questions for team_id={self.team_id}, page={self.page}")
            rows = self.db.get_all_by_team(team_id=self.team_id, limit=self.PER_PAGE, offset=self.page * self.PER_PAGE)
            print(f"[QuestionPaginator] Fetched {len(rows)} rows for team_id={self.team_id}")
        else:
            print(f"[QuestionPaginator] Fetching all questions, page={self.page}")
            rows = self.db.get_all(limit=self.PER_PAGE, offset=self.page * self.PER_PAGE)
            print(f"[QuestionPaginator] Fetched {len(rows)} rows for all teams")
            
        for q_id, q_text, q_answer, q_date, q_time, q_pub, q_limit, q_latex, q_img, channel_id, added_by_team_id in rows:
            print(f"[QuestionPaginator] Processing question {q_id} added by team {added_by_team_id}")
            
            status    = "✅ Published" if q_pub else "⏳ Pending"
            date_br   = _format_date_br(q_date)
            limit_str = f"Early bird: {q_limit}" if q_limit is not None else "No limit"

            tags = []
            if q_latex: tags.append("🔢 LaTeX")
            if q_img:   tags.append("🖼️ Image")
            tag_str = "  •  " + "  •  ".join(tags) if tags else ""

            preview = q_text[:120] + ("…" if len(q_text) > 120 else "")

            embed.add_field(
                name=f"ID {q_id}  •  📅 {date_br}  •  ⏰ {q_time}  •  {status}{tag_str}",
                value=f"```{preview}```\n`Answer: {q_answer}`  •  {limit_str}",
                inline=False,
            )
            
            embed.add_field(
                name="Channel",
                value=f"<#{channel_id}>",
                inline=True,
            )
            
            embed.add_field(
                name="Added by",
                value=f"Team ID: <@&{added_by_team_id}>" if added_by_team_id else "N/A",
                inline=True,
            )

        embed.set_footer(text=f"Page {self.page + 1}/{self.max_pages}  •  Total: {self.total}")
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.page < self.max_pages - 1:
            self.page += 1
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()


# ── Cog ───────────────────────────────────────────────────────────────────────

class DailyChallenge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._check_pending.start()

    def cog_unload(self):
        self._check_pending.cancel()

    # ── Loop automático ───────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def _check_pending(self):
        now       = _now_bahia()
        today_str = now.strftime("%Y-%m-%d")
        time_str  = now.strftime("%H:%M")
        
        print(f"[Question] Checking for pending questions at {today_str} {time_str}...")

        pending = db_daily_question.get_pending_for_now(today_str, time_str)
        if not pending:
            return


        for q_id, q_text, _, _limit, _q_time, is_latex, image_url, channel_id  in pending:
            channel = self.bot.get_channel(int(channel_id))
            print(f"[Question] Found pending question {q_id} for channel {channel_id}. Sending...")
            if not channel:
                print("[Question] Channel not found.")
                return
            embeds, files = await _build_question_embeds(q_id, q_text, bool(is_latex), image_url)
            await channel.send(embeds=embeds, files=files)
            db_daily_question.update(q_id, published=True)
            mode = " + ".join(filter(None, [
                "LaTeX" if is_latex else "text",
                "image" if image_url else "",
            ]))
            print(f"[Question] Question {q_id} ({mode}) sent at {time_str}")

    @_check_pending.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    # ── /answer_challenge ─────────────────────────────────────────────────────

    @app_commands.command(name="answer_challenge",
                          description="Answer the daily challenge")
    @app_commands.describe(
        question_id="ID of the question (shown in the footer of the challenge)",
        answer="Your answer (text or LaTeX)"
    )
    async def answer_challenge(self, interaction: discord.Interaction,
                               question_id: int, answer: str):
        if not _has_member_role(interaction):
            await interaction.response.send_message(
                "❌ You are not a member yet. "
                "Complete your introduction in the introduction channel!",
                ephemeral=True)
            return


        question = db_daily_question.get_by_id(question_id)
        if not question or not question[5]:  # index 5 = published
            await interaction.response.send_message(
                "❌ Question not found or not yet published.", ephemeral=True)
            return

        if interaction.channel_id != int(question[12]):  # index 12 = channel_id
            await interaction.response.send_message(
                f"❌ Use the channel <#{question[12]}> to answer.",
                ephemeral=True)
            return
        is_latex = bool(question[7])  # index 7 = is_latex

        if db_daily_challenge_answer.check_user_answered_question(
                interaction.user.id, question_id):
            await interaction.response.send_message(
                f"❌ You already answered question **#{question_id}**!", ephemeral=True)
            return

        # Defer antes da chamada ao Groq (pode levar alguns segundos)
        await interaction.response.defer(ephemeral=True)

        q_text   = question[1]  # index 1 = question text
        expected = question[2]  # index 2 = expected answer

        is_correct, feedback = await check_answer(q_text, expected, answer)
        # is_correct, feedback = None, "Simulação: resposta marcada como correta (substitua pela chamada real ao check_answer)"

        # Se a API falhou (None), notifica a equipe mas não penaliza o usuário
        if is_correct is None:
            print(f"[DailyChallenge] Groq unavailable for question {question_id}: {feedback}")
            await interaction.followup.send(
                f"⚠️ Could not verify your answer automatically now. "
                f"The team will review manually.\n> {feedback}",
                ephemeral=True)
            # Registra mesmo assim para revisão manual no log
            is_correct = None  # sinaliza revisão pendente

        if is_correct is False:
            await interaction.followup.send(
                f"❌ Incorrect answer.\n> {feedback}",
                ephemeral=True)
            return

        # ── Resposta correta (ou pendente de revisão) ─────────────────────────
        db_daily_challenge_answer.save_challenge_answer(
            interaction.id, interaction.user.id, answer, question_id)

        status_msg = "✅ Correct answer!" if is_correct else "⏳ Answer sent for review."
        await interaction.followup.send(
            f"{status_msg}\n> {feedback}" if feedback else status_msg,
            ephemeral=True)
        
        if is_correct:
           await add_xp(interaction.user.id, 100, member=interaction.user)  # recompensa XP por resposta correta

        # Log
        log_channel = self.bot.get_channel(ID_CHANNEL_DAILY_CHALLENGE_LOG)
        team_role = interaction.guild.get_role(int(question[13])) if interaction.guild else None
        if log_channel:
            color = discord.Color.green() if is_correct else discord.Color.yellow()
            log_embed = discord.Embed(
                title=f"{'✅' if is_correct else '⏳'} Answer — Question #{question_id}",
                color=color,
                timestamp=interaction.created_at,
            )
            log_embed.set_author(name=interaction.user.display_name,
                                 icon_url=interaction.user.display_avatar.url)
            log_embed.add_field(name="User",        value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Correct?",       value="✅ Yes" if is_correct else "⏳ Review", inline=True)
            log_embed.add_field(name="Answer (raw)", value=f"```{answer}```", inline=False)
            log_embed.add_field(name="Feedback Groq", value=feedback or "—", inline=False)
            log_embed.set_footer(text=f"Answer id: {interaction.id}")

            log_kwargs: dict = {"embed": log_embed}
            
            if team_role and not is_correct:
                log_kwargs["content"] = f"{team_role.mention} Review needed for answer by {interaction.user.mention} to question #{question_id}."
            
            if is_latex:
                result = await render_latex(answer)
                if isinstance(result, bytes):
                    log_file = discord.File(fp=io.BytesIO(result), filename="answer_log.png")
                    log_embed.set_image(url="attachment://answer_log.png")
                    log_kwargs["file"] = log_file
                    
            if is_correct is None:
                log_kwargs["view"] = ReviewView(interaction.user, interaction.id, int(question[13]))

            message = await log_channel.send(**log_kwargs)
            if message and is_correct is None:
                # Reação para equipe identificar respostas pendentes de revisão
                await message.add_reaction("👀")
            

    # ── Gestão (equipe / admin) ───────────────────────────────────────────────

    @app_commands.command(name="add_question",
                          description="[Team] Add a question to the database for future publication")
    @app_commands.describe(
        question="Text or LaTeX of the question",
        answer="Expected answer (text or LaTeX) — used as the correct answer by Groq",
        target_date="Date of publication — DD/MM/AAAA",
        scheduled_time="Time of publication — HH:MM (default 08:00)",
        is_latex="Is the question/answer in LaTeX?",
        image_url="URL of an image to complement the question (optional)",
        limit_reward="Early  limit (number of first correct answers that get a special reward; optional)",
        channel="Channel where the question will be posted (default is the daily challenge channel)",
        team="Team responsible for this question"
    )
    async def add_question(self, interaction: discord.Interaction,
                     question: str, answer: str, target_date: str, team: discord.Role,
                     channel: discord.TextChannel, scheduled_time: str = "08:00",
                     is_latex: bool = False, image_url: str = None, limit_reward: int = None):
        if not _has_team_role(interaction):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        db_date = _parse_date_br(target_date)
        if not db_date:
            await interaction.response.send_message(
                "❌ Invalid date. Use the format **DD/MM/AAAA** (e.g. 25/03/2026).",
                ephemeral=True)
            return

        try:
            datetime.strptime(scheduled_time, "%H:%M")
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid time. Use the format **HH:MM** (e.g. 08:00).",
                ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        q_id = db_daily_question.add(
            question, answer, db_date, scheduled_time,
            limit_reward, is_latex, image_url, channel_id=channel.id if channel else None,
            created_by=interaction.user.name, added_by_team_id=team.id if team else None
        )

        if not q_id:
            await interaction.followup.send("❌ Error saving the question.", ephemeral=True)
            return

        limit_str  = f"{limit_reward} people" if limit_reward is not None else "no limit"
        latex_info = "🔢 LaTeX" if is_latex else "📝 Text"
        img_info   = "  •  🖼️ With image" if image_url else ""

        info_embed = discord.Embed(
            title=f"✅ Question ID {q_id} added!",
            color=discord.Color.green(),
        )
        info_embed.add_field(
            name="Details",
            value=f"📅 `{target_date}` — ⏰ `{scheduled_time}` — 🎁 {limit_str} — {latex_info}{img_info}",
            inline=False,
        )
        info_embed.add_field(name="Preview", value="👇", inline=False)

        preview_embeds, preview_files = await _build_question_embeds(
            q_id, question, is_latex, image_url)

        await interaction.followup.send(
            embeds=[info_embed] + preview_embeds,
            files=preview_files,
        )

    @app_commands.command(name="edit_question",
                          description="[Equipe] Edit a question")
    @app_commands.describe(
        question_id="Question ID to edit",
        question="New text or LaTeX (optional)",
        answer="New answer/guess (optional)",
        target_date="New date DD/MM/AAAA (optional)",
        scheduled_time="New time HH:MM (optional)",
        is_latex="Change LaTeX mode (optional)",
        image_url="New image URL; send 'remove' to remove (optional)",
        limit_reward="New early bird limit; use 0 to remove (optional)",
        channel="Channel where the question will be posted (optional, only if you want to change from the default channel)"
    )
    async def edit_question(self, interaction: discord.Interaction,
                      question_id: int, question: str = None, answer: str = None,
                      target_date: str = None, scheduled_time: str = None,
                      is_latex: bool = None, image_url: str = None,
                      limit_reward: int = None, channel: discord.TextChannel = None, team: discord.Role = None):
        if not _has_team_role(interaction):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        existing = db_daily_question.get_by_id(question_id)
        if not existing:
            await interaction.response.send_message(
                f"❌ Question {question_id} not found.", ephemeral=True)
            return

        db_date = None
        if target_date:
            db_date = _parse_date_br(target_date)
            if not db_date:
                await interaction.response.send_message(
                    "❌ Invalid date. Use the format **DD/MM/AAAA** (e.g. 25/03/2026).", ephemeral=True)
                return

        if scheduled_time:
            try:
                datetime.strptime(scheduled_time, "%H:%M")
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid time. Use the format **HH:MM** (e.g. 08:00).", ephemeral=True)
                return

        clear_image    = image_url is not None and image_url.strip().lower() == "remove"
        real_image_url = None if (image_url is None or clear_image) else image_url
        
        if team and team.id != existing[13]:  # index 13 = added_by_team_id
            # Se a equipe mudou, atribui o novo ID; caso contrário, mantém o existente
            log_channel = self.bot.get_channel(ID_CHANNEL_LOG)
            if log_channel:
                await log_channel.send(f"⚠️ Question {question_id} team changed from {existing[13]} to {team.id} by {interaction.user.mention}.")
        updated = db_daily_question.update(
            question_id, question=question, answer=answer,
            target_date=db_date, scheduled_time=scheduled_time,
            is_latex=is_latex, image_url=real_image_url, clear_image=clear_image,
            updated_by=interaction.user.name, channel_id=channel.id if channel else None,
            added_by_team_id=team.id if team else None
        )

        if limit_reward is not None:
            db_daily_question.set_limit_reward(
                question_id, None if limit_reward == 0 else limit_reward,
                updated_by=interaction.user.name)
            updated = True

        if updated:
            await interaction.response.send_message(
                f"✅ Question **{question_id}** updated.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ No changes applied.", ephemeral=True)

    @app_commands.command(name="delete_question",
                          description="[Equipe] Remove a question from the database")
    @app_commands.describe(question_id="The question ID to delete")
    async def delete_question(self, interaction: discord.Interaction, question_id: int):
        if not _has_team_role(interaction):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return
        
        log_channel = self.bot.get_channel(ID_CHANNEL_LOG)
        
        if not log_channel:
            await interaction.response.send_message(
                "❌ Log channel not found. Cannot proceed with deletion.", ephemeral=True)
            return

        if db_daily_question.delete(question_id):
            await log_channel.send(f"⚠️ Question {question_id} deleted by {interaction.user.mention}.")
            await interaction.response.send_message(
                f"✅ Question **{question_id}** removed.", ephemeral=True)
            
        else:
            await interaction.response.send_message(
                f"❌ Question {question_id} not found.", ephemeral=True)

    @app_commands.command(name="list_questions",
                          description="[Team] List all questions in the database, with pagination")
    @app_commands.describe(team="Filter questions by team")
    async def list_questions(self, interaction: discord.Interaction, team: discord.Role = None):
        if not _has_team_role(interaction):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return
        count = 0
        if team:
            count = db_daily_question.count_by_team(str(team.id))
        else:
            count = db_daily_question.count()
        
        print(f"[Questions] User {interaction.user} requested question list for team {team.name if team else 'ALL'}. Count: {count}")
        
        if count == 0:
            await interaction.response.send_message(
                "No questions registered yet.", ephemeral=True)
            return

        paginator = QuestionPaginator(db_daily_question, team_id=str(team.id) if team else None)
        await interaction.response.send_message(
            embed=paginator.build_embed(), view=paginator, ephemeral=True)

    @app_commands.command(name="send_question_now",
                          description="[Team] Send a question immediately to the channel")
    @app_commands.describe(question_id="ID of the question to send now")
    async def send_question_now(self, interaction: discord.Interaction, question_id: int):
        if not _has_team_role(interaction):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        question = db_daily_question.get_by_id(question_id)
        if not question:
            await interaction.response.send_message(
                f"❌ Question {question_id} not found.", ephemeral=True)
            return

        print(f"[DailyChallenge] Sending question {question_id} immediately by request of {interaction.user} in the channel {question[12]}")
        channel = self.bot.get_channel(int(question[12])) if question[12] else self.bot.get_channel(ID_CHANNEL_DAILY_CHALLENGE)  # index 12 = channel_id
        print(f"[DailyChallenge] Resolved channel: {channel}")
        if not channel:
            await interaction.response.send_message(
                "❌ Channel for daily challenges not found.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        q_id, q_text, _answer, _date, _time, _pub, _limit, is_latex, image_url = question[:9]
        embeds, files = await _build_question_embeds(q_id, q_text, bool(is_latex), image_url)
        await channel.send(embeds=embeds, files=files)

        db_daily_question.update(q_id, published=True, updated_by=interaction.user.name)
        await interaction.followup.send(
            f"✅ Question **{q_id}** sent to channel {channel.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyChallenge(bot))