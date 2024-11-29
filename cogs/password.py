import discord
from discord.ext import commands
from discord import ui
import re
import random
from typing import Dict

# Constants
CHEMICAL_ELEMENTS = [
    'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne', 'Na', 'Mg', 'Al',
    'Si', 'P', 'S', 'Cl', 'Ar', 'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe',
    'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr',
    'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn'
]

CHESS_MOVES = [
    'e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'd6', 'Nc3', 'Be7', 'O-O', 'Nf6', 'd4',
    'd5', 'exd5', 'Nxd5', 'Re1', 'Be6', 'Nxe5', 'Nxe5'
]

MONTHS = [
    'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
    'september', 'october', 'november', 'december'
]

MOON_PHASES = [
    '🌑 New Moon', '🌒 Waxing Crescent', '🌓 First Quarter', '🌔 Waxing Gibbous',
    '🌕 Full Moon', '🌖 Waning Gibbous', '🌗 Last Quarter', '🌘 Waning Crescent'
]

RECIPE_INGREDIENTS = [
    'flour', 'sugar', 'eggs', 'milk', 'butter', 'vanilla', 'salt',
    'baking powder', 'chocolate chips', 'cinnamon', 'honey', 'oil'
]

RECIPE_AMOUNTS = [
    '1 cup', '2 tbsp', '3 oz', '1/2 cup', '1 tsp', '2 cups', '3 tbsp', '4 oz',
    '1/4 cup', '1/3 cup', '2 tsp', '1 pinch'
]

SPECIAL_CHARS = '!@#$%^&*(),.?":{}|<>'


class Result:

    def __init__(self, success: bool, message: str = ""):
        self.success = success
        self.message = message


class PasswordView(ui.View):

    def __init__(self, game_instance):
        super().__init__(timeout=None)
        self.game = game_instance

    @ui.button(label="Submit Password", style=discord.ButtonStyle.green)
    async def submit(self, interaction: discord.Interaction,
                     button: ui.Button):
        if interaction.user.id != self.game.player_id:
            await interaction.response.send_message("This isn't your game!",
                                                    ephemeral=True)
            return

        modal = PasswordModal(self.game)
        await interaction.response.send_modal(modal)

    @ui.button(label="End Game", style=discord.ButtonStyle.red)
    async def end_game(self, interaction: discord.Interaction,
                       button: ui.Button):
        if interaction.user.id != self.game.player_id:
            await interaction.response.send_message("This isn't your game!",
                                                    ephemeral=True)
            return

        await interaction.response.send_message(
            "Game ended. Thanks for playing!")
        self.game.cog.active_games.pop(self.game.player_id, None)
        self.stop()


class PasswordModal(ui.Modal, title="Enter Your Password"):

    def __init__(self, game_instance):
        super().__init__()
        self.game = game_instance
 
        self.password = ui.TextInput(
            label="Password",
            style=discord.TextStyle.short,
            placeholder="Enter your password here...",
            default=self.game.
            password  
        )
        self.add_item(self.password)  

    async def on_submit(self, interaction: discord.Interaction):
        result = await self.game.check_password(self.password.value)
        if result.success:
            if self.game.current_rule > self.game.total_rules:
                await interaction.response.send_message(
                    "🎉 Congratulations! You've won The Password Game!")
                self.game.cog.active_games.pop(self.game.player_id, None)
            else:
                embed = self.game.create_game_embed()
                view = PasswordView(self.game)
                await self.game.message.edit(embed=embed, view=view)
                await interaction.response.defer()
        else:
            await interaction.response.send_message(f"❌ {result.message}",
                                                    ephemeral=True)


class GameState:

    def __init__(self, cog, player_id):
        self.cog = cog
        self.player_id = player_id
        self.current_rule = 1
        self.total_rules = 18
        self.password = ""
        self.message = None  

     
        self.moon_phase = random.choice(MOON_PHASES)
        self.current_price = round(random.uniform(10, 1000), 2)
        self.chess_move = random.choice(CHESS_MOVES)
        self.captcha = self.generate_captcha()
        self.roman_sum = random.randint(50, 100)
        self.required_digit_sum = random.randint(20, 30)
        self.fibonacci_requirement = self.generate_fibonacci()
        self.prime_requirement = self.generate_prime_sequence()
        self.recipe = self.generate_recipe()
        self.egg_count = random.randint(1, 5)
        self.rotating_digit = random.randint(0, 9)
        self.color = self.generate_color()

    def create_game_embed(self):
        embed = discord.Embed(title="The Password Game", color=0x00ff00)
        embed.add_field(name="Current Rule",
                        value=str(self.current_rule),
                        inline=False)

        if self.password:
            embed.add_field(name="Current Password",
                            value=f"```{self.password}```",
                            inline=False)

        embed.add_field(name="Rules",
                        value=self.get_active_rules(),
                        inline=False)
        return embed

    def get_active_rules(self):
        rules = []
        for i in range(1, self.current_rule + 1):
            rules.append(self.get_rule_description(i))
        return "\n".join(rules)

    def get_rule_description(self, rule_number):
        rules = {
            1: "Password must be at least 5 characters",
            2: "Must contain an uppercase letter",
            3: "Must contain a number",
            4: "Must contain a special character",
            5: "Must contain a month of the year",
            6: f"Must contain Roman numerals that add up to {self.roman_sum}",
            7: "Must contain a chemical element symbol",
            8: f"Must contain the current moon phase: {self.moon_phase}",
            9: f"Must contain ${self.current_price}",
            10: f"Must contain the chess move: {self.chess_move}",
            11: f"Must contain the captcha: {self.captcha}",
            12: f"The sum of all numbers must equal {self.required_digit_sum}",
            13:
            f"Must contain the Fibonacci sequence: {self.fibonacci_requirement}",
            14:
            f"Must contain these prime numbers in order: {self.prime_requirement}",
            15: f"Must contain the recipe: {self.recipe}",
            16: f"Must contain {self.egg_count} egg emoji(s) 🥚",
            17:
            f"The digit {self.rotating_digit} must rotate one position right every submission",
            18: f"Must contain the color #{self.color}"
        }
        return f"Rule {rule_number}: {rules.get(rule_number, 'Unknown rule')}"

    async def check_password(self, password):
        self.password = password


        for rule in range(1, self.current_rule + 1):
            result = self.check_rule(rule)
            if not result.success:
                return result

        self.current_rule += 1
        return Result(True)

    def check_rule(self, rule):
        if rule == 1:
            if len(self.password) < 5:
                return Result(False,
                              "Password must be at least 5 characters long.")

        elif rule == 2:
            if not any(c.isupper() for c in self.password):
                return Result(False,
                              "Password must contain an uppercase letter.")

        elif rule == 3:
            if not any(c.isdigit() for c in self.password):
                return Result(False, "Password must contain a number.")

        elif rule == 4:
            if not any(c in SPECIAL_CHARS for c in self.password):
                return Result(False,
                              "Password must contain a special character.")

        elif rule == 5:
            if not any(month in self.password.lower() for month in MONTHS):
                return Result(False,
                              "Password must contain a month of the year.")

        elif rule == 6:
            roman_numerals = re.findall(r'[IVXLCDM]+', self.password)
            total = sum(
                self.roman_to_int(numeral) for numeral in roman_numerals)
            if total != self.roman_sum:
                return Result(False,
                              f"Roman numerals must sum to {self.roman_sum}.")

        elif rule == 7:
            if not any(element in self.password
                       for element in CHEMICAL_ELEMENTS):
                return Result(
                    False, "Password must contain a chemical element symbol.")

        elif rule == 8:
            if self.moon_phase not in self.password:
                return Result(
                    False,
                    f"Password must contain the moon phase: {self.moon_phase}")

        elif rule == 9:
            if f"${self.current_price}" not in self.password:
                return Result(False,
                              f"Password must contain ${self.current_price}")

        elif rule == 10:
            if self.chess_move not in self.password:
                return Result(
                    False,
                    f"Password must contain the chess move: {self.chess_move}")

        elif rule == 11:
            if self.captcha not in self.password:
                return Result(
                    False,
                    f"Password must contain the captcha: {self.captcha}")

        elif rule == 12:
            numbers = re.findall(r'\d+', self.password)
            total = sum(int(num) for num in numbers)
            if total != self.required_digit_sum:
                return Result(
                    False,
                    f"Sum of all numbers must be {self.required_digit_sum}")

        elif rule == 13:
            if self.fibonacci_requirement not in self.password:
                return Result(
                    False,
                    f"Must contain the Fibonacci sequence: {self.fibonacci_requirement}"
                )

        elif rule == 14:
            if self.prime_requirement not in self.password:
                return Result(
                    False,
                    f"Must contain these prime numbers in order: {self.prime_requirement}"
                )

        elif rule == 15:
            if self.recipe not in self.password:
                return Result(False, f"Must contain the recipe: {self.recipe}")

        elif rule == 16:
            egg_count = self.password.count("🥚")
            if egg_count != self.egg_count:
                return Result(
                    False,
                    f"Must contain exactly {self.egg_count} egg emoji(s)")

        elif rule == 17:
            digit = str(self.rotating_digit)
            if digit not in self.password:
                return Result(False, f"Must contain the digit {digit}")

        elif rule == 18:
            if f"#{self.color}" not in self.password:
                return Result(False, f"Must contain the color #{self.color}")

        return Result(True)

    def roman_to_int(self, s):
        roman_values = {
            'I': 1,
            'V': 5,
            'X': 10,
            'L': 50,
            'C': 100,
            'D': 500,
            'M': 1000
        }
        total = 0
        prev_value = 0
        for char in reversed(s):
            current_value = roman_values.get(char, 0)
            if current_value >= prev_value:
                total += current_value
            else:
                total -= current_value
            prev_value = current_value
        return total

    def generate_captcha(self):
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
        return ''.join(random.choice(chars) for _ in range(6))

    def generate_fibonacci(self):
        sequence = [1, 1]
        for _ in range(3):
            sequence.append(sequence[-1] + sequence[-2])
        return ''.join(map(str, sequence))

    def generate_prime_sequence(self):
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
        sequence = random.sample(primes, 3)
        return ''.join(map(str, sorted(sequence)))

    def generate_recipe(self):
        return f"{random.choice(RECIPE_AMOUNTS)} {random.choice(RECIPE_INGREDIENTS)}"

    def generate_color(self):
        return ''.join(random.choice('0123456789ABCDEF') for _ in range(6))


class PasswordGame(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.active_games: Dict[int, GameState] = {}

    @commands.command(name="passwordgame")
    async def password_game(self, ctx):
        """Start a new password game"""
        if ctx.author.id in self.active_games:
            await ctx.send("You already have an active game!")
            return

        game = GameState(self, ctx.author.id)
        self.active_games[ctx.author.id] = game

        embed = game.create_game_embed()
        view = PasswordView(game)
        game.message = await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(PasswordGame(bot))
