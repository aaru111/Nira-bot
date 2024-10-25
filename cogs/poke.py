from typing import Optional, List
import discord
from discord.ext import commands
import aiohttp
import random
from io import BytesIO
from PIL import Image
import asyncio
from difflib import get_close_matches
from discord import Interaction, app_commands

from modules.pokemod import *


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

    async def pokemon_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> List[app_commands.Choice[str]]:
        if not current:
            return []
        if not hasattr(self, '_pokemon_names_cache'):
            # Fetch the base Pokémon names
            async with self.session.get(
                    f"{self.pokeapi_url}/pokemon?limit=898") as resp:
                data = await resp.json()
            base_names = {pokemon['name']
                          for pokemon in data['results']
                          }  # Use a set to avoid duplicates

            # Fetch additional forms and Mega Evolutions
            async with self.session.get(
                f"{self.pokeapi_url}/pokemon-form?limit=2000") as resp:
                form_data = await resp.json()
            form_names = {form['name']
                          for form in form_data['results']}  # Also use a set

            # Combine the base Pokémon names with the form names, ensuring uniqueness
            self._pokemon_names_cache = list(
                base_names | form_names)  # Union of both sets

        # Perform matching for the current input
        pokemon_names = self._pokemon_names_cache
        exact_matches = [
            app_commands.Choice(name=name, value=name)
            for name in pokemon_names if current.lower() in name.lower()
        ]
        if exact_matches:
            return exact_matches[:25]

        # Fallback to close matches if no exact matches are found
        close_matches = get_close_matches(current.lower(),
                                          pokemon_names,
                                          n=25,
                                          cutoff=0.4)
        return [
            app_commands.Choice(name=name, value=name)
            for name in close_matches
        ]

    async def find_closest_pokemon(self, pokemon_name: str) -> Optional[str]:
        if not hasattr(self, '_pokemon_names_cache'):
            # Load the Pokémon and form names if not already cached
            async with self.session.get(
                    f"{self.pokeapi_url}/pokemon?limit=898") as resp:
                data = await resp.json()
            self._pokemon_names_cache = [
                pokemon['name'] for pokemon in data['results']
            ]

            # Fetch additional forms and Mega Evolutions
            async with self.session.get(
                f"{self.pokeapi_url}/pokemon-form?limit=2000") as resp:
                form_data = await resp.json()
            form_names = [form['name'] for form in form_data['results']]

            # Combine base and form names
            self._pokemon_names_cache.extend(form_names)

        # Use difflib to find the closest match
        matches = get_close_matches(pokemon_name.lower(),
                                    self._pokemon_names_cache,
                                    n=1,
                                    cutoff=0.6)
        return matches[0] if matches else None

    @commands.hybrid_command(
        name="pokedex",
        aliases=["pd", "dex"],
        description=
        "Lookup detailed information about a Pokémon in the Pokédex",
        brief="Search the Pokédex",
        help=
        """Search for a Pokémon in the Pokédex and view detailed information including:
                - Base stats and type effectiveness
                - Evolution chain and methods
                - Pokédex description
                - Moves and abilities
                Usage: !pokedex <pokemon_name>
                Example: !pokedex pikachu""")
    @app_commands.describe(
        pokemon_name="The name or number of the Pokémon to lookup")
    @app_commands.autocomplete(pokemon_name=pokemon_autocomplete)
    async def pokedex(self, ctx: commands.Context, *, pokemon_name: str):
        """Lookup detailed information about a Pokémon."""
        is_interaction = hasattr(ctx,
                                 'interaction') and ctx.interaction is not None
        try:
            # Defer interaction for slash commands
            if is_interaction:
                await ctx.interaction.response.defer()

            async with self.session.get(
                    f"{self.pokeapi_url}/pokemon/{pokemon_name.lower()}"
            ) as resp:
                if resp.status == 404:
                    # Try to find the closest match
                    closest_match = await self.find_closest_pokemon(
                        pokemon_name)
                    if closest_match:
                        confirm_view = discord.ui.View(timeout=30)
                        confirm_button = discord.ui.Button(
                            style=discord.ButtonStyle.primary,
                            label=f"Show {closest_match.title()}")

                        async def confirm_callback(
                                interaction: discord.Interaction):
                            if interaction.user != ctx.author:
                                await interaction.response.send_message(
                                    "This isn't your search!", ephemeral=True)
                                return
                            await interaction.response.defer(
                            )  # Defer again if needed
                            async with self.session.get(
                                    f"{self.pokeapi_url}/pokemon/{closest_match.lower()}"
                            ) as pokemon_resp:
                                pokemon_data = await pokemon_resp.json()
                            view = PokemonInfoView(pokemon_data)
                            embed = await view.create_main_embed()
                            await interaction.followup.send(embed=embed,
                                                            view=view)
                            confirm_view.stop()

                        confirm_button.callback = confirm_callback
                        confirm_view.add_item(confirm_button)

                        # Send a response depending on whether it's a slash command or a regular command
                        if is_interaction:
                            await ctx.interaction.followup.send(
                                f"Pokémon '{pokemon_name}' not found! Did you mean '{closest_match.title()}'?",
                                view=confirm_view)
                        else:
                            await ctx.send(
                                f"Pokémon '{pokemon_name}' not found! Did you mean '{closest_match.title()}'?",
                                view=confirm_view)
                        return
                    else:
                        # Send a response depending on the command type
                        if is_interaction:
                            await ctx.interaction.followup.send(
                                f"Pokémon '{pokemon_name}' not found!")
                        else:
                            await ctx.send(
                                f"Pokémon '{pokemon_name}' not found!")
                        return

                # If the Pokémon is found, send the data
                pokemon_data = await resp.json()
                view = PokemonInfoView(pokemon_data)
                embed = await view.create_main_embed()

                # Send a response based on the command type
                if is_interaction:
                    await ctx.interaction.followup.send(embed=embed, view=view)
                else:
                    await ctx.send(embed=embed, view=view)

        except Exception as e:
            # Handle unexpected errors gracefully
            if is_interaction:
                await ctx.interaction.followup.send(
                    f"An error occurred: {str(e)}")
            else:
                await ctx.send(f"An error occurred: {str(e)}")

    @commands.hybrid_command(
        name="wtp",
        aliases=["whosthat", "whosthatpokemon"],
        description="Play a game of Who's That Pokémon?",
        brief="Play Who's That Pokémon?",
        help=
        """Start a game of Who's That Pokémon where you need to guess the Pokémon from its silhouette.

        Rules:
        - You have 3 attempts to guess correctly
        - You have 25 seconds to make each guess
        - The spelling must be exact
        - Only the person who started the game can make guesses

        Usage: /wtp
        After starting, type your guess in the chat.""")
    async def wtp(self, ctx: commands.Context):
        """Play a game of Who's That Pokémon? Guess the Pokémon from its silhouette!"""
        pokemon_data = await self.get_random_pokemon()
        pokemon_name = pokemon_data['name']
        pokemon_image = pokemon_data['sprites']['other']['official-artwork'][
            'front_default']

        if not pokemon_image:
            await ctx.send(
                "Sorry, couldn't load Pokémon image. Please try again!")
            return

        silhouette = await self.create_silhouette(pokemon_image)

        embed = discord.Embed(title="**Who's That Pokémon?**",
                              description="Can you guess who this Pokémon is?",
                              color=discord.Color.blue())
        embed.set_image(url="attachment://pokemon.png")
        embed.set_footer(text="Attempts remaining: 3")

        view = PokemonGuessView(pokemon_data, ctx.author)
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

                # Exact match required for the guess
                if guess.content.lower() == pokemon_name.lower():
                    embed = discord.Embed(
                        title="**Who's That Pokémon?**",
                        description=
                        f"Correct! The Pokémon was: {pokemon_name.title()}!",
                        color=discord.Color.green())
                    embed.set_image(url=pokemon_image)

                    new_view = discord.ui.View()
                    new_view.add_item(
                        SeePokedexButton(pokemon_data, ctx.author))
                    await message.edit(embed=embed,
                                       attachments=[],
                                       view=new_view)
                    break

                view.attempts -= 1
                if view.attempts > 0:
                    embed.set_footer(
                        text=f"Attempts remaining: {view.attempts}")
                    await message.edit(embed=embed)
                else:
                    embed = discord.Embed(
                        title="**Who's That Pokémon?**",
                        description=
                        f"Game Over! The Pokémon was: {pokemon_name.title()}!",
                        color=discord.Color.red())
                    embed.set_image(url=pokemon_image)

                    new_view = discord.ui.View()
                    new_view.add_item(
                        SeePokedexButton(pokemon_data, ctx.author))
                    await message.edit(embed=embed,
                                       attachments=[],
                                       view=new_view)

            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="**Who's That Pokémon?**",
                    description=
                    f"You took too long to answer... The Pokémon was: {pokemon_name.title()}!",
                    color=discord.Color.red())
                embed.set_image(url=pokemon_image)

                new_view = discord.ui.View()
                new_view.add_item(SeePokedexButton(pokemon_data, ctx.author))
                await message.edit(embed=embed, attachments=[], view=new_view)
                break

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
            img = img.convert('RGBA')
            pixels = img.load()
            width, height = img.size
            for x in range(width):
                for y in range(height):
                    r, g, b, a = pixels[x, y]
                    if a > 0:
                        pixels[x, y] = (0, 0, 0, 255)

            output = BytesIO()
            img.save(output, format='PNG')
            output.seek(0)
            return output


async def setup(bot: commands.Bot):
    await bot.add_cog(Pokemon(bot))
