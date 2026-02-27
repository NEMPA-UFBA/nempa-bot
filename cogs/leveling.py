import discord
from discord.ext import commands
from discord import app_commands
from database.users import db_user

RANKS = {
    5: 1465905527484715118,  # Nível 5: Rank "Beginner"
    10: 1465905569310310501, # Nível 10: Rank "Student"
    20: 1465905606207733793, # Nível 20: Rank "Scientist"
    50: 1465905628546470021  # Nível 50: Rank "Teacher"
}

class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return  # Ignorar mensagens de bots
        user_id = message.author.id
        data = db_user.get_user(user_id)

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
            await self.update_member_rank(message.author, level)

        db_user.update_user(user_id, xp, level)
        
        # Importante para os comandos funcionarem
        await self.bot.process_commands(message)

    async def update_member_rank(self, member, level):
        # Verifica se o nível atual do utilizador está no nosso dicionário de RANKS
        if level in RANKS or level > max(RANKS.keys()):
            role_id = RANKS[level] if level in RANKS else RANKS[max(RANKS.keys())]
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                    await member.remove_roles(*[r for r in member.roles if r.id in RANKS.values() and r != role])
                    print(f"Role {role.name} added to {member.name}")
                    
                    # Opcional: Enviar mensagem no canal
                    channel = member.guild.system_channel or member.guild.text_channels[0]
                    await channel.send(f"🎖️ {member.mention} reached the Rank **{str(role.name[7:]).capitalize()}**!")
                except discord.Forbidden:
                    print("Error: The bot does not have permission to manage roles.")
                except Exception as e:
                    print(f"Error adding role: {e}")
    
    async def add_xp(self, user_id, amount, member: discord.Member = None):
        data = db_user.get_user(user_id)
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

        db_user.update_user(user_id, xp, level)

        if leveled_up and member:
            await self.update_member_rank(member, level)

        return xp, level



    @app_commands.command(name="give_xp", description="Give XP to a member (management only)")
    @app_commands.describe(
        member="Member to receive XP",
        amount="Amount of XP to give"
    )
    async def give_xp(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        data = db_user.get_user(member.id)
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

        db_user.update_user(member.id, xp, level)

        response = f"✅ {amount} XP given to {member.mention}. New XP: {xp}, Level: {level}."
        if leveled_up:
            response += f" 🎉 {member.mention} leveled up to Level {level}!"
            await self.update_member_rank(member, level)

        await interaction.response.send_message(response)

    @app_commands.command(name="rank", description="Shows your current level and XP")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        data = db_user.get_user(target.id)

        if not data:
            await interaction.response.send_message("This user does not have any XP yet.", ephemeral=True)
            return

        xp, level = data
        next_xp = 100 * (level ** 2)

        embed = discord.Embed(title=f"Status of {target.name}", color=discord.Color.blue())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Ranking Position", value=f"#{db_user.get_user_position(xp)}", inline=True)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Total XP", value=f"{xp}/{next_xp}", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="leaderboard", description="Shows the ranking of the top players")
    async def leaderboard(self, interaction: discord.Interaction):
        # Buscamos os 10 melhores ordenados por XP
        results = db_user.get_top_users()

        if not results:
            return await interaction.response.send_message("No data available.", ephemeral=True)

        description = ""
        for index, (u_id, xp, level) in enumerate(results, start=1):
            # Tentamos buscar o nome do usuário pelo ID
            # Se o bot não encontrar (usuário saiu do server), usamos 'Membro Antigo'
            user = await self.bot.fetch_user(u_id)
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

async def setup(bot):
    await bot.add_cog(Leveling(bot))