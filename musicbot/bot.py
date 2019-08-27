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

import asyncio
import aiohttp
import logging
import shutil
import pkgutil
import sys
import threading
import traceback
import time
import os
import pathlib
from collections import defaultdict, deque, namedtuple
from contextlib import suppress
from functools import partial, wraps
from importlib import import_module, reload
from inspect import iscoroutinefunction, isfunction
from platform import system

import colorlog
from discord.ext.commands import Bot
import discord
from websockets import ConnectionClosed

from .crossmodule import CrossModule
from .rich_guild import guilds, register_bot, prunenoowner, get_guild, get_guild_list
from .playback import PlayerState
from .ytdldownloader import YtdlDownloader
from .utils import isiterable, load_file, write_file, fixg
from .constants import VERSION as BOTVERSION
from .constants import AUDIO_CACHE_PATH

from .config import Config, ConfigDefaults
from .permissions import Permissions, PermissionsDefaults
from .alias import Alias, AliasDefaults
from .json import Json
from .spotify import Spotify
from . import exceptions

MODUBOT_MAJOR = '0'
MODUBOT_MINOR = '1'
MODUBOT_REVISION = '3'
MODUBOT_VERSIONTYPE = 'a'
MODUBOT_SUBVERSION = '3'
MODUBOT_VERSION = '{}.{}.{}-{}{}'.format(MODUBOT_MAJOR, MODUBOT_MINOR, MODUBOT_REVISION, MODUBOT_VERSIONTYPE, MODUBOT_SUBVERSION)
MODUBOT_STR = 'ModuBot {}'.format(MODUBOT_VERSION)

class ModuBot(Bot):

    ModuleTuple = namedtuple('ModuleTuple', ['name', 'module'])

    def __init__(self, *args, logname = "MusicBot", loghandlerlist = [], **kwargs):
        self._aiolocks = defaultdict(asyncio.Lock)
        self.bot_version = (MODUBOT_MAJOR, MODUBOT_MINOR, MODUBOT_REVISION, MODUBOT_VERSIONTYPE, MODUBOT_SUBVERSION)
        self.bot_str = MODUBOT_STR
        try:
            sys.stdout.write("\x1b]2;MusicBot {}\x07".format(BOTVERSION))
        except:
            pass

        print()

        config_file = ConfigDefaults.options_file

        perms_file = PermissionsDefaults.perms_file

        self.thread = None
        self.crossmodule = CrossModule()
        self.log = logging.getLogger(logname)
        for handler in loghandlerlist:
            self.log.addHandler(handler)

        self.config = Config(config_file)
        self.alias = Alias(self, AliasDefaults.alias_file)
        self.downloader = YtdlDownloader(self, 'audio_cache')

        self.log.setLevel(self.config.debug_level)

        self.permissions = Permissions(perms_file, grant_all=[self.config.owner_id])
        self.str = Json(self.config.i18n_file)

        self.blacklist = set(load_file(self.config.blacklist_file))

        self.log.info('Starting MusicBot {}'.format(BOTVERSION))

        if self.blacklist:
            self.log.debug("Loaded blacklist with {} entries".format(len(self.blacklist)))

        # TODO: Do these properly
        ssd_defaults = {
            'last_np_msg': None,
            'auto_paused': False,
            'availability_paused': False
        }
        # guild are of type RichGuild
        self.server_specific_data = defaultdict(ssd_defaults.copy)

        super().__init__(command_prefix = self.config.command_prefix, *args, **kwargs)

        self.aiosession = aiohttp.ClientSession(loop=self.loop)
        self.http.user_agent += ' MusicBot/%s' % BOTVERSION

        self.spotify = None
        if self.config._spotify:
            try:
                self.spotify = Spotify(self.config.spotify_clientid, self.config.spotify_clientsecret, aiosession=self.aiosession, loop=self.loop)
                if not self.spotify.token:
                    self.log.warning('Spotify did not provide us with a token. Disabling.')
                    self.config._spotify = False
                else:
                    self.log.info('Authenticated with Spotify successfully using client ID and secret.')
            except exceptions.SpotifyError as e:
                self.log.warning('There was a problem initialising the connection to Spotify. Is your client ID and secret correct? Details: {0}. Continuing anyway in 5 seconds...'.format(e))
                self.config._spotify = False
                time.sleep(5)  # make sure they see the problem

        self.help_command = None
        self.looplock = threading.Lock()
        self._init = False

        self._owner_id = self.config.owner_id

        self._presence = (None, None)

    async def _load_modules(self, modulelist):
        # TODO: change into cog pre_init, cog init and cog post_init/ deps listing inside cogs
        # 1: walk module
        #     1: module pre_init
        #         this stage should be use to read up config and prepare things such as opening
        #         port to communicate with server, opening file for logging, register stuff to
        #         crossmodule object (except features), etc. pre_init must throw if not successful
        # 2: walk module again
        #     1: load command, cogs, ...
        #         even if some command, cogs in a module is not loaded, it will not get skip 
        #     2: module init
        #         this stage should be use to check commands in the module that got loaded and
        #         register features available after loaded. init must throw if not successful
        # 3: walk module again
        #     1: module post_init
        #         this stage should be use to check if dependency loaded correctly with features
        #         needed and register dependencies needed. post_init must throw if not successful
        #     2: add to loaded
        # 4: walk module again
        #     1: module after_init
        #         this means that stuff in crossmodule is safe to be retrieve. shall not fail

        load_cogs = []

        available_module = set(self.crossmodule.imported.keys())

        for moduleinfo in modulelist:
            available_module.add(moduleinfo.name)

        requirements = defaultdict(list)

        for moduleinfo in modulelist:

            if 'deps' in dir(moduleinfo.module):
                self.log.debug('resolving deps in {}'.format(moduleinfo.name))
                deps = getattr(moduleinfo.module, 'deps')
                if isiterable(deps):
                    for dep in deps:
                        requirements[dep].append(moduleinfo.name)
                else:
                    self.log.debug('deps is not an iterable')

        req_set = set(requirements.keys())

        noreq_already = req_set - available_module
        noreq = list(noreq_already)

        req_not_met = set()

        while noreq:
            current = noreq.pop()
            req_not_met.update(requirements[current])
            for module in requirements[current]:
                if module not in noreq_already:
                    noreq.append(module)
                    noreq_already.add(module)

        if req_not_met:
            self.log.warning('These following modules does not have dependencies required and will not be loaded: {}'.format(str(req_not_met)))

        modulelist = [moduleinfo for moduleinfo in modulelist if moduleinfo.name not in req_not_met]

        for moduleinfo in modulelist:
            self.crossmodule._add_module(moduleinfo.name, moduleinfo.module)

        for moduleinfo in modulelist:
            if 'deps' in dir(moduleinfo.module):
                self.log.debug('adding deps in {}'.format(moduleinfo.name))
                deps = getattr(moduleinfo.module, 'deps')
                if isiterable(deps):
                    self.crossmodule._register_dependency(moduleinfo.name, deps)
                else:
                    self.log.debug('deps is not an iterable')

        for moduleinfo in modulelist:
            if 'cogs' in dir(moduleinfo.module):
                cogs = getattr(moduleinfo.module, 'cogs')
                if isiterable(cogs):
                    for cog in cogs:
                        cg = cog()
                        self.log.debug('found cog {}'.format(cg.qualified_name))
                        if 'pre_init' in dir(cg):
                            self.log.debug('executing pre_init in {}'.format(cg.qualified_name))
                            potential = getattr(cg, 'pre_init')
                            self.log.debug(str(potential))
                            self.log.debug(str(potential.__func__))
                            try:
                                if iscoroutinefunction(potential.__func__):
                                    await potential(self)
                                elif isfunction(potential.__func__):
                                    potential(self)
                                else:
                                    self.log.debug('pre_init is neither funtion nor coroutine function')
                            except Exception:
                                self.log.warning('failed pre-initializing cog {} in module {}'.format(cg.qualified_name, moduleinfo.name))
                                self.log.debug(traceback.format_exc())
                        load_cogs.append((moduleinfo.name, cg))
                else:
                    self.log.debug('cogs is not an iterable')

        for moduleinfo in modulelist:
            if 'commands' in dir(moduleinfo.module):
                self.log.debug('loading commands in {}'.format(moduleinfo.name))
                commands = getattr(moduleinfo.module, 'commands')
                if isiterable(commands):
                    for command in commands:
                        cmd = command()
                        c = defaultdict(list)
                        c[None].append(cmd)
                        if hasattr(cmd, 'walk_commands'):
                            for _c in cmd.walk_commands():
                                c[_c.parent].append(_c)
                        for _c in c.values():
                            for __c in _c:
                                if __c.qualified_name in self.alias.aliases:
                                    self.log.debug('setting aliases for {} as {}'.format(__c.qualified_name, self.alias.aliases[__c.qualified_name]))
                                    __c.update(aliases = self.alias.aliases[__c.qualified_name])
                                else:
                                    # @TheerapakG: for simplicity sake just update it so that I don't have to solve the add_command headache
                                    __c.update()
                        for _p, _c in c.items():
                            if _p:
                                for __c in _c:
                                    _p.add_command(__c)
                        self.add_command(cmd)
                        self.crossmodule._commands[moduleinfo.name].append(cmd.name)
                        self.log.debug('loaded {}'.format(cmd.name))
                else:
                    self.log.debug('commands is not an iterable')

        for modulename, cog in load_cogs.copy():
            if 'init' in dir(cog):
                self.log.debug('executing init in {}'.format(cog.qualified_name))
                potential = getattr(cog, 'init')
                self.log.debug(str(potential))
                self.log.debug(str(potential.__func__))
                try:
                    if iscoroutinefunction(potential.__func__):
                        await potential()
                    elif isfunction(potential.__func__):
                        potential()
                    else:
                        self.log.debug('init is neither funtion nor coroutine function')
                except Exception:
                    self.log.warning('failed initializing cog {} in module {}'.format(cog.qualified_name, modulename))
                    self.log.debug(traceback.format_exc())
                    load_cogs.remove((modulename, cog))

        for modulename, cog in load_cogs:
            if 'post_init' in dir(cog):
                self.log.debug('executing post_init in {}'.format(cog.qualified_name))
                potential = getattr(cog, 'post_init')
                self.log.debug(str(potential))
                self.log.debug(str(potential.__func__))
                try:
                    if iscoroutinefunction(potential.__func__):
                        await potential()
                    elif isfunction(potential.__func__):
                        potential()
                    else:
                        self.log.debug('post_init is neither funtion nor coroutine function')
                except Exception:
                    self.log.warning('failed post-initializing cog {} in module {}'.format(cog.qualified_name, modulename))
                    self.log.debug(traceback.format_exc())
                    load_cogs.remove((modulename, cog))

        self.log.debug('loading cogs')
        for modulename, cog in load_cogs:
            for cmd in cog.get_commands():
                c = defaultdict(list)
                c[None].append(cmd)
                if hasattr(cmd, 'walk_commands'):
                    for _c in cmd.walk_commands():
                        c[_c.parent].append(_c)
                for _c in c.values():
                    for __c in _c:
                        if __c.qualified_name in self.alias.aliases:
                            self.log.debug('setting aliases for {} as {}'.format(__c.qualified_name, self.alias.aliases[__c.qualified_name]))
                            __c.update(aliases = self.alias.aliases[__c.qualified_name])
                        else:
                            # @TheerapakG: for simplicity sake just update it so that I don't have to solve the add_command headache
                            __c.update()
                for _p, _c in c.items():
                    if _p:
                        for __c in _c:
                            _p.add_command(__c)
            self.add_cog(cog)
            self.crossmodule._cogs[modulename].append(cog)
            self.log.debug('loaded {}'.format(cog.qualified_name))

        for modulename, cog in load_cogs:
            if 'after_init' in dir(cog):
                self.log.debug('executing after_init in {}'.format(cog.qualified_name))
                potential = getattr(cog, 'after_init')
                self.log.debug(str(potential))
                self.log.debug(str(potential.__func__))
                try:
                    if iscoroutinefunction(potential.__func__):
                        await potential()
                    elif isfunction(potential.__func__):
                        potential()
                    else:
                        self.log.debug('after_init is neither funtion nor coroutine function')
                except Exception:
                    self.log.error('cog {} in module {} raised exception after initialization'.format(cog.qualified_name, modulename))
                    self.log.debug(traceback.format_exc())
                    self.remove_cog(cog)
                    self.crossmodule._cogs[modulename].remove(cog)

    async def _prepare_load_module(self, modulename):
        if modulename in self.crossmodule.modules_loaded():
            await self.unload_modules([modulename])
            try:
                reload(self.crossmodule.imported[modulename])
            except:
                pass
            module = self.crossmodule.imported[modulename]
        else:
            try:
                module = import_module('.modules.{}'.format(modulename), 'musicbot')
            except Exception as e:
                self.log.error('error fetching module: {}'.format(modulename))
                self.log.error('{}'.format(e))
                self.log.debug(traceback.format_exc())
                return

        return module

    async def _gen_modulelist(self, modulesname):
        modules = list()
        for modulename in modulesname:
            module = await self._prepare_load_module(modulename)
            if module:
                modules.append(self.ModuleTuple(modulename, module))

        return modules

    async def load_modules(self, modulesname):
        modulelist = await self._gen_modulelist(modulesname)
        await self._load_modules(modulelist)

    async def unload_modules(self, modulenames, *, unimport = False):
        # 1: unload dependents
        # 2: unload command, cogs, ...
        # 4: remove from loaded
        # 5: module uninit
        def gendependentlist():
            deplist = list()
            considerdeque = deque(modulenames)
            considerset = set(modulenames)
            while considerdeque:
                node = considerdeque.pop()
                deplist.append(node)
                for module in self.crossmodule._module_graph[node]:
                    if module not in considerset:
                        considerdeque.append(module)
                        considerset.add(module)
            return deplist

        unloadlist = gendependentlist()
        unloadlist.reverse()

        for module in unloadlist:
            for cog in self.crossmodule._cogs[module]:
                if 'uninit' in dir(cog):
                    self.log.debug('executing uninit in {}'.format(cog.qualified_name))
                    potential = getattr(cog, 'uninit')
                    self.log.debug(str(potential))
                    self.log.debug(str(potential.__func__))
                    if iscoroutinefunction(potential.__func__):
                        await potential()
                    elif isfunction(potential.__func__):
                        potential()
                    else:
                        self.log.debug('uninit is neither funtion nor coroutine function')
                self.remove_cog(cog)
            for command in self.crossmodule._cogs[module]:
                self.remove_command(command)
            
            self.crossmodule._remove_module(module)
            self.log.debug('unloaded {}'.format(module))

            if unimport:
                def _is_submodule(parent, child):
                    return parent == child or child.startswith(parent + ".")

                for p_submodule in list(sys.modules.keys()):
                    if _is_submodule(module, p_submodule):
                        del sys.modules[p_submodule]

                self.log.debug('unimported {}'.format(module))

    async def generate_invite_link(self, *, permissions=discord.Permissions(70380544), guild=None):
        app_info = await self.application_info()
        return discord.utils.oauth_url(app_info.id, permissions=permissions, guild=guild)

    async def unload_all_module(self):
        await self.unload_modules(self.crossmodule.modules_loaded())

    def _delete_old_audiocache(self, path=AUDIO_CACHE_PATH):
        try:
            shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)
            return True
        except:
            try:
                os.rename(path, path + '__')
            except:
                return False
            try:
                shutil.rmtree(path)
            except:
                os.rename(path + '__', path)
                return False

        return True

    async def _on_ready_sanity_checks(self):
        # Ensure folders exist
        await self._scheck_ensure_env()

        # Server permissions check
        await self._scheck_server_permissions()

        # playlists in autoplaylist
        await self._scheck_autoplaylist()

        # streamss in autostream
        await self._scheck_autostream()

        # config/permissions async validate?
        await self._scheck_configs()


    async def _scheck_ensure_env(self):
        self.log.debug("Ensuring data folders exist")
        for guild in self.guilds:
            pathlib.Path('data/%s/' % guild.id).mkdir(exist_ok=True)

        with open('data/server_names.txt', 'w', encoding='utf8') as f:
            for guild in sorted(self.guilds, key=lambda s:int(s.id)):
                f.write('{:<22} {}\n'.format(guild.id, guild.name))

        if not self.config.save_videos and os.path.isdir(AUDIO_CACHE_PATH):
            if self._delete_old_audiocache():
                self.log.debug("Deleted old audio cache")
            else:
                self.log.debug("Could not delete old audio cache, moving on.")


    async def _scheck_server_permissions(self):
        self.log.debug("Checking server permissions")
        pass # TODO

    async def _scheck_autoplaylist(self):
        self.log.debug("Auditing autoplaylist")
        pass # TODO

    async def _scheck_autostream(self):
        self.log.debug("Auditing autostream")
        pass # TODO

    async def _scheck_configs(self):
        self.log.debug("Validating config")
        await self.config.async_validate(self)

        self.log.debug("Validating permissions config")
        await self.permissions.async_validate(self)

    @staticmethod
    def _check_if_empty(vchannel: discord.abc.GuildChannel, *, excluding_me=True, excluding_deaf=False):
        def check(member):
            if excluding_me and member == vchannel.guild.me:
                return False

            if excluding_deaf and any([member.deaf, member.self_deaf]):
                return False

            if member.bot:
                return False

            return True

        return not sum(1 for m in vchannel.members if check(m))

    async def _join_startup_channels(self, channels, *, autosummon=True):
        joined_servers = set()
        channel_map = {get_guild(self, c.guild): c for c in channels}

        def _autopause(player):
            if self._check_if_empty(player._guild._voice_channel):
                self.log.info("Initial autopause in empty channel")

                asyncio.ensure_future(player.pause())
                self.server_specific_data[player._guild]['auto_paused'] = True

        for guild in get_guild_list(self):
            if guild.guild.unavailable or guild in channel_map:
                continue

            if guild.guild.me.voice:
                self.log.info("Found resumable voice channel {0.guild.name}/{0.name}".format(guild.guild.me.voice.channel))
                channel_map[guild] = guild.guild.me.voice.channel

            if autosummon:
                owner = guild.get_owner(voice=True)
                if owner:
                    self.log.info("Found owner in \"{}\"".format(owner.voice.channel.name))
                    channel_map[guild] = owner.voice.channel

        for guild, channel in channel_map.items():
            if guild in joined_servers:
                self.log.info("Already joined a channel in \"{}\", skipping".format(guild.name))
                continue

            if channel and isinstance(channel, discord.VoiceChannel):
                self.log.info("Attempting to join {0.guild.name}/{0.name}".format(channel))

                chperms = channel.permissions_for(guild.guild.me)

                if not chperms.connect:
                    self.log.info("Cannot join channel \"{}\", no permission.".format(channel.name))
                    continue

                elif not chperms.speak:
                    self.log.info("Will not join channel \"{}\", no permission to speak.".format(channel.name))
                    continue

                try:
                    await guild.set_connected_voice_channel(channel)
                    joined_servers.add(guild)

                    self.log.info("Joined {0.guild.name}/{0.name}".format(channel))

                    if guild._autos:
                        player = await guild.get_player()
                        if self.config.auto_pause:
                            player.once('play', lambda player, **_: _autopause(player))
                        if not player._playlist._list:
                            await guild.on_player_finished_playing(player)

                except Exception:
                    self.log.debug("Error joining {0.guild.name}/{0.name}".format(channel), exc_info=True)
                    self.log.error("Failed to join {0.guild.name}/{0.name}".format(channel))

            elif channel:
                self.log.warning("Not joining {0.guild.name}/{0.name}, that's a text channel.".format(channel))

            else:
                self.log.warning("Invalid channel thing: {}".format(channel))

    async def on_ready(self):
        self.log.debug("Connection established, ready to go.")

        self.ws._keep_alive.name = 'Gateway Keepalive'

        if self._init:
            self.log.debug("Received additional READY event, may have failed to resume")
            return

        app_info = await self.application_info()  
        if self._owner_id == 'auto' or not self._owner_id:
            self.log.info('Using application\'s owner')
            self._owner_id = app_info.owner.id

        else:
            if not self.get_user(self._owner_id):
                self.log.warning('Cannot find specified owner, falling back to application\'s owner')
                self._owner_id = app_info.owner.id  

        await self._on_ready_sanity_checks()

        register_bot(self)
        
        self.log.info("Connected")
        self.log.info("Client:\n    ID: {id}\n    name: {name}#{discriminator}\n".format(
            id = self.user.id,
            name = self.user.name,
            discriminator = self.user.discriminator
            ))        

        self.log.info("Owner:\n    ID: {id}\n    name: {name}#{discriminator}\n".format(
            id = self._owner_id,
            name = self.get_user(self._owner_id).name,
            discriminator = self.get_user(self._owner_id).discriminator
            ))

        if self._owner_id and self.guilds:

            self.log.info('Guild List:')
            for s in self.guilds:
                ser = ('{} (unavailable)'.format(s.name) if s.unavailable else s.name)
                self.log.info(' - ' + ser)

            unavailable_servers = 0
            if self.config.leavenonowners:
                unavailable_servers = prunenoowner(self)
                
            if unavailable_servers != 0:
                self.log.info('Not proceeding with checks in {} servers due to unavailability'.format(str(unavailable_servers))) 

        elif self.guilds:
            self.log.warning("Owner could not be found on any guild (id: %s)\n" % self.config.owner_id)

            self.log.info('Guild List:')
            for s in self.guilds:
                ser = ('{} (unavailable)'.format(s.name) if s.unavailable else s.name)
                self.log.info(' - ' + ser)

        else:
            self.log.warning("Owner unknown, bot is not on any guilds.")
            if self.user.bot:
                self.log.warning(
                    "To make the bot join a guild, paste this link in your browser. \n"
                    "Note: You should be logged into your main account and have \n"
                    "manage server permissions on the guild you want the bot to join.\n"
                    "  " + await self.generate_invite_link()
                )

        print(flush=True)

        if self.config.bound_channels:
            chlist = set(self.get_channel(i) for i in self.config.bound_channels if i)
            chlist.discard(None)

            invalids = set()
            invalids.update(c for c in chlist if isinstance(c, discord.VoiceChannel))

            chlist.difference_update(invalids)
            self.config.bound_channels.difference_update(invalids)

            if chlist:
                self.log.info("Bound to text channels:")
                [self.log.info(' - {}/{}'.format(ch.guild.name.strip(), ch.name.strip())) for ch in chlist if ch]
            else:
                print("Not bound to any text channels")

            if invalids and self.config.debug_mode:
                print(flush=True)
                self.log.info("Not binding to voice channels:")
                [self.log.info(' - {}/{}'.format(ch.guild.name.strip(), ch.name.strip())) for ch in invalids if ch]

            print(flush=True)

        else:
            self.log.info("Not bound to any text channels")

        if self.config.autojoin_channels:
            chlist = set(self.get_channel(i) for i in self.config.autojoin_channels if i)
            chlist.discard(None)

            invalids = set()
            invalids.update(c for c in chlist if isinstance(c, discord.TextChannel))

            chlist.difference_update(invalids)
            self.config.autojoin_channels.difference_update(invalids)

            if chlist:
                self.log.info("Autojoining voice channels:")
                [self.log.info(' - {}/{}'.format(ch.guild.name.strip(), ch.name.strip())) for ch in chlist if ch]
            else:
                self.log.info("Not autojoining any voice channels")

            if invalids and self.config.debug_mode:
                print(flush=True)
                self.log.info("Cannot autojoin text channels:")
                [self.log.info(' - {}/{}'.format(ch.guild.name.strip(), ch.name.strip())) for ch in invalids if ch]

            self.autojoin_channels = chlist

        else:
            self.log.info("Not autojoining any voice channels")
            self.autojoin_channels = set()
        
        if self.config.show_config_at_start:
            print(flush=True)
            self.log.info("Options:")

            self.log.info("  Command prefix: " + self.config.command_prefix)
            self.log.info("  Default volume: {}%".format(int(self.config.default_volume * 100)))
            self.log.info("  Skip threshold: {} votes or {}%".format(
                self.config.skips_required, fixg(self.config.skip_ratio_required * 100)))
            self.log.info("  Now Playing @mentions: " + ['Disabled', 'Enabled'][self.config.now_playing_mentions])
            self.log.info("  Auto-Summon: " + ['Disabled', 'Enabled'][self.config.auto_summon])
            self.log.info("  Auto-Pause: " + ['Disabled', 'Enabled'][self.config.auto_pause])
            self.log.info("  Delete Messages: " + ['Disabled', 'Enabled'][self.config.delete_messages])
            if self.config.delete_messages:
                self.log.info("    Delete Invoking: " + ['Disabled', 'Enabled'][self.config.delete_invoking])
            self.log.info("  Debug Mode: " + ['Disabled', 'Enabled'][self.config.debug_mode])
            self.log.info("  Downloaded songs will be " + ['deleted', 'saved'][self.config.save_videos])
            if self.config.status_message:
                self.log.info("  Status message: " + self.config.status_message)
            self.log.info("  Write current songs to file: " + ['Disabled', 'Enabled'][self.config.write_current_song])
            self.log.info("  Author insta-skip: " + ['Disabled', 'Enabled'][self.config.allow_author_skip])
            self.log.info("  Embeds: " + ['Disabled', 'Enabled'][self.config.embeds])
            self.log.info("  Spotify integration: " + ['Disabled', 'Enabled'][self.config._spotify])
            self.log.info("  Legacy skip: " + ['Disabled', 'Enabled'][self.config.legacy_skip])
            self.log.info("  Leave non owners: " + ['Disabled', 'Enabled'][self.config.leavenonowners])

        print(flush=True)

        # TODO: now playing status

        # maybe option to leave the ownerid blank and generate a random command for the owner to use
        # wait_for_message is pretty neato

        await self._join_startup_channels(self.autojoin_channels, autosummon=self.config.auto_summon)

        # we do this after the config stuff because it's a lot easier to notice here
        if self.config.missing_keys:
            self.log.warning('Your config file is missing some options. If you have recently updated, '
                        'check the example_options.ini file to see if there are new options available to you. '
                        'The options missing are: {0}'.format(self.config.missing_keys))
            print(flush=True)

        # t-t-th-th-that's all folks!

        self._init = True

        for name, cog in self.cogs.items():
            if 'on_ready' in dir(cog):
                self.log.debug('executing on_ready in {}'.format(name))
                potential = getattr(cog, 'on_ready')
                self.log.debug(str(potential))
                self.log.debug(str(potential.__func__))
                if iscoroutinefunction(potential.__func__):
                    await potential()
                elif isfunction(potential.__func__):
                    potential()
                else:
                    self.log.debug('post_init is neither funtion nor coroutine function')


    def run(self):
        self.thread = threading.currentThread()
        self.log.debug('running bot on thread {}'.format(threading.get_ident()))
        self.looplock.acquire()

        def exchdlr(loop, excctx):
            exception = excctx.get('exception')
            if system() == 'Windows':
                if isinstance(exception, PermissionError) and exception.winerror == 121:
                    self.log.debug('suppressing "the semaphore timeout period has expired" exception', exc_info = exception)
            else:
                raise exception

        self.loop.set_exception_handler(exchdlr)
        try:
            self.loop.create_task(self.start(self.config._login_token))
        except discord.errors.LoginFailure:
            # Add if token, else
            raise exceptions.HelpfulError(
                "Bot cannot login, bad credentials.",
                "Fix your token in the options file.  "
                "Remember that each field should be on their own line."
            )  #     ^^^^ In theory self.config.auth should never have no items
        self.loop.run_forever()

    async def _logout(self):
        guilds = get_guild_list(self)
        for guild in guilds:
            try:
                await guild.set_connected_voice_channel(None)
            except:
                pass
                
            await guild.serialize_to_file()
        await self.unload_all_module()
        await super().logout()
        await self.aiosession.close()
        self.log.debug('finished cleaning up')

    def logout_loopstopped(self):
        self.log.debug('on thread {}'.format(threading.get_ident()))
        self.log.info('logging out (loopstopped)..')
        self.loop.run_until_complete(self._logout())
        self.log.info('canceling incomplete tasks...')
        gathered = asyncio.gather(*asyncio.Task.all_tasks(self.loop), loop=self.loop)
        gathered.cancel()
        async def await_gathered():
            with suppress(Exception):
                await gathered
        self.loop.run_until_complete(await_gathered())
        self.downloader.shutdown()
        self.log.info('closing loop...')
        self.loop.close()
        self.log.info('finished!')

    def logout_looprunning(self):
        async def _stop():
            self.loop.stop()
            self.looplock.release()

        self.log.debug('on thread {}'.format(threading.get_ident()))
        self.log.debug('bot\'s thread status: {}'.format(self.thread.is_alive()))
        self.log.info('logging out (looprunning)..')
        future = asyncio.run_coroutine_threadsafe(self._logout(), self.loop)
        future.result()
        self.log.debug('stopping loop...')
        future = asyncio.run_coroutine_threadsafe(_stop(), self.loop)
        self.looplock.acquire()
        self.log.info('canceling incomplete tasks...')
        gathered = asyncio.gather(*asyncio.Task.all_tasks(self.loop), loop=self.loop)
        gathered.cancel()
        async def await_gathered():
            with suppress(Exception):
                await gathered
        self.loop.run_until_complete(await_gathered())
        self.downloader.shutdown()
        self.log.info('closing loop...')
        self.loop.close()
        self.log.info('finished!')

    def logout(self):
        self.log.info('logging out...')
        if self.loop.is_running():
            self.logout_looprunning()
        else:
            self.logout_loopstopped()
        self._init = False
        if getattr(self, '_restart', None):
            raise exceptions.RestartSignal('restarting...')

    class check_online:
        def __call__(self, func):
            @wraps(func)
            async def wrapper(bot, *args, **kwargs):
                if bot._init:
                    return await func(bot, *args, **kwargs)
                else:
                    raise Exception('bot is not online')
            return wrapper

    @check_online()
    async def get_owner_id(self):
        return self._owner_id

    def online(self):
        return self._init

    async def get_presence(self):
        async with self._aiolocks['presence']:
            return self._presence

    async def set_presence(self, *, activity = None, status=None):
        async with self._aiolocks['presence']:
            await self.change_presence(activity = activity, status = status)
            self._presence = (activity, status)

    async def update_now_playing_status(self, entry=None, is_paused=False):
        game = None

        if not self.config.status_message:
            if self.user.bot:
                activeplayers = sum(1 for g in get_guild_list(self) if g._player and g._player.state == PlayerState.PLAYING)
                if activeplayers > 1:
                    game = discord.Game(type=0, name="music on %s guilds" % activeplayers)
                    entry = None

            if entry:
                prefix = u'\u275A\u275A ' if is_paused else ''

                name = u'{}{}'.format(prefix, entry.title)[:128]
                game = discord.Game(type=0, name=name)
        else:
            game = discord.Game(type=0, name=self.config.status_message.strip()[:128])

        async with self._aiolocks['presence']:
            await self.change_presence(activity = game)
            self._presence = (game, self._presence[1])


    async def eval_bot(self, code):
        return eval(code)

    async def exec_bot(self, code):
        exec(code)
        
