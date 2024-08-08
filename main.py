import os
import logging
import discord
from discord.ext import commands
import asyncio
from aiohttp import ClientSession
from typing import Any
from webserver import keep_alive

# -------------------------
# Logging Configuration
# -------------------------
logging.basicConfig(
    level=logging.INFO,  # Adjust to ERROR or WARNING in production
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)


# -------------------------
# Bot Class Definition
# -------------------------
class Bot(commands.Bot):

    def __init__(self, command_prefix: str, intents: discord.Intents,
                 session: ClientSession, **kwargs: Any) -> None:
        super().__init__(command_prefix=command_prefix,
                         intents=intents,
                         **kwargs)
        self.session = session

    async def setup_hook(self) -> None:
        try:
            await self.load_extension("jishaku")
            logger.info("Extension 'jishaku' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load extension 'jishaku': {e}")

        await self.load_all_cogs()

    async def load_all_cogs(self) -> None:
        cog_files = [f for f in os.listdir('./cogs') if f.endswith('.py')]
        await asyncio.gather(*(self.load_cog(f) for f in cog_files))

    async def load_cog(self, filename: str) -> None:
        cog_name = f'cogs.{filename[:-3]}'
        try:
            await self.load_extension(cog_name)
            logger.info(f"{cog_name} loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load {cog_name}: {e}")

    async def on_ready(self) -> None:
        logger.info(f'Bot is ready as {self.user} (ID: {self.user.id}).')

    async def on_error(self, event_method: str, *args: Any,
                       **kwargs: Any) -> None:
        logger.error('Unhandled exception in %s.', event_method, exc_info=True)

    async def close(self) -> None:
        await self.session.close()
        await super().close()


# -------------------------
# Main Function and Execution
# -------------------------
async def main() -> None:
    intents = discord.Intents.default()
    intents.message_content = True  # Enable only if your bot needs this

    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("DISCORD_BOT_TOKEN environment variable not set.")
        return

    async with ClientSession() as session:  # Create session here
        bot = Bot(command_prefix=".",
                  case_insensitive=True,
                  intents=intents,
                  session=session)
        try:
            await bot.start(token)
        except discord.LoginFailure:
            logger.error("Invalid bot token provided.")
        except Exception as e:
            logger.error(f"An error occurred during bot startup: {e}")
        finally:
            if bot.is_closed():
                logger.warning("Bot has been disconnected.")


if __name__ == "__main__":
    keep_alive()  # Start the webserver for keeping the bot alive
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated by user.")
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)
