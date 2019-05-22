import logging
from typing import Optional

from discord.ext.commands import Cog, command

from ... import exceptions
from ...utils import write_file

from ...messagemanager import safe_send_message, content_gen, ContentTypeColor
from ...rich_guild import get_guild

class Autoplaylist(Cog):
    @command()
    async def resetplaylist(self, ctx):
        """
        Usage:
            {command_prefix}resetplaylist

        Resets all songs in the server's autoplaylist
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        guild.autoplaylist = list(set(bot.autoplaylist))
        await safe_send_message(ctx, content_gen(ctx, bot.str.get('cmd-resetplaylist-response', '\N{OK HAND SIGN}')), expire_in=15)

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
                await safe_send_message(ctx, content_gen(ctx, bot.str.get('cmd-save-success', 'Added <{0}> to the autoplaylist.').format(url)))
            else:
                await safe_send_message(ctx, content_gen(ctx, bot.str.get('cmd-save-exists', 'This song is already in the autoplaylist.'), ContentTypeColor.ERROR))
                raise exceptions.CommandError(bot.str.get('cmd-save-exists', 'This song is already in the autoplaylist.'))
        else:
            await safe_send_message(ctx, content_gen(ctx, bot.str.get('cmd-save-invalid', 'There is no valid song playing.'), ContentTypeColor.ERROR))
            raise exceptions.CommandError(bot.str.get('cmd-save-invalid', 'There is no valid song playing.'))

cogs = [Autoplaylist]