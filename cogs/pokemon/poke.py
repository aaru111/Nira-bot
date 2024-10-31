from typing import Optional, List, Union, Tuple, Dict
import discord
from discord.ext import commands
import aiohttp
import random
from io import BytesIO
from PIL import Image
import asyncio
from difflib import get_close_matches
from discord import app_commands
from colorthief import ColorThief

from .modules.pokemod import *


class Pokemon(commands.Cog):
    TYPE_COLORS = {
        "normal": discord.Color.light_grey(),
        "fire": discord.Color.red(),
        "water": discord.Color.blue(),
        "electric": discord.Color.gold(),
        "grass": discord.Color.green(),
        "ice": discord.Color.teal(),
        "fighting": discord.Color.dark_red(),
        "poison": discord.Color.purple(),
        "ground": discord.Color.dark_gold(),
        "flying": discord.Color.blue(),
        "psychic": discord.Color.magenta(),
        "bug": discord.Color.dark_green(),
        "rock": discord.Color.dark_grey(),
        "ghost": discord.Color.dark_purple(),
        "dragon": discord.Color.dark_blue(),
        "dark": discord.Color.darker_grey(),
        "steel": discord.Color.greyple(),
        "fairy": discord.Color.pink()
    }

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.pokeapi_url: str = "https://pokeapi.co/api/v2"
        self.session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self.session:
            await self.session.close()

    async def find_closest_match(self, name: str,
                                 category: str) -> Optional[str]:
        if category == "pokemon":
            cache = self._pokemon_names_cache
        elif category == "item":
            cache = self._items_cache
        elif category == "ability":
            cache = self._abilities_cache
        elif category == "berry":
            cache = self._berries_cache
        elif category == "move":
            cache = self._moves_cache
        else:
            return None

        matches = get_close_matches(name.lower(),
                                    [item[0].lower() for item in cache],
                                    n=1,
                                    cutoff=0.6)
        return matches[0] if matches else None

    async def pokemon_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> List[app_commands.Choice[str]]:
        if not current:
            return []

        normalized_current: str = current.replace(" ", "-").lower()

        if not hasattr(self, '_pokemon_names_cache'):
            await self.cache_pokemon_names()

        if not hasattr(self, '_items_cache'):
            await self.cache_items()

        if not hasattr(self, '_abilities_cache'):
            await self.cache_abilities()

        if not hasattr(self, '_berries_cache'):
            await self.cache_berries()

        if not hasattr(self, '_moves_cache'):
            await self.cache_moves()

        combined_cache: List[Tuple[str, str]] = (self._pokemon_names_cache +
                                                 self._items_cache +
                                                 self._abilities_cache +
                                                 self._berries_cache +
                                                 self._moves_cache)

        exact_matches: List[app_commands.Choice[str]] = [
            app_commands.Choice(name=f"{name} ({category})", value=name)
            for name, category in combined_cache
            if normalized_current in name.replace(" ", "-").lower()
        ]
        if exact_matches:
            return exact_matches[:25]

        cache_names: List[str] = [
            name.replace(" ", "-").lower() for name, _ in combined_cache
        ]
        close_matches: List[str] = get_close_matches(normalized_current,
                                                     cache_names,
                                                     n=25,
                                                     cutoff=0.4)
        return [
            app_commands.Choice(name=f"{name} ({category})", value=name)
            for name, category in combined_cache
            if name.replace(" ", "-").lower() in close_matches
        ]

    async def cache_pokemon_names(self) -> None:
        async with self.session.get(
                f"{self.pokeapi_url}/pokemon?limit=10277") as resp:
            data: Dict[str, Union[List[Dict[str, str]],
                                  str]] = await resp.json()
            base_names: set = {pokemon['name'] for pokemon in data['results']}

        async with self.session.get(
                f"{self.pokeapi_url}/pokemon-form?limit=10448") as resp:
            form_data: Dict[str, Union[List[Dict[str, str]],
                                       str]] = await resp.json()
            form_names: set = {form['name'] for form in form_data['results']}

        self._pokemon_names_cache: List[Tuple[str, str]] = [
            (name, "pokemon") for name in base_names | form_names
        ]

    async def cache_items(self) -> None:
        async with self.session.get(
                f"{self.pokeapi_url}/item?limit=10002") as resp:
            item_data: Dict[str, Union[List[Dict[str, str]],
                                       str]] = await resp.json()
            self._items_cache: List[Tuple[str, str]] = [
                (item['name'], "item") for item in item_data['results']
            ]

    async def cache_abilities(self) -> None:
        async with self.session.get(
                f"{self.pokeapi_url}/ability?limit=10060") as resp:
            ability_data: Dict[str, Union[List[Dict[str, str]],
                                          str]] = await resp.json()
            self._abilities_cache: List[Tuple[str, str]] = [
                (ability['name'], "ability")
                for ability in ability_data['results']
            ]

    async def cache_berries(self) -> None:
        async with self.session.get(
                f"{self.pokeapi_url}/berry?limit=70") as resp:
            berry_data: Dict[str, Union[List[Dict[str, str]],
                                        str]] = await resp.json()
            self._berries_cache: List[Tuple[str, str]] = [
                (berry['name'], "berry") for berry in berry_data['results']
            ]

    async def cache_moves(self) -> None:
        async with self.session.get(
                f"{self.pokeapi_url}/move?limit=10018") as resp:
            move_data: Dict[str, Union[List[Dict[str, str]],
                                       str]] = await resp.json()
            self._moves_cache: List[Tuple[str, str]] = [
                (move['name'], "move") for move in move_data['results']
            ]

    async def find_closest_pokemon(self, pokemon_name: str) -> Optional[str]:
        if not hasattr(self, '_pokemon_names_cache'):
            await self.cache_pokemon_names()

        matches: List[str] = get_close_matches(
            pokemon_name.lower(),
            [name for name, _ in self._pokemon_names_cache],
            n=1,
            cutoff=0.6)
        return matches[0] if matches else None

    async def get_embed_color_from_sprite(self, url: str) -> discord.Color:
        """
        Fetches the dominant color from an image URL to set the embed color.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        color_thief = ColorThief(BytesIO(image_data))
                        dominant_color = color_thief.get_color(quality=1)
                        return discord.Color.from_rgb(*dominant_color)
        except Exception as e:
            print(f"Failed to fetch color: {e}")
            return discord.Color.default()

    def get_type_color(self, type_name: str) -> discord.Color:
        """
        Returns a discord.Color based on the Pokémon type.
        """
        return self.TYPE_COLORS.get(type_name.lower(), discord.Color.default())

    @commands.hybrid_command(
        name="pokedex",
        aliases=["pd", "dex"],
        description=
        "Look up detailed information about a Pokémon, item, ability, berry, or move in the Pokédex",
        brief="Search the Pokédex",
        help="""
                     Search for a Pokémon, item, ability, berry, or move in the Pokédex and view detailed information.
                     Usage: !pokedex <name>
                     Example: !pokedex flamethrower
                     """)
    @app_commands.describe(
        pokemon_name=
        "The name or number of the Pokémon, item, ability, berry, or move to look up"
    )
    @app_commands.autocomplete(pokemon_name=pokemon_autocomplete)
    async def pokedex(self, ctx: commands.Context, *,
                      pokemon_name: str) -> None:
        is_interaction: bool = isinstance(ctx, discord.Interaction)

        if is_interaction:
            await ctx.response.defer()
        else:
            await ctx.typing()

        # Ensure all caches are initialized
        if not hasattr(self, '_pokemon_names_cache'):
            await self.cache_pokemon_names()
        if not hasattr(self, '_items_cache'):
            await self.cache_items()
        if not hasattr(self, '_abilities_cache'):
            await self.cache_abilities()
        if not hasattr(self, '_berries_cache'):
            await self.cache_berries()
        if not hasattr(self, '_moves_cache'):
            await self.cache_moves()

        normalized_name: str = pokemon_name.replace(" ", "-").lower()

        categories = ["pokemon", "item", "ability", "berry", "move"]

        for category in categories:
            closest_match = await self.find_closest_match(
                normalized_name, category)
            if closest_match:
                normalized_name = closest_match
                break

        try:
            async with self.session.get(
                    f"{self.pokeapi_url}/pokemon/{normalized_name}") as resp:
                if resp.status == 200:
                    pokemon_data: Dict[str, Union[Dict[str, Union[str,
                                                                  List[Dict]]],
                                                  str]] = await resp.json()
                    view = PokemonInfoView(pokemon_data)
                    embed: discord.Embed = await view.create_main_embed()
                    embed.set_thumbnail(
                        url=pokemon_data['sprites']['versions']['generation-v']
                        ['black-white']['animated']['front_default']
                        or pokemon_data['sprites']['other']['official-artwork']
                        ['front_default'])

                    if is_interaction:
                        await ctx.followup.send(embed=embed, view=view)
                    else:
                        await ctx.send(embed=embed, view=view)
                    return

            async with self.session.get(
                    f"{self.pokeapi_url}/item/{normalized_name}") as resp:
                if resp.status == 200:
                    item_data: Dict[str, Union[str, List[Dict[str, Union[
                        str, int]]]]] = await resp.json()
                    sprite_url = item_data['sprites']['default']
                    embed_color = await self.get_embed_color_from_sprite(
                        sprite_url)
                    embed = discord.Embed(
                        title=f"{item_data['name'].title()}",
                        description=next(
                            (entry['effect']
                             for entry in item_data['effect_entries']
                             if entry['language']['name'] == 'en'),
                            "No description available"),
                        color=embed_color)
                    embed.set_thumbnail(url=sprite_url)

                    if is_interaction:
                        await ctx.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                    return

            async with self.session.get(
                    f"{self.pokeapi_url}/ability/{normalized_name}") as resp:
                if resp.status == 200:
                    ability_data: Dict[str,
                                       Union[str,
                                             List[Dict]]] = await resp.json()
                    description: str = next(
                        (entry['effect']
                         for entry in ability_data['effect_entries']
                         if entry['language']['name'] == 'en'),
                        "No description available")
                    pokemon_with_ability: List[str] = [
                        pokemon['pokemon']['name'].title()
                        for pokemon in ability_data['pokemon'][:10]
                    ]
                    pokemon_text: str = ", ".join(pokemon_with_ability) + (
                        "..." if len(ability_data['pokemon']) > 10 else "")
                    sprite_url = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/ability-capsule.png"
                    embed_color = await self.get_embed_color_from_sprite(
                        sprite_url)
                    embed = discord.Embed(
                        title=f"{ability_data['name'].title()} Ability",
                        description=description,
                        color=embed_color)
                    embed.add_field(name="Pokémon with this Ability",
                                    value=pokemon_text,
                                    inline=False)
                    embed.set_thumbnail(url=sprite_url)

                    if is_interaction:
                        await ctx.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                    return

            async with self.session.get(
                    f"{self.pokeapi_url}/berry/{normalized_name}") as resp:
                if resp.status == 200:
                    berry_data: Dict[str, Union[str, int]] = await resp.json()
                    berry_name: str = berry_data['name'].title()
                    sprite_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/{berry_data['name']}-berry.png"
                    embed_color = await self.get_embed_color_from_sprite(
                        sprite_url)
                    embed = discord.Embed(
                        title=f"{berry_name} Berry",
                        description=
                        f"Size: {berry_data['size']} | Growth time: {berry_data['growth_time']}",
                        color=embed_color)
                    embed.set_thumbnail(url=sprite_url)

                    if is_interaction:
                        await ctx.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                    return

            async with self.session.get(
                    f"{self.pokeapi_url}/move/{normalized_name}") as resp:
                if resp.status == 200:
                    move_data: Dict[str,
                                    Union[str, int,
                                          List[Dict]]] = await resp.json()
                    description: str = next(
                        (entry['effect']
                         for entry in move_data['effect_entries']
                         if entry['language']['name'] == 'en'),
                        "No description available")
                    power: Union[str, int] = move_data['power'] or "N/A"
                    pp: int = move_data['pp']
                    move_type: str = move_data['type']['name'].title()
                    damage_class: str = move_data['damage_class'][
                        'name'].title()
                    type_color = self.get_type_color(move_data['type']['name'])
                    embed = discord.Embed(
                        title=f"{move_data['name'].title()} Move",
                        description=description,
                        color=type_color)
                    embed.add_field(name="Power", value=power, inline=True)
                    embed.add_field(name="PP", value=pp, inline=True)
                    embed.add_field(name="Type", value=move_type, inline=True)
                    embed.add_field(name="Damage Class",
                                    value=damage_class,
                                    inline=True)
                    embed.set_thumbnail(
                        url=
                        "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/tm.png"
                    )

                    if is_interaction:
                        await ctx.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                    return

            if is_interaction:
                await ctx.followup.send(
                    f"No results found for '{pokemon_name}'")
            else:
                await ctx.send(f"No results found for '{pokemon_name}'")

        except Exception as e:
            if is_interaction:
                await ctx.followup.send(f"An error occurred: {str(e)}")
            else:
                await ctx.send(f"An error occurred: {str(e)}")

    @commands.hybrid_command(name="wtp",
                             aliases=["whosthat", "whosthatpokemon"],
                             description="Play a game of Who's That Pokémon?",
                             brief="Play Who's That Pokémon?")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
    async def wtp(self, ctx: commands.Context) -> None:
        pokemon_data: Dict[str, Union[str,
                                      Dict]] = await self.get_random_pokemon()
        pokemon_name: str = pokemon_data['name']
        pokemon_image: str = pokemon_data['sprites']['other'][
            'official-artwork']['front_default']

        if not pokemon_image:
            await ctx.send(
                "Sorry, couldn't load Pokémon image. Please try again!")
            return

        silhouette: BytesIO = await self.create_silhouette(pokemon_image)

        embed = discord.Embed(title="**Who's That Pokémon?**",
                              description="Can you guess who this Pokémon is?",
                              color=discord.Color.blue())
        embed.set_image(url="attachment://pokemon.png")
        embed.set_footer(text="Attempts remaining: 3")

        view = PokemonGuessView(pokemon_data, ctx.author)
        message: discord.Message = await ctx.send(embed=embed,
                                                  file=discord.File(
                                                      silhouette,
                                                      filename="pokemon.png"),
                                                  view=view)

        await view.wait()

        def check_guess(m: discord.Message) -> bool:
            return m.author == ctx.author and m.channel == ctx.channel

        while view.attempts > 0:
            try:
                guess: discord.Message = await self.bot.wait_for(
                    'message', timeout=25.0, check=check_guess)

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

    async def get_random_pokemon(self) -> Dict[str, Union[str, Dict]]:
        async with self.session.get(
                f"{self.pokeapi_url}/pokemon?limit=10277") as resp:
            data: Dict[str, Union[List[Dict[str, str]],
                                  str]] = await resp.json()
            pokemon: Dict[str, str] = random.choice(data['results'])

        async with self.session.get(pokemon['url']) as resp:
            return await resp.json()

    async def create_silhouette(self, image_url: str) -> BytesIO:
        async with self.session.get(image_url) as resp:
            image_data: bytes = await resp.read()

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pokemon(bot))
