import logging
import re
import copy
import os
from typing import Optional

from discord.ext.commands import Cog, command

from ... import messagemanager
from ... import exceptions

log = logging.getLogger(__name__)

class Utility(Cog):
    @command()
    async def clean(self, ctx, search_range:Optional[int]=50):
        """
        Usage:
            {command_prefix}clean [range]

        Removes up to [range] messages the bot has posted in chat. Default: 50, Max: 1000
        """

        try:
            float(search_range)  # lazy check
            search_range = min(int(search_range), 1000)
        except:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-clean-invalid', "Invalid parameter. Please provide a number of messages to search."), expire_in=8)

        def is_possible_command_invoke(entry):
            valid_call = any(
                entry.content.startswith(prefix) for prefix in [ctx.bot.config.command_prefix])  # can be expanded
            return valid_call and not entry.content[1:2].isspace()

        delete_invokes = True
        delete_all = ctx.channel.permissions_for(ctx.author).manage_messages or ctx.bot.config.owner_id == ctx.author.id

        def check(message):
            if is_possible_command_invoke(message) and delete_invokes:
                return delete_all or message.author == ctx.author
            return message.author == ctx.bot.user

        if ctx.bot.user.bot:
            if ctx.channel.permissions_for(ctx.guild.me).manage_messages:
                deleted = await ctx.channel.purge(check=check, limit=search_range, before=ctx.message)
                await messagemanager.safe_delete_message(ctx.message, quiet=True)
                await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-clean-reply', 'Cleaned up {0} message{1}.').format(len(deleted), 's' * bool(deleted)), expire_in=15)

    @command()
    async def lib(self, ctx):
        """
        Usage:
            {command_prefix}lib

        List all files in local folder which potentially could be played.
        """
        if not ctx.bot.config.local_dir_only:
            raise exceptions.CommandError(ctx.bot.str.get('utility?cmd?lib?local@no', "You did not specified local library folder!"), expire_in=8)
        else:
            # @TheerapakG TODO: paging
            files = []
            for path in ctx.bot.config.local_dir:
                for tup in os.walk(path):
                    files.extend(tup[2])
            await messagemanager.safe_send_normal(ctx, ctx, '```{}```'.format('\n'.join(files)), expire_in=15)
            

cogs = [Utility]