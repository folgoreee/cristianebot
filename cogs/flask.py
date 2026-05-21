import os
import logging
import threading
from flask import Flask

logger = logging.getLogger('CristianeBot.Web')
app = Flask(__name__)

@app.route('/')
def home():
    return "Cristianebot está online e operando via Cogs!"

def run_server():
    """Lógica interna para gerir a porta e o servidor Waitress/Flask"""
    porta = int(os.environ.get('PORT', 8080))
    
    if os.getenv("RENDER") or os.getenv("PORT"):
        logger.info("🌐 Ambiente de Produção detectado. Servidor Web Nativo Iniciado via Waitress.")
        try:
            from waitress import serve
            serve(app, host='0.0.0.0', port=porta)
        except ImportError:
            logger.warning("⚠️ Waitress não instalado. Iniciando com o servidor padrão do Flask...")
            app.run(host='0.0.0.0', port=porta)
    else:
        logger.info("🔧 Ambiente Local detectado. Servidor Web iniciado na porta 8080.")
        app.run(host='0.0.0.0', port=porta)

def start_web_server():
    """Inicia o servidor numa Thread separada para não bloquear o bot do Discord"""
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
