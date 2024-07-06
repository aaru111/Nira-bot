import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button
import json
from pathlib import Path

# Define the path to the configuration file
CONFIG_FILE = Path('delete_command_config.json')


# Function to load the configuration from the file
def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        CONFIG_FILE.touch()
        return {}


# Function to save the configuration to the file
def save_config(config: dict):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)


# Function to get default settings for a server
def get_default_settings() -> dict:
    return {
        "enabled": False,  # Disabled by default
        "delay": 3,
        "commands": [],
        "categories": []
    }


# Cog class to handle command deletion
class CommandDeletion(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = load_config()

    def cog_check(self, ctx):
        return ctx.author.id == self.bot.owner_id

    def get_guild_config(self, guild_id: int) -> dict:
        if str(guild_id) not in self.config:
            self.config[str(guild_id)] = get_default_settings()
            save_config(self.config)
        return self.config[str(guild_id)]

    @commands.hybrid_command(
        name='set_deletion_delay',
        description='Set the delay for command message deletion')
    async def set_deletion_delay(self, ctx: commands.Context, delay: int):
        await ctx.defer()
        guild_config = self.get_guild_config(ctx.guild.id)
        guild_config['delay'] = delay
        save_config(self.config)
        await ctx.send(
            f"Command message deletion delay set to {delay} seconds.",
            ephemeral=True)

    @commands.hybrid_command(
        name='add_deletion_command',
        description='Add a command to the auto-deletion list')
    async def add_deletion_command(self, ctx: commands.Context,
                                   command_name: str):
        await ctx.defer()
        guild_config = self.get_guild_config(ctx.guild.id)
        command_name = command_name.lower()
        if command_name not in guild_config['commands']:
            guild_config['commands'].append(command_name)
            save_config(self.config)
            await ctx.send(
                f"Command '{command_name}' added to the auto-deletion list.",
                ephemeral=True)
        else:
            await ctx.send(
                f"Command '{command_name}' is already in the auto-deletion list.",
                ephemeral=True)

    @commands.hybrid_command(
        name='remove_deletion_command',
        description='Remove a command from the auto-deletion list')
    async def remove_deletion_command(self, ctx: commands.Context,
                                      command_name: str):
        await ctx.defer()
        guild_config = self.get_guild_config(ctx.guild.id)
        command_name = command_name.lower()
        if command_name in guild_config['commands']:
            guild_config['commands'].remove(command_name)
            save_config(self.config)
            await ctx.send(
                f"Command '{command_name}' removed from the auto-deletion list.",
                ephemeral=True)
        else:
            await ctx.send(
                f"Command '{command_name}' is not in the auto-deletion list.",
                ephemeral=True)

    @commands.hybrid_command(
        name='add_deletion_category',
        description='Add a category to the auto-deletion list')
    async def add_deletion_category(self, ctx: commands.Context,
                                    category_name: str):
        await ctx.defer()
        guild_config = self.get_guild_config(ctx.guild.id)
        category_name = category_name.lower()
        if category_name not in guild_config['categories']:
            guild_config['categories'].append(category_name)
            save_config(self.config)
            await ctx.send(
                f"Category '{category_name}' added to the auto-deletion list.",
                ephemeral=True)
        else:
            await ctx.send(
                f"Category '{category_name}' is already in the auto-deletion list.",
                ephemeral=True)

    @commands.hybrid_command(
        name='remove_deletion_category',
        description='Remove a category from the auto-deletion list')
    async def remove_deletion_category(self, ctx: commands.Context,
                                       category_name: str):
        await ctx.defer()
        guild_config = self.get_guild_config(ctx.guild.id)
        category_name = category_name.lower()
        if category_name in guild_config['categories']:
            guild_config['categories'].remove(category_name)
            save_config(self.config)
            await ctx.send(
                f"Category '{category_name}' removed from the auto-deletion list.",
                ephemeral=True)

    @commands.hybrid_command(
        name='toggle_deletion',
        description='Toggle command message auto-deletion on or off')
    async def toggle_deletion(self, ctx: commands.Context):
        await ctx.defer()
        guild_config = self.get_guild_config(ctx.guild.id)
        if guild_config['enabled']:
            guild_config['enabled'] = False
            guild_config['commands'].clear()
            guild_config['categories'].clear()
            status = "disabled"
        else:
            guild_config['enabled'] = True
            status = "enabled"
        save_config(self.config)
        await ctx.send(f"Command message auto-deletion has been {status}.",
                       ephemeral=True)

    @commands.hybrid_command(
        name='show_deletion_setup',
        description='Show the current auto-deletion setup')
    async def show_deletion_setup(self, ctx: commands.Context):
        await ctx.defer()
        guild_config = self.get_guild_config(ctx.guild.id)
        enabled_status = "enabled" if guild_config['enabled'] else "disabled"
        commands_list = ', '.join(
            guild_config['commands']) if guild_config['commands'] else 'None'
        categories_list = ', '.join(guild_config['categories']
                                    ) if guild_config['categories'] else 'None'

        response = (f"Auto-Deletion Status: {enabled_status}\n"
                    f"Deletion Delay: {guild_config['delay']} seconds\n"
                    f"Commands in Auto-Deletion List: {commands_list}\n"
                    f"Categories in Auto-Deletion List: {categories_list}")
        await ctx.send(response, ephemeral=True)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        guild_config = self.get_guild_config(ctx.guild.id)
        if not guild_config['enabled']:
            return

        # Check if the command is in the deletion list
        if ctx.command and ctx.command.name.lower(
        ) in guild_config['commands']:
            await ctx.message.delete(delay=guild_config['delay'])
            return

        # Check if the command's cog is in the deletion list
        if ctx.command and ctx.command.cog and ctx.command.cog.qualified_name.lower(
        ) in guild_config['categories']:
            await ctx.message.delete(delay=guild_config['delay'])

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        if str(guild.id) not in self.config:
            self.config[str(guild.id)] = get_default_settings()
            save_config(self.config)

    @commands.hybrid_command(name='deletion_setup')
    async def deletion_setup(self, ctx: commands.Context):
        await ctx.defer()
        # Create a view with a dropdown for selecting categories
        view = DeletionSetupView(self.bot, ctx.guild.id)
        categories_count = len(view.children[0].options)
        embed = discord.Embed(
            title="Auto-Deletion Setup Wizard",
            description=
            ("Select the categories you want to set up for auto-deletion.\n\n"
             "To add single categories, use `/add_deletion_category`."),
            color=discord.Color.blue())
        embed.set_footer(
            text=f"Number of categories to choose from: {categories_count}")
        await ctx.send(embed=embed, view=view)


class DeletionSetupView(View):

    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.add_item(DeletionCategorySelect(bot, guild_id))
        self.add_item(ToggleAutoDeletionButton(bot, guild_id))


class DeletionCategorySelect(Select):

    def __init__(self, bot: commands.Bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        categories = {
            cmd.cog_name
            for cmd in bot.commands
            if cmd.cog_name and cmd.cog_name.lower() != 'sync' and cmd.cog_name
            .lower() != 'jishaku' and cmd.cog_name.lower() != 'commanddeletion'
        }
        emoji_dict = {
            'Admin': '🛡️',
            'Fun': '🎉',
            'Utility': '🔧',
            'Moderation': '🔨',
            'Music': '🎵',
            'Economy': '💰',
            # Add more categories and their corresponding emojis as needed
        }
        options = [
            discord.SelectOption(label=cat,
                                 value=cat,
                                 emoji=emoji_dict.get(cat, '❓'))
            for cat in categories
        ]
        super().__init__(placeholder='Select categories to auto-delete...',
                         min_values=1,
                         max_values=len(options),
                         options=options)

    async def callback(self, interaction: discord.Interaction):
        guild_config = self.bot.get_cog('CommandDeletion').get_guild_config(
            self.guild_id)
        for value in self.values:
            category_name = value.lower()
            if category_name not in guild_config['categories']:
                guild_config['categories'].append(category_name)
        save_config(self.bot.get_cog('CommandDeletion').config)
        await interaction.response.send_message(
            "Categories have been updated for auto-deletion.", ephemeral=True)


class ToggleAutoDeletionButton(Button):

    def __init__(self, bot: commands.Bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        super().__init__(label="Toggle Auto-Deletion",
                         style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        guild_config = self.bot.get_cog('CommandDeletion').get_guild_config(
            self.guild_id)
        if guild_config['enabled']:
            guild_config['enabled'] = False
            status = "disabled"
        else:
            guild_config['enabled'] = True
            status = "enabled"
        save_config(self.bot.get_cog('CommandDeletion').config)
        await interaction.response.send_message(
            f"Command message auto-deletion has been {status}.",
            ephemeral=True)


# Function to set up the command deletion cog
async def setup(bot: commands.Bot):
    await bot.add_cog(CommandDeletion(bot))
