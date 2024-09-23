import discord
from discord.ext import commands
from discord import app_commands
import asyncio

# Import necessary classes and functions from embedmod.py
from modules.embedmod import (AuthorModal, BodyModal, ImagesModal, FooterModal,
                              AddFieldModal, EditFieldModal, BaseView,
                              PlusButton, MinusButton, EditFieldButton,
                              FieldsButton, FieldCountButton, ResetButton,
                              create_embed_view, is_embed_configured)


class WelcomerSystem(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.welcome_embed = None
        self.welcome_channel_id = None
        self.is_enabled = False

    @app_commands.command(
        name="welcome_setup",
        description="Set up the welcome message for new members.")
    async def welcome_setup(self, interaction: discord.Interaction) -> None:
        try:
            if not self.welcome_embed:
                self.welcome_embed = discord.Embed(
                    title="Welcome Message Configuration",
                    description=
                    "Use the options below to configure your welcome message.",
                    color=discord.Color.blue())

            view = WelcomerView(self.welcome_embed, self.bot, self)

            await interaction.response.send_message(
                content="Welcome Message Configuration",
                embed=self.welcome_embed,
                view=view,
                ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred: {str(e)}", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not self.is_enabled or not self.welcome_channel_id or not self.welcome_embed:
            return

        channel = self.bot.get_channel(self.welcome_channel_id)
        if not channel:
            return

        # Replace placeholders in the welcome message
        embed = self.welcome_embed.copy()
        embed.description = embed.description.replace("{servername}",
                                                      member.guild.name)
        embed.description = embed.description.replace("{username}",
                                                      member.mention)

        await channel.send(embed=embed)


class WelcomerView(BaseView):

    def __init__(self, embed: discord.Embed, bot: commands.Bot,
                 cog: WelcomerSystem):
        super().__init__(bot=bot, embed=embed)
        self.cog = cog
        self.setup_items()

    def setup_items(self):
        self.clear_items()
        select_options = [
            discord.SelectOption(label="Author", value="author", emoji="📝"),
            discord.SelectOption(label="Body", value="body", emoji="📄"),
            discord.SelectOption(label="Images", value="images", emoji="🖼️"),
            discord.SelectOption(label="Footer", value="footer", emoji="🔻"),
        ]
        select = discord.ui.Select(
            placeholder="Choose a part of the embed to edit...",
            options=select_options)
        select.callback = self.dropdown_callback
        self.add_item(select)
        self.add_item(ToggleWelcomerButton(self.cog))
        self.add_item(SelectWelcomeChannelButton(self.cog))
        self.add_item(TestWelcomeMessageButton(self.cog))
        self.add_item(FieldsButton())
        self.add_item(PlusButton(self.embed))
        self.add_item(MinusButton(self.embed))
        self.add_item(EditFieldButton(self.embed, self.bot))
        self.add_item(FieldCountButton(self.embed))
        self.add_item(ResetButton(self.embed))

    async def dropdown_callback(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        if value == "author":
            modal = AuthorModal(self.embed, self.bot, is_edit=True)
        elif value == "body":
            modal = BodyModal(self.embed, self.bot, is_edit=True)
        elif value == "images":
            modal = ImagesModal(self.embed, self.bot, is_edit=True)
        elif value == "footer":
            modal = FooterModal(self.embed, self.bot, is_edit=True)
        else:
            await interaction.response.send_message("Invalid option selected.",
                                                    ephemeral=True)
            return

        await interaction.response.send_modal(modal)
        await modal.wait()
        await interaction.edit_original_response(embed=self.embed, view=self)


class ToggleWelcomerButton(discord.ui.Button):

    def __init__(self, cog: WelcomerSystem):
        super().__init__(style=discord.ButtonStyle.green
                         if cog.is_enabled else discord.ButtonStyle.red,
                         label="Enabled" if cog.is_enabled else "Disabled",
                         custom_id="toggle_welcomer")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        self.cog.is_enabled = not self.cog.is_enabled
        self.style = discord.ButtonStyle.green if self.cog.is_enabled else discord.ButtonStyle.red
        self.label = "Enabled" if self.cog.is_enabled else "Disabled"
        await interaction.response.edit_message(view=self.view)


class SelectWelcomeChannelButton(discord.ui.Button):

    def __init__(self, cog: WelcomerSystem):
        super().__init__(style=discord.ButtonStyle.blurple,
                         label="Select Welcome Channel",
                         custom_id="select_channel")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        channels = [
            channel for channel in interaction.guild.text_channels
            if channel.permissions_for(interaction.user).send_messages
        ]

        options = [
            discord.SelectOption(label=channel.name, value=str(channel.id))
            for channel in channels[:25]
        ]  # Discord allows max 25 options

        select = discord.ui.Select(placeholder="Select a channel...",
                                   options=options)
        select.callback = self.channel_select_callback

        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message("Select a welcome channel:",
                                                view=view,
                                                ephemeral=True)

    async def channel_select_callback(self, interaction: discord.Interaction):
        channel_id = int(interaction.data["values"][0])
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            self.cog.welcome_channel_id = channel_id
            await interaction.response.send_message(
                f"Welcome channel set to {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Invalid channel selected. Please try again.", ephemeral=True)


class TestWelcomeMessageButton(discord.ui.Button):

    def __init__(self, cog: WelcomerSystem):
        super().__init__(style=discord.ButtonStyle.green,
                         label="Test Welcome Message",
                         custom_id="test_welcome_message")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if not self.cog.welcome_channel_id or not self.cog.welcome_embed:
            await interaction.response.send_message(
                "Please configure the welcome channel and message first.",
                ephemeral=True)
            return

        channel = interaction.guild.get_channel(self.cog.welcome_channel_id)
        if not channel:
            await interaction.response.send_message(
                "The selected welcome channel no longer exists. Please choose a new one.",
                ephemeral=True)
            return

        # Replace placeholders in the welcome message
        embed = self.cog.welcome_embed.copy()
        embed.description = embed.description.replace("{servername}",
                                                      interaction.guild.name)
        embed.description = embed.description.replace("{username}",
                                                      interaction.user.mention)

        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"Test welcome message sent to {channel.mention}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomerSystem(bot))