import asyncio
import inspect
import json
import logging
import math
import os
import pathlib
import random
import re
import shutil
import signal
import socket
import ssl
import sys
import time
import traceback
import uuid
from collections import defaultdict
from io import BytesIO, StringIO
from typing import TYPE_CHECKING, Any, DefaultDict, Dict, List, Optional, Set, Union

import aiohttp
import certifi
import discord
import yt_dlp as youtube_dl  # type: ignore[import-untyped]

from . import downloader, exceptions, write_path
from .aliases import Aliases, AliasesDefault
from .autoplaylist import AutoPlaylistManager
from .config import Config, ConfigDefaults
from .constants import (
    DATA_FILE_SERVERS,
    DATA_GUILD_FILE_CUR_SONG,
    DATA_GUILD_FILE_QUEUE,
    DEFAULT_BOT_ICON,
    DEFAULT_BOT_NAME,
    DEFAULT_FOOTER_TEXT,
    DEFAULT_I18N_DIR,
    DEFAULT_I18N_LANG,
    DEFAULT_OWNER_GROUP_NAME,
    DEFAULT_PERMS_GROUP_NAME,
    DEFAULT_PING_HTTP_URI,
    DEFAULT_PING_SLEEP,
    DEFAULT_PING_TARGET,
    DEFAULT_PING_TIMEOUT,
    DISCORD_MSG_CHAR_LIMIT,
    EMOJI_CHECK_MARK_BUTTON,
    EMOJI_CROSS_MARK_BUTTON,
    EMOJI_IDLE_ICON,
    EMOJI_NEXT_ICON,
    EMOJI_PREV_ICON,
    EMOJI_RESTART_FULL,
    EMOJI_RESTART_SOFT,
    EMOJI_STOP_SIGN,
    EMOJI_UPDATE_ALL,
    EMOJI_UPDATE_GIT,
    EMOJI_UPDATE_PIP,
    EXAMPLE_OPTIONS_FILE,
    EXAMPLE_PERMS_FILE,
    FALLBACK_PING_SLEEP,
    FALLBACK_PING_TIMEOUT,
    MUSICBOT_USER_AGENT_AIOHTTP,
    MUSICBOT_VOICE_MAX_KBITRATE,
)
from .constants import VERSION as BOTVERSION
from .constants import (
    VOICE_CLIENT_MAX_RETRY_CONNECT,
    VOICE_CLIENT_RECONNECT_TIMEOUT,
)
from .constructs import ErrorResponse, GuildSpecificData, MusicBotResponse, Response
from .entry import LocalFilePlaylistEntry, StreamPlaylistEntry, URLPlaylistEntry
from .filecache import AudioFileCache
from .i18n import _D, _L, _Dd
from .logs import muffle_discord_console_log, mute_discord_console_log
from .opus_loader import load_opus_lib
from .permissions import PermissionGroup, Permissions, PermissionsDefaults
from .player import MusicPlayer
from .playlist import Playlist
from .spotify import Spotify
from .utils import (
    _func_,
    check_extractor,
    command_helper,
    count_members_in_voice,
    dev_only,
    format_size_from_bytes,
    format_song_duration,
    format_time_to_seconds,
    is_empty_voice_channel,
    owner_only,
    slugify,
)

# optional imports
try:
    import objgraph
except ImportError:
    objgraph = None  # type: ignore[assignment]


if TYPE_CHECKING:
    from collections.abc import Coroutine
    from contextvars import Context as CtxVars

    AsyncTask = asyncio.Task[Any]
else:
    AsyncTask = asyncio.Task

# Type aliases
ExitSignals = Union[None, exceptions.RestartSignal, exceptions.TerminateSignal]
# Channels that MusicBot Can message.
MessageableChannel = Union[
    discord.VoiceChannel,
    discord.StageChannel,
    discord.TextChannel,
    discord.Thread,
    discord.DMChannel,
    discord.GroupChannel,
    discord.PartialMessageable,
]
GuildMessageableChannels = Union[
    discord.TextChannel,
    discord.Thread,
    discord.VoiceChannel,
    discord.StageChannel,
]
# Voice Channels that MusicBot Can connect to.
VoiceableChannel = Union[
    discord.VoiceChannel,
    discord.StageChannel,
]
MessageAuthor = Union[
    discord.User,
    discord.Member,
]
UserMentions = List[Union[discord.Member, discord.User]]
EntryTypes = Union[URLPlaylistEntry, StreamPlaylistEntry, LocalFilePlaylistEntry]
CommandResponse = Union[None, MusicBotResponse, Response, ErrorResponse]

log = logging.getLogger(__name__)

# Set up discord permissions needed by the bot. Used in auth/invite links.
# We could use the bitmask to save lines, but this documents which perms are needed.
# Bitmask:  4365610048
discord_bot_perms = discord.Permissions()
discord_bot_perms.change_nickname = True
discord_bot_perms.view_channel = True
discord_bot_perms.send_messages = True
discord_bot_perms.manage_messages = True
discord_bot_perms.embed_links = True
discord_bot_perms.attach_files = True
discord_bot_perms.read_message_history = True
discord_bot_perms.use_external_emojis = True
discord_bot_perms.add_reactions = True
discord_bot_perms.connect = True
discord_bot_perms.speak = True
discord_bot_perms.request_to_speak = True


# TODO:  add support for local file playback via indexed data.
#  --  Using tinytag to extract meta data from files and index it.


class MusicBot(discord.Client):
    def __init__(
        self,
        config_file: Optional[pathlib.Path] = None,
        perms_file: Optional[pathlib.Path] = None,
        aliases_file: Optional[pathlib.Path] = None,
        use_certifi: bool = False,
    ) -> None:
        log.info("Initializing MusicBot %s", BOTVERSION)
        load_opus_lib()

        if config_file is None:
            self._config_file = ConfigDefaults.options_file
        else:
            self._config_file = config_file

        if perms_file is None:
            self._perms_file = PermissionsDefaults.perms_file
        else:
            self._perms_file = perms_file

        if aliases_file is None:
            aliases_file = AliasesDefault.aliases_file

        self.use_certifi: bool = use_certifi
        self.exit_signal: ExitSignals = None
        self._init_time: float = time.time()
        self._os_signal: Optional[signal.Signals] = None
        self._ping_peer_addr: str = ""
        self._ping_use_http: bool = False
        self.network_outage: bool = False
        self.on_ready_count: int = 0
        self.init_ok: bool = False
        self.logout_called: bool = False
        self.cached_app_info: Optional[discord.AppInfo] = None
        self.last_status: Optional[discord.BaseActivity] = None
        self.players: Dict[int, MusicPlayer] = {}
        self.task_pool: Set[AsyncTask] = set()

        try:
            self.config = Config(self._config_file)
        except exceptions.RetryConfigException:
            self.config = Config(self._config_file)

        self.permissions = Permissions(self._perms_file)
        # Set the owner ID in case it wasn't auto...
        self.permissions.set_owner_id(self.config.owner_id)

        if self.config.usealias:
            # get a list of natural command names.
            nat_cmds = [
                x.replace("cmd_", "") for x in dir(self) if x.startswith("cmd_")
            ]
            # load the aliases file.
            self.aliases = Aliases(aliases_file, nat_cmds)

        self.playlist_mgr = AutoPlaylistManager(self)

        self.aiolocks: DefaultDict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.filecache = AudioFileCache(self)
        self.downloader = downloader.Downloader(self)

        # Factory function for server specific data objects.
        def server_factory() -> GuildSpecificData:
            return GuildSpecificData(self)

        # defaultdict lets us on-demand create GuildSpecificData.
        self.server_data: DefaultDict[int, GuildSpecificData] = defaultdict(
            server_factory
        )

        self.spotify: Optional[Spotify] = None
        self.session: Optional[aiohttp.ClientSession] = None

        intents = discord.Intents.all()
        intents.typing = False
        intents.presences = False
        super().__init__(intents=intents)

    def create_task(
        self,
        coro: "Coroutine[Any, Any, Any]",
        *,
        name: Optional[str] = None,
        ctx: Optional["CtxVars"] = None,
    ) -> None:
        """
        Same as asyncio.create_task() but manages the task reference.
        This prevents garbage collection of tasks until they are finished.
        """
        if not self.loop:
            log.error("Loop is closed, cannot create task for: %r", coro)
            return

        # context was not added until python 3.11
        if sys.version_info >= (3, 11):
            t = self.loop.create_task(coro, name=name, context=ctx)
        else:  # assume 3.9+
            t = self.loop.create_task(coro, name=name)
        self.task_pool.add(t)

        def discard_task(task: AsyncTask) -> None:
            """Clean up the spawned task and handle its exceptions."""
            ex = task.exception()
            if ex:
                if log.getEffectiveLevel() <= logging.DEBUG:
                    log.exception(
                        "Unhandled exception for task:  %r", task, exc_info=ex
                    )
                else:
                    log.error(
                        "Unhandled exception for task:  %(task)r  --  %(raw_error)s",
                        {"task": task, "raw_error": str(ex)},
                    )

            self.task_pool.discard(task)

        t.add_done_callback(discard_task)

    async def setup_hook(self) -> None:
        """async init phase that is called by d.py before login."""
        if self.config.enable_queue_history_global:
            await self.playlist_mgr.global_history.load()

        # TODO: testing is needed to see if this would be required.
        # See also:  https://github.com/aio-libs/aiohttp/discussions/6044
        # aiohttp version must be at least 3.8.0 for the following to potentially work.
        # Python 3.11+ might also be a requirement if CPython does not support start_tls.
        # setattr(asyncio.sslproto._SSLProtocolTransport, "_start_tls_compatible", True)

        self.http.user_agent = MUSICBOT_USER_AGENT_AIOHTTP
        if self.use_certifi:
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            tcp_connector = aiohttp.TCPConnector(ssl_context=ssl_ctx)

            # Patches discord.py HTTPClient.
            self.http.connector = tcp_connector

            self.session = aiohttp.ClientSession(
                headers={"User-Agent": self.http.user_agent},
                connector=tcp_connector,
            )
        else:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": self.http.user_agent}
            )

        if self.config.spotify_enabled:
            try:
                self.spotify = Spotify(
                    self.config.spotify_clientid,
                    self.config.spotify_clientsecret,
                    aiosession=self.session,
                    loop=self.loop,
                )
                if not await self.spotify.has_token():
                    log.warning("Spotify did not provide us with a token. Disabling.")
                    self.config.spotify_enabled = False
                else:
                    log.info(
                        "Authenticated with Spotify successfully using client ID and secret."
                    )
            except exceptions.SpotifyError as e:
                log.warning(
                    "Could not start Spotify client. Is your client ID and secret correct? Details: %s. Continuing anyway in 5 seconds...",
                    e.message % e.fmt_args,
                )
                self.config.spotify_enabled = False
                time.sleep(5)  # make sure they see the problem
        else:
            try:
                log.warning(
                    "The config did not have Spotify app credentials, attempting to use guest mode."
                )
                self.spotify = Spotify(
                    None, None, aiosession=self.session, loop=self.loop
                )
                if not await self.spotify.has_token():
                    log.warning("Spotify did not provide us with a token. Disabling.")
                    self.config.spotify_enabled = False
                else:
                    log.info(
                        "Authenticated with Spotify successfully using guest mode."
                    )
                    self.config.spotify_enabled = True
            except exceptions.SpotifyError as e:
                log.warning(
                    "Could not start Spotify client using guest mode. Details: %s.",
                    e.message % e.fmt_args,
                )
                self.config.spotify_enabled = False

        log.info("Initialized, now connecting to discord.")
        # this creates an output similar to a progress indicator.
        muffle_discord_console_log()
        self.create_task(self._test_network(), name="MB_PingTest")

    async def _test_network(self) -> None:
        """
        A self looping method that tests network connectivity.
        This will call to the systems ping command and use its return status.
        """
        if not self.config.enable_network_checker:
            log.debug("Network ping test is disabled via config.")
            return

        if self.logout_called:
            log.noise("Network ping test is closing down.")  # type: ignore[attr-defined]
            return

        # Resolve the given target to speed up pings.
        ping_target = self._ping_peer_addr
        if not self._ping_peer_addr:
            try:
                ai = socket.getaddrinfo(DEFAULT_PING_TARGET, 80)
                self._ping_peer_addr = ai[0][4][0]
                ping_target = self._ping_peer_addr
            except OSError:
                log.warning("Could not resolve ping target.")
                ping_target = DEFAULT_PING_TARGET

        # Make a ping test using sys ping command or http request.
        if self._ping_use_http:
            ping_status = await self._test_network_via_http(ping_target)
        else:
            ping_status = await self._test_network_via_ping(ping_target)
            if self._ping_use_http:
                ping_status = await self._test_network_via_http(ping_target)

        # Ping success, network up.
        if ping_status == 0:
            if self.network_outage:
                self.on_network_up()
            self.network_outage = False

        # Ping failed, network down.
        else:
            if not self.network_outage:
                self.on_network_down()
            self.network_outage = True

        # Sleep before next ping.
        try:
            if not self._ping_use_http:
                await asyncio.sleep(DEFAULT_PING_SLEEP)
            else:
                await asyncio.sleep(FALLBACK_PING_SLEEP)
        except asyncio.exceptions.CancelledError:
            log.noise("Network ping test cancelled.")  # type: ignore[attr-defined]
            return

        # set up the next ping task if possible.
        if not self.logout_called:
            self.create_task(self._test_network(), name="MB_PingTest")

    async def _test_network_via_http(self, ping_target: str) -> int:
        """
        This method is used as a fall-back if system ping commands are not available.
        It will make use of current aiohttp session to make a HEAD request for the
        given `ping_target` and a file defined by DEFAULT_PING_HTTP_URI.
        """
        if not self.session:
            log.warning("Network testing via HTTP does not have a session to borrow.")
            # As we cannot test it, assume network is up.
            return 0

        try:
            ping_host = f"http://{ping_target}{DEFAULT_PING_HTTP_URI}"
            async with self.session.head(
                ping_host,
                timeout=FALLBACK_PING_TIMEOUT,  # type: ignore[arg-type,unused-ignore]
            ):
                return 0
        except (aiohttp.ClientError, asyncio.exceptions.TimeoutError, OSError):
            return 1

    async def _test_network_via_ping(self, ping_target: str) -> int:
        """
        This method constructs a ping command to use as a system call.
        If ping cannot be found or is not permitted, the fall-back flag
        will be set by this function, and subsequent ping tests will use
        HTTP ping testing method instead.
        """
        # Make a ping call based on OS.
        if not hasattr(self, "_mb_ping_exe_path"):
            ping_path = shutil.which("ping")
            if not ping_path:
                log.warning("Could not locate `ping` executable in your environment.")
                ping_path = "ping"
            setattr(self, "_mb_ping_exe_path", ping_path)
        else:
            ping_path = getattr(self, "_mb_ping_exe_path", "ping")

        ping_cmd: List[str] = []
        if os.name == "nt":
            # Windows ping -w uses milliseconds.
            t = 1000 * DEFAULT_PING_TIMEOUT
            ping_cmd = [ping_path, "-n", "1", "-w", str(t), ping_target]
        else:
            t = DEFAULT_PING_TIMEOUT
            ping_cmd = [ping_path, "-c", "1", "-w", str(t), ping_target]

        # execute the ping command.
        try:
            p = await asyncio.create_subprocess_exec(
                ping_cmd[0],
                *ping_cmd[1:],
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            ping_status = await p.wait()
        except FileNotFoundError:
            log.error(
                "MusicBot could not locate a `ping` command path.  Will attempt to use HTTP ping instead."
                "\nMusicBot tried the following command:   %s"
                "\nYou should enable ping in your system or container environment for best results."
                "\nAlternatively disable network checking via config.",
                " ".join(ping_cmd),
            )
            self._ping_use_http = True
            return 1
        except PermissionError:
            log.error(
                "MusicBot was denied permission to execute the `ping` command.  Will attempt to use HTTP ping instead."
                "\nMusicBot tried the following command:   %s"
                "\nYou should enable ping in your system or container environment for best results."
                "\nAlternatively disable network checking via config.",
                " ".join(ping_cmd),
            )
            self._ping_use_http = True
            return 1
        except OSError:
            log.error(
                "Your environment may not allow the `ping` system command.  Will attempt to use HTTP ping instead."
                "\nMusicBot tried the following command:   %s"
                "\nYou should enable ping in your system or container environment for best results."
                "\nAlternatively disable network checking via config.",
                " ".join(ping_cmd),
                exc_info=self.config.debug_mode,
            )
            self._ping_use_http = True
            return 1
        return ping_status

    def on_network_up(self) -> None:
        """
        Event called by MusicBot when it detects network returned from outage.
        """
        log.info("MusicBot detected network is available again.")
        for gid, player in self.players.items():
            if player.is_paused and not player.paused_auto:
                if not player.voice_client.is_connected():
                    log.warning(
                        "VoiceClient is not connected, waiting to resume MusicPlayer..."
                    )
                    continue
                log.info(
                    "Resuming playback of player:  (%(guild_id)s) %(player)r",
                    {"guild_id": gid, "player": player},
                )
                player.guild_or_net_unavailable = False
                player.resume()
            player.guild_or_net_unavailable = False

    def on_network_down(self) -> None:
        """
        Event called by MusicBot when it detects network outage.
        """
        log.info("MusicBot detected a network outage.")
        for gid, player in self.players.items():
            if player.is_playing:
                log.info(
                    "Pausing MusicPlayer due to network availability:  (%(guild_id)s) %(player)r",
                    {"guild_id": gid, "player": player},
                )
                player.pause()
            player.guild_or_net_unavailable = True

    def _get_owner_member(
        self, *, server: Optional[discord.Guild] = None, voice: bool = False
    ) -> Optional[discord.Member]:
        """
        Get the discord Member object that has a user ID which matches
        the configured OwnerID.

        :param: server:  The discord Guild in which to expect the member.
        :param: voice:  Require the owner to be in a voice channel.
        """
        owner = discord.utils.find(
            lambda m: m.id == self.config.owner_id and (m.voice if voice else True),
            server.members if server else self.get_all_members(),
        )
        log.noise(  # type: ignore[attr-defined]
            "Looking for owner in guild: %(guild)s (required voice: %(required)s) and got:  %(owner)s",
            {"guild": server, "required": voice, "owner": owner},
        )
        return owner

    async def _auto_join_channels(
        self,
        from_resume: bool = False,
    ) -> None:
        """
        Attempt to join voice channels that have been configured in options.
        Also checks for existing voice sessions and attempts to resume them.
        If self.on_ready_count is 0, it will also run owner auto-summon logic.
        """
        log.info("Checking for channels to auto-join or resume...")
        channel_map: Dict[discord.Guild, VoiceableChannel] = {}

        # Check guilds for a resumable channel, conditionally override with owner summon.
        resuming = False
        for guild in self.guilds:
            auto_join_ch = self.server_data[guild.id].auto_join_channel
            if auto_join_ch:
                channel_map[guild] = auto_join_ch

            if guild.unavailable:
                log.warning(
                    "Guild not available, cannot auto join:  %(id)s/%(name)s",
                    {"id": guild.id, "name": guild.name},
                )
                continue

            # Check for a resumable channel.
            if guild.me.voice and guild.me.voice.channel:
                log.info(
                    "Found resumable voice channel:  %(channel)s  in guild:  %(guild)s",
                    {
                        "channel": guild.me.voice.channel.name,
                        "guild": guild.name,
                    },
                )

                # override an existing auto-join if bot was previously in a different channel.
                if (
                    guild in channel_map
                    and guild.me.voice.channel != channel_map[guild]
                ):
                    log.info(
                        "Will try resuming voice session instead of Auto-Joining channel:  %s",
                        channel_map[guild].name,
                    )
                channel_map[guild] = guild.me.voice.channel
                resuming = True

            # Check for follow-user mode on resume.
            follow_user = self.server_data[guild.id].follow_user
            if from_resume and follow_user:
                if follow_user.voice and follow_user.voice.channel:
                    channel_map[guild] = follow_user.voice.channel

            # Check if we should auto-summon to the owner, but only on startup.
            if self.config.auto_summon and not from_resume:
                owner = self._get_owner_member(server=guild, voice=True)
                if owner and owner.voice and owner.voice.channel:
                    log.info(
                        "Found owner in voice channel:  %s", owner.voice.channel.name
                    )
                    if guild in channel_map:
                        if resuming:
                            log.info(
                                "Ignoring resumable channel, AutoSummon to owner in channel:  %s",
                                owner.voice.channel.name,
                            )
                        else:
                            log.info(
                                "Ignoring Auto-Join channel, AutoSummon to owner in channel:  %s",
                                owner.voice.channel.name,
                            )
                    channel_map[guild] = owner.voice.channel

        for guild, channel in channel_map.items():

            if (
                isinstance(guild.voice_client, discord.VoiceClient)
                and guild.voice_client.is_connected()
            ):
                log.info(
                    "Already connected to channel:  %(channel)s  in guild:  %(guild)s",
                    {"channel": guild.voice_client.channel.name, "guild": guild.name},
                )
                continue

            if channel and isinstance(
                channel, (discord.VoiceChannel, discord.StageChannel)
            ):
                log.info(
                    "Attempting to join channel:  %(channel)s  in guild:  %(guild)s",
                    {"channel": channel.name, "guild": channel.guild},
                )

                player = self.get_player_in(guild)

                if player:
                    log.info("Discarding MusicPlayer and making a new one...")
                    await self.disconnect_voice_client(guild)

                    try:
                        player = await self.get_player(
                            channel,
                            create=True,
                            deserialize=self.config.persistent_queue,
                        )

                        if player.is_stopped and len(player.playlist) > 0:
                            player.play()

                        if self.config.auto_playlist and len(player.playlist) == 0:
                            await self.on_player_finished_playing(player)

                    except (TypeError, exceptions.PermissionsError):
                        continue

                else:
                    log.debug("MusicBot will make a new MusicPlayer now...")
                    try:
                        player = await self.get_player(
                            channel,
                            create=True,
                            deserialize=self.config.persistent_queue,
                        )

                        if player.is_stopped and len(player.playlist) > 0:
                            player.play()

                        if self.config.auto_playlist and len(player.playlist) == 0:
                            await self.on_player_finished_playing(player)

                    except (TypeError, exceptions.PermissionsError):
                        continue

            if channel and not isinstance(
                channel, (discord.VoiceChannel, discord.StageChannel)
            ):
                log.warning(
                    "Not joining %(guild)s/%(channel)s, it isn't a supported voice channel.",
                    {"guild": channel.guild.name, "channel": channel.name},
                )
        log.info("Finished joining configured channels.")

        # Rough estimate for bandwidth use based on Max kbps & number of guilds.
        bw_usage: float = len(self.guilds) * MUSICBOT_VOICE_MAX_KBITRATE
        suffix = "kbps"
        if bw_usage > 1000:
            suffix = "mbps"
            bw_usage /= 1000
        log.info(
            "MusicBot may use up to %(rate).2f %(suffix)s of bandwidth.",
            {"rate": bw_usage, "suffix": suffix},
        )

    async def _check_ignore_non_voice(self, msg: discord.Message) -> bool:
        """Check used by on_message to determine if caller is in a VoiceChannel."""
        if msg.guild and msg.guild.me.voice:
            vc = msg.guild.me.voice.channel
        else:
            vc = None

        # Webhooks can't be voice members. discord.User has no .voice attribute.
        if isinstance(msg.author, discord.User):
            raise exceptions.CommandError(
                "Member is not voice-enabled and cannot use this command.",
            )

        # If we've connected to a voice chat and we're in the same voice channel
        if not vc or (msg.author.voice and vc == msg.author.voice.channel):
            return True

        raise exceptions.PermissionsError(
            "You cannot use this command when not in the voice channel.",
        )

    async def generate_invite_link(
        self,
        *,
        permissions: discord.Permissions = discord_bot_perms,
        guild: discord.Guild = discord.utils.MISSING,
    ) -> str:
        """
        Fetch Application Info from discord and generate an OAuth invite
        URL for MusicBot.
        """
        if not self.cached_app_info:
            log.debug("Getting bot Application Info.")
            self.cached_app_info = await self.application_info()

        return discord.utils.oauth_url(
            self.cached_app_info.id, permissions=permissions, guild=guild
        )

    async def get_voice_client(self, channel: VoiceableChannel) -> discord.VoiceClient:
        """
        Use the given `channel` either return an existing VoiceClient or
        create a new VoiceClient by connecting to the `channel` object.

        :raises: TypeError
            If `channel` is not a discord.VoiceChannel or discord.StageChannel

        :raises: musicbot.exceptions.PermissionsError
            If MusicBot does not have permissions required to join or speak in the `channel`.
        """
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            raise TypeError("[BUG] Channel passed must be a voice channel")

        # Check if MusicBot has required permissions to join in channel.
        chperms = channel.permissions_for(channel.guild.me)
        if not chperms.connect:
            log.error(
                "MusicBot does not have permission to Connect in channel:  %s",
                channel.name,
            )
            raise exceptions.PermissionsError(
                "MusicBot does not have permission to Connect in channel:  `%(name)s`",
                fmt_args={"name": channel.name},
            )
        if not chperms.speak:
            log.error(
                "MusicBot does not have permission to Speak in channel:  %s",
                channel.name,
            )
            raise exceptions.PermissionsError(
                "MusicBot does not have permission to Speak in channel:  `%(name)s`",
                fmt_args={"name": channel.name},
            )

        # check for and return bots VoiceClient if we already have one.
        vc = channel.guild.voice_client
        if vc and isinstance(vc, (discord.VoiceClient, discord.StageChannel)):
            # make sure it is usable
            if vc.is_connected():
                log.voicedebug(  # type: ignore[attr-defined]
                    "Reusing bots VoiceClient from guild:  %s", channel.guild
                )
                return vc
            # or otherwise we kill it and start fresh.
            log.voicedebug(  # type: ignore[attr-defined]
                "Forcing disconnect on stale VoiceClient in guild:  %s", channel.guild
            )
            try:
                await vc.disconnect()
            except (asyncio.exceptions.CancelledError, asyncio.exceptions.TimeoutError):
                if self.config.debug_mode:
                    log.warning("Disconnect failed or was cancelled?")

        # Otherwise we need to connect to the given channel.
        max_timeout = VOICE_CLIENT_RECONNECT_TIMEOUT * VOICE_CLIENT_MAX_RETRY_CONNECT
        for attempt in range(1, (VOICE_CLIENT_MAX_RETRY_CONNECT + 1)):
            timeout = attempt * VOICE_CLIENT_RECONNECT_TIMEOUT
            if timeout > max_timeout:
                log.critical(
                    "MusicBot is unable to connect to the channel right now:  %(channel)s",
                    {"channel": channel},
                )
                raise exceptions.CommandError(
                    "MusicBot could not connect to the channel.\n"
                    "Try again later, or restart the bot if this continues."
                )

            try:
                client: discord.VoiceClient = await channel.connect(
                    timeout=timeout,
                    reconnect=True,
                    self_deaf=self.config.self_deafen,
                )
                log.voicedebug(  # type: ignore[attr-defined]
                    "MusicBot has a VoiceClient now..."
                )
                break
            except asyncio.exceptions.TimeoutError:
                log.warning(
                    "Retrying connection after a timeout error (%(attempt)s) while trying to connect to:  %(channel)s",
                    {"attempt": attempt, "channel": channel},
                )
            except asyncio.exceptions.CancelledError as e:
                log.exception(
                    "MusicBot VoiceClient connection attempt was cancelled. No retry."
                )
                raise exceptions.CommandError(
                    "MusicBot connection to voice was cancelled. This is odd. Maybe restart?"
                ) from e

        # request speaker automatically in stage channels.
        if isinstance(channel, discord.StageChannel):
            try:
                log.info("MusicBot is requesting to speak in channel: %s", channel.name)
                # this has the same effect as edit(suppress=False)
                await channel.guild.me.request_to_speak()
            except discord.Forbidden as e:
                raise exceptions.PermissionsError(
                    "MusicBot does not have permission to speak."
                ) from e
            except (discord.HTTPException, discord.ClientException) as e:
                raise exceptions.MusicbotException(
                    "MusicBot could not request to speak."
                ) from e

        return client

    async def disconnect_voice_client(self, guild: discord.Guild) -> None:
        """
        Check for a MusicPlayer in the given `guild` and close it's VoiceClient
        gracefully then remove the MusicPlayer instance and reset any timers on
        the guild for player/channel inactivity.
        """

        if guild.id in self.players:
            log.info("Disconnecting a MusicPlayer in guild:  %s", guild)
            player = self.players.pop(guild.id)

            await self.reset_player_inactivity(player)

            # reset channel inactivity.
            if self.config.leave_inactive_channel:
                event = self.server_data[guild.id].get_event("inactive_vc_timer")
                if event.is_active() and not event.is_set():
                    event.set()

            if player.voice_client:
                log.debug("Disconnecting VoiceClient before we kill the MusicPlayer.")
                try:
                    await player.voice_client.disconnect()
                except (
                    asyncio.exceptions.CancelledError,
                    asyncio.exceptions.TimeoutError,
                ):
                    if self.config.debug_mode:
                        log.warning("The disconnect failed or was cancelled.")

            # ensure the player is dead and gone.
            player.kill()
            del player

        # Double check for voice objects.
        for vc in self.voice_clients:
            if not isinstance(vc, discord.VoiceClient):
                log.debug(
                    "MusicBot has a VoiceProtocol that is not a VoiceClient. Disconnecting anyway..."
                )
                try:
                    await vc.disconnect(force=True)
                except (
                    asyncio.exceptions.CancelledError,
                    asyncio.exceptions.TimeoutError,
                ):
                    if self.config.debug_mode:
                        log.warning("The disconnect failed or was cancelled.")
                continue

            if vc.guild and vc.guild == guild:
                log.debug("Disconnecting a rogue VoiceClient in guild:  %s", guild)
                try:
                    await vc.disconnect()
                except (
                    asyncio.exceptions.CancelledError,
                    asyncio.exceptions.TimeoutError,
                ):
                    if self.config.debug_mode:
                        log.warning("The disconnect failed or was cancelled.")

        await self.update_now_playing_status()

    async def disconnect_all_voice_clients(self) -> None:
        """
        Loop over all references that may have a VoiceClient and ensure they are
        closed and disposed of in the case of MusicPlayer.
        """
        # Disconnect from all guilds.
        for guild in self.guilds:
            await self.disconnect_voice_client(guild)

        # Double check for detached voice clients.
        for vc in self.voice_clients:
            if isinstance(vc, discord.VoiceClient):
                log.warning("Disconnecting a non-guild VoiceClient...")
                try:
                    await vc.disconnect()
                except (
                    asyncio.exceptions.CancelledError,
                    asyncio.exceptions.TimeoutError,
                ):
                    log.warning("The disconnect failed or was cancelled.")
            else:
                log.warning(
                    "MusicBot.voice_clients list contains a non-VoiceClient object?\n"
                    "The object is actually of type:  %s",
                    type(vc),
                )

        # Triple check we don't have rogue players.  This would be a bug.
        player_gids = list(self.players.keys())
        for gid in player_gids:
            player = self.players[gid]
            log.warning(
                "We still have a MusicPlayer ref in guild (%(guild_id)s):  %(player)r",
                {"guild_id": gid, "player": player},
            )
            del self.players[gid]

    def get_player_in(self, guild: discord.Guild) -> Optional[MusicPlayer]:
        """
        Get a MusicPlayer in the given guild, but do not create a new player.
        MusicPlayer returned from this method may not be connected to a voice channel!
        """
        p = self.players.get(guild.id)
        if log.getEffectiveLevel() <= logging.EVERYTHING:  # type: ignore[attr-defined]
            log.voicedebug(  # type: ignore[attr-defined]
                "Guild (%(guild)s) wants a player, optional:  %(player)r",
                {"guild": guild, "player": p},
            )

        if log.getEffectiveLevel() <= logging.VOICEDEBUG:  # type: ignore[attr-defined]
            if p and not p.voice_client:
                log.error(
                    "[BUG] MusicPlayer is missing a VoiceClient somehow.  You should probably restart the bot."
                )
            if p and p.voice_client and not p.voice_client.is_connected():
                # This is normal if the bot is still connecting to voice, or
                # if the player has been pointedly disconnected.
                log.warning("MusicPlayer has a VoiceClient that is not connected.")
                log.noise("MusicPlayer obj:  %r", p)  # type: ignore[attr-defined]
                log.noise("VoiceClient obj:  %r", p.voice_client)  # type: ignore[attr-defined]
        return p

    async def get_player(
        self,
        channel: VoiceableChannel,
        create: bool = False,
        deserialize: bool = False,
    ) -> MusicPlayer:
        """
        Get a MusicPlayer in the given guild, creating or deserializing one if needed.

        :raises:  TypeError
            If given `channel` is not a discord.VoiceChannel or discord.StageChannel
        :raises:  musicbot.exceptions.PermissionsError
            If MusicBot is not permitted to join the given `channel`.
        """
        guild = channel.guild

        log.voicedebug(  # type: ignore[attr-defined]
            "Getting a MusicPlayer for guild:  %(guild)s  In Channel:  %(channel)s  Create: %(create)s  Deserialize:  %(serial)s",
            {
                "guild": guild,
                "channel": channel,
                "create": create,
                "serial": deserialize,
            },
        )

        async with self.aiolocks[_func_() + ":" + str(guild.id)]:
            if deserialize:
                voice_client = await self.get_voice_client(channel)
                player = await self.deserialize_queue(guild, voice_client)

                if player:
                    log.voicedebug(  # type: ignore[attr-defined]
                        "Created player via deserialization for guild %(guild_id)s with %(number)s entries",
                        {"guild_id": guild.id, "number": len(player.playlist)},
                    )
                    # Since deserializing only happens when the bot starts, I should never need to reconnect
                    return self._init_player(player, guild=guild)

            if guild.id not in self.players:
                if not create:
                    raise exceptions.CommandError(
                        "The bot is not in a voice channel.\n"
                        "Use the summon command to bring the bot to your voice channel."
                    )

                voice_client = await self.get_voice_client(channel)

                if isinstance(voice_client, discord.VoiceClient):
                    playlist = Playlist(self)
                    player = MusicPlayer(self, voice_client, playlist)
                    self._init_player(player, guild=guild)
                else:
                    raise exceptions.MusicbotException(
                        "Something is wrong, we didn't get the VoiceClient."
                    )

        return self.players[guild.id]

    def _init_player(
        self, player: MusicPlayer, *, guild: Optional[discord.Guild] = None
    ) -> MusicPlayer:
        """
        Connect a brand-new MusicPlayer instance with the MusicBot event
        handler functions, and store the player reference for reuse.

        :returns: The player with it's event connections.
        """
        player = (
            player.on("play", self.on_player_play)
            .on("resume", self.on_player_resume)
            .on("pause", self.on_player_pause)
            .on("stop", self.on_player_stop)
            .on("finished-playing", self.on_player_finished_playing)
            .on("entry-added", self.on_player_entry_added)
            .on("error", self.on_player_error)
        )

        if guild:
            self.players[guild.id] = player

        return player

    async def on_player_play(self, player: MusicPlayer, entry: EntryTypes) -> None:
        """
        Event called by MusicPlayer when playback of an entry is started.
        """
        log.debug("Running on_player_play")
        ssd_ = self.server_data[player.voice_client.channel.guild.id]
        await self._handle_guild_auto_pause(player)
        await self.reset_player_inactivity(player)
        await self.update_now_playing_status()
        # manage the cache since we may have downloaded something.
        if isinstance(entry, URLPlaylistEntry):
            self.filecache.handle_new_cache_entry(entry)
        player.skip_state.reset()

        await self.serialize_queue(player.voice_client.channel.guild)

        if self.config.write_current_song:
            await self.write_current_song(player.voice_client.channel.guild, entry)

        if entry.channel and entry.author:
            author_perms = self.permissions.for_user(entry.author)

            if (
                entry.author not in player.voice_client.channel.members
                and author_perms.skip_when_absent
            ):
                newmsg = _D(
                    "Skipping next song `%(title)s` as requester `%(user)s` is not in voice!",
                    ssd_,
                ) % {
                    "title": _D(entry.title, ssd_),
                    "author": entry.author.name,
                }

                # handle history playlist updates.
                guild = player.voice_client.guild
                if (
                    self.config.enable_queue_history_global
                    or self.config.enable_queue_history_guilds
                ):
                    self.server_data[guild.id].current_playing_url = ""

                player.skip()
            elif self.config.now_playing_mentions:
                newmsg = _D(
                    "%(mention)s - your song `%(title)s` is now playing in %(channel)s!",
                    ssd_,
                ) % {
                    "mention": entry.author.mention,
                    "title": _D(entry.title, ssd_),
                    "channel": player.voice_client.channel.name,
                }
            else:
                newmsg = _D(
                    "Now playing in %(channel)s: `%(title)s` added by %(author)s!",
                    ssd_,
                ) % {
                    "channel": player.voice_client.channel.name,
                    "title": _D(entry.title, ssd_),
                    "author": entry.author.name,
                }

        else:
            # no author (and channel), it's an auto playlist entry.
            newmsg = _D(
                "Now playing automatically added entry `%(title)s` in %(channel)s!",
                ssd_,
            ) % {
                "title": _D(entry.title, ssd_),
                "channel": player.voice_client.channel.name,
            }

        # handle history playlist updates.
        guild = player.voice_client.guild
        if (
            self.config.enable_queue_history_global
            or self.config.enable_queue_history_guilds
        ) and not entry.from_auto_playlist:
            log.debug(
                "Setting URL history guild %(guild_id)s == %(url)s",
                {"guild_id": guild.id, "url": entry.url},
            )
            self.server_data[guild.id].current_playing_url = entry.url

        last_np_msg = self.server_data[guild.id].last_np_msg
        np_channel: Optional[MessageableChannel] = None
        if newmsg:
            if self.config.dm_nowplaying and entry.author:
                await self.safe_send_message(entry.author, Response(newmsg))
                return

            if self.config.no_nowplaying_auto and entry.from_auto_playlist:
                return

            if self.config.nowplaying_channels:
                for potential_channel_id in self.config.nowplaying_channels:
                    potential_channel = self.get_channel(potential_channel_id)
                    if isinstance(potential_channel, discord.abc.PrivateChannel):
                        continue

                    if not isinstance(potential_channel, discord.abc.Messageable):
                        continue

                    if potential_channel and potential_channel.guild == guild:
                        np_channel = potential_channel
                        break

            if not np_channel and last_np_msg:
                np_channel = last_np_msg.channel

        content = Response("")
        if entry.thumbnail_url:
            content.set_image(url=entry.thumbnail_url)
        else:
            log.warning(
                "No thumbnail set for entry with URL: %s",
                entry.url,
            )

        if self.config.now_playing_mentions:
            content.title = None
            content.add_field(name="\n", value=newmsg, inline=True)
        else:
            content.title = newmsg

        # send it in specified channel
        if not np_channel:
            log.debug("no channel to put now playing message into")
            return

        # Don't send the same now-playing message more than once.
        # This prevents repeated messages when players reconnect.
        last_subject = self.server_data[guild.id].last_played_song_subject
        if (
            last_np_msg is not None
            and player.current_entry is not None
            and last_subject
            and last_subject == player.current_entry.url
        ):
            log.debug("ignored now-playing message as it was already posted.")
            return

        if player.current_entry:
            self.server_data[guild.id].last_played_song_subject = (
                player.current_entry.url
            )

        self.server_data[guild.id].last_np_msg = await self.safe_send_message(
            np_channel,
            content,
        )

        # TODO: Check channel voice state?

    async def on_player_resume(
        self,
        player: MusicPlayer,
        entry: EntryTypes,  # pylint: disable=unused-argument
        **_: Any,
    ) -> None:
        """
        Event called by MusicPlayer when the player is resumed from pause.
        """
        log.debug("Running on_player_resume")
        await self.reset_player_inactivity(player)
        await self.update_now_playing_status()

    async def on_player_pause(
        self,
        player: MusicPlayer,
        entry: EntryTypes,  # pylint: disable=unused-argument
        **_: Any,
    ) -> None:
        """
        Event called by MusicPlayer when the player enters paused state.
        """
        log.debug("Running on_player_pause")
        await self.update_now_playing_status()

        # save current entry progress, if it played "enough" to merit saving.
        if player.session_progress > 1:
            await self.serialize_queue(player.voice_client.channel.guild)

        self.create_task(
            self.handle_player_inactivity(player), name="MB_HandleInactivePlayer"
        )

    async def on_player_stop(self, player: MusicPlayer, **_: Any) -> None:
        """
        Event called by MusicPlayer any time the player is stopped.
        Typically after queue is empty or an error stopped playback.
        """
        log.debug("Running on_player_stop")
        await self.update_now_playing_status()
        self.create_task(
            self.handle_player_inactivity(player), name="MB_HandleInactivePlayer"
        )

    async def on_player_finished_playing(self, player: MusicPlayer, **_: Any) -> None:
        """
        Event called by MusicPlayer when playback has finished without error.
        """
        log.debug("Running on_player_finished_playing")
        if not self.loop or (self.loop and self.loop.is_closed()):
            log.debug("Event loop is closed, nothing else to do here.")
            return

        if self.logout_called:
            log.debug("Logout under way, ignoring this event.")
            return

        # handle history playlist updates.
        guild = player.voice_client.guild
        last_played_url = self.server_data[guild.id].current_playing_url
        if self.config.enable_queue_history_global and last_played_url:
            await self.playlist_mgr.global_history.add_track(last_played_url)

        if self.config.enable_queue_history_guilds and last_played_url:
            history = await self.server_data[guild.id].get_played_history()
            if history is not None:
                await history.add_track(last_played_url)
        self.server_data[guild.id].current_playing_url = ""

        if not player.voice_client.is_connected():
            log.debug(
                "VoiceClient says it is not connected, nothing else we can do here."
            )
            return

        if self.config.leave_after_queue_empty:
            guild = player.voice_client.guild
            if len(player.playlist.entries) == 0:
                log.info("Player finished and queue is empty, leaving voice channel...")
                await self.disconnect_voice_client(guild)

        # delete last_np_msg somewhere if we have cached it
        if self.config.delete_nowplaying:
            guild = player.voice_client.guild
            last_np_msg = self.server_data[guild.id].last_np_msg
            if last_np_msg:
                await self.safe_delete_message(last_np_msg)

        # avoid downloading the next entries if the user is absent and we are configured to skip.
        notice_sent = False  # set a flag to avoid message spam.
        while len(player.playlist):
            log.everything(  # type: ignore[attr-defined]
                "Looping over queue to expunge songs with missing author..."
            )

            if not self.loop or (self.loop and self.loop.is_closed()):
                log.debug("Event loop is closed, nothing else to do here.")
                return

            if self.logout_called:
                log.debug("Logout under way, ignoring this event.")
                return

            next_entry = player.playlist.peek()

            if not next_entry:
                break

            channel = next_entry.channel
            author = next_entry.author

            if not channel or not author:
                break

            author_perms = self.permissions.for_user(author)
            if (
                author not in player.voice_client.channel.members
                and author_perms.skip_when_absent
            ):
                if not notice_sent:
                    res = Response(
                        _D(
                            "Skipping songs added by %(user)s as they are not in voice!",
                            self.server_data[guild.id],
                        )
                        % {"user": author.name},
                    )
                    await self.safe_send_message(channel, res)
                    notice_sent = True
                deleted_entry = player.playlist.delete_entry_at_index(0)
                log.noise(  # type: ignore[attr-defined]
                    "Author `%(user)s` absent, skipped (deleted) entry from queue:  %(song)s",
                    {"user": author.name, "song": deleted_entry.title},
                )
            else:
                break

        # manage auto playlist playback.
        if (
            not player.playlist.entries
            and not player.current_entry
            and self.config.auto_playlist
        ):
            # NOTE:  self.server_data[].autoplaylist will only contain links loaded from the file.
            #  while player.autoplaylist may contain links expanded from playlists.
            #  the only issue is that links from a playlist might fail and fire
            #  remove event, but no link will be removed since none will match.
            if not player.autoplaylist:
                if not self.server_data[guild.id].autoplaylist:
                    log.warning(
                        "No playable songs in the Guild autoplaylist, disabling."
                    )
                    self.config.auto_playlist = False
                else:
                    log.debug(
                        "No content in current autoplaylist. Filling with new music..."
                    )
                    player.autoplaylist = list(
                        self.server_data[player.voice_client.guild.id].autoplaylist
                    )

            while player.autoplaylist:
                log.everything(  # type: ignore[attr-defined]
                    "Looping over player autoplaylist..."
                )

                if not self.loop or (self.loop and self.loop.is_closed()):
                    log.debug("Event loop is closed, nothing else to do here.")
                    return

                if self.logout_called:
                    log.debug("Logout under way, ignoring this event.")
                    return

                if self.config.auto_playlist_random:
                    random.shuffle(player.autoplaylist)
                    song_url = random.choice(player.autoplaylist)
                else:
                    song_url = player.autoplaylist[0]
                player.autoplaylist.remove(song_url)

                # Check if song is blocked.
                if (
                    self.config.song_blocklist_enabled
                    and self.config.song_blocklist.is_blocked(song_url)
                ):
                    if self.config.auto_playlist_remove_on_block:
                        await self.server_data[guild.id].autoplaylist.remove_track(
                            song_url,
                            ex=UserWarning("Found in song block list."),
                            delete_from_ap=True,
                        )
                    continue

                try:
                    info = await self.downloader.extract_info(
                        song_url, download=False, process=True
                    )

                except (
                    youtube_dl.utils.DownloadError,
                    youtube_dl.utils.YoutubeDLError,
                ) as e:
                    log.error(
                        'Error while processing song "%(url)s":  %(raw_error)s',
                        {"url": song_url, "raw_error": e},
                    )

                    await self.server_data[guild.id].autoplaylist.remove_track(
                        song_url, ex=e, delete_from_ap=self.config.remove_ap
                    )
                    continue

                except exceptions.ExtractionError as e:
                    log.error(
                        'Error extracting song "%(url)s": %(raw_error)s',
                        {
                            "url": song_url,
                            "raw_error": _L(e.message) % e.fmt_args,
                        },
                        exc_info=True,
                    )

                    await self.server_data[guild.id].autoplaylist.remove_track(
                        song_url, ex=e, delete_from_ap=self.config.remove_ap
                    )
                    continue

                except exceptions.MusicbotException:
                    log.exception(
                        "MusicBot needs to stop the auto playlist extraction and bail."
                    )
                    return
                except Exception:  # pylint: disable=broad-exception-caught
                    log.exception(
                        "MusicBot got an unhandled exception in player finished event."
                    )
                    break

                if info.has_entries:
                    log.info(
                        "Expanding auto playlist with entries extracted from:  %s",
                        info.url,
                    )
                    entries = info.get_entries_objects()
                    pl_urls: List[str] = []
                    for entry in entries:
                        pl_urls.append(entry.url)

                    player.autoplaylist = pl_urls + player.autoplaylist
                    continue

                try:
                    await player.playlist.add_entry_from_info(
                        info,
                        channel=None,
                        author=None,
                        head=False,
                    )
                except (
                    # TODO: find usages of these and make sure they get translated.
                    exceptions.ExtractionError,
                    exceptions.WrongEntryTypeError,
                ) as e:
                    log.error(
                        "Error adding song from autoplaylist: %s",
                        _L(e.message) % e.fmt_args,
                    )
                    log.debug("Exception data for above error:", exc_info=True)
                    continue
                break
            # end of autoplaylist loop.

            if not self.server_data[guild.id].autoplaylist:
                log.warning("No playable songs in the autoplaylist, disabling.")
                self.config.auto_playlist = False

        else:  # Don't serialize for autoplaylist events
            await self.serialize_queue(guild)

        if not player.is_dead and not player.current_entry and len(player.playlist):
            player.play(_continue=True)

    async def on_player_entry_added(
        self,
        player: MusicPlayer,
        playlist: Playlist,
        entry: EntryTypes,
        defer_serialize: bool = False,
        **_: Any,
    ) -> None:
        """
        Event called by MusicPlayer when an entry is added to the playlist.
        """
        log.debug("Running on_player_entry_added")
        # if playing auto-playlist track and a user queues a track,
        # if we're configured to do so, auto skip the auto playlist track.
        if (
            self.config.auto_playlist_autoskip
            and player.current_entry
            and player.current_entry.from_auto_playlist
            and playlist.peek() == entry
            and not entry.from_auto_playlist
        ):
            log.debug("Automatically skipping auto-playlist entry for queued entry.")
            player.skip()

        # Only serialize the queue for user-added tracks, unless deferred
        if entry.author and entry.channel and not defer_serialize:
            await self.serialize_queue(player.voice_client.channel.guild)

    async def on_player_error(
        self,
        player: MusicPlayer,
        entry: Optional[EntryTypes],
        ex: Optional[Exception],
        **_: Any,
    ) -> None:
        """
        Event called by MusicPlayer when an entry throws an error.
        """
        # Log the exception according to entry or bare error.
        if entry is not None:
            log.exception(
                "MusicPlayer exception for entry: %r",
                entry,
                exc_info=ex,
            )
        else:
            log.exception(
                "MusicPlayer exception.",
                exc_info=ex,
            )

        # Send a message to the calling channel if we can.
        if entry and entry.channel:
            ssd = self.server_data[player.voice_client.guild.id]
            song = _D(entry.title, ssd) or entry.url
            if isinstance(ex, exceptions.MusicbotException):
                error = _D(ex.message, ssd) % ex.fmt_args
            else:
                error = str(ex)
            res = ErrorResponse(
                _D(
                    "Playback failed for song `%(song)s` due to an error:\n```\n%(error)s```",
                    ssd,
                )
                % {"song": song, "error": error},
                delete_after=self.config.delete_delay_long,
            )
            await self.safe_send_message(entry.channel, res)

        # Take care of auto-playlist related issues.
        if entry and entry.from_auto_playlist:
            log.info("Auto playlist track could not be played:  %r", entry)
            guild = player.voice_client.guild
            await self.server_data[guild.id].autoplaylist.remove_track(
                entry.info.input_subject, ex=ex, delete_from_ap=self.config.remove_ap
            )

        # If the party isn't rockin', don't bother knockin on my door.
        if not player.is_dead:
            if len(player.playlist):
                player.play(_continue=True)
            elif self.config.auto_playlist:
                await self.on_player_finished_playing(player)

    async def update_now_playing_status(self, set_offline: bool = False) -> None:
        """Inspects available players and ultimately fire change_presence()"""
        activity = None  # type: Optional[discord.BaseActivity]
        status = discord.Status.online  # type: discord.Status
        # NOTE:  Bots can only set: name, type, state, and url fields of activity.
        # Even though Custom type is available, we cannot use emoji field with bots.
        # So Custom Activity is effectively useless at time of writing.
        # Streaming Activity is a coin toss at best. Usually status changes correctly.
        # However all other details in the client might be wrong or missing.
        # Example:  Youtube url shows "Twitch" in client profile info.

        # if requested, try to set the bot offline.
        if set_offline:
            activity = discord.Activity(
                type=discord.ActivityType.custom,
                state="",
                name="Custom Status",  # seemingly required.
            )
            await self.change_presence(
                status=discord.Status.invisible, activity=activity
            )
            self.last_status = activity
            return

        # We ignore player related status when logout is called.
        if self.logout_called:
            log.debug("Logout under way, ignoring status update event.")
            return

        playing = sum(1 for p in self.players.values() if p.is_playing)
        if self.config.status_include_paused:
            paused = sum(1 for p in self.players.values() if p.is_paused)
            total = len(self.players)
        else:
            paused = 0
            total = playing

        def format_status_msg(player: Optional[MusicPlayer]) -> str:
            msg = self.config.status_message
            msg = msg.replace("{n_playing}", str(playing))
            msg = msg.replace("{n_paused}", str(paused))
            msg = msg.replace("{n_connected}", str(total))
            if player and player.current_entry:
                msg = msg.replace("{p0_title}", player.current_entry.title)
                msg = msg.replace(
                    "{p0_length}",
                    format_song_duration(player.current_entry.duration_td),
                )
                msg = msg.replace("{p0_url}", player.current_entry.url)
            else:
                msg = msg.replace("{p0_title}", "")
                msg = msg.replace("{p0_length}", "")
                msg = msg.replace("{p0_url}", "")
            return msg

        # multiple servers are playing or paused.
        if total > 1:
            if paused > playing:
                status = discord.Status.idle

            text = f"music on {total} servers"
            if self.config.status_message:
                player = None
                for p in self.players.values():
                    if p.is_playing:
                        player = p
                        break
                text = format_status_msg(player)

            activity = discord.Activity(
                type=discord.ActivityType.playing,
                name=text,
            )

        # only 1 server is playing.
        elif playing:
            player = None
            for p in self.players.values():
                if p.is_playing:
                    player = p
                    break
            if player and player.current_entry:
                text = player.current_entry.title.strip()[:128]
                if self.config.status_message:
                    text = format_status_msg(player)

                activity = discord.Activity(
                    type=discord.ActivityType.streaming,
                    url=player.current_entry.url,
                    name=text,
                )

        # only 1 server is paused.
        elif paused:
            player = None
            for p in self.players.values():
                if p.is_paused:
                    player = p
                    break
            if player and player.current_entry:
                text = player.current_entry.title.strip()[:128]
                if self.config.status_message:
                    text = format_status_msg(player)

                status = discord.Status.idle
                activity = discord.Activity(
                    type=discord.ActivityType.custom,
                    state=text,
                    name="Custom Status",  # seemingly required.
                )

        # nothing going on.
        else:
            text = f" ~ {EMOJI_IDLE_ICON} ~ "
            if self.config.status_message:
                text = format_status_msg(None)

            status = discord.Status.idle
            activity = discord.CustomActivity(
                type=discord.ActivityType.custom,
                state=text,
                name="Custom Status",  # seems required to make idle status work.
            )

        async with self.aiolocks[_func_()]:
            if activity != self.last_status:
                log.noise(  # type: ignore[attr-defined]
                    "Update bot status:  %(status)s -- %(activity)r",
                    {"status": status, "activity": activity},
                )
                await self.change_presence(status=status, activity=activity)
                self.last_status = activity
                # Discord docs say Game status can only be updated 5 times in 20 seconds.
                # This sleep should maintain the above lock for long enough to space
                # out the status updates in multi-guild setups.
                # If not, we should use the lock to ignore further updates.
                try:
                    await asyncio.sleep(4)
                except asyncio.CancelledError:
                    pass

    async def serialize_queue(self, guild: discord.Guild) -> None:
        """
        Serialize the current queue for a server's player to json.
        """
        if not self.config.persistent_queue:
            return

        player = self.get_player_in(guild)
        if not player:
            return

        path = self.config.data_path.joinpath(str(guild.id), DATA_GUILD_FILE_QUEUE)

        async with self.aiolocks["queue_serialization" + ":" + str(guild.id)]:
            log.debug("Serializing queue for %s", guild.id)

            with open(path, "w", encoding="utf8") as f:
                f.write(player.serialize(sort_keys=True))

    async def deserialize_queue(
        self,
        guild: discord.Guild,
        voice_client: discord.VoiceClient,
        playlist: Optional[Playlist] = None,
    ) -> Optional[MusicPlayer]:
        """
        Deserialize a saved queue for a server into a MusicPlayer.  If no queue is saved, returns None.
        """
        if not self.config.persistent_queue:
            return None

        if playlist is None:
            playlist = Playlist(self)

        path = self.config.data_path.joinpath(str(guild.id), DATA_GUILD_FILE_QUEUE)

        async with self.aiolocks["queue_serialization:" + str(guild.id)]:
            if not path.is_file():
                return None

            log.debug("Deserializing queue for %s", guild.id)

            with open(path, "r", encoding="utf8") as f:
                data = f.read()

        return MusicPlayer.from_json(data, self, voice_client, playlist)

    async def write_current_song(self, guild: discord.Guild, entry: EntryTypes) -> None:
        """
        Writes the current song to file
        """
        player = self.get_player_in(guild)
        if not player:
            return

        path = self.config.data_path.joinpath(str(guild.id), DATA_GUILD_FILE_CUR_SONG)

        async with self.aiolocks["current_song:" + str(guild.id)]:
            log.debug("Writing current song for %s", guild.id)

            with open(path, "w", encoding="utf8") as f:
                f.write(entry.title)

    #######################################################################################################################

    async def safe_send_message(
        self,
        dest: discord.abc.Messageable,
        content: MusicBotResponse,
    ) -> Optional[discord.Message]:
        """
        Safely send a message with given `content` to the message-able
        object in `dest`
        This method should handle all raised exceptions so callers will
        not need to handle them locally.

        :param: dest:     A channel, user, or other discord.abc.Messageable object.
        :param: content:  A MusicBotMessage such as Response or ErrorResponse.

        :returns:  May return a discord.Message object if a message was sent.
        """
        if not isinstance(content, MusicBotResponse):
            log.error(
                "Cannot send non-response object:  %r",
                content,
                exc_info=self.config.debug_mode,
            )
            raise exceptions.MusicbotException(
                "[Dev Bug] Tried sending an invalid response object."
            )

        fallback_channel = content.sent_from
        delete_after = content.delete_after
        reply_to = content.reply_to

        # set the default delete delay to configured short delay.
        if delete_after is None:
            delete_after = self.config.delete_delay_short

        msg = None
        retry_after = 0.0
        send_kws: Dict[str, Any] = {}

        ch_name = "DM-Channel"
        if hasattr(dest, "name"):
            ch_name = str(dest.name)

        if not self.config.remove_embed_footer:
            footer_text = DEFAULT_FOOTER_TEXT
            if self.config.footer_text:
                footer_text = self.config.footer_text
            content.set_footer(
                text=footer_text,
                icon_url=DEFAULT_BOT_ICON,
            )

        if reply_to and reply_to.channel == dest:
            send_kws["reference"] = reply_to.to_reference(fail_if_not_exists=False)
            send_kws["mention_author"] = self.config.reply_and_mention

        if content.files:
            send_kws["files"] = content.files

        try:
            if (self.config.embeds and not content.force_text) or content.force_embed:
                log.debug("sending embed to: %s", dest)
                msg = await dest.send(embed=content, **send_kws)
            else:
                log.debug("sending text to: %s", dest)
                msg = await dest.send(content.to_markdown(), **send_kws)

        except discord.Forbidden:
            log.error(
                'Cannot send message to "%s", no permission',
                ch_name,
                exc_info=self.config.debug_mode,
            )

        except discord.NotFound:
            log.error(
                'Cannot send message to "%s", invalid or deleted channel',
                ch_name,
                exc_info=self.config.debug_mode,
            )

        except discord.HTTPException as e:
            if len(content) > DISCORD_MSG_CHAR_LIMIT:
                log.error(
                    "Message is over the message size limit (%s)",
                    DISCORD_MSG_CHAR_LIMIT,
                    exc_info=self.config.debug_mode,
                )

            # if `dest` is a user with strict privacy or a bot, direct message can fail.
            elif e.code == 50007 and fallback_channel:
                log.debug(
                    "Could not send private message, sending in fallback channel instead."
                )
                await self.safe_send_message(fallback_channel, content)

            # If we got rate-limited, retry using the retry-after api header.
            elif e.status == 429:
                # Note:  `e.response` could be either type:  aiohttp.ClientResponse  OR  requests.Response
                # thankfully both share a similar enough `response.headers` member CI Dict.
                # See docs on headers here:  https://discord.com/developers/docs/topics/rate-limits
                try:
                    retry_after = 0.0
                    header_val = e.response.headers.get("RETRY-AFTER")
                    if header_val:
                        retry_after = float(header_val)
                except ValueError:
                    retry_after = 0.0
                if retry_after:
                    log.warning(
                        "Rate limited send message, retrying in %s seconds.",
                        retry_after,
                    )
                    try:
                        await asyncio.sleep(retry_after)
                    except asyncio.CancelledError:
                        log.warning("Cancelled message retry for:  %s", content)
                        return msg
                    return await self.safe_send_message(dest, content)

                log.error(
                    "Rate limited send message, but cannot retry!",
                    exc_info=self.config.debug_mode,
                )

            else:
                log.error(
                    "Failed to send message in fallback channel.",
                    exc_info=self.config.debug_mode,
                )

        except aiohttp.client_exceptions.ClientError:
            log.error("Failed to send due to an HTTP error.")

        finally:
            if not retry_after and self.config.delete_messages and msg and delete_after:
                self.create_task(self._wait_delete_msg(msg, delete_after))

        return msg

    async def safe_delete_message(
        self,
        message: discord.Message,
    ) -> None:
        """
        Safely delete the given `message` from discord.
        This method should handle all raised exceptions so callers will
        not need to handle them locally.

        :param: quiet:  Toggle using log.debug or log.warning
        """
        # TODO: this could use a queue and some other handling.

        try:
            await message.delete()

        except discord.Forbidden:
            log.warning(
                'Cannot delete message "%s", no permission', message.clean_content
            )

        except discord.NotFound:
            log.warning(
                'Cannot delete message "%s", message not found',
                message.clean_content,
            )

        except discord.HTTPException as e:
            if e.status == 429:
                # Note:  `e.response` could be either type:  aiohttp.ClientResponse  OR  requests.Response
                # thankfully both share a similar enough `response.headers` member CI Dict.
                # See docs on headers here:  https://discord.com/developers/docs/topics/rate-limits
                try:
                    retry_after = 0.0
                    header_val = e.response.headers.get("RETRY-AFTER")
                    if header_val:
                        retry_after = float(header_val)
                except ValueError:
                    retry_after = 0.0
                if retry_after:
                    log.warning(
                        "Rate limited message delete, retrying in %s seconds.",
                        retry_after,
                    )
                    self.create_task(self._wait_delete_msg(message, retry_after))
                else:
                    log.error("Rate limited message delete, but cannot retry!")

            else:
                log.warning("Failed to delete message")
                log.noise(  # type: ignore[attr-defined]
                    "Got HTTPException trying to delete message: %s", message
                )

        except aiohttp.client_exceptions.ClientError:
            log.error(
                "Failed to send due to an HTTP error.", exc_info=self.config.debug_mode
            )

        return None

    async def safe_edit_message(
        self,
        message: discord.Message,
        new: MusicBotResponse,
        *,
        send_if_fail: bool = False,
    ) -> Optional[discord.Message]:
        """
        Safely update the given `message` with the `new` content.
        This function should handle all raised exceptions so callers
        will not need to handle them locally.

        :param: send_if_fail:  Toggle sending a new message if edit fails.
        :param: quiet:  Use log.debug if quiet otherwise use log.warning

        :returns:  May return a discord.Message object if edit/send did not fail.
        """
        try:
            if isinstance(new, discord.Embed):
                return await message.edit(embed=new)

            return await message.edit(content=new)

        except discord.NotFound:
            log.warning(
                'Cannot edit message "%s", message not found',
                message.clean_content,
            )
            if send_if_fail:
                log.warning("Sending message instead")
                return await self.safe_send_message(message.channel, new)

        except discord.HTTPException as e:
            if e.status == 429:
                # Note:  `e.response` could be either type:  aiohttp.ClientResponse  OR  requests.Response
                # thankfully both share a similar enough `response.headers` member CI Dict.
                # See docs on headers here:  https://discord.com/developers/docs/topics/rate-limits
                try:
                    retry_after = 0.0
                    header_val = e.response.headers.get("RETRY-AFTER")
                    if header_val:
                        retry_after = float(header_val)
                except ValueError:
                    retry_after = 0.0
                if retry_after:
                    log.warning(
                        "Rate limited edit message, retrying in %s seconds.",
                        retry_after,
                    )
                    try:
                        await asyncio.sleep(retry_after)
                    except asyncio.CancelledError:
                        log.warning("Cancelled message edit for:  %s", message)
                        return None
                    return await self.safe_edit_message(
                        message, new, send_if_fail=send_if_fail
                    )
            else:
                log.warning("Failed to edit message")
                log.noise(  # type: ignore[attr-defined]
                    "Got HTTPException trying to edit message %s to: %s", message, new
                )

        except aiohttp.client_exceptions.ClientError:
            log.error(
                "Failed to send due to an HTTP error.", exc_info=self.config.debug_mode
            )

        return None

    async def _wait_delete_msg(
        self, message: discord.Message, after: Union[int, float]
    ) -> None:
        """
        Uses asyncio.sleep to delay a call to safe_delete_message but
        does not check if the bot can delete a message or if it has
        already been deleted before trying to delete it anyway.
        """
        try:
            await asyncio.sleep(after)
        except asyncio.CancelledError:
            log.warning(
                "Cancelled delete for message (ID: %(id)s):  %(content)s",
                {"id": message.id, "content": message.content},
            )
            return

        if not self.is_closed():
            await self.safe_delete_message(message)

    def _setup_windows_signal_handler(self) -> None:
        """
        Windows needs special handling for Ctrl+C signals to play nice with asyncio
        so this method sets up signals with access to bot event loop.
        This enables capturing KeyboardInterrupt and using it to cleanly shut down.
        """
        if os.name != "nt":
            return

        # method used to set the above member.
        def set_windows_signal(sig: int, _frame: Any) -> None:
            self._os_signal = signal.Signals(sig)

        # method used to periodically check for a signal, and process it.
        async def check_windows_signal() -> None:
            while True:

                if self.logout_called:
                    break
                if self._os_signal is None:
                    try:
                        await asyncio.sleep(1)
                    except asyncio.CancelledError:
                        break
                else:
                    await self.on_os_signal(self._os_signal, self.loop)
                    self._os_signal = None

        # register interrupt signal Ctrl+C to be trapped.
        signal.signal(signal.SIGINT, set_windows_signal)
        # and start the signal checking loop.
        task_ref = asyncio.create_task(
            check_windows_signal(), name="MB_WinInteruptChecker"
        )
        setattr(self, "_mb_win_sig_checker_task", task_ref)

    async def on_os_signal(
        self, sig: signal.Signals, _loop: asyncio.AbstractEventLoop
    ) -> None:
        """
        On Unix-like/Linux OS, this method is called automatically on the event
        loop for signals registered in run.py.
        On Windows, this method is called by custom signal handling set up at
        the start of run_musicbot().
        This allows MusicBot to handle external signals and triggering a clean
        shutdown of MusicBot in response to them.

        It essentially just calls logout, and the rest of MusicBot tear-down is
        finished up in `MusicBot.run_musicbot()` instead.

        Signals handled here are registered with the event loop in run.py.
        """
        # This print facilitates putting '^C' on its own line in the terminal.
        print()
        log.warning("Caught a signal from the OS: %s", sig.name)

        try:
            if self and not self.logout_called:
                log.info("Disconnecting and closing down MusicBot...")
                await self.logout()
        except Exception as e:
            log.exception("Exception thrown while handling interrupt signal!")
            raise KeyboardInterrupt() from e

    async def run_musicbot(self) -> None:
        """
        This method is to be used in an event loop to start the MusicBot.
        It handles cleanup of bot session, while the event loop is closed separately.
        """
        # Windows specifically needs some help with signals.
        self._setup_windows_signal_handler()

        # handle start up and teardown.
        try:
            log.info("MusicBot is now doing start up steps...")
            await self.start(*self.config.auth)
            log.info("MusicBot is now doing shutdown steps...")
            if self.exit_signal is None:
                self.exit_signal = exceptions.TerminateSignal()

        except discord.errors.LoginFailure as e:
            log.warning("Start up failed at login.")
            raise exceptions.HelpfulError(
                # fmt: off
                "Failed Discord API Login!\n"
                "\n"
                "Problem:\n"
                "  MusicBot could not log into Discord API.\n"
                "  Your Token may be incorrect or there may be an API outage.\n"
                "\n"
                "Solution:\n"
                "  Make sure you have the correct Token set in your config.\n"
                "  Check API status at the official site: discordstatus.com"
                # fmt: on
            ) from e

        finally:
            # Shut down the thread pool executor.
            log.info("Waiting for download threads to finish up...")
            # We can't kill the threads in ThreadPoolExecutor.  User can Ctrl+C though.
            # We can pass `wait=False` and carry on with "shutdown" but threads
            # will stay until they're done.  We wait to keep it clean...
            tps_args: Dict[str, Any] = {}
            if sys.version_info >= (3, 9):
                tps_args["cancel_futures"] = True
            self.downloader.thread_pool.shutdown(**tps_args)

            # Inspect all waiting tasks and either cancel them or let them finish.
            pending_tasks = []
            for task in asyncio.all_tasks(loop=self.loop):
                # Don't cancel run_musicbot task, we need it to finish cleaning.
                if task == asyncio.current_task():
                    continue

                tname = task.get_name()
                coro = task.get_coro()
                coro_name = "[unknown]"
                if coro and hasattr(coro, "__qualname__"):
                    coro_name = getattr(coro, "__qualname__", "[unknown]")

                if tname.startswith("Signal_SIG") or coro_name.startswith(
                    "Client.close."
                ):
                    log.debug(
                        "Will wait for task:  %(name)s  (%(func)s)",
                        {"name": tname, "func": coro_name},
                    )
                    pending_tasks.append(task)

                else:
                    log.debug(
                        "Will try to cancel task:  %(name)s  (%(func)s)",
                        {"name": tname, "func": coro_name},
                    )
                    task.cancel()
                    pending_tasks.append(task)

            # wait on any pending tasks.
            if pending_tasks:
                log.debug("Awaiting pending tasks...")
                await asyncio.gather(*pending_tasks, return_exceptions=True)
                await asyncio.sleep(0.5)

            # ensure connector is closed.
            if self.http.connector:
                log.debug("Closing HTTP Connector.")
                await self.http.connector.close()
                await asyncio.sleep(0.5)

            # ensure the session is closed.
            if self.session:
                log.debug("Closing aiohttp session.")
                await self.session.close()
                await asyncio.sleep(0.5)

            # if anything set an exit signal, we should raise it here.
            if self.exit_signal:
                raise self.exit_signal

    async def logout(self) -> None:
        """
        Disconnect all voice clients and signal MusicBot to close it's connections to discord.
        """
        log.noise("Logout has been called.")  # type: ignore[attr-defined]
        await self.update_now_playing_status(set_offline=True)

        self.logout_called = True
        await self.disconnect_all_voice_clients()
        return await super().close()

    async def on_error(self, event: str, /, *_args: Any, **_kwargs: Any) -> None:
        _ex_type, ex, _stack = sys.exc_info()

        if isinstance(ex, exceptions.HelpfulError):
            log.error(
                "Exception in %(event)s:\n%(error)s",
                {
                    "event": event,
                    "error": _L(ex.message) % ex.fmt_args,
                },
            )

            await asyncio.sleep(2)  # makes extra sure this gets seen(?)

            await self.logout()

        elif isinstance(ex, (exceptions.RestartSignal, exceptions.TerminateSignal)):
            self.exit_signal = ex
            await self.logout()

        else:
            log.error("Exception in %s", event, exc_info=True)

    async def on_resumed(self) -> None:
        """
        Event called by discord.py when the client resumed an existing session.
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_resume
        """
        log.info("MusicBot resumed a session with discord.")
        await self._auto_join_channels(from_resume=True)

    async def on_ready(self) -> None:
        """
        Event called by discord.py typically when MusicBot has finished login.
        May be called multiple times, and may not be the first event dispatched!
        See documentations for specifics:
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_ready
        """
        if self.on_ready_count == 0:
            await self._on_ready_once()
            self.init_ok = True

        await self._on_ready_always()
        self.on_ready_count += 1

        log.debug("Finish on_ready")

    async def _on_ready_once(self) -> None:
        """
        A version of on_ready that will only ever be called once, at first login.
        """
        mute_discord_console_log()
        log.debug("Logged in, now getting MusicBot ready...")

        if not self.user:
            log.critical("ClientUser is somehow none, we gotta bail...")
            self.exit_signal = exceptions.TerminateSignal()
            raise self.exit_signal

        # Start the environment checks. Generate folders/files dependent on Discord data.
        # Also takes care of app-info and auto OwnerID updates.
        await self._on_ready_sanity_checks()

        log.info(
            "MusicBot:  %(id)s/%(name)s#%(desc)s",
            {
                "id": self.user.id,
                "name": self.user.name,
                "desc": self.user.discriminator,
            },
        )

        owner = self._get_owner_member()
        if owner and self.guilds:
            log.info(
                "Owner:     %(id)s/%(name)s#%(desc)s\n",
                {
                    "id": owner.id,
                    "name": owner.name,
                    "desc": owner.discriminator,
                },
            )

            log.info("Guild List:")
            unavailable_servers = 0
            for s in self.guilds:
                ser = f"{s.name} (unavailable)" if s.unavailable else s.name
                log.info(" - %s", ser)
                if self.config.leavenonowners:
                    if s.unavailable:
                        unavailable_servers += 1
                    else:
                        check = s.get_member(owner.id)
                        if check is None:
                            await s.leave()
                            log.info(
                                "Left %s due to bot owner not found",
                                s.name,
                            )
            if unavailable_servers != 0:
                log.info(
                    "Not proceeding with checks in %s servers due to unavailability",
                    str(unavailable_servers),
                )

        elif self.guilds:
            log.warning(
                "Owner could not be found on any guild (id: %s)\n", self.config.owner_id
            )

            log.info("Guild List:")
            for s in self.guilds:
                ser = f"{s.name} (unavailable)" if s.unavailable else s.name
                log.info(" - %s", ser)

        else:
            log.warning("Owner unknown, bot is not on any guilds.")
            if self.user.bot:
                invite_url = await self.generate_invite_link()
                log.warning(
                    "To make the bot join a guild, paste this link in your browser. \n"
                    "Note: You should be logged into your main account and have \n"
                    "manage server permissions on the guild you want the bot to join.\n"
                    "  %s",
                    invite_url,
                )

        print(flush=True)

        # validate bound channels and log them.
        if self.config.bound_channels:
            # Get bound channels by ID, and validate that we can use them.
            text_chlist: Set[MessageableChannel] = set()
            invalid_ids: Set[int] = set()
            for ch_id in self.config.bound_channels:
                ch = self.get_channel(ch_id)
                if not ch:
                    log.warning("Got None for bound channel with ID:  %d", ch_id)
                    invalid_ids.add(ch_id)
                    continue

                if not isinstance(ch, discord.abc.Messageable):
                    log.warning(
                        "Cannot bind to non Messageable channel with ID:  %d",
                        ch_id,
                    )
                    invalid_ids.add(ch_id)
                    continue

                if not isinstance(ch, (discord.PartialMessageable, discord.DMChannel)):
                    text_chlist.add(ch)

            # Clean up our config data so it can be reliable later.
            self.config.bound_channels.difference_update(invalid_ids)

            # finally, log what we've bound to.
            if text_chlist:
                log.info("Bound to text channels:")
                for valid_ch in text_chlist:
                    guild_name = _L("Private Channel")
                    if isinstance(valid_ch, discord.DMChannel):
                        ch_name = _L("Unknown User DM")
                        if valid_ch.recipient:
                            ch_name = _L("User DM: %(name)s") % {
                                "name": valid_ch.recipient.name
                            }
                    elif isinstance(valid_ch, discord.PartialMessageable):
                        ch_name = _L("Unknown Channel (Partial)")
                    else:
                        ch_name = valid_ch.name or _L("Unnamed Channel: %(id)s") % {
                            "id": valid_ch.id
                        }
                    if valid_ch.guild:
                        guild_name = valid_ch.guild.name
                    log.info(
                        " - %(guild)s/%(channel)s",
                        {"guild": guild_name, "channel": ch_name},
                    )
            else:
                log.info("Not bound to any text channels")
        else:
            log.info("Not bound to any text channels")

        print(flush=True)  # new line in console.

        # validate and display auto-join channels.
        if self.config.autojoin_channels:
            vc_chlist: Set[VoiceableChannel] = set()
            invalids: Set[int] = set()
            for ch_id in self.config.autojoin_channels:
                ch = self.get_channel(ch_id)
                if not ch:
                    log.warning("Got None for auto join channel with ID:  %d", ch_id)
                    invalids.add(ch_id)
                    continue

                if isinstance(ch, discord.abc.PrivateChannel):
                    log.warning(
                        "Cannot auto join a Private/Non-Guild channel with ID:  %d",
                        ch_id,
                    )
                    invalids.add(ch_id)
                    continue

                if not isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
                    log.warning(
                        "Cannot auto join to non-connectable channel with ID:  %d",
                        ch_id,
                    )
                    invalids.add(ch_id)
                    continue

                # Add the channel to vc_chlist for log readout.
                vc_chlist.add(ch)
                # Add the channel to guild-specific auto-join slot.
                self.server_data[ch.guild.id].auto_join_channel = ch

            # Update config data to be reliable later.
            self.config.autojoin_channels.difference_update(invalids)

            # log what we're connecting to.
            if vc_chlist:
                log.info("Auto joining voice channels:")
                for ch in vc_chlist:
                    log.info(
                        " - %(guild)s/%(channel)s",
                        {"guild": ch.guild.name.strip(), "channel": ch.name.strip()},
                    )

            else:
                log.info("Not auto joining any voice channels")

        else:
            log.info("Not auto joining any voice channels")

        # Display and log the config settings.
        if self.config.show_config_at_start:
            self._on_ready_log_configs()

        # we do this after the config stuff because it's a lot easier to notice here
        if self.config.register.ini_missing_options:
            missing_list = "\n".join(
                sorted(str(o) for o in self.config.register.ini_missing_options)
            )
            log.warning(
                # fmt: off
                "Detected missing config options!\n"
                "\n"
                "Problem:\n"
                "  Your config options.ini file is missing some options.\n"
                "  Default settings will be used for these options until you set them.\n"
                "  Here is a list of options (with [section] names) we didn't find:\n"
                "%(missing)s\n"
                "\n"
                "Solution:\n"
                "  Add the new options listed above to your options.ini file.\n"
                "  You can do this with MusicBot config command, the configure.py tool, or any text editor.\n"
                "  If you recently updated, check example_options.ini for documentation and default values.\n\n",
                # fmt: on
                {"missing": missing_list},
            )

        # Pre-load guild specific data / options.
        # TODO:  probably change this later for better UI/UX.
        if self.config.enable_options_per_guild:
            for guild in self.guilds:
                # Triggers on-demand task to load data from disk.
                self.server_data[guild.id].is_ready()
                # context switch to give scheduled task an execution window.
                await asyncio.sleep(0)

    async def _on_ready_always(self) -> None:
        """
        A version of on_ready that will be called on every event.
        """
        if self.on_ready_count > 0:
            log.debug("Event on_ready has fired %s times", self.on_ready_count)
        self.create_task(self._on_ready_call_later(), name="MB_PostOnReady")

    async def _on_ready_call_later(self) -> None:
        """
        A collection of calls scheduled for execution by _on_ready_once
        """
        await self.update_now_playing_status()
        await self._auto_join_channels()

    async def _on_ready_sanity_checks(self) -> None:
        """
        Run all sanity checks that should be run in/just after on_ready event.
        """
        # Ensure AppInfo is loaded.
        if not self.cached_app_info:
            log.debug("Getting application info.")
            self.cached_app_info = await self.application_info()

        # Ensure folders exist
        await self._on_ready_ensure_env()

        # TODO: Server permissions check
        # TODO: pre-expand playlists in autoplaylist?

        # Ensure configs are valid / auto OwnerID is updated.
        await self._on_ready_validate_configs()

    async def _on_ready_ensure_env(self) -> None:
        """
        Startup check to make sure guild/server specific directories are
        available in the data directory.
        Additionally populate a text file to map guild ID to their names.
        """
        log.debug("Ensuring data folders exist")
        for guild in self.guilds:
            self.config.data_path.joinpath(str(guild.id)).mkdir(exist_ok=True)

        names_path = self.config.data_path.joinpath(DATA_FILE_SERVERS)
        with open(names_path, "w", encoding="utf8") as f:
            for guild in sorted(self.guilds, key=lambda s: int(s.id)):
                f.write(f"{guild.id}: {guild.name}\n")

        self.filecache.delete_old_audiocache(remove_dir=True)

    async def _on_ready_validate_configs(self) -> None:
        """
        Startup check to handle late validation of config and permissions.
        """
        log.debug("Validating config")
        await self.config.async_validate(self)

        log.debug("Validating permissions config")
        await self.permissions.async_validate(self)

    def _on_ready_log_configs(self) -> None:
        """
        Shows information about configs, including missing keys.
        No validation is done in this method, only display/logs.
        """

        def on_or_off(test: bool) -> str:
            return [_L("Disabled"), _L("Enabled")][test]

        print(flush=True)
        log.info("Options:")

        log.info("  Command prefix: %s", self.config.command_prefix)
        log.info(
            "  Command by @mention: %s", on_or_off(self.config.commands_via_mention)
        )
        log.info("  Command aliases: %s", on_or_off(self.config.usealias))
        log.info("  Default volume: %d%%", int(self.config.default_volume * 100))
        log.info(
            "  Skip threshold: %(num)d votes or %(percent).0f%%",
            {
                "num": self.config.skips_required,
                "percent": (self.config.skip_ratio_required * 100),
            },
        )
        log.info("    Legacy skip: %s", on_or_off(self.config.legacy_skip))
        log.info(
            "    Author insta-skip: %s",
            on_or_off(self.config.allow_author_skip),
        )
        log.info(
            "  Now Playing @mentions: %s",
            on_or_off(self.config.now_playing_mentions),
        )
        log.info(
            "  Auto-join Owner's voice channel: %s", on_or_off(self.config.auto_summon)
        )
        log.info(
            "  Auto-Playlist: %(status)s (order: %(order)s)",
            {
                "status": on_or_off(self.config.auto_playlist),
                "order": [_L("sequential"), _L("random")][
                    self.config.auto_playlist_random
                ],
            },
        )
        log.info(
            "    Save per-server queue history: %s",
            on_or_off(self.config.enable_queue_history_guilds),
        )
        log.info(
            "    Save global queue history: %s",
            on_or_off(self.config.enable_queue_history_global),
        )
        log.info(
            "    Remove URLs on extraction error: %s", on_or_off(self.config.remove_ap)
        )
        log.info(
            "    Skip playlist for user requests: %s",
            on_or_off(self.config.auto_playlist_autoskip),
        )
        log.info("  Auto-Pause: %s", on_or_off(self.config.auto_pause))
        log.info(
            "  Delete Messages: %s",
            on_or_off(self.config.delete_messages),
        )
        if self.config.delete_messages:
            log.info(
                "    Delete Invoking: %s",
                on_or_off(self.config.delete_invoking),
            )
            log.info(
                "    Delete Now Playing: %s",
                on_or_off(self.config.delete_nowplaying),
            )
        log.info("  Debug Mode: %s", on_or_off(self.config.debug_mode))
        log.info("  Songs blocklist: %s", on_or_off(self.config.song_blocklist_enabled))
        log.info("  Users blocklist: %s", on_or_off(self.config.user_blocklist_enabled))
        log.info(
            "  Downloaded songs will be %s",
            ["deleted", "saved"][self.config.save_videos],
        )
        if self.config.save_videos and self.config.storage_limit_days:
            log.info("    Delete if unused for %d days", self.config.storage_limit_days)
        if self.config.save_videos and self.config.storage_limit_bytes:
            size = format_size_from_bytes(self.config.storage_limit_bytes)
            log.info("    Delete if cache exceeds %s", size)

        log.info(
            "  Pre-download next track: %s",
            on_or_off(self.config.pre_download_next_song),
        )

        if self.config.status_message:
            log.info("  Status message: %s", self.config.status_message)
        log.info(
            "  Write current song title to file: %s",
            on_or_off(self.config.write_current_song),
        )
        log.info("  Respond with Embeds: %s", on_or_off(self.config.embeds))
        if self.config.embeds:
            if self.config.remove_embed_footer:
                log.info("    Footer Text Disabled")
            else:
                log.info("    Footer Text:  %s", self.config.footer_text)
        log.info(
            "  Spotify integration: %s",
            on_or_off(self.config.spotify_enabled),
        )
        log.info(
            "  Leave servers where Owner is not a member: %s",
            on_or_off(self.config.leavenonowners),
        )
        log.info(
            "  Disconnect from inactive channel: %s",
            on_or_off(self.config.leave_inactive_channel),
        )
        if self.config.leave_inactive_channel:
            log.info(
                "    Timeout: %s seconds",
                self.config.leave_inactive_channel_timeout,
            )
        log.info(
            "  Disconnect at end of queue: %s",
            on_or_off(self.config.leave_after_queue_empty),
        )
        log.info(
            "  Disconnect when player idles: %s",
            "Disabled" if self.config.leave_player_inactive_for == 0 else "Enabled",
        )
        if self.config.leave_player_inactive_for:
            log.info("    Timeout: %d seconds", self.config.leave_player_inactive_for)
        log.info("  Self Deafen: %s", on_or_off(self.config.self_deafen))
        log.info(
            "  Per-server command prefix: %s",
            on_or_off(self.config.enable_options_per_guild),
        )
        log.info("  Search using reactions: %s", on_or_off(not self.config.searchlist))
        log.info("    Results per search: %d", self.config.defaultsearchresults)
        log.info(
            "  Round Robin Queue: %s",
            on_or_off(self.config.round_robin_queue),
        )
        log.info("  Local media files: %s", on_or_off(self.config.enable_local_media))

        log.info(
            "  Network checking ping tests: %s",
            on_or_off(self.config.enable_network_checker),
        )

        if self.config.use_opus_audio and not self.config.use_opus_probe:
            audio_out = "Opus"
        elif self.config.use_opus_probe:
            audio_out = "Copy"
        else:
            audio_out = "PCM"
        log.info("  Audio processed with: %s", audio_out)

        log.info(
            "  Equalize audio level per-track: %s",
            on_or_off(self.config.use_experimental_equalization),
        )

        if self.config.ytdlp_proxy:
            log.info("  HTTP Proxy set to:  %s", self.config.ytdlp_proxy)
        if self.config.ytdlp_user_agent:
            log.info("  User Agent set to:  %s", self.config.ytdlp_user_agent)
        # log.info("  Max Bitrate: %s kbps (per channel)", MUSICBOT_VOICE_MAX_KBITRATE)
        print(flush=True)

    def _get_song_url_or_none(
        self, url: str, player: Optional[MusicPlayer]
    ) -> Optional[str]:
        """Return song url if provided or one is currently playing, else returns None"""
        url_or_none = self.downloader.get_url_or_none(url)
        if url_or_none:
            return url_or_none

        if player and player.current_entry and player.current_entry.url:
            return player.current_entry.url

        return None

    def _do_song_blocklist_check(self, song_subject: str) -> None:
        """
        Check if the `song_subject` is matched in the block list.

        :raises: musicbot.exceptions.CommandError
            The subject is matched by a block list entry.
        """
        if not self.config.song_blocklist_enabled:
            return

        if self.config.song_blocklist.is_blocked(song_subject):
            raise exceptions.CommandError(
                "The requested song `%(subject)s` is blocked by the song block list.",
                fmt_args={"subject": song_subject},
            )

    async def handle_vc_inactivity(self, guild: discord.Guild) -> None:
        """
        Manage a server-specific event timer when MusicBot's voice channel becomes idle,
        if the bot is configured to do so.
        """
        if not guild.voice_client or not guild.voice_client.channel:
            log.warning(
                "Attempted to handle Voice Channel inactivity, but Bot is not in voice..."
            )
            return

        event = self.server_data[guild.id].get_event("inactive_vc_timer")

        if event.is_active():
            log.debug("Channel activity already waiting in guild: %s", guild)
            return
        event.activate()

        try:
            chname = _L("Unknown Channel")
            if hasattr(guild.voice_client.channel, "name"):
                chname = guild.voice_client.channel.name

            log.info(
                "Channel activity waiting %(time)d seconds to leave channel: %(channel)s",
                {
                    "time": self.config.leave_inactive_channel_timeout,
                    "channel": chname,
                },
            )
            await discord.utils.sane_wait_for(
                [event.wait()], timeout=self.config.leave_inactive_channel_timeout
            )
        except asyncio.TimeoutError:
            # could timeout after a disconnect.
            if guild.voice_client and isinstance(
                guild.voice_client.channel, (discord.VoiceChannel, discord.StageChannel)
            ):
                log.info(
                    "Channel activity timer for %s has expired. Disconnecting.",
                    guild.name,
                )
                await self.on_inactivity_timeout_expired(guild.voice_client.channel)
        else:
            log.info(
                "Channel activity timer canceled for: %(channel)s in %(guild)s",
                {
                    "channel": getattr(
                        guild.voice_client.channel, "name", guild.voice_client.channel
                    ),
                    "guild": guild.name,
                },
            )
        finally:
            event.deactivate()
            event.clear()

    async def handle_player_inactivity(self, player: MusicPlayer) -> None:
        """
        Manage a server-specific event timer when it's MusicPlayer becomes idle,
        if the bot is configured to do so.
        """
        if self.logout_called:
            return

        if not self.config.leave_player_inactive_for:
            return
        channel = player.voice_client.channel
        guild = channel.guild
        event = self.server_data[guild.id].get_event("inactive_player_timer")

        if str(channel.id) in str(self.config.autojoin_channels):
            log.debug(
                "Ignoring player inactivity in auto-joined channel:  %s",
                channel.name,
            )
            return

        if event.is_active():
            log.debug(
                "Player activity timer already waiting in guild: %s",
                guild,
            )
            return
        event.activate()

        try:
            log.info(
                "Player activity timer waiting %(time)d seconds to leave channel: %(channel)s",
                {
                    "time": self.config.leave_player_inactive_for,
                    "channel": channel.name,
                },
            )
            await discord.utils.sane_wait_for(
                [event.wait()], timeout=self.config.leave_player_inactive_for
            )
        except asyncio.TimeoutError:
            if not player.is_playing and player.voice_client.is_connected():
                log.info(
                    "Player activity timer for %s has expired. Disconnecting.",
                    guild.name,
                )
                await self.on_inactivity_timeout_expired(channel)
            else:
                log.info(
                    "Player activity timer canceled for: %(channel)s in %(guild)s",
                    {"channel": channel.name, "guild": guild.name},
                )
        else:
            log.info(
                "Player activity timer canceled for: %(channel)s in %(guild)s",
                {"channel": channel.name, "guild": guild.name},
            )
        finally:
            event.deactivate()
            event.clear()

    async def reset_player_inactivity(self, player: MusicPlayer) -> None:
        """
        Handle reset of the server-specific inactive player timer if it is enabled.
        """
        if not self.config.leave_player_inactive_for:
            return
        guild = player.voice_client.channel.guild
        event = self.server_data[guild.id].get_event("inactive_player_timer")
        if event.is_active() and not event.is_set():
            event.set()
            log.debug("Player activity timer is being reset.")

    @command_helper(
        desc=_Dd(
            "Reset the auto playlist queue by copying it back into player memory.\n"
            "This command will be removed in a future version, replaced by the autoplaylist command(s)."
        )
    )
    async def cmd_resetplaylist(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        player: MusicPlayer,
    ) -> CommandResponse:
        """
        Deprecated command, to be replaced with autoplaylist restart sub-command.
        """
        player.autoplaylist = list(self.server_data[guild.id].autoplaylist)
        return Response(
            _D("\N{OK HAND SIGN}", ssd_),
            force_text=True,
        )

    @command_helper(
        usage=["{cmd} [COMMAND]"],
        desc=_Dd(
            "Show usage and description of a command, or list all available commands.\n"
        ),
    )
    async def cmd_help(
        self,
        ssd_: Optional[GuildSpecificData],
        message: discord.Message,
        guild: Optional[discord.Guild],
        command: Optional[str] = None,
    ) -> CommandResponse:
        """
        Display help text for usage of MusicBot or specific commmands.
        """
        commands = []
        is_all = False
        is_emoji = False
        alias_of = ""
        if not guild:
            prefix = self.config.command_prefix
        else:
            prefix = self.server_data[guild.id].command_prefix
        # Its OK to skip unicode emoji here, they render correctly inside of code boxes.
        emoji_regex = re.compile(r"^(<a?:.+:\d+>|:.+:)$")
        if emoji_regex.match(prefix):
            is_emoji = True

        def _get_aliases(cmd: str) -> str:
            aliases = ""
            if cmd and self.config.usealias:
                alias_list = self.aliases.for_command(cmd)
                if alias_list:
                    aliases = _D("**Aliases for this command:**\n", ssd_)
                    for alias in alias_list:
                        aliases += _D(
                            "`%(alias)s` alias of `%(command)s %(args)s`\n",
                            ssd_,
                        ) % {
                            "alias": alias[0],
                            "command": cmd,
                            "args": alias[1],
                        }
            return aliases

        if command:
            if command.lower() == "all":
                is_all = True
                commands = await self.gen_cmd_list(message, list_all_cmds=True)

            else:
                a_command = command
                cmd = getattr(self, "cmd_" + command, None)
                # check for aliases if natural command is not found.
                if not cmd and self.config.usealias:
                    a_command, alias_arg_str = self.aliases.from_alias(command)
                    cmd = getattr(self, "cmd_" + a_command, None)
                    if cmd:
                        alias_of = " ".join([a_command, alias_arg_str]).strip()

                aid = message.author.id
                if cmd and (
                    not hasattr(cmd, "dev_cmd")
                    or self.config.owner_id == aid
                    or aid in self.config.dev_ids
                ):
                    alias_usage = ""
                    if alias_of:
                        alias_usage = _D(
                            "**Alias of command:**\n  `%(command)s`\n", ssd_
                        ) % {
                            "command": alias_of,
                        }

                    return Response(
                        # TRANSLATORS: template string for command-specific help output.
                        _D("%(is_alias)s\n%(docs)s\n%(alias_list)s", ssd_)
                        % {
                            "is_alias": alias_usage,
                            "docs": await self.gen_cmd_help(a_command, guild),
                            "alias_list": _get_aliases(a_command),
                        },
                        delete_after=self.config.delete_delay_long,
                    )

                raise exceptions.CommandError("No such command")

        elif message.author.id == self.config.owner_id:
            commands = await self.gen_cmd_list(message, list_all_cmds=True)

        else:
            commands = await self.gen_cmd_list(message)

        example_help_cmd = f"`{prefix}help [COMMAND]`"
        example_help_all = f"`{prefix}help all`"
        if is_emoji:
            example_help_cmd = f"{prefix}`help [COMMAND]`"
            example_help_all = f"{prefix}`help all`"
        else:
            prefix = f"`{prefix}`"

        all_note = ""
        if not is_all:
            all_note = _D(
                "The list above shows only commands permitted for your use.\n"
                "For a list of all commands, run: %(example_all)s\n",
                ssd_,
            ) % {"example_all": example_help_all}

        desc = _D(
            "**Commands by name:** *(without prefix)*\n"
            "```\n%(command_list)s\n```\n"
            "**Command Prefix:** %(prefix)s\n\n"
            "For help with a particular command, run: %(example_command)s\n"
            "%(all_note)s",
            ssd_,
        ) % {
            "command_list": ", ".join(commands),
            "prefix": prefix,
            "example_command": example_help_cmd,
            "all_note": all_note,
        }

        return Response(desc, delete_after=self.config.delete_delay_long)

    @command_helper(
        # fmt: off
        usage=[
            "{cmd} add <@USER>\n"
            + _Dd("    Block a mentioned user."),

            "{cmd} remove <@USER>\n"
            + _Dd("    Unblock a mentioned user."),

            "{cmd} status <@USER>\n"
            + _Dd("    Show the block status of a mentioned user."),
        ],
        # fmt: on
        desc=_Dd(
            "Manage the users in the user block list.\n"
            "Blocked users are forbidden from using all bot commands.\n"
        ),
        remap_subs={"+": "add", "-": "remove", "?": "status"},
    )
    async def cmd_blockuser(
        self,
        ssd_: Optional[GuildSpecificData],
        user_mentions: UserMentions,
        option: str,
        leftover_args: List[str],
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}blockuser [add | remove | status] @UserName [@UserName2 ...]

        Manage users in the block list.
        Blocked users are forbidden from using all bot commands.
        """

        if not user_mentions and not leftover_args:
            raise exceptions.CommandError(
                "You must mention a user or provide their ID number.",
            )

        if option not in ["+", "-", "?", "add", "remove", "status"]:
            raise exceptions.CommandError(
                "Invalid sub-command given. Use `help blockuser` for usage examples."
            )

        for p_user in leftover_args:
            if p_user.isdigit():
                u = self.get_user(int(p_user))
                if u:
                    user_mentions.append(u)

        if not user_mentions:
            raise exceptions.CommandError(
                "MusicBot could not find the user(s) you specified.",
            )

        for user in user_mentions.copy():
            if option in ["+", "add"] and self.config.user_blocklist.is_blocked(user):
                if user.id == self.config.owner_id:
                    raise exceptions.CommandError(
                        "The owner cannot be added to the block list."
                    )

                log.info(
                    "Not adding user to block list, already blocked:  %(id)s/%(name)s",
                    {"id": user.id, "name": user.name},
                )
                user_mentions.remove(user)

            if option in ["-", "remove"] and not self.config.user_blocklist.is_blocked(
                user
            ):
                log.info(
                    "Not removing user from block list, not listed:  %(id)s/%(name)s",
                    {"id": user.id, "name": user.name},
                )
                user_mentions.remove(user)

        # allow management regardless, but tell the user if it will apply.
        if self.config.user_blocklist_enabled:
            status_msg = _D("User block list is currently enabled.", ssd_)
        else:
            status_msg = _D("User block list is currently disabled.", ssd_)

        old_len = len(self.config.user_blocklist)
        user_ids = {str(user.id) for user in user_mentions}

        if option in ["+", "add"]:
            if not user_mentions:
                raise exceptions.CommandError(
                    "Cannot add the users you listed, they are already added."
                )

            async with self.aiolocks["user_blocklist"]:
                self.config.user_blocklist.append_items(user_ids)

            n_users = len(self.config.user_blocklist) - old_len
            return Response(
                _D(
                    "%(number)s user(s) have been added to the block list.\n"
                    "%(status)s",
                    ssd_,
                )
                % {
                    "number": n_users,
                    "status": status_msg,
                }
            )

        if self.config.user_blocklist.is_disjoint(user_mentions):
            return Response(_D("None of those users are in the blacklist.", ssd_))

        if option in ["?", "status"]:
            ustatus = ""
            for user in user_mentions:
                blocked = _D("User: `%(user)s` is not blocked.\n", ssd_)
                if self.config.user_blocklist.is_blocked(user):
                    blocked = _D("User: `%(user)s` is blocked.\n", ssd_)
                ustatus += blocked % {"user": user.name}
            return Response(
                _D("**Block list status:**\n%(status)s\n%(users)s", ssd_)
                % {"status": status_msg, "users": ustatus},
            )

        async with self.aiolocks["user_blocklist"]:
            self.config.user_blocklist.remove_items(user_ids)

        n_users = old_len - len(self.config.user_blocklist)
        return Response(
            _D(
                "%(number)s user(s) have been removed from the block list.\n%(status)s",
                ssd_,
            )
            % {"number": n_users, "status": status_msg}
        )

    @command_helper(
        usage=["{cmd} <add | remove> [SUBJECT]\n"],
        desc=_Dd(
            "Manage a block list applied to song requests and extracted song data.\n"
            "A subject may be a song URL or a word or phrase found in the track title.\n"
            "If subject is omitted, any currently playing track URL will be added instead.\n"
            "\n"
            "The song block list matches loosely, but is case-sensitive.\n"
            "This means adding 'Pie' will match 'cherry Pie' but not 'piecrust' in checks.\n"
        ),
        remap_subs={"+": "add", "-": "remove"},
    )
    async def cmd_blocksong(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        _player: Optional[MusicPlayer],
        option: str,
        leftover_args: List[str],
        song_subject: str = "",
    ) -> CommandResponse:
        """
        Command for managing the song block list.
        """
        if leftover_args:
            song_subject = " ".join([song_subject, *leftover_args])

        if not song_subject:
            valid_url = self._get_song_url_or_none(song_subject, _player)
            if not valid_url:
                raise exceptions.CommandError(
                    "You must provide a song subject if no song is currently playing.",
                )
            song_subject = valid_url

        if option not in ["+", "-", "add", "remove"]:
            raise exceptions.CommandError(
                "Invalid sub-command given. Use `help blocksong` for usage examples."
            )

        # allow management regardless, but tell the user if it will apply.
        if self.config.song_blocklist_enabled:
            status_msg = "Song block list is currently enabled."
        else:
            status_msg = "Song block list is currently disabled."

        if option in ["+", "add"]:
            if self.config.song_blocklist.is_blocked(song_subject):
                raise exceptions.CommandError(
                    "Subject `%(subject)s` is already in the song block list.",
                    fmt_args={"subject": song_subject},
                )

            # remove song from auto-playlist if it is blocked
            if (
                self.config.auto_playlist_remove_on_block
                and _player
                and _player.current_entry
                and song_subject == _player.current_entry.url
                and _player.current_entry.from_auto_playlist
            ):
                await self.server_data[guild.id].autoplaylist.remove_track(
                    song_subject,
                    ex=UserWarning("Removed and added to block list."),
                    delete_from_ap=True,
                )

            async with self.aiolocks["song_blocklist"]:
                self.config.song_blocklist.append_items([song_subject])

            return Response(
                _D(
                    "Added subject `%(subject)s` to the song block list.\n%(status)s",
                    ssd_,
                )
                % {"subject": song_subject, "status": status_msg}
            )

        # handle "remove" and "-"
        if not self.config.song_blocklist.is_blocked(song_subject):
            raise exceptions.CommandError(
                "The subject is not in the song block list and cannot be removed.",
            )

        async with self.aiolocks["song_blocklist"]:
            self.config.song_blocklist.remove_items([song_subject])

        return Response(
            _D(
                "Subject `%(subject)s` has been removed from the block list.\n%(status)s",
                ssd_,
            )
            % {"subject": song_subject, "status": status_msg}
        )

    @command_helper(
        # fmt: off
        usage=[
            "{cmd} <add | remove> [URL]\n"
            + _Dd("    Adds or removes the specified song or currently playing song to/from the current playlist.\n"),

            "{cmd} add all\n"
            + _Dd("    Adds the entire queue to the guilds playlist.\n"),

            "{cmd} queue [NAME]\n"
            + _Dd(
                "    Add all tracks in the given auto playlist to the normal playback queue.\n"
                "    If playlist name is omitted, the currently loaded playlist is used.\n"
            ),

            "{cmd} clear [NAME]\n"
            + _Dd(
                "    Clear all songs from the named playlist file.\n"
                "    If playlist name is omitted, the currently loaded playlist is emptied.\n"
            ),

            "{cmd} show\n"
            + _Dd("    Show the currently selected playlist and a list of existing playlist files.\n"),

            "{cmd} restart\n"
            + _Dd(
                "    Reload the auto playlist queue, restarting at the first track unless randomized.\n"
            ),

            "{cmd} set <NAME>\n"
            + _Dd("    Set a playlist as default for this guild and reloads the guild auto playlist.\n"),

            "{cmd} reload [NAME]\n"
            + _Dd(
                "    Reload the given playlist from disk into memory, but does not update the current auto playlist queue."
            ),
        ],
        # fmt: on
        desc=_Dd(
            "Manage auto playlist files and per-guild settings.\n"
            "Auto playlists use a their own queue, only playing when the main queue is empty."
        ),
        remap_subs={"+": "add", "-": "remove"},
    )
    async def cmd_autoplaylist(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        author: discord.Member,
        channel: GuildMessageableChannels,
        voice_channel: Optional[VoiceableChannel],
        message: discord.Message,
        _player: Optional[MusicPlayer],
        player: MusicPlayer,
        option: str,
        opt_url: str = "",
    ) -> CommandResponse:
        """
        Manage auto playlists globally and per-guild.
        """
        option = option.lower()
        if option not in [
            "+",
            "-",
            "add",
            "remove",
            "clear",
            "show",
            "set",
            "restart",
            "queue",
            "reload",
        ]:
            raise exceptions.CommandError(
                "Invalid sub-command given. Use `help autoplaylist` for usage examples.",
            )

        def _get_url() -> str:
            url = self._get_song_url_or_none(opt_url, _player)

            if not url:
                raise exceptions.CommandError("The supplied song link is invalid")
            return url

        if option in ["+", "add"] and opt_url.lower() == "all":
            if not player.playlist.entries:
                raise exceptions.CommandError(
                    "The queue is empty. Add some songs with a play command!",
                )

            added_songs = set()
            for e in player.playlist.entries:
                if e.url not in self.server_data[guild.id].autoplaylist:
                    await self.server_data[guild.id].autoplaylist.add_track(e.url)
                    added_songs.add(e.url)

            if not added_songs:
                return Response(
                    _D("All songs in the queue are already in the autoplaylist.", ssd_)
                )

            return Response(
                _D("Added %(number)d songs to the autoplaylist.", ssd_)
                % {"number": len(added_songs)},
            )

        if option in ["+", "add"]:
            url = _get_url()
            self._do_song_blocklist_check(url)
            if url not in self.server_data[guild.id].autoplaylist:
                await self.server_data[guild.id].autoplaylist.add_track(url)
                return Response(
                    _D("Added `%(url)s` to the autoplaylist.", ssd_) % {"url": url},
                )
            raise exceptions.CommandError(
                "This song is already in the autoplaylist.",
            )

        if option in ["-", "remove"]:
            url = _get_url()
            if url in self.server_data[guild.id].autoplaylist:
                await self.server_data[guild.id].autoplaylist.remove_track(
                    url,
                    ex=UserWarning(
                        f"Removed by command from user:  {author.id}/{author.name}#{author.discriminator}"
                    ),
                    delete_from_ap=True,
                )
                return Response(
                    _D("Removed `%(url)s` from the autoplaylist.", ssd_) % {"url": url},
                )
            raise exceptions.CommandError(
                "This song is not yet in the autoplaylist.",
            )

        if option == "restart":
            apl = self.server_data[guild.id].autoplaylist
            await apl.load(force=True)
            player.autoplaylist = list(apl)
            return Response(
                _D(
                    "Loaded a fresh copy of the playlist: `%(file)s`",
                    ssd_,
                )
                % {"file": apl.filename}
            )

        if option == "show":
            self.playlist_mgr.discover_playlists()
            filename = " "
            if ssd_:
                filename = ssd_.autoplaylist.filename
            names = "\n".join([f"`{pl}`" for pl in self.playlist_mgr.playlist_names])
            return Response(
                _D(
                    "**Current Playlist:** `%(playlist)s`"
                    "**Available Playlists:**\n%(names)s",
                    ssd_,
                )
                % {"playlist": filename, "names": names},
                delete_after=self.config.delete_delay_long,
            )

        if option == "set":
            if not opt_url:
                raise exceptions.CommandError(
                    "You must provide a playlist filename.",
                )

            # Add file extension if one was not given.
            if not opt_url.lower().endswith(".txt"):
                opt_url += ".txt"

            # Update the server specific data.
            pl = self.playlist_mgr.get_playlist(opt_url)
            self.server_data[guild.id].autoplaylist = pl
            await self.server_data[guild.id].save_guild_options_file()
            await pl.load()

            # Update the player copy if needed.
            if _player and self.config.auto_playlist:
                _player.autoplaylist = list(pl)

            new_msg = ""
            if not self.playlist_mgr.playlist_exists(opt_url):
                new_msg = _D(
                    "\nThis playlist is new, you must add songs to save it to disk!",
                    ssd_,
                )
            return Response(
                _D(
                    "The playlist for this server has been updated to: `%(name)s`%(note)s",
                    ssd_,
                )
                % {"name": opt_url, "note": new_msg},
            )

        if option == "clear":
            if not opt_url and ssd_:
                plname = ssd_.autoplaylist.filename
            else:
                plname = opt_url.lower()
                if not plname.endswith(".txt"):
                    plname += ".txt"
                if not self.playlist_mgr.playlist_exists(plname):
                    raise exceptions.CommandError(
                        "No playlist file exists with the name: `%(playlist)s`",
                        fmt_args={"playlist": plname},
                    )
            pl = self.playlist_mgr.get_playlist(plname)
            await pl.clear_all_tracks(f"Playlist was cleared by user: {author}")
            return Response(
                _D("The playlist `%(playlist)s` has been cleared.", ssd_)
                % {"playlist": plname}
            )

        if option == "queue":
            if not voice_channel:
                raise exceptions.CommandError(
                    "You must be in a voice channel to use this command."
                )
            if not opt_url and ssd_:
                plname = ssd_.autoplaylist.filename
            else:
                plname = opt_url.lower()
                if not plname.endswith(".txt"):
                    plname += ".txt"
                if not self.playlist_mgr.playlist_exists(plname):
                    raise exceptions.CommandError(
                        "No playlist file exists with the name: `%(playlist)s`",
                        fmt_args={"playlist": plname},
                    )

            premsg = _D(
                "The tracks in playlist `%(playlist)s` will be added to the queue.\n"
                "Please wait while MusicBot processes the playlist.",
                ssd_,
            ) % {"playlist": plname}
            await self.safe_send_message(
                channel,
                Response(premsg, reply_to=message),
            )

            try:
                info = await self.downloader.extract_info(
                    f"mbapl://{plname}", download=False, process=True
                )
            except Exception as e:
                # TODO: i18n for translated exceptions.
                info = None
                log.exception("Issue with extract_info(): ")
                if isinstance(e, exceptions.MusicbotException):
                    raise
                raise exceptions.CommandError(
                    "Failed to extract info due to error:\n%(raw_error)s",
                    fmt_args={"raw_error": e},
                ) from e

            entries: List[EntryTypes] = []
            if info:
                _player = self.get_player_in(guild)
                if _player is None:
                    player = await self.get_player(voice_channel, create=True)
                else:
                    player = _player
                entries, _pos = await player.playlist.import_from_info(
                    info,
                    head=False,
                    channel=channel,
                    author=author,
                )
                if len(entries) and player.is_stopped:
                    player.play()

            return Response(
                _D(
                    "Added %(number)d track(s) to the queue from playlist `%(playlist)s`",
                    ssd_,
                )
                % {"number": len(entries), "playlist": plname}
            )

        if option == "reload":
            if not opt_url and ssd_:
                plname = ssd_.autoplaylist.filename
            else:
                plname = opt_url.lower()
                if not plname.endswith(".txt"):
                    plname += ".txt"
                if not self.playlist_mgr.playlist_exists(plname):
                    raise exceptions.CommandError(
                        "No playlist file exists with the name: `%(playlist)s`",
                        fmt_args={"playlist": plname},
                    )
            await self.playlist_mgr.get_playlist(plname).load()
            return Response(_D("The playlist has been reloaded from disk.", ssd_))

        return None

    @owner_only
    @command_helper(
        desc=_Dd(
            "Generate an invite link that can be used to add this bot to another server."
        ),
        allow_dm=True,
    )
    async def cmd_joinserver(
        self, ssd_: Optional[GuildSpecificData]
    ) -> CommandResponse:
        """
        Generate an oauth invite link for the bot in chat.
        """
        url = await self.generate_invite_link()
        return Response(
            _D("Click here to add me to a discord server:\n%(url)s", ssd_)
            % {"url": url},
        )

    @command_helper(
        desc=_Dd(
            "Toggle karaoke mode on or off. While enabled, only karaoke members may queue songs.\n"
            "Groups with BypassKaraokeMode permission control which members are Karaoke members.\n"
        )
    )
    async def cmd_karaoke(
        self, ssd_: Optional[GuildSpecificData], player: MusicPlayer
    ) -> CommandResponse:
        """
        Toggle the player's karaoke mode.
        """
        player.karaoke_mode = not player.karaoke_mode
        if player.karaoke_mode:
            return Response(_D("\N{OK HAND SIGN} Karaoke mode is now enabled.", ssd_))
        return Response(
            _D("\N{OK HAND SIGN} Karaoke mode is now disabled.", ssd_),
        )

    async def _do_playlist_checks(
        self,
        player: MusicPlayer,
        author: discord.Member,
        result_info: "downloader.YtdlpResponseDict",
    ) -> bool:
        """
        Check if the given `author` has permissions to play the entries
        in `result_info` or not.

        :returns:  True is allowed to continue.
        :raises:  PermissionsError  if permissions deny the playlist.
        """
        num_songs = result_info.playlist_count or result_info.entry_count
        permissions = self.permissions.for_user(author)

        # TODO: correct the language here, since this could be playlist or search results?
        # I have to do extra checks anyways because you can request an arbitrary number of search results
        if not permissions.allow_playlists and num_songs > 1:
            raise exceptions.PermissionsError(
                "You are not allowed to request playlists"
            )

        if (
            permissions.max_playlist_length
            and num_songs > permissions.max_playlist_length
        ):
            raise exceptions.PermissionsError(
                "Playlist has too many entries (%(songs)s but max is %(max)s)",
                fmt_args={"songs": num_songs, "max": permissions.max_playlist_length},
            )

        # This is a little bit weird when it says (x + 0 > y), I might add the other check back in
        if (
            permissions.max_songs
            and player.playlist.count_for_user(author) + num_songs
            > permissions.max_songs
        ):
            raise exceptions.PermissionsError(
                "The playlist entries will exceed your queue limit.\n"
                "There are %(songs)s in the list, and %(queued)s already in queue.\n"
                "The limit is %(max)s for your group.",
                fmt_args={
                    "songs": num_songs,
                    "queued": player.playlist.count_for_user(author),
                    "max": permissions.max_songs,
                },
            )
        return True

    async def _handle_guild_auto_pause(self, player: MusicPlayer, _lc: int = 0) -> None:
        """
        Check the current voice client channel for members and determine
        if the player should be paused automatically.
        This is distinct from Guild availability pausing, which happens
        when Discord or the network has outages.
        """
        if not self.config.auto_pause:
            if player.paused_auto:
                player.paused_auto = False
            return

        if self.network_outage:
            log.debug("Ignoring auto-pause due to network outage.")
            return

        if not player.voice_client or not player.voice_client.channel:
            log.voicedebug(  # type: ignore[attr-defined]
                "MusicPlayer has no VoiceClient or has no channel data, cannot process auto-pause."
            )
            if player.paused_auto:
                player.paused_auto = False
            return

        channel = player.voice_client.channel
        guild = channel.guild

        lock = self.aiolocks[f"auto_pause:{guild.id}"]
        if lock.locked():
            log.debug("Already processing auto-pause, ignoring this event.")
            return

        async with lock:
            if not player.voice_client.is_connected():
                if self.loop:
                    naptime = 3 * (1 + _lc)
                    log.warning(
                        "%sVoiceClient not connected, waiting %s seconds to handle auto-pause in guild:  %s",
                        "[Bug] " if _lc > 12 else "",
                        naptime,
                        player.voice_client.guild,
                    )
                    try:
                        await asyncio.sleep(naptime)
                    except asyncio.CancelledError:
                        log.debug("Auto-pause waiting was cancelled.")
                        return

                    _lc += 1
                    f_player = self.get_player_in(player.voice_client.guild)
                    if player != f_player:
                        log.info(
                            "A new MusicPlayer is being connected, ignoring old auto-pause event."
                        )
                        return

                    if f_player is not None:
                        self.create_task(
                            self._handle_guild_auto_pause(f_player, _lc=_lc),
                            name="MB_HandleGuildAutoPause",
                        )
                return

        is_empty = is_empty_voice_channel(
            channel, include_bots=self.config.bot_exception_ids
        )
        if is_empty and player.is_playing:
            log.info(
                "Playing in an empty voice channel, running auto pause for guild: %s",
                guild,
            )
            player.pause()
            player.paused_auto = True

        elif not is_empty and player.paused_auto:
            log.info("Previously auto paused player is unpausing for guild: %s", guild)
            player.paused_auto = False
            if player.is_paused:
                player.resume()

    async def _do_cmd_unpause_check(
        self,
        player: Optional[MusicPlayer],
        channel: MessageableChannel,
        author: discord.Member,
        message: discord.Message,
    ) -> None:
        """
        Checks for paused player and resumes it while sending a notice.

        This function should not be called from _cmd_play().
        """
        if not self.config.auto_unpause_on_play:
            return

        if not player or not player.voice_client or not player.voice_client.channel:
            return

        if not author.voice or not author.voice.channel:
            return

        # TODO: check this
        if player and player.voice_client and player.voice_client.channel:
            pvc = player.voice_client.channel
            avc = author.voice.channel
            perms = self.permissions.for_user(author)
            ssd = None
            if channel.guild:
                ssd = self.server_data[channel.guild.id]
            if pvc != avc and perms.summonplay:
                await self.cmd_summon(ssd, author.guild, author, message)
                return

            if pvc != avc and not perms.summonplay:
                return

        if player and player.is_paused:
            player.resume()
            await self.safe_send_message(
                channel,
                Response(
                    _D(
                        "Bot was previously paused, resuming playback now.",
                        self.server_data[player.voice_client.channel.guild.id],
                    )
                ),
            )

    @command_helper(
        usage=["{cmd} <URL | SEARCH>"],
        desc=_Dd(
            "Add a song to be played in the queue. If no song is playing or paused, playback will be started.\n"
            "\n"
            "You may supply a URL to a video or audio file or the URL of a service supported by yt-dlp.\n"
            "Playlist links will be extracted into multiple links and added to the queue.\n"
            "If you enter a non-URL, the input will be used as search criteria on YouTube and the first result played.\n"
            "MusicBot also supports Spotify URIs and URLs, but audio is fetched from YouTube regardless.\n"
        ),
    )
    async def cmd_play(
        self,
        message: discord.Message,
        player: MusicPlayer,
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
        song_url: str,
    ) -> CommandResponse:
        """
        The default play command logic.
        """
        await self._do_cmd_unpause_check(player, channel, author, message)

        return await self._cmd_play(
            message,
            player,
            channel,
            guild,
            author,
            permissions,
            leftover_args,
            song_url,
            head=False,
        )

    @command_helper(
        usage=["{cmd} [URL]"],
        desc=_Dd(
            "Play command that shuffles playlist entries before adding them to the queue.\n"
        ),
    )
    async def cmd_shuffleplay(
        self,
        ssd_: Optional[GuildSpecificData],
        message: discord.Message,
        player: MusicPlayer,
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
        song_url: str,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}shuffleplay playlist_link

        Like play command but explicitly shuffles entries before adding them to the queue.
        """
        await self._do_cmd_unpause_check(player, channel, author, message)

        await self._cmd_play(
            message,
            player,
            channel,
            guild,
            author,
            permissions,
            leftover_args,
            song_url,
            head=False,
            shuffle_entries=True,
        )

        return Response(
            _D("Shuffled playlist items into the queue from `%(request)s`", ssd_)
            % {"request": song_url},
        )

    @command_helper(
        usage=["{cmd} <URL | SEARCH>"],
        desc=_Dd(
            "A play command that adds the song as the next to play rather than last.\n"
            "Read help for the play command for information on supported inputs.\n"
        ),
    )
    async def cmd_playnext(
        self,
        message: discord.Message,
        player: MusicPlayer,
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
        song_url: str,
    ) -> CommandResponse:
        """
        Add a song directly as the next entry in the queue, if one is playing.
        """
        await self._do_cmd_unpause_check(player, channel, author, message)

        return await self._cmd_play(
            message,
            player,
            channel,
            guild,
            author,
            permissions,
            leftover_args,
            song_url,
            head=True,
        )

    @command_helper(
        usage=["{cmd} <URL | SEARCH>"],
        desc=_Dd(
            "A play command which skips any current song and plays immediately.\n"
            "Read help for the play command for information on supported inputs.\n"
        ),
    )
    async def cmd_playnow(
        self,
        message: discord.Message,
        player: MusicPlayer,
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
        song_url: str,
    ) -> CommandResponse:
        """
        Play immediately, skip any playing track.  Don't check skip perms.
        """
        await self._do_cmd_unpause_check(player, channel, author, message)

        # attempt to queue the song, but used the front of the queue and skip current playback.
        return await self._cmd_play(
            message,
            player,
            channel,
            guild,
            author,
            permissions,
            leftover_args,
            song_url,
            head=True,
            skip_playing=True,
        )

    @command_helper(
        usage=["{cmd} <TIME>"],
        desc=_Dd(
            "Restarts the current song at the given time.\n"
            "If time starts with + or - seek will be relative to current playback time.\n"
            "Time should be given in seconds, fractional seconds are accepted.\n"
            "Due to codec specifics in ffmpeg, this may not be accurate.\n"
        ),
    )
    async def cmd_seek(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        player: MusicPlayer,
        leftover_args: List[str],
        seek_time: str = "",
    ) -> CommandResponse:
        """
        Allows for playback seeking functionality in non-streamed entries.
        """
        # TODO: perhaps a means of listing chapters and seeking to them. like `seek ch1` & `seek list`
        if not player or not player.current_entry:
            raise exceptions.CommandError(
                "Cannot use seek if there is nothing playing.",
            )

        if player.current_entry.duration is None:
            raise exceptions.CommandError(
                "Cannot use seek on current track, it has an unknown duration.",
            )

        if not isinstance(
            player.current_entry, (URLPlaylistEntry, LocalFilePlaylistEntry)
        ):
            raise exceptions.CommandError("Seeking is not supported for streams.")

        # take in all potential arguments.
        if leftover_args:
            args = leftover_args
            args.insert(0, seek_time)
            seek_time = " ".join(args)

        if not seek_time:
            raise exceptions.CommandError(
                "Cannot use seek without a time to position playback.",
            )

        relative_seek: int = 0
        f_seek_time: float = 0
        if seek_time.startswith("-"):
            relative_seek = -1
        if seek_time.startswith("+"):
            relative_seek = 1

        if "." in seek_time:
            try:
                p1, p2 = seek_time.rsplit(".", maxsplit=1)
                i_seek_time = format_time_to_seconds(p1)
                f_seek_time = float(f"0.{p2}")
                f_seek_time += i_seek_time
            except (ValueError, TypeError) as e:
                raise exceptions.CommandError(
                    "Could not convert `%(input)s` to a valid time in seconds.",
                    fmt_args={"input": seek_time},
                ) from e
        else:
            f_seek_time = 0.0 + format_time_to_seconds(seek_time)

        if relative_seek != 0:
            f_seek_time = player.progress + (relative_seek * f_seek_time)

        if f_seek_time > player.current_entry.duration or f_seek_time < 0:
            td = format_song_duration(player.current_entry.duration_td)
            prog = format_song_duration(player.progress)
            raise exceptions.CommandError(
                "Cannot seek to `%(input)s` (`%(seconds)s` seconds) in the current track with a length of `%(progress)s / %(total)s`",
                fmt_args={
                    "input": seek_time,
                    "seconds": f"{f_seek_time:.2f}",
                    "progress": prog,
                    "total": td,
                },
            )

        entry = player.current_entry
        entry.set_start_time(f_seek_time)
        player.playlist.insert_entry_at_index(0, entry)

        # handle history playlist updates.
        if (
            self.config.enable_queue_history_global
            or self.config.enable_queue_history_guilds
        ):
            self.server_data[guild.id].current_playing_url = ""

        player.skip()

        return Response(
            _D(
                "Seeking to time `%(input)s` (`%(seconds).2f` seconds) in the current song.",
                ssd_,
            )
            % {
                "input": seek_time,
                "seconds": f_seek_time,
            },
        )

    @command_helper(
        usage=["{cmd} [all | song | playlist | on | off]"],
        desc=_Dd(
            "Toggles playlist or song looping.\n"
            "If no option is provided the current song will be repeated.\n"
            "If no option is provided and the song is already repeating, repeating will be turned off.\n"
        ),
    )
    async def cmd_repeat(
        self, ssd_: Optional[GuildSpecificData], player: MusicPlayer, option: str = ""
    ) -> CommandResponse:
        """
        switch through the various repeat modes.
        """
        # TODO: this command needs TLC.

        option = option.lower() if option else ""

        if not player.current_entry:
            return Response(
                _D(
                    "No songs are currently playing. Play something with a play command.",
                    ssd_,
                )
            )

        if option not in ["all", "playlist", "on", "off", "song", ""]:
            raise exceptions.CommandError(
                "Invalid sub-command. Use the command `help repeat` for usage examples.",
            )

        if option in ["all", "playlist"]:
            player.loopqueue = not player.loopqueue
            if player.loopqueue:
                return Response(_D("Playlist is now repeating.", ssd_))

            return Response(
                _D("Playlist is no longer repeating.", ssd_),
            )

        if option == "song":
            player.repeatsong = not player.repeatsong
            if player.repeatsong:
                return Response(_D("Player will now loop the current song.", ssd_))

            return Response(_D("Player will no longer loop the current song.", ssd_))

        if option == "on":
            if player.repeatsong:
                return Response(_D("Player is already looping a song!", ssd_))

            player.repeatsong = True
            return Response(_D("Player will now loop the current song.", ssd_))

        if option == "off":
            # TODO: This will fail to behave is both are somehow on.
            if player.repeatsong:
                player.repeatsong = False
                return Response(
                    _D("Player will no longer loop the current song.", ssd_)
                )

            if player.loopqueue:
                player.loopqueue = False
                return Response(_D("Playlist is no longer repeating.", ssd_))

            raise exceptions.CommandError("The player is not currently looping.")

        if player.repeatsong:
            player.loopqueue = True
            player.repeatsong = False
            return Response(_D("Playlist is now repeating.", ssd_))

        if player.loopqueue:
            if len(player.playlist.entries) > 0:
                message = _D("Playlist is no longer repeating.", ssd_)
            else:
                message = _D("Song is no longer repeating.", ssd_)
            player.loopqueue = False
        else:
            player.repeatsong = True
            message = _D("Song is now repeating.", ssd_)

        return Response(message)

    @command_helper(
        # fmt: off
        usage=[
            "{cmd} <FROM> <TO>\n"
            + _Dd("    Move song at position FROM to position TO.\n"),
        ],
        # fmt: on
        desc=_Dd(
            "Swap existing songs in the queue using their position numbers.\n"
            "Use the queue command to find track position numbers.\n"
        ),
    )
    async def cmd_move(
        self,
        ssd_: Optional[GuildSpecificData],
        player: MusicPlayer,
        guild: discord.Guild,
        channel: MessageableChannel,
        command: str,
        leftover_args: List[str],
    ) -> CommandResponse:
        """
        Swaps the location of a song within the playlist.
        """
        if not player.current_entry:
            return Response(
                _D(
                    "There are no songs queued. Play something with a play command.",
                    ssd_,
                ),
            )

        indexes = []
        try:
            indexes.append(int(command) - 1)
            indexes.append(int(leftover_args[0]) - 1)
        except (ValueError, IndexError) as e:
            raise exceptions.CommandError("Song positions must be integers!") from e

        for i in indexes:
            if i < 0 or i > len(player.playlist.entries) - 1:
                raise exceptions.CommandError(
                    "You gave a position outside the playlist size!"
                )

        await self.safe_send_message(
            channel,
            Response(
                _D(
                    "Successfully moved song from position %(from)s in queue to position %(to)s!",
                    self.server_data[guild.id],
                )
                % {"from": indexes[0] + 1, "to": indexes[1] + 1},
            ),
        )

        song = player.playlist.delete_entry_at_index(indexes[0])

        player.playlist.insert_entry_at_index(indexes[1], song)
        return None

    # Not a command :)
    async def _cmd_play_compound_link(
        self,
        ssd_: Optional[GuildSpecificData],
        message: discord.Message,
        player: MusicPlayer,
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
        song_url: str,
        head: bool,
    ) -> None:
        """
        Helper function to check for playlist IDs embedded in video links.
        If a "compound" URL is detected, ask the user if they want the
        associated playlist to be queued as well.
        """
        # TODO: maybe add config to auto yes or no and bypass this.

        async def _prompt_for_playing(
            prompt: str, next_url: str, ignore_vid: str = ""
        ) -> None:
            msg = await self.safe_send_message(
                channel, Response(prompt, delete_after=self.config.delete_delay_long)
            )
            if not msg:
                log.warning(
                    "Could not prompt for playlist playback, no message to add reactions to."
                )
                return

            for r in [EMOJI_CHECK_MARK_BUTTON, EMOJI_CROSS_MARK_BUTTON]:
                await msg.add_reaction(r)

            def _check_react(reaction: discord.Reaction, user: discord.Member) -> bool:
                return msg == reaction.message and author == user

            try:
                reaction, _user = await self.wait_for(
                    "reaction_add", timeout=60, check=_check_react
                )
                if reaction.emoji == EMOJI_CHECK_MARK_BUTTON:
                    await self._cmd_play(
                        message,
                        player,
                        channel,
                        guild,
                        author,
                        permissions,
                        leftover_args,
                        next_url,
                        head,
                        ignore_video_id=ignore_vid,
                    )
                    await self.safe_delete_message(msg)
                elif reaction.emoji == EMOJI_CROSS_MARK_BUTTON:
                    await self.safe_delete_message(msg)
            except asyncio.TimeoutError:
                await self.safe_delete_message(msg)

        # Check for playlist in youtube watch link.
        # https://youtu.be/VID?list=PLID
        # https://www.youtube.com/watch?v=VID&list=PLID
        playlist_regex = re.compile(
            r"(?:youtube.com/watch\?v=|youtu\.be/)([^?&]{6,})[&?]{1}(list=PL[^&]+)",
            re.I | re.X,
        )
        matches = playlist_regex.search(song_url)
        if matches:
            pl_url = "https://www.youtube.com/playlist?" + matches.group(2)
            ignore_vid = matches.group(1)
            self.create_task(
                _prompt_for_playing(
                    _D(
                        "This link contains a Playlist ID:\n"
                        "`%(url)s`\n\nDo you want to queue the playlist too?",
                        ssd_,
                    )
                    % {"url": song_url},
                    pl_url,
                    ignore_vid,
                )
            )

    # Not a command. :)
    async def _cmd_play(
        self,
        message: discord.Message,
        player: MusicPlayer,
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
        song_url: str,
        head: bool,
        shuffle_entries: bool = False,
        ignore_video_id: str = "",
        skip_playing: bool = False,
    ) -> CommandResponse:
        """
        This function handles actually adding any given URL or song subject to
        the player playlist if extraction was successful and various checks pass.

        :param: head:  Toggle adding the song(s) to the front of the queue, not the end.
        :param: shuffle_entries:  Shuffle entries before adding them to the queue.
        :param: ignore_video_id:  Ignores a video in a playlist if it has this ID.
        :param: skip_playing:  Skip current playback if a new entry is added.
        """
        ssd_ = self.server_data[guild.id]
        await channel.typing()

        if not self.config.enable_local_media and song_url.lower().startswith(
            "file://"
        ):
            raise exceptions.CommandError(
                "Local media playback is not enabled.",
            )

        # Validate song_url is actually a URL, or otherwise a search string.
        valid_song_url = self.downloader.get_url_or_none(song_url)
        if valid_song_url:
            song_url = valid_song_url
            self._do_song_blocklist_check(song_url)

            # Handle if the link has a playlist ID in addition to a video ID.
            await self._cmd_play_compound_link(
                ssd_,
                message,
                player,
                channel,
                guild,
                author,
                permissions,
                leftover_args,
                song_url,
                head,
            )

        if (
            not valid_song_url
            and leftover_args
            and not (
                self.config.enable_local_media
                and song_url.lower().startswith("file://")
            )
        ):
            # treat all arguments as a search string.
            song_url = " ".join([song_url, *leftover_args])
            leftover_args = []  # prevent issues later.
            self._do_song_blocklist_check(song_url)
            if song_url:
                song_url = f"{self.config.default_search_service}:{song_url}"

        # Validate spotify links are supported before we try them.
        if "open.spotify.com" in song_url.lower():
            if self.config.spotify_enabled:
                if not Spotify.is_url_supported(song_url):
                    raise exceptions.CommandError(
                        "Spotify URL is invalid or not currently supported."
                    )
            else:
                raise exceptions.CommandError(
                    "Detected a Spotify URL, but Spotify is not enabled."
                )

        # This lock prevent spamming play commands to add entries that exceeds time limit/ maximum song limit
        async with self.aiolocks[_func_() + ":" + str(author.id)]:
            if (
                permissions.max_songs
                and player.playlist.count_for_user(author) >= permissions.max_songs
            ):
                raise exceptions.PermissionsError(
                    "You have reached your enqueued song limit (%(max)s)",
                    fmt_args={"max": permissions.max_songs},
                )

            if player.karaoke_mode and not permissions.bypass_karaoke_mode:
                raise exceptions.PermissionsError(
                    "Karaoke mode is enabled, please try again when its disabled!",
                )

            # Get processed info from ytdlp
            info = None
            try:
                info = await self.downloader.extract_info(
                    song_url, download=False, process=True
                )
            except Exception as e:
                # TODO: i18n for translated exceptions.
                info = None
                log.exception("Issue with extract_info(): ")
                if isinstance(e, exceptions.MusicbotException):
                    raise
                raise exceptions.CommandError(
                    "Failed to extract info due to error:\n%(raw_error)s",
                    fmt_args={"raw_error": e},
                ) from e

            if not info:
                raise exceptions.CommandError(
                    "That video cannot be played. Try using the stream command.",
                )

            # ensure the extractor has been allowed via permissions.
            permissions.can_use_extractor(info.extractor)

            # if the result has "entries" but it's empty, it might be a failed search.
            if "entries" in info and not info.entry_count:
                if check_extractor(info.extractor, "youtube:search"):
                    # TOOD: UI, i18n stuff
                    raise exceptions.CommandError(
                        "YouTube search returned no results for:  %(url)s",
                        fmt_args={"url": song_url},
                    )

            # If the result has usable entries, we assume it is a playlist
            listlen = 1
            track_title = ""
            if info.has_entries:
                await self._do_playlist_checks(player, author, info)

                num_songs = info.playlist_count or info.entry_count

                if shuffle_entries:
                    random.shuffle(info["entries"])

                # TODO: I can create an event emitter object instead, add event functions, and every play list might be asyncified
                # Also have a "verify_entry" hook with the entry as an arg and returns the entry if its ok
                start_time = time.time()
                entry_list, position = await player.playlist.import_from_info(
                    info,
                    channel=channel,
                    author=author,
                    head=head,
                    ignore_video_id=ignore_video_id,
                )

                time_taken = time.time() - start_time
                listlen = len(entry_list)

                log.info(
                    "Processed %(number)d of %(total)d songs in %(time).3f seconds at %(time_per).2f s/song",
                    {
                        "number": listlen,
                        "total": num_songs,
                        "time": time_taken,
                        "time_per": time_taken / listlen if listlen else 1,
                    },
                )

                if not entry_list:
                    raise exceptions.CommandError(
                        "No songs were added, all songs were over max duration (%(max)s seconds)",
                        fmt_args={"max": permissions.max_song_length},
                    )

                reply_text = _D(
                    "Enqueued **%(number)s** songs to be played.\n"
                    "Position in queue: %(position)s",
                    ssd_,
                )

            # If it's an entry
            else:
                # youtube:playlist extractor but it's actually an entry
                # ^ wish I had a URL for this one.
                if info.get("extractor", "").startswith("youtube:playlist"):
                    log.noise(  # type: ignore[attr-defined]
                        "Extracted an entry with 'youtube:playlist' as extractor key"
                    )

                # Check the block list again, with the info this time.
                self._do_song_blocklist_check(info.url)
                self._do_song_blocklist_check(info.title)

                if (
                    permissions.max_song_length
                    and info.duration_td.seconds > permissions.max_song_length
                ):
                    raise exceptions.PermissionsError(
                        "Song duration exceeds limit (%(length)s > %(max)s)",
                        fmt_args={
                            "length": info.duration,
                            "max": permissions.max_song_length,
                        },
                    )

                entry, position = await player.playlist.add_entry_from_info(
                    info, channel=channel, author=author, head=head
                )

                reply_text = _D(
                    "Enqueued `%(track)s` to be played.\n"
                    "Position in queue: %(position)s",
                    ssd_,
                )
                track_title = _D(entry.title, ssd_)

            log.debug("Added song(s) at position %s", position)
            if position == 1 and player.is_stopped:
                pos_str = _D("Playing next!", ssd_)
                player.play()

            # shift the playing track to the end of queue and skip current playback.
            elif skip_playing and player.is_playing and player.current_entry:
                player.playlist.entries.append(player.current_entry)

                # handle history playlist updates.
                if (
                    self.config.enable_queue_history_global
                    or self.config.enable_queue_history_guilds
                ):
                    self.server_data[guild.id].current_playing_url = ""

                player.skip()
                pos_str = _D("Playing next!", ssd_)

            else:
                try:
                    time_until = await player.playlist.estimate_time_until(
                        position, player
                    )
                    pos_str = _D(
                        "%(position)s - estimated time until playing: `%(eta)s`",
                        ssd_,
                    ) % {
                        "position": position,
                        "eta": format_song_duration(time_until),
                    }
                except exceptions.InvalidDataError:
                    pos_str = _D(
                        "%(position)s - cannot estimate time until playing.",
                        ssd_,
                    ) % {"position": position}
                    log.warning(
                        "Cannot estimate time until playing for position: %d", position
                    )

        reply_text %= {
            "number": listlen,
            "track": track_title,
            "position": pos_str,
        }

        return Response(reply_text)

    @command_helper(
        usage=["{cmd} <URL>"],
        desc=_Dd(
            "Add a media URL to the queue as a Stream.\n"
            "The URL may be actual streaming media, like Twitch, Youtube, or a shoutcast like service.\n"
            "You can also use non-streamed media to play it without downloading it.\n"
            "Note: FFmpeg may drop the stream randomly or if connection hiccups happen.\n"
        ),
    )
    async def cmd_stream(
        self,
        ssd_: Optional[GuildSpecificData],
        player: MusicPlayer,
        channel: GuildMessageableChannels,
        author: discord.Member,
        permissions: PermissionGroup,
        message: discord.Message,
        song_url: str,
    ) -> CommandResponse:
        """
        Tries to add media to the queue as a stream entry type.
        """

        await self._do_cmd_unpause_check(player, channel, author, message)

        # TODO: make sure these permissions checks are used in all play* functions.
        if (
            permissions.max_songs
            and player.playlist.count_for_user(author) >= permissions.max_songs
        ):
            raise exceptions.PermissionsError(
                "You have reached your enqueued song limit (%(max)s)",
                fmt_args={"max": permissions.max_songs},
            )

        if player.karaoke_mode and not permissions.bypass_karaoke_mode:
            raise exceptions.PermissionsError(
                "Karaoke mode is enabled, please try again when its disabled!",
            )

        async with channel.typing():
            # TODO: find more streams to test.
            # NOTE: this will return a URL if one was given but ytdl doesn't support it.
            try:
                info = await self.downloader.extract_info(
                    song_url, download=False, process=True, as_stream=True
                )
            # TODO: i18n handle translation of exceptions
            except Exception as e:
                log.exception(
                    "Failed to get info from the stream request: %s", song_url
                )
                raise exceptions.CommandError(
                    "Failed to extract info due to error:\n%(raw_error)s",
                    fmt_args={"raw_error": e},
                ) from e

            if info.has_entries:
                raise exceptions.CommandError(
                    "Streaming playlists is not yet supported.",
                )
                # TODO: could process these and force them to be stream entries...

            self._do_song_blocklist_check(info.url)
            # if its a "forced stream" this would be a waste.
            if info.url != info.title:
                self._do_song_blocklist_check(info.title)

            await player.playlist.add_stream_from_info(
                info, channel=channel, author=author, head=False
            )

            if player.is_stopped:
                player.play()

        return Response(
            _D("Now streaming track `%(track)s`", ssd_) % {"track": info.title},
        )

    # TODO: cmd_streamnext maybe

    @command_helper(
        # fmt: off
        usage=[
            "{cmd} [SERVICE] [NUMBER] <QUERY>\n"
            + _Dd("    Search with service for a number of results with the search query.\n"),

            "{cmd} [NUMBER] \"<QUERY>\"\n"
            + _Dd(
                "    Search YouTube for query but get a custom number of results.\n"
                "    Note: the double-quotes are required in this case.\n"
            ),
        ],
        # fmt: on
        desc=_Dd(
            "Search a supported service and select from results to add to queue.\n"
            "Service and number arguments can be omitted, default number is 3 results.\n"
            "Select from these services:\n"
            "- yt, youtube (default)\n"
            "- sc, soundcloud\n"
            "- yh, yahoo\n"
            "- gv, google\n"
            "- nv, nico\n"
            "- bb, bili\n"
        ),
    )
    async def cmd_search(
        self,
        ssd_: Optional[GuildSpecificData],
        message: discord.Message,
        player: MusicPlayer,
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
    ) -> CommandResponse:
        """
        Facilitate search with yt-dlp and some select services.
        This starts an interactive message where reactions are used to navigate
        and select from the results.  Only the calling member may react.
        """

        if (
            permissions.max_songs
            and player.playlist.count_for_user(author) > permissions.max_songs
        ):
            raise exceptions.PermissionsError(
                "You have reached your playlist item limit (%(max)s)",
                fmt_args={"max": permissions.max_songs},
            )

        if player.karaoke_mode and not permissions.bypass_karaoke_mode:
            raise exceptions.PermissionsError(
                "Karaoke mode is enabled, please try again when its disabled!",
            )

        def argcheck() -> None:
            if not leftover_args:
                raise exceptions.CommandError(
                    "Please specify a search query.  Use `help search` for more information.",
                )

        argcheck()

        service = self.config.default_search_service
        items_requested = self.config.defaultsearchresults
        max_items = permissions.max_search_items
        services = {
            "bili": "bilisearch",
            "bb": "bilisearch",
            "nico": "nicosearch",
            "nv": "nicosearch",
            "youtube": "ytsearch",
            "google": "gvsearch",
            "soundcloud": "scsearch",
            "yahoo": "yvsearch",
            "yt": "ytsearch",
            "sc": "scsearch",
            "yh": "yvsearch",
            "gv": "gvsearch",
        }
        service_keys = [*services.keys(), *list(set(services.values()))]

        # handle optional [SERVICE] arg
        if leftover_args[0] in service_keys:
            service = leftover_args.pop(0)
            argcheck()

        # handle optional [RESULTS]
        if leftover_args[0].isdigit():
            items_requested = int(leftover_args.pop(0))
            argcheck()

            if items_requested > max_items:
                raise exceptions.CommandError(
                    "You cannot search for more than %(max)s videos",
                    fmt_args={"max": max_items},
                )

        # Look jake, if you see this and go "what the fuck are you doing"
        # and have a better idea on how to do this, I'd be delighted to know.
        # I don't want to just do ' '.join(leftover_args).strip("\"'")
        # Because that eats both quotes if they're there
        # where I only want to eat the outermost ones
        if leftover_args[0][0] in "'\"":
            lchar = leftover_args[0][0]
            leftover_args[0] = leftover_args[0].lstrip(lchar)
            leftover_args[-1] = leftover_args[-1].rstrip(lchar)

        ssd = self.server_data[guild.id]
        srvc = services.get(service, service)
        args_str = " ".join(leftover_args)
        search_query = f"{srvc}{items_requested}:{args_str}"

        self._do_song_blocklist_check(args_str)

        search_msg = await self.safe_send_message(
            channel,
            Response(_D("Searching for videos...", ssd)),
        )
        await channel.typing()

        try:  # pylint: disable=no-else-return
            info = await self.downloader.extract_info(
                search_query, download=False, process=True
            )

        except (
            exceptions.ExtractionError,
            exceptions.SpotifyError,
            youtube_dl.utils.YoutubeDLError,
            youtube_dl.networking.exceptions.RequestError,
        ) as e:
            if search_msg:
                error = str(e)
                if isinstance(e, exceptions.MusicbotException):
                    error = _D(e.message, ssd_) % e.fmt_args
                await self.safe_edit_message(
                    search_msg,
                    ErrorResponse(
                        _D("Search failed due to an error: %(error)s", ssd_)
                        % {"error": error},
                    ),
                    send_if_fail=True,
                )
            return None

        else:
            if search_msg:
                await self.safe_delete_message(search_msg)

        if not info:
            return Response(_D("No videos found.", ssd_))

        entries = info.get_entries_objects()

        # Decide if the list approach or the reaction approach should be used
        if self.config.searchlist:
            result_message_array = []

            content = Response(
                _D("To select a song, type the corresponding number.", ssd_),
                title=_D("Search results from %(service)s:", ssd_)
                % {"service": service},
            )

            for entry in entries:
                # This formats the results and adds it to an array
                # format_song_duration removes the hour section
                # if the song is shorter than an hour
                result_message_array.append(
                    _D("**%(index)s**. **%(track)s** | %(length)s", ssd_)
                    % {
                        "index": entries.index(entry) + 1,
                        "track": entry["title"],
                        "length": format_song_duration(entry.duration_td),
                    },
                )
            # This combines the formatted result strings into one list.
            result_string = "\n".join(str(result) for result in result_message_array)
            result_string += _D("\n**0**. Cancel", ssd_)

            # Add the result entries to the embedded message and send it to the channel
            content.add_field(
                name=_D("Pick a song", ssd_),
                value=result_string,
                inline=False,
            )
            result_message = await self.safe_send_message(channel, content)

            # Check to verify that received message is valid.
            def check(reply: discord.Message) -> bool:
                return (
                    reply.channel.id == channel.id
                    and reply.author == message.author
                    and reply.content.isdigit()
                    and -1 <= int(reply.content) - 1 <= info.entry_count
                )

            # Wait for a response from the author.
            try:
                choice = await self.wait_for(
                    "message",
                    timeout=self.config.delete_delay_long,
                    check=check,
                )
            except asyncio.TimeoutError:
                if result_message:
                    await self.safe_delete_message(result_message)
                return None

            if choice.content == "0":
                # Choice 0 will cancel the search
                if self.config.delete_invoking:
                    await self.safe_delete_message(choice)
                if result_message:
                    await self.safe_delete_message(result_message)
            else:
                # Here we have a valid choice lets queue it.
                if self.config.delete_invoking:
                    await self.safe_delete_message(choice)
                if result_message:
                    await self.safe_delete_message(result_message)
                await self.cmd_play(
                    message,
                    player,
                    channel,
                    guild,
                    author,
                    permissions,
                    [],
                    entries[int(choice.content) - 1]["url"],
                )

                return Response(
                    _D("Added song [%(track)s](%(url)s) to the queue.", ssd_)
                    % {
                        "track": entries[int(choice.content) - 1]["title"],
                        "url": entries[int(choice.content) - 1]["url"],
                    },
                )
        else:
            # patch for loop-defined cell variable.
            res_msg_ids = []
            # Original code
            for entry in entries:
                result_message = await self.safe_send_message(
                    channel,
                    Response(
                        _D("Result %(number)s of %(total)s: %(url)s", ssd)
                        % {
                            "number": entries.index(entry) + 1,
                            "total": info.entry_count,
                            "url": entry["url"],
                        },
                    ),
                )
                if not result_message:
                    continue

                res_msg_ids.append(result_message.id)

                def check_react(
                    reaction: discord.Reaction, user: discord.Member
                ) -> bool:
                    return (
                        user == message.author and reaction.message.id in res_msg_ids
                    )  # why can't these objs be compared directly?

                reactions = [
                    EMOJI_CHECK_MARK_BUTTON,
                    EMOJI_CROSS_MARK_BUTTON,
                    EMOJI_STOP_SIGN,
                ]
                for r in reactions:
                    await result_message.add_reaction(r)

                try:
                    reaction, _user = await self.wait_for(
                        "reaction_add", timeout=60.0, check=check_react
                    )
                except asyncio.TimeoutError:
                    await self.safe_delete_message(result_message)
                    return None

                if str(reaction.emoji) == EMOJI_CHECK_MARK_BUTTON:  # check
                    # play the next and respond, stop the search entry loop.
                    await self.safe_delete_message(result_message)
                    await self.cmd_play(
                        message,
                        player,
                        channel,
                        guild,
                        author,
                        permissions,
                        [],
                        entry["url"],
                    )
                    return Response(
                        _D("Alright, coming right up!", ssd_),
                    )

                if str(reaction.emoji) == EMOJI_CROSS_MARK_BUTTON:  # cross
                    # delete last result and move on to next
                    await self.safe_delete_message(result_message)
                else:  # stop
                    # delete last result and stop showing results.
                    await self.safe_delete_message(result_message)
                    break
        return None

    @command_helper(desc=_Dd("Show information on what is currently playing."))
    async def cmd_np(
        self,
        ssd_: Optional[GuildSpecificData],
        player: MusicPlayer,
        channel: MessageableChannel,
        guild: discord.Guild,
    ) -> CommandResponse:
        """
        Displays data on the current track if any.
        """
        # TODO: this may still need more tweaks for better i18n support.
        # Something to address the fragmented nature of strings in embeds.
        if player.current_entry:
            last_np_msg = self.server_data[guild.id].last_np_msg
            if last_np_msg:
                await self.safe_delete_message(last_np_msg)
                self.server_data[guild.id].last_np_msg = None

            song_progress = format_song_duration(player.progress)
            song_total = (
                format_song_duration(player.current_entry.duration_td)
                if player.current_entry.duration is not None
                else "(no duration data)"
            )

            streaming = isinstance(player.current_entry, StreamPlaylistEntry)
            prog_str = (
                "`[{progress}]`" if streaming else "`[{progress}/{total}]`"
            ).format(progress=song_progress, total=song_total)
            prog_bar_str = ""

            # percentage shows how much of the current song has already been played
            percentage = 0.0
            if (
                player.current_entry.duration
                and player.current_entry.duration_td.total_seconds() > 0
            ):
                percentage = (
                    player.progress / player.current_entry.duration_td.total_seconds()
                )

            # create the actual bar
            progress_bar_length = 30
            for i in range(progress_bar_length):
                if percentage < 1 / progress_bar_length * i:
                    prog_bar_str += "□"
                else:
                    prog_bar_str += "■"

            entry = player.current_entry
            entry_author = player.current_entry.author
            added_by = _D("[autoplaylist]", ssd_)
            if entry_author:
                added_by = entry_author.name

            content = Response("", title=_D("Now playing", ssd_))
            content.add_field(
                name=(
                    _D("Currently streaming:", ssd_)
                    if streaming
                    else _D("Currently playing:", ssd_)
                ),
                value=_D(entry.title, ssd_),
                inline=False,
            )
            content.add_field(
                name=_D("Added By:", ssd_),
                value=_D("`%(user)s`", ssd_) % {"user": added_by},
                inline=False,
            )
            content.add_field(
                name=_D("Progress:", ssd_),
                value=f"{prog_str}\n{prog_bar_str}\n\n",
                inline=False,
            )
            if len(entry.url) <= 1024:
                content.add_field(name="URL:", value=entry.url, inline=False)
            if entry.thumbnail_url:
                content.set_image(url=entry.thumbnail_url)
            else:
                log.warning("No thumbnail set for entry with URL: %s", entry.url)

            self.server_data[guild.id].last_np_msg = await self.safe_send_message(
                channel,
                content,
            )
            return None

        return Response(
            _D("There are no songs queued! Queue something with a play command.", ssd_)
        )

    @command_helper(desc=_Dd("Tell MusicBot to join the channel you're in."))
    async def cmd_summon(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        author: discord.Member,
        message: discord.Message,
    ) -> CommandResponse:
        """
        With a lock, join the caller's voice channel.
        This method will create a MusicPlayer and VoiceClient pair if needed.
        """

        lock_key = f"summon:{guild.id}"

        if self.aiolocks[lock_key].locked():
            log.debug("Waiting for summon lock: %s", lock_key)

        async with self.aiolocks[lock_key]:
            log.debug("Summon lock acquired for: %s", lock_key)

            if not author.voice or not author.voice.channel:
                raise exceptions.CommandError(
                    "You are not connected to voice. Try joining a voice channel!",
                )

            # either move an existing VoiceClient / MusicPlayer pair or make them.
            player = self.get_player_in(guild)
            if player and player.voice_client and guild == author.voice.channel.guild:
                # NOTE:  .move_to() does not support setting self-deafen flag,
                # nor respect flags set in initial connect call.
                # TODO: keep tabs on how this changes in later versions of d.py.
                # await player.voice_client.move_to(author.voice.channel)
                await guild.change_voice_state(
                    channel=author.voice.channel,
                    self_deaf=self.config.self_deafen,
                )
            else:
                player = await self.get_player(
                    author.voice.channel,
                    create=True,
                    deserialize=self.config.persistent_queue,
                )

                if player.is_stopped:
                    player.play()

            log.info(
                "Joining %(guild)s/%(channel)s",
                {
                    "guild": author.voice.channel.guild.name,
                    "channel": author.voice.channel.name,
                },
            )

            self.server_data[guild.id].last_np_msg = message

            return Response(
                _D("Connected to `%(channel)s`", ssd_)
                % {"channel": author.voice.channel},
            )

    @command_helper(
        desc=_Dd(
            "Makes MusicBot follow a user when they change channels in a server.\n"
        )
    )
    async def cmd_follow(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        author: discord.Member,
        user_mentions: UserMentions,
    ) -> CommandResponse:
        """
        Bind a user to be followed by MusicBot between channels in a server.
        """
        # If MusicBot is already following a user, either change user or un-follow.
        followed_user = self.server_data[guild.id].follow_user
        if followed_user is not None:
            # Un-follow current user.
            if followed_user.id == author.id:
                # TODO:  maybe check the current channel for users and decide if
                # we should automatically move back to guilds auto_join_channel.
                self.server_data[guild.id].follow_user = None
                return Response(
                    _D(
                        "No longer following user `%(user)s`",
                        ssd_,
                    )
                    % {"user": author.name}
                )

            # Change to following a new user.
            self.server_data[guild.id].follow_user = author
            return Response(
                _D(
                    "Now following user `%(user)s` between voice channels.",
                    ssd_,
                )
                % {"user": author.name}
            )

        # Follow the invoking user.
        # If owner mentioned a user, bind to the mentioned user instead.
        bind_to_member = author
        if author.id == self.config.owner_id and user_mentions:
            m = user_mentions.pop(0)
            if not isinstance(m, discord.Member):
                raise exceptions.CommandError(
                    "MusicBot cannot follow a user that is not a member of the server.",
                )
            bind_to_member = m

        self.server_data[guild.id].follow_user = bind_to_member
        return Response(
            _D(
                "Will follow user `%(user)s` between voice channels.",
                ssd_,
            )
            % {"user": bind_to_member.name}
        )

    @command_helper(desc=_Dd("Pause playback if a track is currently playing."))
    async def cmd_pause(
        self, ssd_: Optional[GuildSpecificData], player: MusicPlayer
    ) -> CommandResponse:
        """
        Pauses playback of the current song.
        """

        if player.is_playing:
            player.pause()
            return Response(
                _D("Paused music in `%(channel)s`", ssd_)
                % {"channel": player.voice_client.channel},
            )

        raise exceptions.CommandError("Player is not playing.")

    @command_helper(desc=_Dd("Resumes playback if the player was previously paused."))
    async def cmd_resume(
        self, ssd_: Optional[GuildSpecificData], player: MusicPlayer
    ) -> CommandResponse:
        """
        Resume a paused player.
        """

        if player.is_paused:
            player.resume()
            return Response(
                _D("Resumed music in `%(channel)s`", ssd_)
                % {"channel": player.voice_client.channel.name},
            )

        if player.is_stopped and player.playlist:
            player.play()
            return Response(_D("Resumed music queue", ssd_))

        return ErrorResponse(_D("Player is not paused.", ssd_))

    @command_helper(desc=_Dd("Shuffle all current tracks in the queue."))
    async def cmd_shuffle(
        self,
        ssd_: Optional[GuildSpecificData],
        channel: MessageableChannel,
        player: MusicPlayer,
    ) -> CommandResponse:
        """
        Shuffle all tracks in the player queue for the calling guild.
        """

        player.playlist.shuffle()

        cards = [
            "\N{BLACK SPADE SUIT}",
            "\N{BLACK CLUB SUIT}",
            "\N{BLACK HEART SUIT}",
            "\N{BLACK DIAMOND SUIT}",
        ]
        random.shuffle(cards)

        hand = await self.safe_send_message(
            channel, Response(" ".join(cards), force_text=True)
        )
        await asyncio.sleep(0.6)

        if hand:
            for _ in range(4):
                random.shuffle(cards)
                await self.safe_edit_message(
                    hand, Response(" ".join(cards), force_text=True)
                )
                await asyncio.sleep(0.6)

            await self.safe_delete_message(hand)
        return Response(_D("Shuffled all songs in the queue.", ssd_))

    @command_helper(desc=_Dd("Removes all songs currently in the queue."))
    async def cmd_clear(
        self,
        ssd_: Optional[GuildSpecificData],
        _player: MusicPlayer,
        guild: discord.Guild,
    ) -> CommandResponse:
        """
        Clears the playlist but does not skip current playing track.
        If no player is available the queue file will be removed if it exists.
        """

        # Ensure player is not none and that it's not empty
        if _player and len(_player.playlist) < 1:
            raise exceptions.CommandError(
                "There is nothing currently playing. Play something with a play command."
            )

        # Try to gracefully clear the guild queue if we're not in a vc.
        if not _player:
            queue_path = self.config.data_path.joinpath(
                f"{guild.id}/{DATA_GUILD_FILE_QUEUE}"
            )
            try:
                queue_path.unlink()
            except FileNotFoundError:
                pass  # Silently ignore if file doesn't exist.
            except PermissionError:
                log.error(
                    "Missing permissions to delete queue file for %(guild)s(%(id)s) at: %(path)s",
                    {"guild": guild.name, "id": guild.id, "path": queue_path},
                )
            except OSError:
                log.exception(
                    "OS level error while trying to delete queue file: %(path)s",
                    {"path": queue_path},
                )
        else:
            _player.playlist.clear()  # Clear playlist from vc

        return Response(_D("Cleared all songs from the queue.", ssd_))

    @command_helper(
        usage=["{cmd} [POSITION]"],
        desc=_Dd(
            "Remove a song from the queue, optionally at the given queue position.\n"
            "If the position is omitted, the song at the end of the queue is removed.\n"
            "Use the queue command to find position number of your track.\n"
            "However, positions of all songs are changed when a new song starts playing.\n"
        ),
    )
    async def cmd_remove(
        self,
        ssd_: Optional[GuildSpecificData],
        user_mentions: UserMentions,
        author: discord.Member,
        permissions: PermissionGroup,
        player: MusicPlayer,
        index: str = "",
    ) -> CommandResponse:
        """
        Command to remove entries from the player queue using relative IDs or LIFO method.
        """

        if not player.playlist.entries:
            raise exceptions.CommandError("Nothing in the queue to remove!")

        if user_mentions:
            for user in user_mentions:
                if permissions.remove or author == user:
                    try:
                        entry_indexes = [
                            e for e in player.playlist.entries if e.author == user
                        ]
                        for entry in entry_indexes:
                            player.playlist.entries.remove(entry)
                        entry_text = f"{len(entry_indexes)} item"
                        if len(entry_indexes) > 1:
                            entry_text += "s"
                        return Response(
                            _D("Removed `%(track)s` added by `%(user)s`", ssd_)
                            % {"track": entry_text, "user": user.name},
                        )

                    except ValueError as e:
                        raise exceptions.CommandError(
                            "Nothing found in the queue from user `%(user)s`",
                            fmt_args={"user": user.name},
                        ) from e

                raise exceptions.PermissionsError(
                    "You do not have the permission to remove that entry from the queue.\n"
                    "You must be the one who queued it or have instant skip permissions.",
                )

        if not index:
            idx = len(player.playlist.entries)

        try:
            idx = int(index)
        except (TypeError, ValueError) as e:
            raise exceptions.CommandError(
                "Invalid entry number. Use the queue command to find queue positions.",
            ) from e

        if idx > len(player.playlist.entries):
            raise exceptions.CommandError(
                "Invalid entry number. Use the queue command to find queue positions.",
            )

        if (
            permissions.remove
            or author == player.playlist.get_entry_at_index(idx - 1).author
        ):
            entry = player.playlist.delete_entry_at_index((idx - 1))
            if entry.channel and entry.author:
                return Response(
                    _D("Removed entry `%(track)s` added by `%(user)s`", ssd_)
                    % {"track": _D(entry.title, ssd_), "user": entry.author.name},
                )

            return Response(
                _D("Removed entry `%(track)s`", ssd_)
                % {"track": _D(entry.title, ssd_)},
            )

        raise exceptions.PermissionsError(
            "You do not have the permission to remove that entry from the queue.\n"
            "You must be the one who queued it or have instant skip permissions.",
        )

    @command_helper(
        usage=["{cmd} [force | f]"],
        desc=_Dd(
            "Skip or vote to skip the current playing song.\n"
            "Members with InstaSkip permission may use force parameter to bypass voting.\n"
            "If LegacySkip option is enabled, the force parameter can be ignored.\n"
        ),
    )
    async def cmd_skip(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        player: MusicPlayer,
        author: discord.Member,
        message: discord.Message,
        permissions: PermissionGroup,
        voice_channel: Optional[VoiceableChannel],
        param: str = "",
    ) -> CommandResponse:
        """
        Implements the multi-featured skip logic for skip voting or forced skiping.
        Several options and a permission change how this command works.
        InstaSkip permission will allow force, which is not required if LegacySkip option is enabled.
        SkipRatio and SkipsRequired determine how voting is counted and if voting is enabled.
        """

        if player.is_stopped:
            raise exceptions.CommandError("Can't skip! The player is not playing!")

        if not player.current_entry:
            next_entry = player.playlist.peek()
            if next_entry:
                if next_entry.is_downloading:
                    return Response(
                        _D(
                            "The next song `%(track)s` is downloading, please wait.",
                            ssd_,
                        )
                        % {"track": _D(next_entry.title, ssd_)},
                    )

                if next_entry.is_downloaded:
                    return Response(
                        _D("The next song will be played shortly. Please wait.", ssd_)
                    )

                return Response(
                    _D(
                        "Something odd is happening.\n"
                        "You might want to restart the bot if it doesn't start working.",
                        ssd_,
                    )
                )
            return Response(
                _D(
                    "Something strange is happening.\n"
                    "You might want to restart the bot if it doesn't start working.",
                    ssd_,
                )
            )

        current_entry = player.current_entry
        entry_author = current_entry.author
        entry_author_id = 0
        if entry_author:
            entry_author_id = entry_author.id

        permission_force_skip = permissions.instaskip or (
            self.config.allow_author_skip and author.id == entry_author_id
        )
        force_skip = param.lower() in ["force", "f"]

        if permission_force_skip and (force_skip or self.config.legacy_skip):
            if (
                not permission_force_skip
                and not permissions.skip_looped
                and player.repeatsong
            ):
                raise exceptions.PermissionsError(
                    "You do not have permission to force skip a looped song.",
                )

            # handle history playlist updates.
            if (
                self.config.enable_queue_history_global
                or self.config.enable_queue_history_guilds
            ):
                self.server_data[guild.id].current_playing_url = ""

            if player.repeatsong:
                player.repeatsong = False
            player.skip()
            return Response(
                _D("Force skipped `%(track)s`.", ssd_)
                % {"track": _D(current_entry.title, ssd_)},
            )

        if not permission_force_skip and force_skip:
            raise exceptions.PermissionsError(
                "You do not have permission to force skip."
            )

        # get the number of users in the channel who are not deaf, exclude bots with exceptions.
        num_voice = count_members_in_voice(
            voice_channel,
            # make sure we include bot exceptions.
            include_bots=self.config.bot_exception_ids,
        )
        # If all users are deaf, avoid ZeroDivisionError
        if num_voice == 0:
            num_voice = 1

        # add the current skipper id so we can count it.
        player.skip_state.add_skipper(author.id, message)
        # count all members who are in skippers set.
        num_skips = count_members_in_voice(
            voice_channel,
            # This will exclude all other members in the channel who have not skipped.
            include_only=player.skip_state.skippers,
            # If a bot has skipped, this allows the exceptions to be counted.
            include_bots=self.config.bot_exception_ids,
        )

        skips_remaining = (
            min(
                self.config.skips_required,
                math.ceil(
                    self.config.skip_ratio_required / (1 / num_voice)
                ),  # Number of skips from config ratio
            )
            - num_skips
        )

        if skips_remaining <= 0:
            if not permissions.skip_looped and player.repeatsong:
                raise exceptions.PermissionsError(
                    "You do not have permission to skip a looped song.",
                )

            if player.repeatsong:
                player.repeatsong = False

            # handle history playlist updates.
            if (
                self.config.enable_queue_history_global
                or self.config.enable_queue_history_guilds
            ):
                self.server_data[guild.id].current_playing_url = ""

            player.skip()
            return Response(
                _D(
                    "Your skip for `%(track)s` was acknowledged.\n"
                    "The vote to skip has been passed.%(next_up)s",
                    ssd_,
                )
                % {
                    "track": _D(current_entry.title, ssd_),
                    "next_up": (
                        _D(" Next song coming up!", ssd_)
                        if player.playlist.peek()
                        else ""
                    ),
                },
            )

        # TODO: When a song gets skipped, delete the old x needed to skip messages
        if not permissions.skip_looped and player.repeatsong:
            raise exceptions.PermissionsError(
                "You do not have permission to skip a looped song.",
            )

        if player.repeatsong:
            player.repeatsong = False
        return Response(
            _D(
                "Your skip for `%(track)s` was acknowledged.\n"
                "Need **%(votes)s** more vote(s) to skip this song.",
                ssd_,
            )
            % {
                "track": _D(current_entry.title, ssd_),
                "votes": skips_remaining,
            },
        )

    @command_helper(
        usage=["{cmd} [VOLUME]"],
        desc=_Dd(
            "Set the output volume level of MusicBot from 1 to 100.\n"
            "Volume parameter allows a leading + or - for relative adjustments.\n"
            "The volume setting is retained until MusicBot is restarted.\n"
        ),
    )
    async def cmd_volume(
        self,
        ssd_: Optional[GuildSpecificData],
        player: MusicPlayer,
        new_volume: str = "",
    ) -> CommandResponse:
        """
        Command to set volume level of MusicBot output for the session.
        """

        if not new_volume:
            return Response(
                _D("Current volume: `%(volume)s%%`", ssd_)
                % {"volume": int(player.volume * 100)},
            )

        relative = False
        if new_volume[0] in "+-":
            relative = True

        try:
            int_volume = int(new_volume)

        except ValueError as e:
            raise exceptions.CommandError(
                "`%(new_volume)s` is not a valid number",
                fmt_args={"new_volume": new_volume},
            ) from e

        vol_change = 0
        if relative:
            vol_change = int_volume
            int_volume += int(player.volume * 100)

        old_volume = int(player.volume * 100)

        if 0 < int_volume <= 100:
            player.volume = int_volume / 100.0

            if (
                self.config.use_opus_audio
                and player.current_entry
                and player.is_playing
            ):
                # Set current playback progress and restart playback.
                entry = player.current_entry
                if isinstance(entry, (URLPlaylistEntry, LocalFilePlaylistEntry)):
                    entry.set_start_time(player.progress)
                player.playlist.insert_entry_at_index(0, entry)

                # handle history playlist updates.
                if ssd_ and (
                    self.config.enable_queue_history_global
                    or self.config.enable_queue_history_guilds
                ):
                    ssd_.current_playing_url = ""

                player.skip()

            return Response(
                _D("Updated volume from **%(old)d** to **%(new)d**", ssd_)
                % {"old": old_volume, "new": int_volume},
            )

        if relative:
            raise exceptions.CommandError(
                "Unreasonable volume change provided: %(old_volume)s%(adjustment)s is %(new_volume)s.\n"
                "Volume can only be set from 1 to 100.",
                fmt_args={
                    "old_volume": old_volume,
                    "new_volume": old_volume + vol_change,
                    "adjustment": f"{vol_change:+}",
                },
            )

        raise exceptions.CommandError(
            "Unreasonable volume provided: %(volume)s. Provide a value between 1 and 100.",
            fmt_args={"volume": new_volume},
        )

    @command_helper(
        usage=["{cmd} [RATE]"],
        desc=_Dd(
            "Change the playback speed of the currently playing track only.\n"
            "The rate must be between 0.5 and 100.0 due to ffmpeg limits.\n"
            "Streaming playback does not support speed adjustments.\n"
        ),
    )
    async def cmd_speed(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        player: MusicPlayer,
        new_speed: str = "",
    ) -> CommandResponse:
        """
        Check for playing entry and apply a speed to ffmpeg for playback.
        """
        if not player.current_entry:
            raise exceptions.CommandError(
                "No track is playing, cannot set speed.\n"
                "Use the config command to set a default playback speed.",
            )

        if not isinstance(
            player.current_entry, (URLPlaylistEntry, LocalFilePlaylistEntry)
        ):
            raise exceptions.CommandError(
                "Speed cannot be applied to streamed media.",
            )

        if not new_speed:
            raise exceptions.CommandError(
                "You must provide a speed to set.",
            )

        try:
            speed = float(new_speed)
            if speed < 0.5 or speed > 100.0:
                raise ValueError("Value out of range.")
        except (ValueError, TypeError) as e:
            raise exceptions.CommandError(
                "The speed you provided is invalid. Use a number between 0.5 and 100.",
            ) from e

        # Set current playback progress and speed then restart playback.
        entry = player.current_entry
        entry.set_start_time(player.progress)
        entry.set_playback_speed(speed)
        player.playlist.insert_entry_at_index(0, entry)

        # handle history playlist updates.
        if (
            self.config.enable_queue_history_global
            or self.config.enable_queue_history_guilds
        ):
            self.server_data[guild.id].current_playing_url = ""

        player.skip()

        return Response(
            _D("Setting playback speed to `%(speed).3f` for current track.", ssd_)
            % {"speed": speed},
        )

    @owner_only
    @command_helper(
        # fmt: off
        usage=[
            "{cmd} add <ALIAS> <CMD> [ARGS]\n"
            + _Dd("    Add an new alias with optional arguments.\n"),

            "{cmd} remove <ALIAS>\n"
            + _Dd("    Remove an alias with the given name.\n"),

            "{cmd} <save | load>\n"
            + _Dd("    Reload or save aliases from/to the config file.\n"),
        ],
        # fmt: on
        desc=_Dd(
            "Allows management of aliases from discord. To see aliases use the help command."
        ),
        remap_subs={"+": "add", "-": "remove"},
    )
    async def cmd_setalias(
        self,
        ssd_: Optional[GuildSpecificData],
        opt: str,
        leftover_args: List[str],
        alias: str = "",
        cmd: str = "",
    ) -> CommandResponse:
        """
        Enable management of aliases from within discord.
        """
        opt = opt.lower()
        cmd = cmd.strip()
        args = " ".join(leftover_args)
        alias = alias.strip()
        if opt not in ["add", "remove", "save", "load"]:
            raise exceptions.CommandError(
                "Invalid option for command: `%(option)s`",
                fmt_args={"option": opt},
            )

        if opt == "load":
            self.aliases.load()
            return Response(_D("Aliases reloaded from config file.", ssd_))

        if opt == "save":
            try:
                self.aliases.save()
                return Response(_D("Aliases saved to config file.", ssd_))
            except (RuntimeError, OSError) as e:
                raise exceptions.CommandError(
                    "Failed to save aliases due to error:\n`%(raw_error)s`",
                    fmt_args={"raw_error": e},
                ) from e

        if opt == "add":
            if not alias or not cmd:
                raise exceptions.CommandError(
                    "You must supply an alias and a command to alias",
                )
            self.aliases.make_alias(alias, cmd, args)
            cmdstr = " ".join([cmd, args]).strip()
            return Response(
                _D(
                    "New alias added. `%(alias)s` is now an alias of `%(command)s`",
                    ssd_,
                )
                % {"alias": alias, "command": cmdstr}
            )

        if opt == "remove":
            if not alias:
                raise exceptions.CommandError(
                    "You must supply an alias name to remove.",
                )

            if not self.aliases.exists(alias):
                raise exceptions.CommandError(
                    "The alias `%(alias)s` does not exist.",
                    fmt_args={"alias": alias},
                )

            self.aliases.remove_alias(alias)
            return Response(
                _D("Alias `%(alias)s` was removed.", ssd_) % {"alias": alias}
            )

        return None

    @owner_only
    @command_helper(
        # fmt: off
        usage=[
            "{cmd} missing\n"
            + _Dd("    Shows help text about any missing config options.\n"),

            "{cmd} diff\n"
            + _Dd("    Lists the names of options which have been changed since loading config file.\n"),

            "{cmd} list\n"
            + _Dd("    List the available config options and their sections.\n"),

            "{cmd} reload\n"
            + _Dd("    Reload the options.ini file from disk.\n"),

            "{cmd} help <SECTION> <OPTION>\n"
            + _Dd("    Shows help text for a specific option.\n"),

            "{cmd} show <SECTION> <OPTION>\n"
            + _Dd("    Display the current value of the option.\n"),

            "{cmd} save <SECTION> <OPTION>\n"
            + _Dd("    Saves the current value to the options file.\n"),

            "{cmd} set <SECTION> <OPTION> <VALUE>\n"
            + _Dd("    Validates the option and sets the config for the session, but not to file.\n"),

            "{cmd} reset <SECTION> <OPTION>\n"
            + _Dd("    Reset the option to its default value.\n"),
        ],
        # fmt: on
        desc=_Dd("Manage options.ini configuration from within Discord."),
    )
    async def cmd_config(
        self,
        ssd_: Optional[GuildSpecificData],
        user_mentions: UserMentions,
        channel_mentions: List[discord.abc.GuildChannel],
        option: str,
        leftover_args: List[str],
    ) -> CommandResponse:
        """
        Command to enable complex management of options.ini config file.
        """
        if user_mentions and channel_mentions:
            raise exceptions.CommandError(
                "Config cannot use channel and user mentions at the same time.",
            )

        option = option.lower()
        valid_options = [
            "missing",
            "diff",
            "list",
            "save",
            "help",
            "show",
            "set",
            "reload",
            "reset",
        ]
        if option not in valid_options:
            raise exceptions.CommandError(
                "Invalid option for command: `%(option)s`",
                fmt_args={"option": option},
            )

        # Show missing options with help text.
        if option == "missing":
            missed = ""
            for opt in sorted(self.config.register.ini_missing_options, key=str):
                missed += f"{opt}\n"  # pylint: disable=consider-using-join

            if not missed:
                missing = _D(
                    "*All config options are present and accounted for!*",
                    ssd_,
                )
            else:
                missing = _D(
                    "**Missing Options:**\n```\n%(missing)s```",
                    ssd_,
                ) % {"missing": missed}

            return Response(
                missing,
                delete_after=self.config.delete_delay_long,
            )

        # Show options names that have changed since loading.
        if option == "diff":
            changed = ""
            for opt in self.config.register.get_updated_options():
                changed += f"`{str(opt)}`\n"

            if not changed:
                changed = _D("No config options appear to be changed.", ssd_)
            else:
                changed = _D("**Changed Options:**\n%(changed)s", ssd_) % {
                    "changed": changed
                }

            return Response(
                changed,
                delete_after=self.config.delete_delay_long,
            )

        # List all available options.
        if option == "list":
            non_edit_opts = ""
            editable_opts = ""
            for opt in self.config.register.option_list:
                if opt.editable:
                    editable_opts += f"`{opt}`\n"
                else:
                    non_edit_opts += f"`{opt}`\n"

            opt_list = _D(
                "## Available Options:\n"
                "**Editable Options:**\n%(editable)s\n"
                "**Manual Edit Only:**\n%(manual)s",
                ssd_,
            ) % {
                "editable": editable_opts,
                "manual": non_edit_opts,
            }
            return Response(
                opt_list,
                delete_after=self.config.delete_delay_long,
            )

        # Try to reload options.ini file from disk.
        if option == "reload":
            try:
                new_conf = Config(self._config_file)
                await new_conf.async_validate(self)

                self.config = new_conf

                return Response(
                    _D("Config options reloaded from file successfully!", ssd_)
                )
            except Exception as e:
                raise exceptions.CommandError(
                    "Unable to reload Config due to the following error:\n%(raw_error)s",
                    fmt_args={"raw_error": e},
                ) from e

        # sub commands beyond here need 2 leftover_args
        if option in ["help", "show", "save", "set", "reset"]:
            largs = len(leftover_args)
            if (
                self.config.register.resolver_available
                and largs != 0
                and ((option == "set" and largs < 3) or largs < 2)
            ):
                # assume that section is omitted.
                possible_sections = self.config.register.get_sections_from_option(
                    leftover_args[0]
                )
                if len(possible_sections) == 0:
                    raise exceptions.CommandError(
                        "Could not resolve section name from option name. Please provide a valid section and option name.",
                    )
                if len(possible_sections) > 1:
                    raise exceptions.CommandError(
                        "The option given is ambiguous, please provide a section name.",
                    )
                # adjust the command arguments to include the resolved section.
                leftover_args = [list(possible_sections)[0]] + leftover_args
            elif largs < 2 or (option == "set" and largs < 3):
                raise exceptions.CommandError(
                    "You must provide a section name and option name for this command.",
                )

        # Get the command args from leftovers and check them.
        section_arg = leftover_args.pop(0)
        option_arg = leftover_args.pop(0)
        if user_mentions:
            leftover_args += [str(m.id) for m in user_mentions]
        if channel_mentions:
            leftover_args += [str(ch.id) for ch in channel_mentions]
        value_arg = " ".join(leftover_args)
        p_opt = self.config.register.get_config_option(section_arg, option_arg)

        if section_arg not in self.config.register.sections:
            sects = ", ".join(self.config.register.sections)
            raise exceptions.CommandError(
                "The section `%(section)s` is not available.\n"
                "The available sections are:  %(sections)s",
                fmt_args={"section": section_arg, "sections": sects},
            )

        if p_opt is None:
            option_arg = f"[{section_arg}] > {option_arg}"
            raise exceptions.CommandError(
                "The option `%(option)s` is not available.",
                fmt_args={"option": option_arg},
            )
        opt = p_opt

        # Display some commentary about the option and its default.
        if option == "help":
            default = _D(
                "This option can only be set by editing the config file.", ssd_
            )
            if opt.editable:
                default = _D(
                    "By default this option is set to: %(default)s",
                    ssd_,
                ) % {"default": opt.default}
            return Response(
                _D(
                    "**Option:** `%(config)s`\n%(comment)s\n\n%(default)s",
                    ssd_,
                )
                % {"config": opt, "comment": opt.comment, "default": default},
                delete_after=self.config.delete_delay_long,
            )

        # Save the current config value to the INI file.
        if option == "save":
            if not opt.editable:
                raise exceptions.CommandError(
                    "Option `%(option)s` is not editable. Cannot save to disk.",
                    fmt_args={"option": opt},
                )

            async with self.aiolocks["config_edit"]:
                saved = self.config.save_option(opt)

            if not saved:
                raise exceptions.CommandError(
                    "Failed to save the option:  `%(option)s`",
                    fmt_args={"option": opt},
                )
            return Response(
                _D(
                    "Successfully saved the option:  `%(config)s`",
                    ssd_,
                )
                % {"config": opt}
            )

        # Display the current config and INI file values.
        if option == "show":
            if not opt.editable:
                raise exceptions.CommandError(
                    "Option `%(option)s` is not editable, value cannot be displayed.",
                    fmt_args={"option": opt},
                )
            # TODO: perhaps make use of currently unused display value for empty configs.
            cur_val, ini_val, disp_val = self.config.register.get_values(opt)
            cur_val = str(cur_val)
            ini_val = str(ini_val)
            if not cur_val:
                cur_val = " " if not disp_val else disp_val
            if not ini_val:
                ini_val = " " if not disp_val else disp_val

            return Response(
                _D(
                    "**Option:** `%(config)s`\n"
                    "Current Value:  `%(loaded)s`\n"
                    "INI File Value:  `%(ini)s`",
                    ssd_,
                )
                % {
                    "config": opt,
                    "loaded": cur_val,
                    "ini": ini_val,
                }
            )

        # update a config variable, but don't save it.
        if option == "set":
            if not opt.editable:
                raise exceptions.CommandError(
                    "Option `%(option)s` is not editable. Cannot update setting.",
                    fmt_args={"option": opt},
                )

            if not value_arg:
                raise exceptions.CommandError(
                    "You must provide a section, option, and value for this sub command.",
                )

            log.debug(
                "Doing set with on %(config)s == %(value)s",
                {"config": opt, "value": value_arg},
            )
            async with self.aiolocks["config_update"]:
                updated = self.config.update_option(opt, value_arg)
            if not updated:
                raise exceptions.CommandError(
                    "Option `%(option)s` was not updated!",
                    fmt_args={"option": opt},
                )
            return Response(
                _D(
                    "Option `%(config)s` was updated for this session.\n"
                    "To save the change use `config save %(section)s %(option)s`",
                    ssd_,
                )
                % {"config": opt, "section": opt.section, "option": opt.option}
            )

        # reset an option to default value as defined in ConfigDefaults
        if option == "reset":
            if not opt.editable:
                raise exceptions.CommandError(
                    "Option `%(option)s` is not editable. Cannot reset to default.",
                    fmt_args={"option": opt},
                )

            # Use the default value from the option object
            default_value = self.config.register.to_ini(opt, use_default=True)

            # Prepare a user-friendly message for the reset operation
            # TODO look into option registry display code for use here
            reset_value_display = default_value if default_value else "an empty set"

            log.debug(
                "Resetting %(config)s to default %(value)s",
                {"config": opt, "value": default_value},
            )
            async with self.aiolocks["config_update"]:
                updated = self.config.update_option(opt, default_value)
            if not updated:
                raise exceptions.CommandError(
                    "Option `%(option)s` was not reset to default!",
                    fmt_args={"option": opt},
                )
            return Response(
                _D(
                    "Option `%(config)s` was reset to its default value `%(default)s`.\n"
                    "To save the change use `config save %(section)s %(option)s`",
                    ssd_,
                )
                % {
                    "config": opt,
                    "option": opt.option,
                    "section": opt.section,
                    "default": reset_value_display,
                }
            )

        return None

    @owner_only
    @command_helper(desc=_Dd("Deprecated command, use the config command instead."))
    async def cmd_option(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        option: str,
        value: str,
    ) -> CommandResponse:
        """
        Command previously used to change boolean options in config.
        Replaced by the config command.
        """
        raise exceptions.CommandError(
            "The option command is deprecated, use the config command instead.",
        )

    @owner_only
    @command_helper(
        usage=["{cmd} <info | clear | update>"],
        desc=_Dd(
            "Display information about cache storage or clear cache according to configured limits.\n"
            "Using update option will scan the cache for external changes before displaying details."
        ),
    )
    async def cmd_cache(
        self, ssd_: Optional[GuildSpecificData], opt: str = "info"
    ) -> CommandResponse:
        """
        Command to enable cache management from discord.
        """
        opt = opt.lower()
        if opt not in ["info", "update", "clear"]:
            raise exceptions.CommandError(
                "Invalid option specified, use: info, update, or clear"
            )

        # actually query the filesystem.
        if opt == "update":
            self.filecache.scan_audio_cache()
            # force output of info after we have updated it.
            opt = "info"

        # report cache info as it is.
        if opt == "info":
            save_videos = [_D("Disabled", ssd_), _D("Enabled", ssd_)][
                self.config.save_videos
            ]
            time_limit = _D("%(time)s days", ssd_) % {
                "time": self.config.storage_limit_days
            }
            size_limit = format_size_from_bytes(self.config.storage_limit_bytes)

            if not self.config.storage_limit_bytes:
                size_limit = _D("Unlimited", ssd_)

            if not self.config.storage_limit_days:
                time_limit = _D("Unlimited", ssd_)

            cached_bytes, cached_files = self.filecache.get_cache_size()
            return Response(
                _D(
                    "**Video Cache:** *%(state)s*\n"
                    "**Storage Limit:** *%(size)s*\n"
                    "**Time Limit:** *%(time)s*\n"
                    "\n"
                    "**Cached Now:  %(used)s in %(files)s file(s).",
                    ssd_,
                )
                % {
                    "state": save_videos,
                    "size": size_limit,
                    "time": time_limit,
                    "used": format_size_from_bytes(cached_bytes),
                    "files": cached_files,
                },
                delete_after=self.config.delete_delay_long,
            )

        # clear cache according to settings.
        if opt == "clear":
            if self.filecache.cache_dir_exists():
                if self.filecache.delete_old_audiocache():
                    return Response(
                        _D(
                            "Cache has been cleared.",
                            ssd_,
                        ),
                    )

                raise exceptions.CommandError(
                    "**Failed** to delete cache, check logs for more info...",
                )
            return Response(
                _D("No cache found to clear.", ssd_),
            )
        # TODO: maybe add a "purge" option that fully empties cache regardless of settings.
        return None

    @command_helper(
        usage=["{cmd} [PAGE]"],
        desc=_Dd(
            "Display information about the current player queue.\n"
            "Optional page number shows later entries in the queue.\n"
        ),
    )
    async def cmd_queue(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        channel: MessageableChannel,
        player: MusicPlayer,
        page: str = "0",
        update_msg: Optional[discord.Message] = None,
    ) -> CommandResponse:
        """
        Interactive display for player queue, which expires after inactivity.
        """

        # handle the page argument.
        page_number = 0
        if page:
            try:
                page_number = abs(int(page))
            except (ValueError, TypeError) as e:
                raise exceptions.CommandError(
                    "Queue page argument must be a whole number.",
                ) from e

        # check for no entries at all.
        total_entry_count = len(player.playlist.entries)
        if not total_entry_count:
            raise exceptions.CommandError(
                "There are no songs queued! Queue something with a play command.",
            )

        # now check if page number is out of bounds.
        pages_total = math.ceil(total_entry_count / self.config.queue_length)
        if page_number > pages_total:
            raise exceptions.CommandError(
                "Requested page number is out of bounds.\n"
                "There are **%(total)s** pages.",
                fmt_args={"total": pages_total},
            )

        # Get current entry info if any.
        current_progress = ""
        if player.is_playing and player.current_entry:
            song_progress = format_song_duration(player.progress)
            song_total = (
                format_song_duration(player.current_entry.duration_td)
                if player.current_entry.duration is not None
                else _D("(unknown duration)", ssd_)
            )
            added_by = _D("[autoplaylist]", ssd_)
            cur_entry_channel = player.current_entry.channel
            cur_entry_author = player.current_entry.author
            if cur_entry_channel and cur_entry_author:
                added_by = cur_entry_author.name

            current_progress = _D(
                "Currently playing: `%(title)s`\n"
                "Added by: `%(user)s`\n"
                "Progress: `[%(progress)s/%(total)s]`\n",
                ssd_,
            ) % {
                "title": _D(player.current_entry.title, ssd_),
                "user": added_by,
                "progress": song_progress,
                "total": song_total,
            }

        # calculate start and stop slice indices
        start_index = self.config.queue_length * page_number
        end_index = start_index + self.config.queue_length
        starting_at = start_index + 1  # add 1 to index for display.

        # add the tracks to the embed fields
        tracks_list = ""
        queue_segment = list(player.playlist.entries)[start_index:end_index]
        for idx, item in enumerate(queue_segment, starting_at):
            if item == player.current_entry:
                # TODO: remove this debug later
                log.debug("Skipped the current playlist entry.")
                continue

            added_by = _D("[autoplaylist]", ssd_)
            if item.channel and item.author:
                added_by = item.author.name

            tracks_list += _D(
                "**Entry #%(index)s:**"
                "Title: `%(title)s`\n"
                "Added by: `%(user)s`\n\n",
                ssd_,
            ) % {"index": idx, "title": _D(item.title, ssd_), "user": added_by}

        embed = Response(
            _D(
                "%(progress)s"
                "There are `%(total)s` entries in the queue.\n"
                "Here are the next %(per_page)s songs, starting at song #%(start)s\n"
                "\n%(tracks)s",
                ssd_,
            )
            % {
                "progress": current_progress,
                "total": total_entry_count,
                "per_page": self.config.queue_length,
                "start": starting_at,
                "tracks": tracks_list,
            },
            title=_D("Songs in queue", ssd_),
            delete_after=self.config.delete_delay_long,
        )

        # handle sending or editing the queue message.
        if update_msg:
            q_msg = await self.safe_edit_message(update_msg, embed, send_if_fail=True)
        else:
            if pages_total <= 1:
                q_msg = await self.safe_send_message(channel, embed)
            else:
                q_msg = await self.safe_send_message(channel, embed)

        if pages_total <= 1:
            log.debug("Not enough entries to paginate the queue.")
            return None

        if not q_msg:
            log.warning("Could not post queue message, no message to add reactions to.")
            raise exceptions.CommandError(
                "Try that again. MusicBot couldn't make or get a reference to the queue message.\n"
                "If the issue persists, file a bug report."
            )

        # set up the page numbers to be used by reactions.
        # this essentially make the pages wrap around.
        prev_index = page_number - 1
        next_index = page_number + 1
        if prev_index < 0:
            prev_index = pages_total
        if next_index > pages_total:
            next_index = 0

        for r in [EMOJI_PREV_ICON, EMOJI_NEXT_ICON, EMOJI_CROSS_MARK_BUTTON]:
            await q_msg.add_reaction(r)

        def _check_react(reaction: discord.Reaction, user: discord.Member) -> bool:
            # Do not check for the requesting author, any reaction is valid.
            if not self.user:
                return False
            return q_msg.id == reaction.message.id and user.id != self.user.id

        try:
            reaction, _user = await self.wait_for(
                "reaction_add",
                timeout=self.config.delete_delay_long,
                check=_check_react,
            )
            if reaction.emoji == EMOJI_NEXT_ICON:
                await q_msg.clear_reactions()
                await self.cmd_queue(
                    ssd_, guild, channel, player, str(next_index), q_msg
                )

            if reaction.emoji == EMOJI_PREV_ICON:
                await q_msg.clear_reactions()
                await self.cmd_queue(
                    ssd_, guild, channel, player, str(prev_index), q_msg
                )

            if reaction.emoji == EMOJI_CROSS_MARK_BUTTON:
                await self.safe_delete_message(q_msg)

        except asyncio.TimeoutError:
            await self.safe_delete_message(q_msg)

        return None

    @command_helper(
        usage=["{cmd} [RANGE]"],
        desc=_Dd(
            "Search for and remove bot messages and commands from the calling text channel.\n"
            "Optionally supply a number of messages to search through, 50 by default 500 max.\n"
            "This command may be slow if larger ranges are given.\n"
        ),
    )
    async def cmd_clean(
        self,
        ssd_: Optional[GuildSpecificData],
        message: discord.Message,
        channel: MessageableChannel,
        guild: discord.Guild,
        author: discord.Member,
        search_range_str: str = "50",
    ) -> CommandResponse:
        """
        Uses channel.purge() to delete valid bot messages or commands from the calling channel.
        """

        try:
            float(search_range_str)  # lazy check
            search_range = min(int(search_range_str), 500)
        except ValueError:
            return Response(
                _D(
                    "Invalid parameter. Please provide a number of messages to search.",
                    ssd_,
                )
            )

        # TODO:  add alias names to the command names list here.
        # cmd_names = await self.gen_cmd_list(message)

        def is_possible_command_invoke(entry: discord.Message) -> bool:
            prefix_list = self.server_data[guild.id].command_prefix_list
            content = entry.content
            for prefix in prefix_list:
                if content.startswith(prefix):
                    content = content.replace(prefix, "", 1).strip()
                    if content:
                        # TODO: this should check for command names and alias names.
                        return True
            return False

        delete_invokes = True
        delete_all = (
            channel.permissions_for(author).manage_messages
            or self.config.owner_id == author.id
        )

        def check(message: discord.Message) -> bool:
            if is_possible_command_invoke(message) and delete_invokes:
                return delete_all or message.author == author
            return message.author == self.user

        if isinstance(
            channel,
            (discord.DMChannel, discord.GroupChannel, discord.PartialMessageable),
        ):
            # TODO: maybe fix this to work?
            raise exceptions.CommandError("Cannot use purge on private DM channel.")

        if channel.permissions_for(guild.me).manage_messages:
            deleted = await channel.purge(
                check=check, limit=search_range, before=message
            )
            return Response(
                _D("Cleaned up %(number)s message(s).", ssd_)
                % {"number": len(deleted)},
            )
        return ErrorResponse(
            _D("Bot does not have permission to manage messages.", ssd_)
        )

    @command_helper(
        usage=["{cmd} <URL>"],
        desc=_Dd("Dump the individual URLs of a playlist to a file."),
    )
    async def cmd_pldump(
        self,
        ssd_: Optional[GuildSpecificData],
        author: discord.Member,
        song_subject: str,
    ) -> CommandResponse:
        """
        Extracts all URLs from a playlist and create a file attachment with the resulting links.
        This method does not validate the resulting links are actually playable.
        """

        song_url = self.downloader.get_url_or_none(song_subject)
        if not song_url:
            raise exceptions.CommandError(
                "The given URL was not a valid URL.",
            )

        try:
            info = await self.downloader.extract_info(
                song_url, download=False, process=True
            )
        # TODO: i18n stuff with translatable exceptions.
        except Exception as e:
            raise exceptions.CommandError(
                "Could not extract info from input url\n%(raw_error)s\n",
                fmt_args={"raw_error": e},
            )

        if not info.get("entries", None):
            raise exceptions.CommandError("This does not seem to be a playlist.")

        filename = "playlist.txt"
        if info.title:
            safe_title = slugify(info.title)
            filename = f"playlist_{safe_title}.txt"

        with BytesIO() as fcontent:
            total = info.playlist_count or info.entry_count
            fcontent.write(f"# Title:  {info.title}\n".encode("utf8"))
            fcontent.write(f"# Total:  {total}\n".encode("utf8"))
            fcontent.write(f"# Extractor:  {info.extractor}\n\n".encode("utf8"))

            for item in info.get_entries_objects():
                # TODO: maybe add track-name as a comment?
                url = item.get_playable_url()
                line = f"{url}\n"
                fcontent.write(line.encode("utf8"))

            fcontent.seek(0)
            msg_str = _D("Here is the playlist dump for:  %(url)s", ssd_) % {
                "url": song_url
            }
            datafile = discord.File(fcontent, filename=filename)

            return Response(msg_str, send_to=author, files=[datafile], force_text=True)

    @command_helper(
        usage=["{cmd} [@USER]"],
        desc=_Dd(
            "Display your Discord User ID, or the ID of a mentioned user.\n"
            "This command is deprecated in favor of Developer Mode in Discord clients.\n"
        ),
    )
    async def cmd_id(
        self,
        ssd_: Optional[GuildSpecificData],
        author: discord.Member,
        user_mentions: UserMentions,
    ) -> CommandResponse:
        """
        Respond with the Discord User ID / snowflake.
        """
        if not user_mentions:
            return Response(
                _D("Your user ID is `%(id)s`", ssd_) % {"id": author.id},
            )

        usr = user_mentions[0]
        return Response(
            _D("The user ID for `%(username)s` is `%(id)s`", ssd_)
            % {"username": usr.name, "id": usr.id},
        )

    @command_helper(
        usage=["{cmd} [all | users | roles | channels]"],
        desc=_Dd(
            "List the Discord IDs for the selected category.\n"
            "Returns all ID data by default, but one or more categories may be selected.\n"
            "This command is deprecated in favor of using Developer mode in Discord clients.\n"
        ),
    )
    async def cmd_listids(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        author: discord.Member,
        leftover_args: List[str],
        cat: str = "all",
    ) -> CommandResponse:
        """
        Fetch discord IDs from the guild.
        """

        cats = ["channels", "roles", "users"]

        if cat not in cats and cat != "all":
            cats_str = " ".join([f"`{c}`" for c in cats])
            return Response(
                _D("Valid categories: %(cats)s", ssd_) % {"cats": cats_str},
            )

        if cat == "all":
            requested_cats = cats
        else:
            requested_cats = [cat] + [
                c.strip(",") for c in leftover_args if c.strip(",") in cats
            ]

        data = [f"Your ID: {author.id}"]

        for cur_cat in requested_cats:
            rawudata = None

            if cur_cat == "users":
                data.append("\nUser IDs:")
                rawudata = [
                    f"{m.name} #{m.discriminator}: {m.id}" for m in guild.members
                ]

            elif cur_cat == "roles":
                data.append("\nRole IDs:")
                rawudata = [f"{r.name}: {r.id}" for r in guild.roles]

            elif cur_cat == "channels":
                data.append("\nText Channel IDs:")
                tchans = [
                    c for c in guild.channels if isinstance(c, discord.TextChannel)
                ]
                rawudata = [f"{c.name}: {c.id}" for c in tchans]

                rawudata.append("\nVoice Channel IDs:")
                vchans = [
                    c for c in guild.channels if isinstance(c, discord.VoiceChannel)
                ]
                rawudata.extend(f"{c.name}: {c.id}" for c in vchans)

            if rawudata:
                data.extend(rawudata)

        with BytesIO() as sdata:
            slug = slugify(guild.name)
            fname = f"{slug}-ids-{cat}.txt"
            sdata.writelines(d.encode("utf8") + b"\n" for d in data)
            sdata.seek(0)
            datafile = discord.File(sdata, filename=fname)
            msg_str = _D("Here are the IDs you requested:", ssd_)

            return Response(msg_str, send_to=author, files=[datafile])

    @command_helper(
        usage=["{cmd} [@USER]"],
        desc=_Dd(
            "Get a list of your permissions, or the permissions of the mentioned user."
        ),
    )
    async def cmd_perms(
        self,
        ssd_: Optional[GuildSpecificData],
        author: discord.Member,
        user_mentions: UserMentions,
        guild: discord.Guild,
        permissions: PermissionGroup,
        target: str = "",
    ) -> CommandResponse:
        """
        Generate a permission report fit for human consumption, attempt to DM the data.
        """

        user: Optional[MessageAuthor] = None
        if user_mentions:
            user = user_mentions[0]

        if not user_mentions and not target:
            user = author

        if not user_mentions and target:
            getuser = guild.get_member_named(target)
            if getuser is None:
                try:
                    user = await self.fetch_user(int(target))
                except (discord.NotFound, ValueError) as e:
                    raise exceptions.CommandError(
                        "Invalid user ID or server nickname, please double-check the ID and try again.",
                    ) from e
            else:
                user = getuser

        if not user:
            raise exceptions.CommandError(
                "Could not determine the discord User.  Try again.",
            )

        permissions = self.permissions.for_user(user)

        if user == author:
            perms = _D(
                "Your command permissions in %(server)s are:\n"
                "```\n%(permissions)s\n```",
                ssd_,
            ) % {
                "server": guild.name,
                "permissions": permissions.format(for_user=True),
            }
        else:
            perms = _D(
                "The command permissions for %(username)s in %(server)s are:\n"
                "```\n%(permissions)s\n```",
                ssd_,
            ) % {
                "username": user.name,
                "server": guild.name,
                "permissions": permissions.format(),
            }

        return Response(perms, send_to=author)

    @owner_only
    @command_helper(
        # fmt: off
        usage=[
            "{cmd} list\n"
            + _Dd("    Show loaded groups and list permission options.\n"),

            "{cmd} reload\n"
            + _Dd("    Reloads permissions from the permissions.ini file.\n"),

            "{cmd} add <GROUP>\n"
            + _Dd("    Add new group with defaults.\n"),

            "{cmd} remove <GROUP>\n"
            + _Dd("    Remove existing group.\n"),

            "{cmd} help <PERMISSION>\n"
            + _Dd("    Show help text for the permission option.\n"),

            "{cmd} show <GROUP> <PERMISSION>\n"
            + _Dd("    Show permission value for given group and permission.\n"),

            "{cmd} save <GROUP>\n"
            + _Dd("    Save permissions group to file.\n"),

            "{cmd} set <GROUP> <PERMISSION> [VALUE]\n"
            + _Dd("    Set permission value for the group.\n"),
        ],
        # fmt: on
        desc=_Dd("Manage permissions.ini configuration from within discord."),
    )
    async def cmd_setperms(
        self,
        ssd_: Optional[GuildSpecificData],
        user_mentions: UserMentions,
        leftover_args: List[str],
        option: str = "list",
    ) -> CommandResponse:
        """
        Allows management of permissions.ini settings for the bot.
        """
        # TODO: add a method to clear / reset to default.
        if user_mentions:
            raise exceptions.CommandError(
                "Permissions cannot use channel and user mentions at the same time.",
            )

        option = option.lower()
        valid_options = [
            "list",
            "add",
            "remove",
            "save",
            "help",
            "show",
            "set",
            "reload",
        ]
        if option not in valid_options:
            raise exceptions.CommandError(
                "Invalid option for command: `%(option)s`",
                fmt_args={"option": option},
            )

        # Reload the permissions file from disk.
        if option == "reload":
            try:
                new_permissions = Permissions(self._perms_file)
                # Set the owner ID in case it wasn't auto...
                new_permissions.set_owner_id(self.config.owner_id)
                await new_permissions.async_validate(self)

                self.permissions = new_permissions

                return Response(
                    _D("Permissions reloaded from file successfully!", ssd_)
                )
            except Exception as e:
                raise exceptions.CommandError(
                    "Unable to reload Permissions due to an error:\n%(raw_error)s",
                    fmt_args={"raw_error": e},
                ) from e

        # List permission groups and available permission options.
        if option == "list":
            gl = []
            for section in self.permissions.register.sections:
                gl.append(f"`{section}`\n")

            editable_opts = ""
            for opt in self.permissions.register.option_list:
                if opt.section != DEFAULT_PERMS_GROUP_NAME:
                    continue

                # if opt.editable:
                editable_opts += f"`{opt.option}`\n"

            groups = "".join(gl)
            opt_list = _D(
                "## Available Groups:\n%(groups)s\n"
                "## Available Options:\n"
                "%(options)s\n",
                ssd_,
            ) % {
                "groups": groups,
                "options": editable_opts,
            }
            return Response(
                opt_list,
                delete_after=self.config.delete_delay_long,
            )

        # sub commands beyond here need 2 leftover_args
        if option in ["help", "show", "save", "add", "remove"]:
            if len(leftover_args) < 1:
                raise exceptions.CommandError(
                    "You must provide a group or option name for this command.",
                )
        if option == "set" and len(leftover_args) < 3:
            raise exceptions.CommandError(
                "You must provide a group, option, and value to set for this command.",
            )

        # Get the command args from leftovers and check them.
        group_arg = ""
        option_arg = ""
        if option == "help":
            group_arg = DEFAULT_PERMS_GROUP_NAME
            option_arg = leftover_args.pop(0)
        else:
            group_arg = leftover_args.pop(0)
        if option in ["set", "show"]:
            if not leftover_args:
                raise exceptions.CommandError(
                    "The %(option)s sub-command requires a group and permission name.",
                    fmt_args={"option": option},
                )
            option_arg = leftover_args.pop(0)

        if user_mentions:
            leftover_args += [str(m.id) for m in user_mentions]
        value_arg = " ".join(leftover_args)

        if group_arg not in self.permissions.register.sections and option != "add":
            sects = ", ".join(self.permissions.register.sections)
            raise exceptions.CommandError(
                "The group `%(group)s` is not available.\n"
                "The available groups are:  %(sections)s",
                fmt_args={"group": group_arg, "sections": sects},
            )

        # Make sure the option is set if the sub-command needs it.
        if option in ["help", "set", "show"]:
            p_opt = self.permissions.register.get_config_option(group_arg, option_arg)
            if p_opt is None:
                option_arg = f"[{group_arg}] > {option_arg}"
                raise exceptions.CommandError(
                    "The permission `%(option)s` is not available.",
                    fmt_args={"option": option_arg},
                )
            opt = p_opt

        # Display some commentary about the option and its default.
        if option == "help":
            default = _D(
                "This permission can only be set by editing the permissions file.",
                ssd_,
            )
            # TODO:  perhaps use empty display values here.
            if opt.editable:
                dval = self.permissions.register.to_ini(opt, use_default=True)
                if dval == "":
                    dval = " "
                default = _D(
                    "By default this permission is set to: `%(value)s`",
                    ssd_,
                ) % {"value": dval}
            return Response(
                _D(
                    "**Permission:** `%(option)s`\n%(comment)s\n\n%(default)s",
                    ssd_,
                )
                % {
                    "option": opt.option,
                    "comment": opt.comment,
                    "default": default,
                },
                delete_after=self.config.delete_delay_long,
            )

        if option == "add":
            if group_arg in self.permissions.register.sections:
                raise exceptions.CommandError(
                    "Cannot add group `%(group)s` it already exists.",
                    fmt_args={"group": group_arg},
                )
            async with self.aiolocks["permission_edit"]:
                self.permissions.add_group(group_arg)

            return Response(
                _D(
                    "Successfully added new group:  `%(group)s`\n"
                    "You can now customize the permissions with:  `setperms set %(group)s`\n"
                    "Make sure to save the new group with:  `setperms save %(group)s`",
                    ssd_,
                )
                % {"group": group_arg}
            )

        if option == "remove":
            if group_arg in [DEFAULT_OWNER_GROUP_NAME, DEFAULT_PERMS_GROUP_NAME]:
                raise exceptions.CommandError("Cannot remove built-in group.")

            async with self.aiolocks["permission_edit"]:
                self.permissions.remove_group(group_arg)

            return Response(
                _D(
                    "Successfully removed group:  `%(group)s`\n"
                    "Make sure to save this change with:  `setperms save %(group)s`",
                    ssd_,
                )
                % {"group": group_arg}
            )

        # Save the current config value to the INI file.
        if option == "save":
            if group_arg == DEFAULT_OWNER_GROUP_NAME:
                raise exceptions.CommandError(
                    "The owner group is not editable.",
                )

            async with self.aiolocks["permission_edit"]:
                saved = self.permissions.save_group(group_arg)

            if not saved:
                raise exceptions.CommandError(
                    "Failed to save the group:  `%(group)s`",
                    fmt_args={"group": group_arg},
                )
            return Response(
                _D("Successfully saved the group:  `%(group)s`", ssd_)
                % {"group": group_arg}
            )

        # Display the current permissions group and INI file values.
        if option == "show":
            cur_val, ini_val, empty_display_val = self.permissions.register.get_values(
                opt
            )
            return Response(
                _D(
                    "**Permission:** `%(permission)s`\n"
                    "Current Value:  `%(loaded)s`\n"
                    "INI File Value:  `%(ini)s`",
                    ssd_,
                )
                % {
                    "permission": opt,
                    "loaded": cur_val if cur_val == "" else empty_display_val,
                    "ini": ini_val if ini_val == "" else empty_display_val,
                },
            )

        # update a permission, but don't save it.
        if option == "set":
            if group_arg == DEFAULT_OWNER_GROUP_NAME:
                raise exceptions.CommandError(
                    "The owner group is not editable.",
                )

            if not value_arg:
                raise exceptions.CommandError(
                    "You must provide a section, option, and value for this sub command.",
                )

            log.debug(
                "Doing set on %(option)s with value: %(value)s",
                {"option": opt, "value": value_arg},
            )
            async with self.aiolocks["permission_update"]:
                updated = self.permissions.update_option(opt, value_arg)
            if not updated:
                raise exceptions.CommandError(
                    "Permission `%(option)s` was not updated!",
                    fmt_args={"option": opt},
                )
            return Response(
                _D(
                    "Permission `%(permission)s` was updated for this session.\n"
                    "To save the change use `setperms save %(section)s %(option)s`",
                    ssd_,
                )
                % {
                    "permission": opt,
                    "section": opt.section,
                    "option": opt.option,
                }
            )

        return None

    @owner_only
    @command_helper(
        usage=["{cmd} <NAME>"],
        desc=_Dd(
            "Change the bot's username on discord.\n"
            "Note: The API may limit name changes to twice per hour."
        ),
    )
    async def cmd_setname(
        self, ssd_: Optional[GuildSpecificData], leftover_args: List[str], name: str
    ) -> CommandResponse:
        """
        Update the bot's username on discord.
        """

        name = " ".join([name, *leftover_args])

        try:
            if self.user:
                await self.user.edit(username=name)

        except discord.HTTPException as e:
            raise exceptions.CommandError(
                "Failed to change username. Did you change names too many times?\n"
                "Remember name changes are limited to twice per hour.\n"
            ) from e

        except Exception as e:
            raise exceptions.CommandError(
                "Failed to change username due to error:  \n%(raw_error)s",
                fmt_args={"raw_error": e},
            ) from e

        return Response(
            _D("Set the bot's username to `%(name)s`", ssd_) % {"name": name}
        )

    @command_helper(usage=["{cmd} <NICK>"], desc=_Dd("Change the MusicBot's nickname."))
    async def cmd_setnick(
        self,
        ssd_: Optional[GuildSpecificData],
        guild: discord.Guild,
        channel: MessageableChannel,
        leftover_args: List[str],
        nick: str,
    ) -> CommandResponse:
        """
        Update the bot nickname.
        """

        if not channel.permissions_for(guild.me).change_nickname:
            raise exceptions.CommandError("Unable to change nickname: no permission.")

        nick = " ".join([nick, *leftover_args])

        try:
            await guild.me.edit(nick=nick)
        except Exception as e:
            raise exceptions.CommandError(
                "Failed to set nickname due to error:  \n%(raw_error)s",
                fmt_args={"raw_error": e},
            ) from e

        return Response(
            _D("Set the bot's nickname to `%(nick)s`", ssd_) % {"nick": nick}
        )

    @command_helper(
        # fmt: off
        usage=[
            "{cmd} <PREFIX>\n"
            + _Dd("    Set a per-server command prefix."),
            "{cmd} clear\n"
            + _Dd("    Clear the per-server command prefix."),
        ],
        # fmt: on
        desc=_Dd(
            "Override the default command prefix in the server.\n"
            "The option EnablePrefixPerGuild must be enabled first."
        ),
    )
    async def cmd_setprefix(
        self, ssd_: Optional[GuildSpecificData], prefix: str
    ) -> CommandResponse:
        """
        Override the command prefix for the calling guild.
        """
        if ssd_ and self.config.enable_options_per_guild:
            # TODO: maybe filter odd unicode or bad words...
            # Filter custom guild emoji, bot can only use in-guild emoji.
            emoji_match = re.match(r"^<a?:(.+):(\d+)>$", prefix)
            if emoji_match:
                _e_name, e_id = emoji_match.groups()
                try:
                    emoji = self.get_emoji(int(e_id))
                except ValueError:
                    emoji = None
                if not emoji:
                    raise exceptions.CommandError(
                        "Custom emoji must be from this server to use as a prefix.",
                    )

            if "clear" == prefix:
                ssd_.command_prefix = ""
                await ssd_.save_guild_options_file()
                return Response(_D("Server command prefix is cleared.", ssd_))

            ssd_.command_prefix = prefix
            await ssd_.save_guild_options_file()
            return Response(
                _D("Server command prefix is now:  %(prefix)s", ssd_)
                % {"prefix": prefix},
                delete_after=self.config.delete_delay_long,
            )

        raise exceptions.CommandError(
            "Prefix per server is not enabled!\n"
            "Use the config command to update the prefix instead.",
        )

    @command_helper(
        # fmt: off
        usage=[
            "{cmd} show\n"
            + _Dd("    Show language codes available to use.\n"),

            "{cmd} set [LOCALE]\n"
            + _Dd("    Set the desired language for this server.\n"),

            "{cmd} reset\n"
            + _Dd("    Reset the server language to bot's default language.\n"),
        ],
        # fmt: on
        desc=_Dd("Manage the language used for messages in the calling server."),
    )
    async def cmd_language(
        self,
        ssd_: Optional[GuildSpecificData],
        subcmd: str = "show",
        lang_code: str = "",
    ) -> CommandResponse:
        """
        Allow management of per-server language settings.
        This does not depend on an option, outside of default language.
        """
        if not ssd_:
            raise exceptions.CommandError("This command can only be used in guilds.")

        subcmd = subcmd.lower()
        if subcmd not in ["show", "set", "reset"]:
            raise exceptions.CommandError(
                "Invalid sub-command given. Use the help command for more information."
            )

        langdir = pathlib.Path(DEFAULT_I18N_DIR)
        available_langs = set()
        for f in langdir.glob("*/LC_MESSAGES/*.mo"):
            available_langs.add(f.parent.parent.name)

        if subcmd == "show":
            return Response(
                _D(
                    "**Current Language:** `%(locale)s`\n"
                    "**Available Languages:**\n```\n%(languages)s```",
                    ssd_,
                )
                % {"locale": ssd_.lang_code, "languages": ", ".join(available_langs)}
            )

        if subcmd == "set":
            if lang_code not in available_langs:
                raise exceptions.CommandError(
                    "Cannot set language to `%(locale)s` it is not available.",
                    fmt_args={"locale": ssd_.lang_code},
                )
            ssd_.lang_code = lang_code
            return Response(
                _D("Language for this server now set to: `%(locale)s`", ssd_)
                % {"locale": lang_code},
            )

        if subcmd == "reset":
            ssd_.lang_code = ""
            return Response(
                _D(
                    "Language for this server has been reset to: `%(locale)s`",
                    ssd_,
                )
                % {"locale": DEFAULT_I18N_LANG},
            )

        return None

    @owner_only
    @command_helper(
        usage=["{cmd} [URL]"],
        desc=_Dd(
            "Change MusicBot's avatar.\n"
            "Attaching a file and omitting the url parameter also works.\n"
        ),
    )
    async def cmd_setavatar(
        self,
        ssd_: Optional[GuildSpecificData],
        message: discord.Message,
        av_url: str = "",
    ) -> CommandResponse:
        """
        Update the bot avatar with an image URL or attachment.
        """

        url = self.downloader.get_url_or_none(av_url)
        if message.attachments:
            thing = message.attachments[0].url
        elif url:
            thing = url
        else:
            raise exceptions.CommandError("You must provide a URL or attach a file.")

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            if self.user and self.session:
                async with self.session.get(thing, timeout=timeout) as res:
                    await self.user.edit(avatar=await res.read())

        except Exception as e:
            raise exceptions.CommandError(
                "Unable to change avatar due to error:  \n%(raw_error)s",
                fmt_args={"raw_error": e},
            ) from e

        return Response(_D("Changed the bot's avatar.", ssd_))

    @command_helper(
        desc=_Dd("Force MusicBot to disconnect from the discord server."),
    )
    async def cmd_disconnect(self, guild: discord.Guild) -> CommandResponse:
        """
        Forcibly disconnect the voice client from the calling server.
        """
        ssd = self.server_data[guild.id]
        voice_client = self.get_player_in(guild)
        if voice_client:
            await self.disconnect_voice_client(guild)
            return Response(
                _D("Disconnected from server `%(guild)s`", ssd) % {"guild": guild.name},
            )

        # check for a raw voice client instead.
        for vc in self.voice_clients:
            if not hasattr(vc.channel, "guild"):
                log.warning(
                    "MusicBot found a %s with no guild!  This could be a problem.",
                    type(vc),
                )
                continue

            if vc.channel.guild and vc.channel.guild == guild:
                await self.disconnect_voice_client(guild)
                return Response(
                    _D("Disconnected a playerless voice client? [BUG]", ssd)
                )

        raise exceptions.CommandError(
            "Not currently connected to server `%(guild)s`",
            fmt_args={"guild": guild.name},
        )

    @command_helper(
        # fmt: off
        usage=[
            "{cmd} [soft]\n"
            + _Dd("    Attempt to reload without process restart. The default option.\n"),
            "{cmd} full\n"
            + _Dd("    Attempt to restart the entire MusicBot process, reloading everything.\n"),
            "{cmd} uppip\n"
            + _Dd("    Full restart, but attempt to update pip packages before restart.\n"),
            "{cmd} upgit\n"
            + _Dd("    Full restart, but update MusicBot source code with git first.\n"),
            "{cmd} upgrade\n"
            + _Dd("    Attempt to update all dependency and source code before fully restarting.\n"),
        ],
        # fmt: on
        desc=_Dd(
            "Attempts to restart the MusicBot in a number of different ways.\n"
            "With no option supplied, a `soft` restart is implied.\n"
            "It can be used to remotely update a MusicBot installation, but should be used with care.\n"
            "If you have a service manager, we recommend using it instead of this command for restarts.\n"
        ),
    )
    async def cmd_restart(
        self,
        _player: Optional[MusicPlayer],
        guild: discord.Guild,
        channel: MessageableChannel,
        opt: str = "soft",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}restart [soft|full|upgrade|upgit|uppip]
        """
        # TODO:  move the update stuff to its own command, including update check.
        opt = opt.strip().lower()
        if opt not in ["soft", "full", "upgrade", "uppip", "upgit"]:
            raise exceptions.CommandError(
                "Invalid option given, use one of:  soft, full, upgrade, uppip, or upgit"
            )

        out_msg = ""
        if opt == "soft":
            out_msg = _D(
                "%(emoji)s Restarting current instance...",
                self.server_data[guild.id],
            ) % {"emoji": EMOJI_RESTART_SOFT}
        elif opt == "full":
            out_msg = _D(
                "%(emoji)s Restarting bot process...",
                self.server_data[guild.id],
            ) % {"emoji": EMOJI_RESTART_FULL}
        elif opt == "uppip":
            out_msg = _D(
                "%(emoji)s Will try to upgrade required pip packages and restart the bot...",
                self.server_data[guild.id],
            ) % {"emoji": EMOJI_UPDATE_PIP}
        elif opt == "upgit":
            out_msg = _D(
                "%(emoji)s Will try to update bot code with git and restart the bot...",
                self.server_data[guild.id],
            ) % {"emoji": EMOJI_UPDATE_GIT}
        elif opt == "upgrade":
            out_msg = _D(
                "%(emoji)s Will try to upgrade everything and restart the bot...",
                self.server_data[guild.id],
            ) % {"emoji": EMOJI_UPDATE_ALL}

        await self.safe_send_message(channel, Response(out_msg))

        if _player and _player.is_paused:
            _player.resume()

        await self.disconnect_all_voice_clients()
        if opt == "soft":
            raise exceptions.RestartSignal(code=exceptions.RestartCode.RESTART_SOFT)

        if opt == "full":
            raise exceptions.RestartSignal(code=exceptions.RestartCode.RESTART_FULL)

        if opt == "upgrade":
            raise exceptions.RestartSignal(
                code=exceptions.RestartCode.RESTART_UPGRADE_ALL
            )

        if opt == "uppip":
            raise exceptions.RestartSignal(
                code=exceptions.RestartCode.RESTART_UPGRADE_PIP
            )

        if opt == "upgit":
            raise exceptions.RestartSignal(
                code=exceptions.RestartCode.RESTART_UPGRADE_GIT
            )

        return None

    @command_helper(
        desc=_Dd("Disconnect from all voice channels and close the MusicBot process.")
    )
    async def cmd_shutdown(
        self, guild: discord.Guild, channel: MessageableChannel
    ) -> CommandResponse:
        """
        Disconnects from voice channels and raises the TerminateSignal
        which is hopefully respected by all the loopy async processes
        and then results in MusicBot cleanly shutting down.
        """
        await self.safe_send_message(
            channel,
            Response("\N{WAVING HAND SIGN}", force_text=True),
        )

        player = self.get_player_in(guild)
        if player and player.is_paused:
            player.resume()

        await self.disconnect_all_voice_clients()
        raise exceptions.TerminateSignal()

    @command_helper(
        # fmt: off
        usage=[
            "{cmd} <NAME | ID>\n"
            + _Dd("   Leave the discord server given by name or server ID."),
        ],
        # fmt: on
        desc=_Dd(
            "Force MusicBot to leave the given Discord server.\n"
            "Names are case-sensitive, so using an ID number is more reliable.\n"
        ),
    )
    async def cmd_leaveserver(
        self, ssd_: Optional[GuildSpecificData], val: str, leftover_args: List[str]
    ) -> CommandResponse:
        """
        Forces the bot to leave a server.
        """
        guild_id = 0
        guild_name = ""
        if leftover_args:
            guild_name = " ".join([val, *leftover_args])

        try:
            guild_id = int(val)
        except ValueError as e:
            if not guild_name:
                raise exceptions.CommandError("You must provide an ID or name.") from e

        if guild_id:
            leave_guild = self.get_guild(guild_id)

        if leave_guild is None:
            # Get guild by name
            leave_guild = discord.utils.get(self.guilds, name=guild_name)

        if leave_guild is None:
            raise exceptions.CommandError(
                "No guild was found with the ID or name `%(input)s`",
                fmt_args={"input": val},
            )

        await leave_guild.leave()

        guild_name = leave_guild.name
        guild_owner = (
            leave_guild.owner.name if leave_guild.owner else _D("Unknown Owner", ssd_)
        )
        guild_id = leave_guild.id
        # TODO: this response doesn't make sense if the command is issued
        # from within the server being left.
        return Response(
            _D(
                "Left the guild: `%(name)s` (Owner: `%(owner)s`, ID: `%(id)s`)",
                ssd_,
            )
            % {"name": guild_name, "owner": guild_owner, "id": guild_id}
        )

    @dev_only
    @command_helper(
        usage=["{cmd} [dry]"],
        desc=_Dd("Command used to automate testing of commands."),
    )
    async def cmd_testready(
        self, message: discord.Message, opt: str = ""
    ) -> CommandResponse:
        """Command used to signal command testing."""
        cmd_list = await self.gen_cmd_list(message, list_all_cmds=True)

        from .testrig import run_cmd_tests

        dry = False
        if opt.lower() == "dry":
            dry = True

        await run_cmd_tests(self, message, cmd_list, dry)

        return Response(
            f"Tested commands:\n```\n{', '.join(cmd_list)}```", force_text=True
        )

    @dev_only
    @command_helper(
        desc=_Dd(
            "This command issues a log at level CRITICAL, but does nothing else.\n"
            "Can be used to manually pinpoint events in the MusicBot log file.\n"
        ),
    )
    async def cmd_breakpoint(self, guild: discord.Guild) -> CommandResponse:
        """
        Do nothing but print a critical level error to the log.
        """
        uid = str(uuid.uuid4())
        ssd = self.server_data[guild.id]
        log.critical("Activating debug breakpoint ID: %(uuid)s", {"uuid": uid})
        return Response(_D("Logged breakpoint with ID:  %(uuid)s", ssd) % {"uuid": uid})

    @dev_only
    @command_helper(
        # fmt: off
        usage=[
            "{cmd}\n"
            + _Dd("    View most common types reported by objgraph.\n"),

            "{cmd} growth\n"
            + _Dd("    View limited objgraph.show_growth() output.\n"),

            "{cmd} leaks\n"
            + _Dd("    View most common types of leaking objects.\n"),

            "{cmd} leakstats\n"
            + _Dd("    View typestats of leaking objects.\n"),

            "{cmd} [objgraph.function(...)]\n"
            + _Dd("    Evaluate the given function and arguments on objgraph.\n"),
        ],
        # fmt: on
        desc=_Dd(
            "Interact with objgraph, if it is installed, to gain insight into memory usage.\n"
            "You can pass an arbitrary method with arguments (but no spaces!) that is a member of objgraph.\n"
            "Since this method evaluates arbitrary code, it is considered dangerous like the debug command.\n"
        )
    )
    async def cmd_objgraph(
        self,
        message: discord.Message,  # pylint: disable=unused-argument
        channel: MessageableChannel,
        func: str = "most_common_types()",
    ) -> CommandResponse:
        """
        Interact with objgraph to make it spill the beans.
        """
        if not objgraph:
            raise exceptions.CommandError(
                "Could not import `objgraph`, is it installed?"
            )

        await channel.typing()

        data: Any = None
        if func == "growth":
            f = StringIO()
            objgraph.show_growth(limit=10, file=f)
            f.seek(0)
            data = f.read()
            f.close()

        elif func == "leaks":
            f = StringIO()
            objgraph.show_most_common_types(
                objects=objgraph.get_leaking_objects(), file=f
            )
            f.seek(0)
            data = f.read()
            f.close()

        elif func == "leakstats":
            data = objgraph.typestats(objects=objgraph.get_leaking_objects())

        else:
            data = eval("objgraph." + func)  # pylint: disable=eval-used

        return Response(data, codeblock="py")

    @dev_only
    @command_helper(
        # fmt: off
        usage=[
            "{cmd} [PYCODE]\n",
        ],
        # fmt: on
        desc=_Dd(
            "This command will execute arbitrary python code in the command scope.\n"
            "First eval() is attempted, if exceptions are thrown exec() is tried next.\n"
            "If eval is successful, it's return value is displayed.\n"
            "If exec is successful, a value can be set to local variable `result` and that value will be returned.\n"
            "\n"
            "Multi-line code can be executed if wrapped in code-block.\n"
            "Otherwise only a single line may be executed.\n"
            "\n"
            "This command may be removed in a future version, and is used by developers to debug MusicBot behaviour.\n"
            "The danger of this command cannot be understated. Do not use it or give access to it if you do not understand the risks!\n"
        ),
    )
    async def cmd_debug(
        self,
        _player: Optional[MusicPlayer],
        message: discord.Message,  # pylint: disable=unused-argument
        channel: GuildMessageableChannels,  # pylint: disable=unused-argument
        guild: discord.Guild,  # pylint: disable=unused-argument
        author: discord.Member,  # pylint: disable=unused-argument
        permissions: PermissionGroup,  # pylint: disable=unused-argument
        *,
        data: str,
    ) -> CommandResponse:
        """
        Command for debugging MusicBot in real-time.
        It is dangerous and should maybe be removed in later versions...
        """
        codeblock = "```py\n{}\n```"
        result = None

        if data.startswith("```") and data.endswith("```"):
            code = "\n".join(data.lstrip("`").rstrip("`\n").split("\n")[1:])
        else:
            code = data.strip("` \n")

        try:
            run_type = "eval"
            result = eval(code)  # pylint: disable=eval-used
            log.debug("Debug code ran with eval().")
        except Exception:  # pylint: disable=broad-exception-caught
            try:
                run_type = "exec"
                # exec needs a fake locals so we can get `result` from it.
                lscope: Dict[str, Any] = {}
                # exec also needs locals() to be in globals() for access to work.
                gscope = globals().copy()
                gscope.update(locals().copy())
                exec(code, gscope, lscope)  # pylint: disable=exec-used
                log.debug("Debug code ran with exec().")
                result = lscope.get("result", result)
            except Exception as e:
                log.exception("Debug code failed to execute.")
                raise exceptions.CommandError(
                    "Failed to execute debug code:\n%(py_code)s\n"
                    "Exception: ```\n%(ex_name)s:\n%(ex_text)s```",
                    fmt_args={
                        "py_code": codeblock.format(code),
                        "ex_name": type(e).__name__,
                        "ex_text": e,
                    },
                ) from e

        if asyncio.iscoroutine(result):
            result = await result

        return Response(f"**{run_type}() Result:**\n{codeblock.format(result)}")

    @dev_only
    @command_helper(
        usage=["{cmd} < opts | perms | help >"],
        desc=_Dd(
            "Create 'markdown' for options, permissions, or commands from the code.\n"
            "The output is used to update GitHub Pages and is thus unsuitable for normal reference use."
        ),
    )
    async def cmd_makemarkdown(
        self,
        author: discord.Member,
        cfg: str = "opts",
    ) -> CommandResponse:
        """
        Command to generate markdown from various documentation in the code.
        The output is intended to update github pages and is thus unsuitable for normal use.
        """
        valid_opts = ["opts", "perms", "help"]
        if cfg not in valid_opts:
            opts = " ".join([f"`{o}`" for o in valid_opts])
            raise exceptions.CommandError(
                "Sub-command must be one of: %(options)s",
                fmt_args={"options": opts},
            )

        filename = "unknown.md"
        msg_str = ""
        if cfg == "opts":
            filename = "config_options.md"
            msg_str = "Config options described in Markdown:\n"
            config_md = self.config.register.export_markdown()

        if cfg == "perms":
            filename = "config_permissions.md"
            msg_str = "Permissions described in Markdown:\n"
            config_md = self.permissions.register.export_markdown()

        if cfg == "help":
            filename = "commands_help.md"
            msg_str = "All the commands and their usage attached."
            config_md = "### General Commands  \n\n"
            admin_commands = []
            dev_commands = []
            for att in dir(self):
                if att.startswith("cmd_"):
                    cmd = getattr(self, att, None)
                    doc = await self.gen_cmd_help(
                        att.replace("cmd_", ""), None, for_md=True
                    )
                    command_name = att.replace("cmd_", "").lower()
                    cmd_a = hasattr(cmd, "admin_only")
                    cmd_d = hasattr(cmd, "dev_cmd")
                    command_text = f"<details>\n  <summary>{command_name}</summary>\n{doc}\n</details>\n\n"
                    if cmd_a:
                        admin_commands.append(command_text)
                        continue
                    if cmd_d:
                        dev_commands.append(command_text)
                        continue
                    config_md += command_text
            config_md += f"### Owner Commands  \n\n{''.join(admin_commands)}"
            config_md += f"### Dev Commands  \n\n{''.join(dev_commands)}"

        with BytesIO() as fcontent:
            fcontent.write(config_md.encode("utf8"))
            fcontent.seek(0)
            datafile = discord.File(fcontent, filename=filename)

            return Response(msg_str, send_to=author, files=[datafile], force_text=True)

    @dev_only
    @command_helper(desc=_Dd("Makes default INI files."))
    async def cmd_makeini(
        self,
        ssd_: Optional[GuildSpecificData],
        cfg: str = "opts",
    ) -> CommandResponse:
        """Generates an example ini file, used for comparing example_options.ini to documentation in code."""
        valid_opts = ["opts", "perms"]
        if cfg not in valid_opts:
            opts = " ".join([f"`{o}`" for o in valid_opts])
            raise exceptions.CommandError(
                "Sub-command must be one of: %(options)s",
                fmt_args={"options": opts},
            )

        if cfg == "opts":
            self.config.register.write_default_ini(write_path(EXAMPLE_OPTIONS_FILE))

        if cfg == "perms":
            self.permissions.register.write_default_ini(write_path(EXAMPLE_PERMS_FILE))

        return Response(_D("Saved the requested INI file to disk. Go check it", ssd_))

    @owner_only
    @command_helper(
        desc=_Dd(
            "Display the current bot version and check for updates to MusicBot or dependencies.\n"
        ),
    )
    async def cmd_checkupdates(
        self, ssd_: Optional[GuildSpecificData], channel: MessageableChannel
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}checkupdates

        Display the current bot version and check for updates to MusicBot or dependencies.
        The option `GitUpdatesBranch` must be set to check for updates to MusicBot.
        """
        git_status = ""
        pip_status = ""
        updates = False

        await channel.typing()

        # attempt fetching git info.
        try:
            git_bin = shutil.which("git")
            if not git_bin:
                git_status = "Could not locate git executable."
                raise exceptions.CommandError("Could not locate git executable.")

            git_cmd_branch = [git_bin, "rev-parse", "--abbrev-ref", "HEAD"]
            git_cmd_check = [git_bin, "fetch", "--dry-run"]

            # extract current git branch name.
            cmd_branch = await asyncio.create_subprocess_exec(
                *git_cmd_branch,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            branch_stdout, _stderr = await cmd_branch.communicate()
            branch_name = branch_stdout.decode("utf8").strip()

            # check if fetch would update.
            cmd_check = await asyncio.create_subprocess_exec(
                *git_cmd_check,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            check_stdout, check_stderr = await cmd_check.communicate()
            check_stdout += check_stderr
            lines = check_stdout.decode("utf8").split("\n")

            # inspect dry run for our branch name to see if there are updates.
            commit_to = ""
            for line in lines:
                parts = line.split()
                if branch_name in parts:
                    commits = line.strip().split(" ", maxsplit=1)[0]
                    _commit_at, commit_to = commits.split("..")
                    break

            if not commit_to:
                git_status = _D("No updates in branch `%(branch)s` remote.", ssd_) % {
                    "branch": branch_name
                }
            else:
                git_status = _D(
                    "New commits are available in `%(branch)s` branch remote.",
                    ssd_,
                ) % {"branch": branch_name}
                updates = True
        except (OSError, ValueError, ConnectionError, RuntimeError):
            log.exception("Failed while checking for updates via git command.")
            git_status = _D("Error while checking, see logs for details.", ssd_)

        # attempt to fetch pip info.
        try:
            pip_cmd_check = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-U",
                "-r",
                "./requirements.txt",
                "--quiet",
                "--dry-run",
                "--report",
                "-",
            ]
            pip_cmd = await asyncio.create_subprocess_exec(
                *pip_cmd_check,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            pip_stdout, _stderr = await pip_cmd.communicate()
            pip_json = json.loads(pip_stdout)
            pip_packages = ""
            for pkg in pip_json.get("install", []):
                meta = pkg.get("metadata", {})
                if not meta:
                    log.debug("Package missing meta in pip report.")
                    continue
                name = meta.get("name", "")
                ver = meta.get("version", "")
                if name and ver:
                    pip_packages += _D(
                        "Update for `%(name)s` to version: `%(version)s`\n", ssd_
                    ) % {"name": name, "version": ver}
            if pip_packages:
                pip_status = pip_packages
                updates = True
            else:
                pip_status = _D("No updates for dependencies found.", ssd_)
        except (OSError, ValueError, ConnectionError):
            log.exception("Failed to get pip update status due to some error.")
            pip_status = _D("Error while checking, see logs for details.", ssd_)

        if updates:
            header = _D("There are updates for MusicBot available for download.", ssd_)
        else:
            header = _D("MusicBot is totally up-to-date!", ssd_)

        return Response(
            _D(
                "%(status)s\n\n"
                "**Source Code Updates:**\n%(git_status)s\n\n"
                "**Dependency Updates:**\n%(pip_status)s",
                ssd_,
            )
            % {
                "status": header,
                "git_status": git_status,
                "pip_status": pip_status,
            },
            delete_after=self.config.delete_delay_long,
        )

    @command_helper(
        desc=_Dd("Displays the MusicBot uptime, or time since last start / restart."),
    )
    async def cmd_uptime(self, ssd_: Optional[GuildSpecificData]) -> CommandResponse:
        """
        Usage:
            {command_prefix}uptime

        Displays the MusicBot uptime, since last start/restart.
        """
        uptime = time.time() - self._init_time
        delta = format_song_duration(uptime)
        name = DEFAULT_BOT_NAME
        if self.user:
            name = self.user.name
        return Response(
            _D("%(name)s has been online for `%(time)s`", ssd_)
            % {"name": name, "time": delta},
        )

    @owner_only
    @command_helper(
        desc=_Dd(
            "Display latency information for Discord API and all connected voice clients."
        ),
    )
    async def cmd_botlatency(
        self, ssd_: Optional[GuildSpecificData]
    ) -> CommandResponse:
        """
        Command botlatency Prints latency info for everything.
        """
        vclats = ""
        cur_bw: float = 0
        for vc in self.voice_clients:
            if not isinstance(vc, discord.VoiceClient) or not hasattr(
                vc.channel, "rtc_region"
            ):
                log.debug("Got a strange voice client entry.")
                continue

            kbitrate = int(vc.channel.bitrate / 1000)
            cur_bw += kbitrate
            vl = vc.latency * 1000
            vla = vc.average_latency * 1000
            # Display Auto for region instead of None
            region = vc.channel.rtc_region or "auto"
            vclats += _D(
                "- `%(delay).0f ms` (`%(avg).0f ms` Avg.) in region: `%(region)s` using %(bitrate)s kbps.\n",
                ssd_,
            ) % {"delay": vl, "avg": vla, "region": region, "bitrate": kbitrate}

        if not vclats:
            vclats = _D("No voice clients connected.\n", ssd_)

        sl = self.latency * 1000
        cur_suffix = "kbps"
        if cur_bw > 1000:
            cur_bw /= 1000
            cur_suffix = "mbps"
        return Response(
            _D(
                "**API Latency:** `%(delay).0f ms`\n"
                "**VoiceClient Latency:**\n%(voices)s\n"
                "Using approximately %(rate).2f %(suffix)s of bandwidth total.",
                ssd_,
            )
            % {"delay": sl, "voices": vclats, "rate": cur_bw, "suffix": cur_suffix}
        )

    @command_helper(
        desc=_Dd("Display API latency and Voice latency if MusicBot is connected."),
    )
    async def cmd_latency(
        self, ssd_: Optional[GuildSpecificData], guild: discord.Guild
    ) -> CommandResponse:
        """
        Command latency for current guild / voice connections.
        """

        voice_lat = ""
        if guild.id in self.players:
            vc = self.players[guild.id].voice_client
            if vc:
                bitrate = int(vc.channel.bitrate / 1000)
                vl = vc.latency * 1000
                vla = vc.average_latency * 1000
                # TRANSLATORS: short for automatic, displayed when voice region is not selected.
                vcr = vc.channel.rtc_region or _D("auto", ssd_)
                voice_lat = _D(
                    "\n**Voice Latency:** `%(delay).0f ms` (`%(average).0f ms` Avg.) in region `%(region)s` using %(bitrate)s kbps",
                    ssd_,
                ) % {"delay": vl, "average": vla, "region": vcr, "bitrate": bitrate}
        sl = self.latency * 1000
        return Response(
            _D("**API Latency:** `%(delay).0f ms`%(voice)s", ssd_)
            % {"delay": sl, "voice": voice_lat},
        )

    @command_helper(
        desc=_Dd("Display MusicBot version number in the chat."),
    )
    async def cmd_botversion(
        self, ssd_: Optional[GuildSpecificData]
    ) -> CommandResponse:
        """Command to check MusicBot version string in discord."""
        return Response(
            _D(
                "https://github.com/Just-Some-Bots/MusicBot\n"
                "Current version:  `%(version)s`",
                ssd_,
            )
            % {"version": BOTVERSION}
        )

    @owner_only
    @command_helper(
        # fmt: off
        usage=[
            "{cmd}\n"
            + _Dd("    Update the cookies.txt file using a cookies.txt attachment."),

            "{cmd} [off | on]\n"
            + _Dd("    Enable or disable cookies.txt file without deleting it."),
        ],
        # fmt: on
        desc=_Dd(
            "Allows management of the cookies feature in yt-dlp.\n"
            "When updating cookies, you must upload a file named cookies.txt\n"
            "If cookies are disabled, uploading will enable the feature.\n"
            "Uploads will delete existing cookies, including disabled cookies file.\n"
            "\n"
            "WARNING:\n"
            "  Copying cookies can risk exposing your personal information or accounts,\n"
            "  and may result in account bans or theft if you are not careful.\n"
            "  It is not recommended due to these risks, and you should not use this\n"
            "  feature if you do not understand how to avoid the risks."
        ),
    )
    async def cmd_setcookies(
        self, ssd_: Optional[GuildSpecificData], message: discord.Message, opt: str = ""
    ) -> CommandResponse:
        """
        setcookies command allows management of yt-dlp cookies feature.
        """
        opt = opt.lower()
        if opt == "on":
            if self.downloader.cookies_enabled:
                raise exceptions.CommandError("Cookies already enabled.")

            if (
                not self.config.disabled_cookies_path.is_file()
                and not self.config.cookies_path.is_file()
            ):
                raise exceptions.CommandError(
                    "Cookies must be uploaded to be enabled. (Missing cookies file.)"
                )

            # check for cookies file and use it.
            if self.config.cookies_path.is_file():
                self.downloader.enable_ytdl_cookies()
            else:
                # or rename the file as needed.
                try:
                    self.config.disabled_cookies_path.rename(self.config.cookies_path)
                    self.downloader.enable_ytdl_cookies()
                except OSError as e:
                    raise exceptions.CommandError(
                        "Could not enable cookies due to error:  %(raw_error)s",
                        fmt_args={"raw_error": e},
                    ) from e
            return Response(_D("Cookies have been enabled.", ssd_))

        if opt == "off":
            if self.downloader.cookies_enabled:
                self.downloader.disable_ytdl_cookies()

            if self.config.cookies_path.is_file():
                try:
                    self.config.cookies_path.rename(self.config.disabled_cookies_path)
                except OSError as e:
                    raise exceptions.CommandError(
                        "Could not rename cookies file due to error:  %(raw_error)s\n"
                        "Cookies temporarily disabled and will be re-enabled on next restart.",
                        fmt_args={"raw_error": e},
                    ) from e
            return Response(_D("Cookies have been disabled.", ssd_))

        # check for attached files and inspect them for use.
        if not message.attachments:
            raise exceptions.CommandError(
                "No attached uploads were found, try again while uploading a cookie file."
            )

        # check for a disabled cookies file and remove it.
        if self.config.disabled_cookies_path.is_file():
            try:
                self.config.disabled_cookies_path.unlink()
            except OSError as e:
                log.warning(
                    "Could not remove old, disabled cookies file:  %(raw_error)s",
                    {"raw_error": e},
                )

        # simply save the uploaded file in attachment 1 as cookies.txt.
        try:
            await message.attachments[0].save(self.config.cookies_path)
        except discord.HTTPException as e:
            raise exceptions.CommandError(
                "Error downloading the cookies file from discord:  %(raw_error)s",
                fmt_args={"raw_error": e},
            ) from e
        except OSError as e:
            raise exceptions.CommandError(
                "Could not save cookies to disk:  %(raw_error)s",
                fmt_args={"raw_error": e},
            ) from e

        # enable cookies if it is not already.
        if not self.downloader.cookies_enabled:
            self.downloader.enable_ytdl_cookies()

        return Response(_D("Cookies uploaded and enabled.", ssd_))

    async def on_message(self, message: discord.Message) -> None:
        """
        Event called by discord.py when any message is sent to/around the bot.
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_message
        """
        await self.wait_until_ready()

        if not message.channel:
            log.debug("Got a message with no channel, somehow:  %s", message)
            return

        if message.channel.guild:
            command_prefix = self.server_data[message.channel.guild.id].command_prefix
        else:
            command_prefix = self.config.command_prefix
        message_content = message.content.strip()
        # if the prefix is an emoji, silently remove the space often auto-inserted after it.
        # this regex will get us close enough to knowing if an unicode emoji is in the prefix...
        emoji_regex = re.compile(r"^(<a?:.+:\d+>|:.+:|[^ -~]+)$")
        if emoji_regex.match(command_prefix):
            message_content = message_content.replace(
                f"{command_prefix} ", command_prefix, 1
            )

        # lastly check if we allow bot mentions for commands.
        self_mention = "<@MusicBot>"  # placeholder
        if self.user:
            self_mention = f"<@{self.user.id}>"
        if not message_content.startswith(command_prefix) and (
            self.config.commands_via_mention
            and not message_content.startswith(self_mention)
        ):
            return

        # ignore self
        if message.author == self.user:
            log.warning("Ignoring command from myself (%s)", message.content)
            return

        # ignore bots
        if (
            message.author.bot
            and message.author.id not in self.config.bot_exception_ids
        ):
            log.warning("Ignoring command from other bot (%s)", message.content)
            return

        # ignore any channel type we can't respond to. Also type checking.
        if (not isinstance(message.channel, discord.abc.GuildChannel)) and (
            not isinstance(message.channel, discord.abc.PrivateChannel)
        ):
            log.warning(
                "Ignoring command from channel of type:  %s", type(message.channel)
            )
            return

        # if via mentions, we treat the mention as a prefix for args extraction.
        if self.config.commands_via_mention and message_content.startswith(
            self_mention
        ):
            # replace the space often included after mentions.
            message_content = message_content.replace(
                f"{self_mention} ", self_mention, 1
            )
            command_prefix = self_mention

        # handle spaces inside of a command prefix.
        # this is only possible through manual edits to the config.
        if " " in command_prefix:
            invalid_prefix = command_prefix
            command_prefix = command_prefix.replace(" ", "_")
            message_content = message_content.replace(invalid_prefix, command_prefix, 1)

        # Extract the command name and args from the message content.
        command, *args = message_content.split(" ")
        command = command[len(command_prefix) :].lower().strip()

        # Check if the incomming command is a "natural" command.
        handler = getattr(self, "cmd_" + command, None)
        if not handler:
            # If no natural command was found, check for aliases when enabled.
            if self.config.usealias:
                # log.debug("Checking for alias with: %s", command)
                command, alias_arg_str = self.aliases.from_alias(command)
                handler = getattr(self, "cmd_" + command, None)
                if not handler:
                    return
                # log.debug("Alias found:  %s %s", command, alias_arg_str)
                # Complex aliases may have args of their own.
                # We assume the user args go after the alias args.
                if alias_arg_str:
                    args = alias_arg_str.split(" ") + args
            # Or ignore aliases, and this non-existent command.
            else:
                return

        # Legacy / Backwards compat, remap alternative sub-command args.
        args = getattr(handler, "remap_subcommands", list)(args)

        # check for private channel usage, only limited commands can be used in DM.
        if isinstance(message.channel, discord.abc.PrivateChannel):
            if not (
                message.author.id == self.config.owner_id
                and getattr(handler, "cmd_in_dm", False)
            ):
                await self.safe_send_message(
                    message.channel,
                    ErrorResponse(
                        _D("You cannot use this bot in private messages.", None)
                    ),
                )
                return

        # Make sure we only listen in guild channels we are bound to.
        # Unless unbound servers are allowed in addition to bound ones.
        if (
            self.config.bound_channels
            and message.guild
            and message.channel.id not in self.config.bound_channels
        ):
            log.debug(
                "MusicBot has bound channel config and caller channel is not in bound channels."
            )
            if self.config.unbound_servers:
                if any(
                    c.id in self.config.bound_channels for c in message.guild.channels
                ):
                    log.debug(
                        "Caller server has a bound channel, caller channel ignored."
                    )
                    return
                log.debug("Caller server has no bound channel, caller allowed.")
            else:
                log.debug(
                    "Unbound channel (%s) in server:  %s",
                    message.channel,
                    message.guild,
                )
                return

        # check for user id or name in blacklist.
        if (
            self.config.user_blocklist.is_blocked(message.author)
            and message.author.id != self.config.owner_id
        ):
            # TODO:  maybe add a config option to enable telling users they are blocked.
            log.warning(
                "User in block list: %(id)s/%(name)s  tried command: %(command)s",
                {"id": message.author.id, "name": message.author, "comand": command},
            )
            return

        # all command validation checks passed, log a successful message
        log.info(
            "Message from %(id)s/%(name)s: %(message)s",
            {
                "id": message.author.id,
                "name": message.author,
                "message": message_content.replace("\n", "\n... "),
            },
        )

        # Get user's musicbot permissions for use in later checks and commands.
        user_permissions = self.permissions.for_user(message.author)

        # Extract the function signature of the cmd_* command to assign proper values later.
        argspec = inspect.signature(handler)
        params = argspec.parameters.copy()
        response: Optional[MusicBotResponse] = None
        ssd = None
        if message.channel.guild:
            ssd = self.server_data[message.channel.guild.id]

        # Check permissions, assign arguments, and process the command call.
        try:
            # check non-voice permission.
            if (
                user_permissions.ignore_non_voice
                and command in user_permissions.ignore_non_voice
            ):
                await self._check_ignore_non_voice(message)

            # Test for command permissions.
            sub_cmd = args[0] if len(args) else ""
            if (
                message.author.id != self.config.owner_id
                and not user_permissions.can_use_command(command, sub_cmd)
            ):
                raise exceptions.PermissionsError(
                    "This command is not allowed for your permissions group:  %(group)s",
                    fmt_args={"group": user_permissions.name},
                )

            # populate the requested command signature args.
            handler_kwargs: Dict[str, Any] = {}
            if params.pop("message", None):
                handler_kwargs["message"] = message

            if params.pop("channel", None):
                handler_kwargs["channel"] = message.channel

            if params.pop("author", None):
                handler_kwargs["author"] = message.author

            if params.pop("guild", None):
                handler_kwargs["guild"] = message.guild

            # this is the player-required arg, it prompts to be summoned if not already in voice.
            # or otherwise denies use if non-guild voice is used.
            if params.pop("player", None):
                # however, it needs a voice channel to connect to.
                if (
                    isinstance(message.author, discord.Member)
                    and message.guild
                    and message.author.voice
                    and message.author.voice.channel
                ):
                    handler_kwargs["player"] = await self.get_player(
                        message.author.voice.channel, create=user_permissions.summonplay
                    )
                else:
                    # TODO: enable ignore-non-voice commands to work here
                    # by looking for the first available VC if author has none.
                    raise exceptions.CommandError(
                        "This command requires you to be in a Voice channel."
                    )

            # this is the optional-player arg.
            if params.pop("_player", None):
                if message.guild:
                    handler_kwargs["_player"] = self.get_player_in(message.guild)
                else:
                    handler_kwargs["_player"] = None

            if params.pop("permissions", None):
                handler_kwargs["permissions"] = user_permissions

            # this arg only works in guilds.
            if params.pop("user_mentions", None):

                def member_or_user(
                    uid: int,
                ) -> Optional[Union[discord.Member, discord.User]]:
                    if message.guild:
                        m = message.guild.get_member(uid)
                        if m:
                            return m
                    return self.get_user(uid)

                handler_kwargs["user_mentions"] = []
                for um_id in message.raw_mentions:
                    m = member_or_user(um_id)
                    if m is not None:
                        handler_kwargs["user_mentions"].append(m)

            # this arg only works in guilds.
            if params.pop("channel_mentions", None):
                if message.guild:
                    handler_kwargs["channel_mentions"] = list(
                        map(message.guild.get_channel, message.raw_channel_mentions)
                    )
                else:
                    handler_kwargs["channel_mentions"] = []

            if params.pop("voice_channel", None):
                if message.guild:
                    handler_kwargs["voice_channel"] = (
                        message.guild.me.voice.channel
                        if message.guild.me.voice
                        else None
                    )
                else:
                    handler_kwargs["voice_channel"] = None

            if params.pop("ssd_", None):
                handler_kwargs["ssd_"] = ssd

            if params.pop("leftover_args", None):
                handler_kwargs["leftover_args"] = args

            # special case to auto populate "song_url" with attachment url.
            if params.get("song_url", None) and message.attachments and not args:
                params.pop("song_url")
                handler_kwargs["song_url"] = message.attachments[0].url

            for key, param in list(params.items()):
                # parse (*args) as a list of args
                if param.kind == param.VAR_POSITIONAL:
                    handler_kwargs[key] = args
                    params.pop(key)
                    continue

                # parse (*, args) as args rejoined as a string
                # multiple of these arguments will have the same value
                if param.kind == param.KEYWORD_ONLY and param.default == param.empty:
                    handler_kwargs[key] = " ".join(args)
                    params.pop(key)
                    continue

                # Ignore keyword args with default values when the command had no arguments
                if not args and param.default is not param.empty:
                    params.pop(key)
                    continue

                # Assign given values to positional arguments
                if args:
                    arg_value = args.pop(0)
                    handler_kwargs[key] = arg_value
                    params.pop(key)

            # Invalid usage, return docstring
            if params:
                log.debug(
                    "Invalid command usage, missing values for params: %(params)r",
                    {"params": params},
                )
                response = await self.cmd_help(
                    ssd, message, message.channel.guild, command
                )
                if response:
                    response.reply_to = message
                    await self.safe_send_message(message.channel, response)
                return

            response = await handler(**handler_kwargs)
            if response and isinstance(response, MusicBotResponse):
                # Set a default response title if none is set.
                if not response.title:
                    response.title = _D("**Command:** %(name)s", ssd) % {
                        "name": command
                    }

                # Determine if the response goes to a calling channel or a DM.
                send_kwargs: Dict[str, Any] = {}
                send_to = message.channel
                if response.send_to:
                    send_to = response.send_to
                    response.sent_from = message.channel

                # always reply to the caller, no reason not to.
                response.reply_to = message

                await self.safe_send_message(send_to, response, **send_kwargs)

        except (
            exceptions.CommandError,
            exceptions.HelpfulError,
            exceptions.ExtractionError,
            exceptions.MusicbotException,
        ) as e:
            log.error(
                "Error in %(command)s: %(err_name)s: %(err_text)s",
                {
                    "command": command,
                    "err_name": e.__class__.__name__,
                    "err_text": _L(e.message) % e.fmt_args,
                },
                exc_info=True,
            )
            er = ErrorResponse(
                _D(e.message, ssd) % e.fmt_args,
                codeblock="text",
                title="Error",
                reply_to=message,
            )
            await self.safe_send_message(message.channel, er)

        # raise custom signals for shutdown and restart.
        except exceptions.Signal:
            raise

        # Catch everything else to keep bugs from bringing down the bot...
        except Exception:  # pylint: disable=broad-exception-caught
            log.error(
                "Exception while handling command: %(command)s",
                {"command": command},
                exc_info=self.config.debug_mode,
            )
            if self.config.debug_mode:
                er = ErrorResponse(
                    traceback.format_exc(),
                    codeblock="text",
                    title=_D("Exception Error", ssd),
                    reply_to=message,
                )
                await self.safe_send_message(message.channel, er)

        finally:
            if self.config.delete_invoking:
                self.create_task(
                    self._wait_delete_msg(message, self.config.delete_delay_short)
                )

    async def gen_cmd_help(
        self, cmd_name: str, guild: Optional[discord.Guild], for_md: bool = False
    ) -> str:
        """
        Generates help for the given command from documentation in code.

        :param: cmd_name:  The command to get help for.
        :param: guild:  Guild where the call comes from.
        :param: for_md:  If true, output as "markdown" for Github Pages.
        """
        cmd = getattr(self, f"cmd_{cmd_name}", None)
        if not cmd:
            log.debug("Cannot generate help for missing command:  %s", cmd_name)
            return ""

        if not hasattr(cmd, "help_usage") or not hasattr(cmd, "help_desc"):
            log.critical("Missing help data for command:  %s", cmd_name)

        cmd_usage = getattr(cmd, "help_usage", [])
        cmd_desc = getattr(cmd, "help_desc", "")
        emoji_prefix = False
        ssd = None
        if guild:
            ssd = self.server_data[guild.id]
            prefix_l = ssd.command_prefix
        else:
            prefix_l = self.config.command_prefix
        # Its OK to skip unicode emoji here, they render correctly inside of code boxes.
        emoji_regex = re.compile(r"^(<a?:.+:\d+>|:.+:)$")
        prefix_note = ""
        if emoji_regex.match(prefix_l):
            emoji_prefix = True
            prefix_note = _D(
                "**Example with prefix:**\n%(prefix)s`%(command)s ...`\n",
                ssd,
            ) % {"prefix": prefix_l, "command": cmd_name}

        desc = _D(cmd_desc, ssd) or _D("No description given.\n", ssd)
        if desc[-1] != "\n":
            desc += "\n"
        usage = _D("No usage given.", ssd)
        if cmd_usage and isinstance(cmd_usage, list):
            cases = []
            for case in cmd_usage:
                if "\n" in case:
                    bits = case.split("\n", maxsplit=1)
                    example = bits[0]
                    text = ""
                    if len(bits) > 1 and bits[1]:
                        text = "\n"
                        text += _D(bits[1], ssd)
                    cases.append(f"{example}{text}")
                else:
                    cases.append(case)
            usage = "\n".join(cases)
            if emoji_prefix:
                usage = usage.replace("{prefix}", "")
            else:
                usage = usage.replace("{prefix}", prefix_l)

        if for_md:
            usage = usage.replace(prefix_l, "")
            # usage = usage.replace("\n", "<br>\n")
            desc = desc.replace("\n", "<br>\n")
            return (
                "<strong>Example usage:</strong><br>  \n"
                "{%% highlight text %%}\n"
                "%(usage)s\n"
                "{%% endhighlight %%}\n"
                "<strong>Description:</strong><br>  \n"
                "%(desc)s"
            ) % {"usage": usage, "desc": desc}

        return _D(
            "**Example usage:**\n"
            "```%(usage)s```\n"
            "%(prefix_note)s"
            "**Description:**\n"
            "%(desc)s",
            ssd,
        ) % {"usage": usage, "prefix_note": prefix_note, "desc": desc}

    async def gen_cmd_list(
        self, message: discord.Message, list_all_cmds: bool = False
    ) -> List[str]:
        """
        Return a list of valid command names, without prefix, for the given message author.
        Commands marked with @dev_cmd are never included.

        Param `list_all_cmds` set True will list commands regardless of permission restrictions.
        """
        commands = []
        for att in dir(self):
            # This will always return at least cmd_help, since they needed perms to run this command
            if att.startswith("cmd_") and not hasattr(getattr(self, att), "dev_cmd"):
                user_permissions = self.permissions.for_user(message.author)
                command_name = att.replace("cmd_", "").lower()
                whitelist = user_permissions.command_whitelist
                blacklist = user_permissions.command_blacklist
                if list_all_cmds:
                    commands.append(command_name)

                elif blacklist and command_name in blacklist:
                    pass

                elif whitelist and command_name not in whitelist:
                    pass

                else:
                    commands.append(command_name)
        return commands

    async def on_inactivity_timeout_expired(
        self, voice_channel: VoiceableChannel
    ) -> None:
        """
        A generic event called by MusicBot when configured channel or player
        activity timers reach their end.
        """
        guild = voice_channel.guild

        if isinstance(voice_channel, (discord.VoiceChannel, discord.StageChannel)):
            ssd = self.server_data[guild.id]
            last_np_msg = ssd.last_np_msg
            if last_np_msg is not None and last_np_msg.channel:
                channel = last_np_msg.channel
                r = Response(
                    _D("Leaving voice channel %(channel)s due to inactivity.", ssd)
                    % {"channel": voice_channel.name},
                )
                await self.safe_send_message(channel, r)

            log.info(
                "Leaving voice channel %s in %s due to inactivity.",
                voice_channel.name,
                voice_channel.guild,
            )
            await self.disconnect_voice_client(guild)

    async def on_connect(self) -> None:
        """Event called by discord.py when the Client has connected to the API."""
        if self.init_ok:
            log.info("MusicBot has become connected.")

    async def on_disconnect(self) -> None:
        """Event called by discord.py any time bot is disconnected, or fails to connect."""
        log.info("MusicBot has become disconnected.")

    async def on_socket_event_type(self, event_type: str) -> None:
        """Event called by discord.py on any socket event."""
        log.everything(  # type: ignore[attr-defined]
            "Got a Socket Event:  %s", event_type
        )

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """
        Event called by discord.py when a VoiceClient changes state in any way.
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_voice_state_update
        """
        if not self.init_ok:
            if self.config.debug_mode:
                log.warning(
                    "VoiceState updated before on_ready finished"
                )  # TODO: remove after coverage testing
            return  # Ignore stuff before ready

        guild = member.guild
        follow_user = self.server_data[guild.id].follow_user

        if self.config.leave_inactive_channel and not follow_user:
            event = self.server_data[guild.id].get_event("inactive_vc_timer")

            if before.channel and self.user in before.channel.members:
                if str(before.channel.id) in str(self.config.autojoin_channels):
                    log.info(
                        "Ignoring %s in %s as it is a bound voice channel.",
                        before.channel.name,
                        before.channel.guild,
                    )

                elif is_empty_voice_channel(
                    before.channel, include_bots=self.config.bot_exception_ids
                ):
                    log.info(
                        "%s has been detected as empty. Handling timeouts.",
                        before.channel.name,
                    )
                    self.create_task(
                        self.handle_vc_inactivity(guild), name="MB_HandleInactiveVC"
                    )
            elif after.channel and member != self.user:
                if self.user in after.channel.members:
                    if event.is_active():
                        # Added to not spam the console with the message for every person that joins
                        log.info(
                            "A user joined %s, cancelling timer.",
                            after.channel.name,
                        )
                    event.set()

            if (
                member == self.user and before.channel and after.channel
            ):  # bot got moved from channel to channel
                # if not any(not user.bot for user in after.channel.members):
                if is_empty_voice_channel(
                    after.channel, include_bots=self.config.bot_exception_ids
                ):
                    log.info(
                        "The bot got moved and the voice channel %s is empty. Handling timeouts.",
                        after.channel.name,
                    )
                    self.create_task(
                        self.handle_vc_inactivity(guild), name="MB_HandleInactiveVC"
                    )
                else:
                    if event.is_active():
                        log.info(
                            "The bot got moved and the voice channel %s is not empty.",
                            after.channel.name,
                        )
                        event.set()

        # Voice state updates for bot itself.
        if member == self.user:
            # check if bot was disconnected from a voice channel
            if not after.channel and before.channel and not self.network_outage:
                if await self._handle_api_disconnect(before):
                    return

            # if the bot was moved to a stage channel, request speaker.
            # similarly, make the bot request speaker when suppressed.
            if (
                after.channel != before.channel
                and after.suppress
                and isinstance(after.channel, discord.StageChannel)
            ) or (
                after.channel == before.channel
                and after.suppress
                and before.suppress
                and after.requested_to_speak_at is None
                and isinstance(after.channel, discord.StageChannel)
            ):
                try:
                    log.info(
                        "MusicBot is requesting to speak in channel: %s",
                        after.channel.name,
                    )
                    # this has the same effect as edit(suppress=False)
                    await after.channel.guild.me.request_to_speak()
                except discord.Forbidden:
                    log.exception("MusicBot does not have permission to speak.")
                except (discord.HTTPException, discord.ClientException):
                    log.exception("MusicBot could not request to speak.")

        if before.channel:
            player = self.get_player_in(before.channel.guild)
            if player and not follow_user:
                await self._handle_guild_auto_pause(player)
        if after.channel:
            player = self.get_player_in(after.channel.guild)
            if player and not follow_user:
                await self._handle_guild_auto_pause(player)

        if follow_user and member.id == follow_user.id:
            # follow-user has left the server voice channels.
            if after.channel is None:
                log.debug("No longer following user %s", member)
                self.server_data[member.guild.id].follow_user = None
                if player and not self.server_data[member.guild.id].auto_join_channel:
                    await self._handle_guild_auto_pause(player)
                if player and self.server_data[member.guild.id].auto_join_channel:
                    if (
                        player.voice_client.channel
                        != self.server_data[member.guild.id].auto_join_channel
                    ):
                        # move_to does not support setting deafen flags nor keep
                        # the flags set from initial connection.
                        # await player.voice_client.move_to(
                        #     self.server_data[member.guild.id].auto_join_channel
                        # )
                        await member.guild.change_voice_state(
                            channel=self.server_data[member.guild.id].auto_join_channel,
                            self_deaf=self.config.self_deafen,
                        )

            # follow-user has moved to a new channel.
            elif before.channel != after.channel and player:
                log.debug(
                    "Following user `%(user)s` to channel:  %(channel)s",
                    {"user": member, "channel": after.channel},
                )
                if player.is_playing:
                    player.pause()
                # using move_to does not respect the self-deafen flags from connect
                # nor does it allow us to set them...
                # await player.voice_client.move_to(after.channel)
                await member.guild.change_voice_state(
                    channel=after.channel,
                    self_deaf=self.config.self_deafen,
                )
                if player.is_paused:
                    player.resume()

    async def _handle_api_disconnect(self, before: discord.VoiceState) -> bool:
        """
        Method called from on_voice_state_update when MusicBot is disconnected from voice.
        """
        if not before.channel:
            log.debug("VoiceState disconnect before.channel is None.")
            return False

        o_guild = self.get_guild(before.channel.guild.id)
        o_vc: Optional[discord.VoiceClient] = None
        close_code: Optional[int] = None
        state: Optional[Any] = None
        if o_guild is not None and isinstance(
            o_guild.voice_client, discord.VoiceClient
        ):
            o_vc = o_guild.voice_client
            # borrow this for logging sake.
            close_code = (
                o_vc._connection.ws._close_code  # pylint: disable=protected-access
            )
            state = o_vc._connection.state  # pylint: disable=protected-access

        # These conditions are met when API terminates a voice client.
        # This could be a user initiated disconnect, but we have no way to tell.
        # Normally VoiceClients should auto-reconnect. However attempting to wait
        # by using VoiceClient.wait_until_connected() never seems to resolve.
        if (
            o_guild is not None
            and ((o_vc and not o_vc.is_connected()) or o_vc is None)
            and o_guild.id in self.players
        ):
            log.info(
                "Disconnected from voice by Discord API in: %(guild)s/%(channel)s (Code: %(code)s) [S:%(state)s]",
                {
                    "guild": o_guild.name,
                    "channel": before.channel.name,
                    "code": close_code,
                    "state": state.name.upper() if state else None,
                },
            )
            await self.disconnect_voice_client(o_guild)

            # reconnect if the guild is configured to auto-join.
            if self.server_data[o_guild.id].auto_join_channel is not None:
                # Look for the last channel we were in.
                target_channel = self.get_channel(before.channel.id)
                if not target_channel:
                    # fall back to the configured channel.
                    target_channel = self.server_data[o_guild.id].auto_join_channel

                if not isinstance(
                    target_channel, (discord.VoiceChannel, discord.StageChannel)
                ):
                    log.error(
                        "Cannot use auto-join channel with type: %(type)s  in guild:  %(guild)s",
                        {"type": type(target_channel), "guild": before.channel.guild},
                    )
                    return True

                if not target_channel:
                    log.error(
                        "Cannot find the auto-joined channel, was it deleted?  Guild:  %s",
                        before.channel.guild,
                    )
                    return True

                log.info(
                    "Reconnecting to auto-joined guild on channel:  %s",
                    target_channel,
                )
                try:
                    r_player = await self.get_player(
                        target_channel, create=True, deserialize=True
                    )

                    if r_player.is_stopped:
                        r_player.play()

                except (TypeError, exceptions.PermissionsError):
                    log.warning(
                        "Cannot auto join channel:  %s",
                        before.channel,
                        exc_info=True,
                    )
            return True

        # TODO: If bot has left a server but still had a client, we should kill it.
        # if o_guild is None and before.channel.guild.id in self.players:

        return False

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """
        Event called by discord.py when the bot joins a new guild.
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_guild_join
        """
        log.info("Bot has been added to guild: %s", guild.name)

        # Leave guilds if the owner is not a member and configured to do so.
        if self.config.leavenonowners:
            # Get the owner so we can notify them of the leave via DM.
            owner = self._get_owner_member()
            if owner:
                # check for the owner in the guild.
                check = guild.get_member(owner.id)
                if check is None:
                    await guild.leave()
                    log.info(
                        "Left guild '%s' due to bot owner not found.",
                        guild.name,
                    )
                    await self.safe_send_message(
                        owner,
                        Response(
                            _D(
                                "Left `%(guild)s` due to bot owner not being found in it.",
                                None,
                            ),
                            fmt_args={"guild": guild.name},
                        ),
                    )

        log.debug("Creating data folder for guild %s", guild.id)
        self.config.data_path.joinpath(str(guild.id)).mkdir(exist_ok=True)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """
        Event called by discord.py when the bot is removed from a guild or a guild is deleted.
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_guild_remove
        """
        log.info("Bot has been removed from guild: %s", guild.name)
        log.debug("Updated guild list:")
        for s in self.guilds:
            log.debug(" - %s", s.name)

        if guild.id in self.players:
            self.players.pop(guild.id).kill()

    async def on_guild_available(self, guild: discord.Guild) -> None:
        """
        Event called by discord.py when a guild becomes available.
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_guild_available
        """
        if not self.init_ok:
            return  # Ignore pre-ready events

        log.info('Guild "%s" has become available.', guild.name)

        player = self.get_player_in(guild)

        if player and player.is_paused and player.guild_or_net_unavailable:
            log.debug(
                'Resuming player in "%s" due to availability.',
                guild.name,
            )
            player.guild_or_net_unavailable = False
            player.resume()

        if player:
            player.guild_or_net_unavailable = False

    async def on_guild_unavailable(self, guild: discord.Guild) -> None:
        """
        Event called by discord.py when Discord API says a guild is unavailable.
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_guild_unavailable
        """
        if not self.init_ok:
            return  # Ignore pre-ready events.

        log.info('Guild "%s" has become unavailable.', guild.name)

        player = self.get_player_in(guild)

        if player and player.is_playing:
            log.debug(
                'Pausing player in "%s" due to unavailability.',
                guild.name,
            )
            player.pause()

        if player:
            player.guild_or_net_unavailable = True

    async def on_guild_update(
        self, before: discord.Guild, after: discord.Guild
    ) -> None:
        """
        Event called by discord.py when guild properties are updated.
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_guild_update
        """
        if log.getEffectiveLevel() <= logging.EVERYTHING:  # type: ignore[attr-defined]
            log.info("Guild update for:  %s", before)
            for name in set(getattr(before, "__slotnames__")):
                a_val = getattr(after, name, None)
                b_val = getattr(before, name, None)
                if b_val != a_val:
                    log.everything(  # type: ignore[attr-defined]
                        "Guild attribute %(attr)s is now: %(new)s  -- Was: %(old)s",
                        {"attr": name, "new": a_val, "old": b_val},
                    )

    async def on_guild_channel_update(
        self, before: GuildMessageableChannels, after: GuildMessageableChannels
    ) -> None:
        """
        Event called by discord.py when a guild channel is updated.
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_guild_channel_update
        """
        # This allows us to log when certain channel properties are changed.
        # Mostly for information sake at current.
        changes = ""
        if before.name != after.name:
            changes += f" name = {after.name}"
        if isinstance(
            before, (discord.VoiceChannel, discord.StageChannel)
        ) and isinstance(after, (discord.VoiceChannel, discord.StageChannel)):
            # Splitting hairs, but we could pause playback here until voice update later.
            if before.rtc_region != after.rtc_region:
                changes += f" voice-region = {after.rtc_region}"
            if before.bitrate != after.bitrate:
                changes += f" bitrate = {after.bitrate}"

                # if we have a player playing we should update bitrate.
                player = self.get_player_in(after.guild)
                if player and player.is_playing and player.current_entry:
                    # Set current playback progress and restart playback.
                    entry = player.current_entry
                    if isinstance(entry, (URLPlaylistEntry, LocalFilePlaylistEntry)):
                        entry.set_start_time(player.progress)
                    player.playlist.insert_entry_at_index(0, entry)

                    # handle history playlist updates.
                    if (
                        self.config.enable_queue_history_global
                        or self.config.enable_queue_history_guilds
                    ):
                        self.server_data[after.guild.id].current_playing_url = ""

                    player.skip()

            if before.user_limit != after.user_limit:
                changes += f" user-limit = {after.user_limit}"
        # The chat delay is not currently respected by MusicBot. Is this a problem?
        if before.slowmode_delay != after.slowmode_delay:
            changes += f" slowmode = {after.slowmode_delay}"

        if changes:
            log.info(
                "Channel update for:  %(channel)s  --  %(changes)s",
                {"channel": before, "changes": changes},
            )
