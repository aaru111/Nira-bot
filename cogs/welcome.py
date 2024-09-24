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
        except Exception as e:
            print(f"Error generating welcome card: {e}")
            welcome_card = None

        default_message = f"Welcome to {member.guild.name}, {member.mention}!"
        send_message = message.format(
            user=member.mention,
            guild=member.guild.name) if message else default_message

        try:
            if welcome_card:
                await channel.send(
                    send_message,
                    file=discord.File(welcome_card, filename="welcome.png"),
                )
            else:
                await channel.send(send_message)
        except discord.errors.Forbidden:
            print(
                f"Bot doesn't have permission to send messages in {channel.name}"
            )
        except Exception as e:
            print(f"Error sending welcome message: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCmds(bot))
