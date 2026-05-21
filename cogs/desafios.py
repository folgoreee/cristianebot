import os
import json
import logging
import asyncio
import discord
from pathlib import Path
from discord.ext import commands
from discord import app_commands  # Importação necessária para Slash Commands
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

logger = logging.getLogger('CristianeBot.Desafios')
LEADERBOARD_FILE = Path("leaderboard.json")

# ===================================================================
# MODELO DE VALIDAÇÃO PARA O GEMINI (Structured Outputs)
# ===================================================================
class QuizSchema(BaseModel):
    pergunta: str = Field(description="A descrição clara do problem técnico ou código com erro.")
    A: str = Field(description="Texto da Opção A.")
    B: str = Field(description="Texto da Opção B.")
    C: str = Field(description="Texto da Opção C.")
    D: str = Field(description="Texto da Opção D.")
    correta: str = Field(description="A letra da opção correta (A, B, C ou D).")
    pontos: int = Field(description="Um número inteiro de 10 a 50 com base na dificuldade do problema.")

# ===================================================================
# INTERFACE DOS BOTÕES DO QUIZ (discord.ui.View)
# ===================================================================
class QuizView(discord.ui.View):
    def __init__(self, cog_desafios, autor_id: int, resposta_correta: str, pontos: int):
        super().__init__(timeout=60.0)
        self.cog_desafios = cog_desafios
        self.autor_id = autor_id
        self.resposta_correta = resposta_correta.strip().upper()
        self.pontos = pontos
        self.respondido = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("❌ Campeão, este desafio não é teu! Usa `/desafio` para criares o teu próprio.", ephemeral=True)
            return False
        return True

    async def processar_resposta(self, interaction: discord.Interaction, escolha: str):
        if self.respondido:
            return
        self.respondido = True
        self.stop()

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        if escolha == self.resposta_correta:
            novo_total = self.cog_desafios.adicionar_pontos(interaction.user.id, self.pontos)
            embed_sucesso = discord.Embed(
                title="✅ RESPOSTA CORRETA!",
                description=f"Rapaz, sabias mesmo esta! Ganhaste **{self.pontos} pontos**.\n🏆 Total acumulado: **{novo_total} pontos**.",
                color=discord.Color.green()
            )
            embed_sucesso.set_footer(text="Cristiane orgulha-se de ti... por agora.")
            await interaction.response.edit_message(embed=embed_sucesso, view=self)
        else:
            embed_erro = discord.Embed(
                title="❌ ERROU, CAMPEÃO!",
                description=f"Cara, tu já devias saber isto! A resposta correta era a **{self.resposta_correta}**.\nEstuda mais um bocado e tenta novamente!",
                color=discord.Color.red()
            )
            embed_erro.set_footer(text="Mais uma falha para o registo.")
            await interaction.response.edit_message(embed=embed_erro, view=self)

    @discord.ui.button(label="Opção A", style=discord.ButtonStyle.primary, custom_id="button_a")
    async def opcao_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_resposta(interaction, "A")

    @discord.ui.button(label="Opção B", style=discord.ButtonStyle.primary, custom_id="button_b")
    async def opcao_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_resposta(interaction, "B")

    @discord.ui.button(label="Opção C", style=discord.ButtonStyle.primary, custom_id="button_c")
    async def opcao_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_resposta(interaction, "C")

    @discord.ui.button(label="Opção D", style=discord.ButtonStyle.primary, custom_id="button_d")
    async def opcao_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_resposta(interaction, "D")

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

# ===================================================================
# COG DE DESAFIOS E RANKING (COM SLASH COMMANDS)
# ===================================================================
class Desafios(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.leaderboard = self.carregar_leaderboard()

    def carregar_leaderboard(self):
        if LEADERBOARD_FILE.exists():
            try:
                with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
                    logger.info("💾 Leaderboard carregada do disco!")
                    return json.load(f)
            except Exception as e:
                logger.error(f"❌ Erro ao ler leaderboard.json: {e}")
        return {}

    def guardar_leaderboard(self):
        try:
            with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
                json.dump(self.leaderboard, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"❌ Erro ao guardar leaderboard.json: {e}")

    def adicionar_pontos(self, user_id: int, pontos: int) -> int:
        str_id = str(user_id)
        if str_id not in self.leaderboard:
            self.leaderboard[str_id] = 0
        self.leaderboard[str_id] += pontos
        self.guardar_leaderboard()
        return self.leaderboard[str_id]

    # Transformado em Slash Command híbrido (funciona com !desafio e com /desafio)
    @commands.hybrid_command(name="desafio", description="Gera um desafio de escolha múltipla sobre a tecnologia selecionada")
    @app_commands.describe(tecnologia="A linguagem ou tecnologia do desafio (Ex: Python, JavaScript, Linux)")
    @commands.guild_only()
    async def gerar_desafio(self, ctx: commands.Context, tecnologia: str = "Python"):
        logger.info(f"🎲 Gerando desafio de {tecnologia} solicitado por {ctx.author}")
        
        # Nos comandos híbridos/slash, usamos ctx.defer() para avisar o Discord que a resposta vai demorar (IA pensando)
        await ctx.defer()

        prompt_quiz = f"Gere um desafio técnico de escolha múltipla sobre {tecnologia} para programadores."

        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt_quiz,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=QuizSchema,
                    temperature=0.8
                )
            )

            dados_quiz = QuizSchema.model_validate_json(response.text)

            embed_desafio = discord.Embed(
                title=f"💻 DESAFIO TÉCNICO: {tecnologia.upper()}",
                description=f"**Pergunta:**\n{dados_quiz.pergunta}\n\n"
                            f"**A)** {dados_quiz.A}\n"
                            f"**B)** {dados_quiz.B}\n"
                            f"**C)** {dados_quiz.C}\n"
                            f"**D)** {dados_quiz.D}",
                color=discord.Color.blue()
            )
            embed_desafio.add_field(name="💰 Recompensa", value=f"`{dados_quiz.pontos} pontos`", inline=True)
            embed_desafio.set_footer(text=f"Desafio gerado para {ctx.author.name}. Tens 60 segundos!")

            view_botoes = QuizView(self, ctx.author.id, dados_quiz.correta, dados_quiz.pontos)
            
            # ctx.send funciona tanto para chat normal quanto para responder ao Slash Command diferido
            await ctx.send(embed=embed_desafio, view=view_botoes)

        except Exception as e:
            logger.error(f"❌ Erro ao gerar/analisar o desafio: {e}", exc_info=True)
            await ctx.send("❌ Rapaz, deu erro ao gerar o desafio com a IA. Tente rodar o comando novamente!")

    # Transformado em Slash Command híbrido
    @commands.hybrid_command(name="ranking", description="Exibe o top 10 utilizadores com maior pontuação no servidor")
    @commands.guild_only()
    async def mostrar_ranking(self, ctx: commands.Context):
        if not self.leaderboard:
            await ctx.send("📉 Campeão, ainda ninguém pontuou neste servidor! Usa `/desafio` para começares.")
            return

        ranking_ordenado = sorted(self.leaderboard.items(), key=lambda item: item[1], reverse=True)[:10]

        embed_ranking = discord.Embed(
            title="🏆 RANKING DE PROGRAMADORES",
            description="Estes são os campeões que mais estudam e acertam desafios técnicos!",
            color=discord.Color.gold()
        )

        lista_membros = ""
        for index, (user_id, pontos) in enumerate(ranking_ordenado, start=1):
            membro = ctx.guild.get_member(int(user_id))
            nome_membro = membro.name if membro else f"Utilizador ({user_id})"
            
            medalha = "👑" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"`#{index}`"
            lista_membros += f"{medalha} **{nome_membro}** — `{pontos} pontos`\n"

        embed_ranking.add_field(name="Classificação", value=lista_membros, inline=False)
        await ctx.send(embed=embed_ranking)

async def setup(bot):
    await bot.add_cog(Desafios(bot))
