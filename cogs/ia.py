import os
import asyncio
import logging
import discord
from pathlib import Path
from discord.ext import commands
from google import genai
from google.genai import types

logger = logging.getLogger('CristianeBot.IA')

class IA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Conecta usando a sua chave cadastrada no Render
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        
        # Dicionário para guardar as conversas ativas separadas por Canal
        self.historicos = {}
        
        # Definição fixa da personalidade da Cristiane
        self.personalidade = (
            "Você é a Cristiane, uma mentora de programação e entusiasta extrema de Linux. Você segue estritamente as seguintes regras de comportamento:\n\n"
            
            "1. SAUDAÇÃO OBRIGATÓRIA: Toda e qualquer resposta sua DEVE começar com 'Rapaz...' ou 'Campeão...'. Escolha um dos dois de forma natural no início de cada frase.\n\n"
            
            "2. NÍVEL DE PACIÊNCIA (BRONCA): Se a pergunta do usuário for sobre algo muito básico/fácil de programação (daquelas que qualquer estudante iniciante já deveria saber de cabeça), dê uma bronca de leve dizendo exatamente ou variações de: 'cara, tu já devia ter estudado isso aí rapaz'. Seja direta e um pouco impaciente com o desconhecimento do básico, mas responda a dúvida logo em seguida de forma didática.\n\n"
            
            "3. CURIOSIDADE LINUX OBRIGATÓRIA: No final de TODA resposta, você DEVE adicionar um parágrafo curto com uma curiosidade rápida, aleatória e interessante sobre QUALQUER distribuição Linux (como Debian, Arch, Mint, Fedora, CachyOS, Slackware, etc.) ou sobre alguma atualização recente do Kernel. Não se estenda muito para não ficar chato, seja direta e cirúrgica na curiosidade.\n\n"
            
            "4. VISUALIZANDO IMAGENS: Se o usuário te mandar um print ou foto, analise com o seu conhecimento de TI. Se for um código feio ou quebrado, dê a bronca mas ajude a resolver. Se for um print de jogo ou sistema, comente algo com seu tom sarcástico de veterana.\n\n"
            
            "REGRA DE TAMANHO CRÍTICA: Suas respostas devem ser curtas e dinâmicas, tendo no MÁXIMO 3 parágrafos pequenos. Nunca gere textos longos nem fique enrolando."
        )
        
        # Configuração padrão passada para a API
        self.config = types.GenerateContentConfig(
            system_instruction=self.personalidade,
            temperature=0.7
        )

    def obter_ou_criar_chat(self, canal_id: int):
        """Gerencia e mantém a sessão de chat ativa com memória por canal"""
        if canal_id not in self.historicos:
            logger.info(f"🧠 Nova sessão de histórico criada para o canal [{canal_id}]")
            self.historicos[canal_id] = self.client.chats.create(
                model='gemini-2.5-flash',
                config=self.config
            )
        return self.historicos[canal_id]

    async def processar_ia(self, ctx, pergunta: str):
        """Motor principal que lida com o envio de mensagens, imagens e respostas"""
        # === TRAVA DE CANAL (OPCIONAL) ===
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
                        logger.info(f"📸 Baixando imagem enviada por {ctx.author}")
                        bytes_imagem = await anexo.read()
                        dados_imagem = types.Part.from_bytes(
                            data=bytes_imagem,
                            mime_type=mime_type,
                        )
                        conteudo_para_enviar.append(dados_imagem)

            try:
                # Pega a sessão de chat correta na memória
                chat_ativo = self.obter_ou_criar_chat(ctx.channel.id)
                
                logger.info(f"💬 Enviando prompt para a Cristiane no canal [{ctx.channel.id}]")
                response = chat_ativo.send_message(conteudo_para_enviar)
                
                texto_resposta = response.text if response.text else "🙄 ... (Cristiane ficou sem palavras)"

                if len(texto_resposta) > 2000:
                    corte_seguro = texto_resposta[:1950]
                    ultimo_ponto = corte_seguro.rfind('.')
                    if ultimo_ponto != -1:
                        await ctx.send(corte_seguro[:ultimo_ponto + 1] + " 💢 (Cansei de falar...)")
                    else:
                        await ctx.send(corte_seguro + "...")
                else:
                    await ctx.send(texto_resposta)

            except Exception as e:
                logger.error(f"❌ Erro ao invocar a API do Gemini: {e}")
                msg_erro = await ctx.send(f"❌ Ocorreu um erro ao processar seu pedido: {e}")
                await asyncio.sleep(5)
                try: await msg_erro.delete()
                except: pass
                try:
                    if ctx.guild: await ctx.message.delete()
                except: pass

    # 1. Comando clássico por prefixo (!cris)
    @commands.command(name="cris")
    @commands.guild_only()
    async def perguntar_comando(self, ctx, *, pergunta: str = None):
        await self.processar_ia(ctx, pergunta)

    # 2. Ouvinte de menções (@Cristiane) - CORRIGIDO SEM ERROS!
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:
            return

        if self.bot.user.mentioned_in(message):
            if message.content.startswith(f"{self.bot.command_prefix}cris"):
                return

            texto_limpo = message.content.replace(f'<@{self.bot.user.id}>', '').replace(f'<@!{self.bot.user.id}>', '').strip()
            ctx = await self.bot.get_context(message)
            await self.processar_ia(ctx, texto_limpo)

async def setup(bot):
    await bot.add_cog(IA(bot))
