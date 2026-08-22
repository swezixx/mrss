import os
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 7/24 Aktif!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run, daemon=True).start()


# Botu başlatmadan önce bu fonksiyonu çalıştırıyoruz:
keep_alive()

import asyncio
import datetime
import random
import time
import discord
from discord import app_commands
from discord.ext import commands

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables to store support settings
ticket_role_id = None
ticket_category_id = None

# Dictionary to store user cooldowns for opening tickets
user_cooldowns = {}


# --- BOT EVENTS ---
@bot.event
async def on_ready():
    await bot.tree.sync()

    # Set custom status to "MRS"
    activity = discord.CustomActivity(name="MRS")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print(
        f"🤖 {bot.user.name} online! Status set to 'MRS' and Slash Commands synced."
    )


# --- TICKET SYSTEM (SELECT MENU & VIEWS) ---
class TicketSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="Anticheat Support",
                description="Open for Anticheat related issues",
                emoji="🛡️",
                value="anticheat_support",
            ),
            discord.SelectOption(
                label="Game Bugs",
                description="Report bugs or glitches found in the game",
                emoji="🐛",
                value="game_bugs",
            ),
            discord.SelectOption(
                label="Moderation Support",
                description="Report players or request moderation support",
                emoji="🔨",
                value="moderation_support",
            ),
            discord.SelectOption(
                label="Other Support",
                description="Open for general or other issues",
                emoji="❓",
                value="other_support",
            ),
            discord.SelectOption(
                label="Clear Selection",
                description="Reset your selection",
                emoji="🔄",
                value="clear_selection",
            ),
        ]
        super().__init__(
            placeholder="Select a ticket category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select",
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if self.values[0] == "clear_selection":
            await interaction.message.edit(view=TicketView())
            await interaction.followup.send(
                "🔄 Selection reset to default.", ephemeral=True
            )
            return

        guild = interaction.guild
        user = interaction.user
        category_name = self.values[0].replace("_", " ").title()

        await interaction.message.edit(view=TicketView())

        # Check if user already has an open channel
        existing_channel = discord.utils.get(
            guild.text_channels, name=f"ticket-{user.name.lower()}"
        )
        if existing_channel:
            await interaction.followup.send(
                f"❌ You already have an open ticket: {existing_channel.mention}",
                ephemeral=True,
            )
            return

        # Cooldown check (1 minute)
        current_time = time.time()
        last_ticket_time = user_cooldowns.get(user.id, 0)
        cooldown_time = 60

        if current_time - last_ticket_time < cooldown_time:
            remaining = int(cooldown_time - (current_time - last_ticket_time))
            await interaction.followup.send(
                f"⏳ Please wait `{remaining}` seconds before opening another ticket!",
                ephemeral=True,
            )
            return

        user_cooldowns[user.id] = current_time

        # Channel permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=False
            ),
            user: discord.PermissionOverwrite(
                read_messages=True, send_messages=True
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True
            ),
        }

        support_role = None
        if ticket_role_id:
            support_role = guild.get_role(ticket_role_id)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                )

        # Get parent category channel if set by admin
        parent_category = None
        if ticket_category_id:
            parent_category = guild.get_channel(ticket_category_id)

        # Create ticket channel inside the specified category
        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{user.name}",
            category=parent_category,
            overwrites=overwrites,
        )

        embed = discord.Embed(
            title=f"📩 MRS System | {category_name}",
            description=(
                f"Welcome {user.mention}!\n"
                f"Our support team will assist you shortly.\n"
                f"Please describe your issue in detail.\n\n"
                f"📌 **Status:** Unclaimed"
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"MRS System | Ticket Owner ID: {user.id}")

        await ticket_channel.send(
            embed=embed, view=TicketControlView(ticket_channel, user)
        )

        if support_role:
            await ticket_channel.send(
                f"🔔 {support_role.mention} A new ticket has been opened!"
            )

        await interaction.followup.send(
            f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True
        )


class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# --- INSIDE TICKET CHANNEL BUTTONS (CLAIM & CLOSE) ---
class TicketControlView(discord.ui.View):

    def __init__(self, channel, ticket_owner):
        super().__init__(timeout=None)
        self.channel = channel
        self.ticket_owner = ticket_owner
        self.claimed_by = None

    @discord.ui.button(
        label="Claim Ticket ✋",
        style=discord.ButtonStyle.success,
        custom_id="claim_ticket",
    )
    async def claim_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        global ticket_role_id

        if interaction.user.id == self.ticket_owner.id:
            await interaction.response.send_message(
                "❌ You cannot claim your own ticket!", ephemeral=True
            )
            return

        if ticket_role_id:
            support_role = interaction.guild.get_role(ticket_role_id)
            if support_role and support_role not in interaction.user.roles:
                await interaction.response.send_message(
                    f"❌ Only staff with the {support_role.mention} role can claim tickets!",
                    ephemeral=True,
                )
                return

        if self.claimed_by:
            await interaction.response.send_message(
                f"❌ This ticket is already claimed by {self.claimed_by.mention}!",
                ephemeral=True,
            )
            return

        self.claimed_by = interaction.user
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"

        embed = interaction.message.embeds[0]
        embed.description = embed.description.replace(
            "📌 **Status:** Unclaimed",
            f"📌 **Status:** Claimed by {interaction.user.mention}",
        )
        embed.color = discord.Color.green()

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(
            f"✋ This ticket was claimed by {interaction.user.mention}."
        )

    @discord.ui.button(
        label="Close Ticket 🔒",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket",
    )
    async def close_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message("🔒 Closing ticket...")

        await self.channel.set_permissions(
            self.ticket_owner, read_messages=False, send_messages=False
        )
        await self.channel.edit(name=f"closed-{self.ticket_owner.name}")

        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=(
                f"This ticket was closed by {interaction.user.mention}.\n"
                f"Access for {self.ticket_owner.mention} has been revoked.\n\n"
                f"Staff members can reopen or permanently delete this ticket below."
            ),
            color=discord.Color.gold(),
        )
        await self.channel.send(
            embed=embed,
            view=ClosedTicketManageView(self.channel, self.ticket_owner),
        )


# --- CLOSED TICKET MANAGEMENT VIEW (REOPEN & DELETE) ---
class ClosedTicketManageView(discord.ui.View):

    def __init__(self, channel, ticket_owner):
        super().__init__(timeout=None)
        self.channel = channel
        self.ticket_owner = ticket_owner

    @discord.ui.button(
        label="Reopen Ticket 🔓",
        style=discord.ButtonStyle.primary,
        custom_id="reopen_ticket",
    )
    async def reopen_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        global ticket_role_id

        if ticket_role_id:
            support_role = interaction.guild.get_role(ticket_role_id)
            if (
                support_role
                and support_role not in interaction.user.roles
                and not interaction.user.guild_permissions.administrator
            ):
                await interaction.response.send_message(
                    "❌ Only authorized staff members can reopen tickets!",
                    ephemeral=True,
                )
                return

        await self.channel.set_permissions(
            self.ticket_owner, read_messages=True, send_messages=True
        )
        await self.channel.edit(name=f"ticket-{self.ticket_owner.name}")

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description=f"This ticket has been reopened by {interaction.user.mention}.",
            color=discord.Color.green(),
        )
        await self.channel.send(
            content=f"🔔 {self.ticket_owner.mention}, your ticket has been reopened by {interaction.user.mention}!",
            embed=embed,
        )
        await interaction.response.send_message(
            "✅ Ticket reopened successfully!", ephemeral=True
        )

    @discord.ui.button(
        label="Delete Channel 🗑️",
        style=discord.ButtonStyle.secondary,
        custom_id="delete_ticket_channel",
    )
    async def delete_channel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "🗑️ Deleting channel in 5 seconds..."
        )
        await asyncio.sleep(5)
        await self.channel.delete()


# --- ANNOUNCEMENT MODAL (FORM WINDOW) ---
class AnnouncementModal(discord.ui.Modal, title="📢 Direct Message Announcement"):

    def __init__(self, target_role: discord.Role):
        super().__init__()
        self.target_role = target_role

    ann_title = discord.ui.TextInput(
        label="Announcement Title",
        placeholder="Enter headline here...",
        max_length=100,
        required=True,
    )

    ann_message = discord.ui.TextInput(
        label="Announcement Message",
        style=discord.TextStyle.paragraph,
        placeholder="Type the message you want to send directly to members' DMs...",
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"⏳ Dispatching DM announcements to members with role {self.target_role.mention}...",
            ephemeral=True,
        )

        guild_icon = (
            interaction.guild.icon.url
            if interaction.guild.icon
            else interaction.client.user.display_avatar.url
        )

        embed = discord.Embed(
            title=f"📢 {self.ann_title.value.upper()}",
            description=self.ann_message.value,
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=guild_icon)
        embed.set_footer(
            text=f"MRS System Announcement • {interaction.guild.name}",
            icon_url=guild_icon,
        )

        success_count = 0
        failed_count = 0

        # Send DM to each member with the selected role
        for member in self.target_role.members:
            if not member.bot:
                try:
                    await member.send(embed=embed)
                    success_count += 1
                    await asyncio.sleep(0.5)  # Avoid rate limits
                except discord.Forbidden:
                    failed_count += 1
                except Exception:
                    failed_count += 1

        await interaction.followup.send(
            f"✅ **Announcement Complete!**\n"
            f"📬 **Successfully sent:** `{success_count}` users\n"
            f"❌ **Failed (DMs Closed):** `{failed_count}` users",
            ephemeral=True,
        )


# --- SLASH COMMANDS ---

# 1. /ticketgör Command
@bot.tree.command(
    name="ticketgör",
    description="Select the support role that can see and handle tickets.",
)
@app_commands.describe(role="The role that will manage tickets")
@app_commands.checks.has_permissions(administrator=True)
async def ticketgor(interaction: discord.Interaction, role: discord.Role):
    global ticket_role_id
    ticket_role_id = role.id

    await interaction.response.send_message(
        f"✅ {role.mention} has been set as the official Support Role!",
        ephemeral=True,
    )


@ticketgor.error
async def ticketgor_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Only administrators can set the support role!", ephemeral=True
        )


# 2. /set_ticket_category Command
@bot.tree.command(
    name="set_ticket_category",
    description="Select the Discord category channel where tickets will be created.",
)
@app_commands.describe(category="The server category to place tickets under")
@app_commands.checks.has_permissions(administrator=True)
async def set_ticket_category(
    interaction: discord.Interaction, category: discord.CategoryChannel
):
    global ticket_category_id
    ticket_category_id = category.id

    await interaction.response.send_message(
        f"✅ New tickets will now be created under the **{category.name}** category!",
        ephemeral=True,
    )


@set_ticket_category.error
async def set_ticket_category_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Only administrators can set the ticket category!",
            ephemeral=True,
        )


# 3. /ticket Command
@bot.tree.command(
    name="ticket", description="Send the ticket setup embed to the channel."
)
@app_commands.checks.has_permissions(administrator=True)
async def ticket(interaction: discord.Interaction):
    guild_icon = (
        interaction.guild.icon.url
        if interaction.guild.icon
        else bot.user.display_avatar.url
    )

    embed = discord.Embed(
        title="🤖 MRS System | Support System",
        description=(
            "• **Support System Guidelines:**\n\n"
            "> You can use our support system for any problems, questions, or requests.\n\n"
            "> Please select the category that fits your needs from the menu below to open a ticket. Our team will reach out to you as soon as possible."
        ),
        color=discord.Color.blue(),
    )

    embed.set_thumbnail(url=guild_icon)
    BANNER_URL = "https://media.discordapp.net/attachments/1000000000000000000/1000000000000000000/image.png"
    embed.set_image(url=BANNER_URL)
    embed.set_footer(text="MRS System | Support Panel")

    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message(
        "✅ Support panel dispatched successfully!", ephemeral=True
    )


@ticket.error
async def ticket_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Only administrators can use this command!", ephemeral=True
        )


# 4. /giveaway Command
@bot.tree.command(
    name="giveaway", description="Start an interactive giveaway with detailed UI!"
)
@app_commands.describe(
    prize="What is the reward?", duration="Duration in seconds"
)
@app_commands.checks.has_permissions(administrator=True)
async def giveaway(
    interaction: discord.Interaction, prize: str, duration: int
):
    end_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=duration
    )
    timestamp_format = f"<t:{int(end_time.timestamp())}:R>"

    embed = discord.Embed(
        title="🎁 MRS SYSTEM | GIVEAWAY 🎁",
        description=(
            f"Click the **🎉** reaction below to participate!\n\n"
            f"🏆 **Prize:** `{prize}`\n"
            f"⏳ **Ends:** {timestamp_format}\n"
            f"👑 **Hosted by:** {interaction.user.mention}"
        ),
        color=discord.Color.gold(),
        timestamp=end_time,
    )

    server_icon = (
        interaction.guild.icon.url
        if interaction.guild.icon
        else bot.user.display_avatar.url
    )
    embed.set_thumbnail(url=server_icon)

    embed.set_footer(
        text=f"MRS System • {interaction.guild.name}",
        icon_url=bot.user.display_avatar.url,
    )

    await interaction.response.send_message(
        "🎉 Giveaway successfully initialized!", ephemeral=True
    )
    giveaway_msg = await interaction.channel.send(embed=embed)
    await giveaway_msg.add_reaction("🎉")

    await asyncio.sleep(duration)

    try:
        new_msg = await interaction.channel.fetch_message(giveaway_msg.id)
    except discord.NotFound:
        return

    reaction = discord.utils.get(new_msg.reactions, emoji="🎉")
    participants = []

    if reaction:
        async for user in reaction.users():
            if not user.bot:
                participants.append(user)

    total_entries = len(participants)

    if not participants:
        ended_embed = discord.Embed(
            title="🎁 MRS SYSTEM | GIVEAWAY ENDED 🎁",
            description=(
                f"🏆 **Prize:** `{prize}`\n"
                f"👥 **Total Entries:** `{total_entries}`\n"
                f"❌ **Winner:** No valid participants."
            ),
            color=discord.Color.red(),
        )
        ended_embed.set_thumbnail(url=server_icon)
        ended_embed.set_footer(
            text="MRS System • Giveaway Ended",
            icon_url=bot.user.display_avatar.url,
        )
        await giveaway_msg.edit(embed=ended_embed)
        await interaction.channel.send(
            f"❌ The giveaway for **{prize}** ended, but there were no valid participants."
        )
    else:
        winner = random.choice(participants)

        ended_embed = discord.Embed(
            title="🎉 MRS SYSTEM | GIVEAWAY ENDED 🎉",
            description=(
                f"🏆 **Prize:** `{prize}`\n"
                f"👥 **Total Entries:** `{total_entries}` users\n"
                f"👑 **Winner:** {winner.mention}\n"
                f"Hosted by: {interaction.user.mention}"
            ),
            color=discord.Color.green(),
        )
        ended_embed.set_thumbnail(url=winner.display_avatar.url)
        ended_embed.set_footer(
            text="MRS System • Giveaway Completed",
            icon_url=bot.user.display_avatar.url,
        )

        await giveaway_msg.edit(embed=ended_embed)
        await interaction.channel.send(
            f"🎊 Congratulations {winner.mention}! You won **{prize}**! (Total Participants: `{total_entries}`)"
        )


@giveaway.error
async def giveaway_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Only administrators can start a giveaway!", ephemeral=True
        )


# 5. /announcement Command (Opens Form and Sends DM to Role)
@bot.tree.command(
    name="announcement",
    description="Send a direct message announcement to all users with a specific role.",
)
@app_commands.describe(role="Target role to send DM announcement")
@app_commands.checks.has_permissions(administrator=True)
async def announcement(
    interaction: discord.Interaction, role: discord.Role
):
    await interaction.response.send_modal(AnnouncementModal(target_role=role))


@announcement.error
async def announcement_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Only administrators can send announcements!", ephemeral=True
        )


# 6. /vote Command (Expanded Preset Durations up to 20 Days & 1 Month)
NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]


@bot.tree.command(
    name="vote",
    description="Create an advanced timed poll with up to 5 options.",
)
@app_commands.describe(
    title="Poll Title",
    description="Poll Details or Question",
    duration="Select poll duration",
    option1="First option",
    option2="Second option",
    option3="Third option (optional)",
    option4="Fourth option (optional)",
    option5="Fifth option (optional)",
)
@app_commands.choices(
    duration=[
        app_commands.Choice(name="5 Minutes", value=300),
        app_commands.Choice(name="1 Hour", value=3600),
        app_commands.Choice(name="1 Day", value=86400),
        app_commands.Choice(name="2 Days", value=172800),
        app_commands.Choice(name="3 Days", value=259200),
        app_commands.Choice(name="4 Days", value=345600),
        app_commands.Choice(name="5 Days", value=432000),
        app_commands.Choice(name="6 Days", value=518400),
        app_commands.Choice(name="1 Week (7 Days)", value=604800),
        app_commands.Choice(name="8 Days", value=691200),
        app_commands.Choice(name="9 Days", value=777600),
        app_commands.Choice(name="10 Days", value=864000),
        app_commands.Choice(name="11 Days", value=950400),
        app_commands.Choice(name="12 Days", value=1036800),
        app_commands.Choice(name="13 Days", value=1123200),
        app_commands.Choice(name="2 Weeks (14 Days)", value=1209600),
        app_commands.Choice(name="15 Days", value=1296000),
        app_commands.Choice(name="16 Days", value=1382400),
        app_commands.Choice(name="17 Days", value=1468800),
        app_commands.Choice(name="18 Days", value=1555200),
        app_commands.Choice(name="19 Days", value=1641600),
        app_commands.Choice(name="20 Days", value=1728000),
        app_commands.Choice(name="1 Month (30 Days)", value=2592000),
    ]
)
@app_commands.checks.has_permissions(administrator=True)
async def vote(
    interaction: discord.Interaction,
    title: str,
    description: str,
    duration: app_commands.Choice[int],
    option1: str,
    option2: str,
    option3: str = None,
    option4: str = None,
    option5: str = None,
):
    duration_seconds = duration.value
    raw_options = [option1, option2, option3, option4, option5]
    options = [opt for opt in raw_options if opt is not None]

    end_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=duration_seconds
    )
    timestamp_format = f"<t:{int(end_time.timestamp())}:R>"

    formatted_options = ""
    for idx, opt in enumerate(options):
        formatted_options += f"{NUMBER_EMOJIS[idx]} **{opt}**\n"

    guild_icon = (
        interaction.guild.icon.url
        if interaction.guild.icon
        else bot.user.display_avatar.url
    )

    embed = discord.Embed(
        title=f"📊 MRS SYSTEM | {title.upper()}",
        description=(
            f"📌 **Question:**\n> {description}\n\n"
            f"📋 **Options:**\n{formatted_options}\n"
            f"⏳ **Ends:** {timestamp_format}\n"
            f"👤 **Created by:** {interaction.user.mention}"
        ),
        color=discord.Color.purple(),
        timestamp=end_time,
    )
    embed.set_thumbnail(url=guild_icon)
    embed.set_footer(
        text="MRS System Poll • Active", icon_url=bot.user.display_avatar.url
    )

    await interaction.response.send_message(
        "📊 Poll initialized successfully!", ephemeral=True
    )
    poll_msg = await interaction.channel.send(embed=embed)

    for idx in range(len(options)):
        await poll_msg.add_reaction(NUMBER_EMOJIS[idx])

    await asyncio.sleep(duration_seconds)

    try:
        updated_msg = await interaction.channel.fetch_message(poll_msg.id)
    except discord.NotFound:
        return

    results = {}
    total_votes = 0

    for idx, opt in enumerate(options):
        emoji = NUMBER_EMOJIS[idx]
        reaction = discord.utils.get(updated_msg.reactions, emoji=emoji)

        count = (reaction.count - 1) if reaction else 0
        results[opt] = count
        total_votes += count

    if total_votes == 0:
        winner_text = "❌ No votes cast."
    else:
        max_votes = max(results.values())
        winners = [opt for opt, count in results.items() if count == max_votes]

        if max_votes == 0:
            winner_text = "❌ No votes cast."
        elif len(winners) == 1:
            winner_text = f"🏆 **{winners[0]}** (`{max_votes}` votes)"
        else:
            winners_str = ", ".join([f"**{w}**" for w in winners])
            winner_text = f"🤝 **Tie:** {winners_str} (`{max_votes}` votes each)"

    final_breakdown = ""
    for idx, opt in enumerate(options):
        count = results[opt]
        percentage = (
            (count / total_votes * 100) if total_votes > 0 else 0
        )
        final_breakdown += (
            f"{NUMBER_EMOJIS[idx]} **{opt}** — `{count}` votes (`{percentage:.1f}%`)\n"
        )

    ended_embed = discord.Embed(
        title=f"📊 MRS SYSTEM | POLL ENDED: {title.upper()}",
        description=(
            f"📌 **Question:**\n> {description}\n\n"
            f"📈 **Final Results:**\n{final_breakdown}\n"
            f"🗳️ **Total Votes Cast:** `{total_votes}`\n"
            f"👑 **Winner:** {winner_text}"
        ),
        color=discord.Color.dark_purple(),
    )
    ended_embed.set_thumbnail(url=guild_icon)
    ended_embed.set_footer(
        text="MRS System Poll • Ended", icon_url=bot.user.display_avatar.url
    )

    await poll_msg.edit(embed=ended_embed)
    await interaction.channel.send(
        f"📊 Poll **{title}** has ended! Winner: {winner_text}"
    )


@vote.error
async def vote_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Only administrators can create polls!", ephemeral=True
        )


# BOT TOKEN
import os

# En alt satırdaki bot.run kısmını böyle güncelle:
bot.run(os.getenv("DISCORD_TOKEN"))
