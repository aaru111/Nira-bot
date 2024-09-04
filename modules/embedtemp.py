import discord


def get_announcement_template():
    return discord.Embed(
        title="📢 Important Announcement",
        description="Please read this important update from the server staff.",
        color=discord.Color.blue()).add_field(
            name="What's New",
            value="Details of the announcement go here.",
            inline=False)


def get_welcome_template():
    return discord.Embed(
        title="👋 Welcome to the Server!",
        description=
        "We're glad you're here. Please take a moment to familiarize yourself with our community.",
        color=discord.Color.green()).add_field(
            name="Getting Started",
            value="1. Read the rules\n2. Introduce yourself\n3. Have fun!",
            inline=False)


def get_rules_template():
    return discord.Embed(
        title="📜 Server Rules",
        description="To ensure a positive experience for all members, please follow these rules:",
        color=discord.Color.red()
    ).add_field(name="1. Be Respectful", value="Treat others with kindness and respect.", inline=False)\
     .add_field(name="2. No Spam", value="Avoid excessive messages or promotions.", inline=False)\
     .add_field(name="3. Follow Discord TOS", value="Adhere to Discord's Terms of Service.", inline=False)


def get_event_template():
    return discord.Embed(
        title="🎉 Upcoming Event",
        description="Join us for an exciting community event!",
        color=discord.Color.purple()).add_field(
            name="Event Details",
            value="Date: TBA\nTime: TBA\nLocation: TBA",
            inline=False)


templates = {
    "announcement": get_announcement_template,
    "welcome": get_welcome_template,
    "rules": get_rules_template,
    "event": get_event_template
}


def get_template(template_name):
    return templates.get(template_name, lambda: discord.Embed())()
