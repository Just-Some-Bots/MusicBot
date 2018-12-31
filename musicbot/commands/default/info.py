import discord

import logging
from io import BytesIO
from datetime import timedelta
from collections import defaultdict

from ... import exceptions
from ...entry import StreamPlaylistEntry
from ...utils import ftimedelta
from ...constructs import Response
from ...constants import DISCORD_MSG_CHAR_LIMIT

log = logging.getLogger(__name__)

cog_name = 'information'

async def cmd_pldump(bot, channel, author, song_url):
    """
    Usage:
        {command_prefix}pldump url

    Dumps the individual urls of a playlist
    """

    try:
        info = await bot.downloader.extract_info(bot.loop, song_url.strip('<>'), download=False, process=False)
    except Exception as e:
        raise exceptions.CommandError("Could not extract info from input url\n%s\n" % e, expire_in=25)

    if not info:
        raise exceptions.CommandError("Could not extract info from input url, no data.", expire_in=25)

    if not info.get('entries', None):
        # TODO: Retarded playlist checking
        # set(url, webpageurl).difference(set(url))

        if info.get('url', None) != info.get('webpage_url', info.get('url', None)):
            raise exceptions.CommandError("This does not seem to be a playlist.", expire_in=25)
        else:
            return await cmd_pldump(bot, channel, author, info.get(''))

    linegens = defaultdict(lambda: None, **{
        "youtube":    lambda d: 'https://www.youtube.com/watch?v=%s' % d['id'],
        "soundcloud": lambda d: d['url'],
        "bandcamp":   lambda d: d['url']
    })

    exfunc = linegens[info['extractor'].split(':')[0]]

    if not exfunc:
        raise exceptions.CommandError("Could not extract info from input url, unsupported playlist type.", expire_in=25)

    with BytesIO() as fcontent:
        for item in info['entries']:
            fcontent.write(exfunc(item).encode('utf8') + b'\n')

        fcontent.seek(0)
        await author.send("Here's the playlist dump for <%s>" % song_url, file=discord.File(fcontent, filename='playlist.txt'))

    return Response("Sent a message with a playlist file.", delete_after=20)

async def cmd_queue(bot, channel, player):
    """
    Usage:
        {command_prefix}queue

    Prints the current song queue.
    """

    lines = []
    unlisted = 0
    andmoretext = '* ... and %s more*' % ('x' * len(player.playlist.entries))

    if player.is_playing:
        # TODO: Fix timedelta garbage with util function
        song_progress = ftimedelta(timedelta(seconds=player.progress))
        song_total = ftimedelta(timedelta(seconds=player.current_entry.duration))
        prog_str = '`[%s/%s]`' % (song_progress, song_total)

        if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
            lines.append(bot.str.get('cmd-queue-playing-author', "Currently playing: `{0}` added by `{1}` {2}\n").format(
                player.current_entry.title, player.current_entry.meta['author'].name, prog_str))
        else:
            lines.append(bot.str.get('cmd-queue-playing-noauthor', "Currently playing: `{0}` {1}\n").format(player.current_entry.title, prog_str))


    for i, item in enumerate(player.playlist, 1):
        if item.meta.get('channel', False) and item.meta.get('author', False):
            nextline = bot.str.get('cmd-queue-entry-author', '{0} -- `{1}` by `{2}`').format(i, item.title, item.meta['author'].name).strip()
        else:
            nextline = bot.str.get('cmd-queue-entry-noauthor', '{0} -- `{1}`').format(i, item.title).strip()

        currentlinesum = sum(len(x) + 1 for x in lines)  # +1 is for newline char

        if (currentlinesum + len(nextline) + len(andmoretext) > DISCORD_MSG_CHAR_LIMIT) or (i > bot.config.queue_length):
            if currentlinesum + len(andmoretext):
                unlisted += 1
                continue

        lines.append(nextline)

    if unlisted:
        lines.append(bot.str.get('cmd-queue-more', '\n... and %s more') % unlisted)

    if not lines:
        lines.append(
            bot.str.get('cmd-queue-none', 'There are no songs queued! Queue something with {}play.').format(bot.config.command_prefix))

    message = '\n'.join(lines)
    return Response(message, delete_after=30)

async def cmd_listids(bot, guild, author, leftover_args, cat='all'):
    """
    Usage:
        {command_prefix}listids [categories]

    Lists the ids for various things.  Categories are:
        all, users, roles, channels
    """

    cats = ['channels', 'roles', 'users']

    if cat not in cats and cat != 'all':
        return Response(
            "Valid categories: " + ' '.join(['`%s`' % c for c in cats]),
            reply=True,
            delete_after=25
        )

    if cat == 'all':
        requested_cats = cats
    else:
        requested_cats = [cat] + [c.strip(',') for c in leftover_args]

    data = ['Your ID: %s' % author.id]

    for cur_cat in requested_cats:
        rawudata = None

        if cur_cat == 'users':
            data.append("\nUser IDs:")
            rawudata = ['%s #%s: %s' % (m.name, m.discriminator, m.id) for m in guild.members]

        elif cur_cat == 'roles':
            data.append("\nRole IDs:")
            rawudata = ['%s: %s' % (r.name, r.id) for r in guild.roles]

        elif cur_cat == 'channels':
            data.append("\nText Channel IDs:")
            tchans = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
            rawudata = ['%s: %s' % (c.name, c.id) for c in tchans]

            rawudata.append("\nVoice Channel IDs:")
            vchans = [c for c in guild.channels if isinstance(c, discord.VoiceChannel)]
            rawudata.extend('%s: %s' % (c.name, c.id) for c in vchans)

        if rawudata:
            data.extend(rawudata)

    with BytesIO() as sdata:
        sdata.writelines(d.encode('utf8') + b'\n' for d in data)
        sdata.seek(0)

        # TODO: Fix naming (Discord20API-ids.txt)
        await author.send(file=discord.File(sdata, filename='%s-ids-%s.txt' % (guild.name.replace(' ', '_'), cat)))

    return Response("Sent a message with a list of IDs.", delete_after=20)


async def cmd_perms(bot, author, user_mentions, channel, guild, permissions):
    """
    Usage:
        {command_prefix}perms [@user]

    Sends the user a list of their permissions, or the permissions of the user specified.
    """

    lines = ['Command permissions in %s\n' % guild.name, '```', '```']

    if user_mentions:
        user = user_mentions[0]
        permissions = bot.permissions.for_user(user)

    for perm in permissions.__dict__:
        if perm in ['user_list'] or permissions.__dict__[perm] == set():
            continue

        lines.insert(len(lines) - 1, "%s: %s" % (perm, permissions.__dict__[perm]))

    await bot.safe_send_message(author, '\n'.join(lines))
    return Response("\N{OPEN MAILBOX WITH RAISED FLAG}", delete_after=20)

async def cmd_np(bot, player, channel, guild, message):
    """
    Usage:
        {command_prefix}np

    Displays the current song in chat.
    """

    if player.current_entry:
        if bot.server_specific_data[guild]['last_np_msg']:
            await bot.safe_delete_message(bot.server_specific_data[guild]['last_np_msg'])
            bot.server_specific_data[guild]['last_np_msg'] = None

        # TODO: Fix timedelta garbage with util function
        song_progress = ftimedelta(timedelta(seconds=player.progress))
        song_total = ftimedelta(timedelta(seconds=player.current_entry.duration))

        streaming = isinstance(player.current_entry, StreamPlaylistEntry)
        prog_str = ('`[{progress}]`' if streaming else '`[{progress}/{total}]`').format(
            progress=song_progress, total=song_total
        )
        prog_bar_str = ''

        # percentage shows how much of the current song has already been played
        percentage = 0.0
        if player.current_entry.duration > 0:
            percentage = player.progress / player.current_entry.duration

        # create the actual bar
        progress_bar_length = 30
        for i in range(progress_bar_length):
            if (percentage < 1 / progress_bar_length * i):
                prog_bar_str += '□'
            else:
                prog_bar_str += '■'

        action_text = bot.str.get('cmd-np-action-streaming', 'Streaming') if streaming else bot.str.get('cmd-np-action-playing', 'Playing')

        if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
            np_text = bot.str.get('cmd-np-reply-author', "Now {action}: **{title}** added by **{author}**\nProgress: {progress_bar} {progress}\n\N{WHITE RIGHT POINTING BACKHAND INDEX} <{url}>").format(
                action=action_text,
                title=player.current_entry.title,
                author=player.current_entry.meta['author'].name,
                progress_bar=prog_bar_str,
                progress=prog_str,
                url=player.current_entry.url
            )
        else:

            np_text = bot.str.get('cmd-np-reply-noauthor', "Now {action}: **{title}**\nProgress: {progress_bar} {progress}\n\N{WHITE RIGHT POINTING BACKHAND INDEX} <{url}>").format(

                action=action_text,
                title=player.current_entry.title,
                progress_bar=prog_bar_str,
                progress=prog_str,
                url=player.current_entry.url
            )

        bot.server_specific_data[guild]['last_np_msg'] = await bot.safe_send_message(channel, np_text)
        await bot._manual_delete_check(message)
    else:
        return Response(
            bot.str.get('cmd-np-none', 'There are no songs queued! Queue something with {0}play.') .format(bot.config.command_prefix),
            delete_after=30
        )

async def cmd_id(bot, author, user_mentions):
    """
    Usage:
        {command_prefix}id [@user]

    Tells the user their id or the id of another user.
    """
    if not user_mentions:
        return Response(bot.str.get('cmd-id-self', 'Your ID is `{0}`').format(author.id), reply=True, delete_after=35)
    else:
        usr = user_mentions[0]
        return Response(bot.str.get('cmd-id-other', '**{0}**s ID is `{1}`').format(usr.name, usr.id), reply=True, delete_after=35)