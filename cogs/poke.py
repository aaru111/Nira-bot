from typing import Optional, List
import discord
from discord.ext import commands
import aiohttp
import random
from io import BytesIO
from PIL import Image
import asyncio
from difflib import get_close_matches
from discord import app_commands

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

        # Normalize input by replacing spaces with hyphens
        normalized_current = current.replace(" ", "-").lower()

        # Check if caches for different categories exist
        if not hasattr(self, '_pokemon_names_cache'):
            async with self.session.get(
                    f"{self.pokeapi_url}/pokemon?limit=898") as resp:
                data = await resp.json()
                base_names = {pokemon['name'] for pokemon in data['results']}

            # Fetch Pokémon forms as well
            async with self.session.get(
                    f"{self.pokeapi_url}/pokemon-form?limit=2000") as resp:
                form_data = await resp.json()
                form_names = {form['name'] for form in form_data['results']}

            self._pokemon_names_cache = [(name, "pokemon")
                                         for name in base_names | form_names]

        if not hasattr(self, '_items_cache'):
            async with self.session.get(
                    f"{self.pokeapi_url}/item?limit=1000") as resp:
                item_data = await resp.json()
                self._items_cache = [(item['name'], "item")
                                     for item in item_data['results']]

        if not hasattr(self, '_abilities_cache'):
            async with self.session.get(
                    f"{self.pokeapi_url}/ability?limit=300") as resp:
                ability_data = await resp.json()
                self._abilities_cache = [(ability['name'], "ability")
                                         for ability in ability_data['results']
                                         ]

        if not hasattr(self, '_berries_cache'):
            async with self.session.get(
                    f"{self.pokeapi_url}/berry?limit=300") as resp:
                berry_data = await resp.json()
                self._berries_cache = [(berry['name'], "berry")
                                       for berry in berry_data['results']]

        if not hasattr(self, '_moves_cache'):
            async with self.session.get(
                    f"{self.pokeapi_url}/move?limit=1000") as resp:
                move_data = await resp.json()
                self._moves_cache = [(move['name'], "move")
                                     for move in move_data['results']]

        # Combine all categories for matching
        combined_cache = (self._pokemon_names_cache + self._items_cache +
                          self._abilities_cache + self._berries_cache +
                          self._moves_cache)

        # Perform normalized matching
        exact_matches = [
            app_commands.Choice(name=f"{name} ({category})", value=name)
            for name, category in combined_cache
            if normalized_current in name.replace(" ", "-").lower()
        ]
        if exact_matches:
            return exact_matches[:25]

        # Fallback to close matches if no exact matches are found
        cache_names = [
            name.replace(" ", "-").lower() for name, _ in combined_cache
        ]  # Normalized cache names
        close_matches = get_close_matches(normalized_current,
                                          cache_names,
                                          n=25,
                                          cutoff=0.4)
        return [
            app_commands.Choice(name=f"{name} ({category})", value=name)
            for name, category in combined_cache
            if name.replace(" ", "-").lower() in close_matches
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
        "Look up detailed information about a Pokémon, item, ability, berry, or move in the Pokédex",
        brief="Search the Pokédex",
        help=
        """Search for a Pokémon, item, ability, berry, or move in the Pokédex and view detailed information.
        Usage: !pokedex <name> Example: !pokedex flamethrower""")
    @app_commands.describe(
        pokemon_name=
        "The name or number of the Pokémon, item, ability, berry, or move to lookup"
    )
    @app_commands.autocomplete(pokemon_name=pokemon_autocomplete)
    async def pokedex(self, ctx: commands.Context, *, pokemon_name: str):
        """Lookup detailed information about a Pokémon, item, ability, berry, or move."""
        is_interaction = hasattr(ctx,
                                 'interaction') and ctx.interaction is not None

        # Normalize the input to match API format: replace spaces with hyphens
        normalized_name = pokemon_name.replace(" ", "-").lower()

        try:
            if is_interaction:
                await ctx.interaction.response.defer()

            # Attempt to fetch Pokémon data
            async with self.session.get(
                    f"{self.pokeapi_url}/pokemon/{normalized_name}") as resp:
                if resp.status == 200:
                    pokemon_data = await resp.json()
                    view = PokemonInfoView(pokemon_data)
                    embed = await view.create_main_embed()
                    embed.set_thumbnail(url=pokemon_data['sprites']['other']
                                        ['official-artwork']['front_default'])
                    if is_interaction:
                        await ctx.interaction.followup.send(embed=embed,
                                                            view=view)
                    else:
                        await ctx.send(embed=embed, view=view)
                    return

            # Attempt to fetch item data
            async with self.session.get(
                    f"{self.pokeapi_url}/item/{normalized_name}") as resp:
                if resp.status == 200:
                    item_data = await resp.json()
                    embed = discord.Embed(
                        title=f"{item_data['name'].title()}",
                        description=next(
                            (entry['effect']
                             for entry in item_data['effect_entries']
                             if entry['language']['name'] == 'en'),
                            "No description available"),
                        color=discord.Color.gold())
                    embed.set_thumbnail(
                        url=item_data['sprites']
                        ['default'])  # Assuming item has a default image
                    if is_interaction:
                        await ctx.interaction.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                    return

            # Attempt to fetch ability data
            async with self.session.get(
                    f"{self.pokeapi_url}/ability/{normalized_name}") as resp:
                if resp.status == 200:
                    ability_data = await resp.json()
                    description = next(
                        (entry['effect']
                         for entry in ability_data['effect_entries']
                         if entry['language']['name'] == 'en'),
                        "No description available")
                    pokemon_with_ability = [
                        pokemon['pokemon']['name'].title()
                        for pokemon in ability_data['pokemon'][:10]
                    ]
                    pokemon_text = ", ".join(pokemon_with_ability) + (
                        "..." if len(ability_data['pokemon']) > 10 else "")

                    embed = discord.Embed(
                        title=f"{ability_data['name'].title()} Ability",
                        description=description,
                        color=discord.Color.purple())
                    embed.add_field(name="Pokémon with this Ability",
                                    value=pokemon_text,
                                    inline=False)
                    embed.set_thumbnail(
                        url=
                        "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/ability-capsule.png"
                    )  # Example static image
                    if is_interaction:
                        await ctx.interaction.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                    return

            # Attempt to fetch berry data
            async with self.session.get(
                    f"{self.pokeapi_url}/berry/{normalized_name}") as resp:
                if resp.status == 200:
                    berry_data = await resp.json()
                    berry_name = berry_data['name'].title()
                    embed = discord.Embed(
                        title=f"{berry_name} Berry",
                        description=
                        f"Size: {berry_data['size']} | Growth time: {berry_data['growth_time']}",
                        color=discord.Color.red())
                    embed.set_thumbnail(
                        url=
                        f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/{berry_data['name']}-berry.png"
                    )
                    if is_interaction:
                        await ctx.interaction.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                    return

            # Attempt to fetch move data
            async with self.session.get(
                    f"{self.pokeapi_url}/move/{normalized_name}") as resp:
                if resp.status == 200:
                    move_data = await resp.json()
                    description = next(
                        (entry['effect']
                         for entry in move_data['effect_entries']
                         if entry['language']['name'] == 'en'),
                        "No description available")
                    power = move_data['power'] or "N/A"
                    pp = move_data['pp']
                    move_type = move_data['type']['name'].title()
                    damage_class = move_data['damage_class']['name'].title()

                    embed = discord.Embed(
                        title=f"{move_data['name'].title()} Move",
                        description=description,
                        color=discord.Color.blue())
                    embed.add_field(name="Power", value=power, inline=True)
                    embed.add_field(name="PP", value=pp, inline=True)
                    embed.add_field(name="Type", value=move_type, inline=True)
                    embed.add_field(name="Damage Class",
                                    value=damage_class,
                                    inline=True)
                    embed.set_thumbnail(
                        url=
                        "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/tm.png"
                    )  # Example static image
                    if is_interaction:
                        await ctx.interaction.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                    return

            # If no matches are found
            if is_interaction:
                await ctx.interaction.followup.send(
                    f"No results found for '{pokemon_name}'")
            else:
                await ctx.send(f"No results found for '{pokemon_name}'")

        except Exception as e:
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
