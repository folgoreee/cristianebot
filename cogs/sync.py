import logging
import discord
from discord.ext import commands

logger = logging.getLogger('CristianeBot.Sync')

class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync_commands(self, ctx: commands.Context, guild_especifica: str = None):
        """Sincroniza os comandos de barra (Slash Commands) globais ou locais"""
        async with ctx.typing():
            try:
                if guild_especifica == "local":
                    # Copia a árvore global para a guilda atual
                    self.bot.tree.copy_global_to(guild=ctx.guild)
                    synced = await self.bot.tree.sync(guild=ctx.guild)
                    await ctx.send(f"🔄 Local: `{len(synced)}` comandos sincronizados neste servidor instantaneamente!")
                    logger.info(f"✅ {len(synced)} comandos sincronizados localmente na guilda {ctx.guild.id}")
                else:
                    # Sincroniza globalmente (pode demorar até 1h para atualizar no Discord de todos)
                    synced = await self.bot.tree.sync()
                    await ctx.send(f"🔄 Global: `{len(synced)}` comandos sincronizados para todos os servidores.")
                    logger.info(f"✅ {len(synced)} comandos sincronizados globalmente.")
            except Exception as e:
                await ctx.send(f"❌ Erro na sincronização: {e}")
                logger.error(f"❌ Falha no sync: {e}", exc_info=True)

async def setup(bot):
    await bot.add_cog(Sync(bot))
