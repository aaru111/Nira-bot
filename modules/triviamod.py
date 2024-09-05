import discord
import aiohttp
import random
import html
import asyncio


class TriviaView(discord.ui.View):

    def __init__(self, correct_answer, cog, user_id, score):
        super().__init__(timeout=35.0)
        self.correct_answer = correct_answer
        self.cog = cog
        self.user_id = user_id
        self.score = score
        self.answered = False
        self.time_left = 30
        self.timer_message = None
        self.timer_task = None
        self.message: discord.InteractionMessage | discord.Message | None = None

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This trivia game is not for you. Please start your own game using the trivia command.",
                ephemeral=True)
            return False
        if self.answered:
            await interaction.response.send_message(
                "You've already answered this question!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if not self.answered:
            for item in self.children:
                item.disabled = True
            await self.message.edit(
                content="Time's up! You didn't answer in time.", view=self)
            await self.safe_delete_timer()
            await asyncio.sleep(2)
            play_again_view = PlayAgainView(self.cog, self.user_id, self.score)
            await self.message.edit(content=f"Your final score: {self.score}",
                                    view=play_again_view)
            play_again_view.message = self.message

    async def start_timer(self, channel):
        self.timer_message = await channel.send(
            f"Time left: {self.time_left} seconds")
        self.timer_task = asyncio.create_task(self.run_timer())

    async def run_timer(self):
        try:
            while self.time_left > 0 and not self.answered:
                await asyncio.sleep(1)
                self.time_left -= 1
                if self.timer_message:
                    try:
                        await self.timer_message.edit(
                            content=f"Time left: {self.time_left} seconds")
                    except discord.NotFound:
                        break
            if not self.answered:
                await self.on_timeout()
        except asyncio.CancelledError:
            pass

    async def safe_delete_timer(self):
        if self.timer_task:
            self.timer_task.cancel()
            try:
                await self.timer_task
            except asyncio.CancelledError:
                pass
        if self.timer_message:
            try:
                await self.timer_message.delete()
            except discord.NotFound:
                pass
            finally:
                self.timer_message = None

    @discord.ui.button(label='A', style=discord.ButtonStyle.primary)
    async def button_a(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
        await self.check_answer(interaction, 'A')

    @discord.ui.button(label='B', style=discord.ButtonStyle.primary)
    async def button_b(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
        await self.check_answer(interaction, 'B')

    @discord.ui.button(label='C', style=discord.ButtonStyle.primary)
    async def button_c(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
        await self.check_answer(interaction, 'C')

    @discord.ui.button(label='D', style=discord.ButtonStyle.primary)
    async def button_d(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
        await self.check_answer(interaction, 'D')

    async def check_answer(self, interaction: discord.Interaction,
                           chosen_answer):
        if self.answered:
            return
        self.answered = True

        # Reset the timeout
        self.stop()
        self.timeout = None

        for item in self.children:
            item.disabled = True
        await self.safe_delete_timer()
        if chosen_answer == self.correct_answer:
            self.score += 1
            content = f"**Correct!** The answer was {self.correct_answer}."
            await interaction.response.edit_message(content=content, view=self)
            await asyncio.sleep(2)
            await self.cog._send_trivia(interaction, self.user_id, self.score)
        else:
            content = f"**{chosen_answer}** was not the correct answer. The correct answer was **{self.correct_answer}**."
            await interaction.response.edit_message(content=content, view=self)
            await asyncio.sleep(2)
            play_again_view = PlayAgainView(self.cog, self.user_id, self.score)
            await interaction.edit_original_response(
                content=f"Your final score: {self.score}",
                view=play_again_view)
            play_again_view.message = await interaction.original_response()

    @staticmethod
    async def fetch_trivia_question():
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    'https://opentdb.com/api.php?amount=1&type=multiple'
            ) as response:
                data = await response.json()

        question_data = data['results'][0]
        category = question_data['category']
        difficulty = question_data['difficulty']
        question = html.unescape(question_data['question'])
        correct_answer = html.unescape(question_data['correct_answer'])
        incorrect_answers = [
            html.unescape(answer)
            for answer in question_data['incorrect_answers']
        ]

        all_answers = incorrect_answers + [correct_answer]
        random.shuffle(all_answers)
        correct_letter = chr(65 + all_answers.index(correct_answer))

        return {
            'category': category,
            'difficulty': difficulty,
            'question': question,
            'correct_answer': correct_answer,
            'all_answers': all_answers,
            'correct_letter': correct_letter
        }


class PlayAgainView(discord.ui.View):

    def __init__(self, cog, user_id, score):
        super().__init__(timeout=30.0)
        self.cog = cog
        self.user_id = user_id
        self.score = score

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This trivia game is not for you. Please start your own game using the trivia command.",
                ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.green)
    async def play_again(self, interaction: discord.Interaction,
                         button: discord.ui.Button):
        # Reset the timeout
        self.stop()
        self.timeout = None

        await interaction.response.defer()
        await self.cog._send_trivia(interaction, self.user_id, 0)
