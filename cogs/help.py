import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional, Union, Any, Dict
import inspect

# Global variables
EMBED_COLOR = discord.Color.red()
THUMBNAIL_URL = None
COMMANDS_PER_PAGE = 8
FOOTER_TEXT = "[] -> Optional arguments | <> -> Required arguments"
EXCLUDED_COGS = ["jishaku", "sync",
                 "error"]  # Add cogs you want to exclude from help command


class HelpView(discord.ui.View):

    def __init__(self,
                 cog: 'HelpCog',
                 embeds: List[discord.Embed],
                 timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.embeds = embeds
        self.current_page = 0
        self.category = "Home"
        self.message = None
        self.update_buttons()

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        if interaction.user != self.cog.context.author:
            await interaction.response.send_message(
                "This pagination menu is not for you.", ephemeral=True)
            return False
        return True

    def update_buttons(self):
        self.clear_items()
        if len(self.embeds) > 1 and self.category != "Home":
            self.add_item(self.prev_button)
            self.add_item(self.page_indicator)
            self.add_item(self.next_button)
            self.add_item(self.goto_button)
        self.add_item(self.category_select)

        if len(self.embeds) > 1 and self.category != "Home":
            self.prev_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page == len(
                self.embeds) - 1
            self.page_indicator.label = f"Page {self.current_page + 1}/{len(self.embeds)}"

    async def update_view(self, interaction: discord.Interaction):
        self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.red)
    async def prev_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        self.current_page = max(0, self.current_page - 1)
        await self.update_view(interaction)

    @discord.ui.button(label="Page",
                       style=discord.ButtonStyle.blurple,
                       disabled=True)
    async def page_indicator(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.green)
    async def next_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        self.current_page = min(len(self.embeds) - 1, self.current_page + 1)
        await self.update_view(interaction)

    @discord.ui.button(label="Go To", style=discord.ButtonStyle.gray)
    async def goto_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        modal = GoToModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.select(placeholder="Select a category")
    async def category_select(self, interaction: discord.Interaction,
                              select: discord.ui.Select):
        self.category = select.values[0]
        self.embeds = await self.cog.create_paginated_help_embeds(
            self.cog.prefix, self.category)
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], view=self)

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)


class GoToModal(discord.ui.Modal, title="Go To Page"):
    page_number = discord.ui.TextInput(label="Page Number",
                                       placeholder="Enter the page number")

    def __init__(self, view: HelpView):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_number.value) - 1
            if 0 <= page < len(self.view.embeds):
                self.view.current_page = page
                self.view.update_buttons()
                await interaction.response.edit_message(
                    embed=self.view.embeds[self.view.current_page],
                    view=self.view)
            else:
                await interaction.response.send_message(
                    f"Invalid page number. Please enter a number between 1 and {len(self.view.embeds)}.",
                    ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.", ephemeral=True)


class HelpCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = None
        self.context = None
        self.prefix = "/"

    def cog_unload(self) -> None:
        self.bot.help_command = self._original_help_command

    @staticmethod
    def generate_usage(command: Union[commands.Command[Any, Any, Any],
                                      app_commands.Command],
                       prefix: str) -> str:
        if isinstance(command, app_commands.Command):
            usage = f"/{command.qualified_name}"
        elif isinstance(command, commands.HybridCommand):
            usage = f"/{command.qualified_name}"
        else:
            usage = f"{prefix}{command.qualified_name}"

        if hasattr(command, 'usage') and command.usage:
            return f"{usage} {command.usage}"

        parameters: Dict[
            str, inspect.Parameter] = command.clean_params if isinstance(
                command, commands.Command) else {
                    param.name: param
                    for param in command.parameters
                }

        for param_name, param in parameters.items():
            if param_name in ["ctx", "self"]:
                continue
            is_optional = param.default != inspect.Parameter.empty
            usage += f" {'[' if is_optional else '<'}{param_name}{'>' if not is_optional else ']'}"

        if isinstance(command, commands.Group):
            usage += " <subcommand>"

        return usage

    @commands.hybrid_command(name="help",
                             description="Shows help for bot commands")
    @app_commands.describe(command="The command to get help for")
    async def help_command(self,
                           ctx: commands.Context,
                           command: Optional[str] = None) -> None:
        self.context = ctx
        self.prefix = await self.bot.get_prefix(ctx.message)
        if isinstance(self.prefix, list):
            self.prefix = self.prefix[0]
        await self.send_help_embed(ctx, command)

    @help_command.autocomplete("command")
    async def command_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> List[app_commands.Choice[str]]:
        choices: List[app_commands.Choice[str]] = []
        for cmd in self.bot.walk_commands():
            if current.lower() in cmd.qualified_name.lower():
                choices.append(
                    app_commands.Choice(name=f"{cmd.qualified_name}",
                                        value=cmd.qualified_name))
        for cmd in self.bot.tree.walk_commands():
            if current.lower() in cmd.qualified_name.lower():
                choices.append(
                    app_commands.Choice(name=f"{cmd.qualified_name}",
                                        value=f"{cmd.qualified_name}"))
        return choices[:25]

    async def send_help_embed(self, ctx: Union[commands.Context,
                                               discord.Interaction],
                              command_name: Optional[str]) -> None:
        global THUMBNAIL_URL
        THUMBNAIL_URL = self.bot.user.avatar.url

        if command_name:
            embed = await self.create_command_embed(command_name)
            if isinstance(ctx, commands.Context):
                await ctx.send(embed=embed)
            else:
                await ctx.response.send_message(embed=embed)
        else:
            embeds = await self.create_paginated_help_embeds(
                self.prefix, "Home")
            view = HelpView(self, embeds)
            categories = ["Home", "All"] + [
                cog.qualified_name for cog in self.bot.cogs.values()
                if cog.qualified_name.lower() not in EXCLUDED_COGS
            ]
            view.category_select.options = [
                discord.SelectOption(label=category) for category in categories
            ]
            if isinstance(ctx, commands.Context):
                view.message = await ctx.send(embed=embeds[0], view=view)
            else:
                await ctx.response.send_message(embed=embeds[0], view=view)
                view.message = await ctx.original_response()

    async def create_command_embed(self, command_name: str) -> discord.Embed:
        embed = discord.Embed(title="Bot Help", color=EMBED_COLOR)
        command = self.bot.get_command(command_name.lstrip('/'))
        if not command:
            command = self.bot.tree.get_command(command_name.lstrip('/'))

        if command:
            embed.title = f"Help for /{command.qualified_name}"
            embed.description = command.description or "No description available."

            usage = self.generate_usage(command, self.prefix)
            embed.add_field(name="Usage", value=f"```{usage}```", inline=False)

            if isinstance(command, commands.Command) and command.aliases:
                embed.add_field(name="Aliases",
                                value=", ".join(f"`{self.prefix}{alias}`"
                                                for alias in command.aliases),
                                inline=False)
        else:
            embed.description = f"No command found named '{command_name}'."

        embed.set_footer(text=FOOTER_TEXT)
        embed.set_thumbnail(url=THUMBNAIL_URL)
        return embed

    async def create_paginated_help_embeds(self,
                                           prefix: str,
                                           category: str = "Home"
                                           ) -> List[discord.Embed]:
        cog_commands: Dict[str, List[str]] = {}

        for command in self.bot.commands:
            if command.cog and command.cog.qualified_name.lower(
            ) not in EXCLUDED_COGS:
                cog_name = command.cog.qualified_name
                if category in ["Home", "All"] or cog_name == category:
                    if cog_name not in cog_commands:
                        cog_commands[cog_name] = []
                    if isinstance(command, commands.HybridCommand):
                        cog_commands[cog_name].append(f"/{command.name}")
                    else:
                        cog_commands[cog_name].append(
                            f"{prefix}{command.name}")

        for command in self.bot.tree.walk_commands():
            if isinstance(command, app_commands.Command):
                cog_name = command.binding.__class__.__name__ if command.binding else "No Category"
                if cog_name.lower() not in EXCLUDED_COGS:
                    if category in ["Home", "All"] or cog_name == category:
                        if cog_name not in cog_commands:
                            cog_commands[cog_name] = []
                        cog_commands[cog_name].append(f"/{command.name}")

        embeds = []
        if category == "Home":
            embed = discord.Embed(title="Bot Help", color=EMBED_COLOR)
            embed.description = "**Welcome to the Help Menu!**\n\nSelect a category from the dropdown menu below to view commands in that category."
            for cog_name in cog_commands.keys():
                embed.add_field(name=cog_name, value="\u200b", inline=True)
            embeds.append(embed)
        else:
            all_commands = []
            for commands_list in cog_commands.values():
                all_commands.extend(commands_list)

            chunks = [
                all_commands[i:i + COMMANDS_PER_PAGE]
                for i in range(0, len(all_commands), COMMANDS_PER_PAGE)
            ]

            for chunk in chunks:
                embed = discord.Embed(title="Bot Help", color=EMBED_COLOR)
                embed.description = f"**Commands in {'all categories' if category == 'All' else category} category:**"
                for command in chunk:
                    embed.add_field(name="\u200b",
                                    value=f"`{command}`",
                                    inline=True)
                embeds.append(embed)

        for embed in embeds:
            embed.set_footer(text=FOOTER_TEXT)
            embed.set_thumbnail(url=THUMBNAIL_URL)

        return embeds


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
