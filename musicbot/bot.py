import asyncio
import certifi
import inspect
import json
import logging
import math
import os
import pathlib
import random
import re
import shlex
import ssl
import sys
import time
import traceback
from collections import defaultdict
from datetime import timedelta
from functools import wraps
from io import BytesIO, StringIO
from textwrap import dedent
from typing import Optional

import aiohttp
import colorlog
import discord

from . import downloader
from . import exceptions
from .aliases import Aliases, AliasesDefault
from .config import Config, ConfigDefaults
from .constants import (
    DISCORD_MSG_CHAR_LIMIT,
    EMOJI_CHECK_MARK_BUTTON,
    EMOJI_CROSS_MARK_BUTTON,
    EMOJI_IDLE_ICON,
)
from .constants import VERSION as BOTVERSION
from .constructs import SkipState, Response
from .entry import StreamPlaylistEntry
from .filecache import AudioFileCache
from .json import Json
from .opus_loader import load_opus_lib
from .permissions import Permissions, PermissionsDefaults
from .player import MusicPlayer
from .playlist import Playlist
from .spotify import Spotify
from .utils import (
    load_file,
    write_file,
    slugify,
    fixg,
    ftimedelta,
    _func_,
    _get_variable,
    is_empty_voice_channel,
    format_song_duration,
    format_size_from_bytes,
)

log = logging.getLogger(__name__)

# TODO: fix listids command to send in channel if DM fails.
# TODO: fix perms command to send in channel if DM fails.


class MusicBot(discord.Client):
    def __init__(self, config_file=None, perms_file=None, aliases_file=None):
        load_opus_lib()
        try:
            sys.stdout.write("\x1b]2;MusicBot {}\x07".format(BOTVERSION))
        except Exception:
            pass

        print()

        if config_file is None:
            config_file = ConfigDefaults.options_file

        if perms_file is None:
            perms_file = PermissionsDefaults.perms_file

        if aliases_file is None:
            aliases_file = AliasesDefault.aliases_file

        self.players = {}
        self.exit_signal = None
        self.init_ok = False
        self.cached_app_info = None
        self.last_status = None

        self.config = Config(config_file)

        self._setup_logging()

        self.permissions = Permissions(perms_file, grant_all=[self.config.owner_id])
        self.str = Json(self.config.i18n_file)

        if self.config.usealias:
            self.aliases = Aliases(aliases_file)

        self.blacklist = set(load_file(self.config.blacklist_file))
        self.autoplaylist = load_file(self.config.auto_playlist_file)

        self.aiolocks = defaultdict(asyncio.Lock)
        self.filecache = AudioFileCache(self)
        self.downloader = downloader.Downloader(self)

        log.info("Starting MusicBot {}".format(BOTVERSION))

        if not self.autoplaylist:
            log.warning("Autoplaylist is empty, disabling.")
            self.config.auto_playlist = False
        else:
            log.info(
                "Loaded autoplaylist with {} entries".format(len(self.autoplaylist))
            )
            self.filecache.load_autoplay_cachemap()

        if self.blacklist:
            log.debug("Loaded blacklist with {} entries".format(len(self.blacklist)))

        # TODO: Do these properly
        ssd_defaults = {
            "command_prefix": None,
            "session_prefix_history": set(),  # only populated by changing prefixes.
            "last_np_msg": None,
            "availability_paused": False,
            "auto_paused": False,
            "inactive_player_timer": (
                asyncio.Event(),
                False,  # event state tracking.
            ),
            "inactive_vc_timer": (
                asyncio.Event(),
                False,
            ),  # The boolean is going show if the timeout is active or not
        }
        self.server_specific_data = defaultdict(ssd_defaults.copy)

        intents = discord.Intents.all()
        intents.typing = False
        intents.presences = False
        super().__init__(intents=intents)

    async def _doBotInit(self, use_certifi: bool = False):
        self.http.user_agent = "MusicBot/%s" % BOTVERSION
        if use_certifi:
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

        self.spotify: Spotify
        if self.config._spotify:
            try:
                self.spotify = Spotify(
                    self.config.spotify_clientid,
                    self.config.spotify_clientsecret,
                    aiosession=self.session,
                    loop=self.loop,
                )
                if not await self.spotify.has_token():
                    log.warning("Spotify did not provide us with a token. Disabling.")
                    self.config._spotify = False
                else:
                    log.info(
                        "Authenticated with Spotify successfully using client ID and secret."
                    )
            except exceptions.SpotifyError as e:
                log.warning(
                    "There was a problem initialising the connection to Spotify. Is your client ID and secret correct? Details: {0}. Continuing anyway in 5 seconds...".format(
                        e
                    )
                )
                self.config._spotify = False
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
                    self.config._spotify = False
                else:
                    log.info(
                        "Authenticated with Spotify successfully using guest mode."
                    )
                    self.config._spotify = True
            except exceptions.SpotifyError as e:
                log.warning(
                    "There was a problem initialising the connection to Spotify using guest mode. Details: {0}.".format(
                        e
                    )
                )
                self.config._spotify = False

    # TODO: Add some sort of `denied` argument for a message to send when someone else tries to use it
    def owner_only(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Only allow the owner to use these commands
            orig_msg = _get_variable("message")

            if not orig_msg or orig_msg.author.id == self.config.owner_id:
                # noinspection PyCallingNonCallable
                return await func(self, *args, **kwargs)
            else:
                raise exceptions.PermissionsError(
                    "Only the owner can use this command.", expire_in=30
                )

        return wrapper

    def dev_only(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            orig_msg = _get_variable("message")

            if str(orig_msg.author.id) in self.config.dev_ids:
                # noinspection PyCallingNonCallable
                return await func(self, *args, **kwargs)
            else:
                raise exceptions.PermissionsError(
                    "Only dev users can use this command.", expire_in=30
                )

        wrapper.dev_cmd = True
        return wrapper

    def ensure_appinfo(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            await self._cache_app_info()
            # noinspection PyCallingNonCallable
            return await func(self, *args, **kwargs)

        return wrapper

    def _get_owner(self, *, server=None, voice=False):
        return discord.utils.find(
            lambda m: m.id == self.config.owner_id and (m.voice if voice else True),
            server.members if server else self.get_all_members(),
        )

    def _setup_logging(self):
        if len(logging.getLogger(__package__).handlers) > 1:
            log.debug("Skipping logger setup, already set up")
            return

        shandler = logging.StreamHandler(stream=sys.stdout)
        sformatter = colorlog.LevelFormatter(
            fmt={
                "DEBUG": "{log_color}[{levelname}:{module}] {message}",
                "INFO": "{log_color}{message}",
                "WARNING": "{log_color}{levelname}: {message}",
                "ERROR": "{log_color}[{levelname}:{module}] {message}",
                "CRITICAL": "{log_color}[{levelname}:{module}] {message}",
                "EVERYTHING": "{log_color}[{levelname}:{module}] {message}",
                "NOISY": "{log_color}[{levelname}:{module}] {message}",
                "VOICEDEBUG": "{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}",
                "FFMPEG": "{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}",
            },
            log_colors={
                "DEBUG": "cyan",
                "INFO": "white",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
                "EVERYTHING": "bold_cyan",
                "NOISY": "bold_white",
                "FFMPEG": "bold_purple",
                "VOICEDEBUG": "purple",
            },
            style="{",
            datefmt="",
        )
        shandler.setFormatter(sformatter)
        shandler.setLevel(self.config.debug_level)
        logging.getLogger(__package__).addHandler(shandler)

        log.debug("Set logging level to {}".format(self.config.debug_level_str))

        if self.config.debug_mode:
            dlogger = logging.getLogger("discord")
            dlogger.setLevel(logging.DEBUG)
            dhandler = logging.FileHandler(
                filename="logs/discord.log", encoding="utf-8", mode="w"
            )
            dhandler.setFormatter(
                logging.Formatter("{asctime}:{levelname}:{name}: {message}", style="{")
            )
            dlogger.addHandler(dhandler)

    async def _join_startup_channels(self, channels, *, autosummon=True):
        joined_servers = set()
        channel_map = {c.guild: c for c in channels}

        for guild in self.guilds:
            if guild.unavailable or guild in channel_map:
                continue

            if guild.me.voice:
                log.info(
                    "Found resumable voice channel {0.guild.name}/{0.name}".format(
                        guild.me.voice.channel
                    )
                )
                channel_map[guild] = guild.me.voice.channel

            if autosummon:
                owner = self._get_owner(server=guild, voice=True)
                if owner:
                    log.info('Found owner in "{}"'.format(owner.voice.channel.name))
                    channel_map[guild] = owner.voice.channel

        for guild, channel in channel_map.items():
            if guild in joined_servers:
                log.info(
                    'Already joined a channel in "{}", skipping'.format(guild.name)
                )
                continue

            if channel and isinstance(
                channel, (discord.VoiceChannel, discord.StageChannel)
            ):
                log.info("Attempting to join {0.guild.name}/{0.name}".format(channel))

                chperms = channel.permissions_for(guild.me)

                if not chperms.connect:
                    log.info(
                        'Cannot join channel "{}", no permission.'.format(channel.name)
                    )
                    continue

                elif not chperms.speak:
                    log.info(
                        'Will not join channel "{}", no permission to speak.'.format(
                            channel.name
                        )
                    )
                    continue

                try:
                    player = await self.get_player(
                        channel, create=True, deserialize=self.config.persistent_queue
                    )
                    joined_servers.add(guild)

                    log.info("Joined {0.guild.name}/{0.name}".format(channel))

                    if player.is_stopped:
                        player.play()

                    if self.config.auto_playlist:
                        if not player.playlist.entries:
                            await self.on_player_finished_playing(player)

                except Exception:
                    log.debug(
                        "Error joining {0.guild.name}/{0.name}".format(channel),
                        exc_info=True,
                    )
                    log.error("Failed to join {0.guild.name}/{0.name}".format(channel))

            elif channel:
                log.warning(
                    "Not joining {0.guild.name}/{0.name}, that's a text channel.".format(
                        channel
                    )
                )

            else:
                log.warning("Invalid channel thing: {}".format(channel))

    async def _wait_delete_msg(self, message, after):
        try:
            await asyncio.sleep(after)
        except Exception:
            log.exception("_wait_delete_msg sleep caught exception. bailing.")
            return

        if not self.is_closed():
            await self.safe_delete_message(message, quiet=True)

    async def _check_ignore_non_voice(self, msg):
        if msg.guild.me.voice:
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
        else:
            raise exceptions.PermissionsError(
                "you cannot use this command when not in the voice channel (%s)"
                % vc.name,
                expire_in=30,
            )

    async def _cache_app_info(self, *, update=False):
        if not self.cached_app_info and not update and self.user.bot:
            log.debug("Caching app info")
            self.cached_app_info = await self.application_info()

        return self.cached_app_info

    async def remove_url_from_autoplaylist(
        self, song_url: str, *, ex: Exception = None, delete_from_ap=False
    ):
        if song_url not in self.autoplaylist:
            log.debug('URL "{}" not in autoplaylist, ignoring'.format(song_url))
            return

        async with self.aiolocks["autoplaylist_update_lock"]:
            self.autoplaylist.remove(song_url)
            log.info(
                "Removing{} song from session autoplaylist: {}".format(
                    " unplayable" if ex and not isinstance(ex, UserWarning) else "",
                    song_url,
                ),
            )

            with open(
                self.config.auto_playlist_removed_file, "a", encoding="utf8"
            ) as f:
                f.write(
                    "# Entry removed {ctime}\n"
                    "# URL:  {url}\n"
                    "# Reason: {ex}\n"
                    "\n{sep}\n\n".format(
                        ctime=time.ctime(),
                        ex=str(ex).replace(
                            "\n", "\n#" + " " * 10
                        ),  # 10 spaces to line up with # Reason:
                        url=song_url,
                        sep="#" * 32,
                    )
                )

            if delete_from_ap:
                log.info("Updating autoplaylist file...")
                # read the original file in and remove lines with the URL.
                # this is done to preserve the comments and formatting.
                try:
                    apl = pathlib.Path(self.config.auto_playlist_file)
                    data = apl.read_text()
                    data = data.replace(song_url, f"#Removed# {song_url}")
                    apl.write_text(data)
                except Exception:
                    log.exception("Failed to save autoplaylist file.")
                self.filecache.remove_autoplay_cachemap_entry_by_url(song_url)

    async def add_url_to_autoplaylist(self, song_url: str):
        if song_url in self.autoplaylist:
            log.debug("URL already in autoplaylist, ignoring")
            return

        async with self.aiolocks["autoplaylist_update_lock"]:
            # Note, this does not update the player's copy of the list.
            self.autoplaylist.append(song_url)
            log.info(f"Adding new URL to autoplaylist: {song_url}")

            try:
                # append to the file to preserve its formatting.
                with open(self.config.auto_playlist_file, "r+") as fh:
                    lines = fh.readlines()
                    if lines[-1].endswith("\n"):
                        lines.append(f"{song_url}\n")
                    else:
                        lines.append(f"\n{song_url}\n")
                    fh.seek(0)
                    fh.writelines(lines)
            except Exception:
                log.exception("Failed to save autoplaylist file.")

    @ensure_appinfo
    async def generate_invite_link(
        self, *, permissions=discord.Permissions(70380544), guild=discord.utils.MISSING
    ):
        return discord.utils.oauth_url(
            self.cached_app_info.id, permissions=permissions, guild=guild
        )

    async def get_voice_client(self, channel: discord.abc.GuildChannel):
        if isinstance(channel, discord.Object):
            channel = self.get_channel(channel.id)

        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            raise AttributeError("Channel passed must be a voice channel")

        if channel.guild.voice_client:
            return channel.guild.voice_client
        else:
            client = await channel.connect(timeout=60, reconnect=True)
            if isinstance(channel, discord.StageChannel):
                try:
                    await channel.guild.me.edit(suppress=False)
                    await channel.guild.change_voice_state(
                        channel=channel,
                        self_mute=False,
                        self_deaf=self.config.self_deafen,
                    )
                except Exception as e:
                    log.error(e)
            else:
                await channel.guild.change_voice_state(
                    channel=channel,
                    self_mute=False,
                    self_deaf=self.config.self_deafen,
                )
            return client

    async def disconnect_voice_client(self, guild):
        vc = self.voice_client_in(guild)
        if not vc:
            return

        if guild.id in self.players:
            player = self.players.pop(guild.id)

            await self.reset_player_inactivity(player)

            if self.config.leave_inactive_channel:
                event, active = self.server_specific_data[guild.id]["inactive_vc_timer"]
                if active and not event.is_set():
                    event.set()

            player.kill()

        await self.update_now_playing_status()
        await vc.disconnect()

    async def disconnect_all_voice_clients(self):
        for vc in list(self.voice_clients).copy():
            await self.disconnect_voice_client(vc.channel.guild)

    def get_player_in(self, guild: discord.Guild) -> Optional[MusicPlayer]:
        return self.players.get(guild.id)

    async def get_player(
        self, channel, create=False, *, deserialize=False
    ) -> MusicPlayer:
        guild = channel.guild

        async with self.aiolocks[_func_() + ":" + str(guild.id)]:
            if deserialize:
                voice_client = await self.get_voice_client(channel)
                player = await self.deserialize_queue(guild, voice_client)

                if player:
                    log.debug(
                        "Created player via deserialization for guild %s with %s entries",
                        guild.id,
                        len(player.playlist),
                    )
                    # Since deserializing only happens when the bot starts, I should never need to reconnect
                    return self._init_player(player, guild=guild)

            if guild.id not in self.players:
                if not create:
                    raise exceptions.CommandError(
                        "The bot is not in a voice channel.  "
                        "Use %ssummon to summon it to your voice channel."
                        % self._get_guild_cmd_prefix(channel.guild)
                    )

                voice_client = await self.get_voice_client(channel)

                playlist = Playlist(self)
                player = MusicPlayer(self, voice_client, playlist)
                self._init_player(player, guild=guild)

        return self.players[guild.id]

    def _init_player(self, player, *, guild=None):
        player = (
            player.on("play", self.on_player_play)
            .on("resume", self.on_player_resume)
            .on("pause", self.on_player_pause)
            .on("stop", self.on_player_stop)
            .on("finished-playing", self.on_player_finished_playing)
            .on("entry-added", self.on_player_entry_added)
            .on("error", self.on_player_error)
        )

        player.skip_state = SkipState()

        if guild:
            self.players[guild.id] = player

        return player

    async def on_player_play(self, player, entry):
        log.debug("Running on_player_play")
        self._handle_guild_auto_pause(player)
        await self.reset_player_inactivity(player)
        await self.update_now_playing_status()
        # manage the cache since we may have downloaded something.
        self.filecache.handle_new_cache_entry(entry)
        player.skip_state.reset()

        # This is the one event where it's ok to serialize autoplaylist entries
        await self.serialize_queue(player.voice_client.channel.guild)

        if self.config.write_current_song:
            await self.write_current_song(player.voice_client.channel.guild, entry)

        channel = entry.meta.get("channel", None)
        author = entry.meta.get("author", None)

        if channel and author:
            author_perms = self.permissions.for_user(author)

            if (
                author not in player.voice_client.channel.members
                and author_perms.skip_when_absent
            ):
                newmsg = self.str.get(
                    "on_player_play-onChannel_authorNotInChannel_skipWhenAbsent",
                    "Skipping next song in {channel}: {title} added by {author} as queuer not in voice!",
                ).format(
                    channel=player.voice_client.channel.name,
                    title=entry.title,
                    author=entry.meta["author"].name,
                )
                player.skip()
            elif self.config.now_playing_mentions:
                newmsg = self.str.get(
                    "on_player_play-onChannel_playingMention",
                    "{author} - your song {title} is now playing in {channel}!",
                ).format(
                    author=entry.meta["author"].mention,
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
                    author=entry.meta["author"].name,
                )

        else:
            # no author (and channel), it's an autoplaylist (or autostream from my other PR) entry.
            newmsg = self.str.get(
                "on_player_play-onChannel_noAuthor_autoplaylist",
                "Now playing automatically added entry {title} in {channel}!",
            ).format(title=entry.title, channel=player.voice_client.channel.name)

        if newmsg:
            if self.config.dm_nowplaying and author:
                await self.safe_send_message(author, newmsg)
                return

            if self.config.no_nowplaying_auto and not author:
                return

            guild = player.voice_client.guild
            last_np_msg = self.server_specific_data[guild.id]["last_np_msg"]

            if self.config.nowplaying_channels:
                for potential_channel_id in self.config.nowplaying_channels:
                    potential_channel = self.get_channel(potential_channel_id)
                    if potential_channel and potential_channel.guild == guild:
                        channel = potential_channel
                        break

            if channel:
                pass
            elif not channel and last_np_msg:
                channel = last_np_msg.channel
            else:
                log.debug("no channel to put now playing message into")
                return

        if self.config.embeds:
            content = self._gen_embed()

            if entry.thumbnail_url:
                content.set_image(url=entry.thumbnail_url)
            else:
                log.warning(f"No thumbnail set for entry with url: {entry.url}")

            if self.config.now_playing_mentions:
                content.title = None
                content.add_field(name="\n", value=newmsg, inline=True)
            else:
                content.title = newmsg

        # send it in specified channel
        self.server_specific_data[guild.id][
            "last_np_msg"
        ] = await self.safe_send_message(
            channel,
            content if self.config.embeds else newmsg,
            expire_in=30 if self.config.delete_nowplaying else 0,
        )

        # TODO: Check channel voice state?

    async def on_player_resume(self, player, entry, **_):
        log.debug("Running on_player_resume")
        await self.reset_player_inactivity(player)
        await self.update_now_playing_status()

    async def on_player_pause(self, player, entry, **_):
        log.debug("Running on_player_pause")
        await self.update_now_playing_status()
        self.loop.create_task(self.handle_player_inactivity(player))
        # TODO: if we manage to add seek functionality this might be wise.
        # await self.serialize_queue(player.voice_client.channel.guild)

    async def on_player_stop(self, player, **_):
        log.debug("Running on_player_stop")
        await self.update_now_playing_status()
        self.loop.create_task(self.handle_player_inactivity(player))

    async def on_player_finished_playing(self, player, **_):
        log.debug("Running on_player_finished_playing")
        if self.config.leave_after_queue_empty:
            guild = player.voice_client.guild
            if player.playlist.entries.__len__() == 0:
                log.info("Player finished and queue is empty, leaving voice channel...")
                await self.disconnect_voice_client(guild)

        # delete last_np_msg somewhere if we have cached it
        if self.config.delete_nowplaying:
            guild = player.voice_client.guild
            last_np_msg = self.server_specific_data[guild.id]["last_np_msg"]
            if last_np_msg:
                await self.safe_delete_message(last_np_msg)

        # avoid downloading the next entries if the user is absent and we are configured to skip.
        notice_sent = False  # set a flag to avoid message spam.
        while True:
            try:
                next_entry = player.playlist.peek()
            except Exception:
                break

            if not next_entry:
                break

            channel = next_entry.meta.get("channel", None)
            author = next_entry.meta.get("author", None)

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
                        "Skipping songs added by {author} as they are not in voice!".format(
                            author=author.name,
                        ),
                        expire_in=60,
                    )
                    notice_sent = True
                deleted_entry = player.playlist.delete_entry_at_index(0)
                log.noise(
                    "Author `{}` absent, skipped (deleted) entry from queue:  {}".format(
                        author.name, deleted_entry.title
                    )
                )
            else:
                break

        # manage auto playlist playback.
        if (
            not player.playlist.entries
            and not player.current_entry
            and self.config.auto_playlist
        ):
            if not player.autoplaylist:
                if not self.autoplaylist:
                    # TODO: When I add playlist expansion, make sure that's not happening during this check.
                    # @Fae: Could lock this but it probably isn't needed.
                    # - if `self.autoplaylist` is already empty, and the last entry was a playlist URL
                    # - then queued songs from that URL go into the `player.playlist`, not into `self.autoplaylist`.
                    # So if it's empty, it will stay that way unless someone is actively adding URLs when this fires.
                    log.warning("No playable songs in the autoplaylist, disabling.")
                    self.config.auto_playlist = False
                else:
                    log.debug(
                        "No content in current autoplaylist. Filling with new music..."
                    )
                    player.autoplaylist = list(self.autoplaylist)

            while player.autoplaylist:
                if self.config.auto_playlist_random:
                    random.shuffle(player.autoplaylist)
                    song_url = random.choice(player.autoplaylist)
                else:
                    song_url = player.autoplaylist[0]
                player.autoplaylist.remove(song_url)

                info = {}
                try:
                    info = await self.downloader.extract_info(
                        song_url, download=False, process=True
                    )
                except downloader.youtube_dl.utils.DownloadError as e:
                    if "YouTube said:" in e.args[0]:
                        # url is bork, remove from list and put in removed list
                        log.error("Error processing youtube url:\n{}".format(e.args[0]))

                    else:
                        # Probably an error from a different extractor, but I've only seen youtube's
                        log.error(
                            'Error processing "{url}": {ex}'.format(url=song_url, ex=e)
                        )

                    await self.remove_url_from_autoplaylist(
                        song_url, ex=e, delete_from_ap=self.config.remove_ap
                    )
                    continue

                except Exception as e:
                    log.error(
                        'Error processing "{url}": {ex}'.format(url=song_url, ex=e)
                    )
                    log.exception()

                    await self.remove_url_from_autoplaylist(
                        song_url, ex=e, delete_from_ap=self.config.remove_ap
                    )
                    continue

                if info.has_entries:
                    await player.playlist.import_from_info(
                        info, channel=None, author=None, head=False
                    )

                # Do I check the initial conditions again?
                # not (not player.playlist.entries and not player.current_entry and self.config.auto_playlist)

                try:
                    await player.playlist.add_entry_from_info(
                        info, channel=None, author=None, head=False
                    )
                except exceptions.ExtractionError as e:
                    log.error("Error adding song from autoplaylist: {}".format(e))
                    log.debug("", exc_info=True)
                    continue

                break

            if not self.autoplaylist:
                # TODO: When I add playlist expansion, make sure that's not happening during this check
                log.warning("No playable songs in the autoplaylist, disabling.")
                self.config.auto_playlist = False

        else:  # Don't serialize for autoplaylist events
            await self.serialize_queue(player.voice_client.channel.guild)

        if not player.is_stopped and not player.is_dead:
            player.play(_continue=True)

    async def on_player_entry_added(
        self, player, playlist, entry, defer_serialize: bool = False, **_
    ):
        log.debug("Running on_player_entry_added")
        if (
            entry.meta.get("author")
            and entry.meta.get("channel")
            and not defer_serialize
        ):
            await self.serialize_queue(player.voice_client.channel.guild)

    async def on_player_error(self, player, entry, ex, **_):
        author = entry.meta.get("author", None)
        channel = entry.meta.get("channel", None)
        if channel and author:
            song = entry.title or entry.url
            await self.safe_send_message(
                channel,
                # TODO: i18n / UI stuff
                "Playback failed for song: `{}` due to error:\n```\n{}\n```".format(
                    song, ex
                ),
            )
        else:
            log.exception("Player error", exc_info=ex)

    async def update_now_playing_status(self) -> None:
        """Inspects available players and ultimately fire change_presence()"""
        activity = None  # type: Optional[discord.Activity]
        status = discord.Status.online  # type: discord.Status

        playing = sum(1 for p in self.players.values() if p.is_playing)
        paused = sum(1 for p in self.players.values() if p.is_paused)
        total = len(self.players)

        # multiple servers are playing or paused.
        if total > 1:
            if paused > playing:
                status = discord.Status.idle

            activity = discord.Activity(
                type=discord.ActivityType.playing,
                name="music on {} guilds".format(total),
            )

        # only 1 server is playing.
        elif playing:
            player = list(self.players.values())[0]
            activity = discord.Activity(
                type=discord.ActivityType.streaming,
                url=player.current_entry.url,
                name=player.current_entry.title.strip()[:128],
                # platform="" does not work.
            )

        # only 1 server is paused.
        elif paused:
            player = list(self.players.values())[0]
            status = discord.Status.idle
            activity = discord.Activity(
                type=discord.ActivityType.custom,
                state=player.current_entry.title.strip()[:128],
                name="Custom Status",  # seemingly required.
                # TODO: emoji is broken in dpy lib. 2024-01-10
                emoji={"name": ":pause_button:"},
            )

        # nothing going on.
        else:
            status = discord.Status.idle
            activity = discord.CustomActivity(
                type=discord.ActivityType.custom,
                state=f" ~ {EMOJI_IDLE_ICON} ~ ",
                name="Custom Status",  # seems required to make idle status work.
                # TODO: emoji is currently broken in discord.py lib. 2024-01-10
                # emoji={"name": EMOJI_IDLE_ICON},
                emoji="\N{POWER SLEEP SYMBOL}",
            )

        async with self.aiolocks[_func_()]:
            if activity != self.last_status:
                log.noise(f"Update Bot Status:  {status} -- {repr(activity)}")
                await self.change_presence(status=status, activity=activity)
                self.last_status = activity

    async def update_now_playing_message(self, guild, message, *, channel=None):
        lnp = self.server_specific_data[guild.id]["last_np_msg"]
        m = None

        if message is None and lnp:
            await self.safe_delete_message(lnp, quiet=True)

        elif lnp:  # If there was a previous lp message
            oldchannel = lnp.channel

            if lnp.channel == oldchannel:  # If we have a channel to update it in
                async for lmsg in lnp.channel.history(limit=1):
                    if lmsg != lnp and lnp:  # If we need to resend it
                        await self.safe_delete_message(lnp, quiet=True)
                        m = await self.safe_send_message(channel, message, quiet=True)
                    else:
                        m = await self.safe_edit_message(
                            lnp, message, send_if_fail=True, quiet=False
                        )

            elif channel:  # If we have a new channel to send it to
                await self.safe_delete_message(lnp, quiet=True)
                m = await self.safe_send_message(channel, message, quiet=True)

            else:  # we just resend it in the old channel
                await self.safe_delete_message(lnp, quiet=True)
                m = await self.safe_send_message(oldchannel, message, quiet=True)

        elif channel:  # No previous message
            m = await self.safe_send_message(channel, message, quiet=True)

        self.server_specific_data[guild.id]["last_np_msg"] = m

    async def serialize_queue(self, guild, *, dir=None):
        """
        Serialize the current queue for a server's player to json.
        """

        player = self.get_player_in(guild)
        if not player:
            return

        if dir is None:
            dir = "data/%s/queue.json" % guild.id

        async with self.aiolocks["queue_serialization" + ":" + str(guild.id)]:
            log.debug("Serializing queue for %s", guild.id)

            with open(dir, "w", encoding="utf8") as f:
                f.write(player.serialize(sort_keys=True))

    async def serialize_all_queues(self, *, dir=None):
        coros = [self.serialize_queue(s, dir=dir) for s in self.guilds]
        await asyncio.gather(*coros, return_exceptions=True)

    async def deserialize_queue(
        self, guild, voice_client, playlist=None, *, directory=None
    ) -> Optional[MusicPlayer]:
        """
        Deserialize a saved queue for a server into a MusicPlayer.  If no queue is saved, returns None.
        """

        if playlist is None:
            playlist = Playlist(self)

        if directory is None:
            directory = "data/%s/queue.json" % guild.id

        async with self.aiolocks["queue_serialization" + ":" + str(guild.id)]:
            if not os.path.isfile(directory):
                return None

            log.debug("Deserializing queue for %s", guild.id)

            with open(directory, "r", encoding="utf8") as f:
                data = f.read()

        return MusicPlayer.from_json(data, self, voice_client, playlist)

    async def write_current_song(self, guild, entry, *, directory=None):
        """
        Writes the current song to file
        """
        player = self.get_player_in(guild)
        if not player:
            return

        if directory is None:
            directory = "data/%s/current.txt" % guild.id

        async with self.aiolocks["current_song" + ":" + str(guild.id)]:
            log.debug("Writing current song for %s", guild.id)

            with open(directory, "w", encoding="utf8") as f:
                f.write(entry.title)

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
            pathlib.Path("data/%s/" % guild.id).mkdir(exist_ok=True)

        with open("data/server_names.txt", "w", encoding="utf8") as f:
            for guild in sorted(self.guilds, key=lambda s: int(s.id)):
                f.write("{:<22} {}\n".format(guild.id, guild.name))

        self.filecache.delete_old_audiocache(remove_dir=True)

    async def _scheck_server_permissions(self):
        log.debug("Checking server permissions")
        pass  # TODO

    async def _scheck_autoplaylist(self):
        log.debug("Auditing autoplaylist")
        pass  # TODO

    async def _scheck_configs(self):
        log.debug("Validating config")
        await self.config.async_validate(self)

        log.debug("Validating permissions config")
        await self.permissions.async_validate(self)

    async def _load_guild_options(self, guild: discord.Guild):
        opt_file = f"data/{guild.id}/options.json"
        if not os.path.exists(opt_file):
            return
        options = Json(opt_file)
        guild_prefix = options.get("command_prefix", None)
        if guild_prefix:
            self.server_specific_data[guild.id]["command_prefix"] = guild_prefix
            log.info(f"Custom command prefix for: {guild.name}  Prefix: {guild_prefix}")

    async def _save_guild_options(self, guild: discord.Guild):
        opt_file = f"data/{guild.id}/options.json"
        opt_dict = {
            "command_prefix": self.server_specific_data[guild.id]["command_prefix"]
        }
        with open(opt_file, "w") as fh:
            fh.write(json.dumps(opt_dict))

    def _get_guild_cmd_prefix(self, guild: discord.Guild):
        if self.config.enable_options_per_guild:
            if guild:
                prefix = self.server_specific_data[guild.id]["command_prefix"]
                if prefix:
                    return prefix
        return self.config.command_prefix

    #######################################################################################################################

    async def safe_send_message(self, dest, content, **kwargs):
        tts = kwargs.pop("tts", False)
        quiet = kwargs.pop("quiet", False)
        expire_in = kwargs.pop("expire_in", 0)
        allow_none = kwargs.pop("allow_none", True)
        also_delete = kwargs.pop("also_delete", None)

        msg = None
        retry_after = None
        lfunc = log.debug if quiet else log.warning
        if log.getEffectiveLevel() <= logging.NOISY:
            lfunc = log.exception

        try:
            if content is not None or allow_none:
                if isinstance(content, discord.Embed):
                    msg = await dest.send(embed=content)
                else:
                    msg = await dest.send(content, tts=tts)

        except discord.Forbidden:
            lfunc('Cannot send message to "%s", no permission', dest.name)

        except discord.NotFound:
            lfunc('Cannot send message to "%s", invalid channel?', dest.name)

        except discord.HTTPException as e:
            if len(content) > DISCORD_MSG_CHAR_LIMIT:
                lfunc(
                    "Message is over the message size limit (%s)",
                    DISCORD_MSG_CHAR_LIMIT,
                )

            elif e.status == 429:
                # Note:  `e.response` could be either type:  aiohttp.ClientResponse  OR  requests.Response
                # thankfully both share a similar enough `response.headers` member CI Dict.
                # See docs on headers here:  https://discord.com/developers/docs/topics/rate-limits
                try:
                    retry_after = float(e.response.headers.get("RETRY-AFTER"))
                except ValueError:
                    retry_after = None
                if retry_after:
                    log.warning(
                        f"Rate limited send message, retrying in {retry_after} seconds."
                    )
                    try:
                        await asyncio.sleep(retry_after)
                    except Exception:
                        log.exception(
                            "Sleep in send message caught exception, bailing out."
                        )
                        return msg
                    return await self.safe_send_message(dest, content, **kwargs)
                else:
                    log.error("Rate limited send message, but cannot retry!")

            else:
                lfunc("Failed to send message")
                log.noise(
                    "Got HTTPException trying to send message to %s: %s", dest, content
                )

        finally:
            if retry_after:
                return msg

            if self.config.delete_messages:
                if msg and expire_in:
                    asyncio.ensure_future(self._wait_delete_msg(msg, expire_in))

            if self.config.delete_invoking:
                if also_delete and isinstance(also_delete, discord.Message):
                    asyncio.ensure_future(self._wait_delete_msg(also_delete, expire_in))

        return msg

    async def safe_delete_message(self, message, *, quiet=False):
        # TODO: this could use a queue and some other handling.
        lfunc = log.debug if quiet else log.warning

        try:
            return await message.delete()

        except discord.Forbidden:
            lfunc(
                'Cannot delete message "{}", no permission'.format(
                    message.clean_content
                )
            )

        except discord.NotFound:
            lfunc(
                'Cannot delete message "{}", message not found'.format(
                    message.clean_content
                )
            )

        except discord.HTTPException as e:
            if e.status == 429:
                # Note:  `e.response` could be either type:  aiohttp.ClientResponse  OR  requests.Response
                # thankfully both share a similar enough `response.headers` member CI Dict.
                # See docs on headers here:  https://discord.com/developers/docs/topics/rate-limits
                try:
                    retry_after = float(e.response.headers.get("RETRY-AFTER"))
                except ValueError:
                    retry_after = None
                if retry_after:
                    log.warning(
                        f"Rate limited message delete, retrying in {retry_after} seconds."
                    )
                    asyncio.ensure_future(self._wait_delete_msg(message, retry_after))
                else:
                    log.error("Rate limited message delete, but cannot retry!")

            else:
                lfunc("Failed to delete message")
                log.noise("Got HTTPException trying to delete message: %s", message)

    async def safe_edit_message(self, message, new, *, send_if_fail=False, quiet=False):
        lfunc = log.debug if quiet else log.warning

        try:
            return await message.edit(content=new)

        except discord.NotFound:
            lfunc(
                'Cannot edit message "{}", message not found'.format(
                    message.clean_content
                )
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
                    retry_after = float(e.response.headers.get("RETRY-AFTER"))
                except ValueError:
                    retry_after = None
                if retry_after:
                    log.warning(
                        f"Rate limited edit message, retrying in {retry_after} seconds."
                    )
                    try:
                        await asyncio.sleep(retry_after)
                    except Exception:
                        log.exception(
                            "Sleep in edit message caught exception, bailing out."
                        )
                        return None
                    return await self.safe_edit_message(
                        message, new, send_if_fail=send_if_fail, quiet=quiet
                    )
            else:
                lfunc("Failed to edit message")
                log.noise(
                    "Got HTTPException trying to edit message %s to: %s", message, new
                )

    async def _cleanup(self):
        try:  # make sure discord.Client is closed.
            await self.close()  # changed in d.py 2.0
        except Exception:
            log.exception("Issue while closing discord client session.")
            pass

        try:  # make sure discord.http.connector is closed.
            # This may be a bug in aiohttp or within discord.py handling of it.
            # Have read aiohttp 4.x is supposed to fix this, but have not verified.
            if self.http.connector:
                await self.http.connector.close()
        except Exception:
            log.exception("Issue while closing discord aiohttp connector.")
            pass

        try:  # make sure our aiohttp session is closed.
            await self.session.close()
        except Exception:
            log.exception("Issue while closing our aiohttp session.")
            pass

        # now cancel all pending tasks, except for run.py::main()
        for task in asyncio.all_tasks(loop=self.loop):
            if (
                task.get_coro().__name__ == "main"
                and task.get_name().lower() == "task-1"
            ):
                continue

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    # noinspection PyMethodOverriding
    async def run(self):
        try:
            await self.start(*self.config.auth)

        except discord.errors.LoginFailure:
            # Add if token, else
            raise exceptions.HelpfulError(
                "Bot cannot login, bad credentials.",
                "Fix your token in the options file.  "
                "Remember that each field should be on their own line.",
            )  # ^^^^ In theory self.config.auth should never have no items

        finally:
            try:
                await self._cleanup()
            except Exception:
                log.error("Error in cleanup", exc_info=True)

            if self.exit_signal:
                raise self.exit_signal  # pylint: disable=E0702

    async def logout(self):
        await self.disconnect_all_voice_clients()
        return await super().close()

    async def on_error(self, event, *args, **kwargs):
        ex_type, ex, stack = sys.exc_info()

        if ex_type == exceptions.HelpfulError:
            log.error("Exception in {}:\n{}".format(event, ex.message))

            await asyncio.sleep(2)  # don't ask
            await self.logout()

        elif issubclass(ex_type, exceptions.Signal):
            self.exit_signal = ex
            await self.logout()

        else:
            log.error("Exception in {}".format(event), exc_info=True)

    async def on_resumed(self):
        log.info("\nReconnected to discord.\n")

    async def on_ready(self):
        self.is_ready_done = False
        log.debug("Fire on_ready")
        dlogger = logging.getLogger("discord")
        for h in dlogger.handlers:
            if getattr(h, "terminator", None) == "":
                dlogger.removeHandler(h)
                print()

        log.debug("Connection established, ready to go.")

        self.ws._keep_alive.name = "Gateway Keepalive"

        if self.init_ok:
            log.debug("Received additional READY event, may have failed to resume")
            return

        await self._on_ready_sanity_checks()

        self.init_ok = True

        ################################

        log.info(
            "Connected: {0}/{1}#{2}".format(
                self.user.id, self.user.name, self.user.discriminator
            )
        )

        owner = self._get_owner(voice=True) or self._get_owner()
        if owner and self.guilds:
            log.info(
                "Owner:     {0}/{1}#{2}\n".format(
                    owner.id, owner.name, owner.discriminator
                )
            )

            log.info("Guild List:")
            unavailable_servers = 0
            for s in self.guilds:
                ser = "{} (unavailable)".format(s.name) if s.unavailable else s.name
                log.info(" - " + ser)
                if self.config.leavenonowners:
                    if s.unavailable:
                        unavailable_servers += 1
                    else:
                        check = s.get_member(owner.id)
                        if check is None:
                            await s.leave()
                            log.info(
                                "Left {} due to bot owner not found".format(s.name)
                            )
            if unavailable_servers != 0:
                log.info(
                    "Not proceeding with checks in {} servers due to unavailability".format(
                        str(unavailable_servers)
                    )
                )

        elif self.guilds:
            log.warning(
                "Owner could not be found on any guild (id: %s)\n"
                % self.config.owner_id
            )

            log.info("Guild List:")
            for s in self.guilds:
                ser = "{} (unavailable)".format(s.name) if s.unavailable else s.name
                log.info(" - " + ser)

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

        if self.config.enable_options_per_guild:
            for s in self.guilds:
                await self._load_guild_options(s)

        if self.config.bound_channels:
            chlist = set(self.get_channel(i) for i in self.config.bound_channels if i)
            chlist.discard(None)

            invalids = set()
            invalids.update(c for c in chlist if isinstance(c, discord.VoiceChannel))

            chlist.difference_update(invalids)
            self.config.bound_channels.difference_update(invalids)

            if chlist:
                log.info("Bound to text channels:")
                [
                    log.info(" - {}/{}".format(ch.guild.name.strip(), ch.name.strip()))
                    for ch in chlist
                    if ch
                ]
            else:
                print("Not bound to any text channels")

            if invalids and self.config.debug_mode:
                print(flush=True)
                log.info("Not binding to voice channels:")
                [
                    log.info(" - {}/{}".format(ch.guild.name.strip(), ch.name.strip()))
                    for ch in invalids
                    if ch
                ]

            print(flush=True)

        else:
            log.info("Not bound to any text channels")

        if self.config.autojoin_channels:
            chlist = set(
                self.get_channel(i) for i in self.config.autojoin_channels if i
            )
            chlist.discard(None)

            invalids = set()
            invalids.update(c for c in chlist if isinstance(c, discord.TextChannel))

            chlist.difference_update(invalids)
            self.config.autojoin_channels.difference_update(invalids)

            if chlist:
                log.info("Autojoining voice channels:")
                [
                    log.info(" - {}/{}".format(ch.guild.name.strip(), ch.name.strip()))
                    for ch in chlist
                    if ch
                ]
            else:
                log.info("Not autojoining any voice channels")

            if invalids and self.config.debug_mode:
                print(flush=True)
                log.info("Cannot autojoin text channels:")
                [
                    log.info(" - {}/{}".format(ch.guild.name.strip(), ch.name.strip()))
                    for ch in invalids
                    if ch
                ]

            self.autojoin_channels = chlist

        else:
            log.info("Not autojoining any voice channels")
            self.autojoin_channels = set()

        if self.config.show_config_at_start:
            print(flush=True)
            log.info("Options:")

            log.info("  Command prefix: " + self.config.command_prefix)
            log.info(
                "  Default volume: {}%".format(int(self.config.default_volume * 100))
            )
            log.info(
                "  Skip threshold: {} votes or {}%".format(
                    self.config.skips_required,
                    fixg(self.config.skip_ratio_required * 100),
                )
            )
            log.info(
                "  Now Playing @mentions: "
                + ["Disabled", "Enabled"][self.config.now_playing_mentions]
            )
            log.info(
                "  Auto-Summon: " + ["Disabled", "Enabled"][self.config.auto_summon]
            )
            log.info(
                "  Auto-Playlist: "
                + ["Disabled", "Enabled"][self.config.auto_playlist]
                + " (order: "
                + ["sequential", "random"][self.config.auto_playlist_random]
                + ")"
            )
            log.info("  Auto-Pause: " + ["Disabled", "Enabled"][self.config.auto_pause])
            log.info(
                "  Delete Messages: "
                + ["Disabled", "Enabled"][self.config.delete_messages]
            )
            if self.config.delete_messages:
                log.info(
                    "    Delete Invoking: "
                    + ["Disabled", "Enabled"][self.config.delete_invoking]
                )
                log.info(
                    f"    Delete Nowplaying: {['Disabled', 'Enabled'][self.config.delete_nowplaying]}"
                )
            log.info("  Debug Mode: " + ["Disabled", "Enabled"][self.config.debug_mode])
            log.info(
                "  Downloaded songs will be "
                + ["deleted", "saved"][self.config.save_videos]
            )
            if self.config.save_videos and self.config.storage_limit_days:
                log.info(
                    f"    Delete if unused for {self.config.storage_limit_days} days"
                )
            if self.config.save_videos and self.config.storage_limit_bytes:
                size = format_size_from_bytes(self.config.storage_limit_bytes)
                log.info(f"    Delete if size exceeds {size}")

            if self.config.status_message:
                log.info("  Status message: " + self.config.status_message)
            log.info(
                "  Write current songs to file: "
                + ["Disabled", "Enabled"][self.config.write_current_song]
            )
            log.info(
                "  Author insta-skip: "
                + ["Disabled", "Enabled"][self.config.allow_author_skip]
            )
            log.info("  Embeds: " + ["Disabled", "Enabled"][self.config.embeds])
            log.info(
                "  Spotify integration: "
                + ["Disabled", "Enabled"][self.config._spotify]
            )
            log.info(
                "  Legacy skip: " + ["Disabled", "Enabled"][self.config.legacy_skip]
            )
            log.info(
                "  Leave non owners: "
                + ["Disabled", "Enabled"][self.config.leavenonowners]
            )
            log.info(
                "  Leave inactive VC: "
                + ["Disabled", "Enabled"][self.config.leave_inactive_channel]
            )
            log.info(
                f"    Timeout: {self.config.leave_inactive_channel_timeout} seconds"
            )
            log.info(
                "  Leave at song end/empty queue: "
                + ["Disabled", "Enabled"][self.config.leave_after_queue_empty]
            )
            log.info(
                f"  Leave when player idles: {'Disabled' if self.config.leave_player_inactive_for == 0 else 'Enabled'}"
            )
            log.info(f"    Timeout: {self.config.leave_player_inactive_for} seconds")
            log.info(
                "  Self Deafen: " + ["Disabled", "Enabled"][self.config.self_deafen]
            )
            log.info(
                "  Per-server command prefix: "
                + ["Disabled", "Enabled"][self.config.enable_options_per_guild]
            )

        print(flush=True)

        await self.update_now_playing_status()

        # maybe option to leave the ownerid blank and generate a random command for the owner to use
        # wait_for_message is pretty neato

        await self._join_startup_channels(
            self.autojoin_channels, autosummon=self.config.auto_summon
        )

        # we do this after the config stuff because it's a lot easier to notice here
        if self.config.missing_keys:
            log.warning(
                "Your config file is missing some options. If you have recently updated, "
                "check the example_options.ini file to see if there are new options available to you. "
                "The options missing are: {0}".format(self.config.missing_keys)
            )
            print(flush=True)

        # t-t-th-th-that's all folks!
        log.debug("Finish on_ready")
        self.is_ready_done = True

    def _gen_embed(self):
        """Provides a basic template for embeds"""
        e = discord.Embed()
        e.colour = 7506394
        e.set_footer(
            text=self.config.footer_text, icon_url="https://i.imgur.com/gFHBoZA.png"
        )
        e.set_author(
            name=self.user.name,
            url="https://github.com/Just-Some-Bots/MusicBot",
            icon_url=self.user.avatar.url if self.user.avatar else None,
        )
        return e

    @staticmethod
    def _get_song_url_or_none(url, player):
        """Return song url if provided or one is currently playing, else returns None"""
        if not player:
            return url

        if url or (
            player.current_entry
            and not isinstance(player.current_entry, StreamPlaylistEntry)
        ):
            if not url:
                url = player.current_entry.url

            return url

    def _add_url_to_autoplaylist(self, url):
        self.autoplaylist.append(url)
        write_file(self.config.auto_playlist_file, self.autoplaylist)
        log.debug("Appended {} to autoplaylist".format(url))

    def _remove_url_from_autoplaylist(self, url):
        self.autoplaylist.remove(url)
        write_file(self.config.auto_playlist_file, self.autoplaylist)
        log.debug("Removed {} from autoplaylist".format(url))

    async def handle_vc_inactivity(self, guild: discord.Guild):
        if not guild.me.voice:
            log.warning("I HAVE NO MOUTH AND I MUST SCREAM!!!")
            return

        event, active = self.server_specific_data[guild.id]["inactive_vc_timer"]

        if active:
            log.debug(f"Channel activity already waiting in guild: {guild}")
            return
        self.server_specific_data[guild.id]["inactive_vc_timer"] = (event, True)

        try:
            log.info(
                f"Channel activity waiting {self.config.leave_inactive_channel_timeout} seconds to leave channel: {guild.me.voice.channel.name}"
            )
            await discord.utils.sane_wait_for(
                [event.wait()], timeout=self.config.leave_inactive_channel_timeout
            )
        except asyncio.TimeoutError:
            log.info(
                f"Channel activity timer for {guild.name} has expired. Disconnecting."
            )
            await self.on_inactivity_timeout_expired(guild.me.voice.channel)
        else:
            log.info(
                f"Channel activity timer canceled for: {guild.me.voice.channel.name} in {guild.name}"
            )
        finally:
            self.server_specific_data[guild.id]["inactive_vc_timer"] = (event, False)
            event.clear()

    async def handle_player_inactivity(self, player):
        if not self.config.leave_player_inactive_for:
            return
        channel = player.voice_client.channel
        guild = channel.guild
        event, event_active = self.server_specific_data[guild.id][
            "inactive_player_timer"
        ]

        if str(channel.id) in str(self.config.autojoin_channels):
            log.debug(
                f"Ignoring player inactivity in auto-joined channel:  {channel.name}"
            )
            return

        if event_active:
            log.debug(f"Player activity timer already waiting in guild: {guild}")
            return
        self.server_specific_data[guild.id]["inactive_player_timer"] = (event, True)

        try:
            log.info(
                f"Player activity timer waiting {self.config.leave_player_inactive_for} seconds to leave channel: {channel.name}"
            )
            await discord.utils.sane_wait_for(
                [event.wait()], timeout=self.config.leave_player_inactive_for
            )
        except asyncio.TimeoutError:
            log.info(
                f"Player activity timer for {guild.name} has expired. Disconnecting."
            )
            await self.on_inactivity_timeout_expired(channel)
        else:
            log.info(
                f"Player activity timer canceled for: {channel.name} in {guild.name}"
            )
        finally:
            self.server_specific_data[guild.id]["inactive_player_timer"] = (
                event,
                False,
            )
            event.clear()

    async def reset_player_inactivity(self, player):
        if not self.config.leave_player_inactive_for:
            return
        guild = player.voice_client.channel.guild
        event, active = self.server_specific_data[guild.id]["inactive_player_timer"]
        if active and not event.is_set():
            event.set()
            log.debug("Player activity timer is being reset.")

    async def cmd_resetplaylist(self, player, channel):
        """
        Usage:
            {command_prefix}resetplaylist

        Resets all songs in the server's autoplaylist
        """
        player.autoplaylist = list(set(self.autoplaylist))
        return Response(
            self.str.get("cmd-resetplaylist-response", "\N{OK HAND SIGN}"),
            delete_after=15,
        )

    async def cmd_help(self, message, channel, command=None):
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
        prefix = self._get_guild_cmd_prefix(channel.guild)
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
                            self.str.get(
                                "cmd-help-prefix-required",
                                "\n**Prefix required for use:**\n{example_cmd}\n",
                            ).format(example_cmd=f"{prefix}`{command} ...`")
                            if is_emoji
                            else "",
                        ).format(
                            command_prefix=prefix if not is_emoji else "",
                        ),
                        delete_after=60,
                    )
                else:
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
                    example_cmd=f"{prefix}`help [command]`"
                    if is_emoji
                    else f"`{prefix}help [command]`",
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
                    example_cmd=f"{prefix}`help [command]`"
                    if is_emoji
                    else f"`{prefix}help [command]`",
                )
            )
        if not is_all:
            desc += self.str.get(
                "cmd-help-all",
                "\nOnly showing commands you can use, for a list of all commands, run {example_cmd}",
            ).format(
                example_cmd=f"{prefix}`help all`"
                if is_emoji
                else f"`{prefix}help all`",
            )

        return Response(desc, reply=True, delete_after=60)

    async def cmd_blacklist(self, message, user_mentions, option, something):
        """
        Usage:
            {command_prefix}blacklist [ + | - | add | remove ] @UserName [@UserName2 ...]

        Add or remove users to the blacklist.
        Blacklisted users are forbidden from using bot commands.
        """

        if not user_mentions:
            raise exceptions.CommandError("No users listed.", expire_in=20)

        if option not in ["+", "-", "add", "remove"]:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-blacklist-invalid",
                    'Invalid option "{0}" specified, use +, -, add, or remove',
                ).format(option),
                expire_in=20,
            )

        for user in user_mentions.copy():
            if user.id == self.config.owner_id:
                print("[Commands:Blacklist] The owner cannot be blacklisted.")
                user_mentions.remove(user)

        old_len = len(self.blacklist)

        if option in ["+", "add"]:
            self.blacklist.update(user.id for user in user_mentions)

            write_file(self.config.blacklist_file, self.blacklist)

            return Response(
                self.str.get(
                    "cmd-blacklist-added", "{0} users have been added to the blacklist"
                ).format(len(self.blacklist) - old_len),
                reply=True,
                delete_after=10,
            )

        else:
            if self.blacklist.isdisjoint(user.id for user in user_mentions):
                return Response(
                    self.str.get(
                        "cmd-blacklist-none",
                        "None of those users are in the blacklist.",
                    ),
                    reply=True,
                    delete_after=10,
                )

            else:
                self.blacklist.difference_update(user.id for user in user_mentions)
                write_file(self.config.blacklist_file, self.blacklist)

                return Response(
                    self.str.get(
                        "cmd-blacklist-removed",
                        "{0} users have been removed from the blacklist",
                    ).format(old_len - len(self.blacklist)),
                    reply=True,
                    delete_after=10,
                )

    async def cmd_id(self, author, user_mentions):
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
        else:
            usr = user_mentions[0]
            return Response(
                self.str.get("cmd-id-other", "**{0}**s ID is `{1}`").format(
                    usr.name, usr.id
                ),
                reply=True,
                delete_after=35,
            )

    async def cmd_autoplaylist(self, _player, option, url=None):
        """
        Usage:
            {command_prefix}autoplaylist [ + | - | add | remove] [url]

        Adds or removes the specified song or currently playing song to/from the playlist.
        """
        url = self._get_song_url_or_none(url, _player)

        if url:
            if option in ["+", "add"]:
                if url not in self.autoplaylist:
                    await self.add_url_to_autoplaylist(url)
                    return Response(
                        self.str.get(
                            "cmd-save-success", "Added <{0}> to the autoplaylist."
                        ).format(url),
                        delete_after=35,
                    )
                else:
                    raise exceptions.CommandError(
                        self.str.get(
                            "cmd-save-exists",
                            "This song is already in the autoplaylist.",
                        ),
                        expire_in=20,
                    )
            elif option in ["-", "remove"]:
                if url in self.autoplaylist:
                    await self.remove_url_from_autoplaylist(url, delete_from_ap=True)
                    return Response(
                        self.str.get(
                            "cmd-unsave-success", "Removed <{0}> from the autoplaylist."
                        ).format(url),
                        delete_after=35,
                    )
                else:
                    raise exceptions.CommandError(
                        self.str.get(
                            "cmd-unsave-does-not-exist",
                            "This song is not yet in the autoplaylist.",
                        ),
                        expire_in=20,
                    )
            else:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-autoplaylist-option-invalid",
                        'Invalid option "{0}" specified, use +, -, add, or remove',
                    ).format(option),
                    expire_in=20,
                )
        else:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-autoplaylist-invalid", "The supplied song link is invalid"
                ),
                expire_in=20,
            )

    @owner_only
    async def cmd_joinserver(self, message, server_link=None):
        """
        Usage:
            {command_prefix}joinserver invite_link

        Asks the bot to join a server.  Note: Bot accounts cannot use invite links.
        """

        url = await self.generate_invite_link()
        return Response(
            self.str.get(
                "cmd-joinserver-response", "Click here to add me to a server: \n{}"
            ).format(url),
            reply=True,
            delete_after=30,
        )

    async def cmd_karaoke(self, player, channel, author):
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

    async def _do_playlist_checks(self, player, author, result_info):
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

    def _handle_guild_auto_pause(self, player: MusicPlayer):
        """
        function to handle guild activity pausing and unpausing.
        """
        if not self.config.auto_pause:
            return

        if not player.voice_client:
            return

        channel = player.voice_client.channel

        guild = channel.guild
        auto_paused = self.server_specific_data[guild.id]["auto_paused"]

        is_empty = is_empty_voice_channel(
            channel, include_bots=self.config.bot_exception_ids
        )
        if is_empty and not auto_paused and player.is_playing:
            log.info(
                f"Playing in an empty voice channel, running auto pause for guild: {guild}"
            )
            player.pause()
            self.server_specific_data[guild.id]["auto_paused"] = True

        elif not is_empty and auto_paused and player.is_paused:
            log.info(f"Previously auto paused player is unpausing for guild: {guild}")
            player.resume()
            self.server_specific_data[guild.id]["auto_paused"] = False

    async def _do_cmd_unpause_check(
        self, player: MusicPlayer, channel: discord.abc.GuildChannel
    ):
        """
        Checks for paused player and resumes it while sending a notice.

        This function should not be called from _cmd_play().
        """
        if player and player.is_paused:
            await self.safe_send_message(
                channel,
                self.str.get(
                    "cmd-unpause-check",
                    "Bot was previously paused, resuming playback now.",
                ),
                expire_in=30,
            )
            player.resume()

    async def cmd_play(
        self, message, _player, channel, author, permissions, leftover_args, song_url
    ):
        """
        Usage:
            {command_prefix}play song_link
            {command_prefix}play text to search for
            {command_prefix}play spotify_uri

        Adds the song to the playlist.  If a link is not provided, the first
        result from a youtube search is added to the queue.

        If enabled in the config, the bot will also support Spotify URIs, however
        it will use the metadata (e.g song name and artist) to find a YouTube
        equivalent of the song. Streaming from Spotify is not possible.
        """
        await self._do_cmd_unpause_check(_player, channel)

        return await self._cmd_play(
            message,
            _player,
            channel,
            author,
            permissions,
            leftover_args,
            song_url,
            head=False,
        )

    async def cmd_shuffleplay(
        self, message, _player, channel, author, permissions, leftover_args, song_url
    ):
        """
        Usage:
            {command_prefix}shuffleplay playlist_link

        Like play command but explicitly shuffles entries before adding them to the queue.
        """
        await self._do_cmd_unpause_check(_player, channel)

        await self._cmd_play(
            message,
            _player,
            channel,
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
        self, message, _player, channel, author, permissions, leftover_args, song_url
    ):
        """
        Usage:
            {command_prefix}playnext song_link
            {command_prefix}playnext text to search for
            {command_prefix}playnext spotify_uri

        Adds the song to the playlist next.  If a link is not provided, the first
        result from a youtube search is added to the queue.

        If enabled in the config, the bot will also support Spotify URIs, however
        it will use the metadata (e.g song name and artist) to find a YouTube
        equivalent of the song. Streaming from Spotify is not possible.
        """
        await self._do_cmd_unpause_check(_player, channel)

        return await self._cmd_play(
            message,
            _player,
            channel,
            author,
            permissions,
            leftover_args,
            song_url,
            head=True,
        )

    async def cmd_repeat(self, channel, option=None):
        """
        Usage:
            {command_prefix}repeat [all | playlist | song | on | off]

        Toggles playlist or song looping.
        If no option is provided the current song will be repeated.
        If no option is provided and the song is already repeating, repeating will be turned off.
        """

        player = self.get_player_in(channel.guild)
        option = option.lower() if option else ""
        prefix = self._get_guild_cmd_prefix(channel.guild)

        if not player:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-repeat-no-voice",
                    "The bot is not in a voice channel.  "
                    "Use %ssummon to summon it to your voice channel.",
                )
                % self._get_guild_cmd_prefix(channel.guild),
                expire_in=30,
            )

        if not player.current_entry:
            return Response(
                self.str.get(
                    "cmd-repeat-no-songs",
                    "No songs are queued. Play something with {}play.",
                ).format(self._get_guild_cmd_prefix(channel.guild)),
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

            else:
                return Response(
                    self.str.get(
                        "cmd-repeat-playlist-not-looping",
                        "Playlist is no longer repeating.",
                    ),
                    delete_after=30,
                )

        elif option == "song":
            player.repeatsong = not player.repeatsong
            if player.repeatsong:
                return Response(
                    self.str.get("cmd-repeat-song-looping", "Song is now repeating."),
                    delete_after=30,
                )
            else:
                return Response(
                    self.str.get(
                        "cmd-repeat-song-not-looping", "Song is no longer repeating."
                    )
                )

        elif option == "on":
            player.repeatsong = True
            return Response(self.str.get("cmd-repeat-song-looping"), delete_after=30)
            if player.repeatsong:
                return Response(
                    self.str.get(
                        "cmd-repeat-already-looping", "Song is already looping!"
                    ),
                    delete_after=30,
                )

        elif option == "off":
            if player.repeatsong:
                player.repeatsong = False
                return Response(self.str.get("cmd-repeat-song-not-looping"))
            elif player.loopqueue:
                player.loopqueue = False
                return Response(self.str.get("cmd-repeat-playlist-not-looping"))
            else:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-repeat-already-off", "The player is not currently looping."
                    ),
                    expire_in=30,
                )
        else:
            if player.repeatsong:
                player.loopqueue = True
                player.repeatsong = False
                return Response(
                    self.str.get("cmd-repeat-playlist-looping"), delete_after=30
                )

            elif player.loopqueue:
                if player.playlist.entries.__len__() > 0:
                    message = self.str.get("cmd-repeat-playlist-not-looping")
                else:
                    message = self.str.get("cmd-repeat-song-not-looping")
                player.loopqueue = False
            else:
                player.repeatsong = True
                message = self.str.get("cmd-repeat-song-looping")

        return Response(message, delete_after=30)

    async def cmd_move(self, channel, command, leftover_args):
        """
        Usage:
            {command_prefix}move [Index of song to move] [Index to move song to]
            Ex: !move 1 3

        Swaps the location of a song within the playlist.
        """
        # TODO: move command needs some tlc. args renamed, better checks.
        player = self.get_player_in(channel.guild)
        if not player:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-move-no-voice",
                    "The bot is not in a voice channel.  "
                    "Use %ssummon to summon it to your voice channel."
                    % self._get_guild_cmd_prefix(channel.guild),
                )
            )

        if not player.current_entry:
            return Response(
                self.str.get(
                    "cmd-move-no-songs",
                    "There are no songs queued. Play something with {}play".format(
                        self._get_guild_cmd_prefix(channel.guild)
                    ),
                ),
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
            if i < 0 or i > player.playlist.entries.__len__() - 1:
                return Response(
                    self.str.get(
                        "cmd-move-invalid-indexes",
                        "Sent indexes are outside of the playlist scope!",
                    ),
                    delete_after=30,
                )

        await self.safe_send_message(
            channel,
            self.str.get(
                "cmd-move-success",
                "Successfully moved the requested song from positon number {} in queue to position {}!",
            ).format(indexes[0] + 1, indexes[1] + 1),
            expire_in=30,
        ),

        song = player.playlist.delete_entry_at_index(indexes[0])

        player.playlist.insert_entry_at_index(indexes[1], song)

    async def _cmd_play_compound_link(
        self,
        message,
        player,
        channel,
        author,
        permissions,
        leftover_args,
        song_url,
        head,
    ):
        """
        Helper function to check for playlist IDs embeded in video links.
        If a "compound" URL is detected, ask the user if they want the
        associated playlist to be queued as well.
        """
        # TODO: maybe add config to auto yes or no and bypass this.
        # TODO: this currently will queue the original video twice.

        async def _prompt_for_playing(prompt: str, next_url: str):
            msg = await self.safe_send_message(channel, prompt)
            for r in [EMOJI_CHECK_MARK_BUTTON, EMOJI_CROSS_MARK_BUTTON]:
                await msg.add_reaction(r)

            def _check_react(reaction, user):
                return msg == reaction.message and author == user

            try:
                reaction, user = await self.wait_for(
                    "reaction_add", timeout=60, check=_check_react
                )
                if reaction.emoji == EMOJI_CHECK_MARK_BUTTON:
                    await self._cmd_play(
                        message,
                        player,
                        channel,
                        author,
                        permissions,
                        leftover_args,
                        next_url,
                        head,
                    )
                    await self.safe_delete_message(msg)
                elif reaction.emoji == EMOJI_CROSS_MARK_BUTTON:
                    await self.safe_delete_message(msg)
            except asyncio.TimeoutError:
                await self.safe_delete_message(msg)

        # Check for playlist in youtube watch link.
        playlist_regex = r"watch\?v=.+&(list=[^&]+)"
        matches = re.search(playlist_regex, song_url)
        if matches:
            pl_url = "https://www.youtube.com/playlist?" + matches.group(1)
            asyncio.ensure_future(
                _prompt_for_playing(
                    f"This link contains a Playlist ID:\n`{song_url}`\n\nDo you want to queue the playlist too?",
                    pl_url,
                )
            )

    async def _cmd_play(
        self,
        message,
        _player,
        channel,
        author,
        permissions,
        leftover_args,
        song_url,
        head,
        shuffle_entries: bool = False,
    ):
        """
        This function handles actually playing any given URL or song subject.

        Tested against these URLs:
        - https://www.youtube.com/watch?v=UBxIN7f1k30  # live stream that will be dead in the future.
        - https://www.youtube.com/playlist?list=PLBcHt8htZXKVCzW_Mkn4NrByBxn53o3cA   # 1373 videos, 8+ hours each, coffee house jazz.
        - https://www.youtube.com/playlist?list=PL80gRr4GwcsznLYH-G_FXnzkP5_cHl-KR
        - https://www.youtube.com/watch?v=bm48ncbhU10&list=PL80gRr4GwcsznLYH-G_FXnzkP5_cHl-KR
        - https://www.youtube.com/watch?v=bm48ncbhU10
        - https://youtu.be/L5uV3gmOH9g
        - https://open.spotify.com/playlist/37i9dQZF1DXaImRpG7HXqp
        - https://open.spotify.com/track/0YupMLYOYz6lZDbN3kRt7A?si=5b0eeb51b04c4af9
        - https://open.spotify.com/album/1y8Yw0NDcP2qxbZufIXt7u   # 1 item album
        - https://open.spotify.com/album/5LbHbwejgZXRZAgzVAjkhj   # multi-item album
        - https://soundcloud.com/neilcic/cabinet-man
        - https://soundcloud.com/grweston/sets/mashups
        - https://lemondemon.bandcamp.com/album/spirit-phone
        - slippery people talking heads live 84
        - ytsearch4:talking heads stop making sense
        - https://cdn.discordapp.com/attachments/741945274901200897/875075008723046410/cheesed.mp4
        - https://playerservices.streamtheworld.com/api/livestream-redirect/KUPDFM.mp3?dist=hubbard&source=hubbard-web&ttag=web&gdpr=0

        """
        player = _player if _player else None

        await channel.typing()

        if permissions.summonplay and not player:
            voice_channel = author.voice.channel if author.voice else None
            response = await self.cmd_summon(
                channel, channel.guild, author, voice_channel
            )  # @TheerapakG: As far as I know voice_channel param is unused
            if self.config.embeds:
                content = self._gen_embed()
                content.title = "summon"
                content.description = response.content
            else:
                content = response.content
            await self.safe_send_message(
                channel,
                content,
                expire_in=response.delete_after if self.config.delete_messages else 0,
            )
            player = self.get_player_in(channel.guild)

        if not player:
            raise exceptions.CommandError(
                "The bot is not in a voice channel.  "
                "Use %ssummon to summon it to your voice channel."
                % self._get_guild_cmd_prefix(channel.guild)
            )

        # Validate song_url is actually a URL, or otherwise a search string.
        valid_song_url = self.downloader.get_url_or_none(song_url)
        if valid_song_url:
            song_url = valid_song_url

            # Handle if the link has a playlist ID in addition to a video ID.
            await self._cmd_play_compound_link(
                message,
                player,
                channel,
                author,
                permissions,
                leftover_args,
                song_url,
                head,
            )

        if not valid_song_url and leftover_args:
            # treat all arguments as a search string.
            song_url = " ".join([song_url, *leftover_args])
            leftover_args = None  # prevent issues later.

        # Validate spotify links are supported before we try them.
        if "open.spotify.com" in song_url.lower():
            if self.config._spotify:
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
                raise exceptions.CommandError(e)

            if not info:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-play-noinfo",
                        "That video cannot be played. Try using the {0}stream command.",
                    ).format(self._get_guild_cmd_prefix(channel.guild)),
                    expire_in=30,
                )

            # ensure the extractor has been allowed via permissions.
            if info.extractor not in permissions.extractors and permissions.extractors:
                raise exceptions.PermissionsError(
                    self.str.get(
                        "cmd-play-badextractor",
                        "You do not have permission to play the requested media. Service `{}` is not permitted.",
                    ).format(info.extractor),
                    expire_in=30,
                )

            # if the result has "entries" but it's empty, it might be a failed search.
            if "entries" in info and not info.entry_count:
                if info.extractor == "youtube:search":
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
                    info, channel=channel, author=author, head=False
                )

                time_taken = time.time() - start_time
                listlen = len(entry_list)

                log.info(
                    "Processed {} of {} songs in {:.3f} seconds at {:.2f}s/song".format(
                        listlen,
                        num_songs,
                        time_taken,
                        time_taken / listlen if listlen else 1,
                    )
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
                if info.get("extractor", "") == "youtube:playlist":
                    log.noise(
                        "Extracted an entry with youtube:playlist as extractor key"
                    )

                if (
                    permissions.max_song_length
                    and info.get("duration", 0) > permissions.max_song_length
                ):
                    raise exceptions.PermissionsError(
                        self.str.get(
                            "cmd-play-song-limit",
                            "Song duration exceeds limit ({0} > {1})",
                        ).format(info["duration"], permissions.max_song_length),
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

            if position == 1 and player.is_stopped:
                position = self.str.get("cmd-play-next", "Up next!")
                reply_text %= (btext, position)

            else:
                reply_text %= (btext, position)
                try:
                    time_until = await player.playlist.estimate_time_until(
                        position, player
                    )
                    reply_text += self.str.get(
                        "cmd-play-eta", " - estimated time until playing: %s"
                    ) % ftimedelta(time_until)
                except exceptions.InvalidDataError:
                    reply_text += self.str.get(
                        "cmd-play-eta-error", " - cannot estimate time until playing"
                    )
                except Exception:
                    log.exception("Unhandled exception in _cmd_play time until play.")

        return Response(reply_text, delete_after=30)

    async def cmd_stream(self, _player, channel, author, permissions, song_url):
        """
        Usage:
            {command_prefix}stream song_link

        Enqueue a media stream.
        This could mean an actual stream like Twitch or shoutcast, or simply streaming
        media without predownloading it.  Note: FFmpeg is notoriously bad at handling
        streams, especially on poor connections.  You have been warned.
        """

        await self._do_cmd_unpause_check(_player, channel)

        if _player:
            player = _player
        elif permissions.summonplay:
            vc = author.voice.channel if author.voice else None
            response = await self.cmd_summon(
                channel, channel.guild, author, vc
            )  # @TheerapakG: As far as I know voice_channel param is unused
            if self.config.embeds:
                content = self._gen_embed()
                content.title = "summon"
                content.description = response.content
            else:
                content = response.content
            await self.safe_send_message(
                channel,
                content,
                expire_in=response.delete_after if self.config.delete_messages else 0,
            )
            player = self.get_player_in(channel.guild)

        if not player:
            raise exceptions.CommandError(
                "The bot is not in a voice channel.  "
                "Use %ssummon to summon it to your voice channel."
                % self._get_guild_cmd_prefix(channel.guild)
            )

        if (
            permissions.max_songs
            and player.playlist.count_for_user(author) >= permissions.max_songs
        ):
            raise exceptions.PermissionsError(
                self.str.get(
                    "cmd-stream-limit",
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

        async with channel.typing():
            # TODO: find more streams to test.
            # NOTE: this WILL return a link if ytdlp does not support the service.
            try:
                info = await self.downloader.extract_info(
                    song_url, download=False, process=True, as_stream=True
                )
            except Exception as e:
                log.exceptions(
                    f"Failed to get info from the stream request: {song_url}"
                )
                raise exceptions.CommandError(e)

            if info.has_entries:
                raise exceptions.CommandError(
                    "Streaming playlists is not yet supported.",
                    expire_in=30,
                )
                # TODO: could process these and force them to be stream entries...

            await player.playlist.add_stream_from_info(
                info, channel=channel, author=author, head=False
            )

        return Response(
            self.str.get("cmd-stream-success", "Streaming."), delete_after=6
        )

    async def cmd_search(
        self,
        message: discord.Message,
        player: MusicPlayer,
        channel: discord.abc.GuildChannel,
        author: discord.abc.User,
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
                            command_prefix=self._get_guild_cmd_prefix(channel.guild)
                        )
                    ),
                    expire_in=60,
                )

        argcheck()

        try:
            leftover_args = shlex.split(" ".join(leftover_args))
        except ValueError:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-search-noquote", "Please quote your search query properly."
                ),
                expire_in=30,
            )

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
        # and have a better idea on how to do this, i'd be delighted to know.
        # I don't want to just do ' '.join(leftover_args).strip("\"'")
        # Because that eats both quotes if they're there
        # where I only want to eat the outermost ones
        if leftover_args[0][0] in "'\"":
            lchar = leftover_args[0][0]
            leftover_args[0] = leftover_args[0].lstrip(lchar)
            leftover_args[-1] = leftover_args[-1].rstrip(lchar)

        search_query = "%s%s:%s" % (
            services[service],
            items_requested,
            " ".join(leftover_args),
        )

        search_msg = await self.safe_send_message(
            channel, self.str.get("cmd-search-searching", "Searching for videos...")
        )
        if isinstance(channel, discord.abc.Messageable):
            await channel.typing()

        try:
            info = await self.downloader.extract_info(
                search_query, download=False, process=True
            )

        except Exception as e:
            await self.safe_edit_message(search_msg, str(e), send_if_fail=True)
            return None
        else:
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
                        format_song_duration(
                            ftimedelta(timedelta(seconds=entry["duration"]))
                        ),
                    )
                )
            # This combines the formatted result strings into one list.
            result_string = "\n".join(
                "{0}".format(result) for result in result_message_array
            )
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

            # Check to verify that recived message is valid.
            def check(reply):
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
                await self.safe_delete_message(result_message)
                return None

            if choice.content == "0":
                # Choice 0 will cancel the search
                if self.config.delete_invoking:
                    await self.safe_delete_message(choice)
                await self.safe_delete_message(result_message)
            else:
                # Here we have a valid choice lets queue it.
                if self.config.delete_invoking:
                    await self.safe_delete_message(choice)
                await self.safe_delete_message(result_message)
                await self.cmd_play(
                    message,
                    player,
                    channel,
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
                else:
                    return Response(
                        self.str.get(
                            "cmd-search-accept-list-noembed", "{0} added to queue"
                        ).format(entries[int(choice.content) - 1]["title"]),
                        delete_after=30,
                    )
        else:
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

                def check_react(reaction, user) -> bool:
                    return (
                        user == message.author
                        and reaction.message.id == result_message.id
                    )  # why can't these objs be compared directly?

                reactions = ["\u2705", "\U0001F6AB", "\U0001F3C1"]
                for r in reactions:
                    await result_message.add_reaction(r)

                try:
                    reaction, user = await self.wait_for(
                        "reaction_add", timeout=30.0, check=check_react
                    )
                except asyncio.TimeoutError:
                    await self.safe_delete_message(result_message)
                    return None

                if str(reaction.emoji) == "\u2705":  # check
                    await self.safe_delete_message(result_message)
                    await self.cmd_play(
                        message,
                        player,
                        channel,
                        author,
                        permissions,
                        [],
                        entry["url"],
                    )
                    return Response(
                        self.str.get("cmd-search-accept", "Alright, coming right up!"),
                        delete_after=30,
                    )
                elif str(reaction.emoji) == "\U0001F6AB":  # cross
                    await self.safe_delete_message(result_message)
                else:
                    await self.safe_delete_message(result_message)

        return Response(
            self.str.get("cmd-search-decline", "Oh well :("), delete_after=30
        )

    async def cmd_np(self, player, channel, guild, message):
        """
        Usage:
            {command_prefix}np

        Displays the current song in chat.
        """

        if player.current_entry:
            if self.server_specific_data[guild.id]["last_np_msg"]:
                await self.safe_delete_message(
                    self.server_specific_data[guild.id]["last_np_msg"]
                )
                self.server_specific_data[guild.id]["last_np_msg"] = None

            # TODO: Fix timedelta garbage with util function
            song_progress = ftimedelta(timedelta(seconds=player.progress))
            song_total = (
                ftimedelta(timedelta(seconds=player.current_entry.duration))
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
            if player.current_entry.duration and player.current_entry.duration > 0:
                percentage = player.progress / player.current_entry.duration

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
            entry_author = player.current_entry.meta.get("author", None)

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

            if self.config.embeds:
                content = self._gen_embed()
                content.add_field(
                    name=f"Currently {action_text}", value=entry.title, inline=False
                )
                if entry_author:
                    content.add_field(
                        name="Added By:", value=entry_author.name, inline=False
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
                    log.warning(f"No thumbnail set for entry with url: {entry.url}")

            self.server_specific_data[guild.id][
                "last_np_msg"
            ] = await self.safe_send_message(
                channel, content if self.config.embeds else np_text, expire_in=30
            )
        else:
            return Response(
                self.str.get(
                    "cmd-np-none",
                    "There are no songs queued! Queue something with {0}play.",
                ).format(self._get_guild_cmd_prefix(channel.guild)),
                delete_after=30,
            )

    async def cmd_summon(self, channel, guild, author, voice_channel):
        """
        Usage:
            {command_prefix}summon

        Call the bot to the summoner's voice channel.
        """

        # @TheerapakG: Maybe summon should have async lock?

        if not author.voice:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-summon-novc",
                    "You are not connected to voice. Try joining a voice channel!",
                )
            )

        voice_client = self.voice_client_in(guild)
        if voice_client and guild == author.voice.channel.guild:
            await voice_client.move_to(author.voice.channel)
        else:
            # move to _verify_vc_perms?
            chperms = author.voice.channel.permissions_for(guild.me)

            if not chperms.connect:
                log.warning(
                    "Cannot join channel '{0}', no permission.".format(
                        author.voice.channel.name
                    )
                )
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-summon-noperms-connect",
                        "Cannot join channel `{0}`, no permission to connect.",
                    ).format(author.voice.channel.name),
                    expire_in=25,
                )

            elif not chperms.speak:
                log.warning(
                    "Cannot join channel '{0}', no permission to speak.".format(
                        author.voice.channel.name
                    )
                )
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-summon-noperms-speak",
                        "Cannot join channel `{0}`, no permission to speak.",
                    ).format(author.voice.channel.name),
                    expire_in=25,
                )

            player = await self.get_player(
                author.voice.channel,
                create=True,
                deserialize=self.config.persistent_queue,
            )

            if player.is_stopped:
                player.play()

            if self.config.auto_playlist:
                await self.on_player_finished_playing(player)

        log.info("Joining {0.guild.name}/{0.name}".format(author.voice.channel))

        return Response(
            self.str.get("cmd-summon-reply", "Connected to `{0.name}`").format(
                author.voice.channel
            ),
            delete_after=30,
        )

    async def cmd_pause(self, player):
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
                )
            )

        else:
            raise exceptions.CommandError(
                self.str.get("cmd-pause-none", "Player is not playing."), expire_in=30
            )

    async def cmd_resume(self, player):
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
        elif player.is_stopped and player.playlist:
            player.play()
        else:
            raise exceptions.CommandError(
                self.str.get("cmd-resume-none", "Player is not paused."), expire_in=30
            )

    async def cmd_shuffle(self, channel, player):
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

        for x in range(4):
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

    async def cmd_clear(self, guild, player, author):
        """
        Usage:
            {command_prefix}clear

        Clears the playlist.
        """

        player.playlist.clear()

        return Response(
            self.str.get("cmd-clear-reply", "Cleared `{0}`'s queue").format(
                player.voice_client.channel.guild
            ),
            delete_after=20,
        )

    async def cmd_remove(
        self, user_mentions, message, author, permissions, channel, player, index=None
    ):
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
                            e
                            for e in player.playlist.entries
                            if e.meta.get("author", None) == user
                        ]
                        for entry in entry_indexes:
                            player.playlist.entries.remove(entry)
                        entry_text = "%s " % len(entry_indexes) + "item"
                        if len(entry_indexes) > 1:
                            entry_text += "s"
                        return Response(
                            self.str.get(
                                "cmd-remove-reply", "Removed `{0}` added by `{1}`"
                            )
                            .format(entry_text, user.name)
                            .strip()
                        )

                    except ValueError:
                        raise exceptions.CommandError(
                            self.str.get(
                                "cmd-remove-missing",
                                "Nothing found in the queue from user `%s`",
                            )
                            % user.name,
                            expire_in=20,
                        )

                raise exceptions.PermissionsError(
                    self.str.get(
                        "cmd-remove-noperms",
                        "You do not have the valid permissions to remove that entry from the queue, make sure you're the one who queued it or have instant skip permissions",
                    ),
                    expire_in=20,
                )

        if not index:
            index = len(player.playlist.entries)

        try:
            index = int(index)
        except (TypeError, ValueError):
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-remove-invalid",
                    "Invalid number. Use {}queue to find queue positions.",
                ).format(self._get_guild_cmd_prefix(channel.guild)),
                expire_in=20,
            )

        if index > len(player.playlist.entries):
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-remove-invalid",
                    "Invalid number. Use {}queue to find queue positions.",
                ).format(self._get_guild_cmd_prefix(channel.guild)),
                expire_in=20,
            )

        if permissions.remove or author == player.playlist.get_entry_at_index(
            index - 1
        ).meta.get("author", None):
            entry = player.playlist.delete_entry_at_index((index - 1))
            if entry.meta.get("channel", False) and entry.meta.get("author", False):
                return Response(
                    self.str.get(
                        "cmd-remove-reply-author", "Removed entry `{0}` added by `{1}`"
                    )
                    .format(entry.title, entry.meta["author"].name)
                    .strip()
                )
            else:
                return Response(
                    self.str.get("cmd-remove-reply-noauthor", "Removed entry `{0}`")
                    .format(entry.title)
                    .strip()
                )
        else:
            raise exceptions.PermissionsError(
                self.str.get(
                    "cmd-remove-noperms",
                    "You do not have the valid permissions to remove that entry from the queue, make sure you're the one who queued it or have instant skip permissions",
                ),
                expire_in=20,
            )

    async def cmd_skip(
        self, player, channel, author, message, permissions, voice_channel, param=""
    ):
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
            if player.playlist.peek():
                if player.playlist.peek()._is_downloading:
                    return Response(
                        self.str.get(
                            "cmd-skip-dl",
                            "The next song (`%s`) is downloading, please wait.",
                        )
                        % player.playlist.peek().title
                    )

                elif player.playlist.peek().is_downloaded:
                    return Response(
                        "The next song will be played shortly.  Please wait."
                    )
                else:
                    return Response(
                        "Something odd is happening.  "
                        "You might want to restart the bot if it doesn't start working."
                    )
            else:
                return Response(
                    "Something strange is happening.  "
                    "You might want to restart the bot if it doesn't start working."
                )

        current_entry = player.current_entry
        entry_author = current_entry.meta.get("author", None)
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
                and not permissions.skiplooped
                and player.repeatsong
            ):
                raise exceptions.PermissionsError(
                    self.str.get(
                        "cmd-skip-force-noperms-looped-song",
                        "You do not have permission to force skip a looped song.",
                    )
                )
            else:
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

        num_voice = sum(
            1
            for m in voice_channel.members
            if not (m.voice.deaf or m.voice.self_deaf or m == self.user)
        )
        if num_voice == 0:
            num_voice = 1  # incase all users are deafened, to avoid divison by zero

        player.skip_state.add_skipper(author.id, message)
        num_skips = sum(
            1
            for m in voice_channel.members
            if not (m.voice.deaf or m.voice.self_deaf or m == self.user)
            and m.id in player.skip_state.skippers
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
            if not permissions.skiplooped and player.repeatsong:
                raise exceptions.PermissionsError(
                    self.str.get(
                        "cmd-skip-vote-noperms-looped-song",
                        "You do not have permission to skip a looped song.",
                    )
                )
            else:
                if player.repeatsong:
                    player.repeatsong = False
            # check autopause stuff here
            # @TheerapakG: Check for pausing state in the player.py make more sense
            player.skip()
            return Response(
                self.str.get(
                    "cmd-skip-reply-skipped-1",
                    "Your skip for `{0}` was acknowledged.\nThe vote to skip has been passed.{1}",
                ).format(
                    current_entry.title,
                    self.str.get("cmd-skip-reply-skipped-2", " Next song coming up!")
                    if player.playlist.peek()
                    else "",
                ),
                reply=True,
                delete_after=20,
            )

        else:
            # TODO: When a song gets skipped, delete the old x needed to skip messages
            if not permissions.skiplooped and player.repeatsong:
                raise exceptions.PermissionsError(
                    self.str.get(
                        "cmd-skip-vote-noperms-looped-song",
                        "You do not have permission to skip a looped song.",
                    )
                )
            else:
                if player.repeatsong:
                    player.repeatsong = False
                return Response(
                    self.str.get(
                        "cmd-skip-reply-voted-1",
                        "Your skip for `{0}` was acknowledged.\n**{1}** more {2} required to vote to skip this song.",
                    ).format(
                        current_entry.title,
                        skips_remaining,
                        self.str.get("cmd-skip-reply-voted-2", "person is")
                        if skips_remaining == 1
                        else self.str.get("cmd-skip-reply-voted-3", "people are"),
                    ),
                    reply=True,
                    delete_after=20,
                )

    async def cmd_volume(self, message, player, new_volume=None):
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
            new_volume = int(new_volume)

        except ValueError:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-volume-invalid", "`{0}` is not a valid number"
                ).format(new_volume),
                expire_in=20,
            )

        vol_change = None
        if relative:
            vol_change = new_volume
            new_volume += player.volume * 100

        old_volume = int(player.volume * 100)

        if 0 < new_volume <= 100:
            player.volume = new_volume / 100.0

            return Response(
                self.str.get("cmd-volume-reply", "Updated volume from **%d** to **%d**")
                % (old_volume, new_volume),
                reply=True,
                delete_after=20,
            )

        else:
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
            else:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-volume-unreasonable-absolute",
                        "Unreasonable volume provided: {}%. Provide a value between 1 and 100.",
                    ).format(new_volume),
                    expire_in=20,
                )

    @owner_only
    async def cmd_option(self, player, option, value):
        """
        Usage:
            {command_prefix}option [option] [on/y/enabled/off/n/disabled]

        Changes a config option without restarting the bot. Changes aren't permanent and
        only last until the bot is restarted. To make permanent changes, edit the
        config file.

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
                else:
                    if not self.autoplaylist:
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
                else:
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
        else:
            is_generic = [
                o for o in generic if o == option
            ]  # check if it is a generic bool option
            if is_generic and (value in bool_y or value in bool_n):
                name = is_generic[0]
                log.debug("Setting attribute {0}".format(name))
                setattr(
                    self.config, name, True if value in bool_y else False
                )  # this is scary but should work
                attr = getattr(self.config, name)
                res = (
                    "The option {0} is now ".format(option)
                    + ["disabled", "enabled"][attr]
                    + "."
                )
                log.warning("Option overriden for this session: {0}".format(res))
                return Response(res)
            else:
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-option-invalid-param",
                        "The parameters provided were invalid.",
                    )
                )

    @owner_only
    async def cmd_cache(self, leftover_args, opt="info"):
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
                else:
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

    async def cmd_queue(self, channel, player):
        """
        Usage:
            {command_prefix}queue

        Prints the current song queue.
        """

        lines = []
        unlisted = 0
        andmoretext = "* ... and %s more*" % ("x" * len(player.playlist.entries))

        if player.is_playing:
            # TODO: Fix timedelta garbage with util function
            song_progress = ftimedelta(timedelta(seconds=player.progress))
            song_total = (
                ftimedelta(timedelta(seconds=player.current_entry.duration))
                if player.current_entry.duration is not None
                else "(no duration data)"
            )
            prog_str = "`[%s/%s]`" % (song_progress, song_total)

            if player.current_entry.meta.get(
                "channel", False
            ) and player.current_entry.meta.get("author", False):
                lines.append(
                    self.str.get(
                        "cmd-queue-playing-author",
                        "Currently playing: `{0}` added by `{1}` {2}\n",
                    ).format(
                        player.current_entry.title,
                        player.current_entry.meta["author"].name,
                        prog_str,
                    )
                )
            else:
                lines.append(
                    self.str.get(
                        "cmd-queue-playing-noauthor", "Currently playing: `{0}` {1}\n"
                    ).format(player.current_entry.title, prog_str)
                )

        for i, item in enumerate(player.playlist, 1):
            if item.meta.get("channel", False) and item.meta.get("author", False):
                nextline = (
                    self.str.get("cmd-queue-entry-author", "{0} -- `{1}` by `{2}`")
                    .format(i, item.title, item.meta["author"].name)
                    .strip()
                )
            else:
                nextline = (
                    self.str.get("cmd-queue-entry-noauthor", "{0} -- `{1}`")
                    .format(i, item.title)
                    .strip()
                )

            currentlinesum = sum(len(x) + 1 for x in lines)  # +1 is for newline char

            if (
                currentlinesum + len(nextline) + len(andmoretext)
                > DISCORD_MSG_CHAR_LIMIT
            ) or (i > self.config.queue_length):
                if currentlinesum + len(andmoretext):
                    unlisted += 1
                    continue

            lines.append(nextline)

        if unlisted:
            lines.append(self.str.get("cmd-queue-more", "\n... and %s more") % unlisted)

        if not lines:
            lines.append(
                self.str.get(
                    "cmd-queue-none",
                    "There are no songs queued! Queue something with {}play.",
                ).format(self._get_guild_cmd_prefix(channel.guild))
            )

        message = "\n".join(lines)
        return Response(message, delete_after=30)

    async def cmd_clean(self, message, channel, guild, author, search_range=50):
        """
        Usage:
            {command_prefix}clean [range]

        Removes up to [range] messages the bot has posted in chat. Default: 50, Max: 1000
        """

        try:
            float(search_range)  # lazy check
            search_range = min(int(search_range), 1000)
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

        def is_possible_command_invoke(entry):
            prefix_list = [self._get_guild_cmd_prefix(channel.guild)] + list(
                self.server_specific_data[channel.guild.id]["session_prefix_history"]
            )
            # The semi-cursed use of [^ -~] should match all kinds of unicode, which could be an issue.
            # If it is a problem, the best solution is probably adding a dependency for emoji.
            emoji_regex = re.compile(r"^(<a?:.+:\d+>|:.+:|[^ -~]+) \w+")
            content = entry.content
            for prefix in prefix_list:
                if entry.content.startswith(prefix):
                    # emoji prefix may have exactly one space.
                    if emoji_regex.match(entry.content):
                        return True
                    content = content.replace(prefix, "")
                    if content and not content[0].isspace():
                        return True
            return False

        delete_invokes = True
        delete_all = (
            channel.permissions_for(author).manage_messages
            or self.config.owner_id == author.id
        )

        def check(message):
            if is_possible_command_invoke(message) and delete_invokes:
                return delete_all or message.author == author
            return message.author == self.user

        if self.user.bot:
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

    async def cmd_pldump(self, channel, author, song_url):
        """
        Usage:
            {command_prefix}pldump url

        Dumps the individual urls of a playlist
        """

        song_url = self.downloader.get_url_or_none(song_url)
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
                "Could not extract info from input url\n%s\n" % e, expire_in=25
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
                await author.send(
                    msg_str,
                    file=datafile,
                )

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

    async def cmd_listids(self, guild, author, leftover_args, cat="all"):
        """
        Usage:
            {command_prefix}listids [categories]

        Lists the ids for various things.  Categories are:
           all, users, roles, channels
        """

        cats = ["channels", "roles", "users"]

        if cat not in cats and cat != "all":
            return Response(
                "Valid categories: " + " ".join(["`%s`" % c for c in cats]),
                reply=True,
                delete_after=25,
            )

        if cat == "all":
            requested_cats = cats
        else:
            requested_cats = [cat] + [c.strip(",") for c in leftover_args]

        data = ["Your ID: %s" % author.id]

        for cur_cat in requested_cats:
            rawudata = None

            if cur_cat == "users":
                data.append("\nUser IDs:")
                rawudata = [
                    "%s #%s: %s" % (m.name, m.discriminator, m.id)
                    for m in guild.members
                ]

            elif cur_cat == "roles":
                data.append("\nRole IDs:")
                rawudata = ["%s: %s" % (r.name, r.id) for r in guild.roles]

            elif cur_cat == "channels":
                data.append("\nText Channel IDs:")
                tchans = [
                    c for c in guild.channels if isinstance(c, discord.TextChannel)
                ]
                rawudata = ["%s: %s" % (c.name, c.id) for c in tchans]

                rawudata.append("\nVoice Channel IDs:")
                vchans = [
                    c for c in guild.channels if isinstance(c, discord.VoiceChannel)
                ]
                rawudata.extend("%s: %s" % (c.name, c.id) for c in vchans)

            if rawudata:
                data.extend(rawudata)

        with BytesIO() as sdata:
            sdata.writelines(d.encode("utf8") + b"\n" for d in data)
            sdata.seek(0)

            await author.send(
                file=discord.File(
                    sdata,
                    filename="%s-ids-%s.txt" % (slugify(guild.name), cat),
                )
            )

        return Response("Sent a message with a list of IDs.", delete_after=20)

    async def cmd_perms(
        self, author, user_mentions, channel, guild, message, permissions, target=None
    ):
        """
        Usage:
            {command_prefix}perms [@user]
        Sends the user a list of their permissions, or the permissions of the user specified.
        """

        if user_mentions:
            user = user_mentions[0]

        if not user_mentions and not target:
            user = author

        if not user_mentions and target:
            user = guild.get_member_named(target)
            if user is None:
                try:
                    user = await self.fetch_user(target)
                except discord.NotFound:
                    return Response(
                        "Invalid user ID or server nickname, please double check all typing and try again.",
                        reply=False,
                        delete_after=30,
                    )

        permissions = self.permissions.for_user(user)

        if user == author:
            lines = ["Command permissions in %s\n" % guild.name, "```", "```"]
        else:
            lines = [
                "Command permissions for {} in {}\n".format(user.name, guild.name),
                "```",
                "```",
            ]

        for perm in permissions.__dict__:
            if perm in ["user_list"] or permissions.__dict__[perm] == set():
                continue
            lines.insert(len(lines) - 1, "%s: %s" % (perm, permissions.__dict__[perm]))

        await self.safe_send_message(author, "\n".join(lines))
        return Response("\N{OPEN MAILBOX WITH RAISED FLAG}", delete_after=20)

    @owner_only
    async def cmd_setname(self, leftover_args, name):
        """
        Usage:
            {command_prefix}setname name

        Changes the bot's username.
        Note: This operation is limited by discord to twice per hour.
        """

        name = " ".join([name, *leftover_args])

        try:
            await self.user.edit(username=name)

        except discord.HTTPException:
            raise exceptions.CommandError(
                "Failed to change name. Did you change names too many times?  "
                "Remember name changes are limited to twice per hour."
            )

        except Exception as e:
            raise exceptions.CommandError(e, expire_in=20)

        return Response(
            "Set the bot's username to **{0}**".format(name), delete_after=20
        )

    async def cmd_setnick(self, guild, channel, leftover_args, nick):
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
            raise exceptions.CommandError(e, expire_in=20)

        return Response("Set the bot's nickname to `{0}`".format(nick), delete_after=20)

    async def cmd_setprefix(self, guild, leftover_args, prefix):
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
                e_name, e_id = emoji_match.groups()
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
                self.server_specific_data[guild.id]["command_prefix"] = None
                await self._save_guild_options(guild)
                return Response(
                    self.str.get(
                        "cmd-setprefix-cleared",
                        "Server command prefix is cleared.",
                    )
                )

            old_prefix = self._get_guild_cmd_prefix(guild)
            self.server_specific_data[guild.id]["command_prefix"] = prefix
            self.server_specific_data[guild.id]["session_prefix_history"].add(
                old_prefix
            )
            if len(self.server_specific_data[guild.id]["session_prefix_history"]) > 3:
                self.server_specific_data[guild.id]["session_prefix_history"].pop()
            await self._save_guild_options(guild)
            return Response(
                self.str.get(
                    "cmd-setprefix-changed",
                    "Server command prefix is now:  {0}",
                ).format(prefix),
                delete_after=60,
            )
        else:
            raise exceptions.CommandError(
                self.str.get(
                    "cmd-setprefix-disabled",
                    "Prefix per server is not enabled!",
                ),
                expire_in=30,
            )

    @owner_only
    async def cmd_setavatar(self, message, url=None):
        """
        Usage:
            {command_prefix}setavatar [url]

        Changes the bot's avatar.
        Attaching a file and leaving the url parameter blank also works.
        """

        if message.attachments:
            thing = message.attachments[0].url
        elif url:
            thing = url.strip("<>")
        else:
            raise exceptions.CommandError(
                "You must provide a URL or attach a file.", expire_in=20
            )

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(thing, timeout=timeout) as res:
                await self.user.edit(avatar=await res.read())

        except Exception as e:
            raise exceptions.CommandError(
                "Unable to change avatar: {}".format(e), expire_in=20
            )

        return Response("Changed the bot's avatar.", delete_after=20)

    async def cmd_disconnect(self, guild):
        """
        Usage:
            {command_prefix}disconnect

        Forces the bot leave the current voice channel.
        """
        await self.disconnect_voice_client(guild)
        return Response("Disconnected from `{0.name}`".format(guild), delete_after=20)

    async def cmd_restart(self, _player, channel, leftover_args, opt="soft"):
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
                    "Invalid option given, use: soft, full, upgrade, uppip, or upgit",
                ),
                expire_in=30,
            )
        elif opt == "soft":
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
        elif opt == "full":
            raise exceptions.RestartSignal(code=exceptions.RestartCode.RESTART_FULL)
        elif opt == "upgrade":
            raise exceptions.RestartSignal(
                code=exceptions.RestartCode.RESTART_UPGRADE_ALL
            )
        elif opt == "uppip":
            raise exceptions.RestartSignal(
                code=exceptions.RestartCode.RESTART_UPGRADE_PIP
            )
        elif opt == "upgit":
            raise exceptions.RestartSignal(
                code=exceptions.RestartCode.RESTART_UPGRADE_GIT
            )

    async def cmd_shutdown(self, channel):
        """
        Usage:
            {command_prefix}shutdown

        Disconnects from voice channels and closes the bot process.
        """
        await self.safe_send_message(channel, "\N{WAVING HAND SIGN}")

        player = self.get_player_in(channel.guild)
        if player and player.is_paused:
            player.resume()

        await self.disconnect_all_voice_clients()
        raise exceptions.TerminateSignal()

    async def cmd_leaveserver(self, val, leftover_args):
        """
        Usage:
            {command_prefix}leaveserver <name/ID>

        Forces the bot to leave a server.
        When providing names, names are case-sensitive.
        """
        if leftover_args:
            val = " ".join([val, *leftover_args])

        t = self.get_guild(val)
        if t is None:
            # Get guild by name
            t = discord.utils.get(self.guilds, name=val)
            if t is None:
                # Get guild by snowflake
                try:
                    t = discord.utils.get(self.guilds, id=int(val))
                except ValueError:
                    pass

                if t is None:
                    raise exceptions.CommandError(
                        "No guild was found with the ID or name as `{0}`".format(val)
                    )
        await t.leave()
        return Response(
            "Left the guild: `{0.name}` (Owner: `{0.owner.name}`, ID: `{0.id}`)".format(
                t
            )
        )

    @dev_only
    async def cmd_breakpoint(self, message):
        log.critical("Activating debug breakpoint")
        return

    @dev_only
    async def cmd_objgraph(self, channel, func="most_common_types()"):
        import objgraph

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
            data = eval("objgraph." + func)

        return Response(data, codeblock="py")

    @dev_only
    async def cmd_debug(self, message, _player, *, data):
        codeblock = "```py\n{}\n```"
        result = None

        if data.startswith("```") and data.endswith("```"):
            data = "\n".join(data.rstrip("`\n").split("\n")[1:])

        code = data.strip("` \n")

        scope = globals().copy()
        scope.update({"self": self})

        try:
            result = eval(code, scope)
        except Exception:
            try:
                exec(code, scope)
            except Exception as e:
                traceback.print_exc(chain=False)
                return Response("{}: {}".format(type(e).__name__, e))

        if asyncio.iscoroutine(result):
            result = await result

        return Response(codeblock.format(result))

    async def cmd_testready(self, message, channel):
        # pointedly undocumented command that just echos text :)
        await self.safe_send_message(channel, "!!RUN_TESTS!!", expire_in=30)

    async def on_message(self, message):
        await self.wait_until_ready()

        command_prefix = self._get_guild_cmd_prefix(message.channel.guild)
        message_content = message.content.strip()
        # if the prefix is an emoji, silently remove the space often auto-inserted after it.
        # this regex will get us close enough to knowing if an unicode emoji is in the prefix...
        emoji_regex = re.compile(r"^(<a?:.+:\d+>|:.+:|[^ -~]+)$")
        if emoji_regex.match(command_prefix):
            message_content = message_content.replace(
                f"{command_prefix} ", command_prefix
            )

        if not message_content.startswith(command_prefix):
            return

        if message.author == self.user:
            log.warning("Ignoring command from myself ({})".format(message.content))
            return

        if (
            message.author.bot
            and message.author.id not in self.config.bot_exception_ids
        ):
            log.warning("Ignoring command from other bot ({})".format(message.content))
            return

        if (not isinstance(message.channel, discord.abc.GuildChannel)) and (
            not isinstance(message.channel, discord.abc.PrivateChannel)
        ):
            return

        command, *args = message_content.split(
            " "
        )  # Uh, doesn't this break prefixes with spaces in them (it doesn't, config parser already breaks them)
        command = command[len(command_prefix) :].lower().strip()

        # [] produce [''] which is not what we want (it break things)
        if args:
            args = " ".join(args).lstrip(" ").split(" ")
        else:
            args = []

        handler = getattr(self, "cmd_" + command, None)
        if not handler:
            # alias handler
            if self.config.usealias:
                command = self.aliases.get(command)
                handler = getattr(self, "cmd_" + command, None)
                if not handler:
                    return
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
            and message.channel.id not in self.config.bound_channels
        ):
            if self.config.unbound_servers:
                for channel in message.guild.channels:
                    if channel.id in self.config.bound_channels:
                        return
            else:
                return  # if I want to log this I just move it under the prefix check

        if (
            message.author.id in self.blacklist
            and message.author.id != self.config.owner_id
        ):
            log.warning(
                "User blacklisted: {0.id}/{0!s} ({1})".format(message.author, command)
            )
            return

        else:
            log.info(
                "{0.id}/{0!s}: {1}".format(
                    message.author, message_content.replace("\n", "\n... ")
                )
            )

        user_permissions = self.permissions.for_user(message.author)

        argspec = inspect.signature(handler)
        params = argspec.parameters.copy()

        sentmsg = response = None

        # noinspection PyBroadException
        try:
            if (
                user_permissions.ignore_non_voice
                and command in user_permissions.ignore_non_voice
            ):
                await self._check_ignore_non_voice(message)

            handler_kwargs = {}
            if params.pop("message", None):
                handler_kwargs["message"] = message

            if params.pop("channel", None):
                handler_kwargs["channel"] = message.channel

            if params.pop("author", None):
                handler_kwargs["author"] = message.author

            if params.pop("guild", None):
                handler_kwargs["guild"] = message.guild

            if params.pop("player", None):
                handler_kwargs["player"] = await self.get_player(message.channel)

            if params.pop("_player", None):
                handler_kwargs["_player"] = self.get_player_in(message.guild)

            if params.pop("permissions", None):
                handler_kwargs["permissions"] = user_permissions

            if params.pop("user_mentions", None):
                handler_kwargs["user_mentions"] = list(
                    map(message.guild.get_member, message.raw_mentions)
                )

            if params.pop("channel_mentions", None):
                handler_kwargs["channel_mentions"] = list(
                    map(message.guild.get_channel, message.raw_channel_mentions)
                )

            if params.pop("voice_channel", None):
                handler_kwargs["voice_channel"] = (
                    message.guild.me.voice.channel if message.guild.me.voice else None
                )

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
                    "[{}={}]".format(key, param.default)
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

            if message.author.id != self.config.owner_id:
                if (
                    user_permissions.command_whitelist
                    and command not in user_permissions.command_whitelist
                ):
                    raise exceptions.PermissionsError(
                        "This command is not enabled for your group ({}).".format(
                            user_permissions.name
                        ),
                        expire_in=20,
                    )

                elif (
                    user_permissions.command_blacklist
                    and command in user_permissions.command_blacklist
                ):
                    raise exceptions.PermissionsError(
                        "This command is disabled for your group ({}).".format(
                            user_permissions.name
                        ),
                        expire_in=20,
                    )

            # Invalid usage, return docstring
            if params:
                docs = getattr(handler, "__doc__", None)
                if not docs:
                    docs = "Usage: {}{} {}".format(
                        command_prefix, command, " ".join(args_expected)
                    )

                docs = dedent(docs)
                await self.safe_send_message(
                    message.channel,
                    "```\n{}\n```".format(docs.format(command_prefix=command_prefix)),
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
                else:
                    content = response.content

                if response.reply:
                    if isinstance(content, discord.Embed):
                        content.description = "{} {}".format(
                            message.author.mention,
                            content.description,
                        )
                    else:
                        content = "{}: {}".format(message.author.mention, content)

                sentmsg = await self.safe_send_message(
                    message.channel,
                    content,
                    expire_in=response.delete_after
                    if self.config.delete_messages
                    else 0,
                    also_delete=message if self.config.delete_invoking else None,
                )

        except (
            exceptions.CommandError,
            exceptions.HelpfulError,
            exceptions.ExtractionError,
        ) as e:
            log.error(
                "Error in {0}: {1.__class__.__name__}: {1.message}".format(command, e),
                exc_info=True,
            )

            expirein = e.expire_in if self.config.delete_messages else None
            alsodelete = message if self.config.delete_invoking else None

            if self.config.embeds:
                content = self._gen_embed()
                content.add_field(name="Error", value=e.message, inline=False)
                content.colour = 13369344
            else:
                content = "```\n{}\n```".format(e.message)

            await self.safe_send_message(
                message.channel, content, expire_in=expirein, also_delete=alsodelete
            )

        except exceptions.Signal:
            raise

        except Exception:
            log.error("Exception in on_message", exc_info=True)
            if self.config.debug_mode:
                await self.safe_send_message(
                    message.channel, "```\n{}\n```".format(traceback.format_exc())
                )

        finally:
            if not sentmsg and not response and self.config.delete_invoking:
                await asyncio.sleep(5)
                await self.safe_delete_message(message, quiet=True)

    async def gen_cmd_list(self, message, list_all_cmds=False):
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

    async def on_inactivity_timeout_expired(self, voice_channel):
        guild = voice_channel.guild

        if voice_channel:
            try:
                last_np_msg = self.server_specific_data[guild.id]["last_np_msg"]
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
            except Exception:
                log.info(
                    f"Leaving voice channel {voice_channel.name} in {voice_channel.guild} due to inactivity."
                )
            await self.disconnect_voice_client(guild)

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if not self.init_ok:
            log.warning("before init_ok")  # TODO: remove after coverage testing
            return  # Ignore stuff before ready

        if not self.is_ready():
            # TODO: remove after coverage testing
            log.warning("before is_ready")

        if self.config.leave_inactive_channel:
            guild = member.guild
            event, active = self.server_specific_data[guild.id]["inactive_vc_timer"]

            if before.channel and self.user in before.channel.members:
                if str(before.channel.id) in str(self.config.autojoin_channels):
                    log.info(
                        f"Ignoring {before.channel.name} in {before.channel.guild} as it is a binded voice channel."
                    )

                # elif not any(not user.bot for user in before.channel.members):
                elif is_empty_voice_channel(
                    before.channel, include_bots=self.config.bot_exception_ids
                ):
                    log.info(
                        f"{before.channel.name} has been detected as empty. Handling timeouts."
                    )
                    self.loop.create_task(self.handle_vc_inactivity(guild))
            elif after.channel and member != self.user:
                if self.user in after.channel.members:
                    if (
                        active
                    ):  # Added to not spam the console with the message for every person that joins
                        log.info(
                            f"A user joined {after.channel.name}, cancelling timer."
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
                        f"The bot got moved and the voice channel {after.channel.name} is empty. Handling timeouts."
                    )
                    self.loop.create_task(self.handle_vc_inactivity(guild))
                else:
                    if active:
                        log.info(
                            f"The bot got moved and the voice channel {after.channel.name} is not empty."
                        )
                        event.set()

        if (
            member == self.user and not after.channel
        ):  # if bot was disconnected from channel
            await self.disconnect_voice_client(before.channel.guild)
            return

        if before.channel:
            player = self.get_player_in(before.channel.guild)
            if player:
                self._handle_guild_auto_pause(player)
        if after.channel:
            player = self.get_player_in(after.channel.guild)
            if player:
                self._handle_guild_auto_pause(player)

    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        if before.region != after.region:
            log.warning(
                'Guild "%s" changed regions: %s -> %s'
                % (after.name, before.region, after.region)
            )

    async def on_guild_join(self, guild: discord.Guild):
        log.info("Bot has been added to guild: {}".format(guild.name))
        owner = self._get_owner(voice=True) or self._get_owner()
        if self.config.leavenonowners:
            check = guild.get_member(owner.id)
            if check is None:
                await guild.leave()
                log.info("Left {} due to bot owner not found.".format(guild.name))
                await owner.send(
                    self.str.get(
                        "left-no-owner-guilds",
                        "Left `{}` due to bot owner not being found in it.".format(
                            guild.name
                        ),
                    )
                )

        log.debug("Creating data folder for guild %s", guild.id)
        pathlib.Path("data/%s/" % guild.id).mkdir(exist_ok=True)

    async def on_guild_remove(self, guild: discord.Guild):
        log.info("Bot has been removed from guild: {}".format(guild.name))
        log.debug("Updated guild list:")
        [log.debug(" - " + s.name) for s in self.guilds]

        if guild.id in self.players:
            self.players.pop(guild.id).kill()

    async def on_guild_available(self, guild: discord.Guild):
        if not self.init_ok:
            return  # Ignore pre-ready events

        log.debug('Guild "{}" has become available.'.format(guild.name))

        player = self.get_player_in(guild)

        if player and player.is_paused:
            av_paused = self.server_specific_data[guild.id]["availability_paused"]

            if av_paused:
                log.debug(
                    'Resuming player in "{}" due to availability.'.format(guild.name)
                )
                self.server_specific_data[guild.id]["availability_paused"] = False
                player.resume()

    async def on_guild_unavailable(self, guild: discord.Guild):
        if not self.init_ok:
            return  # Ignore pre-ready events.

        log.debug('Guild "{}" has become unavailable.'.format(guild.name))

        player = self.get_player_in(guild)

        if player and player.is_playing:
            log.debug(
                'Pausing player in "{}" due to unavailability.'.format(guild.name)
            )
            self.server_specific_data[guild.id]["availability_paused"] = True
            player.pause()

    def voice_client_in(self, guild):
        for vc in self.voice_clients:
            if vc.guild == guild:
                return vc
        return None
