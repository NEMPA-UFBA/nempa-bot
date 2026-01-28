import asyncio
import os
import discord
from aiohttp import web
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import urllib.parse
from database.database import Db_Manager

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ID_WELCOME_CHANNEL = int(os.getenv('WELCOME_CHANNEL_ID'))  # ID do canal de boas-vindas
PORT = int(os.getenv('PORT', 8080))
RANKS = {
    5: 1465905527484715118,  # Nível 5: Rank "Beginner"
    10: 1465905569310310501, # Nível 10: Rank "Student"
    20: 1465905606207733793, # Nível 20: Rank "Scientist"
    50: 1465905628546470021  # Nível 50: Rank "Teacher"
}

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True  # ESSENCIAL para detectar novos membros

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!!",
            intents=intents,
            chunk_guilds_at_startup=False, # Não carrega todos os membros ao ligar
            member_cache_flags=discord.MemberCacheFlags.none() # Não guarda membros na RAM,
        )
        self._db = Db_Manager()

    async def on_ready(self):
        print(f'Bot logado como {self.user}!')
        try:
            synced = await self.tree.sync()
            print(f"Sincronizados {len(synced)} comandos globais.")
        except Exception as e:
            print(f"Erro ao sincronizar: {e}")

    # EVENTO DE BOAS-VINDAS
    async def on_member_join(self, member):
        channel = member.guild.get_channel(ID_WELCOME_CHANNEL)

        if channel:
            embed = discord.Embed(
                title=f"Bem-vindo(a) ao {member.guild.name}!",
                description=f"Olá {member.mention}, que bom ter você aqui!",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"ID do usuário: {member.id}")
            
            await channel.send(embed=embed)
    
    async def on_message(self, message):
        if message.author.bot:
            return  # Ignorar mensagens de bots
        user_id = message.author.id
        data = self._db.get_user(user_id)

        if data:
            xp, level = data
        else:
            xp, level = 0, 1

        # Ganha entre 5 e 15 de XP por mensagem
        xp += 10 
        
        # Cálculo para subir de nível: 100 * (level^2)
        next_level_xp = 100 * (level ** 2)

        if xp >= next_level_xp:
            level += 1
            await message.channel.send(f"🎉 Congrats {message.author.mention}! You leveled up to **Level {level}**!")
            await update_member_rank(message.author, level)

        self._db.update_user(user_id, xp, level)
        
        # Importante para os comandos funcionarem
        await bot.process_commands(message)

bot = MyBot()

# Servidor HTTP simples para manter o processo vivo em hostings que exigem porta aberta
async def healthcheck(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_web_server() -> None:
    app = web.Application()
    app.router.add_get("/", healthcheck)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

async def update_member_rank(member, level):
    # Verifica se o nível atual do utilizador está no nosso dicionário de RANKS
    if level in RANKS:
        role_id = RANKS[level]
        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role)
                await member.remove_roles(*[r for r in member.roles if r.id in RANKS.values() and r != role])
                print(f"Role {role.name} added to {member.name}")
                
                # Opcional: Enviar mensagem no canal
                channel = member.guild.system_channel or member.guild.text_channels[0]
                await channel.send(f"🎖️ {member.mention} reached the Rank **{role.name[7:0].capitalize()}**!")
            except discord.Forbidden:
                print("Error: The bot does not have permission to manage roles.")
            except Exception as e:
                print(f"Error adding role: {e}")

# Comando simples para testar manualmente
choices = [
    app_commands.Choice(name="Pequeno", value=r"\small"),
    app_commands.Choice(name="Normal", value=r"\normalsize"),
    app_commands.Choice(name="Grande", value=r"\large"),
    app_commands.Choice(name="Muito Grande", value=r"\huge"),
    app_commands.Choice(name="Gigante", value=r"\Huge")
]

@bot.tree.command(name="latex", description="Renders LaTeX with optional size")
@app_commands.describe(
    formula="The LaTeX formula (e.g., a^2 + b^2 = c^2)",
    tamanho="Choose the rendering size"
)
@app_commands.choices(tamanho=choices)
async def latex(interaction: discord.Interaction, formula: str, tamanho: app_commands.Choice[str] = None):
    await interaction.response.defer()
    
    try:
        # Se o usuário não escolher nada, usamos \huge como padrão para ficar visível
        cmd_tamanho = tamanho.value if tamanho else r"\huge"
        
        # Montamos a string final para a API
        # \dpi{200} garante a qualidade da imagem
        prefixo = rf"\dpi{{200}} {cmd_tamanho} \color{{White}} "
        formula_completa = prefixo + formula
        
        encoded_formula = urllib.parse.quote(formula_completa)
        url = f"https://latex.codecogs.com/png.latex?{encoded_formula}"
        
        # Mostramos qual tamanho foi usado na resposta
        txt_tamanho = tamanho.name if tamanho else "Muito Grande (Padrão)"
        await interaction.followup.send(url)
        
    except Exception as e:
        await interaction.followup.send(f"Erro: {e}", ephemeral=True)
      
# Comando para ver o Rank
@bot.tree.command(name="rank", description="Shows your current level and XP")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    data = bot._db.get_user(target.id)

    if not data:
        await interaction.response.send_message("This user does not have any XP yet.", ephemeral=True)
        return

    xp, level = data
    next_xp = 100 * (level ** 2)

    embed = discord.Embed(title=f"Status of {target.name}", color=discord.Color.blue())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Ranking Position", value=f"#{bot._db.get_user_position(xp)}", inline=True)
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="Total XP", value=f"{xp}/{next_xp}", inline=True)
    
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="give_xp", description="Give XP to a member (management only)")
@app_commands.describe(
    member="Member to receive XP",
    amount="Amount of XP to give"
)
async def give_xp(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    data = bot._db.get_user(member.id)
    if data:
        xp, level = data
    else:
        xp, level = 0, 1

    xp += amount
    next_level_xp = 100 * (level ** 2)

    leveled_up = False
    while xp >= next_level_xp:
        level += 1
        leveled_up = True
        next_level_xp = 100 * (level ** 2)

    bot._db.update_user(member.id, xp, level)

    response = f"✅ {amount} XP given to {member.mention}. New XP: {xp}, Level: {level}."
    if leveled_up:
        response += f" 🎉 {member.mention} leveled up to Level {level}!"
        await update_member_rank(member, level)

    await interaction.response.send_message(response)

@bot.tree.command(name="leaderboard", description="Shows the ranking of the top players")
async def leaderboard(interaction: discord.Interaction):
    # Buscamos os 10 melhores ordenados por XP
    results = bot._db.get_top_users()

    if not results:
        return await interaction.response.send_message("No data available.", ephemeral=True)

    description = ""
    for index, (u_id, xp, level) in enumerate(results, start=1):
        # Tentamos buscar o nome do usuário pelo ID
        # Se o bot não encontrar (usuário saiu do server), usamos 'Membro Antigo'
        user = await bot.fetch_user(u_id)
        print(user)
        name = user.display_name if user else f"ID: {u_id}"
        
        # Medalhas para os 3 primeiros
        medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"#{index}"
        description += f"{medal} **{name}** - Level {level} ({xp} XP)\n"

    embed = discord.Embed(
        title="🏆 Global Level Ranking",
        description=description,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Keep chatting to climb the leaderboard!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="Responds with Pong!")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!", ephemeral=True)

if __name__ == "__main__":
    async def main():
        await start_web_server()
        await bot.start(TOKEN)

    asyncio.run(main())