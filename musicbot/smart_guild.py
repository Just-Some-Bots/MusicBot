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
from typing import Optional, Dict, DefaultDict, NamedTuple, Any
from threading import RLock
import json
import os
import random
import glob
import inspect
from .lib.event_emitter import EventEmitter
from .utils import check_restricted
from .guild_config import GuildConfig
from .playback import Player, Playlist, PlayerState
from .constructs import SkipState, Serializable, Serializer
from .messagemanager import safe_send_message, safe_send_normal, safe_delete_message, content_gen, ContentTypeColor
from .ytdldownloader import get_entry, get_unprocessed_entry, get_stream_entry
from youtube_dl.utils import DownloadError
from . import exceptions

guilds = dict()

class SmartGuild(Serializable, EventEmitter):
    _lock: DefaultDict[str, RLock] = defaultdict(RLock)
    _id: int
    config: GuildConfig
    _playlists: Dict[str, Playlist] = dict()
    _auto: Optional[Playlist] = None
    _not_auto: Optional[Playlist] = None
    skip_state: SkipState = SkipState()
    _save_dir: str
    data: Dict[str, Any] = dict()

    def __init__(self, bot, guildid, save_dir = None):
        """
        DO NOT init DIRECTLY! use factory method `try_deserialize_from_dir` instead
        """
        # @TheerapakG: TODO: make ^ not necessary
        super().__init__()
        self._bot = bot
        self._id = guildid
        self.config = GuildConfig(bot)
        self._save_dir = 'data/{}'.format(self._id) if not save_dir else save_dir
        self.emit('initialize', self)

    def __json__(self):
        # @TheerapakG: playlists are only stored as path as it's highly inefficient to serialize all lists when
        # we're shutting down
        return self._enclose_json({
            'version': 3,
            'id': self._id,
            'config': self.config,
            'auto': self._auto._name if self._auto else None,
            'not_auto': self._not_auto._name if self._not_auto else None
        })

    @classmethod
    def _deserialize(cls, data, bot=None, save_dir=None):
        assert bot is not None, cls._bad('bot')
        assert save_dir is not None, cls._bad('save_dir')

        if 'version' not in data or data['version'] < 2:
            raise exceptions.VersionError('data version needs to be higher than 1')

        data_id = data.get('id')

        guild = cls(bot, data_id, save_dir = save_dir)

        guild.config = data.get('config')

        guild.data['_auto'] = data.get('auto')
        guild.data['_not_auto'] = data.get('not_auto')

        return guild

    def is_playlist_auto(self, pl: Playlist):
        with self._lock['c_auto']:
            return pl is self._auto

    def is_currently_auto(self):
        try:
            plpl = self.get_playlist(incl_auto = True)
        except exceptions.VoiceConnectionError:
            return False

        return self.is_playlist_auto(plpl)

    def return_from_auto(self, *, also_skip = False):
        if (self.is_currently_auto()):
            self._bot.log.info("Leaving auto in {}".format(self._id))
            with self._lock['c_auto']:
                self.serialize_playlist(self._auto)
                self.player.set_playlist(self._not_auto)
            self.player.random = False
            self.player.pull_persist = False
            if also_skip:
                self.player.skip()

    def set_auto(self, pl: Optional[Playlist] = None):
        self._bot.log.info("Setting auto in {}".format(self._id))
        with self._lock['c_auto']:
            self.serialize_playlist(self._auto)
            if (self.is_currently_auto()):
                self.player.set_playlist(pl)
            self._auto = pl

    def get_auto(self):
        with self._lock['c_auto']:
            return self._auto

    @classmethod
    def from_json(cls, raw_json, bot, guildid, save_dir):
        try:
            extractor = bot.downloader
            obj = json.loads(raw_json, object_hook=Serializer.deserialize)
            if isinstance(obj, dict):
                bot.log.warning('Cannot parse incompatible smart guild data. Instantiating new smart guild instead.')
                bot.log.debug(raw_json)
                obj = cls(bot, guildid, save_dir)
            if obj._id != guildid:
                bot.log.warning("Guild id contradict with id in the serialized data. Using current guild id instead")
                obj._id = guildid
            return obj
        except Exception as e:
            bot.log.exception("Failed to deserialize smart guild, using default one instead")
            bot.log.exception(e)
            return cls(bot, guildid, save_dir)

    @property
    def id(self):
        return self._id

    @property
    def guild(self):
        return self._bot.get_guild(self._id)

    def serialize_to_dir(self, *, dir=None):
        if dir is None:
            dir = 'data/{}'.format(self._id)

        with self._lock['guild_serialization']:
            self._bot.log.debug("Serializing {}".format(self._id))

            with open(dir + '/smartguildinfo.json', 'w', encoding='utf8') as f:
                f.write(self.serialize(sort_keys=True))

            self.emit('serialize', self)

        self.serialize_queue()

        self._bot.log.debug("Serialized {}".format(self._id))

    @classmethod
    def try_deserialize_from_dir(cls, bot, id, save_dir):
        if not os.path.isfile(save_dir + '/smartguildinfo.json'):
            bot.log.debug("Using defaults for guild {}".format(id))
            guild = cls(bot, id, save_dir)
        with open(save_dir + '/smartguildinfo.json', 'r', encoding='utf8') as f:
            guild = cls.from_json(f.read(), bot, id, save_dir)
        for cog in bot.cogs.values():
            # (auto-generated) _thee_tools_inline_pattern[lang=py]: dispatch_method[obj=cog, attr='on_guild_instantiate', args...=(guild)]@TheerapakG
            try:
                potential_method = getattr(cog, 'on_guild_instantiate')
                potential_descriptor = inspect.getattr_static(cog, 'on_guild_instantiate')
            except AttributeError:
                continue
            potential_method(guild)
        return guild

    def serialize_playlist(self, playlist):
        """
        Serialize the playlist to json.
        """
        dir = self._save_dir + '/playlists/{}.json'.format(playlist._name)

        with self._lock['pl_{}_serialization'.format(playlist._name)]:
            self._bot.log.debug("Serializing `{}` for {}".format(playlist._name, self._id))
            os.makedirs(os.path.dirname(dir), exist_ok=True)
            with open(dir, 'w', encoding='utf8') as f:
                f.write(playlist.serialize(sort_keys=True))
                self._playlists[playlist._name].path = dir

    def serialize_playlists(self):
        for p in self._playlists.copy():
            self.serialize_playlist(p)

    def remove_serialized_playlist(self, name):
        """
        Remove the playlist serialized to json.
        """
        dir = self._save_dir + '/playlists/{}.json'.format(name)

        if not os.path.isfile(dir):
            return

        with self._lock['pl_{}_serialization'.format(name)]:
            self._bot.log.debug("Removing serialized `{}` for {}".format(name, self._id))
            try:
                del self._playlists[name]
            except KeyError:
                pass

            os.unlink(dir)

    def serialize_queue(self):
        """
        Serialize the current queue for a server's player to json.
        """
        if not self.player:
            return

        dir = self._save_dir + '/queue.json'

        with self._lock['queue_serialization']:
            self._bot.log.debug("Serializing queue for %s", self._id)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(self.player.serialize(sort_keys=True))
            
            pl = self.player.get_playlist()
            if pl:
                self.serialize_playlist(pl)

    def write_current_song(self, entry, *, dir=None):
        """
        Writes the current song to file
        """
        if not self.player:
            return

        dir = self._save_dir + 'current.txt'

        with self._lock['current_song']:
            self._bot.log.debug("Writing current song for %s", self._id)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(entry.title)
    
    def set_playlist(self, playlist):
        if self.is_currently_auto():
            with self._lock['c_auto']:
                self._not_auto = playlist
        else:
            self.player.set_playlist(playlist)

    def get_playlist(self, incl_auto = False):
        pl = self.player.get_playlist()

        if incl_auto:
            return pl
        else:
            with self._lock['c_auto']:
                if self.is_playlist_auto(pl):
                    return self._not_auto
                else:
                     return pl

    def get_owner(self, *, voice=False):
        return set(
            filter(
                lambda m: m.id in self._bot.config.owner_id and (m.voice if voice else True),
                self.guild.members
            )
        )

def get_guild(bot, guild) -> SmartGuild:
    return guilds[bot.user.id][guild.id]

def get_guild_list(bot) -> SmartGuild:
    return list(guilds[bot.user.id].values())

def register_bot(bot):
    guilds[bot.user.id] = {guild.id:SmartGuild.try_deserialize_from_dir(bot, guild.id, 'data/{}'.format(guild.id)) for guild in bot.guilds}

    async def on_guild_join(guild):
        if bot.is_ready():
            guilds[bot.user.id][guild.id] = SmartGuild.try_deserialize_from_dir(bot, guild.id)
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
                if not after.channel:
                    await rguild.player.set_voice_channel(None)
                    return
                try:
                    await rguild.player.set_voice_channel(after.channel)
                except exceptions.VoiceConnectionError:
                    # same voice channel, probably because we connect to it ourself
                    pass

            if not rguild._bot.config.auto_pause:
                return

            autopause_msg = "{state} in {channel.guild.name}/{channel.name} {reason}"

            auto_paused = rguild._bot.server_specific_data[rguild]['auto_paused']

            try:
                player = await rguild.get_player()
            except:
                return

            def is_active(member):
                if not member.voice:
                    return False

                if any([member.voice.deaf, member.voice.self_deaf, member.bot]):
                    return False

                return True

            if not member == rguild._bot.user and is_active(member):  # if the user is not inactive
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
                    if not any(is_active(m) for m in rguild._voice_channel.members):  # channel is empty
                        if not auto_paused and player.state != PlayerState.PAUSE:
                            rguild._bot.log.info(autopause_msg.format(
                                state = "Pausing",
                                channel = rguild._voice_channel,
                                reason = "(empty channel)"
                            ).strip())

                            rguild._bot.server_specific_data[rguild]['auto_paused'] = True
                            await player.pause()

                elif rguild._voice_channel == before.channel and rguild._voice_channel == after.channel:  # if the person undeafen
                    if auto_paused and player.state == PlayerState.PAUSE:
                        rguild._bot.log.info(autopause_msg.format(
                            state = "Unpausing",
                            channel = rguild._voice_channel,
                            reason = "(member undeafen)"
                        ).strip())

                        rguild._bot.server_specific_data[rguild]['auto_paused'] = False
                        await player.play()
            else:
                if any(is_active(m) for m in rguild._voice_channel.members):  # channel is not empty
                    if auto_paused and player.state == PlayerState.PAUSE:
                        rguild._bot.log.info(autopause_msg.format(
                            state = "Unpausing",
                            channel = rguild._voice_channel,
                            reason = ""
                        ).strip())
    
                        rguild._bot.server_specific_data[rguild]['auto_paused'] = False
                        await player.play()

                else:
                    if not auto_paused and player.state != PlayerState.PAUSE:
                        rguild._bot.log.info(autopause_msg.format(
                            state = "Pausing",
                            channel = rguild._voice_channel,
                            reason = "(empty channel or member deafened)"
                        ).strip())

                        rguild._bot.server_specific_data[rguild]['auto_paused'] = True
                        await player.pause()

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

        if ctx.author.id in ctx.bot.blacklist and ctx.author.id not in ctx.bot.config.owner_id:
            ctx.bot.log.warning("User blacklisted: {0.id}/{0!s} ({1})".format(ctx.author, ctx.command.name))
            ctx.bot.log.info('Ignoring command from blacklisted users')
            return False

        if ctx.author.bot and ctx.author.id not in ctx.bot.config.bot_exception_ids:
            ctx.bot.log.warning("Ignoring command from other bot ({})".format(ctx.message.content))
            return False

        if (not isinstance(ctx.message.channel, discord.abc.GuildChannel)) and (not isinstance(ctx.message.channel, discord.abc.PrivateChannel)):
            ctx.bot.log.info("WTF is the message channel then")
            return False

        if isinstance(ctx.message.channel, discord.abc.PrivateChannel):
            if not (ctx.author.id in ctx.bot.config.owner_id and ctx.command.name == 'joinserver'):
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

        permissions = ctx.bot.permissions.for_user(ctx.author)

        if not check_restricted(ctx.command, permissions):
            return False
        
        if permissions.ignore_non_voice and ctx.command.name in permissions.ignore_non_voice:
            if ctx.me and ctx.me.voice:
                vc = ctx.me.voice.channel
            else:
                vc = None

            # If we've connected to a voice chat and we're in the same voice channel
            if vc and not (ctx.author.voice and vc == ctx.author.voice.channel):
                raise exceptions.PermissionsError(
                    "you cannot use this command when not in the voice channel (%s)" % vc.name, expire_in=30)

        ctx.bot.log.info("{0.id}/{0!s}: {1}".format(ctx.author, ctx.message.content.replace('\n', '\n... ')))
        return True

    bot.check_once(context_check)

def prunenoowner(client) -> int:
    unavailable_servers = 0
    for server in guilds[client.user.id].values():
        if server.guild.unavailable:
            unavailable_servers += 1
        elif not server.get_owner():
            server.guild.leave()
            client.log.info('Left {} due to bot owner not found'.format(server._guild.name))
    return unavailable_servers