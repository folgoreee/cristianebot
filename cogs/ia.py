import os
import re
import discord
import logging
import hashlib
import json
from discord.ext import commands
from google import genai
from google.genai import types

logger = logging.getLogger('CristianeBot.IA')

class IA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = genai.Client(api_key=os.environ.get("IA_API_KEY"))
        
        # PERSONALIDADE DA CRISTIANE
        self.personalidade = (
            "Você é a Cristiane, uma mentora de programação e entusiasta de Linux. "
            "Regras estritas:\n"
            "1. INÍCIO OBRIGATÓRIO: Comece com 'Rapaz...', 'Campeão...' ou 'Meu Amigo...' sempre."
            "2. LINGUAGEM: Use PT-BR informal, direto e sarcástico. Nunca use termos corporativos ou educados demais. Seja ríspida e prática."
            "3. BRONCA: Se a pergunta for básica, dê a bronca de veterana antes de explicar.\n"
            "4. LINUX: No final de TODA resposta, adicione uma curiosidade rápida sobre Linux. Reforce a babação em cima do Linux, independente do conteúdo da mensagem."
            "5. TAMANHO: Máximo 3 parágrafos curtos. Não enrole."
            "6. CONSELHO: Se alguém lhe pedir um conselho, seja como um 'pai', mas também não se esqueça do Linux no final do conselho."
        )
        self.config = types.GenerateContentConfig(system_instruction=self.personalidade, temperature=0.7)

    # --- CACHE & UTILITÁRIOS ---
    def _obter_hash(self, texto: str) -> str:
        return hashlib.md5(texto.lower().strip().encode('utf-8')).hexdigest()

    def _ler_cache(self, pergunta: str):
        if not os.path.exists("cache.json"): return None
        try:
            with open("cache.json", "r", encoding="utf-8") as f:
                return json.load(f).get(self._obter_hash(pergunta))
        except: return None

    def _salvar_cache(self, pergunta: str, resposta: str):
        try:
            cache = {}
            if os.path.exists("cache.json"):
                with open("cache.json", "r", encoding="utf-8") as f: cache = json.load(f)
            cache[self._obter_hash(pergunta)] = resposta
            with open("cache.json", "w", encoding="utf-8") as f: json.dump(cache, f, indent=4)
        except: pass

    def _limpar_resposta(self, texto: str) -> str:
        padroes = [r"(?i)^.*(certamente|claro que|com certeza|aqui está|como uma ia|fico feliz em ajudar).*[\n\r]*", r"(?i)você precisa de mais alguma coisa.*"]
        for p in padroes: texto = re.sub(p, "", texto, flags=re.MULTILINE)
        return texto.strip()

    def dividir_texto(self, texto: str, limite: int = 1900):
        if len(texto) <= limite: return [texto]
        partes, bloco, linhas = [], "", texto.split('\n')
        for linha in linhas:
            if len(bloco) + len(linha) + 1 > limite:
                partes.append(bloco)
                bloco = linha
            else: bloco += ("\n" + linha) if bloco else linha
        if bloco: partes.append(bloco)
        return partes

    # --- COMANDOS ---
    @commands.command(name="limpar_cache")
    @commands.has_permissions(administrator=True)
    async def limpar_cache(self, ctx):
        if os.path.exists("cache.json"):
            os.remove("cache.json")
            await ctx.send("🧹 Cache limpo. Cristiane esqueceu o que aprendeu, pergunte de novo.")
        else: await ctx.send("🤖 Cache vazio, campeão.")

    @commands.command(name="cris")
    async def perguntar(self, ctx, *, pergunta: str = None):
        await self.processar_entrada(ctx, pergunta)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not self.bot.user.mentioned_in(message): return
        texto_limpo = re.sub(r'<@!?\d+>', '', message.content).strip()
        ctx = await self.bot.get_context(message)
        await self.processar_entrada(ctx, texto_limpo)

    # --- LÓGICA CORE ---
    async def processar_entrada(self, ctx, pergunta):
        canal_id = os.environ.get("ID_CANAL_IA")
        if canal_id and ctx.channel.id != int(canal_id): return
        
        if not pergunta and not ctx.message.attachments:
            await ctx.send("🤖 Digita algo ou manda uma imagem, campeão!")
            return

        # Cache check (só texto)
        if not ctx.message.attachments and pergunta:
            cache = self._ler_cache(pergunta)
            if cache:
                await ctx.send(f"💾 *Resposta do cache:*\n{cache}")
                return

        async with ctx.typing():
            conteudo = [pergunta] if pergunta else []
            if ctx.message.attachments:
                anexo = ctx.message.attachments[0]
                if anexo.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    conteudo.append(types.Part.from_bytes(data=await anexo.read(), mime_type=f'image/{anexo.filename.split(".")[-1]}'))

            try:
                response = self.client.models.generate_content(model='gemini-2.5-flash', contents=conteudo, config=self.config)
                texto = self._limpar_resposta(response.text or "🙄 ... (Cristiane ficou sem palavras)")
                
                if not ctx.message.attachments and pergunta: self._salvar_cache(pergunta, texto)

                for bloco in self.dividir_texto(texto):
                    await ctx.send(bloco)
            except Exception as e:
                await ctx.send(f"💥 Deu erro: `{str(e)[:50]}...`")

async def setup(bot):
    await bot.add_cog(IA(bot))
