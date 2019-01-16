import discord
from .utils import add_method

import logging

log = logging.getLogger(__name__)

async def safe_delete_message(message, *, quiet=False):
    lfunc = log.debug if quiet else log.warning

    try:
        return await message.delete()

    except discord.Forbidden:
        lfunc("Cannot delete message \"{}\", no permission".format(message.clean_content))

    except discord.NotFound:
        lfunc("Cannot delete message \"{}\", message not found".format(message.clean_content))

async def safe_edit_message(message, new, *, send_if_fail=False, quiet=False):
    lfunc = log.debug if quiet else log.warning

    try:
        return await message.edit(content=new)

    except discord.NotFound:
        lfunc("Cannot edit message \"{}\", message not found".format(message.clean_content))
        if send_if_fail:
            lfunc("Sending message instead")
            return await message.channel.safe_send_message(message.channel, new)