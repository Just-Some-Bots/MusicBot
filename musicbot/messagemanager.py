import discord
from enum import Enum
from .constants import DISCORD_MSG_CHAR_LIMIT
from .constants import VERSION as BOTVERSION
import asyncio

import logging

log = logging.getLogger(__name__)

async def _wait_delete_msg(message, after):
    await asyncio.sleep(after)
    await safe_delete_message(message, quiet=True)

# TODO: Check to see if I can just move this to on_message after the response check (this todo is there before spliting the code)
async def _manual_delete_check(client, message, *, quiet=False):
    if client.config.delete_invoking:
        await safe_delete_message(message, quiet=quiet)

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
        if new is not None:
            if isinstance(new, discord.Embed):
                msg = await message.edit(embed=new)
            else:
                msg = await message.edit(content=new)
            return msg

    except discord.NotFound:
        lfunc("Cannot edit message \"{}\", message not found".format(message.clean_content))
        if send_if_fail:
            lfunc("Sending message instead")
            return await message.channel.safe_send_message(message.channel, new)

class ContentTypeColor(Enum):
    NORMAL = discord.Color.blurple()
    ERROR = discord.Color.red()

def content_gen(ctx, fields, color = ContentTypeColor.NORMAL):
    if ctx.bot.config.embeds:
        e = discord.Embed()
        e.colour = color.value
        if ctx.command:
            e.title = ctx.command.name
        else:
            e.title = discord.utils.find((lambda c: ctx.invoked_with in c.aliases), ctx.bot.walk_commands()).name
        e.set_footer(text='Just-Some-Bots/MusicBot ({})'.format(BOTVERSION), icon_url='https://i.imgur.com/gFHBoZA.png')
        e.set_author(name=ctx.bot.user.name, url='https://github.com/Just-Some-Bots/MusicBot', icon_url=ctx.bot.user.avatar_url)
        if isinstance(fields, list):
            for field in fields:
                e.add_field(**field)
        else:
            e.description = fields
        return e
    else:
        if isinstance(fields, list):
            return '\n\n'.join(['{}:\n{}'.format(field.name, field.value) for field in fields])
        else:
            return fields

async def safe_send_message(dest, content, **kwargs):
    tts = kwargs.pop('tts', False)
    quiet = kwargs.pop('quiet', False)
    expire_in = kwargs.pop('expire_in', 0)
    allow_none = kwargs.pop('allow_none', True)
    also_delete = kwargs.pop('also_delete', None)

    msg = None
    lfunc = log.debug if quiet else log.warning

    try:
        if content is not None or allow_none:
            if isinstance(content, discord.Embed):
                msg = await dest.send(embed=content)
            elif isinstance(content, discord.File):
                msg = await dest.send(file=content)
            elif isinstance(content, list) and all(isinstance(o, discord.File) for o in content):
                msg = await dest.send(files=content)
            else:
                msg = await dest.send(content, tts=tts)

    except discord.Forbidden:
        lfunc("Cannot send message to \"%s\", no permission", dest.name)

    except discord.NotFound:
        lfunc("Cannot send message to \"%s\", invalid channel?", dest.name)

    except discord.HTTPException:
        if len(content) > DISCORD_MSG_CHAR_LIMIT:
            lfunc("Message is over the message size limit (%s)", DISCORD_MSG_CHAR_LIMIT)
        else:
            lfunc("Failed to send message")
            log.noise("Got HTTPException trying to send message to %s: %s", dest, content)

    finally:
        if msg and expire_in:
            asyncio.ensure_future(_wait_delete_msg(msg, expire_in))

        if also_delete and isinstance(also_delete, discord.Message):
            asyncio.ensure_future(_wait_delete_msg(also_delete, expire_in))

    return msg

async def safe_send_normal(ctx, dest, fields, **kwargs):
    '''
    shorthand for safe_send_message(dest, content_gen(ctx, fields), **kwargs)
    '''
    return await safe_send_message(dest, content_gen(ctx, fields), **kwargs)

async def safe_edit_normal(ctx, message, fields, **kwargs):
    '''
    shorthand for safe_edit_message(message, content_gen(ctx, fields), **kwargs)
    '''
    return await safe_edit_message(message, content_gen(ctx, fields), **kwargs)

async def send_typing(destination):
    try:
        return await destination.trigger_typing()
    except discord.Forbidden:
        log.warning("Could not send typing to {}, no permission".format(destination))
