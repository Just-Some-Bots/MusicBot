from .BaseEB import BaseEB
from .LocalEB import LocalEB
from .SpotifyEB import SpotifyEB
from .YtdlEB import YtdlEB

from .... import exceptions

class EntryBuilders:
    def __init__(self, bot):
        self.entrybuilders = list()
        self.entrybuilders.append(LocalEB(bot))
        ytdl_eb = YtdlEB(bot)
        self.entrybuilders.append(SpotifyEB(ytdl_eb))
        self.entrybuilders.append(ytdl_eb)

    async def get_entry_from_query(self, ctx, query):
        for EB in self.entrybuilders:
            if not await EB.suitable(ctx, query):
                continue

            eb_result = await EB.get_entry(ctx, query)

            if not eb_result:
                continue

            count, entry_iter = eb_result
            # IF PY35 DEPRECATED
            entry_iter = await entry_iter
            # END IF DEPRECATED

            if count < 1:
                raise exceptions.ExtractionError("Could not get any entry while extracting result for: {}".format(query))

            return (count, entry_iter)