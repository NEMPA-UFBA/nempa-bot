import discord
from discord.ext import commands
import os
from datetime import datetime
from database.users import db_user
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


class CheckIn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.correct_password = os.getenv('SECRET_PASSWORD')  # Altere para a senha desejada
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
            
        
        if interaction.channel_id != channel.id:
            await interaction.response.send_message(
                f"❌ Please use the {channel.mention} channel to check in.",
                ephemeral=True
            )
            return
        
        if senha == self.correct_password:
            try:
                if db_user.get_checkin_answer(interaction.user.id, senha):
                    await interaction.response.send_message(
                        "❌ You have already checked in!",
                        ephemeral=True
                    )
                    return
                role = interaction.guild.get_role(self.role_id)
                if role:
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message(
                        f"✅ Check-in successful! You have received the role {role.mention}",
                        ephemeral=True
                    )
                    xp, level = db_user.add_xp(interaction.user.id, 500)  # Adiciona o usuário ao banco de dados com XP 0 e nível 1
                    db_user.record_checkin(interaction.user.id, senha)  # Registra o check-in no banco de dados com a resposta fornecida
                    
                    # Obter o cargo apropriado para o nível
                    rank_id = get_rank_for_level(level)
                    if rank_id:
                        rank_role = interaction.guild.get_role(rank_id)
                        rank_name = rank_role.name if rank_role else "Unknown"
                    else:
                        rank_name = "No Rank Yet"
                    
                    await interaction.followup.send(f"🎉 You gained 500 XP! Your current XP is {xp}, Level {level}, and your rank is {rank_name}.", ephemeral=True)
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

async def setup(bot):
    await bot.add_cog(CheckIn(bot))