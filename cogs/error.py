import discord
from discord.ext import commands
import logging
import traceback
from typing import Optional, Union, List
from main import Bot
import aiohttp
from difflib import get_close_matches

# Set up logging
logger = logging.getLogger('discord')
logger.setLevel(logging.ERROR)
handler = logging.FileHandler(filename='discord_errors.log',
                              encoding='utf-8',
                              mode='w')
handler.setFormatter(
    logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# Define the embed color
EMBED_COLOR = 0x2f3131


class Errors(commands.Cog):
  """
    A cog to handle and report errors occurring during command execution.
    """

  def __init__(self, bot: Bot) -> None:
    """
        Initialize the Errors cog.

        Args:
            bot (Bot): The instance of the bot.
        """
    self.bot: Bot = bot
    self.session: aiohttp.ClientSession = aiohttp.ClientSession()

  async def send_error_embed(self, ctx: commands.Context, title: str,
                             description: str) -> None:
    """
        Send an embed with error information to the context channel.

        Args:
            ctx (commands.Context): The context in which the command was invoked.
            title (str): The title of the embed.
            description (str): The description of the embed.
        """
    embed = discord.Embed(title=title,
                          description=f"```py\n{description}```",
                          color=EMBED_COLOR)
    await ctx.send(embed=embed)

  async def close(self) -> None:
    """
        Close the aiohttp client session.
        """
    await self.session.close()

  @commands.Cog.listener()
  async def on_shutdown(self):
      await self.close()

  @commands.Cog.listener()
  async def on_disconnect(self):
      await self.close()

  async def handle_error(self, ctx: commands.Context, command_name: str,
                         description: str, title: str) -> None:
    """
        Send an error embed and log the error.

        Args:
            ctx (commands.Context): The context in which the command was invoked.
            command_name (str): The name of the command that triggered the error.
            description (str): The description of the error.
            title (str): The title of the error.
        """
    await self.send_error_embed(ctx, title, description)
    logger.error(f"Ignoring exception in command {command_name}:")
    logger.error(description)

  @commands.Cog.listener()
  async def on_command_error(self, ctx: commands.Context,
                             error: commands.CommandError) -> None:
    """
        Handle errors that occur during command execution.

        Args:
            ctx (commands.Context): The context in which the command was invoked.
            error (commands.CommandError): The error that was raised.
        """
    command_name = ctx.command.qualified_name if ctx.command else "Unknown Command"
    command_signature = getattr(ctx.command, 'signature',
                                '') if ctx.command else ""

    if isinstance(error, commands.MissingRequiredArgument):
      description = f"Argument: '{error.param.name}'\nUsage: {ctx.prefix}{command_name} {command_signature}"
      await self.handle_error(ctx, command_name, description,
                              "Missing Required Argument")

    elif isinstance(error, commands.CommandNotFound):
      description = "Command not found. Please check your command and try again."
      similar_commands = get_close_matches(
          error.args[0].split()[0], [cmd.name for cmd in self.bot.commands],
          n=3,
          cutoff=0.6)
      if similar_commands:
        description += "\n\nDid you mean?\n" + '\n'.join(similar_commands)
      await self.handle_error(ctx, command_name, description,
                              "Command Not Found")

    elif isinstance(error, commands.MissingPermissions):
      perms = ', '.join(error.missing_permissions)
      description = f"You need the following permissions to execute this command: {perms}"
      await self.handle_error(ctx, command_name, description,
                              "Missing Permissions")

    elif isinstance(error, commands.BotMissingPermissions):
      perms = ', '.join(error.missing_permissions)
      description = f"I need the following permissions to execute this command: {perms}"
      await self.handle_error(ctx, command_name, description,
                              "Bot Missing Permissions")

    elif isinstance(error, commands.CommandOnCooldown):
      description = f"This command is on cooldown. Try again after {error.retry_after:.2f} seconds."
      await self.handle_error(ctx, command_name, description,
                              "Command on Cooldown")

    elif isinstance(error, commands.NotOwner):
      description = "Only the bot owner can use this command."
      await self.handle_error(ctx, command_name, description, "Not Owner")

    elif isinstance(error, commands.NoPrivateMessage):
      description = "This command cannot be used in private messages."
      await self.handle_error(ctx, command_name, description,
                              "No Private Message")

    elif isinstance(error, commands.BadArgument):
      await self.handle_error(ctx, command_name, str(error), "Bad Argument")

    elif isinstance(error, commands.CheckFailure):
      description = "You do not have permission to execute this command."
      await self.handle_error(ctx, command_name, description, "Check Failure")

    elif isinstance(error, commands.DisabledCommand):
      description = "This command is currently disabled."
      await self.handle_error(ctx, command_name, description,
                              "Disabled Command")

    elif isinstance(error, commands.UserInputError):
      await self.handle_error(ctx, command_name, str(error),
                              "User Input Error")

    elif isinstance(error, commands.InvalidEndOfQuotedStringError):
      await self.handle_error(ctx, command_name, str(error),
                              "Invalid End of Quoted String")

    elif isinstance(error, commands.ExpectedClosingQuoteError):
      await self.handle_error(ctx, command_name, str(error),
                              "Expected Closing Quote")

    else:
      # Log the error with traceback
      traceback_str = ''.join(
          traceback.format_exception(type(error), error, error.__traceback__))
      await self.handle_error(ctx, command_name, traceback_str,
                              "Unexpected Error")

      # Notify developers
      dev_channel = self.bot.get_channel(
          971651546939031562)  # Replace with your developer channel ID
      if dev_channel and isinstance(dev_channel, discord.TextChannel):
        await dev_channel.send(
            f"Error in command `{command_name}` triggered by {ctx.author} in {ctx.channel}:\n{traceback_str}"
        )

    # Additional error details for logs
    logger.error(f"Command: {command_name}")
    logger.error(f"Author: {ctx.author} (ID: {ctx.author.id})")
    logger.error(f"Channel: {ctx.channel} (ID: {ctx.channel.id})")
    logger.error(f"Guild: {ctx.guild} (ID: {ctx.guild.id})" if ctx.
                 guild else "Guild: None")


async def setup(bot: Bot) -> None:
  """
    Load the Errors cog.

    Args:
        bot (Bot): The instance of the bot.
    """
  await bot.add_cog(Errors(bot))


