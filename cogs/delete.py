import discord
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
from datetime import timedelta
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import aiohttp

# Define the path to the configuration file
CONFIG_FILE = Path('delete_command_config.json')
EMBED_COLOR = 0x2b2d31


def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        CONFIG_FILE.touch()
        return {}


def save_config(config: Dict[str, Any]) -> None:
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)


def get_default_settings() -> Dict[str, Any]:
    return {"enabled": False, "delay": 3, "commands": [], "categories": []}


class CommandDeletion(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.config = load_config()

    async def close(self) -> None:
        await self.session.close()

    def cog_check(self, ctx: commands.Context) -> bool:
        return ctx.author.id == self.bot.owner_id

    def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        if str(guild_id) not in self.config:
            self.config[str(guild_id)] = get_default_settings()
            save_config(self.config)
        return self.config[str(guild_id)]

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        guild_config = self.get_guild_config(ctx.guild.id)
        if not guild_config['enabled']:
            return
        if ctx.command and ctx.command.name.lower(
        ) in guild_config['commands']:
            await ctx.message.delete(delay=guild_config['delay'])

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        if str(guild.id) not in self.config:
            self.config[str(guild.id)] = get_default_settings()
            save_config(self.config)

    @commands.hybrid_command(name='deletion_setup')
    @discord.app_commands.guild_only()
    async def deletion_setup(self, ctx: commands.Context) -> None:
        await ctx.defer()
        guild_config = self.get_guild_config(ctx.guild.id)
        enabled_status = "enabled" if guild_config['enabled'] else "disabled"
        view = DeletionSetupView(self.bot, ctx.guild.id,
                                 guild_config['enabled'])
        embed = discord.Embed(
            title="Auto-Deletion Setup Wizard",
            description=
            (f"Current Status: **{enabled_status}**\n\n"
             "Select the type you want to set up for auto-deletion.\n\n"
             "**Disclaimer:** Disabling auto-deletion will clear all previously set commands and reset the delay."
             ),
            color=EMBED_COLOR)
        message = await ctx.send(embed=embed, view=view)
        view.message = message
        view.start_timeout()


class DeletionSetupView(View):

    def __init__(self, bot: commands.Bot, guild_id: int,
                 enabled: bool) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.enabled = enabled
        self.message: Optional[discord.Message] = None
        self.timeout_task: Optional[asyncio.Task] = None
        self.add_item(DeletionTypeSelect(bot, guild_id, enabled))
        self.add_item(ToggleAutoDeletionButton(bot, guild_id))
        self.add_item(SetDelayButton(bot, guild_id))
        self.add_item(ShowDeletionSetupButton(bot, guild_id))
        self.add_item(DeleteEmbedButton())

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        if self.timeout_task:
            self.timeout_task.cancel()
        self.start_timeout()
        return True

    def start_timeout(self) -> None:
        self.timeout_task = self.bot.loop.create_task(
            self.delete_after_timeout())

    async def delete_after_timeout(self) -> None:
        await discord.utils.sleep_until(discord.utils.utcnow() +
                                        timedelta(minutes=10))
        try:
            if self.message:
                await self.message.delete()
        except discord.NotFound:
            pass


class DeletionTypeSelect(Select):

    def __init__(self, bot: commands.Bot, guild_id: int,
                 enabled: bool) -> None:
        self.bot = bot
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Commands", value="commands"),
            discord.SelectOption(label="Categories", value="categories")
        ]
        super().__init__(placeholder='Select the type to set up...',
                         min_values=1,
                         max_values=1,
                         options=options)
        self.enabled = enabled

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "commands":
            view = DeletionCommandSelect(self.bot, self.guild_id)
        elif self.values[0] == "categories":
            view = DeletionCategorySelect(self.bot, self.guild_id)
        else:
            return

        embed = discord.Embed(
            title="Select Items for Auto-Deletion",
            description=
            f"Select the items to auto-delete for {self.values[0]}.",
            color=EMBED_COLOR)
        await interaction.response.edit_message(embed=embed, view=view)


class DeletionCategorySelect(Select):

    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id
        categories = [
            cat.name for cat in self.bot.cogs.values()
            if cat.name.lower() not in {'sync', 'jishaku', 'commanddeletion'}
        ]
        options = [
            discord.SelectOption(label=cat, value=cat.lower())
            for cat in categories
        ]
        super().__init__(placeholder='Select categories to auto-delete...',
                         min_values=1,
                         max_values=len(options),
                         options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        guild_config = self.bot.get_cog('CommandDeletion').get_guild_config(
            self.guild_id)
        for value in self.values:
            category_name = value.lower()
            if category_name not in guild_config['categories']:
                guild_config['categories'].append(category_name)
        save_config(self.bot.get_cog('CommandDeletion').config)
        await interaction.response.send_message(
            "Categories have been updated for auto-deletion.", ephemeral=True)


class DeletionCommandSelect(Select):

    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id
        commands = [
            cmd.name for cmd in bot.commands if cmd.cog_name and
            cmd.cog_name.lower() not in {'sync', 'jishaku', 'commanddeletion'}
        ]
        options = [
            discord.SelectOption(label=cmd, value=cmd) for cmd in commands
        ]
        super().__init__(placeholder='Select commands to auto-delete...',
                         min_values=1,
                         max_values=len(options),
                         options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        guild_config = self.bot.get_cog('CommandDeletion').get_guild_config(
            self.guild_id)
        for value in self.values:
            command_name = value.lower()
            if command_name not in guild_config['commands']:
                guild_config['commands'].append(command_name)
        save_config(self.bot.get_cog('CommandDeletion').config)
        await interaction.response.send_message(
            "Commands have been updated for auto-deletion.", ephemeral=True)


class ToggleAutoDeletionButton(Button):

    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id
        super().__init__(label="Toggle Auto-Deletion",
                         style=discord.ButtonStyle.primary,
                         emoji="🔄")

    async def callback(self, interaction: discord.Interaction) -> None:
        guild_config = self.bot.get_cog('CommandDeletion').get_guild_config(
            self.guild_id)
        if guild_config['enabled']:
            guild_config['enabled'] = False
            guild_config['commands'].clear()
            guild_config['categories'].clear()
            guild_config['delay'] = 3  # Reset the delay to the default value
            status = "disabled"
        else:
            guild_config['enabled'] = True
            status = "enabled"
        save_config(self.bot.get_cog('CommandDeletion').config)

        if not guild_config['enabled']:
            del self.bot.get_cog('CommandDeletion').config[str(self.guild_id)]
            save_config(self.bot.get_cog('CommandDeletion').config)

        await interaction.response.send_message(
            f"Command message auto-deletion has been {status}.",
            ephemeral=True)

        # Update the embed with the new status
        embed: Optional[discord.Embed] = interaction.message.embeds[
            0] if interaction.message.embeds else None
        if embed:
            enabled_status = "enabled" if guild_config[
                'enabled'] else "disabled"
            embed.description = embed.description.replace(
                f"Current Status: **{'enabled' if status == 'disabled' else 'disabled'}**",
                f"Current Status: **{enabled_status}**")
            # Update the dropdown menu to be enabled/disabled based on the new status
            if interaction.message.components:
                view = interaction.message.components[0]
                if view:
                    for item in view.children:
                        if isinstance(item, (Button, Select)):
                            item.disabled = not guild_config['enabled']
                    await interaction.message.edit(
                        embed=embed,
                        view=DeletionSetupView(self.bot, self.guild_id,
                                               guild_config['enabled']))


class SetDelayButton(Button):

    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id
        super().__init__(label="Set Deletion Delay",
                         style=discord.ButtonStyle.primary,
                         emoji="⏲️")

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            SetDelayModal(self.bot, self.guild_id))


class SetDelayModal(Modal):

    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id
        super().__init__(title="Set Auto-Deletion Delay")
        self.add_item(
            TextInput(label="Enter delay in seconds (3-60):",
                      style=discord.TextStyle.short,
                      placeholder="Enter a number between 3 and 60",
                      required=True,
                      min_length=1,
                      max_length=2))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        delay = int(self.children[0].value)
        if 3 <= delay <= 60:
            guild_config = self.bot.get_cog(
                'CommandDeletion').get_guild_config(self.guild_id)
            guild_config['delay'] = delay
            save_config(self.bot.get_cog('CommandDeletion').config)
            await interaction.response.send_message(
                f"Auto-deletion delay set to {delay} seconds.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Invalid delay. Please enter a number between 3 and 60.",
                ephemeral=True)


class ShowDeletionSetupButton(Button):

    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id
        super().__init__(label="Show Deletion Setup",
                         style=discord.ButtonStyle.primary,
                         emoji="📋")

    async def callback(self, interaction: discord.Interaction) -> None:
        guild_config = self.bot.get_cog('CommandDeletion').get_guild_config(
            self.guild_id)
        commands_list = '\n'.join(
            guild_config['commands']) or "No commands set."
        categories_list = '\n'.join(
            guild_config['categories']) or "No categories set."
        delay = guild_config['delay']
        embed = discord.Embed(title="Auto-Deletion Setup", color=EMBED_COLOR)
        embed.add_field(name="Commands", value=commands_list, inline=False)
        embed.add_field(name="Categories", value=categories_list, inline=False)
        embed.add_field(name="Deletion Delay",
                        value=f"{delay} seconds",
                        inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BackToSetupButton(Button):

    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id
        super().__init__(label="Back to Setup",
                         style=discord.ButtonStyle.secondary,
                         emoji="🔙")

    async def callback(self, interaction: discord.Interaction) -> None:
        guild_config = self.bot.get_cog('CommandDeletion').get_guild_config(
            self.guild_id)
        view = DeletionSetupView(self.bot, self.guild_id,
                                 guild_config['enabled'])
        enabled_status = "enabled" if guild_config['enabled'] else "disabled"
        embed = discord.Embed(
            title="Auto-Deletion Setup Wizard",
            description=
            (f"Current Status: **{enabled_status}**\n\n"
             "Select the type you want to set up for auto-deletion.\n\n"
             "**Disclaimer:** Disabling auto-deletion will clear all previously set commands and reset the delay."
             ),
            color=EMBED_COLOR)
        if interaction.message:
            await interaction.message.edit(embed=embed, view=view)


class DeleteEmbedButton(Button):

    def __init__(self) -> None:
        super().__init__(label=" ",
                         style=discord.ButtonStyle.danger,
                         emoji="🗑️")

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.message:
            await interaction.message.delete()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommandDeletion(bot))
