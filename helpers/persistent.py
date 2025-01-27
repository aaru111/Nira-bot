"""
Persistent Views Manager for Discord.py Bot
-----------------------------------------

This module manages persistent views that stay active between bot restarts.

How to Use:
1. Import in main.py:
   from persistent import PersistentViewManager

2. Initialize in Bot class:
   self._persistent_views = PersistentViewManager(self)

3. Call in setup_hook:
   await self._persistent_views.setup_all_views()

Adding New Persistent Views:
1. Create your view class in your cog file
2. Add a new setup method in PersistentViewManager
3. Call the setup method in setup_all_views()

Example:
    async def setup_custom_views(self) -> None:
        try:
            self.bot.add_view(YourCustomView(self.bot))
        except Exception as e:
            logger.error(f"Error adding custom views: {e}")

    async def setup_all_views(self) -> None:
        await self.setup_ticket_views()
        await self.setup_custom_views()
"""

from discord.ext import commands
from loguru import logger

from cogs.ticket.ticket import panel_views, closed_ticket_views, ticket_views
from cogs.ticket.utils.ticket_manager import TicketManager as DataManager


class PersistentViewManager:

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def setup_ticket_views(self) -> None:
        """Set up persistent views for the ticket system."""
        try:
            self.bot.add_view(panel_views(self.bot))

            tickets = await DataManager.get_all_tickets()
            panels = await DataManager.get_all_panels()

            for panel in panels:
                for ticket in tickets:
                    self.bot.add_view(view=closed_ticket_views(
                        self.bot, panel["id"], ticket["ticket_creator"],
                        ticket["ticket_id"]))

                    self.bot.add_view(view=ticket_views(
                        self.bot, panel["id"], ticket["ticket_creator"]))

        except Exception as e:
            logger.error(f"Error adding persistent ticket views: {e}")

    async def setup_suggestion_views(self) -> None:
        """Set up persistent views for the suggestion system."""
        try:

            from cogs.suggestion.suggestion import InitialSuggestionView, SuggestionButtons

            self.bot.add_view(InitialSuggestionView(self.bot))
            self.bot.add_view(SuggestionButtons(self.bot))

            logger.success("Successfully added persistent suggestion views")
        except Exception as e:
            logger.error(f"Error adding persistent suggestion views: {e}")

    async def setup_all_views(self) -> None:
        """Set up all persistent views for the bot."""
        logger.info("Setting up all persistent views...")

        await self.setup_ticket_views()

        await self.setup_suggestion_views()

        logger.success("All persistent views have been set up successfully")
