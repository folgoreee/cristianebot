import discord
from discord.ext import commands
from google import genai
from google.genai import types
import os
import asyncio
import logging

logger = logging.getLogger('CristianeBot.IA')

class IA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    @commands.command(name="cris")
    @commands.guild_only() 
    async def perguntar(self, ctx, *, pergunta: str = None):
        """Comando da Cristiane: !cris <pergunta>"""

        # === DEBUG: Log para saber se o comando chegou ===
        logger.info(f"Comando !cris recebido de {ctx.author.name} no canal {ctx.channel.id}")

        # === TRAVA DE CANAL ===
        canal_permitido_id = os.environ.get("ID_CANAL_IA")

        if canal_permitido_id and ctx.channel.id != int(canal_permitido_id):
            logger.warning(f"Comando ignorado: Usuário tentou usar fora do canal permitido ({canal_permitido_id})")
            return

        # Se o usuário não enviou texto nem imagem
        if not pergunta and not ctx.message.attachments:
            await ctx.send("🤖 Rapaz, você precisa mandar a pergunta ou uma imagem junto com o `!cris`!")
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
                        bytes_imagem = await anexo.read()
                        dados_imagem = types.Part.from_bytes(
                            data=bytes_imagem,
                            mime_type=mime_type,
                        )
                        conteudo_para_enviar.append(dados_imagem)

            try:
                personalidade = (
                    "Você é a Cristiane, uma mentora de programação e entusiasta de Linux. "
                    "Regras estritas:\n"
                    "1. INÍCIO OBRIGATÓRIO: Comece com 'Rapaz...', 'Campeão...' ou 'Meu Amigo...' sempre.\n"
                    "2. LINGUAGEM: Use PT-BR informal, direto e sarcástico. Seja ríspida e prática.\n"
                    "3. BRONCA: Se a pergunta for básica, dê a bronca de veterana.\n"
                    "4. LINUX: No final de TODA resposta, adicione uma curiosidade rápida sobre Linux.\n"
                    "5. TAMANHO: Máximo 3 parágrafos curtos."
                )

                config = types.GenerateContentConfig(system_instruction=personalidade)
                max_tentativas = 3
                response = None
                
                for tentativa in range(max_tentativas):
                    try:
                        response = await self.client.aio.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=conteudo_para_enviar,
                            config=config
                        )
                        break 
                    
                    except Exception as e:
                        if "503" in str(e) and tentativa < max_tentativas - 1:
                            await asyncio.sleep(4) 
                            continue 
                        else:
                            raise e 

                texto_resposta = response.text if response and response.text else "🙄 ... (Cristiane te ignorou completamente)"

                if len(texto_resposta) > 2000:
                    corte_seguro = texto_resposta[:1950]
                    ultimo_ponto = corte_seguro.rfind('.')
                    await ctx.send(corte_seguro[:ultimo_ponto + 1] + " 💢 (Cansei de falar...)")
                else:
                    await ctx.send(texto_resposta)

            except Exception as e:
                logger.error(f"Erro ao gerar resposta: {e}")
                await ctx.send(f"❌ Ocorreu um erro ao processar seu pedido: {e}")

async def setup(bot):
    await bot.add_cog(IA(bot))
