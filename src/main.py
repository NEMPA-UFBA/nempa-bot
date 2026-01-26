import asyncio
import os

import discord
from aiohttp import web
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ID_WELCOME_CHANNEL = int(os.getenv('WELCOME_CHANNEL_ID'))  # ID do canal de boas-vindas
PORT = int(os.getenv('PORT', 10000))

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True  # ESSENCIAL para detectar novos membros

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

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
@bot.tree.command(name="testar_boas_vindas", description="Simula uma entrada de membro")
async def test_welcome(interaction: discord.Interaction):
    # Simula o evento para o próprio usuário que digitou o comando
    if (interaction.user.guild_permissions.administrator):
      await bot.on_member_join(interaction.user)
      await interaction.response.send_message("Teste de boas-vindas enviado!", ephemeral=True)

if __name__ == "__main__":
    async def main():
        await start_web_server()
        await bot.start(TOKEN)

    asyncio.run(main())