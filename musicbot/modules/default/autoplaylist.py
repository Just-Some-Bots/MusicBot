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
    async def apmode(self, ctx, mode):
        """
        Usage:
            {command_prefix}apmode mode

        Change autoplaylist mode
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        async with guild._aiolocks['ap_mode']:
            if mode not in ['toggle', 'merge']:
                raise exceptions.CommandError('Unknown mode specified.')

            if not guild._internal_auto:
                raise exceptions.CommandError('There is no autoplaylist.')

            # check if mode is the same
            if guild.config.auto_mode == mode:
                raise exceptions.CommandError('Mode is already set to {}.'.format(guild.config.auto_mode))

            # If currently toggle, set internal to None
            if guild.config.auto_mode == 'toggle':
                await guild.serialize_playlist(guild._internal_auto)
                guild._internal_auto = None
            # If currently merge, delete internal in playlists and set internal to None
            elif guild.config.auto_mode == 'merge':
                del guild._playlists[guild._internal_auto._name]
                guild._internal_auto = None
                await guild.remove_serialized_playlist(guild._internal_auto._name)

            # If going to toggle, set first in autos list to internal
            if mode == 'toggle':
                guild._internal_auto = guild._autos[0]
            # If going to merge, create new playlist, append all in _list in autos and set it to internal
            if mode == 'merge':
                pl = Playlist('__internal_merge', bot, persistent = True)
                guild._playlists[pl._name] = pl
                guild._internal_auto = pl
                for p in guild._autos:
                    pl._list.extend(p._list)

            await guild.serialize_playlist(guild._internal_auto)

            p_mode = guild.config.auto_mode
            guild.config.auto_mode = mode
            await guild.serialize_to_file()

            safe_send_normal(ctx, ctx, 'Autoplaylist changed from {} to {}.'.format(p_mode, mode), expire_in=15)

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
    async def toggleplaylist(self, ctx):
        """
        Usage:
            {command_prefix}toggleplaylist

        Toggle between autoplaylist
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        player = await guild.get_player()

        if guild.config.auto_mode == 'toggle':
            if not len(guild._autos) == 0:
                safe_send_normal(ctx, ctx, bot.str.get('cmd-toggleplaylist-nolist', 'There is not any autoplaylist to toggle to'), expire_in=15)
                return

            try:
                i = guild._autos.index(guild._internal_auto) + 1
                if i == len(guild._autos):
                    i = 0
            except ValueError:
                i = 0
            
            guild._internal_auto = guild._autos[i]
            # if autoing then switch
            if bot.config.skip_if_auto and (await guild.is_currently_auto()):
                await player.skip()

            await guild.serialize_to_file()
            safe_send_normal(ctx, ctx, bot.str.get('cmd-toggleplaylist-success', 'Switched autoplaylist to {0}').format(guild._internal_auto._name), expire_in=15)
            return
        else:
            safe_send_normal(ctx, ctx, bot.str.get('cmd-toggleplaylist-wrongmode', 'Mode for dealing with autoplaylists is not set to \'toggle\', currently set to {0}').format(bot.config.auto_mode), expire_in=15)

    @command()
    async def save(self, ctx, *, url:Optional[str] = None):
        """
        Usage:
            {command_prefix}save [url]

        Saves the specified song or current song if not specified to the autoplaylist playing.
        If used in merge mode, the entry added will be lost when changed the mode to toggle.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        player = await guild.get_player()
        current = await player.get_current_entry()
        if not guild._internal_auto:
            raise exceptions.CommandError('There is no autoplaylist.')
        if url or (current and not current.stream):
            if not url:
                url = current.source_url
            else:
                current = get_unprocessed_entry(url, None, bot.downloader, dict())

            if url not in [e.source_url for e in guild._internal_auto]:
                await guild._internal_auto.add_entry(current)
                await guild.serialize_playlist(guild._internal_auto)
                ctx.bot.log.debug("Appended {} to autoplaylist".format(url))
                await safe_send_normal(ctx, ctx, bot.str.get('cmd-save-success', 'Added <{0}> to the autoplaylist.').format(url))
            else:
                raise exceptions.CommandError(bot.str.get('cmd-save-exists', 'This song is already in the autoplaylist.'))
        else:
            raise exceptions.CommandError(bot.str.get('cmd-save-invalid', 'There is no valid song playing.'))

    @command()
    async def convtoap(self, ctx, name):
        """
        Usage:
            {command_prefix}convtoap name

        Convert playlist with that name in the guild to an autoplaylist.
        If used in merge mode, the entry added will be lost when changed the mode to toggle.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if name in guild._playlists:
            guild._playlists[name].persistent = True
            guild._autos.append(guild._playlists[name])
            if not guild._internal_auto:
                if guild.config.auto_mode == 'toggle':
                    guild._internal_auto = guild._playlists[name]
                elif guild.config.auto_mode == 'merge':
                    pl = Playlist('__internal_merge', bot, persistent = True)
                    guild._playlists[pl._name] = pl
                    guild._internal_auto = pl
                    pl._list.extend(guild._playlists[name]._list)
                    await guild.serialize_playlist(guild._internal_auto)
            else:
                if guild.config.auto_mode == 'toggle':
                    pass
                elif guild.config.auto_mode == 'merge':
                    guild._internal_auto._list.extend(guild._playlists[name]._list)
                    await guild.serialize_playlist(guild._internal_auto)
            await guild.serialize_playlist(guild._playlists[name])
            await guild.serialize_to_file()

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

        if not guild._internal_auto:
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
                await guild._internal_auto.add_entry(current)

            processed += 1

        await safe_send_normal(ctx, ctx, 'successfully processed {} attachments'.format(processed))

cogs = [Autoplaylist]