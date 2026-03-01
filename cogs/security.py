import discord
from discord.ext import commands

INTRODUCTION_CHANNEL_ID = 1465414418480365727
MEMBER_ROLE_ID = 1466191571266572371
VISITOR_ROLE_ID = 1477668654957989939

REQUIRED_FIELDS = [
    "Name:",
    "Age:",
    "City/Country:",
    "Education level:",
    "Area of interest:",
]

MIN_LENGTH = 200

def validate_introduction(content: str) -> list[str]:
    return [f for f in REQUIRED_FIELDS if f.lower() not in content.lower()]

class Introduction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.channel.id != INTRODUCTION_CHANNEL_ID:
            return

        member = message.author
        guild = message.guild

        visitor_role = guild.get_role(VISITOR_ROLE_ID)
        member_role = guild.get_role(MEMBER_ROLE_ID)

        if visitor_role not in member.roles:
            return

        if len(message.content) < MIN_LENGTH:
            await message.reply(
                "❌ Your introduction is too short. Please fill in the template properly.",
                delete_after=10,
            )
            return

        missing_fields = validate_introduction(message.content)
        if missing_fields:
            fields_list = "\n".join(f"• `{f}`" for f in missing_fields)
            await message.reply(
                f"❌ Your introduction is missing some required fields:\n{fields_list}\n\n"
                "Please edit your message or send a new one with all fields filled in.",
                delete_after=15
            )
            return

        try:
            await member.add_roles(member_role)
            await member.remove_roles(visitor_role)
            await message.add_reaction("✅")
            await member.send(
                f"👋 Welcome, {member.display_name}!\n\n"
                "Your introduction was received and verified. "
                "You now have full access to the server. Enjoy! 🎉"
            )
        except discord.Forbidden:
            print(f"Sem permissão para atribuir cargo a {member.display_name}")
        except Exception as e:
            print(f"Erro: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        # chama o mesmo on_message com a mensagem editada
        await self.on_message(after)

async def setup(bot: commands.Bot):
    await bot.add_cog(Introduction(bot))