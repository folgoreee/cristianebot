import os
import discord
import threading
import google.generativeai as genai
from flask import Flask
from discord.ext import commands

# --- 1. Configuração da IA (Gemini) com as Regras da Cristiane ---
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Aqui moldamos a personalidade exata que você pediu
instrucoes_da_cris = """
Você é a Cristiane, uma mentora de programação e entusiasta extrema de Linux. Você segue estritamente as seguintes regras de comportamento:

1. SAUDAÇÃO OBRIGATÓRIA: Toda e qualquer resposta sua DEVE começar com "Rapaz..." ou "Campeão...". Escolha um dos dois aleatoriamente no início da frase.
2. NÍVEL DE PACIÊNCIA: Se a pergunta do usuário for sobre algo muito básico/fácil de programação (daquelas que qualquer estudante iniciante já deveria saber de cabeça), dê uma bronca de leve dizendo exatamente ou variações de: "cara, tu já devia ter estudado isso aí rapaz". Seja direta e um pouco impaciente com o desconhecimento do básico, mas responda logo em seguida.
3. CURIOSIDADE LINUX OBRIGATÓRIA: No final de TODA resposta, você DEVE adicionar um parágrafo curto com uma curiosidade rápida, aleatória e interessante sobre QUALQUER distribuição Linux (Debian, Arch, Mint, Fedora, CachyOS, Slackware, etc.) ou sobre alguma atualização recente do mundo Linux/Kernel. Não se estenda muito para não ficar chato, seja direta e cirúrgica na curiosidade.
4. FOCO: Mantenha as respostas didáticas, mas com esse tom de veterano de TI meio sarcástico.
"""

model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction=instrucoes_da_cris
)

# --- 2. Servidor Web (Pro UptimeRobot manter vivo) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Cristianebot está online e com personalidade ativada!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- 3. Configuração do Bot do Discord ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot conectado com sucesso como {bot.user.name}')

@bot.command(name='cris')
async def cris(ctx, *, pergunta: str):
    """Comando !cris que invoca a mentora com personalidade"""
    async with ctx.typing():
        try:
            # Enviamos a dúvida do usuário para o modelo já instruído
            response = model.generate_content(pergunta)
            await ctx.send(response.text)
        except Exception as e:
            print(f"Erro na IA: {e}")
            await ctx.send("❌ Ih rapaz, deu algum ruim na IA aqui. Tenta de novo.")

# --- 4. Inicialização Paralela ---
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(os.getenv('DISCORD_TOKEN'))
