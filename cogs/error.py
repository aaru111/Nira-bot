import discord
from discord.ext import commands
import logging
import traceback
from typing import Optional, Union
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

  def __init__(self, bot: Bot):
    self.bot: Bot = bot
    self.session = aiohttp.ClientSession()

  async def send_error_embed(self, ctx: commands.Context, title: str,
                             description: str) -> None:
    embed = discord.Embed(title=title,
                          description=f"```py\n{description}```",
                          color=EMBED_COLOR)
    await ctx.send(embed=embed)

  async def close(self) -> None:
    await self.session.close()

  @commands.Cog.listener()
  async def on_command_error(self, ctx: commands.Context,
                             error: commands.CommandError) -> None:
    command_name = ctx.command.qualified_name if ctx.command else "Unknown Command"
    command_signature = getattr(ctx.command, 'signature',
                                '') if ctx.command else ""

    if isinstance(error, commands.MissingRequiredArgument):
      await self.send_error_embed(
          ctx, "Missing Required Argument",
          f"Argument: '{error.param.name}'\nUsage: {ctx.prefix}{command_name} {command_signature}"
      )

    elif isinstance(error, commands.CommandNotFound):
      description = "Command not found. Please check your command and try again."
      similar_commands = get_close_matches(
          error.args[0].split()[0], [cmd.name for cmd in self.bot.commands],
          n=3,
          cutoff=0.6)
      if similar_commands:
        description += "\n\nDid you mean?\n" + '\n'.join(similar_commands)
      await self.send_error_embed(ctx, "Command Not Found", description)

    elif isinstance(error, commands.MissingPermissions):
      perms = ', '.join(error.missing_permissions)
      await self.send_error_embed(
          ctx, "Missing Permissions",
          f"You need the following permissions to execute this command: {perms}"
      )

    elif isinstance(error, commands.BotMissingPermissions):
      perms = ', '.join(error.missing_permissions)
      await self.send_error_embed(
          ctx, "Bot Missing Permissions",
          f"I need the following permissions to execute this command: {perms}")

    elif isinstance(error, commands.CommandOnCooldown):
      await self.send_error_embed(
          ctx, "Command on Cooldown",
          f"This command is on cooldown. Try again after {error.retry_after:.2f} seconds."
      )

    elif isinstance(error, commands.NotOwner):
      await self.send_error_embed(ctx, "Not Owner",
                                  "Only the bot owner can use this command.")

    elif isinstance(error, commands.NoPrivateMessage):
      await self.send_error_embed(
          ctx, "No Private Message",
          "This command cannot be used in private messages.")

    elif isinstance(error, commands.BadArgument):
      await self.send_error_embed(ctx, "Bad Argument", str(error))

    elif isinstance(error, commands.CheckFailure):
      await self.send_error_embed(
          ctx, "Check Failure",
          "You do not have permission to execute this command.")

    elif isinstance(error, commands.DisabledCommand):
      await self.send_error_embed(ctx, "Disabled Command",
                                  "This command is currently disabled.")

    elif isinstance(error, commands.UserInputError):
      await self.send_error_embed(ctx, "User Input Error", str(error))

    elif isinstance(error, commands.InvalidEndOfQuotedStringError):
      await self.send_error_embed(ctx, "Invalid End of Quoted String",
                                  str(error))

    elif isinstance(error, commands.ExpectedClosingQuoteError):
      await self.send_error_embed(ctx, "Expected Closing Quote", str(error))

    else:
      # Log the error with traceback
      logger.error(f"Ignoring exception in command {command_name}:")
      logger.error(error)
      traceback_str = ''.join(
          traceback.format_exception(type(error), error, error.__traceback__))
      logger.error(traceback_str)

      # Send a generic error message to the user
      await self.send_error_embed(
          ctx, "Unexpected Error",
          "An unexpected error occurred. The incident has been logged and will be looked into."
      )

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
  await bot.add_cog(Errors(bot))
