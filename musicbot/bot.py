import os
import sys
import time
import shlex
import shutil
import random
import inspect
import logging
import asyncio
import pathlib
import traceback
import math
import re

import aiohttp
import discord
import colorlog

from io import BytesIO, StringIO
from functools import wraps
from textwrap import dedent
from datetime import timedelta
from collections import defaultdict

from discord.enums import ChannelType

from . import exceptions
from . import downloader

from .playlist import Playlist
from .player import MusicPlayer
from .entry import StreamPlaylistEntry
from .opus_loader import load_opus_lib
from .config import Config, ConfigDefaults
from .permissions import Permissions, PermissionsDefaults
from .alias import Alias, AliasDefaults
from .constructs import SkipState, Response
from .utils import load_file, write_file, fixg, ftimedelta, _func_, _get_variable
from .spotify import Spotify
from .json import Json
from .wrappers import ensure_appinfo

from .constants import VERSION as BOTVERSION
from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH

from .cogsmanager import load, callcmd, getcmd, init_cog_system, uninit_cog_system, gen_cmd_list, wait_cog_system
from . import guildmanager
from . import voicechannelmanager
from . import messagemanager


load_opus_lib()

log = logging.getLogger(__name__)


class MusicBot(discord.Client):
    def __init__(self, config_file=None, perms_file=None, alias_file=None):
        try:
            sys.stdout.write("\x1b]2;MusicBot {}\x07".format(BOTVERSION))
        except:
            pass

        print()

        if config_file is None:
            config_file = ConfigDefaults.options_file

        if perms_file is None:
            perms_file = PermissionsDefaults.perms_file

        self.exit_signal = None
        self.init_ok = False
        self.cached_app_info = None
        self.last_status = None

        self.config = Config(config_file)
        
        self._setup_logging()
        
        self.permissions = Permissions(perms_file, grant_all=[self.config.owner_id])
        self.str = Json(self.config.i18n_file)

        self.blacklist = set(load_file(self.config.blacklist_file))
        self.autoplaylist = load_file(self.config.auto_playlist_file)

        self.aiolocks = defaultdict(asyncio.Lock)
        self.downloader = downloader.Downloader(download_folder='audio_cache')

        log.info('Starting MusicBot {}'.format(BOTVERSION))

        if not self.autoplaylist:
            log.warning("Autoplaylist is empty, disabling.")
            self.config.auto_playlist = False
        else:
            log.info("Loaded autoplaylist with {} entries".format(len(self.autoplaylist)))

        if self.blacklist:
            log.debug("Loaded blacklist with {} entries".format(len(self.blacklist)))

        # TODO: Do these properly
        ssd_defaults = {
            'last_np_msg': None,
            'auto_paused': False,
            'availability_paused': False
        }
        self.server_specific_data = defaultdict(ssd_defaults.copy)

        super().__init__()
        self.aiosession = aiohttp.ClientSession(loop=self.loop)
        self.http.user_agent += ' MusicBot/%s' % BOTVERSION

        self.spotify = None
        if self.config._spotify:
            try:
                self.spotify = Spotify(self.config.spotify_clientid, self.config.spotify_clientsecret, aiosession=self.aiosession, loop=self.loop)
                if not self.spotify.token:
                    log.warning('Spotify did not provide us with a token. Disabling.')
                    self.config._spotify = False
                else:
                    log.info('Authenticated with Spotify successfully using client ID and secret.')
            except exceptions.SpotifyError as e:
                log.warning('There was a problem initialising the connection to Spotify. Is your client ID and secret correct? Details: {0}. Continuing anyway in 5 seconds...'.format(e))
                self.config._spotify = False
                time.sleep(5)  # make sure they see the problem

        async def init_modules_importer():
            await wait_cog_system()
            for module in self.config.cogs:
                try:
                    await load(module)
                except exceptions.CogError as e:
                    log.error("Error loading module {0}: {1.__class__.__name__}: {1.message}".format(module, e))
                    if e.__cause__ is not None:
                        log.error("Traceback:\n{0}{1}: {2}".format("".join(traceback.format_list(traceback.extract_tb(e.__cause__.__traceback__))), type(e.__cause__).__name__, e.__context__)) # pylint: disable=E1101

        init_cog_system(self, alias_file)
        self.loop.create_task(init_modules_importer())

    def _get_owner(self, *, server=None, voice=False):
            return discord.utils.find(
                lambda m: m.id == self.config.owner_id and (m.voice if voice else True),
                server.members if server else self.get_all_members()
            )

    def _delete_old_audiocache(self, path=AUDIO_CACHE_PATH):
        try:
            shutil.rmtree(path)
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

    def _setup_logging(self):
        if len(logging.getLogger(__package__).handlers) > 1:
            log.debug("Skipping logger setup, already set up")
            return

        shandler = logging.StreamHandler(stream=sys.stdout)
        shandler.setFormatter(colorlog.LevelFormatter(
            fmt = {
                'DEBUG': '{log_color}[{levelname}:{module}] {message}',
                'INFO': '{log_color}{message}',
                'WARNING': '{log_color}{levelname}: {message}',
                'ERROR': '{log_color}[{levelname}:{module}] {message}',
                'CRITICAL': '{log_color}[{levelname}:{module}] {message}',

                'EVERYTHING': '{log_color}[{levelname}:{module}] {message}',
                'NOISY': '{log_color}[{levelname}:{module}] {message}',
                'VOICEDEBUG': '{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}',
                'FFMPEG': '{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}'
            },
            log_colors = {
                'DEBUG':    'cyan',
                'INFO':     'white',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'bold_red',

                'EVERYTHING': 'white',
                'NOISY':      'white',
                'FFMPEG':     'bold_purple',
                'VOICEDEBUG': 'purple',
        },
            style = '{',
            datefmt = ''
        ))
        shandler.setLevel(self.config.debug_level)
        logging.getLogger(__package__).addHandler(shandler)

        log.debug("Set logging level to {}".format(self.config.debug_level_str))

        if self.config.debug_mode:
            dlogger = logging.getLogger('discord')
            dlogger.setLevel(logging.DEBUG)
            dhandler = logging.FileHandler(filename='logs/discord.log', encoding='utf-8', mode='w')
            dhandler.setFormatter(logging.Formatter('{asctime}:{levelname}:{name}: {message}', style='{'))
            dlogger.addHandler(dhandler)

    @staticmethod
    def _check_if_empty(vchannel: discord.abc.GuildChannel, *, excluding_me=True, excluding_deaf=False):
        def check(member):
            if excluding_me and member == vchannel.guild.me:
                return False

            if excluding_deaf and any([member.deaf, member.self_deaf]):
                return False

            return True

        return not sum(1 for m in vchannel.members if check(m))

    async def _join_startup_channels(self, channels, *, autosummon=True):
        joined_servers = set()
        channel_map = {guildmanager.get_guild(self, c.guild): c for c in channels}

        def _autopause(player):
            if self._check_if_empty(player.voice_client.channel):
                log.info("Initial autopause in empty channel")

                player.pause()
                self.server_specific_data[player.voice_client.channel.guild]['auto_paused'] = True

        for guild in guildmanager.getguildlist(self):
            if guild._guild.unavailable or guild in channel_map:
                continue

            if guild._guild.me.voice:
                log.info("Found resumable voice channel {0.guild.name}/{0.name}".format(guild._guild.me.voice.channel))
                channel_map[guild] = guild._guild.me.voice.channel

            if autosummon:
                owner = guild.get_owner(voice=True)
                if owner:
                    log.info("Found owner in \"{}\"".format(owner.voice.channel.name))
                    channel_map[guild] = owner.voice.channel

        for guild, channel in channel_map.items():
            if guild in joined_servers:
                log.info("Already joined a channel in \"{}\", skipping".format(guild.name))
                continue

            if channel and isinstance(channel, discord.VoiceChannel):
                log.info("Attempting to join {0.guild.name}/{0.name}".format(channel))

                chperms = channel.permissions_for(guild._guild.me)

                if not chperms.connect:
                    log.info("Cannot join channel \"{}\", no permission.".format(channel.name))
                    continue

                elif not chperms.speak:
                    log.info("Will not join channel \"{}\", no permission to speak.".format(channel.name))
                    continue

                try:
                    mchannel = voicechannelmanager.ManagedVC(guild, channel)
                    player = await mchannel.get_player(create=True, deserialize=self.config.persistent_queue)
                    joined_servers.add(guild)

                    log.info("Joined {0.guild.name}/{0.name}".format(channel))

                    if player.is_stopped:
                        player.play()

                    if self.config.auto_playlist:
                        if self.config.auto_pause:
                            player.once('play', lambda player, **_: _autopause(player))
                        if not player.playlist.entries:
                            await mchannel.on_player_finished_playing(player)

                except Exception:
                    log.debug("Error joining {0.guild.name}/{0.name}".format(channel), exc_info=True)
                    log.error("Failed to join {0.guild.name}/{0.name}".format(channel))

            elif channel:
                log.warning("Not joining {0.guild.name}/{0.name}, that's a text channel.".format(channel))

            else:
                log.warning("Invalid channel thing: {}".format(channel))

    async def _check_ignore_non_voice(self, msg):
        if msg.guild.me.voice:
            vc = msg.guild.me.voice.channel
        else:
            vc = None

        # If we've connected to a voice chat and we're in the same voice channel
        if not vc or (msg.author.voice and vc == msg.author.voice.channel):
            return True
        else:
            raise exceptions.PermissionsError(
                "you cannot use this command when not in the voice channel (%s)" % vc.name, expire_in=30)

    async def _cache_app_info(self, *, update=False):
        if not self.cached_app_info and not update and self.user.bot:
            log.debug("Caching app info")
            self.cached_app_info = await self.application_info()

        return self.cached_app_info


    async def remove_from_autoplaylist(self, song_url:str, *, ex:Exception=None, delete_from_ap=False):
        if song_url not in self.autoplaylist:
            log.debug("URL \"{}\" not in autoplaylist, ignoring".format(song_url))
            return

        async with self.aiolocks[_func_()]:
            self.autoplaylist.remove(song_url)
            log.info("Removing unplayable song from session autoplaylist: %s" % song_url)

            with open(self.config.auto_playlist_removed_file, 'a', encoding='utf8') as f:
                f.write(
                    '# Entry removed {ctime}\n'
                    '# Reason: {ex}\n'
                    '{url}\n\n{sep}\n\n'.format(
                        ctime=time.ctime(),
                        ex=str(ex).replace('\n', '\n#' + ' ' * 10), # 10 spaces to line up with # Reason:
                        url=song_url,
                        sep='#' * 32
                ))

            if delete_from_ap:
                log.info("Updating autoplaylist")
                write_file(self.config.auto_playlist_file, self.autoplaylist)

    @ensure_appinfo
    async def generate_invite_link(self, *, permissions=discord.Permissions(70380544), guild=None):
        return discord.utils.oauth_url(self.cached_app_info.id, permissions=permissions, guild=guild)

    async def disconnect_all_voice_clients(self):
        for guild in guildmanager.getguildlist(self):
            await guild.disconnect_voice_client()

    async def update_now_playing_status(self, entry=None, is_paused=False):
        game = None

        if not self.config.status_message:
            if self.user.bot:
                players = [guild.get_player_in() for guild in guildmanager.getguildlist(self) if guild.get_player_in()]
                activeplayers = sum(1 for player in players if player.is_playing)
                if activeplayers > 1:
                    game = discord.Game(type=0, name="music on %s guilds" % activeplayers)
                    entry = None

                elif activeplayers == 1:
                    player = discord.utils.get(players, is_playing=True)
                    entry = player.current_entry

            if entry:
                prefix = u'\u275A\u275A ' if is_paused else ''

                name = u'{}{}'.format(prefix, entry.title)[:128]
                game = discord.Game(type=0, name=name)
        else:
            game = discord.Game(type=0, name=self.config.status_message.strip()[:128])

        async with self.aiolocks[_func_()]:
            if game != self.last_status:
                await self.change_presence(activity=game)
                self.last_status = game

    async def serialize_all_queues(self, *, dir=None):
        coros = [s.serialize_queue(s, dir=dir) for s in guildmanager.getguildlist(self)]
        await asyncio.gather(*coros, return_exceptions=True)

    @ensure_appinfo
    async def _on_ready_sanity_checks(self):
        # Ensure folders exist
        await self._scheck_ensure_env()

        # Server permissions check
        await self._scheck_server_permissions()

        # playlists in autoplaylist
        await self._scheck_autoplaylist()

        # config/permissions async validate?
        await self._scheck_configs()


    async def _scheck_ensure_env(self):
        log.debug("Ensuring data folders exist")
        for guild in self.guilds:
            pathlib.Path('data/%s/' % guild.id).mkdir(exist_ok=True)

        with open('data/server_names.txt', 'w', encoding='utf8') as f:
            for guild in sorted(self.guilds, key=lambda s:int(s.id)):
                f.write('{:<22} {}\n'.format(guild.id, guild.name))

        if not self.config.save_videos and os.path.isdir(AUDIO_CACHE_PATH):
            if self._delete_old_audiocache():
                log.debug("Deleted old audio cache")
            else:
                log.debug("Could not delete old audio cache, moving on.")


    async def _scheck_server_permissions(self):
        log.debug("Checking server permissions")
        pass # TODO

    async def _scheck_autoplaylist(self):
        log.debug("Auditing autoplaylist")
        pass # TODO

    async def _scheck_configs(self):
        log.debug("Validating config")
        await self.config.async_validate(self)

        log.debug("Validating permissions config")
        await self.permissions.async_validate(self)



#######################################################################################################################

    async def restart(self):
        self.exit_signal = exceptions.RestartSignal()
        await self.logout()

    def restart_threadsafe(self):
        asyncio.run_coroutine_threadsafe(self.restart(), self.loop)

    def _cleanup(self):
        self.loop.run_until_complete(uninit_cog_system())
        try:
            self.loop.run_until_complete(self.logout())
            self.loop.run_until_complete(self.aiosession.close())
        except: pass

        pending = asyncio.Task.all_tasks()
        gathered = asyncio.gather(*pending)

        try:
            gathered.cancel()
            self.loop.run_until_complete(gathered)
            gathered.exception()
        except: pass

    # noinspection PyMethodOverriding
    def run(self):
        try:
            self.loop.run_until_complete(self.start(*self.config.auth))

        except discord.errors.LoginFailure:
            # Add if token, else
            raise exceptions.HelpfulError(
                "Bot cannot login, bad credentials.",
                "Fix your token in the options file.  "
                "Remember that each field should be on their own line."
            )  #     ^^^^ In theory self.config.auth should never have no items

        finally:
            try:
                self._cleanup()
            except Exception:
                log.error("Error in cleanup", exc_info=True)

            if self.exit_signal:
                raise self.exit_signal # pylint: disable=E0702

    async def logout(self):
        await self.disconnect_all_voice_clients()
        return await super().logout()

    async def on_error(self, event, *args, **kwargs):
        ex_type, ex, stack = sys.exc_info() # pylint: disable=unused-variable

        if ex_type == exceptions.HelpfulError:
            log.error("Exception in {}:\n{}".format(event, ex.message))

            await asyncio.sleep(2)  # don't ask
            await self.logout()

        elif issubclass(ex_type, exceptions.Signal):
            self.exit_signal = ex_type
            await self.logout()

        else:
            log.error("Exception in {}".format(event), exc_info=True)

    async def on_resumed(self):
        log.info("\nReconnected to discord.\n")

    async def on_ready(self):
        dlogger = logging.getLogger('discord')
        for h in dlogger.handlers:
            if getattr(h, 'terminator', None) == '':
                dlogger.removeHandler(h)
                print()

        log.debug("Connection established, ready to go.")

        self.ws._keep_alive.name = 'Gateway Keepalive'

        if self.init_ok:
            log.debug("Received additional READY event, may have failed to resume")
            return

        await self._on_ready_sanity_checks()

        # prepare guildmanager
        guildmanager.registerguildmanage(self)

        self.init_ok = True

        ################################

        log.info("Connected: {0}/{1}#{2}".format(
            self.user.id,
            self.user.name,
            self.user.discriminator
        ))

        owner = self._get_owner(voice=True) or self._get_owner()
        if owner and self.guilds:
            log.info("Owner:     {0}/{1}#{2}\n".format(
                owner.id,
                owner.name,
                owner.discriminator
            ))

            log.info('Guild List:')
            for s in self.guilds:
                ser = ('{} (unavailable)'.format(s.name) if s.unavailable else s.name)
                log.info(' - ' + ser)

            unavailable_servers = 0
            if self.config.leavenonowners:
                unavailable_servers = guildmanager.prunenoowner(self)
                
            if unavailable_servers != 0:
                log.info('Not proceeding with checks in {} servers due to unavailability'.format(str(unavailable_servers))) 

        elif self.guilds:
            log.warning("Owner could not be found on any guild (id: %s)\n" % self.config.owner_id)

            log.info('Guild List:')
            for s in self.guilds:
                ser = ('{} (unavailable)'.format(s.name) if s.unavailable else s.name)
                log.info(' - ' + ser)

        else:
            log.warning("Owner unknown, bot is not on any guilds.")
            if self.user.bot:
                log.warning(
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
                log.info("Bound to text channels:")
                [log.info(' - {}/{}'.format(ch.guild.name.strip(), ch.name.strip())) for ch in chlist if ch]
            else:
                print("Not bound to any text channels")

            if invalids and self.config.debug_mode:
                print(flush=True)
                log.info("Not binding to voice channels:")
                [log.info(' - {}/{}'.format(ch.guild.name.strip(), ch.name.strip())) for ch in invalids if ch]

            print(flush=True)

        else:
            log.info("Not bound to any text channels")

        if self.config.autojoin_channels:
            chlist = set(self.get_channel(i) for i in self.config.autojoin_channels if i)
            chlist.discard(None)

            invalids = set()
            invalids.update(c for c in chlist if isinstance(c, discord.TextChannel))

            chlist.difference_update(invalids)
            self.config.autojoin_channels.difference_update(invalids)

            if chlist:
                log.info("Autojoining voice channels:")
                [log.info(' - {}/{}'.format(ch.guild.name.strip(), ch.name.strip())) for ch in chlist if ch]
            else:
                log.info("Not autojoining any voice channels")

            if invalids and self.config.debug_mode:
                print(flush=True)
                log.info("Cannot autojoin text channels:")
                [log.info(' - {}/{}'.format(ch.guild.name.strip(), ch.name.strip())) for ch in invalids if ch]

            self.autojoin_channels = chlist

        else:
            log.info("Not autojoining any voice channels")
            self.autojoin_channels = set()
        
        if self.config.show_config_at_start:
            print(flush=True)
            log.info("Options:")

            log.info("  Command prefix: " + self.config.command_prefix)
            log.info("  Default volume: {}%".format(int(self.config.default_volume * 100)))
            log.info("  Skip threshold: {} votes or {}%".format(
                self.config.skips_required, fixg(self.config.skip_ratio_required * 100)))
            log.info("  Now Playing @mentions: " + ['Disabled', 'Enabled'][self.config.now_playing_mentions])
            log.info("  Auto-Summon: " + ['Disabled', 'Enabled'][self.config.auto_summon])
            log.info("  Auto-Playlist: " + ['Disabled', 'Enabled'][self.config.auto_playlist] + " (order: " + ['sequential', 'random'][self.config.auto_playlist_random] + ")")
            log.info("  Auto-Pause: " + ['Disabled', 'Enabled'][self.config.auto_pause])
            log.info("  Delete Messages: " + ['Disabled', 'Enabled'][self.config.delete_messages])
            if self.config.delete_messages:
                log.info("    Delete Invoking: " + ['Disabled', 'Enabled'][self.config.delete_invoking])
            log.info("  Debug Mode: " + ['Disabled', 'Enabled'][self.config.debug_mode])
            log.info("  Downloaded songs will be " + ['deleted', 'saved'][self.config.save_videos])
            if self.config.status_message:
                log.info("  Status message: " + self.config.status_message)
            log.info("  Write current songs to file: " + ['Disabled', 'Enabled'][self.config.write_current_song])
            log.info("  Author insta-skip: " + ['Disabled', 'Enabled'][self.config.allow_author_skip])
            log.info("  Embeds: " + ['Disabled', 'Enabled'][self.config.embeds])
            log.info("  Spotify integration: " + ['Disabled', 'Enabled'][self.config._spotify])
            log.info("  Legacy skip: " + ['Disabled', 'Enabled'][self.config.legacy_skip])
            log.info("  Leave non owners: " + ['Disabled', 'Enabled'][self.config.leavenonowners])

        print(flush=True)

        await self.update_now_playing_status()

        # maybe option to leave the ownerid blank and generate a random command for the owner to use
        # wait_for_message is pretty neato

        await self._join_startup_channels(self.autojoin_channels, autosummon=self.config.auto_summon)

        # we do this after the config stuff because it's a lot easier to notice here
        if self.config.missing_keys:
            log.warning('Your config file is missing some options. If you have recently updated, '
                        'check the example_options.ini file to see if there are new options available to you. '
                        'The options missing are: {0}'.format(self.config.missing_keys))
            print(flush=True)

        # t-t-th-th-that's all folks!

    def _gen_embed(self):
        """Provides a basic template for embeds"""
        e = discord.Embed()
        e.colour = 7506394
        e.set_footer(text='Just-Some-Bots/MusicBot ({})'.format(BOTVERSION), icon_url='https://i.imgur.com/gFHBoZA.png')
        e.set_author(name=self.user.name, url='https://github.com/Just-Some-Bots/MusicBot', icon_url=self.user.avatar_url)
        return e

    async def _do_playlist_checks(self, permissions, player, author, testobj):
        num_songs = sum(1 for _ in testobj)

        # I have to do exe extra checks anyways because you can request an arbitrary number of search results
        if not permissions.allow_playlists and num_songs > 1:
            raise exceptions.PermissionsError(self.str.get('playlists-noperms', "You are not allowed to request playlists"), expire_in=30)

        if permissions.max_playlist_length and num_songs > permissions.max_playlist_length:
            raise exceptions.PermissionsError(
                self.str.get('playlists-big', "Playlist has too many entries ({0} > {1})").format(num_songs, permissions.max_playlist_length),
                expire_in=30
            )

        # This is a little bit weird when it says (x + 0 > y), I might add the other check back in
        if permissions.max_songs and player.playlist.count_for_user(author) + num_songs > permissions.max_songs:
            raise exceptions.PermissionsError(
                self.str.get('playlists-limit', "Playlist entries + your already queued songs reached limit ({0} + {1} > {2})").format(
                    num_songs, player.playlist.count_for_user(author), permissions.max_songs),
                expire_in=30
            )
        return True

    async def on_message(self, message):
        await self.wait_until_ready()

        message_content = message.content.strip()
        if not message_content.startswith(self.config.command_prefix):
            return

        if message.author == self.user:
            log.warning("Ignoring command from myself ({})".format(message.content))
            return

        if self.config.bound_channels and message.channel.id not in self.config.bound_channels:
            if self.config.unbound_servers:
                for channel in message.guild.channels:
                    if channel.id in self.config.bound_channels:
                        return
            else:
                return  # if I want to log this I just move it under the prefix check

        if (not isinstance(message.channel, discord.abc.GuildChannel)) and (not isinstance(message.channel, discord.abc.PrivateChannel)):
            return

        command, *args = message_content.split(' ')  # Uh, doesn't this break prefixes with spaces in them (it doesn't, config parser already breaks them)
        command = command[len(self.config.command_prefix):].lower().strip()

        # [] produce [''] which is not what we want (it break things)
        if args:
            args = ' '.join(args).lstrip(' ').split(' ')
        else:
            args = []

        handler = None
        try:
            handler = await getcmd(command)
        except exceptions.CogError as e:
            if self.config.warn_no_commands:
                expirein = e.expire_in if self.config.delete_messages else None
                alsodelete = message if self.config.delete_invoking else None

                if self.config.embeds:
                    content = self._gen_embed()
                    content.add_field(name='Error', value=e.message, inline=False)
                    content.colour = 13369344
                else:
                    content = '```\n{}\n```'.format(e.message)

                await messagemanager.safe_send_message(
                    message.channel,
                    content,
                    expire_in=expirein,
                    also_delete=alsodelete
                )
            return

        if isinstance(message.channel, discord.abc.PrivateChannel):
            if not (message.author.id == self.config.owner_id and command == 'joinserver'):
                await messagemanager.safe_send_message(message.channel, 'You cannot use this bot in private messages.')
                return

        if message.author.id in self.blacklist and message.author.id != self.config.owner_id:
            log.warning("User blacklisted: {0.id}/{0!s} ({1})".format(message.author, command))
            return

        else:
            log.info("{0.id}/{0!s}: {1}".format(message.author, message_content.replace('\n', '\n... ')))

        user_permissions = self.permissions.for_user(message.author)

        params = handler.params()

        sentmsg = response = None

        # noinspection PyBroadException
        try:
            if user_permissions.ignore_non_voice and command in user_permissions.ignore_non_voice:
                await self._check_ignore_non_voice(message)

            mguild = guildmanager.get_guild(self, message.channel.guild)

            handler_kwargs = {}

            # bot args needed to be sent in all cases, even if cmd doesn't use it
            params.pop('bot', None)
            handler_kwargs['bot'] = self

            if params.pop('message', None):
                handler_kwargs['message'] = message

            if params.pop('channel', None):
                handler_kwargs['channel'] = message.channel

            if params.pop('author', None):
                handler_kwargs['author'] = message.author

            if params.pop('guild', None):
                handler_kwargs['guild'] = message.guild

            if params.pop('player', None):
                handler_kwargs['player'] = mguild.get_player_in()

            if params.pop('_player', None):
                handler_kwargs['_player'] = mguild.get_player_in()

            if params.pop('permissions', None):
                handler_kwargs['permissions'] = user_permissions

            if params.pop('user_mentions', None):
                handler_kwargs['user_mentions'] = list(map(message.guild.get_member, message.raw_mentions))

            if params.pop('channel_mentions', None):
                handler_kwargs['channel_mentions'] = list(map(message.guild.get_channel, message.raw_channel_mentions))

            if params.pop('voice_channel', None):
                handler_kwargs['voice_channel'] = message.guild.me.voice.channel if message.guild.me.voice else None

            if params.pop('leftover_args', None):
                handler_kwargs['leftover_args'] = args

            args_expected = []
            for key, param in list(params.items()):

                # parse (*args) as a list of args
                if param.kind == param.VAR_POSITIONAL:
                    handler_kwargs[key] = args
                    params.pop(key)
                    continue

                # parse (*, args) as args rejoined as a string
                # multiple of these arguments will have the same value
                if param.kind == param.KEYWORD_ONLY and param.default == param.empty:
                    handler_kwargs[key] = ' '.join(args)
                    params.pop(key)
                    continue

                doc_key = '[{}={}]'.format(key, param.default) if param.default is not param.empty else key
                args_expected.append(doc_key)

                # Ignore keyword args with default values when the command had no arguments
                if not args and param.default is not param.empty:
                    params.pop(key)
                    continue

                # Assign given values to positional arguments
                if args:
                    arg_value = args.pop(0)
                    handler_kwargs[key] = arg_value
                    params.pop(key)

            if message.author.id != self.config.owner_id:
                if user_permissions.command_whitelist and handler.name not in user_permissions.command_whitelist:
                    raise exceptions.PermissionsError(
                        "This command is not enabled for your group ({}).".format(user_permissions.name),
                        expire_in=20)

                elif user_permissions.command_blacklist and handler.name in user_permissions.command_blacklist:
                    raise exceptions.PermissionsError(
                        "This command is disabled for your group ({}).".format(user_permissions.name),
                        expire_in=20)

            # Invalid usage, return docstring
            if params:
                docs = getattr(handler, '__doc__', None)
                if not docs:
                    docs = 'Usage: {}{} {}'.format(
                        self.config.command_prefix,
                        command,
                        ' '.join(args_expected)
                    )

                docs = dedent(docs)
                await messagemanager.safe_send_message(
                    message.channel,
                    '```\n{}\n```'.format(docs.format(command_prefix=self.config.command_prefix)),
                    expire_in=60
                )
                return

            response = await callcmd(command, **handler_kwargs)
            if response and isinstance(response, Response):
                if not isinstance(response.content, discord.Embed) and self.config.embeds:
                    content = self._gen_embed()
                    content.title = handler.name
                    content.description = response.content
                else:
                    content = response.content

                if response.reply:
                    if isinstance(content, discord.Embed):
                        content.description = '{} {}'.format(message.author.mention, content.description if content.description is not discord.Embed.Empty else '')
                    else:
                        content = '{}: {}'.format(message.author.mention, content)

                sentmsg = await messagemanager.safe_send_message(
                    message.channel, content,
                    expire_in=response.delete_after if self.config.delete_messages else 0,
                    also_delete=message if self.config.delete_invoking else None
                )

        except (exceptions.CommandError, exceptions.HelpfulError, exceptions.ExtractionError) as e:
            log.error("Error in {0}: {1.__class__.__name__}: {1.message}".format(command, e), exc_info=True)

            expirein = e.expire_in if self.config.delete_messages else None
            alsodelete = message if self.config.delete_invoking else None

            if self.config.embeds:
                content = self._gen_embed()
                content.add_field(name='Error', value=e.message, inline=False)
                content.colour = 13369344
            else:
                content = '```\n{}\n```'.format(e.message)

            await messagemanager.safe_send_message(
                message.channel,
                content,
                expire_in=expirein,
                also_delete=alsodelete
            )

        except exceptions.CogError as e:
            log.error("Error in {0}: {1.__class__.__name__}: {1.message}".format(command, e))
            if e.__cause__ is not None:
                log.error("Traceback:\n{0}{1}: {2}".format("".join(traceback.format_list(traceback.extract_tb(e.__cause__.__traceback__))), type(e.__cause__).__name__, e.__context__)) # pylint: disable=E1101

            expirein = e.expire_in if self.config.delete_messages else None
            alsodelete = message if self.config.delete_invoking else None

            if self.config.debug_mode and (e.__cause__ is not None):
                if self.config.embeds:
                    content = self._gen_embed()
                    content.add_field(name='Error', value=e.message+", traceback below", inline=False)
                    content.colour = 13369344
                else:
                    content = '```\n{}, traceback below\n```'.format(e.message)
            else:
                if self.config.embeds:
                    content = self._gen_embed()
                    content.add_field(name='Error', value=e.message, inline=False)
                    content.colour = 13369344
                else:
                    content = '```\n{}\n```'.format(e.message)

            await messagemanager.safe_send_message(
                message.channel,
                content,
                expire_in=expirein,
                also_delete=alsodelete
            )

            if self.config.debug_mode and (e.__cause__ is not None):
                tb = '```\n{}{}: {}\n```'.format("".join(traceback.format_list(traceback.extract_tb(e.__cause__.__traceback__))), type(e.__cause__).__name__, str(e.__context__)) # pylint: disable=E1101
                await messagemanager.safe_send_message(
                    message.channel,
                    tb,
                    expire_in=expirein,
                    also_delete=alsodelete
                )


        except exceptions.Signal:
            raise

        except Exception:
            log.error("Exception in on_message", exc_info=True)
            if self.config.debug_mode:
                await messagemanager.safe_send_message(message.channel, '```\n{}\n```'.format(traceback.format_exc()))

        finally:
            if not sentmsg and not response and self.config.delete_invoking:
                await asyncio.sleep(5)
                await messagemanager.safe_delete_message(message, quiet=True)

    async def on_voice_state_update(self, member, before, after):
        if not self.init_ok:
            return  # Ignore stuff before ready

        if before.channel:
            channel = before.channel
        elif after.channel:
            channel = after.channel
        else:
            return

        await guildmanager.get_guild(self, channel.guild).on_voice_state_update(member, before, after)        

    async def on_guild_update(self, before:discord.Guild, after:discord.Guild):
        if before.region != after.region:
            log.warning("Guild \"%s\" changed regions: %s -> %s" % (after.name, before.region, after.region))

    async def on_guild_join(self, guild:discord.Guild):
        log.info("Bot has been added to guild: {}".format(guild.name))

        guildmanager.add_guild(self, guild)

        owner = self._get_owner(voice=True) or self._get_owner()
        if self.config.leavenonowners:
            check = guild.get_member(owner.id)
            if check == None:
                await guild.leave()
                log.info('Left {} due to bot owner not found.'.format(guild.name))
                await owner.send(self.str.get('left-no-owner-guilds', 'Left `{}` due to bot owner not being found in it.'.format(guild.name)))
                return

        log.debug("Creating data folder for guild %s", guild.id)
        pathlib.Path('data/%s/' % guild.id).mkdir(exist_ok=True)

    async def on_guild_remove(self, guild:discord.Guild):
        if not self.init_ok:
            return # Ignore pre-ready events
        await guildmanager.get_guild(self, guild).on_guild_remove()

    async def on_guild_available(self, guild:discord.Guild):
        if not self.init_ok:
            return # Ignore pre-ready events
        await guildmanager.get_guild(self, guild).on_guild_available()

    async def on_guild_unavailable(self, guild:discord.Guild):
        if not self.init_ok:
            return # Ignore pre-ready events
        await guildmanager.get_guild(self, guild).on_guild_unavailable()

    def voice_client_in(self, guild):
        for vc in self.voice_clients:
            if vc.guild == guild:
                return vc
        return None

    async def eval_bot(self, code):
        return eval(code)

    async def exec_bot(self, code):
        exec(code)
