import re
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
from urllib.parse import quote

QUICKLATEX_URL = "https://quicklatex.com/latex3.f"

PREAMBLE = r"""\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{tikz}
\usepackage{pgfplots}
\usepackage{xcolor}
\usetikzlibrary{calc, intersections}
\color{white}"""

SIZE_CHOICES = [
    app_commands.Choice(name="Pequeno",      value="15px"),
    app_commands.Choice(name="Normal",       value="25px"),
    app_commands.Choice(name="Grande",       value="35px"),
    app_commands.Choice(name="Muito Grande", value="45px"),
    app_commands.Choice(name="Enorme",       value="60px"),
]


def _prepare_formula(formula: str) -> str:
    """
    Envolve as partes de texto puro em \\text{} para que espaços e acentos
    sejam preservados pelo LaTeX.

    Lógica:
      - Trechos dentro de $...$ ou $$...$$ → mantidos como estão (modo math)
      - Trechos fora de delimitadores math  → envolvidos em \\text{...}

    Exemplos:
      "Um quadrado de lado $a$. Ache $x$."
        → "\\text{Um quadrado de lado }$a$\\text{. Ache }$x$\\text{.}"

      "$a^2 + b^2 = c^2$"   (só math) → inalterado
      "Hello world"          (só texto) → "\\text{Hello world}"
    """
    # Se a fórmula já usa ambientes LaTeX explícitos, não mexemos
    if any(tok in formula for tok in (r"\begin", r"\[", r"\]", r"\text{")):
        return formula

    # Separa math ($...$  ou  $$...$$) do texto puro usando um split que
    # mantém os delimitadores nos tokens
    parts = re.split(r'(\$\$.*?\$\$|\$.*?\$)', formula, flags=re.DOTALL)

    result = []
    for part in parts:
        if part.startswith("$"):
            # Bloco math — preservar intacto
            result.append(part)
        elif part:
            # Texto puro — envolver em \text{}
            result.append(r"\text{" + part + "}")

    return "".join(result)


async def render_latex(formula: str, font_size: str = "60px") -> bytes | str:
    """
    Formato real da resposta:
      Linha 0: <status_code>
      Linha 1: <url> <width> <height>
      Linha 2+: mensagem de erro (se houver)

      status >= 0 → sucesso
      status <  0 → erro
    """
    prepared = _prepare_formula(formula)

    # mode=0 → math inline  |  mode=2 → LaTeX completo (necessário para TikZ, tabular, etc.)
    FULL_LATEX_TRIGGERS = (r"\begin{tikzpicture}", r"\begin{tabular}",
                           r"\begin{array}", r"\begin{pspicture}")
    mode = "2" if any(t in prepared for t in FULL_LATEX_TRIGGERS) else "0"

    body = (
        f"formula={quote(prepared, safe='')}"
        f"&fsize={quote(font_size, safe='')}"
        f"&fcolor=FFFFFF"
        f"&bcolor=323339"
        f"&mode={mode}"
        f"&out=1"
        f"&remhost=quicklatex.com"
        f"&preamble={quote(PREAMBLE, safe='')}"
    )

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with aiohttp.ClientSession() as session:
        async with session.post(QUICKLATEX_URL, data=body, headers=headers) as resp:
            text = await resp.text()

    lines = text.strip().splitlines()
    status_code = int(lines[0])

    if status_code < 0:
        error_msg = "\n".join(lines[2:]) if len(lines) > 2 else "Erro desconhecido."
        return f"❌ Erro do QuickLaTeX (código {status_code}):\n```\n{error_msg}\n```"

    img_url = lines[1].split()[0]

    async with aiohttp.ClientSession() as session:
        async with session.get(img_url) as img_resp:
            return await img_resp.read()


class MathTools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="latex",
        description="Renderiza LaTeX (suporta texto e equações misturados)"
    )
    @app_commands.describe(
        formula="Use $...$ para math inline. Texto fora de $ é tratado como texto normal.",
        size="Tamanho da fonte"
    )
    @app_commands.choices(size=SIZE_CHOICES)
    async def latex(
        self,
        interaction: discord.Interaction,
        formula: str,
        size: app_commands.Choice[str] = None,
    ):
        await interaction.response.defer()

        font_size = size.value if size else "60px"
        result = await render_latex(formula, font_size)

        if isinstance(result, str):
            await interaction.followup.send(result, ephemeral=True)
            return

        file = discord.File(fp=io.BytesIO(result), filename="formula.png")
        await interaction.followup.send(file=file)


async def setup(bot):
    await bot.add_cog(MathTools(bot))