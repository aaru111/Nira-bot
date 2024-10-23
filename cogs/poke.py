from typing import Optional, Dict, List
import discord
from discord.ext import commands
import aiohttp
import random
from io import BytesIO
from PIL import Image
import asyncio
from discord.ui import View


class PokemonInfoSelect(discord.ui.Select):

    def __init__(self, pokemon_data: Dict):
        options = [
            discord.SelectOption(label="Main Info", value="main", emoji="📋"),
            discord.SelectOption(label="Stats", value="stats", emoji="📊"),
            discord.SelectOption(label="Moves", value="moves", emoji="⚔️"),
            discord.SelectOption(label="Locations",
                                 value="locations",
                                 emoji="🗺️")
        ]
        super().__init__(placeholder="Select information to view...",
                         options=options)
        self.pokemon_data = pokemon_data

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if self.values[0] == "main":
            embed = await view.create_main_embed()
        elif self.values[0] == "stats":
            embed = await view.create_stats_embed()
        elif self.values[0] == "moves":
            embed = await view.create_moves_embed()
        elif self.values[0] == "locations":
            embed = await view.create_locations_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PokemonInfoView(discord.ui.View):

    def __init__(self, pokemon_data: Dict, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.pokemon_data = pokemon_data
        self.add_item(PokemonInfoSelect(pokemon_data))
        self.current_page = "main"

    async def create_stats_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{self.pokemon_data['name'].title()} - Base Stats",
            color=discord.Color.blue())
        embed.set_thumbnail(url=self.pokemon_data['sprites']['other']
                            ['official-artwork']['front_default'])

        stats_text = ""
        max_stat = max(stat['base_stat']
                       for stat in self.pokemon_data['stats'])

        for stat in self.pokemon_data['stats']:
            stat_name = stat['stat']['name'].replace('-', ' ').title()
            stat_value = stat['base_stat']
            bar_length = int((stat_value / max_stat) * 15)
            bar = "█" * bar_length + "░" * (15 - bar_length)
            stats_text += f"{stat_name:<15}: {stat_value:>3} {bar}\n"

        embed.add_field(name="📊 Base Stats",
                        value=f"```\n{stats_text}```",
                        inline=False)

        total = sum(stat['base_stat'] for stat in self.pokemon_data['stats'])
        embed.add_field(name="Total", value=str(total), inline=False)

        return embed

    async def create_moves_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{self.pokemon_data['name'].title()} - Moves",
            color=discord.Color.blue())
        embed.set_thumbnail(url=self.pokemon_data['sprites']['other']
                            ['official-artwork']['front_default'])

        level_up_moves = []
        tm_moves = []
        egg_moves = []

        for move in self.pokemon_data['moves']:
            for detail in move['version_group_details']:
                if detail['move_learn_method']['name'] == 'level-up':
                    level_up_moves.append(
                        f"{detail['level_learned_at']}: {move['move']['name'].replace('-', ' ').title()}"
                    )
                elif detail['move_learn_method']['name'] == 'machine':
                    tm_moves.append(move['move']['name'].replace('-',
                                                                 ' ').title())
                elif detail['move_learn_method']['name'] == 'egg':
                    egg_moves.append(move['move']['name'].replace('-',
                                                                  ' ').title())
                break

        if level_up_moves:
            level_up_moves.sort(key=lambda x: int(x.split(':')[0]))
            embed.add_field(
                name="Level Up Moves",
                value="\n".join(level_up_moves[:15]) + "\n..."
                if len(level_up_moves) > 15 else "\n".join(level_up_moves),
                inline=False)

        if tm_moves:
            embed.add_field(
                name="TM/TR Moves",
                value=", ".join(tm_moves[:15]) +
                "..." if len(tm_moves) > 15 else ", ".join(tm_moves),
                inline=False)

        if egg_moves:
            embed.add_field(
                name="Egg Moves",
                value=", ".join(egg_moves[:15]) +
                "..." if len(egg_moves) > 15 else ", ".join(egg_moves),
                inline=False)

        return embed

    async def create_locations_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{self.pokemon_data['name'].title()} - Locations",
            color=discord.Color.blue())
        embed.set_thumbnail(url=self.pokemon_data['sprites']['other']
                            ['official-artwork']['front_default'])

        async with aiohttp.ClientSession() as session:
            async with session.get(
                    f"https://pokeapi.co/api/v2/pokemon/{self.pokemon_data['id']}/encounters"
            ) as resp:
                locations = await resp.json()

        if locations:
            location_text = ""
            for location in locations[:15]:
                location_text += f"• {location['location_area']['name'].replace('-', ' ').title()}\n"
            if len(locations) > 15:
                location_text += "..."
            embed.add_field(name="Found In",
                            value=location_text or "No known locations",
                            inline=False)
        else:
            embed.add_field(name="Found In",
                            value="No known locations",
                            inline=False)

        return embed

    async def create_main_embed(self) -> discord.Embed:
        species_url = self.pokemon_data['species']['url']
        async with aiohttp.ClientSession() as session:
            async with session.get(species_url) as resp:
                species_data = await resp.json()

            async with session.get(
                    species_data['evolution_chain']['url']) as resp:
                evo_data = await resp.json()

        gen_num = species_data['generation']['name'].upper().replace(
            'GENERATION-', 'Gen ')

        embed = discord.Embed(
            title=
            f"{gen_num} - {self.pokemon_data['name'].title()} #{self.pokemon_data['id']}",
            color=discord.Color.blue())
        embed.set_thumbnail(url=self.pokemon_data['sprites']['other']
                            ['official-artwork']['front_default'])

        def get_evo_details(evolution_details):
            if not evolution_details:
                return ""
            details = evolution_details[0]
            if details.get('item'):
                return f"Evolves using {details['item']['name'].replace('-', ' ').title()}"
            elif details.get('min_level'):
                return f"Evolves at level {details['min_level']}"
            elif details.get('trigger'):
                return f"Evolves by {details['trigger']['name'].replace('-', ' ').title()}"
            return ""

        def get_evolution_chain(chain, target_name, prev_chain=None):
            current_name = chain['species']['name']
            if current_name == target_name:
                next_evos = []
                evo_details = []
                for evo in chain['evolves_to']:
                    next_chain = []
                    build_next_chain(evo, next_chain)
                    next_evos.append(" > ".join(p.title() for p in next_chain))
                    evo_details.append(
                        get_evo_details(evo['evolution_details']))
                return prev_chain, next_evos, evo_details

            for evolution in chain['evolves_to']:
                new_prev = prev_chain + [current_name] if prev_chain else [
                    current_name
                ]
                result = get_evolution_chain(evolution, target_name, new_prev)
                if result:
                    return result
            return None

        def build_next_chain(chain, result):
            result.append(chain['species']['name'])
            if chain['evolves_to']:
                build_next_chain(chain['evolves_to'][0], result)

        evolution_data = get_evolution_chain(evo_data['chain'],
                                             self.pokemon_data['name'].lower())

        if evolution_data:
            prev_chain, next_evos, evo_details = evolution_data

            if prev_chain:
                prev_evo_text = " > ".join(name.title() for name in prev_chain)
                embed.add_field(name="Previous Evolution(s)",
                                value=prev_evo_text,
                                inline=True)

            if next_evos:
                embed.add_field(name="Next Evolution(s)",
                                value="\n".join(next_evos),
                                inline=True)

                if any(evo_details):
                    embed.add_field(name="How to Evolve",
                                    value="\n".join(detail
                                                    for detail in evo_details
                                                    if detail),
                                    inline=False)

        type_effectiveness = await self.calculate_type_effectiveness(
            self.pokemon_data['types'])

        weaknesses = [
            f"-# {t} (x{multiplier})"
            for t, multiplier in type_effectiveness.items() if multiplier > 1
        ]
        if weaknesses:
            embed.add_field(name="Weaknesses",
                            value="\n".join(weaknesses),
                            inline=True)

        resistances = [
            f"-# {t} (x{multiplier})"
            for t, multiplier in type_effectiveness.items()
            if 0 < multiplier < 1
        ]
        if resistances:
            embed.add_field(name="Resistances",
                            value="\n".join(resistances),
                            inline=True)

        immunities = [
            f"-# {t}" for t, multiplier in type_effectiveness.items()
            if multiplier == 0
        ]
        embed.add_field(
            name="Immunities",
            value="\n".join(immunities) if immunities else "-# None",
            inline=True)

        pokedex_entries = [
            entry for entry in species_data['flavor_text_entries']
            if entry['language']['name'] == 'en'
        ]
        if pokedex_entries:
            description = pokedex_entries[0]['flavor_text'].replace(
                '\n', ' ').replace('\f', ' ')
            embed.add_field(name="Description",
                            value=description,
                            inline=False)

        return embed

    async def calculate_type_effectiveness(
            self, types: List[Dict]) -> Dict[str, float]:
        type_chart = {
            'normal': {
                'weakness': ['fighting'],
                'resistance': [],
                'immunity': ['ghost']
            },
            'fighting': {
                'weakness': ['flying', 'psychic', 'fairy'],
                'resistance': ['rock', 'bug', 'dark'],
                'immunity': []
            },
        }

        effectiveness = {}
        pokemon_types = [t['type']['name'] for t in types]

        async with aiohttp.ClientSession() as session:
            for type_name in pokemon_types:
                async with session.get(
                        f"https://pokeapi.co/api/v2/type/{type_name}") as resp:
                    type_data = await resp.json()

                    for relation in type_data['damage_relations'][
                            'double_damage_from']:
                        effectiveness[relation['name']] = effectiveness.get(
                            relation['name'], 1) * 2

                    for relation in type_data['damage_relations'][
                            'half_damage_from']:
                        effectiveness[relation['name']] = effectiveness.get(
                            relation['name'], 1) * 0.5

                    for relation in type_data['damage_relations'][
                            'no_damage_from']:
                        effectiveness[relation['name']] = 0

        return {
            k: v
            for k, v in sorted(effectiveness.items(),
                               key=lambda item: (-item[1], item[0]))
        }


class GiveUpButton(discord.ui.Button):

    def __init__(self):
        super().__init__(label="Give Up", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.view.original_author:
            await interaction.response.send_message("This isn't your game!",
                                                    ephemeral=True)
            return

        embed = discord.Embed(
            title="**Who's That Pokémon?**",
            description=
            f"You gave up... The Pokémon was: {self.view.pokemon_name.title()}!",
            color=discord.Color.red())
        embed.set_image(url=self.view.pokemon_image)

        view = View()
        # Pass required data to the SeePokedexButton
        view.add_item(
            SeePokedexButton(self.view.pokemon_data,
                             self.view.original_author))
        await interaction.response.edit_message(embed=embed,
                                                attachments=[],
                                                view=view)
        self.view.stop()


class SeePokedexButton(discord.ui.Button):

    def __init__(self, pokemon_data: Dict, original_author: discord.Member):
        super().__init__(label="See Pokédex Entry",
                         style=discord.ButtonStyle.primary)
        self.pokemon_data = pokemon_data
        self.original_author = original_author

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.original_author:
            await interaction.response.send_message("This isn't your game!",
                                                    ephemeral=True)
            return

        view = PokemonInfoView(self.pokemon_data)
        embed = await view.create_main_embed()
        await interaction.response.send_message(embed=embed, view=view)


class PokemonGuessView(discord.ui.View):

    def __init__(self,
                 pokemon_data: Dict,
                 original_author: discord.Member,
                 timeout: float = 25.0):
        super().__init__(timeout=timeout)
        self.pokemon_data = pokemon_data
        self.pokemon_name = pokemon_data['name'].lower()
        self.pokemon_image = pokemon_data['sprites']['other'][
            'official-artwork']['front_default']
        self.attempts = 3
        self.original_author = original_author
        self.add_item(GiveUpButton())

    async def stop_game(self,
                        interaction: discord.Interaction,
                        gave_up: bool = False):
        self.stop()
        if gave_up:
            embed = discord.Embed(
                title="**Who's That Pokémon?**",
                description=
                f"You gave up... The Pokémon was: {self.pokemon_name.title()}!",
                color=discord.Color.red())

            async with aiohttp.ClientSession() as session:
                async with session.get(self.pokemon_image) as resp:
                    actual_image = BytesIO(await resp.read())

            view = View()
            # Pass required data to the SeePokedexButton
            view.add_item(
                SeePokedexButton(self.pokemon_data, self.original_author))
            await interaction.response.edit_message(
                embed=embed,
                attachments=[
                    discord.File(actual_image, filename="pokemon.png")
                ],
                view=view)


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

    @commands.command(name="pokedex", aliases=["dex"])
    async def pokedex(self, ctx: commands.Context, *, pokemon_name: str):
        """Look up detailed information about a Pokémon."""
        try:
            async with self.session.get(
                    f"{self.pokeapi_url}/pokemon/{pokemon_name.lower()}"
            ) as resp:
                if resp.status == 404:
                    await ctx.send(f"Pokémon '{pokemon_name}' not found!")
                    return
                pokemon_data = await resp.json()

            view = PokemonInfoView(pokemon_data)
            embed = await view.create_main_embed()
            await ctx.send(embed=embed, view=view)

        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command(name="whosthat", description="Play Who's That Pokémon?")
    async def whos_that_pokemon(self, ctx: commands.Context):
        """Start a game of Who's That Pokémon?"""
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

                if guess.content.lower() == pokemon_name.lower():
                    embed = discord.Embed(
                        title="**Who's That Pokémon?**",
                        description=
                        f"Correct! The Pokémon was: {pokemon_name.title()}!",
                        color=discord.Color.green())
                    embed.set_image(
                        url=pokemon_image
                    )  # Set the actual Pokémon image in the embed

                    new_view = View()
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
                    embed.set_image(
                        url=pokemon_image
                    )  # Set the actual Pokémon image in the embed

                    new_view = View()
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
                embed.set_image(url=pokemon_image
                                )  # Set the actual Pokémon image in the embed

                new_view = View()
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
