import discord
from discord.ext import commands
from discord import app_commands
from utils.wel import get_welcome_card
from database import Database
import datetime


class WelcomeModal(discord.ui.Modal, title="Set Welcome Message"):
    message = discord.ui.TextInput(
        label="Welcome Message",
        style=discord.TextStyle.long,
        placeholder=
        "Enter your custom welcome message here or leave empty for default...",
        required=False)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.set_message_callback(interaction, str(self.message))


class DefaultWelcomeModal(discord.ui.Modal,
                          title="Edit Default Welcome Message"):
    message = discord.ui.TextInput(label="Default Welcome Message",
                                   style=discord.TextStyle.long,
                                   required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.message.default = self.cog.default_welcome_message

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.set_message_callback(interaction,
                                            str(self.message),
                                            is_default=True)


class TestButton(discord.ui.Button):

    def __init__(self, cog):
        super().__init__(style=discord.ButtonStyle.primary,
                         label="Test Welcome Message")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        sent = await self.cog.on_member_join(interaction.user)
        if sent:
            await interaction.followup.send("Sent test welcome message!",
                                            ephemeral=True)
        else:
            await interaction.followup.send(
                "Failed to send test welcome message. Please check your welcome channel and message settings.",
                ephemeral=True)


class PlaceholderButton(discord.ui.Button):

    def __init__(self, cog):
        super().__init__(style=discord.ButtonStyle.secondary,
                         label="Show Placeholders")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Available Placeholders",
                              color=discord.Color.blue())

        placeholders = {
            "user": "Mentions the user",
            "username": "Shows the username",
            "userid": "Shows the user ID",
            "server": "Shows the server name",
            "membercount": "Shows the server's member count",
            "joindate": "Shows the user's join date",
            "servercreation": "Shows the server's creation date"
        }

        placeholder_list = list(placeholders.keys())

        embed.add_field(name="User Placeholders",
                        value="\n".join([
                            f"`{{{p}}}`\n ╰> \"{placeholders[p]}\""
                            for p in placeholder_list[:5]
                        ]),
                        inline=True)

        if len(placeholder_list) > 5:
            embed.add_field(name="Server Placeholders",
                            value="\n".join([
                                f"`{{{p}}}`\n ╰> \"{placeholders[p]}\""
                                for p in placeholder_list[5:10]
                            ]),
                            inline=True)

        if len(placeholder_list) > 10:
            embed.add_field(name="Other Placeholders",
                            value="\n".join([
                                f"`{{{p}}}`\n ╰> \"{placeholders[p]}\""
                                for p in placeholder_list[10:]
                            ]),
                            inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class WelcomeCmds(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = Database()
        self.valid_placeholders = {
            "user", "username", "userid", "server", "membercount", "joindate",
            "servercreation"
        }
        self.default_welcome_message = (
            "**Hello {user}!**\n\n"
            "Welcome to our vibrant community. We're thrilled to have you join us as our **{membercount}th** member!\n\n"
            "🔹 **Your Details:**\n"
            "• Name: `{username}`\n"
            "• ID: `{userid}`\n"
            "• Joined on: `{joindate}`\n"
            "• Server created on: `{servercreation}`\n\n"
            "🔹 **Getting Started:**\n"
            "• Check out our rules and guidelines\n"
            "• Introduce yourself in the introductions channel\n"
            "• Explore our various topic-specific channels\n\n"
            "If you have any questions, feel free to ask our friendly community or moderators.\n\n"
            "We hope you have a fantastic time here! 🌟")

    async def cog_load(self):
        await self.db.initialize()
        await self.create_welcome_table()

    async def cog_unload(self):
        await self.db.close()

    async def create_welcome_table(self):
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS welcome (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT,
                message TEXT,
                is_enabled BOOLEAN DEFAULT TRUE,
                embed_color INTEGER DEFAULT 3447003,
                dm_enabled BOOLEAN DEFAULT FALSE,
                channel_enabled BOOLEAN DEFAULT TRUE
            )
            """)
        columns = [("is_enabled", "BOOLEAN DEFAULT TRUE"),
                   ("embed_color", "INTEGER DEFAULT 3447003"),
                   ("dm_enabled", "BOOLEAN DEFAULT FALSE"),
                   ("channel_enabled", "BOOLEAN DEFAULT TRUE")]
        for column, data_type in columns:
            await self.db.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='welcome' AND column_name='{column}') THEN
                        ALTER TABLE welcome ADD COLUMN {column} {data_type};
                    END IF;
                END$$;
            """)

    @app_commands.command(name="welcome-channel",
                          description="Set the welcome channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction,
                          channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        await self.db.execute(
            "INSERT INTO welcome (guild_id, channel_id) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2",
            interaction.guild.id,
            channel.id,
        )
        await interaction.followup.send(
            f"Set welcome channel to {channel.mention}", ephemeral=True)

    @app_commands.command(name="welcome-message",
                          description="Set the welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(message_type=[
        app_commands.Choice(name="Edit Default Message", value="default"),
        app_commands.Choice(name="Custom", value="custom")    
    ])
    async def set_message(self, interaction: discord.Interaction,
                          message_type: app_commands.Choice[str]):
        check = await self.db.fetch(
            "SELECT * FROM welcome WHERE guild_id = $1", interaction.guild.id)
        if not check:
            await interaction.response.send_message(
                "Please set a welcome channel first!", ephemeral=True)
            return

        if message_type.value == "custom":
            modal = WelcomeModal(self)
            await interaction.response.send_modal(modal)
        else:  # default
            modal = DefaultWelcomeModal(self)
            await interaction.response.send_modal(modal)

    async def set_message_callback(self,
                                   interaction: discord.Interaction,
                                   message: str,
                                   is_default: bool = False):
        if not message.strip():
            await self.db.execute(
                "UPDATE welcome SET message = NULL WHERE guild_id = $1",
                interaction.guild.id,
            )
            await interaction.followup.send(
                "Welcome message reset to default.", ephemeral=True)
            return

        if not self.validate_placeholders(message):
            await interaction.followup.send(
                "Invalid placeholders in the message. Please use only the allowed placeholders.",
                ephemeral=True)
            return

        if is_default:
            self.default_welcome_message = message
            await interaction.followup.send(
                f"Updated default welcome message.", ephemeral=True)
        else:
            await self.db.execute(
                "UPDATE welcome SET message = $1 WHERE guild_id = $2",
                message,
                interaction.guild.id,
            )
            await interaction.followup.send(
                f"Set custom welcome message to: {message}", ephemeral=True)

    @app_commands.command(name="welcome-toggle",
                          description="Toggle welcome message settings")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(setting=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Channel", value="channel"),
        app_commands.Choice(name="DM", value="dm")
    ])
    async def toggle_welcome(self, interaction: discord.Interaction,
                             setting: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        record = await self.db.fetch(
            "SELECT * FROM welcome WHERE guild_id = $1", interaction.guild.id)
        if not record:
            await interaction.followup.send(
                "Welcome message is not set up yet.", ephemeral=True)
            return

        if setting.value == "all":
            new_state = not record[0]['is_enabled']
            await self.db.execute(
                "UPDATE welcome SET is_enabled = $1, channel_enabled = $1, dm_enabled = $1 WHERE guild_id = $2",
                new_state, interaction.guild.id)
            state_str = "enabled" if new_state else "disabled"
            await interaction.followup.send(
                f"All welcome messages are now {state_str}.", ephemeral=True)
        elif setting.value == "channel":
            new_state = not record[0]['channel_enabled']
            await self.db.execute(
                "UPDATE welcome SET channel_enabled = $1 WHERE guild_id = $2",
                new_state, interaction.guild.id)
            state_str = "enabled" if new_state else "disabled"
            await interaction.followup.send(
                f"Welcome messages in the channel are now {state_str}.",
                ephemeral=True)
        elif setting.value == "dm":
            new_state = not record[0]['dm_enabled']
            await self.db.execute(
                "UPDATE welcome SET dm_enabled = $1 WHERE guild_id = $2",
                new_state, interaction.guild.id)
            state_str = "enabled" if new_state else "disabled"
            await interaction.followup.send(
                f"Welcome messages via DM are now {state_str}.",
                ephemeral=True)

    @app_commands.command(
        name="welcome-color",
        description="Set the embed color for welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_color(self, interaction: discord.Interaction, color: str):
        await interaction.response.defer(ephemeral=True)
        try:
            color_int = int(color.strip('#'), 16)
        except ValueError:
            await interaction.followup.send(
                "Invalid color. Please use a hex color code (e.g., #FF0000 for red).",
                ephemeral=True)
            return

        await self.db.execute(
            "UPDATE welcome SET embed_color = $1 WHERE guild_id = $2",
            color_int, interaction.guild.id)
        await interaction.followup.send(
            f"Set welcome message embed color to: {color}", ephemeral=True)

    @app_commands.command(name="welcome-info",
                          description="Show current welcome message settings")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        record = await self.db.fetch(
            "SELECT * FROM welcome WHERE guild_id = $1", interaction.guild.id)
        if not record:
            await interaction.followup.send(
                "Welcome message is not set up yet.", ephemeral=True)
            return

        settings = record[0]
        channel = interaction.guild.get_channel(settings['channel_id'])
        channel_mention = channel.mention if channel else "Not set"

        embed = discord.Embed(title="Welcome Message Settings",
                              color=discord.Color(settings['embed_color']))
        embed.add_field(name="Welcome Channel",
                        value=channel_mention,
                        inline=False)
        embed.add_field(name="Welcome Message",
                        value=settings['message'] or "Default message",
                        inline=False)
        embed.add_field(name="Overall Enabled",
                        value="Yes" if settings['is_enabled'] else "No",
                        inline=True)
        embed.add_field(name="DM Enabled",
                        value="Yes" if settings['dm_enabled'] else "No",
                        inline=True)
        embed.add_field(name="Channel Enabled",
                        value="Yes" if settings['channel_enabled'] else "No",
                        inline=True)
        embed.add_field(name="Embed Color",
                        value=f"#{settings['embed_color']:06x}",
                        inline=True)

        view = discord.ui.View()
        view.add_item(TestButton(self))
        view.add_item(PlaceholderButton(self))
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    def validate_placeholders(self, message):
        used_placeholders = set(
            word.strip('{}') for word in message.split()
            if word.startswith('{') and word.endswith('}'))
        return used_placeholders.issubset(self.valid_placeholders)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        record = await self.db.fetch(
            "SELECT * FROM welcome WHERE guild_id = $1", member.guild.id)
        if not record or not record[0]['is_enabled']:
            return False
        channel_id = record[0]['channel_id']
        message = record[0].get('message')
        embed_color = discord.Color(record[0]['embed_color'])
        dm_enabled = record[0]['dm_enabled']
        channel_enabled = record[0]['channel_enabled']
        channel = member.guild.get_channel(channel_id)
        if not channel_enabled and not dm_enabled:
            return False

        try:
            welcome_card = await get_welcome_card(member)
        except Exception:
            welcome_card = None

        placeholders = {
            "user": member.mention,
            "username": member.name,
            "userid": member.id,
            "server": member.guild.name,
            "membercount": member.guild.member_count,
            "joindate": member.joined_at.strftime("%Y-%m-%d %H:%M:%S"),
            "servercreation":
            member.guild.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }

        default_embed = discord.Embed(
            title=f"Welcome to {placeholders['server']}! 🎉",
            description=self.default_welcome_message.format(**placeholders),
            color=embed_color,
        )

        if message:
            try:
                formatted_message = message.format(**placeholders)
                embed = discord.Embed(description=formatted_message,
                                      color=embed_color)
            except KeyError:
                embed = default_embed
        else:
            embed = default_embed

        if welcome_card:
            welcome_card.seek(0)
            file = discord.File(welcome_card, filename="welcome.png")
            embed.set_image(url="attachment://welcome.png")
        else:
            file = None
            embed.set_thumbnail(url=member.display_avatar.url)

        sent = False
        try:
            if channel_enabled and channel:
                await channel.send(content=member.mention,
                                   embed=embed,
                                   file=file)
                sent = True
            if dm_enabled:
                await member.send(embed=embed)
                sent = True
        except discord.errors.Forbidden:
            pass
        except Exception:
            pass

        return sent


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCmds(bot))
