import logging
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

cogs = [Autoplaylist]