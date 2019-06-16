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

        Deprecated
        """
        bot = ctx.bot
        await safe_send_normal(ctx, ctx, bot.str.get('general?cmd@deprecated', 'This command is no longer available.'), expire_in=15)
        await safe_send_normal(ctx, ctx, bot.str.get('cmd-resetplaylist-response', '\N{OK HAND SIGN}'), expire_in=15)

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
        permissions = ctx.bot.permissions.for_user(ctx.author)

        if bot.config.auto_mode == 'toggle':
            if not permissions.toggle_playlists:
                raise exceptions.PermissionsError(
                    bot.str.get('cmd-toggleplaylist-noperm', 'You have no permission to toggle autoplaylist'),
                    expire_in=30
                )

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
            safe_send_normal(ctx, ctx, bot.str.get('cmd-toggleplaylist-success', 'Switched autoplaylist to {0}').format(guild._internal_auto._name), expire_in=15)
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

            if url not in [e.source_url for e in guild._internal_auto]:
                await guild._internal_auto.add_entry(current)
                ctx.bot.log.debug("Appended {} to autoplaylist".format(url))
                await safe_send_normal(ctx, ctx, bot.str.get('cmd-save-success', 'Added <{0}> to the autoplaylist.').format(url))
            else:
                raise exceptions.CommandError(bot.str.get('cmd-save-exists', 'This song is already in the autoplaylist.'))
        else:
            raise exceptions.CommandError(bot.str.get('cmd-save-invalid', 'There is no valid song playing.'))

cogs = [Autoplaylist]