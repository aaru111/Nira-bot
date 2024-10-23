from typing import Optional, List
import discord
from discord.ext import commands
import aiohttp
import random
from io import BytesIO
from PIL import Image
import asyncio
from discord.ui import Button, View


class GiveUpButton(Button):

    def __init__(self):
        super().__init__(label="Give Up", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        if hasattr(self.view, 'stop_game'):
            await self.view.stop_game(interaction, gave_up=True)


class PokemonGuessView(View):

    def __init__(self,
                 pokemon_name: str,
                 pokemon_image: str,
                 timeout: float = 25.0):
        super().__init__(timeout=timeout)
        self.pokemon_name = pokemon_name.lower()
        self.pokemon_image = pokemon_image
        self.attempts = 3
        self.add_item(GiveUpButton())

    async def stop_game(self,
                        interaction: discord.Interaction,
                        gave_up: bool = False):
        self.stop()
        if gave_up:
            # Create embed with the "gave up" message
            embed = discord.Embed(
                title="**Who's That Pokémon?**",
                description=
                f"You took too long to answer... The Pokémon was: {self.pokemon_name.title()}",
                color=discord.Color.red())

            # Get the actual Pokémon image
            async with aiohttp.ClientSession() as session:
                async with session.get(self.pokemon_image) as resp:
                    actual_image = BytesIO(await resp.read())

            # Edit the message with the new embed and actual image
            await interaction.response.edit_message(
                embed=embed,
                attachments=[
                    discord.File(actual_image, filename="pokemon.png")
                ],
                view=None)


class Pokemon(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pokeapi_url = "https://pokeapi.co/api/v2"
        self.session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self.session:
            await self.session.close()

    async def get_random_pokemon(self) -> dict:
        """Fetch a random Pokémon from the PokeAPI."""
        async with self.session.get(
                f"{self.pokeapi_url}/pokemon?limit=898") as resp:
            data = await resp.json()
            pokemon = random.choice(data['results'])

        async with self.session.get(pokemon['url']) as resp:
            return await resp.json()

    async def create_silhouette(self, image_url: str) -> BytesIO:
        """Create a silhouette from a Pokémon image."""
        async with self.session.get(image_url) as resp:
            image_data = await resp.read()

        with Image.open(BytesIO(image_data)) as img:
            # Convert to RGBA if not already
            img = img.convert('RGBA')

            # Create silhouette
            pixels = img.load()
            width, height = img.size
            for x in range(width):
                for y in range(height):
                    r, g, b, a = pixels[x, y]
                    if a > 0:
                        pixels[x, y] = (0, 0, 0, 255)

            # Save to BytesIO
            output = BytesIO()
            img.save(output, format='PNG')
            output.seek(0)
            return output

    @commands.command(name="whosthat", description="Play Who's That Pokémon?")
    async def whos_that_pokemon(self, ctx: commands.Context):
        """Start a game of Who's That Pokémon?"""
        # Get random pokemon
        pokemon_data = await self.get_random_pokemon()
        pokemon_name = pokemon_data['name']
        pokemon_image = pokemon_data['sprites']['other']['official-artwork'][
            'front_default']

        if not pokemon_image:
            await ctx.send(
                "Sorry, couldn't load Pokémon image. Please try again!")
            return

        # Create silhouette
        silhouette = await self.create_silhouette(pokemon_image)

        # Create initial embed
        embed = discord.Embed(title="**Who's That Pokémon?**",
                              description="Can you guess who this Pokémon is?",
                              color=discord.Color.blue())
        embed.set_image(url="attachment://pokemon.png")
        embed.set_footer(text="Attempts remaining: 3")

        # Create view with timeout and pass pokemon_image
        view = PokemonGuessView(pokemon_name, pokemon_image)

        # Send initial message
        message = await ctx.send(embed=embed,
                                 file=discord.File(silhouette,
                                                   filename="pokemon.png"),
                                 view=view)

        def check_guess(m):
            return m.author == ctx.author and m.channel == ctx.channel

        while view.attempts > 0:
            try:
                guess = await self.bot.wait_for('message',
                                                timeout=25.0,
                                                check=check_guess)

                if guess.content.lower() == pokemon_name.lower():
                    embed.description = f"Correct! The Pokémon was: {pokemon_name.title()}"
                    embed.color = discord.Color.green()
                    # Reveal actual pokemon image
                    async with self.session.get(pokemon_image) as resp:
                        actual_image = BytesIO(await resp.read())
                    await message.edit(embed=embed,
                                       attachments=[
                                           discord.File(actual_image,
                                                        filename="pokemon.png")
                                       ],
                                       view=None)
                    break

                view.attempts -= 1
                if view.attempts > 0:
                    embed.set_footer(
                        text=f"Attempts remaining: {view.attempts}")
                    await message.edit(embed=embed)
                else:
                    embed.description = f"Game Over! The Pokémon was: {pokemon_name.title()}"
                    embed.color = discord.Color.red()
                    # Reveal actual pokemon image
                    async with self.session.get(pokemon_image) as resp:
                        actual_image = BytesIO(await resp.read())
                    await message.edit(embed=embed,
                                       attachments=[
                                           discord.File(actual_image,
                                                        filename="pokemon.png")
                                       ],
                                       view=None)

            except asyncio.TimeoutError:
                embed.description = f"You took too long to answer... The Pokémon was: {pokemon_name.title()}"
                embed.color = discord.Color.red()
                # Reveal actual pokemon image
                async with self.session.get(pokemon_image) as resp:
                    actual_image = BytesIO(await resp.read())
                await message.edit(embed=embed,
                                   attachments=[
                                       discord.File(actual_image,
                                                    filename="pokemon.png")
                                   ],
                                   view=None)
                break


async def setup(bot: commands.Bot):
    await bot.add_cog(Pokemon(bot))
