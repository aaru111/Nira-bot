import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import datetime
import random

# Embed color variable
EMBED_COLOR = 0x2b2d31


class GiveawayModal(Modal):

    def __init__(self, bot, setup_type, *args, **kwargs):
        self.bot = bot
        self.setup_type = setup_type
        super().__init__(*args, **kwargs)

    async def on_submit(self, interaction: discord.Interaction):
        item_name = self.children[0].value
        time_str = self.children[1].value
        requirements = self.children[2].value or "No requirements"
        num_winners = self.children[3].value or "1"

        end_time = datetime.datetime.now() + self.parse_time(time_str)

        embed = discord.Embed(
            title=f"🎉 {item_name} Giveaway! 🎉",
            description=
            f"Requirements: {requirements}\nNumber of Winners: {num_winners}\nParticipants: 0",
            color=EMBED_COLOR)
        embed.set_footer(
            text=
            f"Ends at: {end_time.strftime('%Y-%m-%d %H:%M:%S')} | Winners: {num_winners}"
        )

        message = await interaction.channel.send(embed=embed)
        view = GiveawayView(self.bot, message.id, end_time, item_name,
                            num_winners)
        view.message = message
        self.bot.add_view(view)  # Ensure the view is persistent
        await message.edit(view=view)
        await interaction.response.send_message(
            "Giveaway created successfully!", ephemeral=True)

    def parse_time(self, time_str):
        time_units = {"h": 3600, "d": 86400, "w": 604800, "m": 2592000}
        return datetime.timedelta(seconds=int(time_str[:-1]) *
                                  time_units[time_str[-1]])


class ConfigureModal(Modal):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_submit(self, interaction: discord.Interaction):
        giveaway_manager_role = self.children[0].value
        embed_color = self.children[1].value or EMBED_COLOR
        image_link = self.children[2].value

        # Store configuration (in this example, we just print it, but you can store it in a database or file)
        print(
            f"Giveaway Manager Role: {giveaway_manager_role}, Embed Color: {embed_color}, Image Link: {image_link}"
        )

        await interaction.response.send_message(
            "Configuration updated successfully!", ephemeral=True)


class GiveawayView(View):

    def __init__(self, bot, message_id, end_time, item_name, num_winners):
        super().__init__(timeout=None)
        self.bot = bot
        self.message_id = message_id
        self.end_time = end_time
        self.item_name = item_name
        self.num_winners = num_winners
        self.participants = []

    @discord.ui.button(label="Join/Leave",
                       custom_id="join_leave",
                       emoji="✅",
                       style=discord.ButtonStyle.primary)
    async def join_leave(self, interaction: discord.Interaction,
                         button: Button):
        if interaction.user.id in self.participants:
            self.participants.remove(interaction.user.id)
            await interaction.response.send_message(
                "You have left the giveaway!", ephemeral=True)
        else:
            self.participants.append(interaction.user.id)
            await interaction.response.send_message(
                "You have entered the giveaway!", ephemeral=True)

        # Update embed with number of participants
        embed = interaction.message.embeds[0]
        embed.description = embed.description.split(
            '\n')[0] + f"\nParticipants: {len(self.participants)}"
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="End Giveaway",
                       custom_id="end_giveaway",
                       emoji="🛑",
                       style=discord.ButtonStyle.danger)
    async def end_giveaway(self, interaction: discord.Interaction,
                           button: Button):
        if interaction.user.guild_permissions.administrator:
            await self.end_giveaway_process(interaction)
        else:
            await interaction.response.send_message(
                "You do not have permission to end the giveaway!",
                ephemeral=True)

    async def end_giveaway_process(self, interaction: discord.Interaction):
        # Remove buttons from the embed
        embed = interaction.message.embeds[0]
        embed.title = f"🎉 {self.item_name} Giveaway Ended! 🎉"
        embed.color = discord.Color.red()
        embed.set_footer(
            text=f"The giveaway has ended. Winners: {self.num_winners}")

        await interaction.message.edit(embed=embed, view=None)

        # Announce winners
        winners = self.select_winners()
        if winners:
            winner_mentions = ", ".join(winner.mention for winner in winners)
            winner_embed = discord.Embed(
                title="🎉 Giveaway Ended! 🎉",
                description=
                f"Congratulations {winner_mentions}, you won the **{self.item_name}** giveaway!",
                color=EMBED_COLOR)
            await interaction.channel.send(embed=winner_embed)
        else:
            await interaction.channel.send("No winners were selected.")

        await interaction.response.send_message("The giveaway has been ended!",
                                                ephemeral=True)

    def select_winners(self):
        if len(self.participants) == 0:
            return []
        num_winners = int(self.num_winners)
        winners = random.sample(self.participants,
                                min(num_winners, len(self.participants)))
        return [self.bot.get_user(winner_id) for winner_id in winners]

    @discord.ui.button(label="List",
                       custom_id="list",
                       emoji="📋",
                       style=discord.ButtonStyle.secondary)
    async def list(self, interaction: discord.Interaction, button: Button):
        if not self.participants:
            await interaction.response.send_message("No participants yet.",
                                                    ephemeral=True)
        else:
            participants_mentions = ", ".join(
                interaction.guild.get_member(user_id).mention
                for user_id in self.participants)
            await interaction.response.send_message(
                f"Participants: {participants_mentions}", ephemeral=True)


class GiveawayCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="giveaway_setup",
                             description="Setup a giveaway")
    async def giveaway_setup(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Setup a Giveaway",
            description=
            "Choose one of the options below to configure and start a giveaway.",
            color=EMBED_COLOR)
        view = View()

        configure_button = Button(label="Configure",
                                  custom_id="configure",
                                  emoji="⚙️",
                                  style=discord.ButtonStyle.secondary)
        configure_button.callback = self.configure_callback
        view.add_item(configure_button)

        setup_button = Button(label="Setup",
                              custom_id="setup",
                              emoji="🎉",
                              style=discord.ButtonStyle.success)
        setup_button.callback = self.setup_callback
        view.add_item(setup_button)

        drop_button = Button(label="Drop",
                             custom_id="drop",
                             emoji="🎁",
                             style=discord.ButtonStyle.primary)
        drop_button.callback = self.drop_callback
        view.add_item(drop_button)

        await ctx.send(embed=embed, view=view, ephemeral=True)

    async def configure_callback(self, interaction: discord.Interaction):
        modal = ConfigureModal(title="Configure Giveaway")
        modal.add_item(
            TextInput(label="Giveaway Manager Role",
                      placeholder="Enter the role ID",
                      required=True))
        modal.add_item(
            TextInput(label="Embed Color (Hex)",
                      placeholder="Enter a hex color code (optional)",
                      required=False))
        modal.add_item(
            TextInput(label="Image Link",
                      placeholder="Enter an image link (optional)",
                      required=False))
        await interaction.response.send_modal(modal)

    async def setup_callback(self, interaction: discord.Interaction):
        modal = GiveawayModal(self.bot, "giveaway", title="Setup Giveaway")
        modal.add_item(
            TextInput(label="Item Name",
                      placeholder="Enter the item name",
                      required=True))
        modal.add_item(
            TextInput(label="Giveaway Time",
                      placeholder="Enter the time (e.g., 1h, 1d)",
                      required=True))
        modal.add_item(
            TextInput(label="Requirements",
                      placeholder="Enter the requirements (optional)",
                      required=False))
        modal.add_item(
            TextInput(label="Number of Winners",
                      placeholder="Enter the number of winners (default: 1)",
                      required=False))
        await interaction.response.send_modal(modal)

    async def drop_callback(self, interaction: discord.Interaction):
        modal = GiveawayModal(self.bot, "drop", title="Setup Drop")
        modal.add_item(
            TextInput(label="Item Name",
                      placeholder="Enter the item name",
                      required=True))
        modal.add_item(
            TextInput(label="Drop Time",
                      placeholder="Enter the time (1-5 minutes)",
                      required=True))
        modal.add_item(
            TextInput(label="Number of Winners",
                      placeholder="Enter the number of winners (default: 1)",
                      required=False))
        await interaction.response.send_modal(modal)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GiveawayCog(bot))
