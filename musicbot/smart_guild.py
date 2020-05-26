"""
MusicBot: The original Discord music bot written for Python 3.5+, using the discord.py library.
ModuBot: A modular discord bot with dependency management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The MIT License (MIT)

Copyright (c) 2019 TheerapakG
Copyright (c) 2019-2020 Just-Some-Bots (https://github.com/Just-Some-Bots)

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
from .lib.event_emitter import AsyncEventEmitter
from .utils import check_restricted
from .guild_config import GuildConfig
from .playback import Player, Playlist, PlayerState
from .constructs import SkipState, Serializable, Serializer
from .messagemanager import safe_send_message, safe_send_normal, safe_delete_message, content_gen, ContentTypeColor
from .ytdldownloader import get_entry, get_unprocessed_entry, get_stream_entry
from youtube_dl.utils import DownloadError
from . import exceptions

guilds = dict()

class SmartGuild(Serializable, AsyncEventEmitter):
    _lock: DefaultDict[str, RLock] = defaultdict(RLock)
    _id: int
    config: GuildConfig
    _auto: Optional[Playlist] = None
    _not_auto: Optional[Playlist] = None
    skip_state: SkipState = SkipState()
    _save_dir: str

    def __init__(self, bot, guildid, *, init_data = True):
        super().__init__()
        self._bot = bot
        self._id = guildid

        self.config = GuildConfig(bot)
        self._save_dir = 'data/{}'.format(self._id)

        if init_data:
            self.init_addons_data()              

    def gather_addons_data(self):
        # run when serialize
        data = dict()
        for cog in self._bot.crossmodule.cogs_by_deps():
            # (auto-generated) _thee_tools_inline_pattern[lang=py]: dispatch_method[obj=cog, attr='get_guild_data_dict', args...=(self)]@TheerapakG
            try:
                potential_method = getattr(cog, 'get_guild_data_dict')
            except AttributeError:
                continue
            data.update(potential_method(self))
        return data

    def init_addons_data(self, data = dict()):
        # run when initialize
        for cog in self._bot.crossmodule.cogs_by_deps():
            # (auto-generated) _thee_tools_inline_pattern[lang=py]: dispatch_method[obj=cog, attr='initialize_guild_data_dict', args...=(self, data)]@TheerapakG
            try:
                potential_method = getattr(cog, 'initialize_guild_data_dict')
            except AttributeError:
                continue
            potential_method(self, data)

    async def unload_addons(self):
        for cog in self._bot.crossmodule.cogs_by_deps():
            # (auto-generated) _thee_tools_inline_pattern[lang=py]: dispatch_method_p_async[obj=cog, attr='unload_guild', args...=(self)]@TheerapakG
            try:
                potential_method = getattr(cog, 'unload_guild')
            except AttributeError:
                continue
            potential_async = potential_method(self)
            if inspect.isawaitable(potential_async):
                await potential_async

    def __json__(self):
        # @TheerapakG: playlists are only stored as path as it's highly inefficient to serialize all lists when
        # we're shutting down
        return self._enclose_json({
            'version': 4,
            'id': self._id,
            'config': self.config,
            'external_data': self.gather_addons_data()
        })

    @classmethod
    def _deserialize(cls, data, bot=None, save_dir=None):
        assert bot is not None, cls._bad('bot')
        assert save_dir is not None, cls._bad('save_dir')

        if 'version' not in data or data['version'] < 2:
            raise exceptions.VersionError('data version needs to be higher than 1')

        data_id = data.get('id')

        guild = cls(bot, data_id, init_data = False)
        guild._save_dir = save_dir

        guild.config = data.get('config')

        guild.init_addons_data(data['external_data'])

        return guild

    @classmethod
    def from_json(cls, raw_json, bot, guildid, save_dir):
        try:
            extractor = bot.downloader
            obj = json.loads(raw_json, object_hook=Serializer.deserialize)
            if isinstance(obj, dict):
                bot.log.warning('Cannot parse incompatible smart guild data.')
                bot.log.debug(raw_json)
                raise Exception('raw_json is not SmartGuild data')
            if obj._id != guildid:
                bot.log.warning("Guild id contradict with id in the serialized data. Using current guild id instead")
                obj._id = guildid
            return obj
        except Exception as e:
            raise Exception("Failed to deserialize smart guild") from e

    @property
    def id(self):
        return self._id

    @property
    def guild(self):
        return self._bot.get_guild(self._id)

    async def serialize_to_dir(self, *, dir=None):
        if dir is None:
            dir = 'data/{}'.format(self._id)

        with self._lock['guild_serialization']:
            self._bot.log.debug("Serializing {}".format(self._id))

            with open(dir + '/smartguildinfo.json', 'w', encoding='utf8') as f:
                f.write(self.serialize(sort_keys=True))

            await self.emit('serialize', self)

        self._bot.log.debug("Serialized {}".format(self._id))

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

def _init_deserialize_guild(bot, id) -> SmartGuild:
    save_dir = 'data/{}'.format(id)
    try:
        with open(save_dir + '/smartguildinfo.json', 'r', encoding='utf8') as f:
            guild = SmartGuild.from_json(f.read(), bot, id, save_dir)
    except Exception:
        guild = SmartGuild(bot, id)
    return guild

def register_bot(bot):
    guilds[bot.user.id] = {guild.id:_init_deserialize_guild(bot, guild.id) for guild in bot.guilds}

    async def on_guild_join(guild):
        if bot.is_ready():
            guilds[bot.user.id][guild.id] = _init_deserialize_guild(bot, guild.id)
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
            guild = get_guild(bot, c.guild)
            await guild.emit('voice-update', guild, member, before, after)

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