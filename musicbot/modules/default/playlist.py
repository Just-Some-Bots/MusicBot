from discord.ext.commands import Cog, command, group
from discord import User

from typing import Optional, Union, AnyStr
from datetime import timedelta

from ... import exceptions

from ...constants import DISCORD_MSG_CHAR_LIMIT
from ...utils import ftimedelta
from ...command_injector import InjectableMixin, inject_as_subcommand, inject_as_main_command, inject_as_group
from ...smart_guild import get_guild
from ...playback import Playlist, PlayerState
from ...ytdldownloader import get_unprocessed_entry
from ... import messagemanager


class PlaylistManagement(InjectableMixin, Cog):
    @inject_as_main_command('playlist', invoke_without_command=False)
    @inject_as_group
    async def playlist(self, ctx):
        """
        A command group for managing playlist
        """
        pass

    @inject_as_subcommand('list', name = 'playlist')
    @inject_as_subcommand('playlist', name = 'list', after = 'inject_playlist')
    async def listplaylist(self, ctx):
        """
        Usage:
            {command_prefix}list playlist

        List all playlists in the guild.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        pls = []
        apl = None

        for name, pl in guild._playlists.items():
            if pl is not guild._auto:
                pls.append(name)

        if guild._auto:
            apl = guild._auto._name

        plmsgtitle = 'playlist{}'.format('s' if len(pls)>1 else '')
        plmsgdesc = '\n'.join(pls) if pls else None
        
        aplmsgtitle = 'autoplaylist'
        aplmsgdesc = apl

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

    @inject_as_subcommand('add', name = 'playlist')
    @inject_as_subcommand('playlist', name = 'add', after = 'inject_playlist')
    async def addplaylist(self, ctx, name):
        """
        Usage:
            {command_prefix}add playlist name

        Add a playlist.
        """
        await self.add_pl(ctx, name)
        await messagemanager.safe_send_normal(ctx, ctx, 'added playlist: {}'.format(name))
        

    @inject_as_subcommand('add', name = 'entries', invoke_without_command=False)
    @inject_as_group
    async def addentries(self, ctx):
        """
        A command group for adding entries to the playlist
        """

    @inject_as_subcommand('add entries', name = 'playlist', after = 'inject_add_entries')
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
            raise exceptions.CommandError('There is not any playlist with that name.')
        else:
            for e in guild._playlists[name]._list:
                bot.log.debug('{} ({})'.format(e, e.source_url))
                # @TheerapakG: TODO: make unprocessed from processed
                await g_pl.add_entry(await get_unprocessed_entry(e.source_url, ctx.author.id, bot.downloader, dict()))
            await guild.serialize_playlist(g_pl)

        await messagemanager.safe_send_normal(ctx, ctx, 'imported entries from playlist: {}'.format(name))

    @inject_as_subcommand('list', name = 'entries')
    @inject_as_main_command('queue')
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

        for i, item in enumerate(await playlist[:]):
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

    @inject_as_subcommand('remove', name = 'playlist')
    @inject_as_subcommand('playlist', name = 'remove', after = 'inject_playlist')
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
            if pl is guild._auto:
                guild._auto = None
                if (await guild.is_currently_auto()):
                    await guild.return_from_auto()
                await guild.remove_serialized_playlist(name)
                del guild._playlists[name]
                await guild.serialize_to_file()
            elif pl is (await guild.get_playlist()):
                raise exceptions.CommandError('Playlist is currently in use.')
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
            if pl is guild._auto:
                raise exceptions.CommandError('This playlist is not swapable (is autoplaylist).')
            else:
                await guild.set_playlist(pl)
                await guild.serialize_to_file()
        else:
            raise exceptions.CommandError('There is not any playlist with that name.')

        await messagemanager.safe_send_normal(ctx, ctx, 'swapped playlist from {} to {}'.format(prev._name, name))

    @inject_as_subcommand('add entries', name = 'url', after = 'inject_add_entries')
    async def addentriesurl(self, ctx, url, name = None):
        """
        Usage:
            {command_prefix}add entries url url [name]

        Retrieve entries of playlist from url and save it as a playlist named name.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        pl = guild._playlists[name] if name else (await guild.get_playlist())
        await bot.crossmodule.async_call_object('_play', ctx, pl, url, send_reply = False)
        await guild.serialize_playlist(pl)

        await messagemanager.safe_send_normal(ctx, ctx, 'imported playlist from {} to {}'.format(url, pl._name))

    @inject_as_subcommand('remove', name = 'entry')
    @inject_as_main_command('re')
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
                    await guild.serialize_playlist(playlist)
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
            await guild.serialize_playlist(playlist)
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

    @inject_as_subcommand('remove', name = 'entries')
    @inject_as_main_command(['clear', 'res'])
    async def clear(self, ctx, name: Optional[AnyStr] = None):
        """
        Usage:
            {command_prefix}clear

        Clears the playlist.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        if name:
            playlist = guild._playlists[name]
        else:
            playlist = await guild.get_playlist()

        await playlist.clear()
        await guild.serialize_playlist(playlist)
        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-clear-reply', "Cleared `{0}`").format(playlist._name), expire_in=20)
            

cogs = [PlaylistManagement]
deps = ['default.base']