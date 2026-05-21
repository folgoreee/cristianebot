import os
import logging
import threading
from pathlib import Path
import discord
from discord.ext import commands
from flask import Flask

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('CristianeBot')

app = Flask(__name__)

@app.route('/')
def home():
    return "Cristianebot está online e operando via Cogs!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

intents = discord.Intents.default()
intents.message_content = True  
intents.guilds = True
intents.members = True         

class CristianeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        logger.info("📂 Iniciando varredura automatizada da pasta 'cogs'...")
        cogs_dir = Path("./cogs")
        
        if not cogs_dir.exists():
            cogs_dir.mkdir(parents=True, exist_ok=True)

        for py_file in cogs_dir.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue

            cog_name = py_file.with_suffix("").as_posix().replace("/", ".")

            try:
                await self.load_extension(cog_name)
                logger.info(f"✅ Módulo [{cog_name}] carregado!")
            except Exception as e:
                logger.error(f"❌ Falha ao carregar o módulo {cog_name}: {e}")

        # O Comando de Sync definitivo e sem erros
        @self.command(name="sync")
        @commands.is_owner()
        async def sync_commands(ctx: commands.Context, guild_especifica: str = None):
            async with ctx.typing():
                try:
                    if guild_especifica == "local":
                        # Copia os comandos das cogs para o servidor atual e sincroniza na hora
                        self.tree.copy_global_to(guild=ctx.guild)
                        synced = await self.tree.sync(guild=ctx.guild)
                        await ctx.send(f"🔄 Local: `{len(synced)}` comandos sincronizados neste servidor instantaneamente!")
                    else:
                        # Sincronização global padrão
                        synced = await self.tree.sync()
                        await ctx.send(f"🔄 Global: `{len(synced)}` comandos sincronizados para todos os servidores.")
                except Exception as e:
                    await ctx.send(f"❌ Erro na sincronização: {e}")
                    logger.error(f"❌ Falha no sync: {e}", exc_info=True)

    async def on_ready(self):
        logger.info(f"🚀 {self.user.name} está ONLINE!")

if __name__ == "__main__":
    if os.getenv("RENDER") or os.getenv("PORT"):
        logger.info("🌐 Ambiente de Produção detectado. Servidor Web ativado.")
        threading.Thread(target=run_web, daemon=True).start()

    bot = CristianeBot()
    
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token, log_handler=None)
    else:
        logger.critical("❌ ERRO CRÍTICO: DISCORD_TOKEN não encontrado!")
