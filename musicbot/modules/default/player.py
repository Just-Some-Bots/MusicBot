import glob, os
import asyncio
from functools import partial

from discord.ext.commands import Cog, command, group
from discord import User, VoiceChannel

from typing import Optional, Union, AnyStr, DefaultDict, Dict
from datetime import timedelta
from collections import defaultdict
from threading import RLock

from ... import exceptions

from ...constants import DISCORD_MSG_CHAR_LIMIT
from ...utils import ftimedelta
from ...command_injector import InjectableMixin, inject_as_subcommand, inject_as_main_command, inject_as_group
from ...smart_guild import SmartGuild, get_guild
from ...playback import Player as PlayerObj
from ...playback import Playlist, PlayerState
from ...ytdldownloader import get_unprocessed_entry
from ... import messagemanager

class Player(InjectableMixin, Cog):
    playlists: Optional[DefaultDict[SmartGuild, Dict[str, Playlist]]]
    player: Dict[SmartGuild, PlayerObj] = dict()
    _lock: DefaultDict[str, RLock] = DefaultDict(RLock)

    def __init__(self):
        self.bot = None

    def pre_init(self, bot):
        self.bot = bot
        self.playlists = bot.crossmodule.get_object('playlists')
        self.bot.crossmodule.register_object('player', self.player)
        self.bot.crossmodule.register_object('serialize_player', self.serialize_player)
        self.bot.crossmodule.register_object('write_current_song', self.write_current_song)
        self.bot.crossmodule.register_object('set_playlist', self.set_playlist)
        self.bot.crossmodule.register_object('get_playlist', self.get_playlist)

    def serialize_player(self, guild: SmartGuild):
        """
        Serialize the current player for a server's player to json.
        """
        dir = self._save_dir + '/queue.json'

        with self._lock['{}_serialization'.format(guild._id)]:
            self.bot.log.debug("Serializing queue for %s", guild._id)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(self.player[guild].serialize(sort_keys=True))
            
            pl = self.player.get_playlist()
            if pl:
                self.serialize_playlist(pl)

    def write_current_song(self, guild: SmartGuild, entry, *, dir=None):
        """
        Writes the current song to file
        """
        dir = self._save_dir + '/current.txt'

        with self._lock['{}_current_song'.format(guild._id)]:
            self.bot.log.debug("Writing current song for %s", guild._id)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(entry.title)

    # @TheerapakG: TODO: move auto stuff to auto cog
    async def on_player_play(self, guild, player, entry):
        self.bot.log.debug('Running on_player_play')
        await self.bot.update_now_playing_status(entry)
        guild.skip_state.reset()

        # This is the one event where its ok to serialize autoplaylist entries
        self.serialize_player(guild)

        if self.bot.config.write_current_song:
            self.write_current_song(guild, entry)

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
        # self.serialize_player(guild)

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

        self.serialize_player(guild)

    async def on_player_entry_added(self, guild, player, playlist, entry, **_):
        self.bot.log.debug('Running on_player_entry_added')
        if entry.queuer_id:
            self.serialize_player(guild)

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

    def on_guild_instantiate(self, guild):
        try:
            with open(guild._save_dir + '/queue.json', 'r', encoding='utf8') as f:
                playerdata = f.read()
                self.player[guild] = self.apply_player_hooks(Player.from_json(playerdata, guild), guild)
        except Exception as e:
            self.bot.log.exception('cannot deserialize queue, using default one')
            self.bot.log.exception(e)
            self.player[guild] = self.apply_player_hooks(Player(guild), guild)

        channel = None

        if guild in self.bot.autojoin_channel_map:
            channel = self.bot.autojoin_channel_map[guild]

        if guild.guild.me.voice:
            self.bot.log.info("Found resumable voice channel {0.guild.name}/{0.name}".format(guild.guild.me.voice.channel))
            channel = guild.guild.me.voice.channel

        if self.bot.config.auto_summon:
            owner = guild.get_owner(voice=True)
            for own in owner:
                self.log.info("Found owner in \"{}\"".format(own.voice.channel.name))
                channel = own.voice.channel
                break

        elif channel and isinstance(channel, VoiceChannel):
            self.log.info("Attempting to join {0.guild.name}/{0.name}".format(channel))

            chperms = channel.permissions_for(guild.guild.me)

            if not chperms.connect:
                self.log.info("Cannot join channel \"{}\", no permission.".format(channel.name))

            elif not chperms.speak:
                self.log.info("Will not join channel \"{}\", no permission to speak.".format(channel.name))

            else:
                try:
                    asyncio.ensure_future(self.player[guild].voice.set_voice_channel(channel))

                    self.log.info("Joined {0.guild.name}/{0.name}".format(channel))

                    if not player._playlist._list:
                        player.pause()
                        self.bot.server_specific_data[guild]['auto_paused'] = True

                except Exception:
                    self.log.debug("Error joining {0.guild.name}/{0.name}".format(channel), exc_info=True)
                    self.log.error("Failed to join {0.guild.name}/{0.name}".format(channel))

        elif channel:
            self.log.warning("Not joining {0.guild.name}/{0.name}, that's a text channel.".format(channel))

        else:
            self.log.warning("Invalid channel thing: {}".format(channel))  

        guild.on('serialize', self.serialize_player)

    def set_playlist(self, guild, playlist):
        self.player[guild].set_playlist(playlist)

    def get_playlist(self, guild):
        return self.player[guild].get_playlist()

    @command()
    async def np(self, ctx):
        """
        Usage:
            {command_prefix}np

        Displays the current song in chat.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = self.player[guild]
        entry = player.get_current_entry()

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
            player = self.player[guild]
            entry = player.get_current_entry()
            playlist = bot.call('get_playlist', guild)

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

cogs = [Player]
deps = ['default.base', 'default.playlist']