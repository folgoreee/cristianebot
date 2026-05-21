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

# --- 2. SERVIDOR WEB NATIVO ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Cristianebot está online e operando via Cogs!"

# --- 3. CLASSE DO BOT E SISTEMA COGS ---
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

            # Converte o caminho do arquivo para o formato de importação do Python (ex: cogs.ia)
            cog_name = py_file.with_suffix("").as_posix().replace("/", ".")

            try:
                await self.load_extension(cog_name)
                logger.info(f"✅ Módulo [{cog_name}] carregado!")
            except Exception as e:
                logger.error(f"❌ Falha ao carregar o módulo {cog_name}: {e}")

    async def on_ready(self):
        logger.info(f"🚀 {self.user.name} está ONLINE!")

# Instanciando o bot globalmente para os decoradores funcionarem perfeitamente
bot = CristianeBot()

# --- 4. COMANDO DE SYNC (ISOLADO E GARANTIDO) ---
@bot.command(name="sync")
@commands.is_owner()
async def sync_commands(ctx: commands.Context, guild_especifica: str = None):
    async with ctx.typing():
        try:
            if guild_especifica == "local":
                bot.tree.copy_global_to(guild=ctx.guild)
                synced = await bot.tree.sync(guild=ctx.guild)
                await ctx.send(f"🔄 Local: `{len(synced)}` comandos sincronizados neste servidor instantaneamente!")
                logger.info(f"✅ {len(synced)} comandos sincronizados localmente na guilda {ctx.guild.id}")
            else:
                synced = await bot.tree.sync()
                await ctx.send(f"🔄 Global: `{len(synced)}` comandos sincronizados para todos os servidores.")
                logger.info(f"✅ {len(synced)} comandos sincronizados globalmente.")
        except Exception as e:
            await ctx.send(f"❌ Erro na sincronização: {e}")
            logger.error(f"❌ Falha no sync: {e}", exc_info=True)

# --- 5. INICIALIZAÇÃO ---
if __name__ == "__main__":
    # 1. Corrige o erro de sintaxe do hífen e inicia o servidor com waitress se estiver no Render
    if os.getenv("RENDER") or os.getenv("PORT"):
        logger.info("🌐 Ambiente de Produção detectado. Servidor Web Nativo Iniciado via Waitress.")
        from waitress import serve
        
        # Inicia o Flask em uma Thread separada para não bloquear a execução do bot do Discord
        porta = int(os.environ.get('PORT', 8080))
        threading.Thread(
            target=lambda: serve(app, host='0.0.0.0', port=porta),
            daemon=True
        ).start()
    
    # 2. Verificação de segurança do Token
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token, log_handler=None)
    else:
        logger.critical("❌ ERRO CRÍTICO: DISCORD_TOKEN não encontrado!")
