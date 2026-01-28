import discord
from discord.ext import commands
from discord import app_commands
import urllib

class DailyChallenge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(DailyChallenge(bot))