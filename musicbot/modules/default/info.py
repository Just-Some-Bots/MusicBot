import discord

import logging
from io import BytesIO
from datetime import timedelta
from collections import defaultdict
from typing import Optional

from discord.ext.commands import Cog, command

from ... import exceptions
from ...rich_guild import get_guild
from ...utils import ftimedelta
from ...command_injector import InjectableMixin, inject_as_subcommand, inject_as_main_command

from ... import messagemanager

log = logging.getLogger(__name__)

class Information(InjectableMixin, Cog):
    @command()
    async def pldump(self, ctx, *, song_url:str):
        """
        Usage:
            {command_prefix}pldump url

        Dumps the individual urls of a playlist
        """

        try:
            info = await ctx.bot.downloader.extract_info(song_url.strip('<>'), download=False, process=False)
        except Exception as e:
            raise exceptions.ExtractionError("Could not extract info from input url\n%s\n" % e, expire_in=25)

        if not info:
            raise exceptions.ExtractionError("Could not extract info from input url, no data.", expire_in=25)

        if not info.get('entries', None):
            # TODO: Retarded playlist checking
            # set(url, webpageurl).difference(set(url))

            if info.get('url', None) != info.get('webpage_url', info.get('url', None)):
                raise exceptions.ExtractionError("This does not seem to be a playlist.", expire_in=25)
            else:
                return await self.pldump(ctx, song_url = info.get(''))

        linegens = defaultdict(lambda: None, **{
            "youtube":    lambda d: 'https://www.youtube.com/watch?v=%s' % d['id'],
            "soundcloud": lambda d: d['url'],
            "bandcamp":   lambda d: d['url']
        })

        exfunc = linegens[info['extractor'].split(':')[0]]

        if not exfunc:
            raise exceptions.ExtractionError("Could not extract info from input url, unsupported playlist type.", expire_in=25)

        with BytesIO() as fcontent:
            for item in info['entries']:
                fcontent.write(exfunc(item).encode('utf8') + b'\n')

            fcontent.seek(0)
            await messagemanager.safe_send_message(ctx.author, "Here's the playlist dump for <%s>" % song_url, file=discord.File(fcontent, filename='playlist.txt'))

        return messagemanager.safe_send_normal(ctx, ctx, "Sent a message with a playlist file.", expire_in=20)


    @inject_as_subcommand('list', name = 'ids')
    @inject_as_main_command('listids')
    async def listids(self, ctx, *, cat:Optional[str]='all'):
        """
        Usage:
            {command_prefix}list ids [categories]

        Lists the ids for various things.  Categories are:
            all, users, roles, channels
        """

        cats = ['channels', 'roles', 'users']

        if cat not in cats and cat != 'all':
            await messagemanager.safe_send_normal(
                ctx,
                ctx,
                "Valid categories: " + ' '.join(['`%s`' % c for c in cats]),
                reply=True,
                expire_in=25
            )
            return

        if cat == 'all':
            requested_cats = cats
        else:
            requested_cats = [c.strip(',') for c in cat]

        data = ['Your ID: %s' % ctx.author.id]

        for cur_cat in requested_cats:
            rawudata = None

            if cur_cat == 'users':
                data.append("\nUser IDs:")
                rawudata = ['%s #%s: %s' % (m.name, m.discriminator, m.id) for m in ctx.guild.members]

            elif cur_cat == 'roles':
                data.append("\nRole IDs:")
                rawudata = ['%s: %s' % (r.name, r.id) for r in ctx.guild.roles]

            elif cur_cat == 'channels':
                data.append("\nText Channel IDs:")
                tchans = [c for c in ctx.guild.channels if isinstance(c, discord.TextChannel)]
                rawudata = ['%s: %s' % (c.name, c.id) for c in tchans]

                rawudata.append("\nVoice Channel IDs:")
                vchans = [c for c in ctx.guild.channels if isinstance(c, discord.VoiceChannel)]
                rawudata.extend('%s: %s' % (c.name, c.id) for c in vchans)

            if rawudata:
                data.extend(rawudata)

        with BytesIO() as sdata:
            sdata.writelines(d.encode('utf8') + b'\n' for d in data)
            sdata.seek(0)

            # TODO: Fix naming (Discord20API-ids.txt)
            await messagemanager.safe_send_message(ctx.author, discord.File(sdata, filename='%s-ids-%s.txt' % (ctx.guild.name.replace(' ', '_'), cat)))

        await messagemanager.safe_send_normal(ctx, ctx, "Sent a message with a list of IDs.", expire_in=20)

    @command()
    async def perms(self, ctx, user:Optional[discord.User]):
        """
        Usage:
            {command_prefix}perms [user_id|user_mention|user_name#discrim|user_name]

        Sends the user a list of their permissions, or the permissions of the user specified.
        """
        member = ctx.guild.get_member(user.id)
        if member:
            user = member

        if user:
            permissions = ctx.bot.permissions.for_user(user)

        if user == ctx.author:
            lines = ['Command permissions in %s\n' % ctx.guild.name, '```', '```']
        else:
            lines = ['Command permissions for {} in {}\n'.format(user.name, ctx.guild.name), '```', '```']

        for perm in permissions.__dict__:
            if perm in ['user_list'] or permissions.__dict__[perm] == set():
                continue

            lines.insert(len(lines) - 1, "%s: %s" % (perm, permissions.__dict__[perm]))

        await messagemanager.safe_send_normal(ctx, ctx.author, '\n'.join(lines))
        await messagemanager.safe_send_normal(ctx, ctx, "\N{OPEN MAILBOX WITH RAISED FLAG}", expire_in=20)

    @command()
    async def np(self, ctx):
        """
        Usage:
            {command_prefix}np

        Displays the current song in chat.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()
        entry = await player.get_current_entry()

        if entry:
            if ctx.bot.server_specific_data[guild]['last_np_msg']:
                await messagemanager.safe_delete_message(ctx.bot.server_specific_data[guild]['last_np_msg'])
                ctx.bot.server_specific_data[guild]['last_np_msg'] = None

            # TODO: Fix timedelta garbage with util function
            song_progress = ftimedelta(timedelta(seconds=await player.progress()))
            song_total = ftimedelta(timedelta(seconds=entry.duration)) if entry.duration != None else '(no duration data)'

            streaming = entry.stream
            prog_str = ('`[{progress}]`' if streaming else '`[{progress}/{total}]`').format(
                progress=song_progress, total=song_total
            )
            prog_bar_str = ''

            # percentage shows how much of the current song has already been played
            percentage = 0.0
            if entry.duration and entry.duration > 0:
                percentage = (await player.progress()) / entry.duration

            # create the actual bar
            progress_bar_length = 30
            for i in range(progress_bar_length):
                if (percentage < 1 / progress_bar_length * i):
                    prog_bar_str += '□'
                else:
                    prog_bar_str += '■'

            action_text = ctx.bot.str.get('cmd-np-action-streaming', 'Streaming') if streaming else ctx.bot.str.get('cmd-np-action-playing', 'Playing')

            if entry.queuer_id:
                np_text = ctx.bot.str.get('cmd-np-reply-author', "Now {action}: **{title}** added by **{author}**\nProgress: {progress_bar} {progress}\n\N{WHITE RIGHT POINTING BACKHAND INDEX} <{url}>").format(
                    action=action_text,
                    title=entry.title,
                    author=guild.guild.get_member(entry.queuer_id).name,
                    progress_bar=prog_bar_str,
                    progress=prog_str,
                    url=entry.source_url
                )
            else:

                np_text = ctx.bot.str.get('cmd-np-reply-noauthor', "Now {action}: **{title}**\nProgress: {progress_bar} {progress}\n\N{WHITE RIGHT POINTING BACKHAND INDEX} <{url}>").format(

                    action=action_text,
                    title=entry.title,
                    progress_bar=prog_bar_str,
                    progress=prog_str,
                    url=entry.source_url
                )

            ctx.bot.server_specific_data[guild]['last_np_msg'] = await messagemanager.safe_send_message(ctx, np_text)
        else:
            raise exceptions.CommandError(
                ctx.bot.str.get('cmd-np-none', 'There are no songs queued! Queue something with {0}play.') .format(ctx.bot.config.command_prefix),
                expire_in=30
            )

    @command()
    async def id(self, ctx, user:Optional[discord.User]):
        """
        Usage:
            {command_prefix}id [user_id|user_mention|user_name#discrim|user_name]

        Tells the user their id or the id of another user.
        """
        if not user:
            await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-id-self', 'Your ID is `{0}`').format(ctx.author.id), reply=True, expire_in=35)
        else:
            await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-id-other', '**{0}**s ID is `{1}`').format(user.name, user.id), reply=True, expire_in=35)

cogs = [Information]
deps = ['default.base']