import os
import logging
from pathlib import Path
import discord
from discord.ext import commands
from keep_alive import start_web_server 
from dotenv import load_dotenv

# 1. Carrega as variáveis de ambiente do arquivo .env invisivelmente
load_dotenv()

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
                # 2. Extrai o caminho relativo e converte para módulos de forma segura
                cog_path = ".".join(file.relative_to(".").with_suffix("").parts)
                try:
                    await self.load_extension(cog_path)
                    logger.info(f"✅ Módulo {cog_path} carregado!")
                except Exception as e:
                    logger.error(f"❌ Falha ao carregar {cog_path}: {e}")

    async def on_ready(self):
        logger.info(f"🚀 {self.user.name} está ONLINE!")

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    # Inicia o servidor Web (Flask/Waitress)
    # Checagem dupla (RENDER ou PORT) para garantir que ele ative na nuvem
    if os.getenv("RENDER") or os.getenv("PORT"):
        # Chamando a função diretamente, sem o prefixo web_server
        start_web_server() 

    bot = CristianeBot()
    token = os.getenv('DISCORD_TOKEN')
    
    if token:
        # 3. Desativa o log duplicado do discord.py para usar o seu customizado
        bot.run(token, log_handler=None)
    else:
        logger.critical("❌ DISCORD_TOKEN não encontrado nas variáveis de ambiente!")
