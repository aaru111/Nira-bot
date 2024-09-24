import discord
from discord import app_commands
from discord.ext import commands
import random
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io
from database import db
import time
from typing import Optional, Dict, Union, List
import os
import base64


class XPRateSelect(discord.ui.Select):

    def __init__(self, current_min: int, current_max: int):
        options = [
            discord.SelectOption(label='Low (5-15 XP)',
                                 description='Slower progression',
                                 value='5,15'),
            discord.SelectOption(label='Medium (10-20 XP)',
                                 description='Balanced progression',
                                 value='10,20'),
            discord.SelectOption(label='High (15-25 XP)',
                                 description='Faster progression',
                                 value='15,25')
        ]
        current_option = next((opt for opt in options
                               if opt.value == f"{current_min},{current_max}"),
                              None)
        placeholder = f'XP Rate: {current_min}-{current_max}'
        if current_option:
            placeholder = f'XP Rate: {current_option.label}'
        super().__init__(placeholder=placeholder, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.xp_min, self.view.xp_max = map(int,
                                                 self.values[0].split(','))
        selected_option = next(opt for opt in self.options
                               if opt.value == self.values[0])
        self.placeholder = f'XP Rate: {selected_option.label}'
        await self.view.update_embed(interaction)


class XPCooldownSelect(discord.ui.Select):

    def __init__(self, current_cooldown: int):
        options = [
            discord.SelectOption(label='Short (30 seconds)',
                                 description='More frequent XP gains',
                                 value='30'),
            discord.SelectOption(label='Medium (60 seconds)',
                                 description='Balanced XP gains',
                                 value='60'),
            discord.SelectOption(label='Long (120 seconds)',
                                 description='Less frequent XP gains',
                                 value='120')
        ]
        current_option = next(
            (opt for opt in options if opt.value == str(current_cooldown)),
            None)
        placeholder = f'XP Cooldown: {current_cooldown}s'
        if current_option:
            placeholder = f'XP Cooldown: {current_option.label}'
        super().__init__(placeholder=placeholder, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.xp_cooldown = int(self.values[0])
        selected_option = next(opt for opt in self.options
                               if opt.value == self.values[0])
        self.placeholder = f'XP Cooldown: {selected_option.label}'
        await self.view.update_embed(interaction)


class ToggleButton(discord.ui.Button):

    def __init__(self, is_enabled: bool):
        super().__init__(style=discord.ButtonStyle.green
                         if is_enabled else discord.ButtonStyle.red,
                         label='Enabled' if is_enabled else 'Disabled',
                         custom_id='toggle')

    async def callback(self, interaction: discord.Interaction):
        self.view.is_enabled = not self.view.is_enabled
        self.style = discord.ButtonStyle.green if self.view.is_enabled else discord.ButtonStyle.red
        self.label = 'Enabled' if self.view.is_enabled else 'Disabled'
        await self.view.update_embed(interaction)


class AnnouncementChannelSelect(discord.ui.ChannelSelect):

    def __init__(self, current_channel_id: Optional[int]):
        super().__init__(
            channel_types=[discord.ChannelType.text],
            placeholder=
            f'Announcement Channel: {current_channel_id or "Not set"}',
            min_values=0,
            max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.announcement_channel = self.values[
            0].id if self.values else None
        await self.view.update_embed(interaction)


class LevelUpMessageModal(discord.ui.Modal, title='Edit Level Up Message'):
    message = discord.ui.TextInput(
        label='New Level Up Message',
        style=discord.TextStyle.paragraph,
        placeholder=
        'Enter the new level up message... Use {user_mention}, {new_level}, and {role_rewards} as placeholders.',
        required=True,
        max_length=1000)

    def __init__(self, current_message: str, view: 'SetupView'):
        super().__init__()
        self.message.default = current_message
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.view.level_up_message = self.message.value
        await self.view.update_embed(interaction)
        self.stop()


class ConfirmView(discord.ui.View):

    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        self.value = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        self.value = False
        self.stop()


class SetupView(discord.ui.View):

    def __init__(self, guild_settings: Dict[str, int | bool | Optional[int]],
                 role_rewards: Dict[int, int]):
        super().__init__()
        self.xp_min: int = guild_settings['xp_min']
        self.xp_max: int = guild_settings['xp_max']
        self.xp_cooldown: int = guild_settings['xp_cooldown']
        self.is_enabled: bool = guild_settings['enabled']
        self.announcement_channel: Optional[int] = guild_settings.get(
            'announcement_channel')
        self.level_up_message: str = guild_settings.get(
            'level_up_message',
            "Congratulations {user_mention}! You've reached level {new_level}!"
        )
        self.confirmed: bool = False
        self.role_rewards: Dict[int, int] = role_rewards
        self.message = None

        self.add_item(ToggleButton(self.is_enabled))
        self.add_item(XPRateSelect(self.xp_min, self.xp_max))
        self.add_item(XPCooldownSelect(self.xp_cooldown))
        self.add_item(AnnouncementChannelSelect(self.announcement_channel))

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)

    @discord.ui.button(label='Edit Level Up Message',
                       style=discord.ButtonStyle.blurple)
    async def edit_message_button(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
        modal = LevelUpMessageModal(self.level_up_message, self)
        await interaction.response.send_modal(modal)
        await modal.wait()

    @discord.ui.button(label='Reset All Levels',
                       style=discord.ButtonStyle.danger)
    async def reset_levels_button(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
        confirm_view = ConfirmView()
        await interaction.response.send_message(
            "Are you sure you want to reset all levels?",
            view=confirm_view,
            ephemeral=True)
        await confirm_view.wait()
        if confirm_view.value:
            query = "DELETE FROM user_levels WHERE guild_id = $1;"
            await db.execute(query, interaction.guild_id)
            await interaction.followup.send("All levels have been reset.",
                                            ephemeral=True)
        else:
            await interaction.followup.send("Level reset cancelled.",
                                            ephemeral=True)

    @discord.ui.button(label='Save Changes', style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
        self.confirmed = True
        await interaction.response.edit_message(content='Setup confirmed!',
                                                view=None,
                                                embed=None)
        self.stop()

    async def update_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🛠️ Leveling System Configuration",
                              color=discord.Color.blue())
        embed.add_field(name="Status",
                        value="🟢 Enabled" if self.is_enabled else "🔴 Disabled",
                        inline=False)
        embed.add_field(name="XP Range",
                        value=f"{self.xp_min}-{self.xp_max}",
                        inline=True)
        embed.add_field(name="XP Cooldown",
                        value=f"{self.xp_cooldown} seconds",
                        inline=True)
        embed.add_field(name="Announcement Channel",
                        value=f"<#{self.announcement_channel}>"
                        if self.announcement_channel else "Not set",
                        inline=False)
        embed.add_field(name="Level Up Message",
                        value=f"```{self.level_up_message}```",
                        inline=False)

        # Add role rewards fields
        sorted_rewards = sorted(self.role_rewards.items())
        for i in range(0, len(sorted_rewards), 6):
            chunk = sorted_rewards[i:i + 6]
            value = "\n".join(
                [f"Level {level}: <@&{role_id}>" for level, role_id in chunk])
            embed.add_field(name=f"Role Rewards {i//6 + 1}",
                            value=value or "No rewards set",
                            inline=True)

        await interaction.response.edit_message(embed=embed, view=self)


class Leveling(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.leveling_settings: Dict[int,
                                     Dict[str,
                                          int | bool | Optional[int]]] = {}
        self.cooldowns: Dict[int, Dict[int, float]] = {}
        self.default_level_up_message: str = "Congratulations {user_mention}! You've reached level {new_level}! {role_rewards}"
        self.role_rewards: Dict[int, Dict[int, int]] = {}

    async def cog_load(self):
        await db.initialize()
        await self.create_tables()
        await self.load_settings()
        await self.load_role_rewards()

    async def cog_unload(self):
        await self.db.close()

    async def is_premium(self, user_id: int) -> bool:
        query = "SELECT is_premium FROM users WHERE user_id = $1;"
        result = await db.fetch(query, user_id)
        return bool(result) and result[0]['is_premium']

    async def send_level_up_message(
            self, context: Union[discord.Interaction, discord.Message],
            new_level: int, guild_settings: Dict[str,
                                                 int | bool | Optional[int]],
            awarded_roles: list):
        if isinstance(context, discord.Interaction):
            user = context.user
            guild_id = context.guild_id
        else:  # discord.Message
            user = context.author
            guild_id = context.guild.id

        user_id = user.id

        # Get updated XP and rank
        query = """
        SELECT xp, 
               (SELECT COUNT(*) FROM user_levels ul2 
                WHERE ul2.guild_id = $2 AND ul2.xp > ul1.xp) + 1 AS rank
        FROM user_levels ul1
        WHERE user_id = $1 AND guild_id = $2;
        """
        result = await db.fetch(query, user_id, guild_id)
        if not result:
            return  # User not found in database

        xp, rank = result[0]['xp'], result[0]['rank']

        # Create rank card
        rank_card = await self.create_rank_card(user, xp, new_level, rank)

        role_rewards_text = f"You've earned the following role(s): {', '.join([role.name for role in awarded_roles])}" if awarded_roles else ""
        level_up_message = guild_settings['level_up_message'].format(
            user_mention=user.mention,
            new_level=new_level,
            role_rewards=role_rewards_text)

        file = discord.File(rank_card, filename="rank_card.png")

        if guild_settings['announcement_channel']:
            channel = self.bot.get_channel(
                guild_settings['announcement_channel'])
            if channel:
                await channel.send(content=level_up_message, file=file)
        else:
            # Send in the original channel if no announcement channel is set
            if isinstance(context, discord.Interaction):
                await context.followup.send(content=level_up_message,
                                            file=file)
            else:
                await context.channel.send(content=level_up_message, file=file)

    async def create_tables(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS user_levels (
                user_id BIGINT,
                guild_id BIGINT,
                xp INT DEFAULT 0,
                level INT DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );
            """, """
            CREATE TABLE IF NOT EXISTS guild_leveling_settings (
                guild_id BIGINT PRIMARY KEY,
                enabled BOOLEAN DEFAULT FALSE,
                xp_min INT DEFAULT 10,
                xp_max INT DEFAULT 20,
                xp_cooldown INT DEFAULT 60,
                announcement_channel BIGINT,
                level_up_message TEXT
            );
            """, """
            CREATE TABLE IF NOT EXISTS level_role_rewards (
                guild_id BIGINT,
                level INT,
                role_id BIGINT,
                PRIMARY KEY (guild_id, level)
            );
            """, """
            CREATE TABLE IF NOT EXISTS user_backgrounds (
                user_id BIGINT,
                guild_id BIGINT,
                background TEXT,
                PRIMARY KEY (user_id, guild_id)
            );
            """
        ]

        changes_made = False

        for query in queries:
            try:
                result = await db.execute(query)
                if result and "CREATE TABLE" in result:
                    changes_made = True
            except Exception as e:
                print(f"Error executing query: {e}")
                print(f"Query: {query}")

        check_columns_query = """
        DO $$
        DECLARE
            column_added BOOLEAN := FALSE;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='guild_leveling_settings' AND column_name='announcement_channel') THEN
                ALTER TABLE guild_leveling_settings ADD COLUMN announcement_channel BIGINT;
                column_added := TRUE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='guild_leveling_settings' AND column_name='level_up_message') THEN
                ALTER TABLE guild_leveling_settings ADD COLUMN level_up_message TEXT;
                column_added := TRUE;
            END IF;
            IF column_added THEN
                RAISE NOTICE 'Columns added';
            END IF;
        END $$;
        """

        try:
            result = await db.execute(check_columns_query)
            if result and "NOTICE" in result:
                changes_made = True
        except Exception as e:
            print(f"Error checking/adding columns: {e}")

        if changes_made:
            print("Database tables and columns checked/created successfully.")

    async def load_settings(self):
        try:
            query = "SELECT * FROM guild_leveling_settings;"
            results = await db.fetch(query)
            for row in results:
                self.leveling_settings[row['guild_id']] = {
                    'enabled':
                    row['enabled'],
                    'xp_min':
                    row['xp_min'],
                    'xp_max':
                    row['xp_max'],
                    'xp_cooldown':
                    row['xp_cooldown'],
                    'announcement_channel':
                    row.get('announcement_channel'),
                    'level_up_message':
                    row.get('level_up_message')
                    or self.default_level_up_message
                }
        except Exception as e:
            print(f"Error loading settings: {e}")

    async def load_role_rewards(self):
        try:
            query = "SELECT * FROM level_role_rewards;"
            results = await db.fetch(query)
            for row in results:
                guild_id = row['guild_id']
                if guild_id not in self.role_rewards:
                    self.role_rewards[guild_id] = {}
                self.role_rewards[guild_id][row['level']] = row['role_id']
        except Exception as e:
            print(f"Error loading role rewards: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_settings = self.leveling_settings.get(message.guild.id)
        if not guild_settings or not guild_settings['enabled']:
            return

        user_id = message.author.id
        guild_id = message.guild.id

        current_time = time.time()
        if guild_id not in self.cooldowns:
            self.cooldowns[guild_id] = {}
        last_message_time = self.cooldowns[guild_id].get(user_id, 0)
        if current_time - last_message_time < guild_settings['xp_cooldown']:
            return

        xp_gained = random.randint(guild_settings['xp_min'],
                                   guild_settings['xp_max'])
        leveled_up, new_level = await self.add_xp(user_id, guild_id, xp_gained)
        self.cooldowns[guild_id][user_id] = current_time

        if leveled_up:
            awarded_roles = await self.check_and_award_role(
                message.author, new_level)
            await self.send_level_up_message(message, new_level,
                                             guild_settings, awarded_roles)

    async def add_xp(self, user_id: int, guild_id: int,
                     xp: int) -> tuple[bool, int]:
        query = """
        INSERT INTO user_levels (user_id, guild_id, xp, level)
        VALUES ($1, $2, $3, 0)
        ON CONFLICT (user_id, guild_id)
        DO UPDATE SET xp = user_levels.xp + $3
        RETURNING xp, level;
        """
        result = await db.fetch(query, user_id, guild_id, xp)
        new_xp, current_level = result[0]['xp'], result[0]['level']

        new_level = self.calculate_level(new_xp)
        if new_level > current_level:
            await self.update_level(user_id, guild_id, new_level)
            return True, new_level
        return False, current_level

    def calculate_level(self, xp: int) -> int:
        return int((xp // 100)**0.5)

    async def update_level(self, user_id: int, guild_id: int, new_level: int):
        query = """
        UPDATE user_levels
        SET level = $3
        WHERE user_id = $1 AND guild_id = $2;
        """
        await db.execute(query, user_id, guild_id, new_level)

    async def get_level(self, user_id: int, guild_id: int) -> int:
        query = "SELECT level FROM user_levels WHERE user_id = $1 AND guild_id = $2;"
        result = await db.fetch(query, user_id, guild_id)
        return result[0]['level'] if result else 0

    level_group = app_commands.Group(name="level",
                                     description="Leveling system commands")

    async def create_rank_card(self, member: discord.Member, xp: int,
                               level: int, rank: int) -> io.BytesIO:
        card_width, card_height = 800, 200

        query = "SELECT background FROM user_backgrounds WHERE user_id = $1 AND guild_id = $2;"
        result = await db.fetch(query, member.id, member.guild.id)
        background_data = result[0]['background'] if result else None

        if background_data:
            try:
                image_data = base64.b64decode(background_data)
                background = Image.open(io.BytesIO(image_data)).convert('RGBA')

                # Calculate scaling factor to cover the card while maintaining aspect ratio
                bg_ratio = background.width / background.height
                card_ratio = card_width / card_height

                if bg_ratio > card_ratio:
                    new_height = card_height
                    new_width = int(new_height * bg_ratio)
                else:
                    new_width = card_width
                    new_height = int(new_width / bg_ratio)

                background = background.resize((new_width, new_height),
                                               Image.Resampling.LANCZOS)

                # Crop to fit
                left = (background.width - card_width) // 2
                top = (background.height - card_height) // 2
                background = background.crop(
                    (left, top, left + card_width, top + card_height))

                card = Image.new('RGBA', (card_width, card_height),
                                 (0, 0, 0, 0))
                card.paste(background, (0, 0), background)
            except:
                # If there's an error with the custom background, fall back to default
                card = Image.new('RGBA', (card_width, card_height),
                                 (0, 0, 0, 0))
        else:
            card = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))

            gradient = Image.new('RGBA', (card_width, card_height),
                                 (0, 0, 0, 0))
            gradient_draw = ImageDraw.Draw(gradient)

            avatar_size = 150
            avatar_url = member.display_avatar.replace(format='png', size=256)
            avatar_data = io.BytesIO(await avatar_url.read())
            avatar_image = Image.open(avatar_data).convert('RGBA')
            avatar_image = avatar_image.resize((avatar_size, avatar_size),
                                               Image.Resampling.LANCZOS)

            try:
                avatar_colors = avatar_image.getcolors(avatar_image.size[0] *
                                                       avatar_image.size[1])
                dominant_color = max(avatar_colors, key=lambda x: x[0])[1][:3]
            except:
                dominant_color = (100, 100, 100)

            for y in range(card_height):
                alpha = int(255 * (1 - y / card_height))
                gradient_draw.line([(0, y), (card_width, y)],
                                   fill=dominant_color + (alpha, ))

            card = Image.alpha_composite(card, gradient)

        # Avatar
        avatar_size = 150
        avatar_url = member.display_avatar.replace(format='png', size=256)
        avatar_data = io.BytesIO(await avatar_url.read())
        avatar_image = Image.open(avatar_data).convert('RGBA')
        avatar_image = avatar_image.resize((avatar_size, avatar_size),
                                           Image.Resampling.LANCZOS)

        mask = Image.new('L', (avatar_size, avatar_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

        card.paste(avatar_image, (25, 25), mask)

        # Text
        draw = ImageDraw.Draw(card)

        try:
            title_font = ImageFont.truetype("fonts/ndot47.ttf", 40)
            text_font = ImageFont.truetype("fonts/InterVariable.ttf", 28)
            xp_font = ImageFont.truetype("fonts/InterVariable.ttf", 20)
        except IOError:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
            xp_font = ImageFont.load_default()

        draw.text((200, 13),
                  member.display_name,
                  font=title_font,
                  fill=(255, 255, 255, 255))
        draw.text((200, 71),
                  f"Rank: #{rank}",
                  font=text_font,
                  fill=(255, 255, 255, 255))
        draw.text((200, 107),
                  f"Level: {level}",
                  font=text_font,
                  fill=(255, 255, 255, 255))

        # XP Bar
        xp_to_next_level = (level + 1)**2 * 100
        progress = xp / xp_to_next_level
        bar_width, bar_height = 500, 30
        bar_x, bar_y = 200, 151

        def rounded_rectangle(size, radius):
            rect = Image.new('RGBA', size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(rect)
            draw.rounded_rectangle([(0, 0), size],
                                   radius,
                                   fill=(255, 255, 255, 255))
            return rect

        bar_bg = rounded_rectangle((bar_width, bar_height), bar_height // 2)
        bar_bg = ImageEnhance.Brightness(bar_bg).enhance(0.2)
        card.paste(bar_bg, (bar_x, bar_y), bar_bg)

        start_color = (138, 43, 226)
        end_color = (75, 0, 130)

        progress_width = int(bar_width * progress)
        progress_bar = Image.new('RGBA', (progress_width, bar_height),
                                 (0, 0, 0, 0))
        progress_draw = ImageDraw.Draw(progress_bar)
        for x in range(progress_width):
            r = int(start_color[0] + (end_color[0] - start_color[0]) *
                    (x / progress_width))
            g = int(start_color[1] + (end_color[1] - start_color[1]) *
                    (x / progress_width))
            b = int(start_color[2] + (end_color[2] - start_color[2]) *
                    (x / progress_width))
            progress_draw.line([(x, 0), (x, bar_height)], fill=(r, g, b, 255))

        progress_mask = rounded_rectangle((progress_width, bar_height),
                                          bar_height // 2)
        card.paste(progress_bar, (bar_x, bar_y), progress_mask)

        xp_text = f"{xp}/{xp_to_next_level} XP"
        bbox = draw.textbbox((0, 0), xp_text, font=xp_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = bar_x + (bar_width - text_width) // 2
        text_y = bar_y + (bar_height - text_height) // 2 - 1

        draw.text((text_x, text_y),
                  xp_text,
                  font=xp_font,
                  fill=(255, 255, 255, 255))

        buffer = io.BytesIO()
        card.save(buffer, 'PNG')
        buffer.seek(0)
        return buffer

    @level_group.command(name="rank")
    async def rank(self,
                   interaction: discord.Interaction,
                   member: Optional[discord.Member] = None):
        """Check your or another member's rank"""
        await interaction.response.defer()
        try:
            guild_settings = self.leveling_settings.get(interaction.guild_id)
            if not guild_settings or not guild_settings['enabled']:
                return await interaction.followup.send(
                    "Leveling system is not enabled in this server.",
                    ephemeral=True)

            member = member or interaction.user
            user_id, guild_id = member.id, interaction.guild_id

            # First, get all users' XP and calculate ranks
            query = """
            SELECT user_id, xp, level,
                   ROW_NUMBER() OVER (ORDER BY xp DESC) as rank
            FROM user_levels
            WHERE guild_id = $1
            ORDER BY xp DESC;
            """
            all_results = await db.fetch(query, guild_id)

            user_data = next(
                (r for r in all_results if r['user_id'] == user_id), None)

            if not user_data:
                return await interaction.followup.send(
                    f"{member.display_name} has not gained any XP yet.",
                    ephemeral=True)

            xp, level, rank = user_data['xp'], user_data['level'], user_data[
                'rank']
            card = await self.create_rank_card(member, xp, level, rank)

            await interaction.followup.send(
                file=discord.File(card, filename="rank_card.png"))
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}",
                                            ephemeral=True)

    def create_setup_embed(self,
                           settings: dict,
                           role_rewards: dict,
                           is_confirmation: bool = False) -> discord.Embed:
        """Create an embed for the setup wizard or confirmation"""
        title = "✅ Leveling System Setup Complete!" if is_confirmation else "🛠️ Leveling System Setup Wizard"
        color = discord.Color.green(
        ) if is_confirmation else discord.Color.blue()

        embed = discord.Embed(title=title, color=color)
        embed.add_field(
            name="Status",
            value="🟢 Enabled" if settings['enabled'] else "🔴 Disabled",
            inline=False)
        embed.add_field(name="XP Range",
                        value=f"{settings['xp_min']}-{settings['xp_max']}",
                        inline=True)
        embed.add_field(name="XP Cooldown",
                        value=f"{settings['xp_cooldown']} seconds",
                        inline=True)
        embed.add_field(name="Announcement Channel",
                        value=f"<#{settings['announcement_channel']}>"
                        if settings['announcement_channel'] else "Not set",
                        inline=False)
        embed.add_field(name="Level Up Message",
                        value=f"```{settings['level_up_message']}```",
                        inline=False)

        # Add role rewards fields
        sorted_rewards = sorted(role_rewards.items())
        for i in range(0, len(sorted_rewards), 6):
            chunk = sorted_rewards[i:i + 6]
            value = "\n".join(
                [f"Level {level}: <@&{role_id}>" for level, role_id in chunk])
            embed.add_field(name=f"Role Rewards {i//6 + 1}",
                            value=value or "No rewards set",
                            inline=True)

        if not is_confirmation:
            embed.set_footer(
                text=
                "Use the buttons and dropdowns below to configure the leveling system."
            )

        return embed

    @level_group.command(name="setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_wizard(self, interaction: discord.Interaction):
        """Setup wizard for the leveling system"""
        guild_settings = self.leveling_settings.get(
            interaction.guild_id, {
                'enabled': False,
                'xp_min': 10,
                'xp_max': 20,
                'xp_cooldown': 60,
                'announcement_channel': None,
                'level_up_message': self.default_level_up_message
            })

        # Fetch role rewards for the guild
        role_rewards = self.role_rewards.get(interaction.guild_id, {})

        view = SetupView(guild_settings, role_rewards)
        embed = self.create_setup_embed(guild_settings, role_rewards)

        await interaction.response.send_message(embed=embed,
                                                view=view,
                                                ephemeral=True)

        timeout = await view.wait()
        if timeout:
            await interaction.edit_original_response(
                content="⏱️ Setup wizard timed out. No changes were made.",
                embed=None,
                view=None)
            return

        if view.confirmed:
            new_settings = {
                'enabled': view.is_enabled,
                'xp_min': view.xp_min,
                'xp_max': view.xp_max,
                'xp_cooldown': view.xp_cooldown,
                'announcement_channel': view.announcement_channel,
                'level_up_message': view.level_up_message
            }
            self.leveling_settings[interaction.guild_id] = new_settings

            query = """
            INSERT INTO guild_leveling_settings (guild_id, enabled, xp_min, xp_max, xp_cooldown, announcement_channel, level_up_message)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (guild_id)
            DO UPDATE SET enabled = $2, xp_min = $3, xp_max = $4, xp_cooldown = $5, announcement_channel = $6, level_up_message = $7;
            """
            await db.execute(query, interaction.guild_id, view.is_enabled,
                             view.xp_min, view.xp_max, view.xp_cooldown,
                             view.announcement_channel, view.level_up_message)

            confirmation_embed = self.create_setup_embed(new_settings,
                                                         view.role_rewards,
                                                         is_confirmation=True)
            await interaction.edit_original_response(embed=confirmation_embed,
                                                     view=None)
        else:
            await interaction.edit_original_response(
                content="❌ Setup cancelled. No changes were made.",
                embed=None,
                view=None)

    @setup_wizard.error
    async def setup_wizard_error(self, interaction: discord.Interaction,
                                 error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "You don't have permission to use this command. Administrator permission is required.",
                    ephemeral=True)
            else:
                await interaction.followup.send(
                    "You don't have permission to use this command. Administrator permission is required.",
                    ephemeral=True)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"An error occurred: {str(error)}", ephemeral=True)
            else:
                await interaction.followup.send(
                    f"An error occurred: {str(error)}", ephemeral=True)

    @level_group.command(name="leaderboard")
    async def leaderboard(self,
                          interaction: discord.Interaction,
                          top: int = 10):
        """Show the server's XP leaderboard"""
        await interaction.response.defer()
        try:
            guild_settings = self.leveling_settings.get(interaction.guild_id)
            if not guild_settings or not guild_settings['enabled']:
                return await interaction.followup.send(
                    "Leveling system is not enabled in this server.",
                    ephemeral=True)

            query = """
            SELECT user_id, xp, level,
                   ROW_NUMBER() OVER (ORDER BY xp DESC) as rank
            FROM user_levels
            WHERE guild_id = $1
            ORDER BY xp DESC
            LIMIT $2;
            """
            results = await db.fetch(query, interaction.guild_id, top)

            if not results:
                return await interaction.followup.send(
                    "No one has gained any XP yet.", ephemeral=True)

            embed = discord.Embed(title="🏆 XP Leaderboard",
                                  color=discord.Color.gold())
            for row in results:
                user = interaction.guild.get_member(row['user_id'])
                if user:
                    embed.add_field(
                        name=f"{row['rank']}. {user.display_name}",
                        value=f"Level: {row['level']} (XP: {row['xp']})",
                        inline=False)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}",
                                            ephemeral=True)

    @level_group.command(name="give")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def give_levels(self, interaction: discord.Interaction,
                          member: discord.Member, levels: int):
        await interaction.response.defer()
        try:
            guild_settings = self.leveling_settings.get(interaction.guild_id)
            if not guild_settings or not guild_settings['enabled']:
                return await interaction.followup.send(
                    "Leveling system is not enabled in this server.",
                    ephemeral=True)

            user_id, guild_id = member.id, interaction.guild_id

            # Get current XP and level
            query = "SELECT xp, level FROM user_levels WHERE user_id = $1 AND guild_id = $2;"
            result = await db.fetch(query, user_id, guild_id)

            if not result:
                current_xp, current_level = 0, 0
            else:
                current_xp, current_level = result[0]['xp'], result[0]['level']

            # Calculate new level and XP
            new_level = max(0, current_level +
                            levels)  # Ensure level doesn't go below 0
            new_xp = new_level**2 * 100  # Ensure XP is at least the minimum for the new level

            # Update database
            query = """
            INSERT INTO user_levels (user_id, guild_id, xp, level)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, guild_id)
            DO UPDATE SET xp = $3, level = $4;
            """
            await db.execute(query, user_id, guild_id, new_xp, new_level)

            awarded_roles = []
            removed_roles = []

            if levels > 0:
                # Check and award roles for all levels up to and including the new level
                for level in range(current_level + 1, new_level + 1):
                    awarded_roles.extend(await self.check_and_award_role(
                        member, level))
            elif levels < 0:
                # Remove roles that the user no longer qualifies for
                for level in range(current_level, new_level, -1):
                    removed_roles.extend(await self.check_and_remove_role(
                        member, level))

            # Remove duplicates while preserving order
            unique_awarded_roles = list(dict.fromkeys(awarded_roles))
            unique_removed_roles = list(dict.fromkeys(removed_roles))

            if levels > 0:
                # Announce level up and role rewards
                await self.send_level_up_message(interaction, new_level,
                                                 guild_settings,
                                                 unique_awarded_roles)

            awarded_text = f"They were awarded: `{', '.join([role.name for role in unique_awarded_roles])}`." if unique_awarded_roles else ""
            removed_text = f"They lost the following roles: `{', '.join([role.name for role in unique_removed_roles])}`." if unique_removed_roles else ""

            level_change_text = "increased" if levels > 0 else "decreased"
            await interaction.followup.send(
                f"Successfully {level_change_text} {member.mention}'s level by {abs(levels)}. Their new level is {new_level}. {awarded_text} {removed_text}"
            )

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}",
                                            ephemeral=True)

    @level_group.command(name="set_role_reward")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def set_role_reward(self, interaction: discord.Interaction,
                              level: int, role: discord.Role):
        """Set a role reward for reaching a specific level"""
        await interaction.response.defer()
        try:
            guild_settings = self.leveling_settings.get(interaction.guild_id)
            if not guild_settings or not guild_settings['enabled']:
                return await interaction.followup.send(
                    "Leveling system is not enabled in this server.",
                    ephemeral=True)

            if level <= 0:
                return await interaction.followup.send(
                    "Please specify a positive level number.", ephemeral=True)

            # Check if the bot can manage the role
            if role >= interaction.guild.me.top_role:
                return await interaction.followup.send(
                    "I cannot manage this role as it's higher than or equal to my highest role.",
                    ephemeral=True)

            # Update database
            query = """
            INSERT INTO level_role_rewards (guild_id, level, role_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, level)
            DO UPDATE SET role_id = $3;
            """
            await db.execute(query, interaction.guild_id, level, role.id)

            # Update local cache
            if interaction.guild_id not in self.role_rewards:
                self.role_rewards[interaction.guild_id] = {}
            self.role_rewards[interaction.guild_id][level] = role.id

            await interaction.followup.send(
                f"Successfully set `@{role.name}` as the reward for reaching level {level}."
            )

            # Update the setup wizard if it's open
            for view in self.bot.persistent_views:
                if isinstance(
                        view, SetupView
                ) and view.message.guild.id == interaction.guild_id:
                    view.role_rewards = self.role_rewards[interaction.guild_id]
                    await view.update_embed(interaction)
                    break

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}",
                                            ephemeral=True)

    @set_role_reward.error
    async def set_role_reward_error(self, interaction: discord.Interaction,
                                    error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command. 'Manage Roles' permission is required.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                f"An error occurred: {str(error)}", ephemeral=True)

    async def check_and_award_role(self, member: discord.Member,
                                   new_level: int):
        guild_id = member.guild.id
        awarded_roles = []
        if guild_id in self.role_rewards:
            for level, role_id in sorted(self.role_rewards[guild_id].items()):
                if new_level >= level:
                    role = member.guild.get_role(role_id)
                    if role and role not in member.roles:
                        try:
                            await member.add_roles(role)
                            awarded_roles.append(role)
                        except discord.Forbidden:
                            print(
                                f"Failed to add role {role.name} to {member.name} due to insufficient permissions."
                            )
        return awarded_roles

    @level_group.command(name="reset")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reset_user(self, interaction: discord.Interaction,
                         member: discord.Member):
        """Reset the level and XP of a specific user"""
        await interaction.response.defer()
        try:
            guild_settings = self.leveling_settings.get(interaction.guild_id)
            if not guild_settings or not guild_settings['enabled']:
                return await interaction.followup.send(
                    "Leveling system is not enabled in this server.",
                    ephemeral=True)

            user_id, guild_id = member.id, interaction.guild_id

            # Get current level
            query = "SELECT level FROM user_levels WHERE user_id = $1 AND guild_id = $2;"
            result = await db.fetch(query, user_id, guild_id)

            if not result:
                return await interaction.followup.send(
                    f"{member.mention} has no levels to reset.",
                    ephemeral=True)

            current_level = result[0]['level']

            # Reset user's XP and level
            query = """
            UPDATE user_levels
            SET xp = 0, level = 0
            WHERE user_id = $1 AND guild_id = $2;
            """
            await db.execute(query, user_id, guild_id)

            # Remove all level-based roles
            removed_roles = []
            for level in range(1, current_level + 1):
                removed_roles.extend(await
                                     self.check_and_remove_role(member, level))

            # Remove duplicates while preserving order
            unique_removed_roles = list(dict.fromkeys(removed_roles))

            removed_text = f"They lost the following roles: `{', '.join([role.name for role in unique_removed_roles])}`." if unique_removed_roles else ""

            await interaction.followup.send(
                f"Successfully reset {member.mention}'s level and XP to 0. {removed_text}"
            )

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}",
                                            ephemeral=True)

    @reset_user.error
    async def reset_user_error(self, interaction: discord.Interaction,
                               error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command. 'Manage Roles' permission is required.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                f"An error occurred: {str(error)}", ephemeral=True)

    async def check_and_remove_role(self, member: discord.Member, level: int):
        guild_id = member.guild.id
        removed_roles = []
        if guild_id in self.role_rewards:
            for reward_level, role_id in sorted(
                    self.role_rewards[guild_id].items(), reverse=True):
                if level <= reward_level:
                    role = member.guild.get_role(role_id)
                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role)
                            removed_roles.append(role)
                        except discord.Forbidden:
                            print(
                                f"Failed to remove role {role.name} from {member.name} due to insufficient permissions."
                            )
        return removed_roles

    @level_group.command(name="card")
    async def card(self,
                   interaction: discord.Interaction,
                   image: Optional[discord.Attachment] = None):
        """Set the background for your rank card"""
        await interaction.response.defer(ephemeral=True)
        try:
            if image:
                is_premium = await self.is_premium(interaction.user.id)
                if not is_premium:
                    await interaction.followup.send(
                        "Custom image backgrounds are only available for premium users. You can still choose from pre-configured backgrounds, by running the `/level card` command again without using a custom picture.",
                        ephemeral=True)
                    return

                if not image.content_type.startswith('image/'):
                    await interaction.followup.send(
                        "Please upload a valid image file.", ephemeral=True)
                    return

                image_data = await image.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')

                query = """
                INSERT INTO user_backgrounds (user_id, guild_id, background)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, guild_id)
                DO UPDATE SET background = $3;
                """
                await db.execute(query, interaction.user.id,
                                 interaction.guild_id, image_base64)

                await interaction.followup.send(
                    "Your rank card background has been updated with your custom image.",
                    ephemeral=True)
            else:
                backgrounds_dir = "backgrounds"
                background_files = [
                    f for f in os.listdir(backgrounds_dir)
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                ]

                if not background_files:
                    await interaction.followup.send(
                        "No background options are available at the moment.",
                        ephemeral=True)
                    return

                options = [
                    discord.SelectOption(label=bg.split('.')[0], value=bg)
                    for bg in background_files
                ]

                view = BackgroundView(options, interaction.user.id,
                                      interaction.guild_id)
                await interaction.followup.send(
                    "Choose a background for your rank card:",
                    view=view,
                    ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}",
                                            ephemeral=True)

    @card.error
    async def card_error(self, interaction: discord.Interaction,
                         error: app_commands.AppCommandError):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"An error occurred: {str(error)}", ephemeral=True)
        else:
            await interaction.followup.send(f"An error occurred: {str(error)}",
                                            ephemeral=True)


class BackgroundSelect(discord.ui.Select):

    def __init__(self, options: List[discord.SelectOption], user_id: int,
                 guild_id: int):
        super().__init__(placeholder="Choose a background", options=options)
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        background = self.values[0]

        with open(os.path.join("backgrounds", background), "rb") as image_file:
            image_data = image_file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')

        query = """
        INSERT INTO user_backgrounds (user_id, guild_id, background)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, guild_id)
        DO UPDATE SET background = $3;
        """
        await db.execute(query, self.user_id, self.guild_id, image_base64)

        await interaction.followup.send(
            f"Your rank card background has been updated to {background}.",
            ephemeral=True)


class BackgroundView(discord.ui.View):

    def __init__(self, options: List[discord.SelectOption], user_id: int,
                 guild_id: int):
        super().__init__()
        self.add_item(BackgroundSelect(options, user_id, guild_id))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leveling(bot))
