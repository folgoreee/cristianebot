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

# ===================================================================
# INTERFACE DO BOTÃO DE LIMPEZA (discord.ui.View)
# ===================================================================
class MenuIA(discord.ui.View):
    def __init__(self, cog_ia, canal_id: int):
        super().__init__(timeout=180)
        self.cog_ia = cog_ia
        self.canal_id = canal_id

    @discord.ui.button(label="Limpar Memória", style=discord.ButtonStyle.danger, emoji="🧹")
    async def limpar_memoria_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verifica se quem clicou tem permissão de gerenciar mensagens ou é o dono do servidor
        if not interaction.user.guild_permissions.manage_messages and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "❌ Rapaz, tu não tens permissão de moderador para limpar essa memória não!", 
                ephemeral=True
            )
            return

        await self.cog_ia.limpar_historico_canal(self.canal_id)
        
        button.disabled = True
        button.label = "Memória Limpa!"
        button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        
        msg_aviso = await interaction.channel.send("🧹 **Memória resetada!** Arquivo de histórico limpo para este canal.")
        await asyncio.sleep(4)
        try:
            await msg_aviso.delete()
        except Exception:
            pass

# ===================================================================
# COG PRINCIPAL DA INTELIGÊNCIA ARTIFICIAL
# ===================================================================
class IA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        
        # Fila assíncrona para processamento linear seguro (evita Rate Limits)
        self.fila_requisicoes = asyncio.Queue()
        
        # Histórico persistente carregado do arquivo JSON local
        self.historicos_locais = self.carregar_banco_json()
        
        # Controle de timestamps de ociosidade
        self.ultimas_atividades = {}
        self.ttl_segundos = 30 * 60  # 30 minutos

        self.personalidade = (
            "Você é a Cristiane, uma mentora de programação e entusiasta extrema de Linux. Você segue estritamente as seguintes regras de comportamento:\n\n"
            "1. SAUDAÇÃO OBRIGATÓRIA: Toda e qualquer resposta sua DEVE começar com 'Rapaz...' ou 'Campeão...'. Escolha um dos dois de forma natural no início de cada frase.\n\n"
            "2. NÍVEL DE PACIÊNCIA (BRONCA): Se a pergunta do usuário for sobre algo muito básico/fácil de programação (daquelas que qualquer estudante iniciante já deveria saber de cabeça), dê uma bronca de leve dizendo exatamente ou variações de: 'cara, tu já devias ter estudado isso aí rapaz'. Seja direta e um pouco impaciente com o desconhecimento do básico, mas responda a dúvida logo em seguida de forma didática.\n\n"
            "3. CURIOSIDADE LINUX OBRIGATÓRIA: No final de TODA resposta, você DEVE adicionar um parágrafo curto com uma curiosidade rápida, aleatória e interessante sobre QUALQUER distribuição Linux (como Debian, Arch, Mint, Fedora, CachyOS, Slackware, etc.) ou sobre alguma atualização recente do Kernel. Não se estenda muito para não ficar chato, seja direta e cirúrgica na curiosidade.\n\n"
            "4. VISUALIZANDO IMAGENS: Se o usuário te mandar um print ou foto, analise com o seu conhecimento de TI. Se for um código feio ou quebrado, dê a bronca mas ajude a resolver. Se for um print de jogo ou sistema, comente algo com seu tom sarcástico de veterana.\n\n"
            "REGRA DE TAMANHO CRÍTICA: Suas respostas devem ser curtas e dinâmicas, tendo no MÁXIMO 3 parágrafos pequenos. Nunca gere textos longos nem fique enrolando."
        )
        
        self.config = types.GenerateContentConfig(
            system_instruction=self.personalidade,
            temperature=0.7
        )

        # Inicializa as tarefas em segundo plano para o loop do bot
        self.bot.loop.create_task(self.processador_da_fila())
        self.bot.loop.create_task(self.verificador_limpeza_ram())

    # --- SISTEMA DE PERSISTÊNCIA JSON ---
    def carregar_banco_json(self):
        if DB_FILE.exists():
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    logger.info("💾 Banco de dados JSON de histórico carregado!")
                    return json.load(f)
            except Exception as e:
                logger.error(f"❌ Erro ao ler historico_canais.json: {e}")
        return {}

    def salvar_banco_json(self):
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.historicos_locais, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"❌ Falha ao salvar no JSON: {e}")

    async def limpar_historico_canal(self, canal_id: int):
        str_id = str(canal_id)
        if str_id in self.historicos_locais:
            del self.historicos_locais[str_id]
            self.salvar_banco_json()
        if canal_id in self.ultimas_atividades:
            del self.ultimas_atividades[canal_id]
        logger.info(f"♻️ Histórico do canal [{canal_id}] foi zerado.")

    async def verificador_limpeza_ram(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            agora = time.time()
            canais_para_limpar = [cid for cid, t in list(self.ultimas_atividades.items()) if agora - t > self.ttl_segundos]
            for cid in canais_para_limpar:
                if cid in self.ultimas_atividades:
                    del self.ultimas_atividades[cid]
                logger.info(f"⏳ Canal [{cid}] ocioso no cache de RAM.")
            await asyncio.sleep(60)

    def atualizar_contexto_canal(self, canal_id: int, papel: str, texto: str):
        str_id = str(canal_id)
        if str_id not in self.historicos_locais:
            self.historicos_locais[str_id] = []
        
        self.historicos_locais[str_id].append({"role": papel, "text": texto})
        
        # Janela deslizante: Mantém apenas as últimas 20 mensagens no histórico
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

    # --- PROCESSAMENTO SEGURO DA FILA ---
    async def processador_da_fila(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            ctx, pergunta, dados_imagem = await self.fila_requisicoes.get()
            try:
                await self.executar_processamento_ia(ctx, pergunta, dados_imagem)
            except Exception as e:
                logger.error(f"❌ Erro crítico no worker da fila de IA: {e}")
            finally:
                self.fila_requisicoes.task_done()

    async def executar_processamento_ia(self, ctx, pergunta: str, dados_imagem):
        async with ctx.typing():
            try:
                historico_api = self.compilar_conteudo_historico(ctx.channel.id)
                
                conteudo_atual = []
                if pergunta:
                    conteudo_atual.append(types.Part.from_text(text=pergunta))
                if dados_imagem:
                    conteudo_atual.append(dados_imagem)
                
                historico_api.append(types.Content(role="user", parts=conteudo_atual))
                logger.info(f"⚡ Solicitando Gemini para Canal [{ctx.channel.id}]...")
                
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=historico_api,
                    config=self.config
                )
                
                texto_resposta = response.text if response.text else "🙄 ... (Cristiane ficou sem palavras)"

                # Salva a conversa no banco JSON
                if pergunta:
                    self.atualizar_contexto_canal(ctx.channel.id, "user", pergunta)
                else:
                    self.atualizar_contexto_canal(ctx.channel.id, "user", "[Enviou uma Imagem]")
                    
                self.atualizar_contexto_canal(ctx.channel.id, "model", texto_resposta)

                # Divide textos gigantes para evitar limitação de 2000 caracteres do Discord
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
                    title="💥 Erro de Processamento",
                    description=f"```py\n{e}\n```\nSe o erro persistir, limpe a memória do canal.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed_erro)

    def dividir_texto_inteligente(self, texto: str, limite: int = 1900):
        if len(texto) <= limite:
            return [texto]
        partes = []
        linhas = texto.split('\n')
        bloco_atual = ""
        em_bloco_codigo = False

        for linha in linhas:
            if linha.strip().startswith("```"):
                em_bloco_codigo = not em_bloco_codigo
            if len(bloco_atual) + len(linha) + 1 > limite:
                if em_bloco_codigo:
                    bloco_atual += "\n```"
                    partes.append(bloco_atual)
                    bloco_atual = "```\n" + linha
                else:
                    partes.append(bloco_atual)
                    bloco_atual = linha
            else:
                if bloco_atual:
                    bloco_atual += "\n" + linha
                else:
                    bloco_atual = linha
        if bloco_atual:
            partes.append(bloco_atual)
        return partes

    async def pre_processar_e_enfileirar(self, ctx, pergunta: str):
        canal_permitido_id = os.environ.get("AI_CHANNEL_ID")
        if canal_permitido_id and ctx.channel.id != int(canal_permitido_id):
            return

        if not pergunta and not ctx.message.attachments:
            await ctx.send("🤖 Campeão, você precisa digitar uma pergunta ou mandar uma imagem junto!")
            return

        dados_imagem = None
        if ctx.message.attachments:
            anexo = ctx.message.attachments[0]
            extensao = anexo.filename.lower()
            mime_type = None
            if extensao.endswith('.png'): mime_type = 'image/png'
            elif extensao.endswith(('.jpg', '.jpeg')): mime_type = 'image/jpeg'
            elif extensao.endswith('.webp'): mime_type = 'image/webp'

            if mime_type:
                logger.info(f"📸 Baixando imagem vinda de {ctx.author}")
                bytes_imagem = await anexo.read()
                dados_imagem = types.Part.from_bytes(data=bytes_imagem, mime_type=mime_type)

        await self.fila_requisicoes.put((ctx, pergunta, dados_imagem))
        logger.info(f"📥 Requisição de {ctx.author} enfileirada com sucesso.")

    # --- GATILHOS (COMANDO & MENÇÃO) ---
    @commands.command(name="cris")
    @commands.guild_only()
    async def perguntar(self, ctx, *, pergunta: str = None):
        """Comando da Cristiane: aceita texto, imagens ou os dois juntos"""
        await self.pre_processar_e_enfileirar(ctx, pergunta)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:
            return

        # Reconhecimento dinâmico de menção crua ou formatada
        id_bot_marcao = f"<@{self.bot.user.id}>"
        id_bot_marcao_alt = f"<@!{self.bot.user.id}>"
        
        if id_bot_marcao in message.content or id_bot_marcao_alt in message.content or self.bot.user.mentioned_in(message):
            # Se for uma chamada do comando por prefixo, ignora o listener para não responder duas vezes
            if message.content.startswith(f"{self.bot.command_prefix}cris"):
                return

            texto_limpo = message.content.replace(id_bot_marcao, '').replace(id_bot_marcao_alt, '').strip()
            ctx = await self.bot.get_context(message)
            await self.pre_processar_e_enfileirar(ctx, texto_limpo)

async def setup(bot):
    await bot.add_cog(IA(bot))
