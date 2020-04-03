from discord.ext.commands import Cog

from .entrybuilders import EntryBuilders

class QueryConverter(Cog):
    def __init__(self):
        self.entrybuilders = None

    def pre_init(self, bot):
        self.bot = bot
        self.entrybuilders = EntryBuilders(bot)
        self.bot.crossmodule.register_object('entrybuilders', self.entrybuilders)

    def uninit(self):
        self.bot.crossmodule.unregister_object('entrybuilders')

cogs = [QueryConverter]