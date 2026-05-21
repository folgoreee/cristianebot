import os
import asyncio
import logging
import time
import discord
from pathlib import Path
from discord.ext import commands
from google import genai
from google.genai import types

logger = logging.getLogger('CristianeBot.IA')

# ===================================================================
# INTERFACE DO BOTÃO DE LIMPEZA (discord.ui.View)
# ===================================================================
class MenuIA(discord.ui.View):
    def __init__(self, cog_ia, canal_id: int):
        super().__init__(timeout=180)  # O botão fica ativo por 3 minutos
        self.cog_ia = cog_ia
        self.canal_id = canal_id

    @discord.ui.button(label="Limpar Memória", style=discord.ButtonStyle.danger, emoji="🧹")
    async def limpar_memoria_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verifica se quem clicou tem permissão de gerenciar mensagens ou é o dono
        if not interaction.user.guild_permissions.manage_messages and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Rapaz, tu não tem permissão de moderador para limpar essa memória não!", ephemeral=True)
            return

        # Executa a limpeza
        self.cog_ia.limpar_historico_canal(self.canal_id)
        
        # Desabilita o botão após o clique para ficar elegante
        button.disabled = True
        button.label = "Memória Limpa!"
        button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        
        msg_aviso = await interaction.channel.send("🧹 **Memória resetada!** Começando um novo contexto do zero, campeão.")
        await asyncio.sleep(4)
        try: await msg_aviso.delete()
        except: pass

    async def on_timeout(self):
        """Remove os botões da mensagem quando o tempo expira para não poluir o chat"""
        try:
            # Desabilita a view inteira após o timeout de 3 minutos
            self.clear_items()
            # Nota: para atualizar a mensagem original no timeout precisaríamos da msg de referência,
            # mas deixar em branco impede cliques em botões fantasmas antigos.
        except:
            pass


# ===================================================================
# COG PRINCIPAL DA INTELIGÊNCIA ARTIFICIAL
# ===================================================================
class IA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        
        # Dicionários de controle: históricos e timestamps de última atividade
        self.historicos = {}
        self.ultimas_atividades = {}
        
        # Tempo limite de inatividade (15 minutos em segundos)
        self.ttl_segundos = 15 * 60

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

        # Inicia a tarefa de segundo plano que limpa a memória por inatividade
        self.bot.loop.create_task(self.verificador_limpeza_ram())

    def limpar_historico_canal(self, canal_id: int):
        """Remove a sessão do dicionário para liberar espaço na RAM"""
        if canal_id in self.historicos:
            del self.historicos[canal_id]
        if canal_id in self.ultimas_atividades:
            del self.ultimas_atividades[canal_id]
        logger.info(f"♻️ Memória RAM liberada: Histórico do canal [{canal_id}] deletado.")

    async def verificador_limpeza_ram(self):
        """Loop de segundo plano (Background Task) que limpa canais inativos a cada 1 minuto"""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            agora = time.time()
            canais_para_limpar = []
            
            for canal_id, ultimo_acesso in list(self.ultimas_atividades.items()):
                if agora - ultimo_acesso > self.ttl_segundos:
                    canais_para_limpar.append(canal_id)
            
            for canal_id in canais_para_limpar:
                logger.info(f"⏳ Canal [{canal_id}] inativo por mais de 15 minutos.")
                self.limpar_historico_canal(canal_id)
                
            await asyncio.sleep(60) # Roda a checagem a cada 1 minuto

    def obter_ou_criar_chat(self, canal_id: int):
        """Gerencia e cria a sessão de chat mantendo os timestamps atualizados"""
        self.ultimas_atividades[canal_id] = time.time() # Atualiza o relógio de atividade
        
        if canal_id not in self.historicos:
            logger.info(f"🧠 Nova sessão de histórico criada para o canal [{canal_id}]")
            self.historicos[canal_id] = self.client.chats.create(
                model='gemini-2.5-flash',
                config=self.config
            )
        return self.historicos[canal_id]

    def dividir_texto_inteligente(self, texto: str, limite: int = 1900):
        """Quebra textos gigantes respeitando blocos de código e quebras de linha do Discord"""
        if len(texto) <= limite:
            return [texto]

        partes = []
        linhas = texto.split('\n')
        bloco_atual = ""
        em_bloco_codigo = False

        for linha in linhas:
            if linha.strip().startswith("```"):
                em_bloco_codigo = not em_bloco_codigo

            # Se adicionar a linha estourar o limite, fecha o bloco atual
            if len(bloco_atual) + len(linha) + 1 > limite:
                if em_bloco_codigo:
                    bloco_atual += "\n```" # Fecha o bloco para não quebrar a formatação
                    partes.append(bloco_atual)
                    bloco_atual = "```\n" + linha # Reabre o bloco na próxima mensagem
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

    async def processar_ia(self, ctx, pergunta: str):
        """Motor principal que lida com o envio de mensagens, imagens e respostas"""
        canal_permitido_id = os.environ.get("AI_CHANNEL_ID")
        if canal_permitido_id and ctx.channel.id != int(canal_permitido_id):
            return

        if not pergunta and not ctx.message.attachments:
            await ctx.send("🤖 Campeão, você precisa digitar uma pergunta ou mandar uma imagem junto!")
            return

        async with ctx.typing():
            conteudo_para_enviar = []

            if pergunta:
                conteudo_para_enviar.append(pergunta)

            if ctx.message.attachments:
                for anexo in ctx.message.attachments:
                    extensao = anexo.filename.lower()
                    mime_type = None
                    if extensao.endswith('.png'): mime_type = 'image/png'
                    elif extensao.endswith(('.jpg', '.jpeg')): mime_type = 'image/jpeg'
                    elif extensao.endswith('.webp'): mime_type = 'image/webp'

                    if mime_type:
                        logger.info(f"📸 Processando imagem enviada por {ctx.author}")
                        bytes_imagem = await anexo.read()
                        dados_imagem = types.Part.from_bytes(
                            data=bytes_imagem,
                            mime_type=mime_type,
                        )
                        conteudo_para_enviar.append(dados_imagem)

            try:
                # Busca ou cria a sessão com controle de tempo ativo
                chat_ativo = self.obter_ou_criar_chat(ctx.channel.id)
                
                logger.info(f"💬 Enviando prompt para a Cristiane no canal [{ctx.channel.id}]")
                response = chat_ativo.send_message(conteudo_para_enviar)
                texto_resposta = response.text if response.text else "🙄 ... (Cristiane ficou sem palavras)"

                # Executa o divisor inteligente de texto para evitar erros de tamanho
                blocos_de_texto = self.dividir_texto_inteligente(texto_resposta)
                
                # Instancia o botão dinâmico de limpar memória
                visao_botoes = MenuIA(self, ctx.channel.id)

                # Envia cada bloco sequencialmente
                for i, bloco in enumerate(blocos_de_texto):
                    # Só anexa o botão na ÚLTIMA parte da resposta
                    if i == len(blocos_de_texto) - 1:
                        await ctx.send(bloco, view=visao_botoes)
                    else:
                        await ctx.send(bloco)

            except Exception as e:
                logger.error(f"❌ Erro na API do Gemini ou Discord: {e}")
                # Rich Embed elegante para exibir o erro sem avacalhar o design do chat
                embed_erro = discord.Embed(
                    title="💥 Ih campeão, deu algum ruim interno!",
                    description=f"```py\n{e}\n```\nSe o erro persistir, peça para limparem a memória do canal no botão.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed_erro)

    # 1. Comando clássico por prefixo (!cris)
    @commands.command(name="cris")
    @commands.guild_only()
    async def perguntar_comando(self, ctx, *, pergunta: str = None):
        await self.processar_ia(ctx, pergunta)

    # 2. Ouvinte de menções (@Cristiane)
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:
            return

        id_bot_marcao = f"<@{self.bot.user.id}>"
        id_bot_marcao_alt = f"<@!{self.bot.user.id}>"
        
        if id_bot_marcao in message.content or id_bot_marcao_alt in message.content or self.bot.user.mentioned_in(message):
            if message.content.startswith(f"{self.bot.command_prefix}cris"):
                return

            texto_limpo = message.content.replace(id_bot_marcao, '').replace(id_bot_marcao_alt, '').strip()
            ctx = await self.bot.get_context(message)
            await self.processar_ia(ctx, texto_limpo)

async def setup(bot):
    await bot.add_cog(IA(bot))
