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


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        intents.members = True  # ESSENCIAL para detectar novos membros
        super().__init__(
            command_prefix="!!",
            intents=intents,
            chunk_guilds_at_startup=False, # Não carrega todos os membros ao ligar
            member_cache_flags=discord.MemberCacheFlags.none() # Não guarda membros na RAM,
        )
        self._db = Db_Manager()

    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'Módulo {filename} carregado.')
    
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


async def main():
    bot = MyBot()
    
    @bot.tree.command(name="ping", description="Responds with Pong!")
    async def ping(interaction: discord.Interaction):
        await interaction.response.send_message("Pong!", ephemeral=True)

    await start_web_server()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
