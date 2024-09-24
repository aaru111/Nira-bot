import discord
from discord.ext import commands
from discord import app_commands
from utils.wel import get_welcome_card
from database import Database


class WelcomeCmds(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = Database()

    async def cog_load(self):
        await self.db.initialize()

    async def cog_unload(self):
        await self.db.close()

    welcome = app_commands.Group(name="welcome",
                                 description="Welcome commands",
                                 guild_only=True)

    @welcome.command(name="channel", description="Set the welcome channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction,
                          channel: discord.TextChannel):
        """
        Set the channel where welcome messages will be sent.

        Parameters:
        - channel: The text channel to set as the welcome channel.
        """
        await self.db.execute(
            "INSERT INTO welcome (guild_id, channel_id) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2",
            interaction.guild.id,
            channel.id,
        )
        await interaction.response.send_message(
            f"Set welcome channel to {channel.mention}")

    @welcome.command(name="message", description="Set the welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_message(self, interaction: discord.Interaction, *,
                          message: str):
        """
        Set the custom welcome message for new members.

        Available placeholders:
        {user.mention} - Mentions the new member
        {user.name} - The username of the new member
        {user.id} - The ID of the new member
        {guild.name} - The name of the server
        {guild.member_count} - The current member count of the server

        Parameters:
        - message: The custom welcome message to set.
        """
        check = await self.db.fetch(
            "SELECT * FROM welcome WHERE guild_id = $1", interaction.guild.id)
        if not check:
            return await interaction.response.send_message(
                "Please set a welcome channel first!")
        await self.db.execute(
            "UPDATE welcome SET message = $1 WHERE guild_id = $2",
            message,
            interaction.guild.id,
        )
        await interaction.response.send_message(
            f"Set welcome message to: {message}")

    @welcome.command(name="test", description="Test the welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def test(self,
                   interaction: discord.Interaction,
                   user: discord.Member = None):
        """
        Test the welcome message by simulating a new member join.

        Parameters:
        - user: The user to simulate as a new member (optional, defaults to the command user).
        """
        user = user or interaction.user
        await self.on_member_join(user)
        return await interaction.response.send_message(
            "Sent test welcome message!")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        record = await self.db.fetch(
            "SELECT * FROM welcome WHERE guild_id = $1", member.guild.id)
        if not record:
            return  # No welcome settings for this guild
        channel_id = record[0]['channel_id']
        message = record[0].get('message')
        channel = member.guild.get_channel(channel_id)
        if not channel:
            return  # Channel not found

        try:
            welcome_card = await get_welcome_card(member)
        except Exception:
            welcome_card = None

        # Prepare placeholder values
        placeholders = {
            "user.mention": member.mention,
            "user.name": member.name,
            "user.id": member.id,
            "guild.name": member.guild.name,
            "guild.member_count": member.guild.member_count,
        }

        # Default embed message using all placeholders
        default_embed = discord.Embed(
            title=f"Welcome to {placeholders['guild.name']}!",
            description=
            (f"Hello {placeholders['user.mention']}! Welcome to our community.\n\n"
             f"You are our {placeholders['guild.member_count']}th member!\n\n"
             f"Your Details:\n"
             f"Name: {placeholders['user.name']}\n"
             f"ID: {placeholders['user.id']}\n\n"
             "We hope you enjoy your stay!"),
            color=discord.Color.green())
        default_embed.set_thumbnail(url=member.display_avatar.url)

        # Format the message with placeholders if a custom message is set
        if message:
            embed = discord.Embed(description=message.format(**placeholders),
                                  color=discord.Color.green())
            embed.set_thumbnail(url=member.display_avatar.url)
        else:
            embed = default_embed

        try:
            if welcome_card:
                await channel.send(
                    embed=embed,
                    file=discord.File(welcome_card, filename="welcome.png"),
                )
            else:
                await channel.send(embed=embed)
        except discord.errors.Forbidden:
            pass  # Bot doesn't have permission to send messages in the channel
        except Exception:
            pass  # Error sending welcome message


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCmds(bot))
