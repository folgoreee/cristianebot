import os
import asyncio
import logging
import time
import json
import re
import discord
from pathlib import Path
from discord.ext import commands
from google import genai
from google.genai import types

logger = logging.getLogger('CristianeBot.IA')
DB_FILE = Path("historico_canais.json")

class IA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.fila_requisicoes = asyncio.Queue()
        self.historicos_locais = self.carregar_banco_json()
        self.ultimas_atividades = {}
        self.ttl_segundos = 30 * 60 

        # --- PERSONALIDADE ---
        self.personalidade = (
            "Você é a Cristiane, uma mentora de programação e entusiasta de Linux. "
            "Regras estritas:\n"
            "1. INÍCIO OBRIGATÓRIO: Comece com 'Rapaz...', 'Campeão...' ou 'Meu Amigo...' sempre."
            "2. LINGUAGEM: Use PT-BR informal, direto e sarcástico. Nunca use termos corporativos ou educados demais (ex: 'Com certeza', 'Como IA', 'Estou aqui para ajudar', 'Espero que isso resolva'). Seja ríspida e prática."
            "3. BRONCA: Se a pergunta for básica, dê a bronca de veterana antes de explicar.\n"
            "4. LINUX: No final de TODA resposta, adicione uma curiosidade rápida sobre Linux. Reforce a babação em cima do Linux, independente do conteúdo da mensagem."
            "5. TAMANHO: Máximo 3 parágrafos curtos. Não enrole."
            "6. CONSELHO: Se alguém lhe pedir um conselho, seja como um 'pai', mas também não se esqueça do Linux no final do conselho."
        )
        
        self.config = types.GenerateContentConfig(
            system_instruction=self.personalidade,
            temperature=0.7
        )
        self.bot.loop.create_task(self.processador_da_fila())
        self.bot.loop.create_task(self.verificador_limpeza_ram())

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

    # --- MÉTODOS JSON E GERENCIAMENTO ---
    def carregar_banco_json(self):
        if DB_FILE.exists():
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: pass
        return {}

    def salvar_banco_json(self):
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.historicos_locais, f, ensure_ascii=False, indent=4)
        except: pass

    async def limpar_historico_canal(self, canal_id: int):
        str_id = str(canal_id)
        if str_id in self.historicos_locais:
            del self.historicos_locais[str_id]
            self.salvar_banco_json()
        logger.info(f"♻️ Histórico do canal [{canal_id}] zerado.")

    async def verificador_limpeza_ram(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            agora = time.time()
            canais_para_limpar = [cid for cid, t in list(self.ultimas_atividades.items()) if agora - t > self.ttl_segundos]
            for cid in canais_para_limpar:
                if cid in self.ultimas_atividades: del self.ultimas_atividades[cid]
            await asyncio.sleep(60)

    def atualizar_contexto_canal(self, canal_id: int, papel: str, texto: str):
        str_id = str(canal_id)
        if str_id not in self.historicos_locais: self.historicos_locais[str_id] = []
        self.historicos_locais[str_id].append({"role": papel, "text": texto})
        if len(self.historicos_locais[str_id]) > 20: self.historicos_locais[str_id] = self.historicos_locais[str_id][-20:]
        self.salvar_banco_json()
        self.ultimas_atividades[canal_id] = time.time()

    def compilar_conteudo_historico(self, canal_id: int):
        str_id = str(canal_id)
        parts_historico = []
        if str_id in self.historicos_locais:
            for msg in self.historicos_locais[str_id]:
                role_api = "user" if msg["role"] == "user" else "model"
                parts_historico.append(types.Content(role=role_api, parts=[types.Part.from_text(text=msg["text"])]))
        return parts_historico

    # --- PROCESSAMENTO ---
    async def processador_da_fila(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            ctx, pergunta, dados_imagem = await self.fila_requisicoes.get()
            try:
                await self.executar_processamento_ia(ctx, pergunta, dados_imagem)
            except Exception as e:
                logger.error(f"❌ Erro crítico: {e}")
            finally:
                self.fila_requisicoes.task_done()

    async def executar_processamento_ia(self, ctx, pergunta: str, dados_imagem):
        async with ctx.typing():
            try:
                historico_api = self.compilar_conteudo_historico(ctx.channel.id)
                conteudo_atual = []
                if pergunta: conteudo_atual.append(types.Part.from_text(text=pergunta))
                if dados_imagem: conteudo_atual.append(dados_imagem)
                
                historico_api.append(types.Content(role="user", parts=conteudo_atual))
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=historico_api,
                    config=self.config
                )
                
                texto_raw = response.text if response.text else "🙄 ... (Cristiane ficou sem palavras)"
                texto_final = self._limpar_resposta(texto_raw)

                if pergunta: self.atualizar_contexto_canal(ctx.channel.id, "user", pergunta)
                else: self.atualizar_contexto_canal(ctx.channel.id, "user", "[Enviou uma Imagem]")
                self.atualizar_contexto_canal(ctx.channel.id, "model", texto_final)

                blocos = self.dividir_texto_inteligente(texto_final)
                # Botões removidos aqui
                for bloco in blocos:
                    await ctx.send(bloco)

            except Exception as e:
                await ctx.send(f"💥 Deu ruim aqui: {e}")

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

    async def pre_processar_e_enfileirar(self, ctx, pergunta: str):
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
        await self.fila_requisicoes.put((ctx, pergunta, dados_imagem))

    @commands.command(name="cris")
    @commands.guild_only()
    async def perguntar(self, ctx, *, pergunta: str = None):
        await self.pre_processar_e_enfileirar(ctx, pergunta)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id: return
        if self.bot.user.mentioned_in(message):
            ctx = await self.bot.get_context(message)
            texto_limpo = re.sub(r'<@!?\d+>', '', message.content).strip()
            await self.pre_processar_e_enfileirar(ctx, texto_limpo)

async def setup(bot):
    await bot.add_cog(IA(bot))
