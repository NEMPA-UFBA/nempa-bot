import asyncio
import os
from discord import File
import discord
from aiohttp import web
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import urllib.parse

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ID_WELCOME_CHANNEL = int(os.getenv('WELCOME_CHANNEL_ID'))  # ID do canal de boas-vindas
PORT = int(os.getenv('PORT', 8080))

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True  # ESSENCIAL para detectar novos membros

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!!", intents=intents)

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
        return await super().on_message(message)

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

# Comando simples para testar manualmente
choices = [
    app_commands.Choice(name="Pequeno", value=r"\small"),
    app_commands.Choice(name="Normal", value=r"\normalsize"),
    app_commands.Choice(name="Grande", value=r"\large"),
    app_commands.Choice(name="Muito Grande", value=r"\huge"),
    app_commands.Choice(name="Gigante", value=r"\Huge")
]

@bot.tree.command(name="latex", description="Renderiza LaTeX com tamanho opcional")
@app_commands.describe(
    formula="A fórmula LaTeX (ex: a^2 + b^2 = c^2)",
    tamanho="Escolha o tamanho da renderização"
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
      
@bot.tree.command(name="give_daily_reward", description="Dá XP ao usuário (comando de teste)")
@app_commands.describe(user_id="Id do usuário para dar XP")
async def give_xp(interaction: discord.Interaction,user_id: str):
    # Implementar a lógica para dar XP ao usuário aqui
    
    await interaction.response.send_message(f"!give {user_id} 1000 XP", ephemeral=True)

@bot.tree.command(name="ping", description="Responde com Pong!")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!", ephemeral=True)

if __name__ == "__main__":
    async def main():
        await start_web_server()
        await bot.start(TOKEN)

    asyncio.run(main())