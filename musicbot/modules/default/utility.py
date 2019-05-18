import logging
import re
import copy
from typing import Optional

from discord.ext.commands import Cog, command

from ... import messagemanager

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
            await messagemanager.safe_send_message(ctx, ctx.bot.str.get('cmd-clean-invalid', "Invalid parameter. Please provide a number of messages to search."), reply=True, expire_in=8)

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
                await messagemanager.safe_send_message(ctx, ctx.bot.str.get('cmd-clean-reply', 'Cleaned up {0} message{1}.').format(len(deleted), 's' * bool(deleted)), expire_in=15)

cogs = [Utility]