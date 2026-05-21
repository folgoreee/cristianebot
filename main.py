import os
import logging
import threading
from pathlib import Path
import discord
from discord.ext import commands
from flask import Flask

# --- 1. LOGS SIMPLIFICADOS ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('CristianeBot')

# --- 2. SERVIDOR WEB NATIVO (Sem dependências inúteis) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Cristianebot está online e operando via Cogs!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- 3. CLASSE DO BOT E SISTEMA COGS ---
intents = discord.Intents.default()
intents.message_content = True  # Obrigatório para a Cristiane ler o !cris e !sync
intents.guilds = True
intents.members = True         # Importante para puxar os nomes corretamente no Cog de Ranking

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

            # Converte o arquivo do Linux para formato de módulo Python (ex: cogs.ia)
            cog_name = py_file.with_suffix("").as_posix().replace("/", ".")

            try:
                await self.load_extension(cog_name)
                logger.info(f"✅ Módulo [{cog_name}] carregado!")
            except Exception as e:
                logger.error(f"❌ Falha ao carregar o módulo {cog_name}: {e}")

        # Adiciona o comando de sincronização dos Slash Commands dentro do próprio bot
        @self.command(name="sync")
        @commands.is_owner()  # Apenas você (dono do Token) pode usar
        async def sync_commands(ctx: commands.Context):
            async with ctx.typing():
                try:
                    logger.info("🔄 Sincronizando comandos de barra globalmente...")
                    synced = await self.tree.sync()
                    await ctx.send(f"🔄 Sucesso! Sincronizados `{len(synced)}` comandos de barra globalmente.")
                    logger.info(f"✅ {len(synced)} comandos de barra sincronizados com sucesso!")
                except Exception as e:
                    await ctx.send(f"❌ Erro ao sincronizar comandos: {e}")
                    logger.error(f"❌ Falha na sincronização da árvore de comandos: {e}")

    async def on_ready(self):
        logger.info(f"🚀 {self.user.name} está ONLINE!")

# --- 4. INICIALIZAÇÃO DO ECOSSISTEMA ---
if __name__ == "__main__":
    # Só liga o Flask na nuvem (Render) para economizar processamento local
    if os.getenv("RENDER") or os.getenv("PORT"):
        logger.info("🌐 Ambiente de Production detectado. Servidor Web ativado.")
        threading.Thread(target=run_web, daemon=True).start()

    bot = CristianeBot()
    
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token, log_handler=None)
    else:
        logger.critical("❌ ERRO CRÍTICO: DISCORD_TOKEN não encontrado!")
