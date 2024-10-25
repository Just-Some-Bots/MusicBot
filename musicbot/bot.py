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
from collections import defaultdict
from io import BytesIO, StringIO
from textwrap import dedent
from typing import TYPE_CHECKING, Any, DefaultDict, Dict, List, Optional, Set, Union

import aiohttp
import certifi  # type: ignore[import-untyped, unused-ignore]
import discord
import yt_dlp as youtube_dl  # type: ignore[import-untyped]

from . import downloader, exceptions
from .aliases import Aliases, AliasesDefault
from .autoplaylist import AutoPlaylistManager
from .config import Config, ConfigDefaults
from .constants import (
    DATA_FILE_SERVERS,
    DATA_GUILD_FILE_CUR_SONG,
    DATA_GUILD_FILE_QUEUE,
    DEFAULT_BOT_NAME,
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
    EMOJI_STOP_SIGN,
    FALLBACK_PING_SLEEP,
    FALLBACK_PING_TIMEOUT,
    MUSICBOT_USER_AGENT_AIOHTTP,
)
from .constants import VERSION as BOTVERSION
from .constants import VOICE_CLIENT_MAX_RETRY_CONNECT, VOICE_CLIENT_RECONNECT_TIMEOUT
from .constructs import GuildSpecificData, Response
from .entry import LocalFilePlaylistEntry, StreamPlaylistEntry, URLPlaylistEntry
from .filecache import AudioFileCache
from .json import Json
from .opus_loader import load_opus_lib
from .permissions import PermissionGroup, Permissions, PermissionsDefaults
from .player import MusicPlayer
from .playlist import Playlist
from .spotify import Spotify
from .utils import (
    _func_,
    count_members_in_voice,
    dev_only,
    format_size_from_bytes,
    format_song_duration,
    format_time_to_seconds,
    is_empty_voice_channel,
    muffle_discord_console_log,
    mute_discord_console_log,
    owner_only,
    slugify,
)

# optional imports
try:
    import objgraph  # type: ignore[import-untyped]
except ImportError:
    objgraph = None


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
CommandResponse = Union[Response, None]


log = logging.getLogger(__name__)


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

        self.config = Config(self._config_file)

        self.permissions = Permissions(self._perms_file)
        # Set the owner ID in case it wasn't auto...
        self.permissions.set_owner_id(self.config.owner_id)
        self.str = Json(self.config.i18n_file)

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
        else:  # assume 3.8 +
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
                        "Unhandled exception for task:  %r  --  %s",
                        task,
                        str(ex),
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
                    e,
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
                    "Could not start Spotify client using guest mode. Details: %s.", e
                )
                self.config.spotify_enabled = False

        # trigger yt tv oauth2 authorization.
        if self.config.ytdlp_use_oauth2 and self.config.ytdlp_oauth2_url:
            log.warning(
                "Experimental Yt-dlp OAuth2 plugin is enabled. This might break at any point!"
            )
            # could probably do this with items from an auto-playlist but meh.
            await self.downloader.extract_info(
                self.config.ytdlp_oauth2_url, download=False, process=True
            )

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
                log.info("Resuming playback of player:  (%s) %s", gid, repr(player))
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
                    "Pausing MusicPlayer due to network availability:  (%s) %s",
                    gid,
                    repr(player),
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
            "Looking for owner (in guild: %s) (required voice: %s) and got:  %s",
            server,
            voice,
            owner,
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
                    "Guild not available, cannot auto join:  %s/%s",
                    guild.id,
                    guild.name,
                )
                continue

            # Check for a resumable channel.
            if guild.me.voice and guild.me.voice.channel:
                log.info(
                    "Found resumable voice channel:  %s  in guild:  %s",
                    guild.me.voice.channel.name,
                    guild.name,
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
                    "Already connected to channel:  %s  in guild:  %s",
                    guild.voice_client.channel.name,
                    guild.name,
                )
                continue

            if channel and isinstance(
                channel, (discord.VoiceChannel, discord.StageChannel)
            ):
                log.info(
                    "Attempting to join channel:  %s/%s  in guild:  %s",
                    channel.guild.name,
                    channel.name,
                    channel.guild,
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
                    "Not joining %s/%s, it isn't a supported voice channel.",
                    channel.guild.name,
                    channel.name,
                )
        log.info("Finished joining configured channels.")

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
                "Cancelled delete for message (ID: %s):  %s",
                message.id,
                message.content,
            )
            return

        if not self.is_closed():

            await self.safe_delete_message(message, quiet=True)

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
                expire_in=30,
            )

        # If we've connected to a voice chat and we're in the same voice channel
        if not vc or (msg.author.voice and vc == msg.author.voice.channel):
            return True

        raise exceptions.PermissionsError(
            f"you cannot use this command when not in the voice channel ({vc.name})",
            expire_in=30,
        )

    async def generate_invite_link(
        self,
        *,
        permissions: discord.Permissions = discord.Permissions(70380544),
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
            raise TypeError("Channel passed must be a voice channel")

        # Check if MusicBot has required permissions to join in channel.
        chperms = channel.permissions_for(channel.guild.me)
        if not chperms.connect:
            log.error(
                "MusicBot does not have permission to Connect in channel:  %s",
                channel.name,
            )
            raise exceptions.PermissionsError(
                f"MusicBot does not have permission to Connect in channel:  `{channel.name}`",
                expire_in=30,
            )
        if not chperms.speak:
            log.error(
                "MusicBot does not have permission to Speak in channel:  %s",
                channel.name,
            )
            raise exceptions.PermissionsError(
                f"MusicBot does not have permission to Speak in channel:  `{channel.name}`",
                expire_in=30,
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
                    "MusicBot is unable to connect to the channel right now:  %s",
                    channel,
                )
                raise exceptions.CommandError(
                    "MusicBot could not connect to the channel. Try again later, or restart the bot if this continues."
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
                    "Retrying connection after a timeout error (%s) while trying to connect to:  %s",
                    attempt,
                    channel,
                )
            except asyncio.exceptions.CancelledError as e:
                log.exception(
                    "MusicBot VoiceClient connection attempt was cancelled. No retry."
                )
                raise exceptions.CommandError(
                    "MusicBot connection to voice was cancelled. This is odd. Maybe restart?"
                ) from e

        # Moving the bot does not grant it permissions to speak automatically,
        # however stage mods can invite it to speak
        if isinstance(channel, discord.StageChannel):
            await self._handle_stage_channels(channel)

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
                "We still have a MusicPlayer ref in guild (%s):  %s",
                gid,
                repr(player),
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
                "Guild (%s) wants a player, optional:  %s", guild, repr(p)
            )

        if log.getEffectiveLevel() <= logging.VOICEDEBUG:  # type: ignore[attr-defined]
            if p and not p.voice_client:
                log.error(
                    "[BUG] MusicPlayer is missing a VoiceClient some how.  You should probably restart the bot."
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
        *,
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
            "Getting a MusicPlayer for guild:  %s  In Channel:  %s  Will Create:  %s  Deserialize:  %s",
            guild,
            channel,
            create,
            deserialize,
        )

        async with self.aiolocks[_func_() + ":" + str(guild.id)]:
            if deserialize:
                voice_client = await self.get_voice_client(channel)
                player = await self.deserialize_queue(guild, voice_client)

                if player:
                    log.voicedebug(  # type: ignore[attr-defined]
                        "Created player via deserialization for guild %s with %s entries",
                        guild.id,
                        len(player.playlist),
                    )
                    # Since deserializing only happens when the bot starts, I should never need to reconnect
                    return self._init_player(player, guild=guild)

            if guild.id not in self.players:
                if not create:
                    prefix = self.server_data[channel.guild.id].command_prefix
                    raise exceptions.CommandError(
                        "The bot is not in a voice channel.  "
                        f"Use {prefix}summon to summon it to your voice channel."
                    )

                voice_client = await self.get_voice_client(channel)

                if isinstance(voice_client, discord.VoiceClient):
                    playlist = Playlist(self)
                    player = MusicPlayer(self, voice_client, playlist)
                    self._init_player(player, guild=guild)
                else:
                    raise RuntimeError(
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
                newmsg = self.str.get(
                    "on_player_play-onChannel_authorNotInChannel_skipWhenAbsent",
                    "Skipping next song in {channel}: {title} added by {author} as queuer not in voice!",
                ).format(
                    channel=player.voice_client.channel.name,
                    title=entry.title,
                    author=entry.author.name,
                )

                # handle history playlist updates.
                guild = player.voice_client.guild
                if (
                    self.config.enable_queue_history_global
                    or self.config.enable_queue_history_guilds
                ):
                    self.server_data[guild.id].current_playing_url = ""

                player.skip()
            elif self.config.now_playing_mentions:
                newmsg = self.str.get(
                    "on_player_play-onChannel_playingMention",
                    "{author} - your song {title} is now playing in {channel}!",
                ).format(
                    author=entry.author.mention,
                    title=entry.title,
                    channel=player.voice_client.channel.name,
                )
            else:
                newmsg = self.str.get(
                    "on_player_play-onChannel",
                    "Now playing in {channel}: {title} added by {author}!",
                ).format(
                    channel=player.voice_client.channel.name,
                    title=entry.title,
                    author=entry.author.name,
                )

        else:
            # no author (and channel), it's an auto playlist entry.
            newmsg = self.str.get(
                "on_player_play-onChannel_noAuthor_autoplaylist",
                "Now playing automatically added entry {title} in {channel}!",
            ).format(title=entry.title, channel=player.voice_client.channel.name)

        # handle history playlist updates.
        guild = player.voice_client.guild
        if (
            self.config.enable_queue_history_global
            or self.config.enable_queue_history_guilds
        ) and not entry.from_auto_playlist:
            log.debug("Setting URL history guild %s == %s", guild.id, entry.url)
            self.server_data[guild.id].current_playing_url = entry.url

        last_np_msg = self.server_data[guild.id].last_np_msg
        np_channel: Optional[MessageableChannel] = None
        if newmsg:
            if self.config.dm_nowplaying and entry.author:
                await self.safe_send_message(entry.author, newmsg)
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

        content = self._gen_embed()
        if self.config.embeds:
            if entry.thumbnail_url:
                content.set_image(url=entry.thumbnail_url)
            else:
                log.warning(
                    "No thumbnail set for entry with url: %s",
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
            content if self.config.embeds else newmsg,
            expire_in=30 if self.config.delete_nowplaying else 0,
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
                    await self.safe_send_message(
                        channel,
                        # TODO: i18n UI stuff.
                        f"Skipping songs added by {author.name} as they are not in voice!",
                        expire_in=60,
                    )
                    notice_sent = True
                deleted_entry = player.playlist.delete_entry_at_index(0)
                log.noise(  # type: ignore[attr-defined]
                    "Author `%s` absent, skipped (deleted) entry from queue:  %s",
                    author.name,
                    deleted_entry.title,
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

                except youtube_dl.utils.DownloadError as e:
                    log.error(
                        'Error while processing song "%s":  %s',
                        song_url,
                        e,
                    )

                    await self.server_data[guild.id].autoplaylist.remove_track(
                        song_url, ex=e, delete_from_ap=self.config.remove_ap
                    )
                    continue

                except (
                    exceptions.ExtractionError,
                    youtube_dl.utils.YoutubeDLError,
                ) as e:
                    log.error(
                        'Error extracting song "%s": %s',
                        song_url,
                        e,
                        exc_info=True,
                    )

                    await self.server_data[guild.id].autoplaylist.remove_track(
                        song_url, ex=e, delete_from_ap=self.config.remove_ap
                    )
                    continue

                except exceptions.MusicbotException:
                    log.exception(
                        "MusicBot needs to stop the autoplaylist extraction and bail."
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
                    exceptions.ExtractionError,
                    exceptions.WrongEntryTypeError,
                ) as e:
                    log.error(
                        "Error adding song from autoplaylist: %s",
                        str(e),
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
            song = entry.title or entry.url
            await self.safe_send_message(
                entry.channel,
                # TODO: i18n / UI stuff
                f"Playback failed for song: `{song}` due to error:\n```\n{ex}\n```",
                expire_in=90,
            )

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
                    f"Update Bot Status:  {status} -- {repr(activity)}"
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
        content: Union[str, discord.Embed],
        **kwargs: Any,
    ) -> Optional[discord.Message]:
        """
        Safely send a message with given `content` to the message-able
        object in `dest`
        This method should handle all raised exceptions so callers will
        not need to handle them locally.

        :param: tts:  set the Text-to-Speech flag on the message.
        :param: quiet:  Toggle using log.debug or log.warning.
        :param: expire_in:  time in seconds to wait before auto deleting this message
        :param: allow_none:  Allow sending a message with empty `content`
        :param: also_delete:  Optional discord.Message to delete when `expire_in` is set.

        :returns:  May return a discord.Message object if a message was sent.
        """
        tts = kwargs.pop("tts", False)
        quiet = kwargs.pop("quiet", False)
        expire_in = int(kwargs.pop("expire_in", 0))
        allow_none = kwargs.pop("allow_none", True)
        also_delete = kwargs.pop("also_delete", None)
        fallback_channel = kwargs.pop("fallback_channel", None)

        msg = None
        retry_after = 0.0
        lfunc = log.debug if quiet else log.warning
        if log.getEffectiveLevel() <= logging.NOISY:  # type: ignore[attr-defined]
            lfunc = log.exception

        ch_name = "DM-Channel"
        if hasattr(dest, "name"):
            ch_name = str(dest.name)

        try:
            if content is not None or allow_none:
                if isinstance(content, discord.Embed):
                    msg = await dest.send(embed=content)
                else:
                    msg = await dest.send(content, tts=tts)

        except discord.Forbidden:
            lfunc('Cannot send message to "%s", no permission', ch_name)

        except discord.NotFound:
            lfunc('Cannot send message to "%s", invalid channel?', ch_name)

        except discord.HTTPException as e:
            if len(content) > DISCORD_MSG_CHAR_LIMIT:
                lfunc(
                    "Message is over the message size limit (%s)",
                    DISCORD_MSG_CHAR_LIMIT,
                )

            # if `dest` is a user with strict privacy or a bot, direct message can fail.
            elif e.code == 50007 and fallback_channel:
                log.debug("DM failed, sending in fallback channel instead.")
                await self.safe_send_message(fallback_channel, content, **kwargs)

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
                    return await self.safe_send_message(dest, content, **kwargs)

                log.error("Rate limited send message, but cannot retry!")

            else:
                lfunc("Failed to send message")
                log.noise(  # type: ignore[attr-defined]
                    "Got HTTPException trying to send message to %s: %s", dest, content
                )

        except aiohttp.client_exceptions.ClientError:
            lfunc("Failed to send due to an HTTP error.")

        finally:
            if not retry_after and self.config.delete_messages:
                if msg and expire_in:
                    self.create_task(self._wait_delete_msg(msg, expire_in))

            if not retry_after and self.config.delete_invoking:
                if also_delete and isinstance(also_delete, discord.Message):
                    self.create_task(self._wait_delete_msg(also_delete, expire_in))

        return msg

    async def safe_delete_message(
        self, message: discord.Message, *, quiet: bool = False
    ) -> None:
        """
        Safely delete the given `message` from discord.
        This method should handle all raised exceptions so callers will
        not need to handle them locally.

        :param: quiet:  Toggle using log.debug or log.warning
        """
        # TODO: this could use a queue and some other handling.
        lfunc = log.debug if quiet else log.warning

        try:
            await message.delete()

        except discord.Forbidden:
            lfunc('Cannot delete message "%s", no permission', message.clean_content)

        except discord.NotFound:
            lfunc(
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
                lfunc("Failed to delete message")
                log.noise(  # type: ignore[attr-defined]
                    "Got HTTPException trying to delete message: %s", message
                )

        except aiohttp.client_exceptions.ClientError:
            lfunc("Failed to send due to an HTTP error.")

        return None

    async def safe_edit_message(
        self,
        message: discord.Message,
        new: Union[str, discord.Embed],
        *,
        send_if_fail: bool = False,
        quiet: bool = False,
    ) -> Optional[discord.Message]:
        """
        Safely update the given `message` with the `new` content.
        This function should handle all raised exceptions so callers
        will not need to handle them locally.

        :param: send_if_fail:  Toggle sending a new message if edit fails.
        :param: quiet:  Use log.debug if quiet otherwise use log.warning

        :returns:  May return a discord.Message object if edit/send did not fail.
        """
        lfunc = log.debug if quiet else log.warning

        try:
            if isinstance(new, discord.Embed):
                return await message.edit(embed=new)

            return await message.edit(content=new)

        except discord.NotFound:
            lfunc(
                'Cannot edit message "%s", message not found',
                message.clean_content,
            )
            if send_if_fail:
                lfunc("Sending message instead")
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
                        message, new, send_if_fail=send_if_fail, quiet=quiet
                    )
            else:
                lfunc("Failed to edit message")
                log.noise(  # type: ignore[attr-defined]
                    "Got HTTPException trying to edit message %s to: %s", message, new
                )

        except aiohttp.client_exceptions.ClientError:
            lfunc("Failed to send due to an HTTP error.")

        return None

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
            await self.start(*self.config.auth)
            log.info("MusicBot is now doing shutdown steps...")
            if self.exit_signal is None:
                self.exit_signal = exceptions.TerminateSignal()

        except discord.errors.LoginFailure as e:
            raise exceptions.HelpfulError(
                preface="Failed login to discord API!",
                issue="MusicBot cannot login to discord, is your token correct?",
                solution="Fix your token in the options.ini config file.\n"
                "Remember that each field should be on their own line.",
                footnote="Note: If you are certain your token is correct, this may be due to a Discord API outage.",
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
                    log.debug("Will wait for task:  %s  (%s)", tname, coro_name)
                    pending_tasks.append(task)

                else:
                    log.debug("Will try to cancel task:  %s  (%s)", tname, coro_name)
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
            log.error("Exception in %s:\n%s", event, ex.message)

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
            "MusicBot:  %s/%s#%s",
            self.user.id,
            self.user.name,
            self.user.discriminator,
        )

        owner = self._get_owner_member()
        if owner and self.guilds:
            log.info(
                "Owner:     %s/%s#%s\n",
                owner.id,
                owner.name,
                owner.discriminator,
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
                        "Cannot bind to non-messagable channel with ID:  %d",
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
                    guild_name = "PrivateChannel"
                    if isinstance(valid_ch, discord.DMChannel):
                        ch_name = "Unknown User DM"
                        if valid_ch.recipient:
                            ch_name = f"DM: {valid_ch.recipient.name}"
                    elif isinstance(valid_ch, discord.PartialMessageable):
                        ch_name = "Unknown Partial Channel"
                    else:
                        ch_name = valid_ch.name or f"Unnamed Channel: {valid_ch.id}"
                    if valid_ch.guild:
                        guild_name = valid_ch.guild.name
                    log.info(" - %s/%s", guild_name, ch_name)
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
                    log.warning("Got None for autojoin channel with ID:  %d", ch_id)
                    invalids.add(ch_id)
                    continue

                if isinstance(ch, discord.abc.PrivateChannel):
                    log.warning(
                        "Cannot autojoin a Private/Non-Guild channel with ID:  %d",
                        ch_id,
                    )
                    invalids.add(ch_id)
                    continue

                if not isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
                    log.warning(
                        "Cannot autojoin to non-connectable channel with ID:  %d",
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
                log.info("Autojoining voice channels:")
                for ch in vc_chlist:
                    log.info(" - %s/%s", ch.guild.name.strip(), ch.name.strip())

            else:
                log.info("Not autojoining any voice channels")

        else:
            log.info("Not autojoining any voice channels")

        # Display and log the config settings.
        if self.config.show_config_at_start:
            self._on_ready_log_configs()

        # we do this after the config stuff because it's a lot easier to notice here
        if self.config.register.ini_missing_options:
            missing_list = "\n".join(
                sorted(str(o) for o in self.config.register.ini_missing_options)
            )
            conf_warn = exceptions.HelpfulError(
                preface="Detected missing config options!",
                issue=(
                    "Your config file is missing some options. Defaults will be used for this session.\n"
                    f"Here is a list of options we think are missing:\n{missing_list}"
                ),
                solution="Check the example_options.ini file for newly added options and copy them to your config.",
                footnote="You can also use the `config` command to set the missing options.",
            )
            log.warning(str(conf_warn)[1:])

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

        print(flush=True)
        log.info("Options:")

        log.info("  Command prefix: %s", self.config.command_prefix)
        log.info("  Default volume: %d%%", int(self.config.default_volume * 100))
        log.info(
            "  Skip threshold: %d votes or %.0f%%",
            self.config.skips_required,
            (self.config.skip_ratio_required * 100),
        )
        log.info(
            "  Now Playing @mentions: %s",
            ["Disabled", "Enabled"][self.config.now_playing_mentions],
        )
        log.info("  Auto-Summon: %s", ["Disabled", "Enabled"][self.config.auto_summon])
        log.info(
            "  Auto-Playlist: %s (order: %s)",
            ["Disabled", "Enabled"][self.config.auto_playlist],
            ["sequential", "random"][self.config.auto_playlist_random],
        )
        log.info("  Auto-Pause: %s", ["Disabled", "Enabled"][self.config.auto_pause])
        log.info(
            "  Delete Messages: %s",
            ["Disabled", "Enabled"][self.config.delete_messages],
        )
        if self.config.delete_messages:
            log.info(
                "    Delete Invoking: %s",
                ["Disabled", "Enabled"][self.config.delete_invoking],
            )
            log.info(
                "    Delete Nowplaying: %s",
                ["Disabled", "Enabled"][self.config.delete_nowplaying],
            )
        log.info("  Debug Mode: %s", ["Disabled", "Enabled"][self.config.debug_mode])
        log.info(
            "  Downloaded songs will be %s",
            ["deleted", "saved"][self.config.save_videos],
        )
        if self.config.save_videos and self.config.storage_limit_days:
            log.info("    Delete if unused for %d days", self.config.storage_limit_days)
        if self.config.save_videos and self.config.storage_limit_bytes:
            size = format_size_from_bytes(self.config.storage_limit_bytes)
            log.info("    Delete if size exceeds %s", size)

        if self.config.status_message:
            log.info("  Status message: %s", self.config.status_message)
        log.info(
            "  Write current songs to file: %s",
            ["Disabled", "Enabled"][self.config.write_current_song],
        )
        log.info(
            "  Author insta-skip: %s",
            ["Disabled", "Enabled"][self.config.allow_author_skip],
        )
        log.info("  Embeds: %s", ["Disabled", "Enabled"][self.config.embeds])
        log.info(
            "  Spotify integration: %s",
            ["Disabled", "Enabled"][self.config.spotify_enabled],
        )
        log.info("  Legacy skip: %s", ["Disabled", "Enabled"][self.config.legacy_skip])
        log.info(
            "  Leave non owners: %s",
            ["Disabled", "Enabled"][self.config.leavenonowners],
        )
        log.info(
            "  Leave inactive VC: %s",
            ["Disabled", "Enabled"][self.config.leave_inactive_channel],
        )
        if self.config.leave_inactive_channel:
            log.info(
                "    Timeout: %s seconds",
                self.config.leave_inactive_channel_timeout,
            )
        log.info(
            "  Leave at song end/empty queue: %s",
            ["Disabled", "Enabled"][self.config.leave_after_queue_empty],
        )
        log.info(
            "  Leave when player idles: %s",
            "Disabled" if self.config.leave_player_inactive_for == 0 else "Enabled",
        )
        if self.config.leave_player_inactive_for:
            log.info("    Timeout: %d seconds", self.config.leave_player_inactive_for)
        log.info("  Self Deafen: %s", ["Disabled", "Enabled"][self.config.self_deafen])
        log.info(
            "  Per-server command prefix: %s",
            ["Disabled", "Enabled"][self.config.enable_options_per_guild],
        )
        log.info("  Search List: %s", ["Disabled", "Enabled"][self.config.searchlist])
        log.info(
            "  Round Robin Queue: %s",
            ["Disabled", "Enabled"][self.config.round_robin_queue],
        )
        print(flush=True)

    def _gen_embed(self) -> discord.Embed:
        """Provides a basic template for embeds"""
        e = discord.Embed()
        e.colour = discord.Colour(7506394)
        e.set_footer(
            text=self.config.footer_text, icon_url="https://i.imgur.com/gFHBoZA.png"
        )

        # TODO: handle this part when EmbedResponse get handled.
        author_name = "MusicBot"
        avatar_url = None
        if self.user:
            author_name = self.user.name
            if self.user.avatar:
                avatar_url = self.user.avatar.url

        e.set_author(
            name=author_name,
            url="https://github.com/Just-Some-Bots/MusicBot",
            icon_url=avatar_url,
        )
        return e

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
                # TODO: i18n
                f"The requested song `{song_subject}` is blocked by the song blocklist.",
                expire_in=30,
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
            chname = "Unknown"
            if hasattr(guild.voice_client.channel, "name"):
                chname = guild.voice_client.channel.name

            log.info(
                "Channel activity waiting %d seconds to leave channel: %s",
                self.config.leave_inactive_channel_timeout,
                chname,
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
                "Channel activity timer canceled for: %s in %s",
                getattr(guild.voice_client.channel, "name", guild.voice_client.channel),
                guild.name,
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
                "Player activity timer waiting %d seconds to leave channel: %s",
                self.config.leave_player_inactive_for,
                channel.name,
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
                    "Player activity timer canceled for: %s in %s",
                    channel.name,
                    guild.name,
                )
        else:
            log.info(
                "Player activity timer canceled for: %s in %s",
                channel.name,
                guild.name,
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

    async def cmd_resetplaylist(
        self, guild: discord.Guild, player: MusicPlayer
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}resetplaylist

        Resets all songs in the server's autoplaylist
        """
        player.autoplaylist = list(self.server_data[guild.id].autoplaylist)
        return Response(
            self.str.get("cmd-resetplaylist-response", "\N{OK HAND SIGN}"),
            delete_after=15,
        )

    async def cmd_help(
        self,
        message: discord.Message,
        guild: discord.Guild,
        command: Optional[str] = None,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}help [command]

        Prints a help message.
        If a command is specified, it prints a help message for that command.
        Otherwise, it lists the available commands.
        """
        commands = []
        is_all = False
        is_emoji = False
        prefix = self.server_data[guild.id].command_prefix
        # Its OK to skip unicode emoji here, they render correctly inside of code boxes.
        emoji_regex = re.compile(r"^(<a?:.+:\d+>|:.+:)$")
        if emoji_regex.match(prefix):
            is_emoji = True

        if command:
            if command.lower() == "all":
                is_all = True
                commands = await self.gen_cmd_list(message, list_all_cmds=True)

            else:
                cmd = getattr(self, "cmd_" + command, None)
                if cmd and not hasattr(cmd, "dev_cmd"):
                    return Response(
                        "```\n{0}```{1}".format(
                            dedent(cmd.__doc__),
                            (
                                self.str.get(
                                    "cmd-help-prefix-required",
                                    "\n**Prefix required for use:**\n{example_cmd}\n",
                                ).format(example_cmd=f"{prefix}`{command} ...`")
                                if is_emoji
                                else ""
                            ),
                        ).format(
                            command_prefix=prefix if not is_emoji else "",
                        ),
                        delete_after=60,
                    )

                raise exceptions.CommandError(
                    self.str.get("cmd-help-invalid", "No such command"),
                    expire_in=10,
                )

        elif message.author.id == self.config.owner_id:
            commands = await self.gen_cmd_list(message, list_all_cmds=True)

        else:
            commands = await self.gen_cmd_list(message)

        if is_emoji:
            desc = (
                f"\n{prefix}`"
                + f"`, {prefix}`".join(commands)
                + "`\n\n"
                + self.str.get(
                    "cmd-help-response",
                    "For information about a particular command, run {example_cmd}\n"
                    "For further help, see https://just-some-bots.github.io/MusicBot/",
                ).format(
                    example_cmd=(
                        f"{prefix}`help [command]`"
                        if is_emoji
                        else f"`{prefix}help [command]`"
                    ),
                )
            )
        else:
            desc = (
                f"```\n{prefix}"
                + f", {prefix}".join(commands)
                + "\n```\n"
                + self.str.get(
                    "cmd-help-response",
                    "For information about a particular command, run {example_cmd}\n"
                    "For further help, see https://just-some-bots.github.io/MusicBot/",
                ).format(
                    example_cmd=(
                        f"{prefix}`help [command]`"
                        if is_emoji
                        else f"`{prefix}help [command]`"
                    ),
                )
            )
        if not is_all:
            desc += self.str.get(
                "cmd-help-all",
                "\nOnly showing commands you can use, for a list of all commands, run {example_cmd}",
            ).format(
                example_cmd=(
                    f"{prefix}`help all`" if is_emoji else f"`{prefix}help all`"
                ),
            )

        return Response(desc, reply=True, delete_after=60)

    async def cmd_blockuser(
        self,
        user_mentions: UserMentions,
        option: str,
        leftover_args: List[str],
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}blockuser [ + | - | ? | add | remove | status ] @UserName [@UserName2 ...]

        Manage users in the block list.
        Blocked users are forbidden from using all bot commands.
        """

        if not user_mentions and not leftover_args:
            raise exceptions.CommandError(
                "You must mention a user or provide their ID number.",
                expire_in=20,
            )

        if option not in ["+", "-", "?", "add", "remove", "status"]:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-blacklist-invalid",
                    'Invalid option "{0}" specified, use +, -, add, or remove',
                ).format(option),
                expire_in=20,
            )

        for p_user in leftover_args:
            if p_user.isdigit():
                u = self.get_user(int(p_user))
                if u:
                    user_mentions.append(u)

        if not user_mentions:
            raise exceptions.CommandError(
                "MusicBot could not find the user(s) you specified.",
                expire_in=20,
            )

        for user in user_mentions.copy():
            if option in ["+", "add"] and self.config.user_blocklist.is_blocked(user):
                if user.id == self.config.owner_id:
                    raise exceptions.CommandError(
                        "The owner cannot be added to the block list."
                    )

                log.info(
                    "Not adding user to block list, already blocked:  %s/%s",
                    user.id,
                    user.name,
                )
                user_mentions.remove(user)

            if option in ["-", "remove"] and not self.config.user_blocklist.is_blocked(
                user
            ):
                log.info(
                    "Not removing user from blocklist, not listed:  %s/%s",
                    user.id,
                    user.name,
                )
                user_mentions.remove(user)

        # allow management regardless, but tell the user if it will apply.
        if self.config.user_blocklist_enabled:
            status_msg = "User block list is currently enabled."
        else:
            status_msg = "User block list is currently disabled."

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
                f"{n_users} user(s) have been added to the block list.\n{status_msg}",
                reply=True,
                delete_after=10,
            )

        if self.config.user_blocklist.is_disjoint(user_mentions):
            return Response(
                self.str.get(
                    "cmd-blacklist-none",
                    "None of those users are in the blacklist.",
                ),
                reply=True,
                delete_after=10,
            )

        if option in ["?", "status"]:
            ustatus = ""
            for user in user_mentions:
                blocked = "not blocked"
                if self.config.user_blocklist.is_blocked(user):
                    blocked = "blocked"
                ustatus += f"User: `{user.name}` is {blocked}\n"
            return Response(
                f"**Block list status:**\n{ustatus}\n{status_msg}",
                delete_after=30,
            )

        async with self.aiolocks["user_blocklist"]:
            self.config.user_blocklist.remove_items(user_ids)

        n_users = old_len - len(self.config.user_blocklist)
        return Response(
            f"{n_users} user(s) have been removed from the block list.\n{status_msg}",
            reply=True,
            delete_after=10,
        )

    async def cmd_blocksong(
        self,
        guild: discord.Guild,
        _player: Optional[MusicPlayer],
        option: str,
        leftover_args: List[str],
        song_subject: str = "",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}blocksong [ + | - | add | remove ] [subject]

        Manage a block list applied to song requests and extracted info.
        A `subject` may be a song URL or a word or phrase found in the track title.
        If `subject` is omitted, a currently playing track will be used instead.

        Song block list matches loosely, but is case sensitive.
        So adding "Pie" will match "cherry Pie" but not "cherry pie" in checks.
        """
        if leftover_args:
            song_subject = " ".join([song_subject, *leftover_args])

        if not song_subject:
            valid_url = self._get_song_url_or_none(song_subject, _player)
            if not valid_url:
                raise exceptions.CommandError(
                    "You must provide a song subject if no song is currently playing.",
                    expire_in=30,
                )
            song_subject = valid_url

        if option not in ["+", "-", "add", "remove"]:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-blacklist-invalid",
                    'Invalid option "{0}" specified, use +, -, add, or remove',
                ).format(option),
                expire_in=20,
            )

        # allow management regardless, but tell the user if it will apply.
        if self.config.song_blocklist_enabled:
            status_msg = "Song block list is currently enabled."
        else:
            status_msg = "Song block list is currently disabled."

        if option in ["+", "add"]:
            if self.config.song_blocklist.is_blocked(song_subject):
                raise exceptions.CommandError(
                    f"Subject `{song_subject}` is already in the song block list.\n{status_msg}"
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

            # TODO: i18n/UI stuff.
            return Response(
                f"Added subject `{song_subject}` to the song block list.\n{status_msg}",
                reply=True,
                delete_after=10,
            )

        # handle "remove" and "-"
        if not self.config.song_blocklist.is_blocked(song_subject):
            raise exceptions.CommandError(
                "The subject is not in the song block list and cannot be removed.",
                expire_in=10,
            )

        async with self.aiolocks["song_blocklist"]:
            self.config.song_blocklist.remove_items([song_subject])

        return Response(
            f"Subject `{song_subject}` has been removed from the block list.\n{status_msg}",
            reply=True,
            delete_after=10,
        )

    async def cmd_id(
        self, author: discord.Member, user_mentions: UserMentions
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}id [@user]

        Tells the user their id or the id of another user.
        """
        if not user_mentions:
            return Response(
                self.str.get("cmd-id-self", "Your ID is `{0}`").format(author.id),
                reply=True,
                delete_after=35,
            )

        usr = user_mentions[0]
        return Response(
            self.str.get("cmd-id-other", "**{0}**s ID is `{1}`").format(
                usr.name, usr.id
            ),
            reply=True,
            delete_after=35,
        )

    async def cmd_autoplaylist(
        self,
        guild: discord.Guild,
        author: discord.Member,
        _player: Optional[MusicPlayer],
        player: MusicPlayer,
        option: str,
        opt_url: str = "",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}autoplaylist [+ | - | add | remove] [url]
                Adds or removes the specified song or currently playing song to/from the current playlist.

            {command_prefix}autoplaylist [+ all | add all]
                Adds the entire queue to the guilds playlist.

            {command_prefix}autoplaylist show
                Show a list of existing playlist files.

            {command_prefix}autoplaylist set [playlist.txt]
                Set a playlist as default for this guild and reloads the guild auto playlist.
        """
        option = option.lower()
        if option not in ["+", "-", "add", "remove", "show", "set"]:
            raise exceptions.CommandError(
                "You must provide one of the following options:  `add`, `remove`, `show`, or `set`",
                expire_in=30,
            )

        def _get_url() -> str:
            url = self._get_song_url_or_none(opt_url, _player)

            if not url:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-autoplaylist-invalid", "The supplied song link is invalid"
                    ),
                    expire_in=20,
                )
            return url

        if option in ["+", "add"] and opt_url.lower() == "all":
            if not player.playlist.entries:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-autoplaylist-add-all-empty-queue",
                        "The queue is empty. Add some songs with `{0}play`!",
                    ).format(self.server_data[guild.id].command_prefix),
                    expire_in=30,
                )

            added_songs = set()
            for e in player.playlist.entries:
                if e.url not in self.server_data[guild.id].autoplaylist:
                    await self.server_data[guild.id].autoplaylist.add_track(e.url)
                    added_songs.add(e.url)

            if not added_songs:
                return Response(
                    self.str.get(
                        "cmd-save-all-exist",
                        "All songs in the queue are already in the autoplaylist.",
                    ),
                    delete_after=20,
                )

            return Response(
                self.str.get(
                    "cmd-save-success-multiple",
                    "Added {0} songs to the autoplaylist.",
                ).format(len(added_songs)),
                delete_after=30,
            )

        if option in ["+", "add"]:
            url = _get_url()
            self._do_song_blocklist_check(url)
            if url not in self.server_data[guild.id].autoplaylist:
                await self.server_data[guild.id].autoplaylist.add_track(url)
                return Response(
                    self.str.get(
                        "cmd-save-success", "Added <{0}> to the autoplaylist."
                    ).format(url),
                    delete_after=35,
                )
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-save-exists",
                    "This song is already in the autoplaylist.",
                ),
                expire_in=20,
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
                    self.str.get(
                        "cmd-unsave-success", "Removed <{0}> from the autoplaylist."
                    ).format(url),
                    delete_after=35,
                )
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-unsave-does-not-exist",
                    "This song is not yet in the autoplaylist.",
                ),
                expire_in=20,
            )

        if option == "show":
            self.playlist_mgr.discover_playlists()
            names = "\n".join([f"`{pl}`" for pl in self.playlist_mgr.playlist_names])
            return Response(
                f"**Available Playlists:**\n{names}",
                delete_after=40,
            )

        if option == "set":
            if not opt_url:
                raise exceptions.CommandError(
                    "You must provide a playlist filename.",
                    expire_in=30,
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
                new_msg = (
                    "\nThis playlist is new, you must add songs to save it to disk!"
                )
            return Response(
                f"The playlist for this server has been updated to: `{opt_url}`{new_msg}",
                delete_after=30,
            )

        raise exceptions.CommandError(
            self.str.get(
                "cmd-autoplaylist-option-invalid",
                'Invalid option "{0}" specified, use +, -, add, or remove',
            ).format(option),
            expire_in=20,
        )

    @owner_only
    async def cmd_joinserver(self) -> CommandResponse:
        """
        Usage:
            {command_prefix}joinserver

        Generate an invite link that can be used to add this bot to another server.
        """
        url = await self.generate_invite_link()
        return Response(
            self.str.get(
                "cmd-joinserver-response",
                "Click here to add me to another server: \n{}",
            ).format(url),
            reply=True,
            delete_after=30,
        )

    async def cmd_karaoke(self, player: MusicPlayer) -> CommandResponse:
        """
        Usage:
            {command_prefix}karaoke

        Activates karaoke mode. During karaoke mode, only groups with the BypassKaraokeMode
        permission in the config file can queue music.
        """
        player.karaoke_mode = not player.karaoke_mode
        return Response(
            "\N{OK HAND SIGN} Karaoke mode is now "
            + ["disabled", "enabled"][player.karaoke_mode],
            delete_after=15,
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
                self.str.get(
                    "playlists-noperms", "You are not allowed to request playlists"
                ),
                expire_in=30,
            )

        if (
            permissions.max_playlist_length
            and num_songs > permissions.max_playlist_length
        ):
            raise exceptions.PermissionsError(
                self.str.get(
                    "playlists-big", "Playlist has too many entries ({0} > {1})"
                ).format(num_songs, permissions.max_playlist_length),
                expire_in=30,
            )

        # This is a little bit weird when it says (x + 0 > y), I might add the other check back in
        if (
            permissions.max_songs
            and player.playlist.count_for_user(author) + num_songs
            > permissions.max_songs
        ):
            raise exceptions.PermissionsError(
                self.str.get(
                    "playlists-limit",
                    "Playlist entries + your already queued songs reached limit ({0} + {1} > {2})",
                ).format(
                    num_songs,
                    player.playlist.count_for_user(author),
                    permissions.max_songs,
                ),
                expire_in=30,
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

        if player and player.voice_client and player.voice_client.channel:
            pvc = player.voice_client.channel
            avc = author.voice.channel
            perms = self.permissions.for_user(author)
            if pvc != avc and perms.summonplay:
                await self.cmd_summon(author.guild, author, message)
                return

            if pvc != avc and not perms.summonplay:
                return

        if player and player.is_paused:
            player.resume()
            await self.safe_send_message(
                channel,
                self.str.get(
                    "cmd-unpause-check",
                    "Bot was previously paused, resuming playback now.",
                ),
                expire_in=30,
            )

    async def cmd_play(
        self,
        message: discord.Message,
        _player: Optional[MusicPlayer],
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
        song_url: str,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}play song_link
            {command_prefix}play text to search for
            {command_prefix}play spotify_uri

        Adds the song to the playlist.  If a link is not provided, the first
        result from a youtube search is added to the queue.

        If enabled in the config, the bot will also support Spotify URLs, however
        it will use the metadata (e.g song name and artist) to find a YouTube
        equivalent of the song. Streaming from Spotify is not possible.
        """
        await self._do_cmd_unpause_check(_player, channel, author, message)

        return await self._cmd_play(
            message,
            _player,
            channel,
            guild,
            author,
            permissions,
            leftover_args,
            song_url,
            head=False,
        )

    async def cmd_shuffleplay(
        self,
        message: discord.Message,
        _player: Optional[MusicPlayer],
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
        await self._do_cmd_unpause_check(_player, channel, author, message)

        await self._cmd_play(
            message,
            _player,
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
            self.str.get("cmd-shuffleplay-shuffled", "Shuffled {0}'s playlist").format(
                message.guild
            ),
            delete_after=30,
        )

    async def cmd_playnext(
        self,
        message: discord.Message,
        _player: Optional[MusicPlayer],
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
        song_url: str,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}playnext song_link
            {command_prefix}playnext text to search for
            {command_prefix}playnext spotify_uri

        Adds the song to the playlist next.  If a link is not provided, the first
        result from a youtube search is added to the queue.

        If enabled in the config, the bot will also support Spotify URLs, however
        it will use the metadata (e.g song name and artist) to find a YouTube
        equivalent of the song. Streaming from Spotify is not possible.
        """
        await self._do_cmd_unpause_check(_player, channel, author, message)

        return await self._cmd_play(
            message,
            _player,
            channel,
            guild,
            author,
            permissions,
            leftover_args,
            song_url,
            head=True,
        )

    async def cmd_playnow(
        self,
        message: discord.Message,
        _player: Optional[MusicPlayer],
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
        song_url: str,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}play song_link
            {command_prefix}play text to search for
            {command_prefix}play spotify_uri

        Adds the song to be played back immediately.  If a link is not provided, the first
        result from a youtube search is added to the queue.

        If enabled in the config, the bot will also support Spotify URLs, however
        it will use the metadata (e.g song name and artist) to find a YouTube
        equivalent of the song. Streaming from Spotify is not possible.
        """
        await self._do_cmd_unpause_check(_player, channel, author, message)

        # attempt to queue the song, but used the front of the queue and skip current playback.
        return await self._cmd_play(
            message,
            _player,
            channel,
            guild,
            author,
            permissions,
            leftover_args,
            song_url,
            head=True,
            skip_playing=True,
        )

    async def cmd_seek(
        self,
        guild: discord.Guild,
        _player: Optional[MusicPlayer],
        leftover_args: List[str],
        seek_time: str = "",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}seek [time]

        Restarts the current song at the given time.
        If time starts with + or - seek will be relative to current playback time.
        Time should be given in seconds, fractional seconds are accepted.
        Due to codec specifics in ffmpeg, this may not be accurate.
        """
        # TODO: perhaps a means of listing chapters and seeking to them. like `seek ch1` & `seek list`
        if not _player or not _player.current_entry:
            raise exceptions.CommandError(
                "Cannot use seek if there is nothing playing.",
                expire_in=30,
            )

        if _player.current_entry.duration is None:
            raise exceptions.CommandError(
                "Cannot use seek on current track, it has an unknown duration.",
                expire_in=30,
            )

        if not isinstance(
            _player.current_entry, (URLPlaylistEntry, LocalFilePlaylistEntry)
        ):
            raise exceptions.CommandError(
                "Seeking is not supported for streams.",
                expire_in=30,
            )

        # take in all potential arguments.
        if leftover_args:
            args = leftover_args
            args.insert(0, seek_time)
            seek_time = " ".join(args)

        if not seek_time:
            raise exceptions.CommandError(
                "Cannot use seek without a time to position playback.",
                expire_in=30,
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
                    f"Could not convert `{seek_time}` to a valid time in seconds.",
                    expire_in=30,
                ) from e
        else:
            f_seek_time = 0.0 + format_time_to_seconds(seek_time)

        if relative_seek != 0:
            f_seek_time = _player.progress + (relative_seek * f_seek_time)

        if f_seek_time > _player.current_entry.duration or f_seek_time < 0:
            td = format_song_duration(_player.current_entry.duration_td)
            prog = format_song_duration(_player.progress)
            raise exceptions.CommandError(
                f"Cannot seek to `{seek_time}` (`{f_seek_time:.2f}` seconds) in the current track with a length of `{prog} / {td}`",
                expire_in=30,
            )

        entry = _player.current_entry
        entry.set_start_time(f_seek_time)
        _player.playlist.insert_entry_at_index(0, entry)

        # handle history playlist updates.
        if (
            self.config.enable_queue_history_global
            or self.config.enable_queue_history_guilds
        ):
            self.server_data[guild.id].current_playing_url = ""

        _player.skip()

        return Response(
            f"Seeking to time `{seek_time}` (`{f_seek_time:.2f}` seconds) in the current song.",
            delete_after=30,
        )

    async def cmd_repeat(
        self, guild: discord.Guild, option: str = ""
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}repeat [all | playlist | song | on | off]

        Toggles playlist or song looping.
        If no option is provided the bot will toggle through playlist looping, song looping, and looping off.
        """
        # TODO: this command needs TLC.

        player = self.get_player_in(guild)
        option = option.lower() if option else ""
        prefix = self.server_data[guild.id].command_prefix

        if not player:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-repeat-no-voice",
                    "The bot is not in a voice channel.  "
                    "Use %ssummon to summon it to your voice channel.",
                )
                % prefix,
                expire_in=30,
            )

        if not player.current_entry:
            return Response(
                self.str.get(
                    "cmd-repeat-no-songs",
                    "No songs are currently playing. Play something with {}play.",
                ).format(prefix),
                delete_after=30,
            )

        if option not in ["all", "playlist", "on", "off", "song", ""]:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-repeat-invalid",
                    "Invalid option, please run {}help repeat to a list of available options.",
                ).format(prefix),
                expire_in=30,
            )

        if option in ["all", "playlist"]:
            player.loopqueue = not player.loopqueue
            if player.loopqueue:
                return Response(
                    self.str.get(
                        "cmd-repeat-playlist-looping", "Playlist is now repeating."
                    ),
                    delete_after=30,
                )

            return Response(
                self.str.get(
                    "cmd-repeat-playlist-not-looping",
                    "Playlist is no longer repeating.",
                ),
                delete_after=30,
            )

        if option == "song":
            player.repeatsong = not player.repeatsong
            if player.repeatsong:
                return Response(
                    self.str.get("cmd-repeat-song-looping", "Song is now repeating."),
                    delete_after=30,
                )

            return Response(
                self.str.get(
                    "cmd-repeat-song-not-looping", "Song is no longer repeating."
                )
            )

        if option == "on":
            if player.repeatsong:
                return Response(
                    self.str.get(
                        "cmd-repeat-already-looping", "Song is already looping!"
                    ),
                    delete_after=30,
                )

            player.repeatsong = True
            return Response(self.str.get("cmd-repeat-song-looping"), delete_after=30)

        if option == "off":
            # TODO: This will fail to behave is both are somehow on.
            if player.repeatsong:
                player.repeatsong = False
                return Response(self.str.get("cmd-repeat-song-not-looping"))

            if player.loopqueue:
                player.loopqueue = False
                return Response(self.str.get("cmd-repeat-playlist-not-looping"))

            raise exceptions.CommandError(
                self.str.get(
                    "cmd-repeat-already-off", "The player is not currently looping."
                ),
                expire_in=30,
            )

        if player.repeatsong:
            player.loopqueue = True
            player.repeatsong = False
            return Response(
                self.str.get("cmd-repeat-playlist-looping"), delete_after=30
            )

        if player.loopqueue:
            if len(player.playlist.entries) > 0:
                message = self.str.get("cmd-repeat-playlist-not-looping")
            else:
                message = self.str.get("cmd-repeat-song-not-looping")
            player.loopqueue = False
        else:
            player.repeatsong = True
            message = self.str.get("cmd-repeat-song-looping")

        return Response(message, delete_after=30)

    async def cmd_move(
        self,
        guild: discord.Guild,
        channel: MessageableChannel,
        command: str,
        leftover_args: List[str],
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}move [Index of song to move] [Index to move song to]
            Ex: !move 1 3

        Swaps the location of a song within the playlist.
        """
        # TODO: move command needs some tlc. args renamed, better checks.
        player = self.get_player_in(guild)
        if not player:
            prefix = self.server_data[guild.id].command_prefix
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-move-no-voice",
                    "The bot is not in a voice channel.  "
                    f"Use {prefix}summon to summon it to your voice channel.",
                )
            )

        if not player.current_entry:
            return Response(
                self.str.get(
                    "cmd-move-no-songs",
                    "There are no songs queued. Play something with {}play",
                ).format(self.server_data[guild.id].command_prefix),
            )

        indexes = []
        try:
            indexes.append(int(command) - 1)
            indexes.append(int(leftover_args[0]) - 1)
        except (ValueError, IndexError):
            # TODO: return command error instead, specific to the exception.
            return Response(
                self.str.get(
                    "cmd-move-indexes_not_intergers", "Song indexes must be integers!"
                ),
                delete_after=30,
            )

        for i in indexes:
            if i < 0 or i > len(player.playlist.entries) - 1:
                return Response(
                    self.str.get(
                        "cmd-move-invalid-indexes",
                        "Sent indexes are outside of the playlist scope!",
                    ),
                    delete_after=30,
                )

        # TODO:  replace this with a Response maybe.  UI stuff.
        await self.safe_send_message(
            channel,
            self.str.get(
                "cmd-move-success",
                "Successfully moved the requested song from positon number {} in queue to position {}!",
            ).format(indexes[0] + 1, indexes[1] + 1),
            expire_in=30,
        )

        song = player.playlist.delete_entry_at_index(indexes[0])

        player.playlist.insert_entry_at_index(indexes[1], song)
        return None

    async def _cmd_play_compound_link(
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
            msg = await self.safe_send_message(channel, prompt)
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
                    # TODO: i18n / UI stuff
                    f"This link contains a Playlist ID:\n`{song_url}`\n\nDo you want to queue the playlist too?",
                    pl_url,
                    ignore_vid,
                )
            )

    async def _cmd_play(
        self,
        message: discord.Message,
        _player: Optional[MusicPlayer],
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
        player = _player if _player else None

        await channel.typing()

        if not player and permissions.summonplay and channel.guild:
            response = await self.cmd_summon(channel.guild, author, message)
            if response:
                if self.config.embeds:
                    content = self._gen_embed()
                    content.title = "summon"
                    content.description = str(response.content)
                    await self.safe_send_message(
                        channel,
                        content,
                        expire_in=(
                            response.delete_after if self.config.delete_messages else 0
                        ),
                    )
                else:
                    await self.safe_send_message(
                        channel,
                        str(response.content),
                        expire_in=(
                            response.delete_after if self.config.delete_messages else 0
                        ),
                    )
                player = self.get_player_in(channel.guild)

        if not player:
            prefix = self.server_data[guild.id].command_prefix
            raise exceptions.CommandError(
                "The bot is not in a voice channel.  "
                f"Use {prefix}summon to summon it to your voice channel."
            )

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

        # Validate spotify links are supported before we try them.
        if "open.spotify.com" in song_url.lower():
            if self.config.spotify_enabled:
                if not Spotify.is_url_supported(song_url):
                    raise exceptions.CommandError(
                        "Spotify URL is invalid or not currently supported."
                    )
            else:
                raise exceptions.CommandError(
                    "Detected a spotify URL, but spotify is not enabled."
                )

        # This lock prevent spamming play commands to add entries that exceeds time limit/ maximum song limit
        async with self.aiolocks[_func_() + ":" + str(author.id)]:
            if (
                permissions.max_songs
                and player.playlist.count_for_user(author) >= permissions.max_songs
            ):
                raise exceptions.PermissionsError(
                    self.str.get(
                        "cmd-play-limit",
                        "You have reached your enqueued song limit ({0})",
                    ).format(permissions.max_songs),
                    expire_in=30,
                )

            if player.karaoke_mode and not permissions.bypass_karaoke_mode:
                raise exceptions.PermissionsError(
                    self.str.get(
                        "karaoke-enabled",
                        "Karaoke mode is enabled, please try again when its disabled!",
                    ),
                    expire_in=30,
                )

            # Get processed info from ytdlp
            info = None
            try:
                info = await self.downloader.extract_info(
                    song_url, download=False, process=True
                )
            except Exception as e:
                info = None
                log.exception("Issue with extract_info(): ")
                raise exceptions.CommandError(str(e)) from e

            if not info:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-play-noinfo",
                        "That video cannot be played. Try using the {0}stream command.",
                    ).format(self.server_data[guild.id].command_prefix),
                    expire_in=30,
                )

            # ensure the extractor has been allowed via permissions.
            permissions.can_use_extractor(info.extractor)

            # if the result has "entries" but it's empty, it might be a failed search.
            if "entries" in info and not info.entry_count:
                if info.extractor.startswith("youtube:search"):
                    # TOOD: UI, i18n stuff
                    raise exceptions.CommandError(
                        f"Youtube search returned no results for:  {song_url}"
                    )

            # If the result has usable entries, we assume it is a playlist
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
                    "Processed %d of %d songs in %.3f seconds at %.2f s/song",
                    listlen,
                    num_songs,
                    time_taken,
                    time_taken / listlen if listlen else 1,
                )

                if not entry_list:
                    raise exceptions.CommandError(
                        self.str.get(
                            "cmd-play-playlist-maxduration",
                            "No songs were added, all songs were over max duration (%ss)",
                        )
                        % permissions.max_song_length,
                        expire_in=30,
                    )

                reply_text = self.str.get(
                    "cmd-play-playlist-reply",
                    "Enqueued **%s** songs to be played. Position in queue: %s",
                )
                btext = str(listlen)

            # If it's an entry
            else:
                # youtube:playlist extractor but it's actually an entry
                # ^ wish I had a URL for this one.
                if info.get("extractor", "").startswith("youtube:playlist"):
                    log.noise(  # type: ignore[attr-defined]
                        "Extracted an entry with youtube:playlist as extractor key"
                    )

                # Check the block list again, with the info this time.
                self._do_song_blocklist_check(info.url)
                self._do_song_blocklist_check(info.title)

                if (
                    permissions.max_song_length
                    and info.duration_td.seconds > permissions.max_song_length
                ):
                    raise exceptions.PermissionsError(
                        self.str.get(
                            "cmd-play-song-limit",
                            "Song duration exceeds limit ({0} > {1})",
                        ).format(info.duration, permissions.max_song_length),
                        expire_in=30,
                    )

                entry, position = await player.playlist.add_entry_from_info(
                    info, channel=channel, author=author, head=head
                )

                reply_text = self.str.get(
                    "cmd-play-song-reply",
                    "Enqueued `%s` to be played. Position in queue: %s",
                )
                btext = entry.title

            log.debug("Added song(s) at position %s", position)
            if position == 1 and player.is_stopped:
                position = self.str.get("cmd-play-next", "Up next!")
                reply_text %= (btext, position)
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

                position = self.str.get("cmd-play-next", "Up next!")
                reply_text %= (btext, position)

            else:
                reply_text %= (btext, position)
                try:
                    time_until = await player.playlist.estimate_time_until(
                        position, player
                    )
                    reply_text += (
                        self.str.get(
                            "cmd-play-eta", " - estimated time until playing: %s"
                        )
                        % f"`{format_song_duration(time_until)}`"
                    )
                except exceptions.InvalidDataError:
                    reply_text += self.str.get(
                        "cmd-play-eta-error", " - cannot estimate time until playing"
                    )
                    log.warning(
                        "Cannot estimate time until playing for position: %d", position
                    )

        return Response(reply_text, delete_after=30)

    async def cmd_stream(
        self,
        _player: Optional[MusicPlayer],
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        message: discord.Message,
        song_url: str,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}stream song_link

        Enqueue a media stream.
        This could mean an actual stream like Twitch or shoutcast, or simply streaming
        media without pre-downloading it.  Note: FFmpeg is notoriously bad at handling
        streams, especially on poor connections.  You have been warned.
        """

        await self._do_cmd_unpause_check(_player, channel, author, message)

        if permissions.summonplay and not _player:
            response = await self.cmd_summon(guild, author, message)
            if response:
                if self.config.embeds:
                    content = self._gen_embed()
                    content.title = "summon"
                    content.description = str(response.content)
                    await self.safe_send_message(
                        channel,
                        content,
                        expire_in=(
                            response.delete_after if self.config.delete_messages else 0
                        ),
                    )
                else:
                    await self.safe_send_message(
                        channel,
                        str(response.content),
                        expire_in=(
                            response.delete_after if self.config.delete_messages else 0
                        ),
                    )
                p = self.get_player_in(guild)
                if p:
                    _player = p

        if not _player:
            prefix = self.server_data[guild.id].command_prefix
            raise exceptions.CommandError(
                "The bot is not in a voice channel.  "
                f"Use {prefix}summon to summon it to your voice channel."
            )

        if (
            permissions.max_songs
            and _player.playlist.count_for_user(author) >= permissions.max_songs
        ):
            raise exceptions.PermissionsError(
                self.str.get(
                    "cmd-stream-limit",
                    "You have reached your enqueued song limit ({0})",
                ).format(permissions.max_songs),
                expire_in=30,
            )

        if _player.karaoke_mode and not permissions.bypass_karaoke_mode:
            raise exceptions.PermissionsError(
                self.str.get(
                    "karaoke-enabled",
                    "Karaoke mode is enabled, please try again when its disabled!",
                ),
                expire_in=30,
            )

        async with channel.typing():
            # TODO: find more streams to test.
            # NOTE: this will return a URL if one was given but ytdl doesn't support it.
            try:
                info = await self.downloader.extract_info(
                    song_url, download=False, process=True, as_stream=True
                )
            except Exception as e:
                log.exception(
                    "Failed to get info from the stream request: %s", song_url
                )
                raise exceptions.CommandError(str(e)) from e

            if info.has_entries:
                raise exceptions.CommandError(
                    "Streaming playlists is not yet supported.",
                    expire_in=30,
                )
                # TODO: could process these and force them to be stream entries...

            self._do_song_blocklist_check(info.url)
            # if its a "forced stream" this would be a waste.
            if info.url != info.title:
                self._do_song_blocklist_check(info.title)

            await _player.playlist.add_stream_from_info(
                info, channel=channel, author=author, head=False
            )

            if _player.is_stopped:
                _player.play()

        return Response(
            self.str.get("cmd-stream-success", "Streaming."), delete_after=6
        )

    async def cmd_search(
        self,
        message: discord.Message,
        player: MusicPlayer,
        channel: GuildMessageableChannels,
        guild: discord.Guild,
        author: discord.Member,
        permissions: PermissionGroup,
        leftover_args: List[str],
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}search [service] [number] query

        Searches a service for a video and adds it to the queue.
        - service: any one of the following services:
            - youtube (yt) (default if unspecified)
            - soundcloud (sc)
            - yahoo (yh)
        - number: return a number of video results and waits for user to choose one
          - defaults to 3 if unspecified
          - note: If your search query starts with a number,
                  you must put your query in quotes
            - ex: {command_prefix}search 2 "I ran seagulls"
        The command issuer can use reactions to indicate their response to each result.
        """

        if (
            permissions.max_songs
            and player.playlist.count_for_user(author) > permissions.max_songs
        ):
            raise exceptions.PermissionsError(
                self.str.get(
                    "cmd-search-limit",
                    "You have reached your playlist item limit ({0})",
                ).format(permissions.max_songs),
                expire_in=30,
            )

        if player.karaoke_mode and not permissions.bypass_karaoke_mode:
            raise exceptions.PermissionsError(
                self.str.get(
                    "karaoke-enabled",
                    "Karaoke mode is enabled, please try again when its disabled!",
                ),
                expire_in=30,
            )

        def argcheck() -> None:
            if not leftover_args:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-search-noquery", "Please specify a search query.\n%s"
                    )
                    % dedent(
                        self.cmd_search.__doc__.format(  # type: ignore
                            command_prefix=self.server_data[guild.id].command_prefix
                        )
                    ),
                    expire_in=60,
                )

        argcheck()

        service = "youtube"
        items_requested = self.config.defaultsearchresults
        max_items = permissions.max_search_items
        services = {
            "youtube": "ytsearch",
            "soundcloud": "scsearch",
            "yahoo": "yvsearch",
            "yt": "ytsearch",
            "sc": "scsearch",
            "yh": "yvsearch",
        }

        if leftover_args[0] in services:
            service = leftover_args.pop(0)
            argcheck()

        if leftover_args[0].isdigit():
            items_requested = int(leftover_args.pop(0))
            argcheck()

            if items_requested > max_items:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-search-searchlimit",
                        "You cannot search for more than %s videos",
                    )
                    % max_items
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

        srvc = services[service]
        args_str = " ".join(leftover_args)
        search_query = f"{srvc}{items_requested}:{args_str}"

        self._do_song_blocklist_check(args_str)

        search_msg = await self.safe_send_message(
            channel, self.str.get("cmd-search-searching", "Searching for videos...")
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
                await self.safe_edit_message(search_msg, str(e), send_if_fail=True)
            return None

        else:
            if search_msg:
                await self.safe_delete_message(search_msg)

        if not info:
            return Response(
                self.str.get("cmd-search-none", "No videos found."), delete_after=30
            )

        entries = info.get_entries_objects()

        # Decide if the list approach or the reaction approach should be used
        if self.config.searchlist:
            result_message_array = []

            if self.config.embeds:
                content = self._gen_embed()
                content.title = self.str.get(
                    "cmd-search-title", "{0} search results:"
                ).format(service.capitalize())
                content.description = "To select a song, type the corresponding number"
            else:
                result_header = self.str.get(
                    "cmd-search-title", "{0} search results:"
                ).format(service.capitalize())
                result_header += "\n\n"

            for entry in entries:
                # This formats the results and adds it to an array
                # format_song_duration removes the hour section
                # if the song is shorter than an hour
                result_message_array.append(
                    self.str.get(
                        "cmd-search-list-entry", "**{0}**. **{1}** | {2}"
                    ).format(
                        entries.index(entry) + 1,
                        entry["title"],
                        format_song_duration(entry.duration_td),
                    )
                )
            # This combines the formatted result strings into one list.
            result_string = "\n".join(str(result) for result in result_message_array)
            result_string += "\n**0.** Cancel"

            if self.config.embeds:
                # Add the result entries to the embedded message and send it to the channel
                content.add_field(
                    name=self.str.get("cmd-search-field-name", "Pick a song"),
                    value=result_string,
                    inline=False,
                )
                result_message = await self.safe_send_message(channel, content)
            else:
                # Construct the complete message and send it to the channel.
                result_string = result_header + result_string
                result_string += "\n\nSelect song by typing the corresponding number or type cancel to cancel search"
                result_message = await self.safe_send_message(
                    channel,
                    self.str.get("cmd-search-result-list-noembed", "{0}").format(
                        result_string
                    ),
                )

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
                choice = await self.wait_for("message", timeout=30.0, check=check)
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
                if self.config.embeds:
                    return Response(
                        self.str.get(
                            "cmd-search-accept-list-embed", "[{0}]({1}) added to queue"
                        ).format(
                            entries[int(choice.content) - 1]["title"],
                            entries[int(choice.content) - 1]["url"],
                        ),
                        delete_after=30,
                    )

                return Response(
                    self.str.get(
                        "cmd-search-accept-list-noembed", "{0} added to queue"
                    ).format(entries[int(choice.content) - 1]["title"]),
                    delete_after=30,
                )
        else:
            # patch for loop-defined cell variable.
            res_msg_ids = []
            # Original code
            for entry in entries:
                result_message = await self.safe_send_message(
                    channel,
                    self.str.get("cmd-search-result", "Result {0}/{1}: {2}").format(
                        entries.index(entry) + 1,
                        info.entry_count,
                        entry["url"],
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
                        self.str.get("cmd-search-accept", "Alright, coming right up!"),
                        delete_after=30,
                    )

                if str(reaction.emoji) == EMOJI_CROSS_MARK_BUTTON:  # cross
                    # delete last result and move on to next
                    await self.safe_delete_message(result_message)
                else:  # stop
                    # delete last result and stop showing results.
                    await self.safe_delete_message(result_message)
                    break
        return None

    async def cmd_np(
        self,
        player: MusicPlayer,
        channel: MessageableChannel,
        guild: discord.Guild,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}np

        Displays the current song in chat.
        """

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

            # TODO: properly do the i18n stuff in here.
            action_text = (
                self.str.get("cmd-np-action-streaming", "Streaming")
                if streaming
                else self.str.get("cmd-np-action-playing", "Playing")
            )

            entry = player.current_entry
            entry_author = player.current_entry.author

            if entry_author:
                np_text = self.str.get(
                    "cmd-np-reply-author",
                    "Currently {action}: **{title}** added by **{author}**\nProgress: {progress_bar} {progress}\n\N{WHITE RIGHT POINTING BACKHAND INDEX} <{url}>",
                ).format(
                    action=action_text,
                    title=entry.title,
                    author=entry_author.name,
                    progress_bar=prog_bar_str,
                    progress=prog_str,
                    url=entry.url,
                )
            else:
                np_text = self.str.get(
                    "cmd-np-reply-noauthor",
                    "Currently {action}: **{title}**\nProgress: {progress_bar} {progress}\n\N{WHITE RIGHT POINTING BACKHAND INDEX} <{url}>",
                ).format(
                    action=action_text,
                    title=entry.title,
                    progress_bar=prog_bar_str,
                    progress=prog_str,
                    url=entry.url,
                )

                # TODO: i18n
                if entry.from_auto_playlist:
                    np_text += "\n`via autoplaylist`"

            if self.config.embeds:
                content = self._gen_embed()
                content.title = action_text
                content.add_field(
                    name=f"Currently {action_text}", value=entry.title, inline=False
                )
                if entry_author:
                    content.add_field(
                        name="Added By:", value=entry_author.name, inline=False
                    )
                elif entry.from_auto_playlist:
                    content.add_field(
                        name="Added By:", value="`auto playlist`", inline=False
                    )
                content.add_field(
                    name="Progress",
                    value=f"{prog_str}\n{prog_bar_str}\n\n",
                    inline=False,
                )
                if len(entry.url) <= 1024:
                    content.add_field(name="URL:", value=entry.url, inline=False)
                if entry.thumbnail_url:
                    content.set_image(url=entry.thumbnail_url)
                else:
                    log.warning("No thumbnail set for entry with url: %s", entry.url)

            self.server_data[guild.id].last_np_msg = await self.safe_send_message(
                channel, content if self.config.embeds else np_text, expire_in=30
            )
            return None

        return Response(
            self.str.get(
                "cmd-np-none",
                "There are no songs queued! Queue something with {0}play.",
            ).format(self.server_data[guild.id].command_prefix),
            delete_after=30,
        )

    async def cmd_summon(
        self, guild: discord.Guild, author: discord.Member, message: discord.Message
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}summon

        Call the bot to the summoner's voice channel.
        """

        lock_key = f"summon:{guild.id}"

        if self.aiolocks[lock_key].locked():
            log.debug("Waiting for summon lock: %s", lock_key)

        async with self.aiolocks[lock_key]:
            log.debug("Summon lock acquired for: %s", lock_key)

            if not author.voice or not author.voice.channel:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-summon-novc",
                        "You are not connected to voice. Try joining a voice channel!",
                    )
                )

            player = self.get_player_in(guild)
            if player and player.voice_client and guild == author.voice.channel.guild:
                # NOTE:  .move_to() does not support setting self-deafen flag,
                # nor respect flags set in initial connect call.
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
                "Joining %s/%s",
                author.voice.channel.guild.name,
                author.voice.channel.name,
            )

            self.server_data[guild.id].last_np_msg = message

            return Response(
                self.str.get("cmd-summon-reply", "Connected to `{0.name}`").format(
                    author.voice.channel
                ),
                delete_after=30,
            )

    async def cmd_follow(
        self,
        guild: discord.Guild,
        author: discord.Member,
        user_mentions: UserMentions,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}follow

        MusicBot will automatically follow a user when they change channels.
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
                    f"No longer following user `{author.name}`",
                    delete_after=30,
                )

            # Change to following a new user.
            self.server_data[guild.id].follow_user = author
            return Response(
                f"Now following user `{author.name}` between voice channels.",
                delete_after=30,
            )

        # Follow the invoking user.
        # If owner mentioned a user, bind to the mentioned user instead.
        bind_to_member = author
        if author.id == self.config.owner_id and user_mentions:
            m = user_mentions.pop(0)
            if not isinstance(m, discord.Member):
                raise exceptions.CommandError(
                    "MusicBot cannot follow a user that is not a member of the server.",
                    expire_in=30,
                )
            bind_to_member = m

        self.server_data[guild.id].follow_user = bind_to_member
        return Response(
            f"Will follow user `{bind_to_member.name}` between voice channels.",
            delete_after=30,
        )

    async def cmd_pause(self, player: MusicPlayer) -> CommandResponse:
        """
        Usage:
            {command_prefix}pause

        Pauses playback of the current song.
        """

        if player.is_playing:
            player.pause()
            return Response(
                self.str.get("cmd-pause-reply", "Paused music in `{0.name}`").format(
                    player.voice_client.channel
                ),
                delete_after=30,
            )

        raise exceptions.CommandError(
            self.str.get("cmd-pause-none", "Player is not playing."), expire_in=30
        )

    async def cmd_resume(self, player: MusicPlayer) -> CommandResponse:
        """
        Usage:
            {command_prefix}resume

        Resumes playback of a paused song.
        """

        if player.is_paused:
            player.resume()
            return Response(
                self.str.get("cmd-resume-reply", "Resumed music in `{0.name}`").format(
                    player.voice_client.channel
                ),
                delete_after=15,
            )

        if player.is_stopped and player.playlist:
            player.play()
            return None

        raise exceptions.CommandError(
            self.str.get("cmd-resume-none", "Player is not paused."), expire_in=30
        )

    async def cmd_shuffle(
        self, channel: MessageableChannel, player: MusicPlayer
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}shuffle

        Shuffles the server's queue.
        """

        player.playlist.shuffle()

        cards = [
            "\N{BLACK SPADE SUIT}",
            "\N{BLACK CLUB SUIT}",
            "\N{BLACK HEART SUIT}",
            "\N{BLACK DIAMOND SUIT}",
        ]
        random.shuffle(cards)

        hand = await self.safe_send_message(channel, " ".join(cards))
        await asyncio.sleep(0.6)

        if hand:
            for _ in range(4):
                random.shuffle(cards)
                await self.safe_edit_message(hand, " ".join(cards))
                await asyncio.sleep(0.6)

            await self.safe_delete_message(hand, quiet=True)
        return Response(
            self.str.get("cmd-shuffle-reply", "Shuffled `{0}`'s queue.").format(
                player.voice_client.channel.guild
            ),
            delete_after=15,
        )

    async def cmd_clear(
        self,
        player: MusicPlayer,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}clear

        Clears the playlist.
        """

        player.playlist.clear()

        return Response(
            self.str.get("cmd-clear-reply", "Cleared `{0}'s` queue").format(
                player.voice_client.channel.guild
            ),
            delete_after=20,
        )

    async def cmd_remove(
        self,
        user_mentions: UserMentions,
        author: discord.Member,
        permissions: PermissionGroup,
        guild: discord.Guild,
        player: MusicPlayer,
        index: str = "",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}remove [# in queue]

        Removes queued songs. If a number is specified, removes that song in the queue, otherwise removes the most recently queued song.
        """

        if not player.playlist.entries:
            raise exceptions.CommandError(
                self.str.get("cmd-remove-none", "There's nothing to remove!"),
                expire_in=20,
            )

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
                            self.str.get(
                                "cmd-remove-reply", "Removed `{0}` added by `{1}`"
                            )
                            .format(entry_text, user.name)
                            .strip()
                        )

                    except ValueError as e:
                        raise exceptions.CommandError(
                            self.str.get(
                                "cmd-remove-missing",
                                "Nothing found in the queue from user `%s`",
                            )
                            % user.name,
                            expire_in=20,
                        ) from e

                raise exceptions.PermissionsError(
                    self.str.get(
                        "cmd-remove-noperms",
                        "You do not have the valid permissions to remove that entry from the queue, make sure you're the one who queued it or have instant skip permissions",
                    ),
                    expire_in=20,
                )

        if not index:
            idx = len(player.playlist.entries)

        try:
            idx = int(index)
        except (TypeError, ValueError) as e:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-remove-invalid",
                    "Invalid number. Use {}queue to find queue positions.",
                ).format(self.server_data[guild.id].command_prefix),
                expire_in=20,
            ) from e

        if idx > len(player.playlist.entries):
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-remove-invalid",
                    "Invalid number. Use {}queue to find queue positions.",
                ).format(self.server_data[guild.id].command_prefix),
                expire_in=20,
            )

        if (
            permissions.remove
            or author == player.playlist.get_entry_at_index(idx - 1).author
        ):
            entry = player.playlist.delete_entry_at_index((idx - 1))
            if entry.channel and entry.author:
                return Response(
                    self.str.get(
                        "cmd-remove-reply-author", "Removed entry `{0}` added by `{1}`"
                    )
                    .format(entry.title, entry.author.name)
                    .strip()
                )

            return Response(
                self.str.get("cmd-remove-reply-noauthor", "Removed entry `{0}`")
                .format(entry.title)
                .strip()
            )

        raise exceptions.PermissionsError(
            self.str.get(
                "cmd-remove-noperms",
                "You do not have the valid permissions to remove that entry from the queue, make sure you're the one who queued it or have instant skip permissions",
            ),
            expire_in=20,
        )

    async def cmd_skip(
        self,
        guild: discord.Guild,
        player: MusicPlayer,
        author: discord.Member,
        message: discord.Message,
        permissions: PermissionGroup,
        voice_channel: Optional[VoiceableChannel],
        param: str = "",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}skip [force/f]

        Skips the current song when enough votes are cast.
        Owners and those with the instaskip permission can add 'force' or 'f' after the command to force skip.
        """

        if player.is_stopped:
            raise exceptions.CommandError(
                self.str.get("cmd-skip-none", "Can't skip! The player is not playing!"),
                expire_in=20,
            )

        if not player.current_entry:
            next_entry = player.playlist.peek()
            if next_entry:
                if next_entry.is_downloading:
                    return Response(
                        self.str.get(
                            "cmd-skip-dl",
                            "The next song (`%s`) is downloading, please wait.",
                        )
                        % next_entry.title
                    )

                if next_entry.is_downloaded:
                    return Response(
                        "The next song will be played shortly.  Please wait."
                    )

                return Response(
                    "Something odd is happening.  "
                    "You might want to restart the bot if it doesn't start working."
                )
            return Response(
                "Something strange is happening.  "
                "You might want to restart the bot if it doesn't start working."
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
                    self.str.get(
                        "cmd-skip-force-noperms-looped-song",
                        "You do not have permission to force skip a looped song.",
                    )
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
                self.str.get("cmd-skip-force", "Force skipped `{}`.").format(
                    current_entry.title
                ),
                reply=True,
                delete_after=30,
            )

        if not permission_force_skip and force_skip:
            raise exceptions.PermissionsError(
                self.str.get(
                    "cmd-skip-force-noperms",
                    "You do not have permission to force skip.",
                ),
                expire_in=30,
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
                    self.str.get(
                        "cmd-skip-vote-noperms-looped-song",
                        "You do not have permission to skip a looped song.",
                    )
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
                self.str.get(
                    "cmd-skip-reply-skipped-1",
                    "Your skip for `{0}` was acknowledged.\nThe vote to skip has been passed.{1}",
                ).format(
                    current_entry.title,
                    (
                        self.str.get(
                            "cmd-skip-reply-skipped-2", " Next song coming up!"
                        )
                        if player.playlist.peek()
                        else ""
                    ),
                ),
                reply=True,
                delete_after=20,
            )

        # TODO: When a song gets skipped, delete the old x needed to skip messages
        if not permissions.skip_looped and player.repeatsong:
            raise exceptions.PermissionsError(
                self.str.get(
                    "cmd-skip-vote-noperms-looped-song",
                    "You do not have permission to skip a looped song.",
                )
            )

        if player.repeatsong:
            player.repeatsong = False
        return Response(
            self.str.get(
                "cmd-skip-reply-voted-1",
                "Your skip for `{0}` was acknowledged.\n**{1}** more {2} required to vote to skip this song.",
            ).format(
                current_entry.title,
                skips_remaining,
                (
                    self.str.get("cmd-skip-reply-voted-2", "person is")
                    if skips_remaining == 1
                    else self.str.get("cmd-skip-reply-voted-3", "people are")
                ),
            ),
            reply=True,
            delete_after=20,
        )

    async def cmd_volume(
        self, player: MusicPlayer, new_volume: str = ""
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}volume (+/-)[volume]

        Sets the playback volume. Accepted values are from 1 to 100.
        Putting + or - before the volume will make the volume change relative to the current volume.
        """

        if not new_volume:
            return Response(
                self.str.get("cmd-volume-current", "Current volume: `%s%%`")
                % int(player.volume * 100),
                reply=True,
                delete_after=20,
            )

        relative = False
        if new_volume[0] in "+-":
            relative = True

        try:
            int_volume = int(new_volume)

        except ValueError as e:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-volume-invalid", "`{0}` is not a valid number"
                ).format(new_volume),
                expire_in=20,
            ) from e

        vol_change = 0
        if relative:
            vol_change = int_volume
            int_volume += int(player.volume * 100)

        old_volume = int(player.volume * 100)

        if 0 < int_volume <= 100:
            player.volume = int_volume / 100.0

            return Response(
                self.str.get("cmd-volume-reply", "Updated volume from **%d** to **%d**")
                % (old_volume, int_volume),
                reply=True,
                delete_after=20,
            )

        if relative:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-volume-unreasonable-relative",
                    "Unreasonable volume change provided: {}{:+} -> {}%.  Provide a change between {} and {:+}.",
                ).format(
                    old_volume,
                    vol_change,
                    old_volume + vol_change,
                    1 - old_volume,
                    100 - old_volume,
                ),
                expire_in=20,
            )

        raise exceptions.CommandError(
            self.str.get(
                "cmd-volume-unreasonable-absolute",
                "Unreasonable volume provided: {}%. Provide a value between 1 and 100.",
            ).format(new_volume),
            expire_in=20,
        )

    async def cmd_speed(
        self, guild: discord.Guild, player: MusicPlayer, new_speed: str = ""
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}speed [rate]

        Apply a speed to the currently playing track.
        The rate must be between 0.5 and 100.0 due to ffmpeg limits.
        Stream playback does not support speed adjustments.
        """
        if not player.current_entry:
            raise exceptions.CommandError(
                "No track is playing, cannot set speed.\n"
                "Use the config command to set a default playback speed.",
                expire_in=30,
            )

        if not isinstance(
            player.current_entry, (URLPlaylistEntry, LocalFilePlaylistEntry)
        ):
            raise exceptions.CommandError(
                "Speed cannot be applied to streamed media.",
                expire_in=30,
            )

        if not new_speed:
            raise exceptions.CommandError(
                "You must provide a speed to set.",
                expire_in=30,
            )

        try:
            speed = float(new_speed)
            if speed < 0.5 or speed > 100.0:
                raise ValueError("Value out of range.")
        except (ValueError, TypeError) as e:
            raise exceptions.CommandError(
                "The speed you proivded is invalid. Use a number between 0.5 and 100.",
                expire_in=30,
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
            f"Setting playback speed to `{speed:.3f}` for current track.",
            delete_after=30,
        )

    @owner_only
    async def cmd_config(
        self,
        user_mentions: UserMentions,
        channel_mentions: List[discord.abc.GuildChannel],
        option: str,
        leftover_args: List[str],
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}config missing
                Shows help text about any missing config options.

            {command_prefix}config diff
                Lists the names of options which have been changed since loading config file.

            {command_prefix}config list
                List the available config options and their sections.

            {command_prefix}config reload
                Reload the options.ini file from disk.

            {command_prefix}config help [Section] [Option]
                Shows help text for a specific option.

            {command_prefix}config show [Section] [Option]
                Display the current value of the option.

            {command_prefix}config save [Section] [Option]
                Saves the current current value to the options file.

            {command_prefix}config set [Section] [Option] [value]
                Validates the option and sets the config for the session, but not to file.

        This command allows management of MusicBot config options file.
        """
        if user_mentions and channel_mentions:
            raise exceptions.CommandError(
                "Config cannot use channel and user mentions at the same time.",
                expire_in=30,
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
                f"Invalid option for command: `{option}`",
                expire_in=30,
            )

        # Show missing options with help text.
        if option == "missing":
            missing = ""
            for opt in self.config.register.ini_missing_options:
                missing += (
                    f"**Missing Option:** `{opt}`\n"
                    "```"
                    f"{opt.comment}\n"
                    f"Default is set to:  {opt.default}"
                    "```\n"
                )
            if not missing:
                missing = "*All config options are present and accounted for!*"

            return Response(
                missing,
                delete_after=60,
            )

        # Show options names that have changed since loading.
        if option == "diff":
            changed = ""
            for opt in self.config.register.get_updated_options():
                changed += f"`{str(opt)}`\n"

            if not changed:
                changed = "No config options appear to be changed."
            else:
                changed = f"**Changed Options:**\n{changed}"

            return Response(
                changed,
                delete_after=60,
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

            opt_list = (
                f"## Available Options:\n"
                f"**Editable Options:**\n{editable_opts}\n"
                f"**Manual Edit Only:**\n{non_edit_opts}"
            )
            return Response(
                opt_list,
                delete_after=60,
            )

        # Try to reload options.ini file from disk.
        if option == "reload":
            try:
                new_conf = Config(self._config_file)
                await new_conf.async_validate(self)

                self.config = new_conf

                return Response(
                    "Config options reloaded from file successfully!",
                    delete_after=30,
                )
            except Exception as e:
                raise exceptions.CommandError(
                    f"Unable to reload Config due to the following errror:\n{str(e)}",
                    expire_in=30,
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
                        expire_in=30,
                    )
                if len(possible_sections) > 1:
                    raise exceptions.CommandError(
                        "The option given is ambiguous, please provide a section name.",
                        expire_in=30,
                    )
                # adjust the command arguments to include the resolved section.
                leftover_args = [list(possible_sections)[0]] + leftover_args
            elif largs < 2 or (option == "set" and largs < 3):
                raise exceptions.CommandError(
                    "You must provide a section name and option name for this command.",
                    expire_in=30,
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
                f"The section `{section_arg}` is not available.\n"
                f"The available sections are:  {sects}",
                expire_in=30,
            )

        if p_opt is None:
            option_arg = f"[{section_arg}] > {option_arg}"
            raise exceptions.CommandError(
                f"The option `{option_arg}` is not available.",
                expire_in=30,
            )
        opt = p_opt

        # Display some commentary about the option and its default.
        if option == "help":
            default = "\nThis option can only be set by editing the config file."
            if opt.editable:
                default = f"\nBy default this option is set to: {opt.default}"
            return Response(
                f"**Option:** `{opt}`\n{opt.comment}{default}",
                delete_after=60,
            )

        # Save the current config value to the INI file.
        if option == "save":
            if not opt.editable:
                raise exceptions.CommandError(
                    f"Option `{opt}` is not editable. Cannot save to disk.",
                    expire_in=30,
                )

            async with self.aiolocks["config_edit"]:
                saved = self.config.save_option(opt)

            if not saved:
                raise exceptions.CommandError(
                    f"Failed to save the option:  `{opt}`",
                    expire_in=30,
                )
            return Response(
                f"Successfully saved the option:  `{opt}`",
                delete_after=30,
            )

        # Display the current config and INI file values.
        if option == "show":
            if not opt.editable:
                raise exceptions.CommandError(
                    f"Option `{opt}` is not editable, value cannot be displayed.",
                    expire_in=30,
                )
            # TODO: perhaps make use of currently unused display value for empty configs.
            cur_val, ini_val, _disp_val = self.config.register.get_values(opt)
            return Response(
                f"**Option:** `{opt}`\n"
                f"Current Value:  `{cur_val}`\n"
                f"INI File Value:  `{ini_val}`",
                delete_after=30,
            )

        # update a config variable, but don't save it.
        if option == "set":
            if not opt.editable:
                raise exceptions.CommandError(
                    f"Option `{opt}` is not editable. Cannot update setting.",
                    expire_in=30,
                )

            if not value_arg:
                raise exceptions.CommandError(
                    "You must provide a section, option, and value for this sub command.",
                    expire_in=30,
                )

            log.debug("Doing set with on %s == %s", opt, value_arg)
            async with self.aiolocks["config_update"]:
                updated = self.config.update_option(opt, value_arg)
            if not updated:
                raise exceptions.CommandError(
                    f"Option `{opt}` was not updated!",
                    expire_in=30,
                )
            return Response(
                f"Option `{opt}` was updated for this session.\n"
                f"To save the change use `config save {opt.section} {opt.option}`",
                delete_after=30,
            )

        # reset an option to default value as defined in ConfigDefaults
        if option == "reset":
            if not opt.editable:
                raise exceptions.CommandError(
                    f"Option `{opt}` is not editable. Cannot reset to default.",
                    expire_in=30,
                )

            # Use the default value from the option object
            default_value = self.config.register.to_ini(opt, use_default=True)

            # Prepare a user-friendly message for the reset operation
            # TODO look into option registry display code for use here
            reset_value_display = default_value if default_value else "an empty set"

            log.debug("Resetting %s to default %s", opt, default_value)
            async with self.aiolocks["config_update"]:
                updated = self.config.update_option(opt, default_value)
            if not updated:
                raise exceptions.CommandError(
                    f"Option `{opt}` was not reset to default!",
                    expire_in=30,
                )
            return Response(
                f"Option `{opt}` was reset to its default value `{reset_value_display}`.\n"
                f"To save the change use `config save {opt.section} {opt.option}`",
                delete_after=30,
            )

        return None

    @owner_only
    async def cmd_option(
        self, guild: discord.Guild, option: str, value: str
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}option [option] [on/y/enabled/off/n/disabled]

        Changes a config option without restarting the bot. Changes aren't permanent and
        only last until the bot is restarted. To make permanent changes, edit the
        config file or use the config set and save commands.

        Valid options:
            autoplaylist, save_videos, now_playing_mentions, auto_playlist_random, auto_pause,
            delete_messages, delete_invoking, write_current_song, round_robin_queue

        For information about these options, see the option's comment in the config file.
        """
        option = option.lower()
        value = value.lower()
        bool_y = ["on", "y", "enabled"]
        bool_n = ["off", "n", "disabled"]
        generic = [
            "save_videos",
            "now_playing_mentions",
            "auto_playlist_random",
            "auto_pause",
            "delete_messages",
            "delete_invoking",
            "write_current_song",
            "round_robin_queue",
        ]  # these need to match attribute names in the Config class
        if option in ["autoplaylist", "auto_playlist"]:
            if value in bool_y:
                if self.config.auto_playlist:
                    raise exceptions.CommandError(
                        self.str.get(
                            "cmd-option-autoplaylist-enabled",
                            "The autoplaylist is already enabled!",
                        )
                    )

                if not self.server_data[guild.id].autoplaylist:
                    raise exceptions.CommandError(
                        self.str.get(
                            "cmd-option-autoplaylist-none",
                            "There are no entries in the autoplaylist file.",
                        )
                    )

                self.config.auto_playlist = True
            elif value in bool_n:
                if not self.config.auto_playlist:
                    raise exceptions.CommandError(
                        self.str.get(
                            "cmd-option-autoplaylist-disabled",
                            "The autoplaylist is already disabled!",
                        )
                    )

                self.config.auto_playlist = False
            else:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-option-invalid-value", "The value provided was not valid."
                    )
                )
            return Response(
                "The autoplaylist is now "
                + ["disabled", "enabled"][self.config.auto_playlist]
                + "."
            )

        is_generic = [
            o for o in generic if o == option
        ]  # check if it is a generic bool option
        if is_generic and (value in bool_y or value in bool_n):
            name = is_generic[0]
            log.debug("Setting attribute: %s", name)
            setattr(self.config, name, value in bool_y)  # this is scary but should work
            attr = getattr(self.config, name)
            res = f"The option {option} is now " + ["disabled", "enabled"][attr] + "."
            log.warning("Option overriden for this session: %s", res)
            return Response(res)

        raise exceptions.CommandError(
            self.str.get(
                "cmd-option-invalid-param",
                "The parameters provided were invalid.",
            )
        )

    @owner_only
    async def cmd_cache(self, opt: str = "info") -> CommandResponse:
        """
        Usage:
            {command_prefix}cache

        Display cache storage info or clear cache files.
        Valid options are:  info, update, clear
        """
        opt = opt.lower()
        if opt not in ["info", "update", "clear"]:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-cache-invalid-arg",
                    'Invalid option "{0}" specified, use info or clear',
                ).format(opt),
                expire_in=30,
            )

        # actually query the filesystem.
        if opt == "update":
            self.filecache.scan_audio_cache()
            # force output of info after we have updated it.
            opt = "info"

        # report cache info as it is.
        if opt == "info":
            save_videos = ["Disabled", "Enabled"][self.config.save_videos]
            time_limit = f"{self.config.storage_limit_days} days"
            size_limit = format_size_from_bytes(self.config.storage_limit_bytes)
            size_now = ""

            if not self.config.storage_limit_bytes:
                size_limit = "Unlimited"

            if not self.config.storage_limit_days:
                time_limit = "Unlimited"

            cached_bytes, cached_files = self.filecache.get_cache_size()
            size_now = self.str.get(
                "cmd-cache-size-now", "\n\n**Cached Now:**  {0} in {1} file(s)"
            ).format(
                format_size_from_bytes(cached_bytes),
                cached_files,
            )

            return Response(
                self.str.get(
                    "cmd-cache-info",
                    "**Video Cache:** *{0}*\n**Storage Limit:** *{1}*\n**Time Limit:** *{2}*{3}",
                ).format(save_videos, size_limit, time_limit, size_now),
                delete_after=60,
            )

        # clear cache according to settings.
        if opt == "clear":
            if self.filecache.cache_dir_exists():
                if self.filecache.delete_old_audiocache():
                    return Response(
                        self.str.get(
                            "cmd-cache-clear-success",
                            "Cache has been cleared.",
                        ),
                        delete_after=30,
                    )

                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-cache-clear-failed",
                        "**Failed** to delete cache, check logs for more info...",
                    ),
                    expire_in=30,
                )
            return Response(
                self.str.get(
                    "cmd-cache-clear-no-cache",
                    "No cache found to clear.",
                ),
                delete_after=30,
            )
        # TODO: maybe add a "purge" option that fully empties cache regardless of settings.
        return None

    async def cmd_queue(
        self,
        guild: discord.Guild,
        channel: MessageableChannel,
        player: MusicPlayer,
        page: str = "0",
        update_msg: Optional[discord.Message] = None,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}queue [page_number]

        Prints the current song queue.
        Show later entries if available by giving optional page number.
        """

        # handle the page argument.
        page_number = 0
        if page:
            try:
                page_number = abs(int(page))
            except (ValueError, TypeError) as e:
                raise exceptions.CommandError(
                    "Queue page argument must be a whole number.",
                    expire_in=30,
                ) from e

        # check for no entries at all.
        total_entry_count = len(player.playlist.entries)
        if not total_entry_count:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-queue-none",
                    "There are no songs queued! Queue something with {}play.",
                ).format(self.server_data[guild.id].command_prefix)
            )

        # now check if page number is out of bounds.
        limit_per_page = 25  # TODO: make this configurable, up to 25 fields per embed.
        # TODO:  actually just don't use fields, put it all into description field.
        pages_total = math.ceil(total_entry_count / limit_per_page)
        if page_number > pages_total:
            raise exceptions.CommandError(
                "Requested page number is out of bounds.\n"
                f"There are **{pages_total}** pages."
            )

        # Get current entry info if any.
        current_progress = ""
        if player.is_playing and player.current_entry:
            song_progress = format_song_duration(player.progress)
            song_total = (
                format_song_duration(player.current_entry.duration_td)
                if player.current_entry.duration is not None
                else "(no duration data)"
            )
            prog_str = f"`[{song_progress}/{song_total}]`"

            cur_entry_channel = player.current_entry.channel
            cur_entry_author = player.current_entry.author
            if cur_entry_channel and cur_entry_author:
                current_progress = self.str.get(
                    "cmd-queue-playing-author",
                    "Currently playing: `{0}`\nAdded by: `{1}`\nProgress: {2}\n",
                ).format(
                    player.current_entry.title,
                    cur_entry_author.name,
                    prog_str,
                )

            else:
                current_progress = self.str.get(
                    "cmd-queue-playing-noauthor",
                    "Currently playing: `{0}`\nProgress: {1}\n",
                ).format(player.current_entry.title, prog_str)
                # TODO: i18n
                current_progress += "`via autoplaylist`\n"

        # calculate start and stop slice indices
        start_index = limit_per_page * page_number
        end_index = start_index + limit_per_page

        # create an embed
        starting_at = start_index + 1  # add 1 to index for display.
        embed = self._gen_embed()
        embed.title = "Songs in queue"
        embed.description = (
            f"{current_progress}There are `{total_entry_count}` entries in the queue.\n"
            f"Here are the next {limit_per_page} songs, starting at song #{starting_at}"
        )

        # add the tracks to the embed fields
        queue_segment = list(player.playlist.entries)[start_index:end_index]
        for idx, item in enumerate(queue_segment, starting_at):
            if item == player.current_entry:
                # TODO: remove this debug later
                log.debug("Skipped the current playlist entry.")
                continue

            if item.channel and item.author:
                embed.add_field(
                    name=f"Entry #{idx}",
                    value=f"Title: `{item.title}`\nAdded by: `{item.author.name}`",
                    inline=False,
                )
            else:
                embed.add_field(
                    name=f"Entry #{idx}",
                    value=f"Title: `{item.title}`",
                    inline=False,
                )

        # handle sending or editing the queue message.
        if update_msg:
            q_msg = await self.safe_edit_message(update_msg, embed, send_if_fail=True)
        else:
            if pages_total <= 1:
                q_msg = await self.safe_send_message(channel, embed, expire_in=30)
            else:
                q_msg = await self.safe_send_message(channel, embed)

        if pages_total <= 1:
            log.debug("Not enough entries to paginate the queue.")
            return None

        if not q_msg:
            log.warning("Could not post queue message, no message to add reactions to.")
            raise exceptions.CommandError(
                "Try that again. MusicBot couldn't make or get a reference to the queue message.  If the issue persists, file a bug report."
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
                "reaction_add", timeout=60, check=_check_react
            )
            if reaction.emoji == EMOJI_NEXT_ICON:
                await q_msg.clear_reactions()
                await self.cmd_queue(guild, channel, player, str(next_index), q_msg)

            if reaction.emoji == EMOJI_PREV_ICON:
                await q_msg.clear_reactions()
                await self.cmd_queue(guild, channel, player, str(prev_index), q_msg)

            if reaction.emoji == EMOJI_CROSS_MARK_BUTTON:
                await self.safe_delete_message(q_msg)

        except asyncio.TimeoutError:
            await self.safe_delete_message(q_msg)

        return None

    async def cmd_clean(
        self,
        message: discord.Message,
        channel: MessageableChannel,
        guild: discord.Guild,
        author: discord.Member,
        search_range_str: str = "50",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}clean [range]

        Removes up to [range] messages the bot has posted in chat. Default: 50, Max: 1000
        """

        try:
            float(search_range_str)  # lazy check
            search_range = min(int(search_range_str), 100)
        except ValueError:
            return Response(
                self.str.get(
                    "cmd-clean-invalid",
                    "Invalid parameter. Please provide a number of messages to search.",
                ),
                reply=True,
                delete_after=8,
            )

        await self.safe_delete_message(message, quiet=True)

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

        if self.user and self.user.bot:
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
                    self.str.get(
                        "cmd-clean-reply", "Cleaned up {0} message{1}."
                    ).format(len(deleted), "s" * bool(deleted)),
                    delete_after=15,
                )
        return None

    async def cmd_pldump(
        self, channel: MessageableChannel, author: discord.Member, song_subject: str
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}pldump url

        Dumps the individual urls of a playlist
        """

        song_url = self.downloader.get_url_or_none(song_subject)
        if not song_url:
            raise exceptions.CommandError(
                "The given URL was not a valid URL.", expire_in=25
            )

        try:
            info = await self.downloader.extract_info(
                song_url, download=False, process=True
            )
        except Exception as e:
            raise exceptions.CommandError(
                f"Could not extract info from input url\n{str(e)}\n",
                expire_in=25,
            )

        if not info.get("entries", None):
            raise exceptions.CommandError(
                "This does not seem to be a playlist.", expire_in=25
            )

        sent_to_channel = None
        filename = "playlist.txt"
        if info.title:
            safe_title = slugify(info.title)
            filename = f"playlist_{safe_title}.txt"

        # TODO: refactor this in favor of safe_send_message doing it all.
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
            msg_str = f"Here is the playlist dump for:  <{song_url}>"
            datafile = discord.File(fcontent, filename=filename)

            try:
                # try to DM. this could fail for users with strict privacy settings.
                # or users who just can't get direct messages.
                await author.send(msg_str, file=datafile)

            except discord.errors.HTTPException as e:
                if e.code == 50007:  # cannot send to this user.
                    log.debug("DM failed, sending in channel instead.")
                    sent_to_channel = await channel.send(
                        msg_str,
                        file=datafile,
                    )
                else:
                    raise
        if not sent_to_channel:
            return Response("Sent a message with a playlist file.", delete_after=20)
        return None

    async def cmd_listids(
        self,
        guild: discord.Guild,
        author: discord.Member,
        channel: MessageableChannel,
        leftover_args: List[str],
        cat: str = "all",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}listids [categories]

        Lists the ids for various things.  Categories are:
           all, users, roles, channels
        """

        cats = ["channels", "roles", "users"]

        if cat not in cats and cat != "all":
            cats_str = " ".join([f"`{c}`" for c in cats])
            return Response(
                f"Valid categories: {cats_str}",
                reply=True,
                delete_after=25,
            )

        if cat == "all":
            requested_cats = cats
        else:
            requested_cats = [cat] + [c.strip(",") for c in leftover_args]

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

        # TODO: refactor this in favor of safe_send_message doing it all.
        sent_to_channel = None
        with BytesIO() as sdata:
            slug = slugify(guild.name)
            fname = f"{slug}-ids-{cat}.txt"
            sdata.writelines(d.encode("utf8") + b"\n" for d in data)
            sdata.seek(0)
            datafile = discord.File(sdata, filename=fname)
            msg_str = "Here are the IDs you requested:"

            try:
                # try to DM and fall back to channel
                await author.send(msg_str, file=datafile)

            except discord.errors.HTTPException as e:
                if e.code == 50007:  # cannot send to this user.
                    log.debug("DM failed, sending in channel instead.")
                    sent_to_channel = await channel.send(msg_str, file=datafile)
                else:
                    raise
        if not sent_to_channel:
            return Response("Sent a message with a list of IDs.", delete_after=20)
        return None

    async def cmd_perms(
        self,
        author: discord.Member,
        channel: MessageableChannel,
        user_mentions: UserMentions,
        guild: discord.Guild,
        permissions: PermissionGroup,
        target: str = "",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}perms [@user]
        Sends the user a list of their permissions, or the permissions of the user specified.
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
                        "Invalid user ID or server nickname, please double check the ID and try again.",
                        expire_in=30,
                    ) from e
            else:
                user = getuser

        if not user:
            raise exceptions.CommandError(
                "Could not determine the discord User.  Try again.",
                expire_in=30,
            )

        permissions = self.permissions.for_user(user)

        if user == author:
            perms = (
                f"Your command permissions in {guild.name} are:\n"
                f"```{permissions.format(for_user=True)}```"
            )
        else:
            perms = (
                f"The command permissions for {user.name} in {guild.name} are:\n"
                f"```{permissions.format()}```"
            )

        await self.safe_send_message(author, perms, fallback_channel=channel)
        return Response("\N{OPEN MAILBOX WITH RAISED FLAG}", delete_after=20)

    @owner_only
    async def cmd_setperms(
        self,
        user_mentions: UserMentions,
        leftover_args: List[str],
        option: str = "list",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}setperms list
                show loaded groups and list permission options.

            {command_prefix}setperms reload
                reloads permissions from the permissions.ini file.

            {command_prefix}setperms add [GroupName]
                add new group with defaults.

            {command_prefix}setperms remove [GroupName]
                remove existing group.

            {command_prefix}setperms help [PermName]
                show help text for the permission option.

            {command_prefix}setperms show [GroupName] [PermName]
                show permission value for given group and permission.

            {command_prefix}setperms save [GroupName]
                save permissions group to file.

            {command_prefix}setperms set [GroupName] [PermName] [Value]
                set permission value for the group.
        """
        if user_mentions:
            raise exceptions.CommandError(
                "Permissions cannot use channel and user mentions at the same time.",
                expire_in=30,
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
                f"Invalid option for command: `{option}`",
                expire_in=30,
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
                    "Permissions reloaded from file successfully!",
                    delete_after=30,
                )
            except Exception as e:
                raise exceptions.CommandError(
                    f"Unable to reload Permissions due to the following errror:\n{str(e)}",
                    expire_in=30,
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
            opt_list = (
                f"## Available Groups:\n{groups}\n"
                f"## Available Options:\n"
                f"{editable_opts}\n"
            )
            return Response(
                opt_list,
                delete_after=60,
            )

        # sub commands beyond here need 2 leftover_args
        if option in ["help", "show", "save", "add", "remove"]:
            if len(leftover_args) < 1:
                raise exceptions.CommandError(
                    "You must provide a group or option name for this command.",
                    expire_in=30,
                )
        if option == "set" and len(leftover_args) < 3:
            raise exceptions.CommandError(
                "You must provide a group, option, and value to set for this command.",
                expire_in=30,
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
                    f"The {option} sub-command requires a group and permission name.",
                    expire_in=30,
                )
            option_arg = leftover_args.pop(0)

        if user_mentions:
            leftover_args += [str(m.id) for m in user_mentions]
        value_arg = " ".join(leftover_args)

        if group_arg not in self.permissions.register.sections and option != "add":
            sects = ", ".join(self.permissions.register.sections)
            raise exceptions.CommandError(
                f"The group `{group_arg}` is not available.\n"
                f"The available groups are:  {sects}",
                expire_in=30,
            )

        # Make sure the option is set if the sub-command needs it.
        if option in ["help", "set", "show"]:
            p_opt = self.permissions.register.get_config_option(group_arg, option_arg)
            if p_opt is None:
                option_arg = f"[{group_arg}] > {option_arg}"
                raise exceptions.CommandError(
                    f"The permission `{option_arg}` is not available.",
                    expire_in=30,
                )
            opt = p_opt

        # Display some commentary about the option and its default.
        if option == "help":
            default = (
                "\nThis permission can only be set by editing the permissions file."
            )
            # TODO:  perhaps use empty display values here.
            if opt.editable:
                dval = self.permissions.register.to_ini(opt, use_default=True)
                default = f"\nBy default this permission is set to: `{dval}`"
            return Response(
                f"**Permission:** `{opt.option}`\n{opt.comment}{default}",
                delete_after=60,
            )

        if option == "add":
            if group_arg in self.permissions.register.sections:
                raise exceptions.CommandError(
                    f"Cannot add group `{group_arg}` it already exists.",
                    expire_in=30,
                )
            async with self.aiolocks["permission_edit"]:
                self.permissions.add_group(group_arg)

            return Response(
                f"Successfully added new group:  `{group_arg}`\n"
                f"You can now customizse the permissions with:  `setperms set {group_arg}`\n"
                f"Make sure to save the new group with:  `setperms save {group_arg}`",
                delete_after=30,
            )

        if option == "remove":
            if group_arg in [DEFAULT_OWNER_GROUP_NAME, DEFAULT_PERMS_GROUP_NAME]:
                raise exceptions.CommandError(
                    "Cannot remove built-in group.", expire_in=30
                )

            async with self.aiolocks["permission_edit"]:
                self.permissions.remove_group(group_arg)

            return Response(
                f"Successfully removed group:  `{group_arg}`"
                f"Make sure to save this change with:  `setperms save {group_arg}`",
                delete_after=30,
            )

        # Save the current config value to the INI file.
        if option == "save":
            if group_arg == DEFAULT_OWNER_GROUP_NAME:
                raise exceptions.CommandError(
                    "The owner group is not editable.",
                    expire_in=30,
                )

            async with self.aiolocks["permission_edit"]:
                saved = self.permissions.save_group(group_arg)

            if not saved:
                raise exceptions.CommandError(
                    f"Failed to save the group:  `{group_arg}`",
                    expire_in=30,
                )
            return Response(
                f"Successfully saved the group:  `{group_arg}`",
                delete_after=30,
            )

        # Display the current permissions group and INI file values.
        if option == "show":
            cur_val, ini_val, empty_display_val = self.permissions.register.get_values(
                opt
            )
            return Response(
                f"**Permission:** `{opt}`\n"
                f"Current Value:  `{cur_val}` {empty_display_val}\n"
                f"INI File Value:  `{ini_val}`",
                delete_after=30,
            )

        # update a permission, but don't save it.
        if option == "set":
            if group_arg == DEFAULT_OWNER_GROUP_NAME:
                raise exceptions.CommandError(
                    "The owner group is not editable.",
                    expire_in=30,
                )

            if not value_arg:
                raise exceptions.CommandError(
                    "You must provide a section, option, and value for this sub command.",
                    expire_in=30,
                )

            log.debug("Doing set with on %s == %s", opt, value_arg)
            async with self.aiolocks["permission_update"]:
                updated = self.permissions.update_option(opt, value_arg)
            if not updated:
                raise exceptions.CommandError(
                    f"Permission `{opt}` was not updated!",
                    expire_in=30,
                )
            return Response(
                f"Permission `{opt}` was updated for this session.\n"
                f"To save the change use `setperms save {opt.section} {opt.option}`",
                delete_after=30,
            )

        return None

    @owner_only
    async def cmd_setname(self, leftover_args: List[str], name: str) -> CommandResponse:
        """
        Usage:
            {command_prefix}setname name

        Changes the bot's username.
        Note: This operation is limited by discord to twice per hour.
        """

        name = " ".join([name, *leftover_args])

        try:
            if self.user:
                await self.user.edit(username=name)

        except discord.HTTPException as e:
            raise exceptions.CommandError(
                "Failed to change name. Did you change names too many times?  "
                "Remember name changes are limited to twice per hour."
            ) from e

        except Exception as e:
            raise exceptions.CommandError(str(e), expire_in=20) from e

        return Response(f"Set the bot's username to **{name}**", delete_after=20)

    async def cmd_setnick(
        self,
        guild: discord.Guild,
        channel: MessageableChannel,
        leftover_args: List[str],
        nick: str,
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}setnick nick

        Changes the bot's nickname.
        """

        if not channel.permissions_for(guild.me).change_nickname:
            raise exceptions.CommandError("Unable to change nickname: no permission.")

        nick = " ".join([nick, *leftover_args])

        try:
            await guild.me.edit(nick=nick)
        except Exception as e:
            raise exceptions.CommandError(str(e), expire_in=20)

        return Response(f"Set the bot's nickname to `{nick}`", delete_after=20)

    async def cmd_setprefix(self, guild: discord.Guild, prefix: str) -> CommandResponse:
        """
        Usage:
            {command_prefix}setprefix prefix

        If enabled by owner, set an override for command prefix with a custom prefix.
        """
        if self.config.enable_options_per_guild:
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
                        self.str.get(
                            "cmd-setprefix-emoji-unavailable",
                            "Custom emoji must be from this server to use as a prefix.",
                        ),
                        expire_in=30,
                    )

            if "clear" == prefix:
                self.server_data[guild.id].command_prefix = ""
                await self.server_data[guild.id].save_guild_options_file()
                return Response(
                    self.str.get(
                        "cmd-setprefix-cleared",
                        "Server command prefix is cleared.",
                    )
                )

            self.server_data[guild.id].command_prefix = prefix
            await self.server_data[guild.id].save_guild_options_file()
            return Response(
                self.str.get(
                    "cmd-setprefix-changed",
                    "Server command prefix is now:  {0}",
                ).format(prefix),
                delete_after=60,
            )

        raise exceptions.CommandError(
            self.str.get(
                "cmd-setprefix-disabled",
                "Prefix per server is not enabled!",
            ),
            expire_in=30,
        )

    @owner_only
    async def cmd_setavatar(
        self, message: discord.Message, av_url: str = ""
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}setavatar [url]

        Changes the bot's avatar.
        Attaching a file and leaving the url parameter blank also works.
        """

        url = self.downloader.get_url_or_none(av_url)
        if message.attachments:
            thing = message.attachments[0].url
        elif url:
            thing = url
        else:
            raise exceptions.CommandError(
                "You must provide a URL or attach a file.", expire_in=20
            )

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            if self.user and self.session:
                async with self.session.get(thing, timeout=timeout) as res:
                    await self.user.edit(avatar=await res.read())

        except Exception as e:
            raise exceptions.CommandError(
                f"Unable to change avatar: {str(e)}", expire_in=20
            ) from e

        return Response("Changed the bot's avatar.", delete_after=20)

    async def cmd_disconnect(self, guild: discord.Guild) -> CommandResponse:
        """
        Usage:
            {command_prefix}disconnect

        Forces the bot leave the current voice channel.
        """
        voice_client = self.get_player_in(guild)
        if voice_client:
            await self.disconnect_voice_client(guild)
            return Response(
                self.str.get(
                    "cmd-disconnect-success", "Disconnected from `{0.name}`"
                ).format(guild),
                delete_after=20,
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
                    "Disconnected a playerless voice client? [BUG]",
                    delete_after=30,
                )

        raise exceptions.CommandError(
            self.str.get(
                "cmd-disconnect-no-voice", "Not currently connected to `{0.name}`"
            ).format(guild),
            expire_in=30,
        )

    async def cmd_restart(
        self,
        _player: Optional[MusicPlayer],
        channel: MessageableChannel,
        opt: str = "soft",
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}restart [soft|full|upgrade|upgit|uppip]

        Restarts the bot, uses soft restart by default.
        `soft` reloads config without reloading bot code.
        `full` restart reloading source code and configs.
        `uppip` upgrade pip packages then fully restarts.
        `upgit` upgrade bot with git then fully restarts.
        `upgrade` upgrade bot and packages then restarts.
        """
        opt = opt.strip().lower()
        if opt not in ["soft", "full", "upgrade", "uppip", "upgit"]:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-restart-invalid-arg",
                    "Invalid option given, use: soft, full, upgrade, uppip, or upgit.",
                ),
                expire_in=30,
            )

        if opt == "soft":
            await self.safe_send_message(
                channel,
                self.str.get(
                    "cmd-restart-soft",
                    "{emoji} Restarting current instance...",
                ).format(
                    emoji="\u21A9\uFE0F",  # Right arrow curving left
                ),
            )
        elif opt == "full":
            await self.safe_send_message(
                channel,
                self.str.get(
                    "cmd-restart-full",
                    "{emoji} Restarting bot process...",
                ).format(
                    emoji="\U0001F504",  # counterclockwise arrows
                ),
            )
        elif opt == "uppip":
            await self.safe_send_message(
                channel,
                self.str.get(
                    "cmd-restart-uppip",
                    "{emoji} Will try to upgrade required pip packages and restart the bot...",
                ).format(
                    emoji="\U0001F4E6",  # package / box
                ),
            )
        elif opt == "upgit":
            await self.safe_send_message(
                channel,
                self.str.get(
                    "cmd-restart-upgit",
                    "{emoji} Will try to update bot code with git and restart the bot...",
                ).format(
                    emoji="\U0001F5C3\uFE0F",  # card box
                ),
            )
        elif opt == "upgrade":
            await self.safe_send_message(
                channel,
                self.str.get(
                    "cmd-restart-upgrade",
                    "{emoji} Will try to upgrade everything and restart the bot...",
                ).format(
                    emoji="\U0001F310",  # globe with meridians
                ),
            )

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

    async def cmd_shutdown(
        self, guild: discord.Guild, channel: MessageableChannel
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}shutdown

        Disconnects from voice channels and closes the bot process.
        """
        await self.safe_send_message(channel, "\N{WAVING HAND SIGN}")

        player = self.get_player_in(guild)
        if player and player.is_paused:
            player.resume()

        await self.disconnect_all_voice_clients()
        raise exceptions.TerminateSignal()

    async def cmd_leaveserver(
        self, val: str, leftover_args: List[str]
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}leaveserver <name/ID>

        Forces the bot to leave a server.
        When providing names, names are case-sensitive.
        """
        guild_id = 0
        guild_name = ""
        if leftover_args:
            guild_name = " ".join([val, *leftover_args])

        try:
            guild_id = int(val)
        except ValueError as e:
            if not guild_name:
                # TODO: i18n / UI stuff
                raise exceptions.CommandError("You must provide an ID or name.") from e

        if guild_id:
            leave_guild = self.get_guild(guild_id)

        if leave_guild is None:
            # Get guild by name
            leave_guild = discord.utils.get(self.guilds, name=guild_name)

        if leave_guild is None:
            raise exceptions.CommandError(
                f"No guild was found with the ID or name as `{val}`"
            )

        await leave_guild.leave()

        guild_name = leave_guild.name
        guild_owner = leave_guild.owner.name if leave_guild.owner else "Unknown"
        guild_id = leave_guild.id
        # TODO: this response doesn't make sense if the command is issued
        # from within the server being left.
        return Response(
            # TODO: i18n / UI stuff
            f"Left the guild: `{guild_name}` (Owner: `{guild_owner}`, ID: `{guild_id}`)"
        )

    @dev_only
    async def cmd_breakpoint(self) -> CommandResponse:
        """
        Do nothing but print a critical level error to the log.
        """
        log.critical("Activating debug breakpoint")
        return None

    @dev_only
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
        Usage:
            {command_prefix}debug [one line of code]
                OR
            {command_prefix}debug ` ` `py
            many lines
            of python code.
            ` ` `

            This command will execute python code in the commands scope.
            First eval() is attempted, if exceptions are thrown exec() is tried.
            If eval is successful, its return value is displayed.
            If exec is successful, a value can be set to local variable `result`
            and that value will be returned.
        """
        codeblock = "```py\n{}\n```"
        result = None

        if data.startswith("```") and data.endswith("```"):
            data = "\n".join(data.rstrip("`\n").split("\n")[1:])

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
                    f"Failed to execute debug code.\n{codeblock.format(code)}\n"
                    f"Exception: ```\n{type(e).__name__}:\n{str(e)}```"
                ) from e

        if asyncio.iscoroutine(result):
            result = await result

        return Response(f"**{run_type}() Result:**\n{codeblock.format(result)}")

    @dev_only
    async def cmd_makemarkdown(
        self,
        channel: MessageableChannel,
        author: discord.Member,
        cfg: str = "opts",
    ) -> CommandResponse:
        """
        Command to generate markdown for options and permissions files.
        Contents are generated from code and not pulled from the files!
        """
        valid_opts = ["opts", "perms"]
        if cfg not in valid_opts:
            opts = ", ".join([f"`{o}`" for o in valid_opts])
            raise exceptions.CommandError(f"Option must be one of: {opts}")

        filename = "config_options.md"
        msg_str = "Config options described in Markdown:\n"
        if cfg == "perms":
            filename = "config_permissions.md"
            msg_str = "Permissions described in Markdown:\n"
            config_md = self.permissions.register.export_markdown()
        else:
            config_md = self.config.register.export_markdown()

        sent_to_channel = None

        # TODO: refactor this in favor of safe_send_message doing it all.
        with BytesIO() as fcontent:
            fcontent.write(config_md.encode("utf8"))
            fcontent.seek(0)
            datafile = discord.File(fcontent, filename=filename)

            try:
                # try to DM. this could fail for users with strict privacy settings.
                # or users who just can't get direct messages.
                await author.send(msg_str, file=datafile)

            except discord.errors.HTTPException as e:
                if e.code == 50007:  # cannot send to this user.
                    log.debug("DM failed, sending in channel instead.")
                    sent_to_channel = await channel.send(
                        msg_str,
                        file=datafile,
                    )
                else:
                    raise
        if not sent_to_channel:
            return Response(
                "Sent a message with the requested config markdown.", delete_after=20
            )
        return None

    @owner_only
    async def cmd_checkupdates(self, channel: MessageableChannel) -> CommandResponse:
        """
        Usage:
            {command_prefix}checkupdates

        Display the current bot version and check for updates to MusicBot or dependencies.
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
                raise RuntimeError("Could not locate git executable.")

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
                git_status = f"No updates in branch `{branch_name}` remote."
            else:
                git_status = (
                    f"New commits are available in `{branch_name}` branch remote."
                )
                updates = True
        except (OSError, ValueError, ConnectionError, RuntimeError):
            log.exception("Failed while checking for updates via git command.")
            git_status = "Error while checking, see logs for details."

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
                    pip_packages += f"Update for `{name}` to version: `{ver}`\n"
            if pip_packages:
                pip_status = pip_packages
                updates = True
            else:
                pip_status = "No updates for dependencies found."
        except (OSError, ValueError, ConnectionError):
            log.exception("Failed to get pip update status due to some error.")
            pip_status = "Error while checking, see logs for details."

        if updates:
            header = "There are updates for MusicBot available for download."
        else:
            header = "MusicBot is totally up-to-date!"

        return Response(
            f"{header}\n\n"
            f"**Source Code Updates:**\n{git_status}\n\n"
            f"**Dependency Updates:**\n{pip_status}",
            delete_after=60,
        )

    async def cmd_uptime(self) -> CommandResponse:
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
            f"{name} has been up for `{delta}`",
            delete_after=30,
        )

    @owner_only
    async def cmd_botlatency(self) -> CommandResponse:
        """
        Usage:
            {command_prefix}botlatency

        Prints latency info for all voice clients.
        """
        vclats = ""
        for vc in self.voice_clients:
            if not isinstance(vc, discord.VoiceClient) or not hasattr(
                vc.channel, "rtc_region"
            ):
                log.debug("Got a strange voice client entry.")
                continue

            vl = vc.latency * 1000
            vla = vc.average_latency * 1000
            # Display Auto for region instead of None
            region = vc.channel.rtc_region or "auto"
            vclats += f"- `{vl:.0f} ms` (`{vla:.0f} ms` Avg.) in region: `{region}`\n"

        if not vclats:
            vclats = "No voice clients connected.\n"

        sl = self.latency * 1000
        return Response(
            f"**API Latency:** `{sl:.0f} ms`\n**VoiceClient Latency:**\n{vclats}",
            delete_after=30,
        )

    async def cmd_latency(self, guild: discord.Guild) -> CommandResponse:
        """
        Usage:
            {command_prefix}latency

        Prints the latency info available to MusicBot.
        If connected to a voice channel, voice latency is also returned.
        """

        voice_lat = ""
        if guild.id in self.players:
            vc = self.players[guild.id].voice_client
            if vc:
                vl = vc.latency * 1000
                vla = vc.average_latency * 1000
                voice_lat = f"\n**Voice Latency:** `{vl:.0f} ms` (`{vla:.0f} ms` Avg.)"
        sl = self.latency * 1000
        return Response(
            f"**API Latency:** `{sl:.0f} ms`{voice_lat}",
            delete_after=30,
        )

    async def cmd_botversion(self) -> CommandResponse:
        """
        Usage:
            {command_prefix}botversion

        Prints the current bot version to chat.
        """
        return Response(
            "https://github.com/Just-Some-Bots/MusicBot\n"
            f"Current version:  `{BOTVERSION}`",
            delete_after=30,
        )

    @owner_only
    async def cmd_setcookies(
        self, message: discord.Message, opt: str = ""
    ) -> CommandResponse:
        """
        Usage:
            {command_prefix}setcookies [ off | on ]
                Disable or enable cookies.txt file without deleting it.

            {command_prefix}setcookies
                Update the cookies.txt file using a supplied attachment.

        Note:
          When updating cookies, you must upload a file named cookies.txt
          If cookies are disabled, uploading will enable the feature.
          Uploads will delete existing cookies, including disabled cookies file.

        WARNING:
          Copying cookies can risk exposing your personal information or accounts,
          and may result in account bans or theft if you are not careful.
          It is not recommended due to these risks, and you should not use this
          feature if you do not understand how to avoid the risks.
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
                        f"Could not enable cookies due to error:  {str(e)}"
                    ) from e
            return Response("Cookies have been enabled.")

        if opt == "off":
            if self.downloader.cookies_enabled:
                self.downloader.disable_ytdl_cookies()

            if self.config.cookies_path.is_file():
                try:
                    self.config.cookies_path.rename(self.config.disabled_cookies_path)
                except OSError as e:
                    raise exceptions.CommandError(
                        f"Could not rename cookies file due to error:  {str(e)}\n"
                        "Cookies temporarily disabled and will be re-enabled on next restart."
                    ) from e
            return Response("Cookies have been disabled.")

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
                log.warning("Could not remove old, disabled cookies file:  %s", str(e))

        # simply save the uploaded file in attachment 1 as cookies.txt.
        try:
            await message.attachments[0].save(self.config.cookies_path)
        except discord.HTTPException as e:
            raise exceptions.CommandError(
                f"Error downloading the cookies file from discord:  {str(e)}"
            ) from e
        except OSError as e:
            raise exceptions.CommandError(
                f"Could not save cookies to disk:  {str(e)}"
            ) from e

        # enable cookies if it is not already.
        if not self.downloader.cookies_enabled:
            self.downloader.enable_ytdl_cookies()

        return Response("Cookies uploaded and enabled.")

    async def on_message(self, message: discord.Message) -> None:
        """
        Event called by discord.py when any message is sent to/around the bot.
        https://discordpy.readthedocs.io/en/stable/api.html#discord.on_message
        """
        await self.wait_until_ready()

        if not message.channel:
            log.debug("Got a message with no channel, somehow:  %s", message)
            return

        self_mention = "<@MusicBot>"  # placeholder
        if self.user:
            self_mention = f"<@{self.user.id}>"

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

        if not message_content.startswith(command_prefix) and (
            self.config.commands_via_mention
            and not message_content.startswith(self_mention)
        ):
            return

        if message.author == self.user:
            log.warning("Ignoring command from myself (%s)", message.content)
            return

        if (
            message.author.bot
            and message.author.id not in self.config.bot_exception_ids
        ):
            log.warning("Ignoring command from other bot (%s)", message.content)
            return

        if (not isinstance(message.channel, discord.abc.GuildChannel)) and (
            not isinstance(message.channel, discord.abc.PrivateChannel)
        ):
            log.warning(
                "Ignoring command from channel of type:  %s", type(message.channel)
            )
            return

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

        # [] produce [''] which is not what we want (it break things)
        if args:
            args = " ".join(args).lstrip(" ").split(" ")
        else:
            args = []

        # Check if the incomming command is a "natural" command.
        handler = getattr(self, "cmd_" + command, None)
        if not handler:
            # If no natural command was found, check for aliases when enabled.
            if self.config.usealias:
                # log.debug("Checking for alias with: %s", command)
                command, alias_arg_str = self.aliases.get(command)
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

        if isinstance(message.channel, discord.abc.PrivateChannel):
            if not (
                message.author.id == self.config.owner_id and command == "joinserver"
            ):
                await self.safe_send_message(
                    message.channel, "You cannot use this bot in private messages."
                )
                return

        if (
            self.config.bound_channels
            and message.guild
            and message.channel.id not in self.config.bound_channels
        ):
            if self.config.unbound_servers:
                for channel in message.guild.channels:
                    if channel.id in self.config.bound_channels:
                        return
            else:
                return  # if I want to log this I just move it under the prefix check

        # check for user id or name in blacklist.
        if (
            self.config.user_blocklist.is_blocked(message.author)
            and message.author.id != self.config.owner_id
        ):
            log.warning(
                "User in block list: %s/%s  tried command: %s",
                message.author.id,
                str(message.author),
                command,
            )
            return

        log.info(
            "Message from %s/%s: %s",
            message.author.id,
            str(message.author),
            message_content.replace("\n", "\n... "),
        )

        user_permissions = self.permissions.for_user(message.author)

        argspec = inspect.signature(handler)
        params = argspec.parameters.copy()

        sentmsg = response = None

        try:
            if (
                user_permissions.ignore_non_voice
                and command in user_permissions.ignore_non_voice
            ):
                await self._check_ignore_non_voice(message)

            # populate the existing command signature args.
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
                        message.author.voice.channel
                    )
                else:
                    # TODO: enable ignore-non-voice commands to work here
                    # by looking for the first available VC if author has none.
                    raise exceptions.CommandError(
                        "This command requires you to be in a Guild Voice channel."
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

            if params.pop("leftover_args", None):
                handler_kwargs["leftover_args"] = args

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
                    handler_kwargs[key] = " ".join(args)
                    params.pop(key)
                    continue

                doc_key = (
                    f"[{key}={param.default}]"
                    if param.default is not param.empty
                    else key
                )
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

            # Test non-owners for command permissions.
            if message.author.id != self.config.owner_id:
                user_permissions.can_use_command(command)

            # Invalid usage, return docstring
            if params:
                docs = getattr(handler, "__doc__", None)
                if not docs:
                    doc_args = " ".join(args_expected)
                    docs = f"Usage: {command_prefix}{command} {doc_args}"

                docs = dedent(docs).format(command_prefix=command_prefix)
                await self.safe_send_message(
                    message.channel,
                    f"```\n{docs}\n```",
                    expire_in=60,
                )
                return

            response = await handler(**handler_kwargs)
            if response and isinstance(response, Response):
                if (
                    not isinstance(response.content, discord.Embed)
                    and self.config.embeds
                ):
                    content = self._gen_embed()
                    content.title = command
                    content.description = response.content

                    if response.reply:
                        content.description = (
                            f"{message.author.mention} {content.description}"
                        )
                    sentmsg = await self.safe_send_message(
                        message.channel,
                        content,
                        expire_in=(
                            response.delete_after if self.config.delete_messages else 0
                        ),
                        also_delete=message if self.config.delete_invoking else None,
                    )

                else:
                    contents = response.content
                    if response.reply:
                        contents = f"{message.author.mention}: {contents}"

                    sentmsg = await self.safe_send_message(
                        message.channel,
                        contents,
                        expire_in=(
                            response.delete_after if self.config.delete_messages else 0
                        ),
                        also_delete=message if self.config.delete_invoking else None,
                    )

        except (
            exceptions.CommandError,
            exceptions.HelpfulError,
            exceptions.ExtractionError,
        ) as e:
            log.error(
                "Error in %s: %s: %s",
                command,
                e.__class__.__name__,
                e.message,
                exc_info=True,
            )

            expirein = e.expire_in if self.config.delete_messages else 0
            alsodelete = message if self.config.delete_invoking else None

            if self.config.embeds:
                content = self._gen_embed()
                content.add_field(name="Error", value=e.message, inline=False)
                content.colour = discord.Colour(13369344)

                await self.safe_send_message(
                    message.channel, content, expire_in=expirein, also_delete=alsodelete
                )

            else:
                contents = f"```\n{e.message}\n```"

                await self.safe_send_message(
                    message.channel,
                    contents,
                    expire_in=expirein,
                    also_delete=alsodelete,
                )

        except exceptions.Signal:
            raise

        except Exception:  # pylint: disable=broad-exception-caught
            log.error("Exception in on_message", exc_info=True)
            if self.config.debug_mode:
                tb_str = traceback.format_exc()
                await self.safe_send_message(message.channel, f"```\n{tb_str}\n```")

        finally:
            if not sentmsg and not response and self.config.delete_invoking:
                await asyncio.sleep(5)
                await self.safe_delete_message(message, quiet=True)

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
            last_np_msg = self.server_data[guild.id].last_np_msg
            if last_np_msg is not None and last_np_msg.channel:
                channel = last_np_msg.channel
                if self.config.embeds:
                    embed = self._gen_embed()
                    embed.title = "Leaving voice channel"
                    embed.description = (
                        f"Leaving voice channel {voice_channel.name} due to inactivity."
                    )
                    await self.safe_send_message(channel, embed, expire_in=30)
                else:
                    await self.safe_send_message(
                        channel,
                        f"Leaving voice channel {voice_channel.name} in due to inactivity.",
                        expire_in=30,
                    )

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

        # Voice stat updates for bot itself.
        if member == self.user:
            # check if bot was disconnected from a voice channel
            if not after.channel and before.channel and not self.network_outage:
                if await self._handle_api_disconnect(before):
                    return

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
                log.debug("Following user `%s` to channel:  %s", member, after.channel)
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

        # handle cases where the bot was moved into a stage channel
        if (
            before.channel
            and after.channel
            and isinstance(after.channel, discord.StageChannel)
        ):
            if after.channel != before.channel:
                await self._handle_stage_channels(after.channel)
            # handles bot moved to audience
            elif after.suppress and not before.suppress:
                log.info(f"Bot was moved  to the audience in {after.channel}.")
                if player.is_playing:
                    player.pause()
                    log.info("Player is pausing.")
                return
            # handles bot invited to speak
            elif not after.suppress and before.suppress:
                log.info(f"Bot was made speaker in {after.channel}.")
                if player.is_paused:
                    player.resume()
                    log.info("Player is resuming.")
                return

    async def _handle_stage_channels(self, channel: discord.StageChannel) -> None:
        """
        Handles actions related to a StageChannel, such as unmuting the bot
        and requesting permission to speak if necessary.

        :param channel:
            The StageChannel to handle.

        :raises: musicbot.exceptions.PermissionsError
            If MusicBot does not have permissions required to unmute or request to speak.
        """

        lock_key = f"stage_channel:{channel.id}"
        async with self.aiolocks[lock_key]:
            try:
                await channel.guild.me.edit(suppress=False)
                log.info(f"Connected to {channel} and unmuted successfully.")
                return
            except (discord.Forbidden, discord.HTTPException) as e:
                if isinstance(e, discord.Forbidden):
                    log.info(
                        "Missing permissions to unmute. Attempting to request to speak."
                    )
                    raise exceptions.PermissionsError(
                        "Missing permissions to unmute. Will try to request to speak."
                    )
                else:
                    log.debug(f"HTTP exception occured: {e}")

                try:
                    await channel.guild.me.request_to_speak()
                    log.info(f"Requested permission to speak in {channel}.")
                    return
                except discord.Forbidden:
                    log.exception(
                        "Failed to request to speak. Waiting for permission to play audio."
                    )
                    raise exceptions.PermissionsError(
                        "Unable to request to speak, missing permissions"
                    )
                except discord.HTTPException as e:
                    log.debug(f"HTTP exception occured: {e}")

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
                "Disconnected from voice by Discord API in: %s/%s (Code: %s) [S:%s]",
                o_guild.name,
                before.channel.name,
                close_code,
                state.name.upper() if state else None,
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
                        "Cannot use auto-join channel with type: %s  in guild:  %s",
                        type(target_channel),
                        before.channel.guild,
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
                    await owner.send(
                        self.str.get(
                            "left-no-owner-guilds",
                            "Left `{}` due to bot owner not being found in it.",
                        ).format(guild.name)
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
                        f"Guild attribute {name} is now: {a_val}  -- Was: {b_val}"
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
            if before.user_limit != after.user_limit:
                changes += f" user-limit = {after.user_limit}"
        # The chat delay is not currently respected by MusicBot. Is this a problem?
        if before.slowmode_delay != after.slowmode_delay:
            changes += f" slowmode = {after.slowmode_delay}"

        if changes:
            log.info("Channel update for:  %s  --  %s", before, changes)
