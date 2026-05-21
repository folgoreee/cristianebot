import os
import logging
import threading
from pathlib import Path
import discord
from discord.ext import commands
from flask import Flask

# --- 1. CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('CristianeBot')

# --- 2. SERVIDOR WEB NATIVO PARA O RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Cristianebot está online e operando via Cogs!"

# --- 3. CLASSE DO BOT E SISTEMA COGS ---
intents = discord.Intents.default()
intents.message_content = True  # Obrigatório para ler prefixos e menções
intents.guilds = True
intents.members = True          # Obrigatório para buscar membros no ranking

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


# Instanciação única do Bot
bot = CristianeBot()


# --- 4. COMANDO DE SYNC (ESTRUTURADO E SEGURO) ---
@bot.command(name="sync")
@commands.is_owner()
async def sync_commands(ctx: commands.Context, guild_especifica: str = None):
    """Sincroniza os comandos de barra (Slash Commands) globais ou locais"""
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


# --- 5. INICIALIZAÇÃO DO SISTEMA ---
if __name__ == "__main__":
    # Inicia o servidor com Waitress se estiver em ambiente de produção (Render)
    if os.getenv("RENDER") or os.getenv("PORT"):
        logger.info("🌐 Ambiente de Produção detectado. Servidor Web Nativo Iniciado via Waitress.")
        try:
            from waitress import serve
            porta = int(os.environ.get('PORT', 8080))
            threading.Thread(
                target=lambda: serve(app, host='0.0.0.0', port=porta),
                daemon=True
            ).start()
        except ImportError:
            logger.warning("⚠️ Waitress não instalado. Iniciando com o servidor padrão do Flask...")
            porta = int(os.environ.get('PORT', 8080))
            threading.Thread(
                target=lambda: app.run(host='0.0.0.0', port=porta),
                daemon=True
            ).start()
    
    # Execução segura do Bot do Discord
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token, log_handler=None)
    else:
        logger.critical("❌ ERRO CRÍTICO: DISCORD_TOKEN não encontrado nas variáveis de ambiente!")
