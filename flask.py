import threading
import logging
from flask import Flask
from waitress import serve
import os

app = Flask(__name__)
logger = logging.getLogger('CristianeBot.Web')

@app.route('/')
def home():
    return "Cristianebot está online e operando!"

def start_web_server():
    """Inicia o servidor web em uma thread separada."""
    porta = int(os.environ.get('PORT', 8080))
    
    def run():
        try:
            logger.info(f"🌐 Servidor Web iniciado na porta {porta}")
            serve(app, host='0.0.0.0', port=porta)
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar servidor web: {e}")

    threading.Thread(target=run, daemon=True).start()
