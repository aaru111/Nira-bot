import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select
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

    @app_commands.command(
        name='set_deletion_delay',
        description='Set the delay for command message deletion')
    async def set_deletion_delay(self, interaction: discord.Interaction,
                                 delay: int):
        guild_config = self.get_guild_config(interaction.guild.id)
        guild_config['delay'] = delay
        save_config(self.config)
        await interaction.response.send_message(
            f"Command message deletion delay set to {delay} seconds.",
            ephemeral=True)

    @app_commands.command(
        name='add_deletion_command',
        description='Add a command to the auto-deletion list')
    async def add_deletion_command(self, interaction: discord.Interaction,
                                   command_name: str):
        guild_config = self.get_guild_config(interaction.guild.id)
        command_name = command_name.lower()
        if command_name not in guild_config['commands']:
            guild_config['commands'].append(command_name)
            save_config(self.config)
            await interaction.response.send_message(
                f"Command '{command_name}' added to the auto-deletion list.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                f"Command '{command_name}' is already in the auto-deletion list.",
                ephemeral=True)

    @app_commands.command(
        name='remove_deletion_command',
        description='Remove a command from the auto-deletion list')
    async def remove_deletion_command(self, interaction: discord.Interaction,
                                      command_name: str):
        guild_config = self.get_guild_config(interaction.guild.id)
        command_name = command_name.lower()
        if command_name in guild_config['commands']:
            guild_config['commands'].remove(command_name)
            save_config(self.config)
            await interaction.response.send_message(
                f"Command '{command_name}' removed from the auto-deletion list.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                f"Command '{command_name}' is not in the auto-deletion list.",
                ephemeral=True)

    @app_commands.command(
        name='add_deletion_category',
        description='Add a category to the auto-deletion list')
    async def add_deletion_category(self, interaction: discord.Interaction,
                                    category_name: str):
        guild_config = self.get_guild_config(interaction.guild.id)
        category_name = category_name.lower()
        if category_name not in guild_config['categories']:
            guild_config['categories'].append(category_name)
            save_config(self.config)
            await interaction.response.send_message(
                f"Category '{category_name}' added to the auto-deletion list.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                f"Category '{category_name}' is already in the auto-deletion list.",
                ephemeral=True)

    @app_commands.command(
        name='remove_deletion_category',
        description='Remove a category from the auto-deletion list')
    async def remove_deletion_category(self, interaction: discord.Interaction,
                                       category_name: str):
        guild_config = self.get_guild_config(interaction.guild.id)
        category_name = category_name.lower()
        if category_name in guild_config['categories']:
            guild_config['categories'].remove(category_name)
            save_config(self.config)
            await interaction.response.send_message(
                f"Category '{category_name}' removed from the auto-deletion list.",
                ephemeral=True)

    @app_commands.command(
        name='toggle_deletion',
        description='Toggle command message auto-deletion on or off')
    async def toggle_deletion(self, interaction: discord.Interaction):
        guild_config = self.get_guild_config(interaction.guild.id)
        if guild_config['enabled']:
            guild_config['enabled'] = False
            guild_config['commands'].clear()
            guild_config['categories'].clear()
            status = "disabled"
        else:
            guild_config['enabled'] = True
            status = "enabled"
        save_config(self.config)
        await interaction.response.send_message(
            f"Command message auto-deletion has been {status}.",
            ephemeral=True)

    @app_commands.command(name='show_deletion_setup',
                          description='Show the current auto-deletion setup')
    async def show_deletion_setup(self, interaction: discord.Interaction):
        guild_config = self.get_guild_config(interaction.guild.id)
        enabled_status = "enabled" if guild_config['enabled'] else "disabled"
        commands_list = ', '.join(
            guild_config['commands']) if guild_config['commands'] else 'None'
        categories_list = ', '.join(guild_config['categories']
                                    ) if guild_config['categories'] else 'None'

        response = (f"Auto-Deletion Status: {enabled_status}\n"
                    f"Deletion Delay: {guild_config['delay']} seconds\n"
                    f"Commands in Auto-Deletion List: {commands_list}\n"
                    f"Categories in Auto-Deletion List: {categories_list}")
        await interaction.response.send_message(response, ephemeral=True)

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

    @commands.command(name='deletion_setup')
    async def deletion_setup(self, ctx: commands.Context):
        # Create a view with a dropdown for selecting commands and categories
        view = DeletionSetupView(self.bot, ctx.guild.id)
        embed = discord.Embed(
            title="Auto-Deletion Setup Wizard",
            description=
            ("Select the commands and categories you want to set up for auto-deletion.\n\n"
             "To add single commands, use `/add_deletion_command`.\n"
             "To add single categories, use `/add_deletion_category`."),
            color=discord.Color.blue())
        await ctx.send(embed=embed, view=view)


class DeletionSetupView(View):

    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.add_item(DeletionCommandSelect(bot, guild_id))
        self.add_item(DeletionCategorySelect(bot, guild_id))


class DeletionCommandSelect(Select):

    def __init__(self, bot: commands.Bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label=cmd.name, value=cmd.name)
            for cmd in bot.commands
        ]
        super().__init__(placeholder='Select commands to auto-delete...',
                         min_values=1,
                         max_values=len(options),
                         options=options)

    async def callback(self, interaction: discord.Interaction):
        guild_config = self.bot.get_cog('CommandDeletion').get_guild_config(
            self.guild_id)
        for value in self.values:
            command_name = value.lower()
            if command_name not in guild_config['commands']:
                guild_config['commands'].append(command_name)
        save_config(self.bot.get_cog('CommandDeletion').config)
        await interaction.response.send_message(
            "Commands have been updated for auto-deletion.", ephemeral=True)


class DeletionCategorySelect(Select):

    def __init__(self, bot: commands.Bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        categories = {cmd.cog_name for cmd in bot.commands if cmd.cog_name}
        options = [
            discord.SelectOption(label=cat, value=cat) for cat in categories
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


# Function to set up the command deletion cog
async def setup(bot: commands.Bot):
    await bot.add_cog(CommandDeletion(bot))
