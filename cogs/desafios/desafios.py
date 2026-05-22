import os
import json
import logging
import asyncio
import discord
from pathlib import Path
from discord.ext import commands
from discord import app_commands
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

logger = logging.getLogger('CristianeBot.Desafios')
LEADERBOARD_FILE = Path("leaderboard.json")

# Schema de validação do Pydantic
class QuizSchema(BaseModel):
    pergunta: str = Field(description="A descrição clara do problema técnico ou código com erro.")
    A: str = Field(description="Texto da Opção A.")
    B: str = Field(description="Texto da Opção B.")
    C: str = Field(description="Texto da Opção C.")
    D: str = Field(description="Texto da Opção D.")
    correta: str = Field(description="A letra da opção correta (A, B, C ou D).")
    pontos: int = Field(description="Um número inteiro de 10 a 50 com base na dificuldade do problema.")

# ===================================================================
# INTERFACE DOS BOTÕES DO QUIZ
# ===================================================================
class QuizView(discord.ui.View):
    def __init__(self, cog_desafios, autor_id: int, resposta_correta: str, pontos: int):
        super().__init__(timeout=60.0)
        self.cog_desafios = cog_desafios
        self.autor_id = autor_id
        self.resposta_correta = resposta_correta.strip().upper()
        self.pontos = pontos
        self.respondido = False
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "❌ Campeão, este desafio não é teu! Usa `/desafio` para criares o teu próprio.", 
                ephemeral=True
            )
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
            await interaction.response.edit_message(embed=embed_sucesso, view=self)
        else:
            embed_erro = discord.Embed(
                title="❌ ERROU, CAMPEÃO!",
                description=f"Cara, tu já devias saber isto! A resposta correta era a **{self.resposta_correta}**.\nEstuda mais um bocado e tenta novamente!",
                color=discord.Color.red()
            )
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
        if self.respondido:
            return
        self.respondido = True
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                logger.warning(f"Falha ao atualizar timeout: {e}")

# ===================================================================
# COG PRINCIPAL DE DESAFIOS
# ===================================================================
class Desafios(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Padronizado para GEMINI_API_KEY
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.leaderboard = self.carregar_leaderboard()

    def carregar_leaderboard(self):
        if LEADERBOARD_FILE.exists():
            try:
                with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"❌ Erro ao ler leaderboard: {e}")
        return {}

    def guardar_leaderboard(self):
        try:
            with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
                json.dump(self.leaderboard, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"❌ Erro ao guardar leaderboard: {e}")

    def adicionar_pontos(self, user_id: int, pontos: int) -> int:
        str_id = str(user_id)
        if str_id not in self.leaderboard:
            self.leaderboard[str_id] = 0
        self.leaderboard[str_id] += pontos
        self.guardar_leaderboard()
        return self.leaderboard[str_id]

    @commands.hybrid_command(name="desafio", description="Gera um desafio técnico")
    @app_commands.describe(tecnologia="A linguagem ou tecnologia do desafio")
    @commands.guild_only()
    async def gerar_desafio(self, ctx: commands.Context, tecnologia: str = "Python"):
        await ctx.defer()
        prompt_quiz = f"Gere um desafio técnico avançado de múltipla escolha sobre {tecnologia}."

        max_tentativas = 3
        dados_quiz = None

        # Loop de Retry para lidar com erros 503 da API
        for tentativa in range(max_tentativas):
            try:
                # CHAMADA ASSÍNCRONA (AIO)
                response = await self.client.aio.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt_quiz,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=QuizSchema,
                        temperature=0.85
                    )
                )
                dados_quiz = QuizSchema.model_validate_json(response.text)
                break # Sai do loop se der certo
            except Exception as e:
                if "503" in str(e) and tentativa < max_tentativas - 1:
                    logger.warning(f"Tentativa {tentativa+1} falhou (503). Retentando...")
                    await asyncio.sleep(2)
                    continue
                else:
                    logger.error(f"Erro ao gerar desafio após {tentativa+1} tentativas: {e}")
                    await ctx.send("❌ A Cristiane está ocupada demais agora. Tenta de novo daqui a pouco!")
                    return

        embed_desafio = discord.Embed(
            title=f"💻 DESAFIO TÉCNICO: {tecnologia.upper()}",
            description=f"**Pergunta:**\n{dados_quiz.pergunta}\n\n**A)** {dados_quiz.A}\n**B)** {dados_quiz.B}\n**C)** {dados_quiz.C}\n**D)** {dados_quiz.D}",
            color=discord.Color.blue()
        )
        embed_desafio.add_field(name="💰 Recompensa", value=f"`{dados_quiz.pontos} pontos`")
        
        view_botoes = QuizView(self, ctx.author.id, dados_quiz.correta, dados_quiz.pontos)
        view_botoes.message = await ctx.send(embed=embed_desafio, view=view_botoes)

    @commands.hybrid_command(name="ranking", description="Exibe o top 10")
    @commands.guild_only()
    async def mostrar_ranking(self, ctx: commands.Context):
        if not self.leaderboard:
            await ctx.send("📉 Ainda ninguém pontuou!")
            return

        ranking_ordenado = sorted(self.leaderboard.items(), key=lambda item: item[1], reverse=True)[:10]
        embed_ranking = discord.Embed(title="🏆 RANKING", color=discord.Color.gold())
        
        texto = ""
        for index, (uid, pts) in enumerate(ranking_ordenado, start=1):
            texto += f"{index}º - {pts} pts\n"
        
        embed_ranking.description = texto
        await ctx.send(embed=embed_ranking)

async def setup(bot):
    await bot.add_cog(Desafios(bot))
