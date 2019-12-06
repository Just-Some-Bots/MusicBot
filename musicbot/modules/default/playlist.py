from discord.ext.commands import Cog, command, group
from discord import User

from typing import Optional, Union
from datetime import timedelta

from ... import exceptions

from ...constants import DISCORD_MSG_CHAR_LIMIT
from ...utils import ftimedelta
from ...command_injector import InjectableMixin, inject_as_subcommand
from ...rich_guild import get_guild
from ...playback import Playlist, PlayerState
from ... import messagemanager


class PlaylistManagement(InjectableMixin, Cog):
    @inject_as_subcommand('list')
    @command(name = 'playlist')
    async def listplaylist(self, ctx):
        """
        Usage:
            {command_prefix}list playlist

        List all playlists in the guild.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        pls = []
        apls = []

        for name, pl in guild._playlists.items():
            if pl not in guild._autos:
                pls.append(name)

        for pl in guild._autos:
            apls.append(pl._name)

        plmsgtitle = 'playlist{}'.format('s' if len(pls)>1 else '')
        plmsgdesc = '\n'.join(pls) if pls else None
        
        aplmsgtitle = 'autoplaylist{}'.format('s' if len(apls)>1 else '')
        aplmsgdesc = '\n'.join(apls) if apls else None

        await messagemanager.safe_send_normal(ctx, ctx,
            [
                {'name': plmsgtitle, 'value': plmsgdesc, 'inline': False},
                {'name': aplmsgtitle, 'value': aplmsgdesc, 'inline': False}
            ]
        )

    async def add_pl(self, ctx, name):
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if name in guild._playlists:
            raise exceptions.CommandError('There is already a playlist with that name.')
        else:
            guild._playlists[name] = Playlist(name, bot)
            await guild.serialize_playlist(guild._playlists[name])
            return guild._playlists[name]

    @inject_as_subcommand('add')
    @command(name = 'playlist')
    async def addplaylist(self, ctx, name):
        """
        Usage:
            {command_prefix}add playlist name

        Add a playlist.
        """
        await self.add_pl(ctx, name)
        await messagemanager.safe_send_normal(ctx, ctx, 'added playlist: {}'.format(name))
        

    @inject_as_subcommand('add')
    @group(name = 'entries', invoke_without_command=False)
    async def addentries(self, ctx):
        """
        A command group for adding entries to the playlist
        """

    @inject_as_subcommand('add entries')
    @command(name = 'playlist')
    async def addentriesplaylist(self, ctx, name, target = None):
        """
        Usage:
            {command_prefix}add entries playlist name [target]

        Append entries from a playlist to the target.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        if target:
            g_pl = guild._playlists[target]
        else:
            g_pl = await guild.get_playlist()

        if name not in guild._playlists:
            raise exceptions.CommandError('There is already a playlist with that name.')
        else:
            for e in guild._playlists[name]._list:
                bot.log.debug('{} ({})'.format(e, e.source_url))
                await g_pl.add_entry(e)
            await guild.serialize_playlist(g_pl)

        await messagemanager.safe_send_normal(ctx, ctx, 'imported entries from playlist: {}'.format(name))

    @inject_as_subcommand('list')
    @command(name = 'entries')
    async def listentries(self, ctx, name = None):
        """
        Usage:
            {command_prefix}list entries [playlist_name]

        Prints the playlist, if playlist name is unspecified the command prints the active playlist.
        """

        guild = get_guild(ctx.bot, ctx.guild)

        lines = []

        if not name:
            player = await guild.get_player()
            entry = await player.get_current_entry()
            playlist = await guild.get_playlist()

            if (await player.status()) == PlayerState.PLAYING:
                # TODO: Fix timedelta garbage with util function
                song_progress = ftimedelta(timedelta(seconds=await player.progress()))
                song_total = ftimedelta(timedelta(seconds=entry.duration))
                prog_str = '`[%s/%s]`' % (song_progress, song_total)

                if entry.queuer_id:
                    lines.append(ctx.bot.str.get('cmd-queue-playing-author', "Currently playing: `{0}` added by `{1}` {2}\n").format(
                        entry.title, guild.guild.get_member(entry.queuer_id).name, prog_str))
                else:
                    lines.append(ctx.bot.str.get('cmd-queue-playing-noauthor', "Currently playing: `{0}` {1}\n").format(entry.title, prog_str))
        else:
            playlist = guild._playlists[name]

        unlisted = 0
        andmoretext = '* ... and %s more*' % (await playlist.get_length())

        for i, item in enumerate(playlist):
            if item.queuer_id:
                nextline = ctx.bot.str.get('cmd-queue-entry-author', '{0} -- `{1}` by `{2}`').format(i+1, item.title, guild.guild.get_member(item.queuer_id).name).strip()
            else:
                nextline = ctx.bot.str.get('cmd-queue-entry-noauthor', '{0} -- `{1}`').format(i+1, item.title).strip()

            currentlinesum = sum(len(x) + 1 for x in lines)  # +1 is for newline char

            if (currentlinesum + len(nextline) + len(andmoretext) > DISCORD_MSG_CHAR_LIMIT) or (i > ctx.bot.config.queue_length):
                if currentlinesum + len(andmoretext):
                    unlisted += 1
                    continue

            lines.append(nextline)

        if unlisted:
            lines.append(ctx.bot.str.get('cmd-queue-more', '\n... and %s more') % unlisted)

        if not lines:
            lines.append(
                ctx.bot.str.get('cmd-queue-none', 'There are no songs queued! Queue something with {}play.').format(ctx.bot.config.command_prefix))

        message = '\n'.join(lines)
        await messagemanager.safe_send_normal(ctx, ctx, message, expire_in=30)

    @inject_as_subcommand('remove')
    @command(name = 'playlist')
    async def removeplaylist(self, ctx, name):
        """
        Usage:
            {command_prefix}remove playlist name

        Remove a playlist.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if name in guild._playlists:
            pl = guild._playlists[name]
            if pl is guild._internal_auto:
                # @TheerapakG: TODO: figure out if toggling then maybe move to next playlist?
                raise exceptions.CommandError('This playlist is in use.')
            elif pl in guild._autos:
                guild._autos.remove(pl)
                await guild.remove_serialized_playlist(name)
                del guild._playlists[name]
                await guild.serialize_to_file()
            else:
                await guild.remove_serialized_playlist(name)
                del guild._playlists[name]
        else:
            raise exceptions.CommandError('There is not any playlist with that name.')

        await messagemanager.safe_send_normal(ctx, ctx, 'removed playlist: {}'.format(name))

    @command()
    async def swap(self, ctx, name):
        """
        Usage:
            {command_prefix}swap name

        Swap currently playing playlist.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        prev = await guild.get_playlist()

        if name in guild._playlists:
            pl = guild._playlists[name]
            if pl is guild._internal_auto:
                raise exceptions.CommandError('This playlist is not swapable.')
            elif pl in guild._autos:
                raise exceptions.CommandError('This playlist is not swapable.')
            else:
                await guild.set_playlist(pl)
                await guild.serialize_to_file()
        else:
            raise exceptions.CommandError('There is not any playlist with that name.')

        await messagemanager.safe_send_normal(ctx, ctx, 'swapped playlist from {} to {}'.format(prev._name, name))

    @inject_as_subcommand('add entries')
    @command(name = 'url')
    async def addentriesurl(self, ctx, url, name = None):
        """
        Usage:
            {command_prefix}add entries url url [name]

        Retrieve entries of playlist from url and save it as a playlist named name.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        pl = await self.add_pl(ctx, name if name else (await guild.get_playlist())._name)
        await bot.crossmodule.async_call_object('_play', ctx, pl, url, send_reply = False)
        await guild.serialize_playlist(pl)

        await messagemanager.safe_send_normal(ctx, ctx, 'imported playlist from {} to {}'.format(url, name))

    @inject_as_subcommand('remove')
    @command(name = 'entry')
    async def removeentry(self, ctx, index:Optional[Union[int, User]]=None, name:Optional[str]=None):
        """
        Usage:
            {command_prefix}remove entry [# in playlist] [name]

        Removes entries in the specified playlist. If a number is specified, removes that song in the queue, 
        otherwise removes the most recently queued song. If playlist is unspecified, playlist is assumed to be the active playlist
        """
        guild = get_guild(ctx.bot, ctx.guild)
        if name:
            playlist = guild._playlists[name]
        else:
            playlist = await guild.get_playlist()

        permissions = ctx.bot.permissions.for_user(ctx.author)

        num = await playlist.get_length()

        if num == 0:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-remove-none', "There's nothing to remove!"), expire_in=20)

        if isinstance(index, User):
            if permissions.remove or ctx.author == index:
                try:
                    entry_indexes = [e for e in playlist if e.queuer_id == index.id]
                    for entry in entry_indexes:
                        pos = await playlist.get_entry_position(entry)
                        await playlist.remove_position(pos)
                    entry_text = '%s ' % len(entry_indexes) + 'item'
                    if len(entry_indexes) > 1:
                        entry_text += 's'
                    await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-remove-reply', "Removed `{0}` added by `{1}`").format(entry_text, index.name).strip())
                    return

                except ValueError:
                    raise exceptions.CommandError(ctx.bot.str.get('cmd-remove-missing', "Nothing found in the queue from user `%s`") % index.name, expire_in=20)

            raise exceptions.PermissionsError(
                ctx.bot.str.get('cmd-remove-noperms', "You do not have the valid permissions to remove that entry from the queue, make sure you're the one who queued it or have instant skip permissions"),
                expire_in=20
            )

        if not index:
            index = num

        try:
            index = int(index)
        except (TypeError, ValueError):
            raise exceptions.CommandError(ctx.bot.str.get('cmd-remove-invalid', "Invalid number. Use {}list entries to find queue positions.").format(ctx.bot.config.command_prefix), expire_in=20)

        if index > num:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-remove-invalid', "Invalid number. Use {}list entries to find queue positions.").format(ctx.bot.config.command_prefix), expire_in=20)

        if permissions.remove or ctx.author.id == playlist[index - 1].queuer_id:
            entry = await playlist.remove_position((index - 1))
            if entry.queuer_id:
                await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-remove-reply-author', "Removed entry `{0}` added by `{1}`").format(entry.title, guild.guild.get_member(entry.queuer_id)).strip())
                return
            else:
                await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-remove-reply-noauthor', "Removed entry `{0}`").format(entry.title).strip())
                return
        else:
            raise exceptions.PermissionsError(
                ctx.bot.str.get('cmd-remove-noperms', "You do not have the valid permissions to remove that entry from the queue, make sure you're the one who queued it or have instant skip permissions"), expire_in=20
            )
            

cogs = [PlaylistManagement]
deps = ['default.base']