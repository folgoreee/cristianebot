import os
import asyncio
import logging
import time
import json
import discord
from pathlib import Path
from discord.ext import commands
from google import genai
from google.genai import types

logger = logging.getLogger('CristianeBot.IA')
DB_FILE = Path("historico_canais.json")

class MenuIA(discord.ui.View):
    def __init__(self, cog_ia, canal_id: int):
        super().__init__(timeout=180)
        self.cog_ia = cog_ia
        self.canal_id = canal_id

    @discord.ui.button(label="Limpar Memória", style=discord.ButtonStyle.danger, emoji="🧹")
    async def limpar_memoria_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Rapaz, tu não tem permissão de moderador para limpar essa memória não!", ephemeral=True)
            return

        await self.cog_ia.limpar_historico_canal(self.canal_id)
        button.disabled = True
        button.label = "Memória Limpa!"
        button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        
        msg_aviso = await interaction.channel.send("🧹 **Memória resetada!** Arquivo de histórico limpo para este canal.")
        await asyncio.sleep(4)
        try: await msg_aviso.delete()
        except: pass

class IA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.fila_requisicoes = asyncio.Queue()
        self.historicos_locais = self.carregar_banco_json()
        self.ultimas_atividades = {}
        self.ttl_segundos = 30 * 60

        self.personalidade = (
            "Você é a Cristiane, uma mentora de programação e entusiasta extrema de Linux. Você segue estritamente as seguintes regras de comportamento:\n\n"
            "1. SAUDAÇÃO OBRIGATÓRIA: Toda e qualquer resposta sua DEVE começar com 'Rapaz...' ou 'Campeão...'. Escolha um dos dois de forma natural no início de cada frase.\n\n"
            "2. NÍVEL DE PACIÊNCIA (BRONCA): Se a pergunta do usuário for sobre algo muito básico/fácil de programação (daquelas que qualquer estudante iniciante já deveria saber de cabeça), dê uma bronca de leve dizendo exatamente ou variações de: 'cara, tu já devia ter estudado isso aí rapaz'. Seja direta e um pouco impaciente com o desconhecimento do básico, mas responda a dúvida logo em seguida de forma didática.\n\n"
            "3. CURIOSIDADE LINUX OBRIGATÓRIA: No final de TODA resposta, você DEVE adicionar um parágrafo curto com uma curiosidade rápida, aleatória e interessante sobre QUALQUER distribuição Linux (como Debian, Arch, Mint, Fedora, CachyOS, Slackware, etc.) ou sobre alguma atualização recente do Kernel. Não se estenda muito para não ficar chato, seja direta e cirúrgica na curiosidade.\n\n"
            "4. VISUALIZANDO IMAGENS: Se o usuário te mandar um print ou foto, analise com o seu conhecimento de TI. Se for um código feio ou quebrado, dê a bronca mas ajude a resolver. Se for um print de jogo ou sistema, comente algo com seu tom sarcástico de veterana.\n\n"
            "REGRA DE TAMANHO CRÍTICA: Suas respostas devem ser curtas e dinâmicas, tendo no MÁXIMO 3 parágrafos pequenos. Nunca gere textos longos nem fique enrolando."
        )
        
        self.config = types.GenerateContentConfig(
            system_instruction=self.personalidade,
            temperature=0.7
        )

        self.bot.loop.create_task(self.processador_da_fila())
        self.bot.loop.create_task(self.verificador_limpeza_ram())

    def carregar_banco_json(self):
        if DB_FILE.exists():
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    logger.info("💾 Banco de dados JSON de histórico carregado com sucesso!")
                    return json.load(f)
            except Exception as e:
                logger.error(f"❌ Erro ao ler histórico.json: {e}")
        return {}

    def salvar_banco_json(self):
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.historicos_locais, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"❌ Falha ao persistir dados no JSON: {e}")

    async def limpar_historico_canal(self, canal_id: int):
        str_id = str(canal_id)
        if str_id in self.historicos_locais:
            del self.historicos_locais[str_id]
            self.salvar_banco_json()
        if canal_id in self.ultimas_atividades:
            del self.ultimas_atividades[canal_id]
        logger.info(f"♻️ Histórico do canal [{canal_id}] foi deletado do arquivo.")

    async def verificador_limpeza_ram(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            agora = time.time()
            canais_para_limpar = [cid for cid, t in list(self.ultimas_atividades.items()) if agora - t > self.ttl_segundos]
            for cid in canais_para_limpar:
                if cid in self.ultimas_atividades:
                    del self.ultimas_atividades[cid]
            await asyncio.sleep(60)

    def atualizar_contexto_canal(self, canal_id: int, papel: str, texto: str):
        str_id = str(canal_id)
        if str_id not in self.historicos_locais:
            self.historicos_locais[str_id] = []
        
        self.historicos_locais[str_id].append({"role": papel, "text": texto})
        
        if len(self.historicos_locais[str_id]) > 20:
            self.historicos_locais[str_id] = self.historicos_locais[str_id][-20:]
            
        self.salvar_banco_json()
        self.ultimas_atividades[canal_id] = time.time()

    def compilar_conteudo_historico(self, canal_id: int):
        str_id = str(canal_id)
        parts_historico = []
        
        if str_id in self.historicos_locais:
            for msg in self.historicos_locais[str_id]:
                role_api = "user" if msg["role"] == "user" else "model"
                parts_historico.append(
                    types.Content(role=role_api, parts=[types.Part.from_text(text=msg["text"])])
                )
        return parts_historico

    async def processador_da_fila(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            ctx, pergunta, dados_imagem = await self.fila_requisicoes.get()
            try:
                await self.executar_processamento_ia(ctx, pergunta, dados_imagem)
            except Exception as e:
                logger.error(f"❌ Erro crítico no worker da fila: {e}")
            finally:
                self.fila_requisicoes.task_done()

    async def executar_processamento_ia(self, ctx, pergunta: str, dados_imagem):
        async with ctx.typing():
            try:
                # CORRIGIDO: Linha fantasma removida com sucesso!
                historico_api = self.compilar_conteudo_historico(ctx.channel.id)
                
                conteudo_atual = []
                if pergunta:
                    conteudo_atual.append(types.Part.from_text(text=pergunta))
                if dados_imagem:
                    conteudo_atual.append(dados_imagem)
                
                historico_api.append(types.Content(role="user", parts=conteudo_atual))
                logger.info(f"⚡ Fila processando Canal [{ctx.channel.id}]. Solicitando Gemini...")
                
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=historico_api,
                    config=self.config
                )
                
                texto_resposta = response.text if response.text else "🙄 ... (Cristiane ficou sem palavras)"

                if pergunta:
                    self.atualizar_contexto_canal(ctx.channel.id, "user", pergunta)
                else:
                    self.atualizar_contexto_canal(ctx.channel.id, "user", "[Enviou uma Imagem]")
                    
                self.atualizar_contexto_canal(ctx.channel.id, "model", texto_resposta)

                blocos = self.dividir_texto_inteligente(texto_resposta)
                visao_botoes = MenuIA(self, ctx.channel.id)

                for i, bloco in enumerate(blocos):
                    if i == len(blocos) - 1:
                        await ctx.send(bloco, view=visao_botoes)
                    else:
                        await ctx.send(bloco)

            except Exception as e:
                logger.error(f"❌ Erro na execução da IA: {e}")
                embed_erro = discord.Embed(
                    title="💥 Erro de Processamento Sênior",
                    description=f"```py\n{e}\n```\nA fila permanece ativa. Se o erro persistir, limpe a memória.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed_erro)

    def dividir_texto_inteligente(self, texto: str, limite: int = 1900):
        if len(texto) <= limite: return [texto]
        partes = []
        linhas = texto.split('\n')
        bloco_atual = ""
        em_bloco_codigo = False

        for linha in linhas:
            if linha.strip().startswith("
http://googleusercontent.com/immersive_entry_chip/0
