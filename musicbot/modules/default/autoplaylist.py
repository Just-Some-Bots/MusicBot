import logging
import time
from typing import Optional

from discord.ext.commands import Cog, command

from ... import exceptions
from ...utils import write_file

from ...messagemanager import safe_send_normal
from ...rich_guild import get_guild

class Autoplaylist(Cog):
    @command()
    async def resetplaylist(self, ctx):
        """
        Usage:
            {command_prefix}resetplaylist

        Resets all songs in the server's autoplaylist and autostream
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        if not bot.autoplaylist:
            # TODO: When I add playlist expansion, make sure that's not happening during this check
            bot.log.warning("No playable songs in the autoplaylist, disabling.")
            bot.config.auto_playlist = False
            if bot.config.auto_mode == 'toggle' and bot.config.auto_mode_toggle == 'playlist':
                bot.config.auto_mode_toggle == 'stream'
        else:
            bot.log.debug("No content in current autoplaylist. Filling with new music...")
            if bot.config.auto_mode == 'merge' or (bot.config.auto_mode == 'toggle' and bot.config.auto_mode_toggle == 'playlist'):
                guild.autoplaylist.extend([(e, 'playlist') for e in bot.autoplaylist])

        if not bot.autostream:
            bot.log.warning("No playable songs in the autostream, disabling.")
            bot.config.auto_stream = False
            if bot.config.auto_mode == 'toggle' and bot.config.auto_mode_toggle == 'stream':
                bot.config.auto_mode_toggle == 'playlist'
        else:
            bot.log.debug("No content in current autoplaylist. Filling with new music...")
            if bot.config.auto_mode == 'merge' or (bot.config.auto_mode == 'toggle' and bot.config.auto_mode_toggle == 'stream'):
                guild.autoplaylist.extend([(e, 'stream') for e in bot.autostream])
        await safe_send_normal(ctx, ctx, bot.str.get('cmd-resetplaylist-response', '\N{OK HAND SIGN}'), expire_in=15)

    @command()
    async def toggleplaylist(self, ctx):
        """
        Usage:
            {command_prefix}toggleplaylist

        Toggle between autoplaylist and autostream
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        permissions = ctx.bot.permissions.for_user(ctx.author)

        if bot.config.auto_mode == 'toggle':
            if not permissions.toggle_playlists:
                raise exceptions.PermissionsError(
                    bot.str.get('cmd-toggleplaylist-noperm', 'You have no permission to toggle autoplaylist'),
                    expire_in=30
                )

            playlisttype = list()
            if bot.config.auto_playlist:
                playlisttype.append('playlist')
            if bot.config.auto_stream:
                playlisttype.append('stream')

            if not len(playlisttype) == 0:
                safe_send_normal(ctx, ctx, bot.str.get('cmd-toggleplaylist-nolist', 'There is not any autoplaylist to toggle to'), expire_in=15)
                return

            try:
                i = playlisttype.index(bot.config.auto_mode_toggle ) + 1
                if i == len(playlisttype):
                    i = 0
            except ValueError:
                i = 0
            if playlisttype[i] == bot.config.auto_mode_toggle:
                safe_send_normal(ctx, ctx, bot.str.get('cmd-toggleplaylist-nolist', 'There is not any autoplaylist to toggle to'), expire_in=15)
                return
            else:
                bot.config.auto_mode_toggle = playlisttype[i]
                # reset playlist
                guild.autoplaylist = list()
                # TODO: if autoing then switch
                # on_player_finished_playing should fill in the music
                # done!
                safe_send_normal(ctx, ctx, bot.str.get('cmd-toggleplaylist-success', 'Switched autoplaylist to {0}').format(bot.config.auto_mode_toggle), expire_in=15)
                return
        else:
            safe_send_normal(ctx, ctx, bot.str.get('cmd-toggleplaylist-wrongmode', 'Mode for dealing with autoplaylists is not set to \'toggle\', currently set to {0}').format(bot.config.auto_mode), expire_in=15)

    @command()
    async def save(self, ctx, *, url:Optional[str] = None):
        """
        Usage:
            {command_prefix}save [url]

        Saves the specified song or current song if not specified to the autoplaylist.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        player = await guild.get_player()
        current = await player.get_current_entry()
        if url or (current and not current.stream):
            if not url:
                url = current.source_url

            if url not in bot.autoplaylist:
                bot.autoplaylist.append(url)
                write_file(bot.config.auto_playlist_file, bot.autoplaylist)
                ctx.bot.log.debug("Appended {} to autoplaylist".format(url))
                await safe_send_normal(ctx, ctx, bot.str.get('cmd-save-success', 'Added <{0}> to the autoplaylist.').format(url))
            else:
                raise exceptions.CommandError(bot.str.get('cmd-save-exists', 'This song is already in the autoplaylist.'))
        else:
            raise exceptions.CommandError(bot.str.get('cmd-save-invalid', 'There is no valid song playing.'))

    async def autostream(self, ctx, option, url:Optional[str]=None):
        """
        Usage:
            {command_prefix}autostream (+|-|add|remove) url

        Add or remove the specified stream or current stream if not specified to/from the autostream.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        player = await guild.get_player()
        current = await player.get_current_entry()
        if current.stream:
            if not url:
                url = player.current_entry.url
        else:
            if not url:
                raise exceptions.CommandError(bot.str.get('cmd-autostream-stream-invalid', 'There is no valid stream playing.'))

        if not url:
            raise exceptions.CommandError(bot.str.get('cmd-autostream-nourl', '\'Emptiness\' is not a valid URL. Maybe you forget options?'))


        if option in ['+', 'add']:
            if url not in bot.autostream:
                bot.autostream.append(url)
                write_file(bot.config.auto_stream_file, bot.autostream)
                bot.log.debug("Appended {} to autostream".format(url))
                await safe_send_normal(ctx, ctx, bot.str.get('cmd-addstream-success', 'Added <{0}> to the autostream.').format(url))
                return
            else:
                raise exceptions.CommandError(bot.str.get('cmd-addstream-exists', 'This stream is already in the autostream.'))

        elif option in ['-', 'remove']:
            if url not in bot.autostream:
                bot.log.debug("URL \"{}\" not in autostream, ignoring".format(url))
                raise exceptions.CommandError(bot.str.get('cmd-removestream-notexists', 'This stream is already not in the autostream.'))

            async with bot._aiolocks['remove_from_autostream']:
                bot.autostream.remove(url)
                bot.log.info("Removing song from session autostream: %s" % url)

                with open(bot.config.auto_stream_removed_file, 'a', encoding='utf8') as f:
                    f.write(
                        '# Entry removed {ctime}\n'
                        '# Reason: {re}\n'
                        '{url}\n\n{sep}\n\n'.format(
                            ctime=time.ctime(),
                            re='\n#' + ' ' * 10 + 'removed by user', # 10 spaces to line up with # Reason:
                            url=url,
                            sep='#' * 32
                    ))

                bot.log.info("Updating autostream")
                write_file(bot.config.auto_stream_file, bot.autostream)

            await safe_send_normal(ctx, ctx, bot.str.get('cmd-removestream-success', 'Removed <{0}> from the autostream.').format(url))
            return

        else:
            raise exceptions.CommandError(bot.str.get('cmd-autostream-nooption', 'Check your specified option argument. It needs to be +, -, add or remove.'))

cogs = [Autoplaylist]