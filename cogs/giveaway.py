# giveaway.py

import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from discord import Embed, Color
import random
import asyncio

GIVEAWAY_COLOR = 0x2b2d31


class GiveawayModal(Modal):

    def __init__(self, title: str, *args, **kwargs):
        super().__init__(title=title, *args, **kwargs)
        self.item = TextInput(label="Item", placeholder="Name of the item")
        self.time = TextInput(label="Time", placeholder="1h, 1d, 1w, 1m")
        self.requirements = TextInput(
            label="Requirements", placeholder="Requirements for the giveaway")
        self.winners = TextInput(label="Winners",
                                 placeholder="Number of winners")
        self.add_item(self.item)
        self.add_item(self.time)
        self.add_item(self.requirements)
        self.add_item(self.winners)

    async def callback(self, interaction: discord.Interaction):
        item = self.item.value
        time = self.time.value
        requirements = self.requirements.value
        winners = int(self.winners.value)
        # Handle the giveaway setup here
        await interaction.response.send_message(
            f"Giveaway for {item} set for {time} with {winners} winners.",
            ephemeral=True)


class Giveaway(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.giveaways = {}  # To track active giveaways
        self.config = {}  # To track configurations

    @commands.command(name="giveaway_setup")
    @commands.has_permissions(administrator=True)
    async def giveaway_setup(self, ctx: commands.Context):
        embed = Embed(
            title="🎉 Giveaway Setup Wizard 🎉",
            description="Configure your giveaway using the buttons below.",
            color=GIVEAWAY_COLOR)
        view = View()

        configure_button = Button(label="Configure",
                                  style=discord.ButtonStyle.primary,
                                  emoji="⚙️")
        configure_button.callback = self.configure_callback
        view.add_item(configure_button)

        setup_button = Button(label="Setup",
                              style=discord.ButtonStyle.success,
                              emoji="🛠️")
        setup_button.callback = self.setup_callback
        view.add_item(setup_button)

        drop_button = Button(label="Drop",
                             style=discord.ButtonStyle.danger,
                             emoji="🎁")
        drop_button.callback = self.drop_callback
        view.add_item(drop_button)

        await ctx.send(embed=embed, view=view, ephemeral=True)

    async def configure_callback(self, interaction: discord.Interaction):
        modal = Modal(title="Configure Giveaway Manager Role and More")
        role_input = TextInput(label="Giveaway Manager Role",
                               placeholder="Role ID or Mention")
        color_input = TextInput(label="Embed Color", placeholder="#2b2d31")
        image_input = TextInput(label="Image URL", placeholder="Link to image")
        modal.add_item(role_input)
        modal.add_item(color_input)
        modal.add_item(image_input)

        async def modal_callback(modal_interaction: discord.Interaction):
            role = role_input.value
            color = color_input.value
            image = image_input.value
            # Validate and save the configuration
            if not discord.utils.get(interaction.guild.roles, id=int(role)):
                await modal_interaction.response.send_message("Invalid role!",
                                                              ephemeral=True)
                return
            if not color.startswith("#") or len(color) != 7:
                await modal_interaction.response.send_message(
                    "Invalid color format!", ephemeral=True)
                return
            self.config[interaction.guild.id] = {
                "role": role,
                "color": color,
                "image": image
            }
            await modal_interaction.response.send_message(
                "Configuration saved!", ephemeral=True)

        modal.callback = modal_callback
        await interaction.response.send_modal(modal)

    async def setup_callback(self, interaction: discord.Interaction):
        modal = GiveawayModal(title="Setup Giveaway")
        await interaction.response.send_modal(modal)

    async def drop_callback(self, interaction: discord.Interaction):
        modal = Modal(title="Quick Giveaway")
        item_input = TextInput(label="Item", placeholder="Name of the item")
        time_input = TextInput(label="Time", placeholder="1-5 minutes")
        winners_input = TextInput(label="Winners",
                                  placeholder="Number of winners")
        modal.add_item(item_input)
        modal.add_item(time_input)
        modal.add_item(winners_input)

        async def modal_callback(modal_interaction: discord.Interaction):
            item = item_input.value
            time = int(time_input.value.replace("m", ""))
            winners = int(winners_input.value)
            # Handle the quick giveaway setup here
            await modal_interaction.response.send_message(
                f"Quick giveaway for {item} set for {time} minutes with {winners} winners.",
                ephemeral=True)

        modal.callback = modal_callback
        await interaction.response.send_modal(modal)

    async def start_giveaway(self,
                             ctx: commands.Context,
                             duration: int,
                             prize: str,
                             winners: int,
                             requirements: str = None):
        embed = Embed(title="🎉 Giveaway! 🎉",
                      description=f"Prize: **{prize}**",
                      color=GIVEAWAY_COLOR)
        embed.add_field(name="How to enter", value="React with 🎉 to enter!")
        embed.add_field(name="Duration", value=f"{duration} seconds")
        embed.set_footer(text="Giveaway ends")
        message = await ctx.send(embed=embed)
        self.giveaways[message.id] = {
            "prize": prize,
            "participants": [],
            "winners": winners,
            "requirements": requirements
        }

        await message.add_reaction("🎉")

        await asyncio.sleep(duration)

        await self.end_giveaway(ctx, message.id)

    @commands.command(name="end_giveaway")
    @commands.has_permissions(administrator=True)
    async def end_giveaway(self, ctx: commands.Context, message_id: int):
        if message_id not in self.giveaways:
            await ctx.send("No active giveaway found with that message ID.")
            return

        giveaway = self.giveaways.pop(message_id)
        winners = random.sample(
            giveaway["participants"],
            k=giveaway["winners"]) if giveaway["participants"] else []

        if winners:
            winner_mentions = ", ".join([winner.mention for winner in winners])
            await ctx.send(
                f"Congratulations {winner_mentions}! You won the **{giveaway['prize']}**!"
            )
        else:
            await ctx.send("No participants, no winner.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.message_id in self.giveaways and payload.emoji.name == "🎉":
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            if not member.bot:
                self.giveaways[payload.message_id]["participants"].append(
                    member)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.message_id in self.giveaways and payload.emoji.name == "🎉":
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            if not member.bot:
                self.giveaways[payload.message_id]["participants"].remove(
                    member)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))
