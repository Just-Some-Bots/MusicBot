import logging

from .. import exceptions
from ..entry import StreamPlaylistEntry
from ..utils import write_file
from ..constructs import Response

log = logging.getLogger(__name__)

cog_name = 'autoplaylist'

async def cmd_resetplaylist(self, player, channel):
    """
    Usage:
        {command_prefix}resetplaylist

    Resets all songs in the server's autoplaylist
    """
    player.autoplaylist = list(set(self.autoplaylist))
    return Response(self.str.get('cmd-resetplaylist-response', '\N{OK HAND SIGN}'), delete_after=15)

async def cmd_save(self, player, url=None):
    """
    Usage:
        {command_prefix}save [url]

    Saves the specified song or current song if not specified to the autoplaylist.
    """
    if url or (player.current_entry and not isinstance(player.current_entry, StreamPlaylistEntry)):
        if not url:
            url = player.current_entry.url

        if url not in self.autoplaylist:
            self.autoplaylist.append(url)
            write_file(self.config.auto_playlist_file, self.autoplaylist)
            log.debug("Appended {} to autoplaylist".format(url))
            return Response(self.str.get('cmd-save-success', 'Added <{0}> to the autoplaylist.').format(url))
        else:
            raise exceptions.CommandError(self.str.get('cmd-save-exists', 'This song is already in the autoplaylist.'))
    else:
        raise exceptions.CommandError(self.str.get('cmd-save-invalid', 'There is no valid song playing.'))