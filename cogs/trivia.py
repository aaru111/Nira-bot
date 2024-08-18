import discord
from discord.ext import commands
import aiohttp
import random
import html

class TriviaView(discord.ui.View):
    def __init__(self, correct_answer, cog):
        super().__init__(timeout=30.0)
        self.correct_answer = correct_answer
        self.cog = cog

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label='A', style=discord.ButtonStyle.primary)
    async def button_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.check_answer(interaction, 'A')

    @discord.ui.button(label='B', style=discord.ButtonStyle.primary)
    async def button_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.check_answer(interaction, 'B')

    @discord.ui.button(label='C', style=discord.ButtonStyle.primary)
    async def button_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.check_answer(interaction, 'C')

    @discord.ui.button(label='D', style=discord.ButtonStyle.primary)
    async def button_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.check_answer(interaction, 'D')

    async def check_answer(self, interaction: discord.Interaction, chosen_answer):
        self.clear_items()
        if chosen_answer == self.correct_answer:
            content = f"**Correct!** The answer was {self.correct_answer}."
        else:
            content = f"**{chosen_answer}** was not the correct answer. The correct answer was **{self.correct_answer}**."
        
        play_again_view = PlayAgainView(self.cog)
        await interaction.response.edit_message(content=content, view=play_again_view)
        play_again_view.message = await interaction.original_response()

class PlayAgainView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=30.0)
        self.cog = cog

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.green)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.trivia(interaction)

class Trivia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def trivia(self, ctx):
        await self._send_trivia(ctx)

    async def _send_trivia(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get('https://opentdb.com/api.php?amount=1&type=multiple') as response:
                data = await response.json()

        question_data = data['results'][0]
        category = question_data['category']
        difficulty = question_data['difficulty']
        question = html.unescape(question_data['question'])
        correct_answer = html.unescape(question_data['correct_answer'])
        incorrect_answers = [html.unescape(answer) for answer in question_data['incorrect_answers']]

        all_answers = incorrect_answers + [correct_answer]
        random.shuffle(all_answers)

        correct_letter = chr(65 + all_answers.index(correct_answer))

        embed = discord.Embed(
            title=f"**Category:** {category} | **Difficulty:** {difficulty.capitalize()}",
            description=f"**Question:**\n*{question}*\n\n" + 
                        "\n".join([f"**{chr(65+i)}:** {answer}" for i, answer in enumerate(all_answers)]),
            color=discord.Color.blue()
        )
        embed.set_footer(text="You have 30 seconds to answer!")

        view = TriviaView(correct_letter, self)
        message = await ctx.send(embed=embed, view=view)
        view.message = message

async def setup(bot):
    await bot.add_cog(Trivia(bot))