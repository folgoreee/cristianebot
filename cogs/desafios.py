import os
import json
import random
import asyncio
import logging
import discord
from pathlib import Path
from discord.ext import commands
from google import genai
from google.genai import types

# Configuração de logs em Português de Portugal
logger = logging.getLogger('CristianeBot.Desafios')
LEADERBOARD_FILE = Path("leaderboard.json")

# ===================================================================
# INTERFACE DOS BOTÕES DO DESAFIO (discord.ui.View)
# ===================================================================
class QuizView(discord.ui.View):
    def __init__(self, cog_desafios, autor_id: int, resposta_correta: str, pontos: int):
        super().__init__(timeout=60)  # O utilizador tem 60 segundos para responder
        self.cog_desafios = cog_desafios
        self.autor_id = autor_id
        self.resposta_correta = resposta_correta.strip().upper()
        self.pontos = pontos
        self.respondido = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Apenas quem iniciou o desafio pode responder
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("❌ Campeão, este desafio não é teu! Usa `!desafio` para gerares o teu próprio.", ephemeral=True)
            return False
        return True

    async def processar_resposta(self, interaction: discord.Interaction, escolha: str):
        if self.respondido:
            return
        self.respondido = True
        self.stop()

        # Desabilita todos os botões após a escolha
        for child in self.children:
            child.disabled = True

        if escolha == self.resposta_correta:
            # Atualiza a pontuação do utilizador
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
            embed_erro.set_footer(text="Mais uma para o registo de falhas.")
            await interaction.response.edit_message(embed=embed_erro, view=self)

    @discord.ui.button(label="Opção A", style=discord.ButtonStyle.primary, custom_id="A")
    async def opcao_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_resposta(interaction, "A")

    @discord.ui.button(label="Opção B", style=discord.ButtonStyle.primary, custom_id="B")
    async def opcao_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_resposta(interaction, "B")

    @discord.ui.button(label="Opção C", style=discord.ButtonStyle.primary, custom_id="C")
    async def opcao_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_resposta(interaction, "C")

    @discord.ui.button(label="Opção D", style=discord.ButtonStyle.primary, custom_id="D")
    async def opcao_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_resposta(interaction, "D")

    async def on_timeout(self):
        """Trata o caso em que o utilizador demora mais de 60 segundos"""
        if not self.respondido:
            self.clear_items()
            # Esta função tenta apenas limpar a visualização para evitar cliques fantasmas
            logger.info(f"⏳ Tempo limite esgotado para o desafio do utilizador [{self.autor_id}]")

# ===================================================================
# COG DE DESAFIOS E RANKING
# ===================================================================
class Desafios(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.leaderboard = self.carregar_leaderboard()

    def carregar_leaderboard(self):
        """Carrega o ficheiro JSON com as pontuações"""
        if LEADERBOARD_FILE.exists():
            try:
                with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
                    logger.info("💾 Leaderboard carregada com sucesso!")
                    return json.load(f)
            except Exception as e:
                logger.error(f"❌ Erro ao ler leaderboard.json: {e}")
        return {}

    def guardar_leaderboard(self):
        """Persiste as pontuações no disco"""
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

    @commands.command(name="desafio")
    @commands.guild_only()
    async def gerar_desafio(self, ctx, tecnologia: str = "Python"):
        """Gera um desafio de escolha múltipla sobre a tecnologia especificada"""
        async with ctx.typing():
            # Prompt estruturado para forçar a IA a responder em formato JSON estrito
            prompt_quiz = (
                f"Gere um desafio técnico de escolha múltipla sobre {tecnologia} para programadores.\n"
                "Deves responder estritamente em formato JSON válido, contendo as seguintes chaves:\n"
                "- 'pergunta': A descrição clara do problema técnico ou código com erro.\n"
                "- 'A': Texto da Opção A.\n"
                "- 'B': Texto da Opção B.\n"
                "- 'C': Texto da Opção C.\n"
                "- 'D': Texto da Opção D.\n"
                "- 'correta': A letra da opção correta (A, B, C ou D).\n"
                "- 'pontos': Um número inteiro de 10 a 50 com base na dificuldade do problema.\n\n"
                "Não adiciones nenhuma formatação markdown extra, apenas o bloco JSON."
            )

            try:
                # Solicitação estruturada ao Gemini
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt_quiz,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.8
                    )
                )

                dados_quiz = json.loads(response.text)
                
                pergunta = dados_quiz.get("pergunta", "Sem descrição")
                opt_a = dados_quiz.get("A", "Opção A")
                opt_b = dados_quiz.get("B", "Opção B")
                opt_c = dados_quiz.get("C", "Opção C")
                opt_d = dados_quiz.get("D", "Opção D")
                correta = dados_quiz.get("correta", "A")
                pontos = int(dados_quiz.get("pontos", 10))

                # Monta um Embed elegante
                embed_desafio = discord.Embed(
                    title=f"💻 DESAFIO TÉCNICO: {tecnologia.upper()}",
                    description=f"**Pergunta:**\n{pergunta}\n\n"
                                f"**A)** {opt_a}\n"
                                f"**B)** {opt_b}\n"
                                f"**C)** {opt_c}\n"
                                f"**D)** {opt_d}",
                    color=discord.Color.blue()
                )
                embed_desafio.add_field(name="💰 Recompensa", value=f"`{pontos} pontos`", inline=True)
                embed_desafio.set_footer(text=f"Desafio gerado para {ctx.author.name}. Tens 60 segundos!")

                view_botoes = QuizView(self, ctx.author.id, correta, pontos)
                await ctx.send(embed=embed_desafio, view=view_botoes)

            except Exception as e:
                logger.error(f"❌ Erro ao processar desafio técnico: {e}")
                await ctx.send("❌ Rapaz, deu algum erro a gerar o desafio. Tenta outra tecnologia!")

    @commands.command(name="ranking")
    @commands.guild_only()
    async def mostrar_ranking(self, ctx):
        """Exibe o top 10 utilizadores com maior pontuação no servidor"""
        if not self.leaderboard:
            await ctx.send("📉 Campeão, ainda ninguém pontuou neste servidor! Usa `!desafio` para começares.")
            return

        # Ordena a leaderboard do maior para o menor
        ranking_ordenado = sorted(self.leaderboard.items(), key=lambda item: item[1], reverse=True)[:10]

        embed_ranking = discord.Embed(
            title="🏆 RANKING DE PROGRAMADORES",
            description="Estes são os campeões que mais estudam e acertam desafios técnicos!",
            color=discord.Color.gold()
        )

        lista_membros = ""
        for index, (user_id, pontos) in enumerate(ranking_ordenado, start=1):
            membro = ctx.guild.get_member(int(user_id))
            nome_membro = membro.name if membro else f"Utilizador Desconhecido ({user_id})"
            
            medalha = "👑" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"`#{index}`"
            lista_membros += f"{medalha} **{nome_membro}** — `{pontos} pontos`\n"

        embed_ranking.add_field(name="Classificação", value=lista_membros, inline=False)
        await ctx.send(embed=embed_ranking)

async def setup(bot):
    await bot.add_cog(Desafios(bot))
```
eof

### 🚀 O que este novo Cog adiciona ao seu bot?

1. **Comando `!desafio [Tecnologia]` (Ex: `!desafio Python`, `!desafio Linux`, `!desafio SQL`):**
   * A Cristiane invoca o Gemini, cria uma pergunta técnica e gera 4 botões dinâmicos (`Opção A`, `Opção B`...). 
   * Apenas quem pediu o desafio pode responder. Se acertar dentro de 60 segundos, ganha os pontos; se errar, a Cristiane dá-lhe uma reprimenda clássica!
2. **Comando `!ranking`:**
   * Mostra um painel visualmente fantástico com os top 10 utilizadores que acumularam mais pontos no servidor, incentivando uma competição saudável de estudos de programação e Linux entre os seus amigos.

---

### 📝 Como instalar no seu CachyOS agora mesmo?

1. **Abra o seu terminal:**
   ```fish
   nano cogs/desafios.py
   ```
2. **Copie todo o código acima e cole dentro do nano.** Salve e saia (`Ctrl+O`, `Enter`, `Ctrl+X`).
3. **Faça o Push para o GitHub:**
   ```fish
   git add cogs/desafios.py
   git commit -m "Feature: Adicionado modulo de desafios tecnicos e ranking interativo"
   git push origin main
