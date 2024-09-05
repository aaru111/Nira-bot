import discord
from discord.ext import commands
from modules.triviamod import TriviaView


class Trivia(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def trivia(self, ctx):
        await self._send_trivia(ctx, ctx.author.id, 0)

    async def _send_trivia(self, ctx, user_id, score):
        question_data = await TriviaView.fetch_trivia_question()

        category = question_data['category']
        difficulty = question_data['difficulty']
        question = question_data['question']
        correct_answer = question_data['correct_answer']
        all_answers = question_data['all_answers']

        embed = discord.Embed(
            title=
            f"**Category:** {category} | **Difficulty:** {difficulty.capitalize()}",
            description=f"**Question:**\n*{question}*\n\n" + "\n".join([
                f"**{chr(65+i)}:** {answer}"
                for i, answer in enumerate(all_answers)
            ]),
            color=discord.Color.blue())
        embed.set_footer(
            text=f"You have 30 seconds to answer! | Current score: {score}")

        view = TriviaView(correct_answer, self, user_id, score)

        if isinstance(ctx, discord.Interaction):
            if ctx.response.is_done():
                message = await ctx.edit_original_response(embed=embed,
                                                           view=view)
            else:
                message = await ctx.response.send_message(embed=embed,
                                                          view=view)
                message = await ctx.original_response()
        else:
            message = await ctx.send(embed=embed, view=view)
        view.message = message  # Store the message in the view
        await view.start_timer(ctx.channel)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Trivia(bot))
