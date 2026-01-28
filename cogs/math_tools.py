import discord
from discord.ext import commands
from discord import app_commands
import urllib

class MathTools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    choices = [
        app_commands.Choice(name="Pequeno", value=r"\small"),
        app_commands.Choice(name="Normal", value=r"\normalsize"),
        app_commands.Choice(name="Grande", value=r"\large"),
        app_commands.Choice(name="Muito Grande", value=r"\huge"),
        app_commands.Choice(name="Gigante", value=r"\Huge")
    ]

    @app_commands.command(name="latex", description="Renders LaTeX with optional size")
    @app_commands.describe(
        formula="The LaTeX formula (e.g., a^2 + b^2 = c^2)",
        size="Choose the rendering size"
    )
    @app_commands.choices(size=choices)
    async def latex(self, interaction: discord.Interaction, formula: str, size: app_commands.Choice[str] = None):
        await interaction.response.defer()
        
        try:
            # Se o usuário não escolher nada, usamos \huge como padrão para ficar visível
            cmd_tamanho = size.value if size else r"\huge"
            
            # Montamos a string final para a API
            # \dpi{200} garante a qualidade da imagem
            prefixo = rf"\dpi{{200}} {cmd_tamanho} \color{{White}} "
            formula_completa = prefixo + formula
            
            encoded_formula = urllib.parse.quote(formula_completa)
            url = f"https://latex.codecogs.com/png.latex?{encoded_formula}"
            
            # Mostramos qual tamanho foi usado na resposta
            txt_tamanho = size.name if size else "Muito Grande (Padrão)"
            await interaction.followup.send(url)
            
        except Exception as e:
            await interaction.followup.send(f"Erro: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MathTools(bot))