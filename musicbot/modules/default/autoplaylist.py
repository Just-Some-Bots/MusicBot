import logging
import time
from typing import Optional

from discord.ext.commands import Cog, command

from ... import exceptions
from ...utils import write_file

from ...messagemanager import safe_send_normal
from ...rich_guild import get_guild
from ...ytdldownloader import get_unprocessed_entry, get_stream_entry
from ...playback import Playlist

class Autoplaylist(Cog):
    @command()
    async def resetplaylist(self, ctx):
        """
        Usage:
            {command_prefix}resetplaylist

        Deprecated
        """
        bot = ctx.bot
        await safe_send_normal(ctx, ctx, bot.str.get('general?cmd@deprecated', 'This command is no longer available.'), expire_in=15)

    @command()
    async def aprandom(self, ctx):
        """
        Usage:
            {command_prefix}aprandom

        Change whether autoplaylist would randomize song
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        guild.config.auto_random = not guild.config.auto_random
        safe_send_normal(ctx, ctx, 'Autoplaylist randomization is now set to {}.'.format(guild.config.auto_random), expire_in=15)

    @command()
    async def save(self, ctx, *, url:Optional[str] = None):
        """
        Usage:
            {command_prefix}save [url]

        Saves the specified song or current song if not specified to the autoplaylist playing.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        player = await guild.get_player()
        current = await player.get_current_entry()
        if not guild._auto:
            raise exceptions.CommandError('There is no autoplaylist.')
        if url or (current and not current.stream):
            if not url:
                url = current.source_url
            else:
                current = await get_unprocessed_entry(url, None, bot.downloader, dict())

            if url not in [e.source_url for e in guild._auto.list_snapshot()]:
                await guild._auto.add_entry(current)
                await guild.serialize_playlist(guild._auto)
                ctx.bot.log.debug("Appended {} to autoplaylist".format(url))
                await safe_send_normal(ctx, ctx, bot.str.get('cmd-save-success', 'Added <{0}> to the autoplaylist.').format(url))
            else:
                raise exceptions.CommandError(bot.str.get('cmd-save-exists', 'This song is already in the autoplaylist.'))
        else:
            raise exceptions.CommandError(bot.str.get('cmd-save-invalid', 'There is no valid song playing.'))

    @command()
    async def swapap(self, ctx, *, name:Optional[str] = None):
        """
        Usage:
            {command_prefix}swapap [name]

        Swap autoplaylist to the specified playlist
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if not name:
            await guild.set_auto(None)

        elif name in guild._playlists:
            await guild.set_auto(guild._playlists[name])

        else:
            raise exceptions.CommandError('There is no playlist with that name.')

    @command()
    async def fromfile(self, ctx, mode = 'playlist'):
        """
        Usage:
            {command_prefix}fromfile mode

        Load playlist from .txt file attached to the message.
        Check _autoplaylist.txt in the config folder for example.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if not guild._auto:
            raise exceptions.CommandError('There is no autoplaylist.')

        if mode not in ['playlist', 'stream']:
            raise exceptions.CommandError('Unknown mode specified.')

        processed = 0

        for f in ctx.message.attachments:
            if (f.filename.split('.'))[-1] != 'txt':
                continue

            try:
                load = await f.read()
                slines = str(load, 'utf-8').splitlines()
            except UnicodeError:
                await safe_send_normal(ctx, ctx, 'Cannot process {}, ensure that your playlist file is encoded as utf-8'.format(f.filename))
                continue

            results = []
            for line in slines:
                line = line.strip()

                if line and not line.startswith('#'):
                    results.append(line)

            for r in results:
                if mode == 'playlist':
                    current = get_unprocessed_entry(r, None, bot.downloader, dict())
                elif mode == 'stream':
                    current = get_stream_entry(r, None, bot.downloader, dict())
                await guild._auto.add_entry(current)

            processed += 1

        await safe_send_normal(ctx, ctx, 'successfully processed {} attachments'.format(processed))

cogs = [Autoplaylist]