import discord
from .utils import add_method

import logging

log = logging.getLogger(__name__)

@add_method(discord.Message)
async def safe_delete_message(self, *, quiet=False):
    lfunc = log.debug if quiet else log.warning

    try:
        return await self.delete()

    except discord.Forbidden:
        lfunc("Cannot delete message \"{}\", no permission".format(self.clean_content))

    except discord.NotFound:
        lfunc("Cannot delete message \"{}\", message not found".format(self.clean_content))

# @TheerapakG: TODO: inject safe_send_message into channels
@add_method(discord.Message)
async def safe_edit_message(self, new, *, send_if_fail=False, quiet=False):
    lfunc = log.debug if quiet else log.warning

    try:
        return await self.edit(content=new)

    except discord.NotFound:
        lfunc("Cannot edit message \"{}\", message not found".format(self.clean_content))
        if send_if_fail:
            lfunc("Sending message instead")
            return await self.channel.safe_send_message(self.channel, new)