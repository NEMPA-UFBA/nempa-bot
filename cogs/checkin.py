import discord
from discord.ext import commands
import os
from datetime import datetime

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
            await interaction.user.add_roles(interaction.guild.get_role(1475270433107349545))  # Adiciona o cargo de "Olympic Week" automaticamente
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
        
        role = interaction.guild.get_role(self.role_id)
        if role in interaction.user.roles:
            await interaction.response.send_message(
                "❌ You have already checked in!",
                ephemeral=True
            )
            return
        
        if senha == self.correct_password:
            if role:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(
                    f"✅ Check-in successful! You have received the role {role.mention}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Role not found. Please contact an administrator.",
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