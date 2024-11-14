from typing import Optional, Dict, List
from database import db


class TicketManager:

    @staticmethod
    async def create_panel(panel_id: int, channel_id: int, guild_id: int,
                           limit_per_user: int, panel_title: str,
                           panel_description: str,
                           panel_moderators: List[int]) -> None:
        query = """
        INSERT INTO ticket_panels (id, channel_id, guild_id, limit_per_user, panel_title, panel_description, panel_moderators)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        await db.execute(query, panel_id, channel_id, guild_id, limit_per_user,
                         panel_title, panel_description, panel_moderators)

    @staticmethod
    async def get_panel_data(panel_id: int) -> Optional[Dict]:
        query = "SELECT * FROM ticket_panels WHERE id = $1 AND deleted = FALSE"
        result = await db.fetch(query, panel_id)
        return dict(result[0]) if result else None

    @staticmethod
    async def edit_panel_data(panel_id: int, field: str, value: any) -> None:
        if field == "delete":
            query = "UPDATE ticket_panels SET deleted = TRUE WHERE id = $1"
            await db.execute(query, panel_id)
            return

        query = f"UPDATE ticket_panels SET {field} = $1 WHERE id = $2"
        await db.execute(query, value, panel_id)

    @staticmethod
    async def create_ticket(panel_id: int, ticket_id: int,
                            creator_id: int) -> None:
        query = """
        INSERT INTO tickets (panel_id, ticket_id, ticket_creator)
        VALUES ($1, $2, $3)
        """
        await db.execute(query, panel_id, ticket_id, creator_id)

    @staticmethod
    async def get_ticket_data(panel_id: int, ticket_id: int) -> Optional[Dict]:
        query = "SELECT * FROM tickets WHERE panel_id = $1 AND ticket_id = $2"
        result = await db.fetch(query, panel_id, ticket_id)
        return dict(result[0]) if result else None

    @staticmethod
    async def close_ticket(panel_id: int, ticket_id: int) -> None:
        query = "UPDATE tickets SET closed = TRUE WHERE panel_id = $1 AND ticket_id = $2"
        await db.execute(query, panel_id, ticket_id)

    @staticmethod
    async def open_ticket(panel_id: int, ticket_id: int) -> None:
        query = "UPDATE tickets SET closed = FALSE WHERE panel_id = $1 AND ticket_id = $2"
        await db.execute(query, panel_id, ticket_id)

    @staticmethod
    async def get_all_tickets() -> List[Dict]:
        query = "SELECT * FROM tickets"
        results = await db.fetch(query)
        return [dict(row) for row in results]

    @staticmethod
    async def get_all_panels() -> List[Dict]:
        query = "SELECT * FROM ticket_panels WHERE deleted = FALSE"
        results = await db.fetch(query)
        return [dict(row) for row in results]

    @staticmethod
    async def get_panel_id_by_ticket_id(ticket_id: int) -> Optional[int]:
        query = "SELECT panel_id FROM tickets WHERE ticket_id = $1"
        result = await db.fetch(query, ticket_id)
        return result[0]['panel_id'] if result else None
