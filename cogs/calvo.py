import discord
from discord.ext import commands

class Calvo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # O comando !calvo
    @commands.command(name="calvo")
    async def calvo_command(self, ctx):
        """Diz a verdade crucial sobre a capilaridade do usuário."""
        # ctx.author.mention marca a pessoa que enviou a mensagem
        await ctx.send(f"Atenção {ctx.author.mention}, o diagnóstico foi fechado: você é 100% calvo! 👨‍🦲")

# Função obrigatória para o discord.py carregar o Cog
async def setup(bot):
    await bot.add_cog(Calvo(bot))