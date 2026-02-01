import os
from datetime import time, datetime, timezone
import discord
from discord.ext import commands, tasks
from discord import app_commands
from database.daily_challenge_answers import db_daily_challenge_answer
import pytz

ID_CHANNEL_DAILY_CHALLENGE = int(os.getenv('ID_CHANNEL_DAILY_CHALLENGE'))
ID_CHANNEL_DAILY_CHALLENGE_LOG = int(os.getenv('ID_CHANNEL_DAILY_CHALLENGE_LOG'))

class DailyChallenge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.target_time = time(hour=8, minute=0, tzinfo=pytz.timezone('America/Bahia'))
        self.end_time = time(hour=22, minute=0, tzinfo=pytz.timezone('America/Bahia'))
        self.daily_message.start()
    
    def cog_unload(self):
        self.daily_message.cancel()
    
    @tasks.loop(time=time(hour=8, minute=0, tzinfo=pytz.timezone('America/Bahia')))
    async def daily_message(self):
        channel = self.bot.get_channel(ID_CHANNEL_DAILY_CHALLENGE)
        if channel:
            embed = discord.Embed(
                title="Test",
                description=f"DAILY TEST MESSAGE",
                color=discord.Color.orange()
            )
            await channel.send(embed=embed)
            print(f"Mensagem diária enviada às {datetime.now(pytz.timezone('America/Bahia'))}")
    
    
    @daily_message.before_loop
    async def before_daily_message(self):
        # Espera o bot estar pronto antes de iniciar o loop
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="answer_daily_challenge", description="Answer the daily challenge")
    async def answer_daily_challenge(self, interaction: discord.Interaction, answer: str):
        # await interaction.response.defer()
        if interaction.channel_id != ID_CHANNEL_DAILY_CHALLENGE:
            await interaction.response.send_message(f"This command can only be used in the <#{ID_CHANNEL_DAILY_CHALLENGE}> channel.", ephemeral=True)
            return
        
        if datetime.now(pytz.timezone('America/Bahia')).time() < self.target_time:
            await interaction.response.send_message("You can only answer the daily challenge after 8:00 AM Bahia time.", ephemeral=True)
            return
        
        if datetime.now(pytz.timezone('America/Bahia')).time() > self.end_time:
            await interaction.response.send_message("The time to answer today's challenge has ended (after 10:00 PM Bahia time).", ephemeral=True)
            return
        
        user_answered = db_daily_challenge_answer.check_user_answered(interaction.user.id)
        if user_answered:
            await interaction.response.send_message("You have already answered today's challenge.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📝 Answer to the Daily Challenge",
            description=answer,
            color=discord.Color.green(),
            timestamp=interaction.created_at
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        msg_sent = await interaction.response.send_message(embed=embed)
        
        db_daily_challenge_answer.save_challenge_answer(msg_sent.id, interaction.user.id, answer)
        
        log_channel = self.bot.get_channel(ID_CHANNEL_DAILY_CHALLENGE_LOG)
        print(log_channel)
        if log_channel:
            embed_log = discord.Embed(
                title="📝 New Answer to the Daily Challenge",
                description=f"User: {interaction.user.mention}\nAnswer: {answer}",
                color=discord.Color.blue(),
                timestamp=interaction.created_at
            )
            embed_log.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            msg_sent_url = f"https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{msg_sent.id}"
            embed_log.add_field(name="Original Message", value=f"[Click here to see the message]({msg_sent_url})", inline=False)
            log = await log_channel.send(embed=embed_log)
            if not log:
                print("Failed to send log message.")
        else:
            print("Log channel not found.")
        

async def setup(bot):
    await bot.add_cog(DailyChallenge(bot))