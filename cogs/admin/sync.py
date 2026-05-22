import discord
from discord.ext import commands
import logging

logger = logging.getLogger('CristianeBot.Admin')

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync_commands(self, ctx: commands.Context, guild_especifica: str = None):
        """Sincroniza os comandos de barra (Slash Commands)"""
        async with ctx.typing():
            try:
                if guild_especifica == "local":
                    self.bot.tree.copy_global_to(guild=ctx.guild)
                    synced = await self.bot.tree.sync(guild=ctx.guild)
                    await ctx.send(f"🔄 Local: `{len(synced)}` comandos sincronizados.")
                else:
                    synced = await self.bot.tree.sync()
                    await ctx.send(f"🔄 Global: `{len(synced)}` comandos sincronizados.")
                logger.info("✅ Sincronização realizada com sucesso.")
            except Exception as e:
                await ctx.send(f"❌ Erro: {e}")
                logger.error(f"❌ Falha no sync: {e}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
