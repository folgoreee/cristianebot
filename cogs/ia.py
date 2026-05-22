import discord
from discord.ext import commands
from google import genai
from google.genai import types
import os
import asyncio

class IA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 1. VARIÁVEL UNIVERSAL PARA A API DA IA
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    @commands.command(name="ia")
    @commands.guild_only() # Proteção contra o uso no privado (DM) do bot
    async def perguntar(self, ctx, *, pergunta: str = None):
        """Comando universal, ultra otimizado e leve para enviar texto e/ou imagens à Cristiane"""

        # === TRAVA DE CANAL ===
        canal_permitido_id = os.environ.get("ID_CANAL_IA")

        # Se a variável existir e o canal atual não for o correto, ignora completamente
        if canal_permitido_id and ctx.channel.id != int(canal_permitido_id):
            return

        # Se o usuário não enviou texto nem imagem
        if not pergunta and not ctx.message.attachments:
            await ctx.send("🤖 Você precisa mandar alguma pergunta ou enviar uma imagem com o comando!")
            return

        # Mostra que o bot está "digitando" enquanto a IA pensa (evita erro de timeout)
        async with ctx.typing():
            conteudo_para_enviar = []

            # 1. Se o usuário digitou algum texto, adiciona na lista
            if pergunta:
                conteudo_para_enviar.append(pergunta)

            # 2. SISTEMA ULTRA LEVE DE IMAGENS:
            if ctx.message.attachments:
                for anexo in ctx.message.attachments:
                    extensao = anexo.filename.lower()

                    # Mapeia a extensão direto para o MIME Type que o Gemini precisa
                    mime_type = None
                    if extensao.endswith('.png'): mime_type = 'image/png'
                    elif extensao.endswith(('.jpg', '.jpeg')): mime_type = 'image/jpeg'
                    elif extensao.endswith('.webp'): mime_type = 'image/webp'

                    if mime_type:
                        # Baixa apenas o binário bruto compactado do Discord
                        bytes_imagem = await anexo.read()

                        # Passa os bytes brutos com a etiqueta do formato direto para a API
                        dados_imagem = types.Part.from_bytes(
                            data=bytes_imagem,
                            mime_type=mime_type,
                        )
                        conteudo_para_enviar.append(dados_imagem)

           try:
                # === PERSONALIDADE DA IA ===
                personalidade = (
                    "Você é a Cristiane, uma mentora de programação e entusiasta de Linux. "
                    "Regras estritas:\n"
                    "1. INÍCIO OBRIGATÓRIO: Comece com 'Rapaz...', 'Campeão...' ou 'Meu Amigo...' sempre."
                    "2. LINGUAGEM: Use PT-BR informal, direto e sarcástico. Nunca use termos corporativos ou educados demais. Seja ríspida e prática."
                    "3. BRONCA: Se a pergunta for básica, dê a bronca de veterana antes de explicar.\n"
                    "4. LINUX: No final de TODA resposta, adicione uma curiosidade rápida sobre Linux. Reforce a babação em cima do Linux, independente do conteúdo da mensagem."
                    "5. TAMANHO: Máximo 3 parágrafos curtos. Não enrole."
                    "6. CONSELHO: Se alguém lhe pedir um conselho, seja como um 'pai', mas também não se esqueça do Linux no final do conselho."
                )

                config = types.GenerateContentConfig(system_instruction=personalidade)

                # === SISTEMA DE TENTATIVAS (RETRY PARA ERRO 503) ===
                max_tentativas = 3
                response = None
                
                for tentativa in range(max_tentativas):
                    try:
                        # CORREÇÃO REAL: Usando 'aio' para o bot não congelar
                        response = await self.client.aio.models.generate_content(
                            model='gemini-2.5-flash', # Você estava certíssimo aqui!
                            contents=conteudo_para_enviar,
                            config=config
                        )
                        break # Se deu certo, quebra o loop e segue o jogo
                    
                    except Exception as e:
                        # Se for erro 503 de servidor lotado, ele tenta de novo
                        if "503" in str(e) and tentativa < max_tentativas - 1:
                            aviso = await ctx.send(f"⚠️ A Cristiane esbarrou num servidor lotado. Tentando de novo ({tentativa+1}/{max_tentativas})...")
                            await asyncio.sleep(4) # Espera 4 segundinhos pra API respirar
                            await aviso.delete()   
                            continue 
                        else:
                            raise e # Se for outro erro (ou esgotar tentativas), aciona o except lá de baixo

                # Proteção de segurança
                texto_resposta = response.text if response and response.text else "🙄 ... (Cristiane te ignorou completamente)"

                # === CORTE INTELIGENTE DE TEXTO ===
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
                msg_erro = await ctx.send(f"❌ Ocorreu um erro ao processar seu pedido: {e}")
                await asyncio.sleep(5)

