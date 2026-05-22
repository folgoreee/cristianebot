import os
import logging
from pathlib import Path
import discord
from discord.ext import commands
from keep_alive import keep_alive

# --- CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger('CristianeBot')

intents = discord.Intents.default()
intents.message_content = True

class CristianeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Carrega as Cogs automaticamente da pasta ./cogs
        for file in Path("./cogs").rglob("*.py"):
            if not file.name.startswith("__"):
                cog_path = file.with_suffix("").as_posix().replace("/", ".")
                try:
                    await self.load_extension(cog_path)
                    logger.info(f"✅ Módulo {cog_path} carregado!")
                except Exception as e:
                    logger.error(f"❌ Falha ao carregar {cog_path}: {e}")

    async def on_ready(self):
        logger.info(f"🚀 {self.user.name} está ONLINE!")

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    # Inicia o servidor Web (Flask)
    if os.getenv("RENDER"):
        web_server.start_web_server()

    bot = CristianeBot()
    token = os.getenv('DISCORD_TOKEN')
    
    if token:
        bot.run(token)
    else:
        logger.critical("❌ DISCORD_TOKEN não encontrado!")
