import glob, os
from functools import partial

from discord.ext.commands import Cog, command, group
from discord import User

from typing import Optional, Union, AnyStr, DefaultDict, List
from datetime import timedelta
from collections import defaultdict

from ... import exceptions

from ...constants import DISCORD_MSG_CHAR_LIMIT
from ...utils import ftimedelta
from ...command_injector import InjectableMixin, inject_as_subcommand, inject_as_main_command, inject_as_group
from ...smart_guild import SmartGuild, get_guild
from ...playback import Player, Playlist, PlayerState
from ...ytdldownloader import get_unprocessed_entry
from ... import messagemanager

class PlaylistManagement(InjectableMixin, Cog):
    playlists: DefaultDict[SmartGuild, Dict[str, Playlist]] = defaultdict(dict)
    player: Dict[SmartGuild, Player] = dict()

    def __init__(self):
        self.bot = None

    def pre_init(self, bot):
        self.bot = bot
        self.bot.crossmodule.register_object('playlists', self.playlists)
        self.bot.crossmodule.register_object('player', self.player)

    # @TheerapakG: TODO: deserialize playlists and players to this cog instead of guild
    # @TheerapakG: TODO: move auto stuff to auto cog
    async def on_player_play(self, guild, player, entry):
        self.bot.log.debug('Running on_player_play')
        await self.bot.update_now_playing_status(entry)
        guild.skip_state.reset()

        # This is the one event where its ok to serialize autoplaylist entries
        guild.serialize_queue()

        if self.bot.config.write_current_song:
            guild.write_current_song(entry)

        if not guild.is_currently_auto():
            channel = entry._metadata.get('channel', None)
            author = guild.guild.get_member(entry.queuer_id)

            if author:
                author_perms = self.bot.permissions.for_user(author)

                if author not in player.voice.voice_channel().members and author_perms.skip_when_absent:
                    newmsg = 'Skipping next song in `%s`: `%s` added by `%s` as queuer not in voice' % (
                        player.voice.voice_channel().name, entry.title, author.name)
                    await player.skip()
                elif self.bot.config.now_playing_mentions:
                    newmsg = '%s - your song `%s` is now playing in `%s`!' % (
                        author.mention, entry.title, player.voice.voice_channel().name)
                else:
                    newmsg = 'Now playing in `%s`: `%s` added by `%s`' % (
                        player.voice.voice_channel().name, entry.title, author.name)
            elif entry.queuer_id:
                if author_perms.skip_when_absent:
                    newmsg = 'Skipping next song in `%s`: `%s` added by user id `%s` as queuer already left the guild' % (
                        player.voice.voice_channel().name, entry.title, entry.queuer_id)
                    await player.skip()
                else:
                    newmsg = 'Now playing in `%s`: `%s` added by user id `%s`' % (
                        player.voice.voice_channel().name, entry.title, entry.queuer_id)
        else:
            # it's an autoplaylist
            channel = None
            author = None            
            newmsg = 'Now playing automatically added entry `%s` in `%s`' % (
                entry.title, player.voice.voice_channel().name)

        if newmsg:
            if self.bot.config.dm_nowplaying and author:
                await messagemanager.safe_send_message(author, newmsg)
                return

            if self.bot.config.no_nowplaying_auto and not author:
                return

            last_np_msg = self.bot.server_specific_data[guild]['last_np_msg']

            if self.bot.config.nowplaying_channels:
                for potential_channel_id in self.bot.config.nowplaying_channels:
                    potential_channel = self.bot.get_channel(potential_channel_id)
                    if potential_channel and potential_channel.guild == guild.guild:
                        channel = potential_channel
                        break

            meta = entry.get_metadata()

            if channel:
                pass
            elif 'channel_id' in meta:
                channel = guild.guild.get_channel(meta['channel_id'])
            elif not channel and last_np_msg:
                channel = last_np_msg.channel
            else:
                self.bot.log.debug('no channel to put now playing message into')
                return

            # send it in specified channel
            self.bot.server_specific_data[guild]['last_np_msg'] = await messagemanager.safe_send_message(channel, newmsg)

        # TODO: Check channel voice state?

    async def on_player_resume(self, guild, player, entry, **_):
        self.bot.log.debug('Running on_player_resume')
        await self.bot.update_now_playing_status(entry)

    async def on_player_pause(self, guild, player, entry, **_):
        self.bot.log.debug('Running on_player_pause')
        await self.bot.update_now_playing_status(entry, True)
        # await self.serialize_queue(self)

    async def on_player_stop(self, guild, player, **_):
        self.bot.log.debug('Running on_player_stop')
        await self.bot.update_now_playing_status()

    async def on_player_finished_playing(self, guild, player, **_):
        self.bot.log.debug('Running on_player_finished_playing')

        # delete last_np_msg somewhere if we have cached it
        if self.bot.config.delete_nowplaying:
            last_np_msg = self.bot.server_specific_data[guild]['last_np_msg']
            if last_np_msg:
                await messagemanager.safe_delete_message(last_np_msg)
        
        def _autopause(player):
            if self.bot._check_if_empty(player.voice.voice_channel()):
                self.bot.log.info("Player finished playing, autopaused in empty channel")

                player.pause()
                self.bot.server_specific_data[guild]['auto_paused'] = True

        current = player.get_playlist()
        with guild._lock['c_auto']:
            if await current.get_length() == 0 and guild._auto:
                self.bot.log.info("Entering auto in {}".format(guild._id))
                guild._not_auto = current
                player.set_playlist(guild._auto)
                player.random = guild.config.auto_random
                player.pull_persist = True

                if self.bot.config.auto_pause:
                    player.once('play', lambda player, **_: _autopause(player))

        await guild.serialize_queue()

    async def on_player_entry_added(self, guild, player, playlist, entry, **_):
        self.bot.log.debug('Running on_player_entry_added')
        if entry.queuer_id:
            await guild.serialize_queue()

    async def on_player_error(self, guild, player, entry, ex, **_):
        if 'channel_id' in entry._metadata:
            await messagemanager.safe_send_message(
                guild.guild.get_channel(entry._metadata['channel_id']),
                "```\nError from FFmpeg:\n{}\n```".format(ex)
            )
        else:
            self.bot.log.exception("Player error", exc_info=ex)

    def apply_player_hooks(self, player, guild):
        return player.on('play', partial(self.on_player_play, self, guild)) \
                    .on('resume', partial(self.on_player_resume, self, guild)) \
                    .on('pause', partial(self.on_player_pause, self, guild)) \
                    .on('stop', partial(self.on_player_stop, self, guild)) \
                    .on('finished-playing', partial(self.on_player_finished_playing, self, guild)) \
                    .on('entry-added', partial(self.on_player_entry_added, self, guild)) \
                    .on('error', partial(self.on_player_error, self, guild))

    def deserialize_playlists(self, guild):
        """
        Deserialize playlists for the server.
        """
        for path in glob.iglob(os.path.join(guild._save_dir + '/playlists', '*.json')):
            with open(path, 'r') as f:
                data = f.read()
                playlist = Playlist.from_json(data, self.bot, self.bot.downloader)
                self.playlists[guild][playlist._name] = playlist

        try:
            with open(guild._save_dir + '/queue.json', 'r', encoding='utf8') as playerf:
                playerdata = playerf.read()
                self.player[guild] = self.apply_player_hooks(Player.from_json(playerdata, guild), guild)
        except Exception as e:
            self.bot.log.exception('cannot deserialize queue, using default one')
            self.bot.log.exception(e)
            self.player[guild] = self.apply_player_hooks(Player(guild), guild)       

        data_auto = guild.data['_auto']
        guild._auto = self.playlists[data_auto] if data_auto else None

        data_not_auto = guild.data['_not_auto']
        guild._not_auto = self.playlists[data_not_auto] if data_not_auto else None

    def on_guild_instantiate(self, guild):
        self.deserialize_playlists(guild)

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

        for name, pl in self.playlists[guild].items():
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

        if name in self.playlists[guild]:
            raise exceptions.CommandError('There is already a playlist with that name.')
        else:
            self.playlists[guild][name] = Playlist(name, bot)
            await guild.serialize_playlist(self.playlists[guild][name])
            return self.playlists[guild][name]

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
            g_pl = self.playlists[guild][target]
        else:
            g_pl = await guild.get_playlist()

        if name not in self.playlists[guild]:
            raise exceptions.CommandError('There is not any playlist with that name.')
        else:
            for e in self.playlists[guild][name]._list:
                bot.log.debug('{} ({})'.format(e, e.source_url))
                # @TheerapakG: TODO: make unprocessed from processed
                await g_pl.add_entry(await get_unprocessed_entry(e.source_url, ctx.author.id, bot.downloader, dict()))
            await guild.serialize_playlist(g_pl)

        await messagemanager.safe_send_normal(ctx, ctx, 'imported entries from playlist: {}'.format(name))

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
            playlist = self.playlists[guild][name]

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

        if name in self.playlists[guild]:
            pl = self.playlists[guild][name]
            if pl is guild._auto:
                guild._auto = None
                if (await guild.is_currently_auto()):
                    await guild.return_from_auto()
                await guild.remove_serialized_playlist(name)
                del self.playlists[guild][name]
                await guild.serialize_to_file()
            elif pl is (await guild.get_playlist()):
                raise exceptions.CommandError('Playlist is currently in use.')
            else:
                await guild.remove_serialized_playlist(name)
                del self.playlists[guild][name]
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

        if name in self.playlists[guild]:
            pl = self.playlists[guild][name]
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

        pl = self.playlists[guild][name] if name else (await guild.get_playlist())
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
            playlist = self.playlists[guild][name]
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
            playlist = self.playlists[guild][name]
        else:
            playlist = await guild.get_playlist()

        await playlist.clear()
        await guild.serialize_playlist(playlist)
        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-clear-reply', "Cleared `{0}`").format(playlist._name), expire_in=20)

    @command()
    async def karaoke(self, ctx):
        """
        Usage:
            {command_prefix}karaoke

        Activates karaoke mode. During karaoke mode, only groups with the BypassKaraokeMode
        permission in the config file can queue music.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        playlist = await guild.get_playlist()
        playlist.karaoke_mode = not playlist.karaoke_mode
        await messagemanager.safe_send_normal(ctx, ctx, "\N{OK HAND SIGN} Karaoke mode is now " + ['disabled', 'enabled'][playlist.karaoke_mode], expire_in=15)
            

cogs = [PlaylistManagement]
deps = ['default.base']