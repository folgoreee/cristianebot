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
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        
        # --- PERSONALIDADE ---
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
        
        self.config = types.GenerateContentConfig(
            system_instruction=self.personalidade,
            temperature=0.7
        )

    # --- CACHE ---
    def _obter_hash(self, texto: str) -> str:
        return hashlib.md5(texto.lower().strip().encode('utf-8')).hexdigest()

    def _ler_cache(self, pergunta: str):
        if not os.path.exists("cache.json"): return None
        try:
            with open("cache.json", "r", encoding="utf-8") as f:
                cache = json.load(f)
                return cache.get(self._obter_hash(pergunta))
        except: return None

    def _salvar_cache(self, pergunta: str, resposta: str):
        try:
            cache = {}
            if os.path.exists("cache.json"):
                with open("cache.json", "r", encoding="utf-8") as f: cache = json.load(f)
            cache[self._obter_hash(pergunta)] = resposta
            with open("cache.json", "w", encoding="utf-8") as f: json.dump(cache, f, indent=4)
        except: pass

    # --- FILTRO DE LIMPEZA ---
    def _limpar_resposta(self, texto: str) -> str:
        padroes_lixo = [
            r"(?i)^.*(certamente|claro que|com certeza|aqui está|como uma ia|como um modelo de linguagem|fico feliz em ajudar|espero que isso ajude).*[\n\r]*",
            r"(?i)você precisa de mais alguma coisa.*",
            r"(?i)se tiver mais dúvidas.*"
        ]
        for padrao in padroes_lixo:
            texto = re.sub(padrao, "", texto, flags=re.MULTILINE)
        return texto.strip()

    # --- DIVISÃO DE TEXTO ---
    def dividir_texto_inteligente(self, texto: str, limite: int = 1900):
        if len(texto) <= limite: return [texto]
        partes = []
        linhas = texto.split('\n')
        bloco_atual = ""
        for linha in linhas:
            if len(bloco_atual) + len(linha) + 1 > limite:
                partes.append(bloco_atual)
                bloco_atual = linha
            else:
                bloco_atual += "\n" + linha if bloco_atual else linha
        if bloco_atual: partes.append(bloco_atual)
        return partes

    # --- EXECUÇÃO DA IA ---
    async def processar_ia(self, ctx, pergunta: str, dados_imagem):
        # Cache check: Só checa se não for imagem
        if not dados_imagem and pergunta:
            cache_resposta = self._ler_cache(pergunta)
            if cache_resposta:
                await ctx.send(f"💾 *Resposta recuperada do cache:* \n{cache_resposta}")
                return

        async with ctx.typing():
            try:
                conteudo = []
                if pergunta: conteudo.append(types.Part.from_text(text=pergunta))
                if dados_imagem: conteudo.append(dados_imagem)
                
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=conteudo,
                    config=self.config
                )
                
                texto_raw = response.text if response.text else "🙄 ... (Cristiane ficou sem palavras)"
                texto_final = self._limpar_resposta(texto_raw)

                # Salvar no cache se não for imagem
                if not dados_imagem and pergunta:
                    self._salvar_cache(pergunta, texto_final)

                for bloco in self.dividir_texto_inteligente(texto_final):
                    await ctx.send(bloco)

            except Exception as e:
                logger.error(f"❌ Erro na IA: {e}")
                if "429" in str(e):
                    await ctx.send("🛑 **Cota diária esgotada.** Tente amanhã ou habilite o faturamento no Google AI Studio.")
                else:
                    await ctx.send(f"💥 Deu ruim no motor: `{str(e)[:50]}...`")

    # --- INTERFACE ---
    async def pre_processar(self, ctx, pergunta: str):
        canal_permitido_id = os.environ.get("AI_CHANNEL_ID")
        if canal_permitido_id and ctx.channel.id != int(canal_permitido_id): return
        
        if not pergunta and not ctx.message.attachments:
            await ctx.send("🤖 Campeão, digita algo ou manda uma imagem!")
            return

        dados_imagem = None
        if ctx.message.attachments:
            anexo = ctx.message.attachments[0]
            if anexo.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                dados_imagem = types.Part.from_bytes(data=await anexo.read(), mime_type=f'image/{anexo.filename.split(".")[-1]}')
        
        await self.processar_ia(ctx, pergunta, dados_imagem)

    @commands.command(name="cris")
    @commands.guild_only()
    async def perguntar(self, ctx, *, pergunta: str = None):
        await self.pre_processar(ctx, pergunta)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id: return
        if self.bot.user.mentioned_in(message):
            ctx = await self.bot.get_context(message)
            texto_limpo = re.sub(r'<@!?\d+>', '', message.content).strip()
            await self.pre_processar(ctx, texto_limpo)

async def setup(bot):
    await bot.add_cog(IA(bot))
