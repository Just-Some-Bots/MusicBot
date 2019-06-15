"""
MusicBot: The original Discord music bot written for Python 3.5+, using the discord.py library.
ModuBot: A modular discord bot with dependency management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The MIT License (MIT)

Copyright (c) 2019 TheerapakG
Copyright (c) 2019 Just-Some-Bots (https://github.com/Just-Some-Bots)

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from discord import Guild
import discord
from asyncio import Lock, ensure_future
from collections import defaultdict
import json
import os
import random
from .playback import Player, Playlist, PlayerState
from .constructs import SkipState, Serializable, Serializer
from .messagemanager import safe_send_message, safe_send_normal, safe_delete_message, content_gen, ContentTypeColor
from .ytdldownloader import get_entry, get_unprocessed_entry, get_stream_entry
from youtube_dl.utils import DownloadError
from . import exceptions

guilds = dict()

class RichGuild(Serializable):
    def __init__(self, bot, guildid):
        super().__init__()
        self._aiolocks = defaultdict(Lock)
        self._bot = bot
        self._id = guildid
        self._voice_channel = None
        self._voice_client = None
        self._player = None
        self._playlists = dict()
        self._playlists_active_path = dict()
        # @TheerapakG: _internal_auto hold entries that we're really autoing, _auto is just a playlist that 
        # hold entry in each category accordingly just to not get mixed up
        # @TheerapakG: we're holding object references in the _autos as that should take up less memory than holding strs
        self._autos = list()
        self._internal_auto = None
        self.skip_state = SkipState()
        self.autoplaylist = list()

    def __json__(self):
        # @TheerapakG: playlists are only stored as path as it's highly inefficient to serialize all lists when
        # we're shutting down
        return self._enclose_json({
            'version': 1,
            'id': self._id,
            'playlists': self._playlists_active_path,
            'autos': [p._name for p in self._autos],
            'internal_auto': self._internal_auto._name if self._internal_auto else None
        })

    @classmethod
    def _deserialize(cls, data, bot=None):
        assert bot is not None, cls._bad('bot')

        if 'version' not in data or data['version'] < 0:
            raise exceptions.VersionError('data version needs to be higher than 0')

        data_id = data.get('id')

        guild = cls(bot, data_id)

        async def unpack_playlists():
            data_pl = data.get('playlists')
            if data_pl:
                for plpath in data_pl:
                    await guild.deserialize_playlist(dir = plpath)

            data_autos = data.get('autos')
            if data_autos:
                guild._autos = [guild._playlists[plname] for plname in data_autos]

            data_internal_auto = data.get('internal_auto')
            guild._internal_auto = guild._playlists[data_internal_auto] if data_internal_auto else None

        ensure_future(unpack_playlists())

        return guild

    @classmethod
    def from_json(cls, raw_json, bot, guildid):
        try:
            obj = json.loads(raw_json, object_hook=Serializer.deserialize)
            if isinstance(obj, dict):
                bot.log.warning('Cannot parse incompatible rich guild data. Instantiating new rich guild instead.')
                bot.log.debug(raw_json)
                obj = cls(bot, guildid)
            if obj._id != guildid:
                bot.log.warning("Guild id contradict with id in the serialized data. Using current guild id instead")
                obj._id = guildid
            return obj
        except Exception as e:
            bot.log.exception("Failed to deserialize rich guild", e)

    @property
    def id(self):
        return self._id

    @property
    def guild(self):
        return self._bot.get_guild(self._id)

    async def serialize_to_file(self, *, dir=None):
        if dir is None:
            dir = 'data/{}/richguildinfo.json'.format(self._id)

        async with self._aiolocks['guild_serialization']:
            self._bot.log.debug("Serializing {}".format(self._id))

            with open(dir, 'w', encoding='utf8') as f:
                f.write(self.serialize(sort_keys=True))

    @classmethod
    def deserialize_from_file(cls, bot, guildid, *, dir=None):
        if dir is None:
            dir = 'data/{}/richguildinfo.json'.format(guildid)

        if not os.path.isfile(dir):
            bot.log.debug('Instantiating new rich guild for {}.'.format(guildid))
            return cls(bot, guildid)

        bot.log.debug("Deserializing {}".format(guildid))

        with open(dir, 'r', encoding='utf8') as f:
            data = f.read()
            guild = cls.from_json(data, bot, guildid)
            return guild

    async def serialize_playlist(self, playlist):
        """
        Serialize the playlist to json.
        """
        dir = 'data/{}/playlists/{}.json'.format(self._id, playlist._name)

        async with self._aiolocks['{}_serialization'.format(playlist._name)]:
            self._bot.log.debug("Serializing `{}` for {}".format(playlist._name, self._id))

            with open(dir, 'w', encoding='utf8') as f:
                f.write(playlist.serialize(sort_keys=True))
                self._playlists_active_path[playlist._name] = dir

    async def serialize_playlists(self):
        for p in self._playlists.copy():
            await self.serialize_playlist(p)

    async def remove_serialized_playlist(self, name):
        """
        Remove the playlist serialized to json.
        """
        dir = 'data/{}/playlists/{}.json'.format(self._id, name)

        if not os.path.isfile(dir):
            return

        async with self._aiolocks['{}_serialization'.format(name)]:
            self._bot.log.debug("Removing serialized `{}` for {}".format(name, self._id))
            try:
                del self._playlists_active_path[name]
            except KeyError:
                pass

            os.unlink(dir)

    async def deserialize_playlist(self, name = None, *, dir=None):
        """
        Deserialize specified playlist for the server.
        """
        if dir is None:
            dir = 'data/{}/playlists/{}.json'.format(self._id, name)

        if not os.path.isfile(dir):
            return None

        # @TheerapakG: Something ((dir.split('.'))[0]) that is uncertain, as all things should be
        async with self._aiolocks['{}_serialization'.format((dir.split('.'))[0])]:
            self._bot.log.debug("Deserializing `{}` for {}".format((dir.split('.'))[0], self._id))

            with open(dir, 'r', encoding='utf8') as f:
                data = f.read()
                playlist = Playlist.from_json(data, self._bot, self._bot.downloader)
                self._playlists[playlist._name] = playlist
                self._playlists_active_path[playlist._name] = dir

    async def deserialize_playlists(self, *, dir=None):
        """
        Deserialize all playlists for a server.
        """
        if dir is None:
            dir = 'data/%s/playlists' % self._id
            fs = [f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))]

        for fname in fs:
            # @TheerapakG: TODO: prevent playlist deletion if this is iterating
            # @TheerapakG: Something ((fname.split('.'))[0]) that is uncertain, as all things should be
            async with self._aiolocks['{}_serialization'.format((fname.split('.'))[0])]:
                self._bot.log.debug("Deserializing `{}` for {}".format((fname.split('.'))[0], self._id))

                with open(fname, 'r', encoding='utf8') as f:
                    data = f.read()
                    playlist = Playlist.from_json(data, self._bot, self._bot.downloader)
                    self._playlists[playlist._name] = playlist
                    self._playlists_active_path[playlist._name] = dir

    async def serialize_queue(self, *, dir=None):
        """
        Serialize the current queue for a server's player to json.
        """
        if not self._player:
            return

        if dir is None:
            dir = 'data/%s/queue.json' % self._id

        async with self._aiolocks['queue_serialization']:
            self._bot.log.debug("Serializing queue for %s", self._id)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(self._player.serialize(sort_keys=True))

    async def deserialize_queue(self, *, dir=None):
        """
        Deserialize a saved queue for a server into a Player.  If no queue is saved, returns None.
        """
        if dir is None:
            dir = 'data/%s/queue.json' % self._id

        async with self._aiolocks['queue_serialization']:
            if not os.path.isfile(dir):
                return None

            self._bot.log.debug("Deserializing queue for %s", self._id)

            with open(dir, 'r', encoding='utf8') as f:
                data = f.read()

        return Player.from_json(data, self, self._bot, self._bot.downloader)

    async def write_current_song(self, entry, *, dir=None):
        """
        Writes the current song to file
        """
        if not self._player:
            return

        if dir is None:
            dir = 'data/%s/current.txt' % self._id

        async with self._aiolocks['current_song']:
            self._bot.log.debug("Writing current song for %s", self._id)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(entry.title)

    async def get_connected_voice_channel(self):
        async with self._aiolocks['c_voice_channel']:
            return self._voice_channel

    async def _check_perm_connect(self, channel):
        perms = channel.permissions_for(self.guild.me)
        if not perms.connect:
            raise exceptions.VoiceConnectionError('Cannot join channel, no permission to connect.')
        elif not perms.speak:
            raise exceptions.VoiceConnectionError('Cannot join channel, no permission to speak.')

    async def _move_channel(self, new_channel):
        await self._check_perm_connect(new_channel)
        async with self._aiolocks['c_voice_channel']:
            await self._voice_client.move_to(new_channel)
            self._voice_channel = new_channel

    async def _disconnect_channel(self):
        async with self._aiolocks['c_voice_channel']:
            await self._voice_client.disconnect()
            self.voice_channel = None
            self._voice_client = None
            await self._player.kill()
            self._player = None

    async def _connect_channel(self, new_channel):
        await self._check_perm_connect(new_channel)
        async with self._aiolocks['c_voice_channel']:
            self._voice_client = await new_channel.connect()
            self.voice_channel = new_channel
            player = None

            if self._bot.config.persistent_queue:
                player = await self.deserialize_queue()
                if player:
                    self._bot.log.debug("Created player via deserialization for guild %s with %s entries", self._id, len(player._playlist._list) if player._playlist else 0)
            
            if not player:
                player = Player(self)

            if not player._playlist:
                await player.set_playlist(Playlist('default-{}'.format(self._id), self._bot))
                
            self._player = player.on('play', self.on_player_play) \
                                 .on('resume', self.on_player_resume) \
                                 .on('pause', self.on_player_pause) \
                                 .on('stop', self.on_player_stop) \
                                 .on('finished-playing', self.on_player_finished_playing) \
                                 .on('entry-added', self.on_player_entry_added) \
                                 .on('error', self.on_player_error)

    async def on_player_play(self, player, entry):
        self._bot.log.debug('Running on_player_play')
        await self._bot.update_now_playing_status(entry)
        self.skip_state.reset()

        # This is the one event where its ok to serialize autoplaylist entries
        await self.serialize_queue()

        if self._bot.config.write_current_song:
            await self.write_current_song(entry)

        channel = entry._metadata.get('channel', None)
        author = self.guild.get_member(entry.queuer_id)

        if author:
            author_perms = self._bot.permissions.for_user(author)

            if author not in self._voice_channel.members and author_perms.skip_when_absent:
                newmsg = 'Skipping next song in `%s`: `%s` added by `%s` as queuer not in voice' % (
                    self._voice_channel.name, entry.title, author.name)
                await player.skip()
            elif self._bot.config.now_playing_mentions:
                newmsg = '%s - your song `%s` is now playing in `%s`!' % (
                    author.mention, entry.title, self._voice_channel.name)
            else:
                newmsg = 'Now playing in `%s`: `%s` added by `%s`' % (
                    self._voice_channel.name, entry.title, author.name)
        elif entry.queuer_id:
            if author_perms.skip_when_absent:
                newmsg = 'Skipping next song in `%s`: `%s` added by user id `%s` as queuer already left the guild' % (
                    self._voice_channel.name, entry.title, entry.queuer_id)
                await player.skip()
            else:
                newmsg = 'Now playing in `%s`: `%s` added by user id `%s`' % (
                    self._voice_channel.name, entry.title, entry.queuer_id)
        else:
            # no author (and channel), it's an autoplaylist (or autostream from my other PR) entry.
            newmsg = 'Now playing automatically added entry `%s` in `%s`' % (
                entry.title, self._voice_channel.name)

        if newmsg:
            if self._bot.config.dm_nowplaying and author:
                await safe_send_message(author, newmsg)
                return

            if self._bot.config.no_nowplaying_auto and not author:
                return

            last_np_msg = self._bot.server_specific_data[self]['last_np_msg']

            if self._bot.config.nowplaying_channels:
                for potential_channel_id in self._bot.config.nowplaying_channels:
                    potential_channel = self._bot.get_channel(potential_channel_id)
                    if potential_channel and potential_channel.guild == self.guild:
                        channel = potential_channel
                        break

            meta = entry.get_metadata()

            if channel:
                pass
            elif 'channel_id' in meta:
                channel = self.guild.get_channel(meta['channel_id'])
            elif not channel and last_np_msg:
                channel = last_np_msg.channel
            else:
                self._bot.log.debug('no channel to put now playing message into')
                return

            # send it in specified channel
            self._bot.server_specific_data[self]['last_np_msg'] = await safe_send_message(channel, newmsg)

        # TODO: Check channel voice state?

    async def on_player_resume(self, player, entry, **_):
        self._bot.log.debug('Running on_player_resume')
        await self._bot.update_now_playing_status(entry)

    async def on_player_pause(self, player, entry, **_):
        self._bot.log.debug('Running on_player_pause')
        await self._bot.update_now_playing_status(entry, True)
        # await self.serialize_queue(self)

    async def on_player_stop(self, player, **_):
        self._bot.log.debug('Running on_player_stop')
        await self._bot.update_now_playing_status()

    async def on_player_finished_playing(self, player, **_):
        self._bot.log.debug('Running on_player_finished_playing')

        # delete last_np_msg somewhere if we have cached it
        if self._bot.config.delete_nowplaying:
            last_np_msg = self._bot.server_specific_data[self]['last_np_msg']
            if last_np_msg:
                await safe_delete_message(last_np_msg)
        
        def _autopause(player):
            if self._bot._check_if_empty(self._voice_channel):
                self._bot.log.info("Player finished playing, autopaused in empty channel")

                ensure_future(player.pause())
                self._bot.server_specific_data[self]['auto_paused'] = True

        if not player._playlist._list and not player._current and (self._bot.config.auto_playlist or self._bot.config.auto_stream):
            if not self.autoplaylist:
                if self._bot.config.auto_playlist:
                    if not self._bot.autoplaylist:
                        # TODO: When I add playlist expansion, make sure that's not happening during this check
                        self._bot.log.warning("No playable songs in the autoplaylist, disabling.")
                        self._bot.config.auto_playlist = False
                        if self._bot.config.auto_mode == 'toggle' and self._bot.config.auto_mode_toggle == 'playlist':
                            self._bot.config.auto_mode_toggle == 'stream'
                    else:
                        self._bot.log.debug("No content in current autoplaylist. Filling with new music (autoplaylist)...")
                        if self._bot.config.auto_mode == 'merge' or (self._bot.config.auto_mode == 'toggle' and self._bot.config.auto_mode_toggle == 'playlist'):
                            self.autoplaylist.extend([(e, 'playlist') for e in self._bot.autoplaylist])

                if self._bot.config.auto_stream:
                    if not self._bot.autostream:
                        self._bot.log.warning("No playable songs in the autostream, disabling.")
                        self._bot.config.auto_stream = False
                        if self._bot.config.auto_mode == 'toggle' and self._bot.config.auto_mode_toggle == 'stream':
                            self._bot.config.auto_mode_toggle == 'playlist'
                    else:
                        self._bot.log.debug("No content in current autoplaylist. Filling with new music (autostream)...")
                        if self._bot.config.auto_mode == 'merge' or (self._bot.config.auto_mode == 'toggle' and self._bot.config.auto_mode_toggle == 'stream'):
                            self.autoplaylist.extend([(e, 'stream') for e in self._bot.autostream])

            while self.autoplaylist:
                if self._bot.config.auto_playlist_stream_random:
                    random.shuffle(self.autoplaylist)
                    song_url, song_type = random.choice(self.autoplaylist)
                else:
                    song_url, song_type = self.autoplaylist[0]
                self.autoplaylist.remove((song_url, song_type))
                self._bot.log.debug("get url: {} ({})".format(song_url, song_type))

                if song_type == 'playlist':
                    info = {}

                    try:
                        info = await self._bot.downloader.extract_info(song_url, download=False, process=False)
                    except DownloadError as e:
                        if 'YouTube said:' in e.args[0]:
                            # url is bork, remove from list and put in removed list
                            self._bot.log.error("Error processing youtube url:\n{}".format(e.args[0]))

                        else:
                            # Probably an error from a different extractor, but I've only seen youtube's
                            self._bot.log.error("Error processing \"{url}\": {ex}".format(url=song_url, ex=e))

                        await self._bot.remove_from_autoplaylist(song_url, ex=e, delete_from_ap=self._bot.config.remove_ap)
                        continue

                    except Exception as e:
                        self._bot.log.error("Error processing \"{url}\": {ex}".format(url=song_url, ex=e))
                        self._bot.log.exception()

                        self._bot.autoplaylist.remove(song_url)
                        continue

                    if info.get('entries', None):  # or .get('_type', '') == 'playlist'
                        self._bot.log.debug("Playlist found but is unsupported at this time, skipping.")
                        # TODO: Playlist expansion

                    # Do I check the initial conditions again?
                    # not (not player.playlist.entries and not player.current_entry and self.config.auto_playlist)

                    if self._bot.config.auto_pause:
                        player.once('play', lambda player, **_: _autopause(player))

                    try:
                        entry = await get_entry(song_url, None, self._bot.downloader, dict())
                        await player._playlist.add_entry(entry)
                    except exceptions.ExtractionError as e:
                        self._bot.log.error("Error adding song from autoplaylist: {}".format(e))
                        self._bot.log.debug('', exc_info=True)
                        continue
                
                elif song_type == 'stream':
                    # TODO: streams check                    
                    try:
                        entry = await get_stream_entry(song_url, None, self._bot.downloader, dict())
                        await player._playlist.add_entry(entry)
                        if self._bot.config.auto_pause:
                            player.once('play', lambda player, **_: _autopause(player))
                    except exceptions.ExtractionError as e:
                        self._bot.log.error("Error adding song from autostream: {}".format(e))
                        self._bot.log.debug('', exc_info=True)
                        continue

                break

            if self._bot.config.auto_playlist:
                if not self._bot.autoplaylist:
                    # TODO: When I add playlist expansion, make sure that's not happening during this check
                    self._bot.log.warning("No playable songs in the autoplaylist, disabling.")
                    self._bot.config.auto_playlist = False
                    if self._bot.config.auto_mode == 'toggle' and self._bot.config.auto_mode_toggle == 'playlist':
                        self._bot.config.auto_mode_toggle == 'stream'

            if self._bot.config.auto_stream:
                if not self._bot.autostream:
                    self._bot.log.warning("No playable songs in the autostream, disabling.")
                    self._bot.config.auto_stream = False
                    if self._bot.config.auto_mode == 'toggle' and self._bot.config.auto_mode_toggle == 'stream':
                        self._bot.config.auto_mode_toggle == 'playlist'

        else: # Don't serialize for autoplaylist events
            await self.serialize_queue()

    async def on_player_entry_added(self, player, playlist, entry, **_):
        self._bot.log.debug('Running on_player_entry_added')
        if entry.queuer_id:
            await self.serialize_queue()

    async def on_player_error(self, player, entry, ex, **_):
        if 'channel_id' in entry._metadata:
            await safe_send_message(
                self.guild.get_channel(entry._metadata['channel_id']),
                "```\nError from FFmpeg:\n{}\n```".format(ex)
            )
        else:
            self._bot.log.exception("Player error", exc_info=ex)

    async def set_connected_voice_channel(self, voice_channel):
        if self._voice_client:
            if voice_channel:
                await self._move_channel(voice_channel)
            else:
                await self._disconnect_channel()
        else:
            if voice_channel:
                await self._connect_channel(voice_channel)
            else:
                raise exceptions.VoiceConnectionError("bot is not connected to any voice channel")

    async def get_connected_voice_client(self):
        async with self._aiolocks['c_voice_channel']:
            return self._voice_client

    async def get_player(self):
        async with self._aiolocks['c_voice_channel']:
            if self._player:
                return self._player
            else:
                raise exceptions.VoiceConnectionError("bot is not connected to any voice channel")
    
    async def set_playlist(self, playlist):
        async with self._aiolocks['c_voice_channel']:
            await self._player.set_playlist(playlist)

    async def get_playlist(self):
        async with self._aiolocks['c_voice_channel']:
            return await self._player.get_playlist()

    def get_owner(self, *, voice=False):
            return discord.utils.find(
                lambda m: m.id == self._bot.config.owner_id and (m.voice if voice else True),
                self.guild.members
            )

def get_guild(bot, guild) -> RichGuild:
    return guilds[bot.user.id][guild.id]

def get_guild_list(bot) -> RichGuild:
    return list(guilds[bot.user.id].values())

def register_bot(bot):
    guilds[bot.user.id] = {guild.id:RichGuild.deserialize_from_file(bot, guild.id) for guild in bot.guilds}

    async def on_guild_join(guild):
        if bot.is_ready():
            guilds[bot.user.id][guild.id] = RichGuild.deserialize_from_file(bot, guild.id)
            bot.log.info('joined guild {}'.format(guild.name))

    bot.event(on_guild_join)

    async def on_guild_remove(guild):
        if bot.is_ready():
            await guilds[bot.user.id][guild.id].serialize_to_file()
            del guilds[bot.user.id][guild.id]
            bot.log.info('removed guild {}'.format(guild.name))

    bot.event(on_guild_remove)

    async def on_voice_state_update(member, before, after):
        if bot.is_ready():
            c = before.channel
            c = after.channel if not c else c
            guild = c.guild
            rguild = get_guild(bot, guild)

            if member == bot.user:
                async with guilds[bot.user.id][guild.id]._aiolocks['c_voice_channel']:                    
                    if not after.channel:
                        rguild._voice_client = None
                        if rguild._player:
                            await rguild._player.kill()
                            rguild._player = None
                    rguild._voice_channel = after.channel

            if not rguild._bot.config.auto_pause:
                return

            autopause_msg = "{state} in {channel.guild.name}/{channel.name} {reason}"

            auto_paused = rguild._bot.server_specific_data[rguild]['auto_paused']

            try:
                player = await rguild.get_player()
            except:
                return

            if not member == rguild._bot.user:  # if the user is not the bot
                if rguild._voice_channel != before.channel and rguild._voice_channel == after.channel:  # if the person joined
                    if auto_paused and player.state == PlayerState.PAUSE:
                        rguild._bot.log.info(autopause_msg.format(
                            state = "Unpausing",
                            channel = rguild._voice_channel,
                            reason = ""
                        ).strip())

                        rguild._bot.server_specific_data[rguild]['auto_paused'] = False
                        await player.play()
                elif rguild._voice_channel == before.channel and rguild._voice_channel != after.channel:
                    if len(rguild._voice_channel.members) == 1:
                        if not auto_paused and player.state != PlayerState.PAUSE:
                            rguild._bot.log.info(autopause_msg.format(
                                state = "Pausing",
                                channel = rguild._voice_channel,
                                reason = "(empty channel)"
                            ).strip())

                            rguild._bot.server_specific_data[rguild]['auto_paused'] = True
                            await player.pause()
            else:
                if len(rguild._voice_channel.members) > 0:  # channel is not empty
                    if auto_paused and player.state == PlayerState.PAUSE:
                        rguild._bot.log.info(autopause_msg.format(
                            state = "Unpausing",
                            channel = rguild._voice_channel,
                            reason = ""
                        ).strip())
    
                        rguild._bot.server_specific_data[rguild]['auto_paused'] = False
                        await player.play()

    bot.event(on_voice_state_update)

    async def on_command_error(ctx, exception):
        message = exception.message if isinstance(exception, exceptions.MusicbotException) else str(exception)
        expire_in = exception.expire_in if isinstance(exception, exceptions.MusicbotException) else None
        await safe_send_message(ctx, content_gen(ctx, message, color = ContentTypeColor.ERROR), expire_in = expire_in)
        if not isinstance(exception, exceptions.MusicbotException):
            raise exception

    bot.event(on_command_error)

    async def context_check(ctx):
        if ctx.author == ctx.bot.user:
            ctx.bot.log.info("Ignoring command from myself ({})".format(ctx.message.content))
            return False

        if (not isinstance(ctx.message.channel, discord.abc.GuildChannel)) and (not isinstance(ctx.message.channel, discord.abc.PrivateChannel)):
            ctx.bot.log.info("WTF is the message channel then")
            return False

        if isinstance(ctx.message.channel, discord.abc.PrivateChannel):
            if not (ctx.author.id == ctx.bot.config.owner_id and ctx.command.name == 'joinserver'):
                await safe_send_normal(ctx, ctx, 'You cannot use this bot in private messages.')
                ctx.bot.log.info('Ignoring command via private messages.')
                return False

        if ctx.bot.config.bound_channels and ctx.message.channel.id not in ctx.bot.config.bound_channels:
            if ctx.bot.config.unbound_servers:
                for channel in ctx.message.guild.channels:
                    if channel.id in ctx.bot.config.bound_channels:
                        ctx.bot.log.info('Ignoring command that is not sent in bounded channels.')
                        return False
            else:
               ctx.bot.log.info('Ignoring command that is not sent in bounded channels.')
               return False

        if ctx.author.id in ctx.bot.blacklist and ctx.author.id != ctx.bot.config.owner_id:
            ctx.bot.log.warning("User blacklisted: {0.id}/{0!s} ({1})".format(ctx.author, ctx.command.name))
            ctx.bot.log.info('Ignoring command from blacklisted users')
            return False

        else:
            ctx.bot.log.info("{0.id}/{0!s}: {1}".format(ctx.author, ctx.message.content.replace('\n', '\n... ')))
            return True

    bot.check_once(context_check)

def prunenoowner(client) -> int:
    unavailable_servers = 0
    for server in guilds[client.user.id]:
        if server.guild.unavailable:
            unavailable_servers += 1
        elif server.get_owner() == None:
            server.guild.leave()
            client.log.info('Left {} due to bot owner not found'.format(server._guild.name))
    return unavailable_servers