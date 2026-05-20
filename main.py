import os
import discord
import threading
import google.generativeai as genai
from flask import Flask
from discord.ext import commands

# --- Configuração IA ---
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

# --- Servidor Web (para o UptimeRobot) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot está online!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- Configuração Bot Discord ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.command(name='mentor')
async def mentor(ctx, *, pergunta: str):
    async with ctx.typing():
        response = model.generate_content(f"Mentor técnico: {pergunta}")
        await ctx.send(f"🤖 **Mentor:**\n{response.text}")

# --- Iniciar ambos ---
if __name__ == "__main__":
    # Roda o servidor web em uma thread separada
    threading.Thread(target=run_web).start()
    # Roda o bot
    bot.run(os.getenv('DISCORD_TOKEN'))
