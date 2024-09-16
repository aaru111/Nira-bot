import discord
from discord import ui
from urllib.parse import quote
import re

class UrbanDictionarySelect(ui.Select):
    def __init__(self, definitions):
        # Sort definitions by thumbs_up in descending order
        sorted_definitions = sorted(definitions, key=lambda x: x['thumbs_up'], reverse=True)
        options = [
            discord.SelectOption(
                label=f"{definition['word'][:50]}",
                description=f"{definition['author'][:50]} | 👍 {definition['thumbs_up']}",
                value=str(i)
            ) for i, definition in enumerate(sorted_definitions)
        ]
        super().__init__(placeholder="Select a definition", options=options)
        self.definitions = sorted_definitions

    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        definition = self.definitions[index]
        embed = create_definition_embed(definition['word'],
                                        quote(definition['word']), definition,
                                        index + 1, len(self.definitions))
        await interaction.response.edit_message(embed=embed)

class UrbanDictionaryView(ui.View):
    def __init__(self, definitions, dropdown):
        super().__init__(timeout=30)
        self.definitions = definitions
        self.add_item(dropdown)
        self.message = None

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

    async def start(self, ctx, embed):
        self.message = await ctx.send(embed=embed, view=self)

def format_definition(text):
    # Format words in square brackets
    words = re.findall(r'\[([^\]]+)\]', text)
    for word in words:
        encoded_word = quote(word)
        link = f"https://www.urbandictionary.com/define.php?term={encoded_word}"
        text = text.replace(f"[{word}]", f"[{word}]({link})")
    # Format words with double dollar signs
    words = re.findall(r'\$\$([^\$]+)\$\$', text)
    for word in words:
        encoded_word = quote(word)
        link = f"https://www.urbandictionary.com/define.php?term={encoded_word}"
        text = text.replace(f"$${word}$$", f"[{word}]({link})")
    return text

def create_definition_embed(word, encoded_word, definition, index, total):
    embed = discord.Embed(
        title=f"Urban Dictionary: {word}",
        url=f"https://www.urbandictionary.com/define.php?term={encoded_word}",
        color=0x00ff00)
    embed.set_author(name="Urban Dictionary",
                     icon_url="https://i.imgur.com/vdoosDm.png")
    formatted_definition = format_definition(definition["definition"])
    formatted_example = format_definition(definition["example"])
    embed.add_field(name="📚 Definition",
                    value=formatted_definition[:1000],
                    inline=False)
    embed.add_field(name="📝 Example",
                    value=f"*{formatted_example[:1000]}*",
                    inline=False)
    embed.add_field(name="👍 Upvotes",
                    value=definition["thumbs_up"],
                    inline=True)
    embed.add_field(name="👎 Downvotes",
                    value=definition["thumbs_down"],
                    inline=True)
    embed.set_footer(
        text=f"Definition {index}/{total} | Written by {definition['author']}")
    return embed

def create_urban_dropdown(definitions):
    return UrbanDictionarySelect(definitions)