import os
import logging
import discord
from discord.ext import commands
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# -------------------------
# Bot Class Definition
# -------------------------

class Bot(commands.Bot):

    def __init__(self, command_prefix: str, intents: discord.Intents, **kwargs):
        super().__init__(command_prefix=command_prefix, intents=intents, **kwargs)
        self.command_prefix = command_prefix

    async def setup_hook(self) -> None:
        """
        Performs initial setup tasks for the bot.
        """
        # Example asynchronous operation
        await self.load_extension("jishaku") # Example asynchronous operation
        await self.load_all_cogs() # Example asynchronous operation

    async def load_all_cogs(self) -> None:
        """
        Loads all cog extensions from the 'cogs' directory.
        """
        async def load_cog(filename):
            cog_name = f'cogs.{filename[:-3]}'
            try:
                await self.load_extension(cog_name)
                logging.info(f"{cog_name} loaded")
            except Exception as e:
                logging.error(f"Failed to load {cog_name}: {e}")

        await asyncio.gather(*(load_cog(filename) for filename in os.listdir('./cogs') if filename.endswith('.py')))

    async def on_ready(self):
        """
        Event handler triggered when the bot is ready.
        """
        logging.info('Bot is ready.')
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')

    async def on_error(self, event_method, *args, **kwargs):
        """
        Error handler for unhandled exceptions.
        """
        logging.error('Unhandled exception occurred.', exc_info=True)

# -------------------------
# Main Function and Execution
# -------------------------

async def main():
    """
    Main function to set up and start the Discord bot.
    """
    # Define the necessary intents for the bot
    intents = discord.Intents.all()
    intents.message_content = True # Enable if your bot needs to read message content

    # Create bot instance
    bot = Bot(command_prefix=".", case_insensitive=True, intents=intents)

    # Load environment variables
    token = os.getenv('DISCORD_BOT_TOKEN')

    # Check if token is provided
    if not token:
        logging.error("DISCORD_BOT_TOKEN environment variable not set.")
        return

    # Attempt to start the bot
    try:
        await bot.start(token)
    except discord.LoginFailure:
        logging.error("Invalid bot token provided.")
    except Exception as e:
        logging.error(f"An error occurred during bot startup: {e}")

if __name__ == "__main__":
    # Run the main function asynchronously
    asyncio.run(main())
