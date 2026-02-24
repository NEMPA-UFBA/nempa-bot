import discord
from discord.ext import commands
import os
from datetime import datetime
from typing import List, Optional
from database.users import db_user
from database.questions import db_question, QuestionDatabaseManager
from cogs.leveling import RANKS


def get_rank_for_level(level):
    """Retorna o cargo apropriado para o nível do usuário"""
    if level >= 50:
        return RANKS[50]  # Teacher
    elif level >= 20:
        return RANKS[20]  # Scientist
    elif level >= 10:
        return RANKS[10]  # Student
    elif level >= 5:
        return RANKS[5]   # Beginner
    return None


class QuestionPaginator(discord.ui.View):
    def __init__(self, db_manager: QuestionDatabaseManager, per_page=5, by_published=False):
        super().__init__(timeout=180)
        self.db_manager = db_manager
        self.per_page = per_page
        self.current_page = 0
        self.by_published = by_published
        # Contar total de perguntas para calcular max_pages
        self.total_questions = db_manager.count_questions(only_published=by_published)
        self.max_pages = max(1, (self.total_questions - 1) // per_page + 1)
        
    def get_embed(self):
        embed = discord.Embed(
            title="📋 Questions in the Database",
            color=0xfe6c00
        )
        
        # Usar os parâmetros da função get_all_questions
        offset = self.current_page * self.per_page
        questions = self.db_manager.get_all_questions(
            limit=self.per_page, 
            offset=offset,
            only_published=self.by_published
        )
        
        for q in questions:
            q_id, q_text, q_answer, q_target_date = q
            q_text = q_text.replace('\\n', '\n')
            target_date_str = f" (Target Date: {q_target_date})" if q_target_date else ""
            embed.add_field(
                name=f"ID {q_id}", 
                value=f"{q_text}\nAnswer: `{q_answer}`{target_date_str}", 
                inline=False
            )
        
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages}")
        return embed
    
    @discord.ui.button(label="◀", style=discord.ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="▶", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()


class CheckIn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_id = 1475270926789640412  # Altere para o ID do cargo desejado

    @discord.app_commands.command(name="checkin", description="Check in with the correct password")
    async def checkin(self, interaction: discord.Interaction, senha: str):
        channel = interaction.guild.get_channel(1475596475689078794)
        log_channel = interaction.guild.get_channel(1475598600535801946)
        
        if not channel:
            await interaction.response.send_message(
                "❌ Check-in channel not found. Please contact an administrator.",
                ephemeral=True
            )
            return
        
        # Verifica se a data atual está entre os dias 23 e 27
        day = datetime.now().day
        month = datetime.now().month
        if 23 <= day <= 27 and month == 2:  # Verifica se é fevereiro e se o dia está entre 23 e 27
            olympic_role = interaction.guild.get_role(1475270433107349545)
            if olympic_role:
                try:
                    await interaction.user.add_roles(olympic_role)
                except Exception as e:
                    print(f"[checkin] Error assigning Olympic Week role: {e}")
        else:
            await interaction.response.send_message(
                "❌ Check-in is only available from February 23 to 27.",
                ephemeral=True
            )
            return
            
        
        if interaction.channel_id != channel.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                f"❌ Please use the {channel.mention} channel to check in.",
                ephemeral=True
            )
            return
        
        question = db_question.get_question_by_answer(senha)  # Verifica se a resposta corresponde a uma pergunta existente
        
        if question and question[4]:  # Verifica se a pergunta tem uma data alvo definida
            target_date = datetime.strptime(question[4], "%Y-%m-%d").date()
            if datetime.now().date() > target_date:
                await interaction.response.send_message(
                    "❌ This password is no longer valid. The target date for this question has passed.",
                    ephemeral=True
                )
                return
            
            if datetime.now().date() < target_date:
                await interaction.response.send_message(
                    f"❌ Incorrect password! Please try again.",
                    ephemeral=True
                )
                return
        
        if not question:
            await interaction.response.send_message(
                "❌ Incorrect password! Please try again.",
                ephemeral=True
            )
            return
        
        if not question[3]:  # Verifica se a pergunta está publicada
            await interaction.response.send_message(
                "❌ This question is not published yet. Please try again later.",
                ephemeral=True
            )
            return
        
        if senha == question[2]:
            try:
                if db_user.get_checkin_answer(interaction.user.id, senha):
                    await interaction.response.send_message(
                        f"❌ You have already checked in with the password '{senha}'!",
                        ephemeral=True
                    )
                    return
                role = interaction.guild.get_role(self.role_id)
                if role:
                    if role not in interaction.user.roles:
                        await interaction.user.add_roles(role)
                        await interaction.response.send_message(
                            f"✅ Check-in successful! You have received the role {role.mention}",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            f"✅ Check-in successful! You already had the role {role.mention}",
                            ephemeral=True
                        )
                    
                    xp, level = db_user.add_xp(interaction.user.id, 500)
                    
                    db_user.record_checkin(interaction.user.id, senha, question[0])  # Registra o check-in no banco de dados com a resposta fornecida
                    checkins_count = db_user.count_checkins_by_question(question[0])
                    print(checkins_count)
                    if checkins_count <= question[3]:  # Verifica se o número de check-ins ainda está dentro do limite para recompensa secreta
                        embed = discord.Embed(
                            title="🎉 Early Check-in Bonus! 🎉",
                            description=f"{interaction.user.mention} is one of the first {question[3]} to check in and has received a bonus!",
                            colour=discord.Color.gold()
                        )
                        embed.set_footer(text=f"Total check-ins so far: {checkins_count}")
                        embed.set_thumbnail(url=interaction.user.display_avatar.url)
                        await interaction.followup.send(embed=embed)
                    # Obter o cargo apropriado para o nível
                    rank_id = get_rank_for_level(level)
                    if rank_id:
                        rank_role = interaction.guild.get_role(rank_id)
                        rank_name = rank_role.name if rank_role else "Unknown"
                    else:
                        rank_name = "No Rank Yet"
                    
                    embed = discord.Embed(
                        title="🎉 XP and Level Update! 🎉",
                        description=f"🎉 You gained 500 XP! Your current XP is {xp}, Level {level}, and your rank is {rank_name}.\nYou can see the leaderboard using the `/leaderboard` command.",
                        colour=discord.Color.blue()
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    
                    
                else:
                    await interaction.response.send_message(
                        "❌ Role not found. Please contact an administrator.",
                        ephemeral=True
                    )
            except Exception as e:
                print(f"Error assigning role: {e}")
                await interaction.response.send_message(
                    "❌ An error occurred while assigning the role. Please contact an administrator.",
                    ephemeral=True
                )
            
            
            # Log the successful check-in
            if log_channel:
                embed = discord.Embed(
                    title="✅ Check-in Successful",
                    description=f"User {interaction.user.mention} has successfully checked in.",
                    color=discord.Color.green()
                )
                await log_channel.send(embed=embed)
            
        else:
            await interaction.response.send_message(
                "❌ Incorrect password!",
                ephemeral=True
            )

    @discord.app_commands.command(name="add_question", description="Check if you have already checked in with a specific password")
    @discord.app_commands.describe(
        question="The question to be added",
        answer="The answer to the question",
        target_date="Optional target date for the question (YYYY-MM-DD)",
        limit_secret_reward="Optional limit for secret reward (default is 3)"
    )
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def add_question(self, interaction: discord.Interaction, question: str, answer: str, target_date: str = None, limit_secret_reward: int = 3):
        try:
            if target_date:
                try:
                    target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
                except ValueError:
                    await interaction.response.send_message(
                        "❌ Invalid date format. Please use YYYY-MM-DD.",
                        ephemeral=True
                    )
                    return
            else:
                target_date_obj = None
            
            question_id = db_question.save_question(question, answer, target_date_obj, limit_secret_reward)
            if question_id:
                await interaction.response.send_message(
                    f"✅ Question added successfully with ID {question_id}!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ A question with that answer already exists or an error occurred. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error adding question: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while adding the question. Please contact an administrator.",
                ephemeral=True
            )
    
    @discord.app_commands.command(name="see_questions", description="See all questions in the database")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def see_all_questions(self, interaction: discord.Interaction):
        try:
            # Verificar se há perguntas
            all_questions = db_question.get_all_questions()
            if not all_questions:
                await interaction.response.send_message(
                    "No questions found in the database.",
                    ephemeral=True
                )
                return
            
            paginator = QuestionPaginator(db_question, per_page=5)
            await interaction.response.send_message(
                embed=paginator.get_embed(), 
                view=paginator, 
                ephemeral=True
            )
        except Exception as e:
            print(f"Error retrieving questions: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while retrieving questions. Please contact an administrator.",
                ephemeral=True
            )
    
    @discord.app_commands.command(name="publish_question", description="Publish a question by its ID")
    @discord.app_commands.describe(
        question_id="The ID of the question to publish, you can use the /see_questions command to see all question IDs",
        channel="The channel where the question will be published",
        role_to_mention="The roles to be mentioned in the published question (mention them with @)",
        thumbnail_url="Optional thumbnail URL for the published question",
        title="Optional title for the published question"
    )
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def publish_question(self, interaction: discord.Interaction, question_id: int, channel: discord.TextChannel, role_to_mention: str = None, title: str = None, thumbnail_url: str = None):
        question = db_question.get_question_by_id(question_id)
        if not question:
            await interaction.response.send_message(
                f"❌ Question with ID {question_id} not found.",
                ephemeral=True
            )
            return
        
        if question[3]:  # Verifica se a pergunta já foi publicada
            await interaction.response.send_message(
                f"❌ Question with ID {question_id} has already been published.",
                ephemeral=True
            )
            return
        
        selected_channel = interaction.guild.get_channel(channel.id)
        if not selected_channel:
            await interaction.response.send_message(
                f"❌ Channel with ID {channel.id} not found.",
                ephemeral=True
            )
            return
        
        # Substituir \n literal por quebra de linha real
        question_text = question[1].replace('\\n', '\n')
        
        embed = discord.Embed(
            title=title,
            description=question_text,
            color=0xfe6c00
        )
        
        if thumbnail_url:
            embed.set_image(url=thumbnail_url)
        
        # Formatar a data no formato desejado usando a target_date da questão
        if question[4]:  # Se houver target_date
            dias_semana = {
                0: "segunda-feira",
                1: "terça-feira",
                2: "quarta-feira",
                3: "quinta-feira",
                4: "sexta-feira",
                5: "sábado",
                6: "domingo"
            }
            target_date = datetime.strptime(question[4], "%Y-%m-%d")
            dia_semana = dias_semana[target_date.weekday()]
            data_formatada = target_date.strftime("%d/%m")
            embed.set_footer(text=f"Enigma de {dia_semana} ({data_formatada})")
        else:
            embed.set_footer(text=f"Question ID: {question_id}")
        
        # db_question.alter_question(question_id, published=True)
        
        content_to_send = role_to_mention if role_to_mention else None
        
        # Verifica se o canal tem webhooks
        webhooks = await selected_channel.webhooks()
        if webhooks:
            # Usa o primeiro webhook encontrado
            webhook = webhooks[0]
            await webhook.send(embed=embed, content=content_to_send)
        else:
            # Envia normalmente sem webhook
            await selected_channel.send(embed=embed, content=content_to_send)
        
        await interaction.response.send_message(f"✅ Question published in channel {selected_channel.mention}", ephemeral=True)
    
    @discord.app_commands.command(name="delete_question", description="Delete a question by its ID")
    @discord.app_commands.describe(
        question_id="The ID of the question to delete, you can use the /see_questions command to see all question IDs"
    )
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def delete_question(self, interaction: discord.Interaction, question_id: int):
        deleted = db_question.delete_question_by_id(question_id)
        if deleted:
            await interaction.response.send_message(f"✅ Question with ID {question_id} deleted.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Question with ID {question_id} not found.", ephemeral=True)
    
async def setup(bot):
    await bot.add_cog(CheckIn(bot))