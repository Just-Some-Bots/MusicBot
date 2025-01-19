import configparser
import datetime
import logging
import os
import pathlib
import shutil
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Union,
    overload,
)

import configupdater
from configupdater.block import Comment, Space

from . import get_write_base, write_path
from .constants import (
    APL_FILE_HISTORY,
    DATA_FILE_COOKIES,
    DATA_FILE_SERVERS,
    DEFAULT_AUDIO_CACHE_DIR,
    DEFAULT_COMMAND_ALIAS_FILE,
    DEFAULT_DATA_DIR,
    DEFAULT_FOOTER_TEXT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOGS_KEPT,
    DEFAULT_LOGS_ROTATE_FORMAT,
    DEFAULT_MEDIA_FILE_DIR,
    DEFAULT_OPTIONS_FILE,
    DEFAULT_PLAYLIST_DIR,
    DEFAULT_SONG_BLOCKLIST_FILE,
    DEFAULT_USER_BLOCKLIST_FILE,
    DEPRECATED_USER_BLACKLIST,
    EXAMPLE_OPTIONS_FILE,
    MAXIMUM_LOGS_LIMIT,
    MUSICBOT_CONFIG_SECTIONS_ORDERED,
    MUSICBOT_TOKEN_ENV_VAR,
)
from .exceptions import HelpfulError, RetryConfigException
from .i18n import _Dd
from .logs import (
    set_logging_level,
    set_logging_max_kept_logs,
    set_logging_rotate_date_format,
)
from .utils import format_size_from_bytes, format_size_to_bytes, format_time_to_seconds

if TYPE_CHECKING:
    import discord

    from .bot import MusicBot
    from .permissions import Permissions

# Type for ConfigParser.get(... vars) argument
ConfVars = Optional[Mapping[str, str]]
CommentArgs = Optional[Dict[str, Any]]
# Types considered valid for config options.
DebugLevel = Tuple[str, int]
RegTypes = Union[str, int, bool, float, Set[int], Set[str], DebugLevel, pathlib.Path]

log = logging.getLogger(__name__)


def create_file_ifnoexist(
    path: pathlib.Path, content: Optional[Union[str, List[str]]]
) -> None:
    """
    Creates a UTF8 text file at given `path` if it does not exist.
    If supplied, `content` will be used to write initial content to the file.
    """
    if not path.exists():
        with open(path, "w", encoding="utf8") as fh:
            if content and isinstance(content, list):
                fh.writelines(content)
            elif content and isinstance(content, str):
                fh.write(content)
            log.warning("Creating %s", path)


class Config:
    """
    This object is responsible for loading and validating config, using default
    values where needed. It provides interfaces to read and set the state of
    config values, and finally a method to update the config file with values
    from this instance of config.
    """

    def __init__(self, config_file: pathlib.Path) -> None:
        """
        Handles locating, initializing, loading, and validating config data.
        Immediately validates all data which can be without async facilities.

        :param: config_file:  a configuration file path to load.

        :raises: musicbot.exceptions.HelpfulError
            if configuration fails to load for some typically known reason.
        """
        log.info("Loading config from:  %s", config_file)
        self.config_file = config_file
        self.find_config()  # this makes sure the config exists.

        # Make updates to config file before loading it in.
        ConfigRenameManager(self.config_file)

        config = ExtendedConfigParser()
        if self.config_file.is_file():
            config.read(config_file, encoding="utf-8")
        self.parser = config
        self.register = ConfigOptionRegistry(self, config)

        # DebugLevel is important for feedback, so we load it first.
        self._debug_level: DebugLevel = self.register.init_option(
            section="MusicBot",
            option="DebugLevel",
            dest="_debug_level",
            default=ConfigDefaults._debug_level(),
            getter="getdebuglevel",
            comment=_Dd(
                "Set the log verbosity of MusicBot. Normally this should be set to INFO.\n"
                "It can be set to one of the following:\n"
                " CRITICAL, ERROR, WARNING, INFO, DEBUG, VOICEDEBUG, FFMPEG, NOISY, or EVERYTHING"
            ),
            editable=False,
        )
        self.debug_level_str: str = self._debug_level[0]
        self.debug_level: int = self._debug_level[1]
        self.debug_mode: bool = self.debug_level <= logging.DEBUG
        set_logging_level(self.debug_level)

        # This gets filled in later while checking for token in the environment vars.
        self.auth: Tuple[str] = ("",)

        ########################################################################
        # Credentials
        ########################################################################
        self._login_token: str = self.register.init_option(
            section="Credentials",
            option="Token",
            dest="_login_token",
            getter="get",
            default=ConfigDefaults.token,
            comment=_Dd(
                "Discord bot authentication token for your Bot.\n"
                "Visit Discord Developer Portal to create a bot App and generate your Token.\n"
                "Never publish your bot token!"
            ),
            editable=False,
        )

        self.spotify_clientid = self.register.init_option(
            section="Credentials",
            option="Spotify_ClientID",
            dest="spotify_clientid",
            default=ConfigDefaults.spotify_clientid,
            comment=_Dd(
                "Provide your own Spotify Client ID to enable MusicBot to interact with Spotify API.\n"
                "MusicBot will try to use the web player API (guest mode) if nothing is set here.\n"
                "Using your own API credentials grants higher usage limits than guest mode."
            ),
            editable=False,
        )
        self.spotify_clientsecret = self.register.init_option(
            section="Credentials",
            option="Spotify_ClientSecret",
            dest="spotify_clientsecret",
            default=ConfigDefaults.spotify_clientsecret,
            comment=_Dd(
                "Provide your Spotify Client Secret to enable MusicBot to interact with Spotify API.\n"
                "This is required if you set the Spotify_ClientID option above."
            ),
            editable=False,
        )

        ########################################################################
        # Permissions
        ########################################################################
        self.owner_id: int = self.register.init_option(
            section="Permissions",
            option="OwnerID",
            dest="owner_id",
            default=ConfigDefaults.owner_id,
            comment=_Dd(
                # TRANSLATORS: 'auto' should not be translated.
                "Provide a Discord User ID number to set the owner of this bot.\n"
                "The word 'auto' or number 0 will set the owner based on App information.\n"
                "Only one owner ID can be set here. Generally, setting 'auto' is recommended."
            ),
            getter="getownerid",
            editable=False,
        )
        self.dev_ids: Set[int] = self.register.init_option(
            section="Permissions",
            option="DevIDs",
            dest="dev_ids",
            default=ConfigDefaults.dev_ids,
            comment=_Dd(
                "A list of Discord User IDs who can use the dev-only commands.\n"
                "Warning: dev-only commands can allow arbitrary remote code execution.\n"
                "Use spaces to separate multiple IDs.\n"
                "Most users should leave this setting blank."
            ),
            getter="getidset",
            editable=False,
        )

        self.bot_exception_ids: Set[int] = self.register.init_option(
            section="Permissions",
            option="BotExceptionIDs",
            dest="bot_exception_ids",
            getter="getidset",
            default=ConfigDefaults.bot_exception_ids,
            comment=_Dd(
                "Discord Member IDs for other bots that MusicBot should not ignore.\n"
                "Use spaces to separate multiple IDs.\n"
                "All bots are ignored by default."
            ),
        )

        ########################################################################
        # Chat Commands
        ########################################################################
        self.command_prefix: str = self.register.init_option(
            section="ChatCommands",
            option="CommandPrefix",
            dest="command_prefix",
            default=ConfigDefaults.command_prefix,
            comment=_Dd(
                "Command prefix is how all MusicBot commands must be started in Discord messages.\n"
                "E.g., if you set this to * the play command is trigger by *play ..."
            ),
        )
        self.commands_via_mention: bool = self.register.init_option(
            section="ChatCommands",
            option="CommandsByMention",
            dest="commands_via_mention",
            default=ConfigDefaults.commands_via_mention,
            getter="getboolean",
            comment=_Dd(
                # TRANSLATORS: YourBotNameHere can be translated.  CommandPrefix should not be translated.
                "Enable using commands with @[YourBotNameHere]\n"
                "The CommandPrefix is still available, but can be replaced with @ mention."
            ),
        )
        self.bound_channels: Set[int] = self.register.init_option(
            section="ChatCommands",
            option="BindToChannels",
            dest="bound_channels",
            default=ConfigDefaults.bound_channels,
            getter="getidset",
            comment=_Dd(
                "ID numbers for text channels that MusicBot should exclusively use for commands.\n"
                "This can contain IDs for channels in multiple servers.\n"
                "Use spaces to separate multiple IDs.\n"
                "All channels are used if this is not set."
            ),
        )
        self.unbound_servers: bool = self.register.init_option(
            section="ChatCommands",
            option="AllowUnboundServers",
            dest="unbound_servers",
            default=ConfigDefaults.unbound_servers,
            getter="getboolean",
            comment=_Dd(
                # TRANSLATORS: BindToChannels should not be translated.
                "Allow responses in all channels while no specific channel is set for a server.\n"
                "Only used when BindToChannels is missing an ID for a server."
            ),
        )
        self.usealias: bool = self.register.init_option(
            section="ChatCommands",
            option="UseAlias",
            dest="usealias",
            default=ConfigDefaults.usealias,
            getter="getboolean",
            comment=_Dd(
                "If enabled, MusicBot will allow commands to have multiple names using data in:  config/aliases.json"
            ),
            comment_args={"filepath": DEFAULT_COMMAND_ALIAS_FILE},
        )
        self.enable_options_per_guild: bool = self.register.init_option(
            section="ChatCommands",
            option="EnablePrefixPerGuild",
            dest="enable_options_per_guild",
            default=ConfigDefaults.enable_options_per_guild,
            getter="getboolean",
            comment=_Dd(
                # TRANSLATORS: setprefix should not be translated.
                "Allow MusicBot to save a per-server command prefix, and enables the setprefix command."
            ),
        )

        ########################################################################
        # Chat Responses
        ########################################################################
        self.dm_nowplaying: bool = self.register.init_option(
            section="ChatResponses",
            option="DMNowPlaying",
            dest="dm_nowplaying",
            default=ConfigDefaults.dm_nowplaying,
            getter="getboolean",
            comment=_Dd(
                "MusicBot will try to send Now Playing notices directly to the member who requested the song instead of posting in a server channel."
            ),
        )
        self.no_nowplaying_auto: bool = self.register.init_option(
            section="ChatResponses",
            option="DisableNowPlayingAutomatic",
            dest="no_nowplaying_auto",
            default=ConfigDefaults.no_nowplaying_auto,
            getter="getboolean",
            comment=_Dd(
                "Disable now playing messages for songs played via auto playlist."
            ),
        )
        self.nowplaying_channels: Set[int] = self.register.init_option(
            section="ChatResponses",
            option="NowPlayingChannels",
            dest="nowplaying_channels",
            default=ConfigDefaults.nowplaying_channels,
            getter="getidset",
            comment=_Dd(
                "Forces MusicBot to use a specific channel to send now playing messages.\n"
                "Only one text channel ID can be used per server."
            ),
        )
        self.delete_nowplaying: bool = self.register.init_option(
            section="ChatResponses",
            option="DeleteNowPlaying",
            dest="delete_nowplaying",
            default=ConfigDefaults.delete_nowplaying,
            getter="getboolean",
            comment=_Dd("MusicBot will automatically delete Now Playing messages."),
        )

        self.now_playing_mentions: bool = self.register.init_option(
            section="ChatResponses",
            option="NowPlayingMentions",
            dest="now_playing_mentions",
            default=ConfigDefaults.now_playing_mentions,
            getter="getboolean",
            comment=_Dd("Mention the user who added the song when it is played."),
        )

        self.delete_messages: bool = self.register.init_option(
            section="ChatResponses",
            option="DeleteMessages",
            dest="delete_messages",
            default=ConfigDefaults.delete_messages,
            getter="getboolean",
            comment=_Dd(
                # TRANSLATORS: DeleteDelayShort and DeleteDelayLong should not be translated.
                "Allow MusicBot to automatically delete messages it sends, after a delay.\n"
                "Delay period is controlled by DeleteDelayShort and DeleteDelayLong."
            ),
        )
        self.delete_invoking: bool = self.register.init_option(
            section="ChatResponses",
            option="DeleteInvoking",
            dest="delete_invoking",
            default=ConfigDefaults.delete_invoking,
            getter="getboolean",
            comment=_Dd("Auto delete valid commands after a delay."),
        )
        self.delete_delay_short: float = self.register.init_option(
            section="ChatResponses",
            option="DeleteDelayShort",
            dest="delete_delay_short",
            default=ConfigDefaults.delete_delay_short,
            getter="getduration",
            comment=_Dd(
                "Sets the short period of seconds before deleting messages.\n"
                "This period is used by messages that require no further interaction."
            ),
        )
        self.delete_delay_long: float = self.register.init_option(
            section="ChatResponses",
            option="DeleteDelayLong",
            dest="delete_delay_long",
            default=ConfigDefaults.delete_delay_long,
            getter="getduration",
            comment=_Dd(
                "Sets the long delay period before deleting messages.\n"
                "This period is used by interactive or long-winded messages, like search and help."
            ),
        )
        self.embeds: bool = self.register.init_option(
            section="ChatResponses",
            option="UseEmbeds",
            dest="embeds",
            default=ConfigDefaults.embeds,
            getter="getboolean",
            comment=_Dd("Allow MusicBot to format its messages as embeds."),
        )
        self.footer_text: str = self.register.init_option(
            section="ChatResponses",
            option="CustomEmbedFooter",
            dest="footer_text",
            default=ConfigDefaults.footer_text,
            comment=_Dd(
                # TRANSLATORS: UseEmbeds should not be translated.
                "Replace MusicBot name/version in embed footer with custom text.\n"
                "Only applied when UseEmbeds is enabled and it is not blank."
            ),
            default_is_empty=True,
        )
        self.remove_embed_footer: bool = self.register.init_option(
            section="ChatResponses",
            option="RemoveEmbedFooter",
            dest="remove_embed_footer",
            default=ConfigDefaults.remove_embed_footer,
            getter="getboolean",
            comment=_Dd("Completely remove the footer from embeds."),
        )
        self.searchlist: bool = self.register.init_option(
            section="ChatResponses",
            option="SearchList",
            dest="searchlist",
            default=ConfigDefaults.searchlist,
            getter="getboolean",
            comment=_Dd(
                "If enabled, users must indicate search result choices by sending a message instead of using reactions."
            ),
        )
        self.defaultsearchresults: int = self.register.init_option(
            section="ChatResponses",
            option="DefaultSearchResults",
            dest="defaultsearchresults",
            default=ConfigDefaults.defaultsearchresults,
            getter="getint",
            comment=_Dd(
                "Sets the default number of search results to fetch when using the search command without a specific number."
            ),
        )
        self.queue_length: int = self.register.init_option(
            section="ChatResponses",
            option="QueueLength",
            dest="queue_length",
            default=ConfigDefaults.queue_length,
            getter="getint",
            comment=_Dd(
                "The number of entries to show per-page when using q command to list the queue."
            ),
        )
        self.reply_and_mention: bool = self.register.init_option(
            section="ChatResponses",
            option="ReplyAndMention",
            dest="reply_and_mention",
            default=ConfigDefaults.reply_and_mention,
            getter="getboolean",
            comment=_Dd("Command responses will also mention or notify the user."),
        )

        ########################################################################
        # Playback
        ########################################################################
        self.default_volume: float = self.register.init_option(
            section="Playback",
            option="DefaultVolume",
            dest="default_volume",
            default=ConfigDefaults.default_volume,
            getter="getpercent",
            comment=_Dd(
                "Sets the default volume level MusicBot will play songs at.\n"
                "You can use any value from 0 to 1, or 0% to 100% volume."
            ),
        )
        self.default_speed: float = self.register.init_option(
            section="Playback",
            option="DefaultSpeed",
            dest="default_speed",
            default=ConfigDefaults.default_speed,
            getter="getfloat",
            comment=_Dd(
                "Sets the default speed MusicBot will play songs at.\n"
                "Must be a value from 0.5 to 100.0 for ffmpeg to use it.\n"
                "A value of 1 is normal playback speed.\n"
                "Note: Streamed media does not support speed adjustments."
            ),
        )
        self.skips_required: int = self.register.init_option(
            section="Playback",
            option="SkipsRequired",
            dest="skips_required",
            default=ConfigDefaults.skips_required,
            getter="getint",
            comment=_Dd(
                # TRANSLATORS: SkipRatio should not be translated.
                "Number of channel member votes required to skip a song.\n"
                "Acts as a minimum when SkipRatio would require more votes."
            ),
        )
        self.skip_ratio_required: float = self.register.init_option(
            section="Playback",
            option="SkipRatio",
            dest="skip_ratio_required",
            default=ConfigDefaults.skip_ratio_required,
            getter="getpercent",
            comment=_Dd(
                # TRANSLATORS: SkipsRequired is not translated
                "This percent of listeners in voice must vote for skip.\n"
                "If SkipsRequired is lower than the computed value, it will be used instead.\n"
                "You can set this from 0 to 1, or 0% to 100%."
            ),
        )
        self.allow_author_skip: bool = self.register.init_option(
            section="Playback",
            option="AllowAuthorSkip",
            dest="allow_author_skip",
            default=ConfigDefaults.allow_author_skip,
            getter="getboolean",
            comment=_Dd(
                "Allow the member who requested the song to skip it, bypassing votes."
            ),
        )
        self.legacy_skip: bool = self.register.init_option(
            section="Playback",
            option="LegacySkip",
            dest="legacy_skip",
            default=ConfigDefaults.legacy_skip,
            getter="getboolean",
            comment=_Dd(
                # TRANSLATORS: InstaSkip should not be translated.
                "Enable users with the InstaSkip permission to bypass skip voting and force skips."
            ),
        )
        self.auto_pause: bool = self.register.init_option(
            section="Playback",
            option="AutoPause",
            dest="auto_pause",
            default=ConfigDefaults.auto_pause,
            getter="getboolean",
            comment="MusicBot will automatically pause playback when no users are listening.",
        )

        self.persistent_queue: bool = self.register.init_option(
            section="Playback",
            option="PersistentQueue",
            dest="persistent_queue",
            default=ConfigDefaults.persistent_queue,
            getter="getboolean",
            comment=_Dd(
                "Allow MusicBot to save the song queue, so queued songs will survive restarts."
            ),
        )
        self.pre_download_next_song: bool = self.register.init_option(
            section="Playback",
            option="PreDownloadNextSong",
            dest="pre_download_next_song",
            default=ConfigDefaults.pre_download_next_song,
            getter="getboolean",
            comment=_Dd(
                "Enable MusicBot to download the next song in the queue while a song is playing.\n"
                "Currently this option does not apply to auto playlist or songs added to an empty queue."
            ),
        )
        self.use_experimental_equalization: bool = self.register.init_option(
            section="Playback",
            option="UseExperimentalEqualization",
            dest="use_experimental_equalization",
            default=ConfigDefaults.use_experimental_equalization,
            getter="getboolean",
            comment=_Dd(
                "Tries to use ffmpeg to get volume normalizing options for use in playback.\n"
                "This option can cause delay between playing songs, as the whole track must be processed."
            ),
        )
        self.round_robin_queue: bool = self.register.init_option(
            section="Playback",
            option="RoundRobinQueue",
            dest="round_robin_queue",
            default=ConfigDefaults.defaultround_robin_queue,
            getter="getboolean",
            comment=_Dd(
                "If enabled and multiple members are adding songs, MusicBot will organize playback for one song per member."
            ),
        )
        self.enable_local_media: bool = self.register.init_option(
            section="Playback",
            option="EnableLocalMedia",
            dest="enable_local_media",
            default=ConfigDefaults.enable_local_media,
            getter="getboolean",
            comment=_Dd(
                # TRANSLATORS: MediaFileDirectory should not be translated.
                "Enable playback of local media files using the play command.\n"
                "When enabled, users can use:  `play file://path/to/file.ext`\n"
                "to play files from the local MediaFileDirectory path."
            ),
        )

        self.auto_unpause_on_play: bool = self.register.init_option(
            section="Playback",
            option="UnpausePlayerOnPlay",
            dest="auto_unpause_on_play",
            default=ConfigDefaults.auto_unpause_on_play,
            getter="getboolean",
            comment=_Dd(
                "Allow MusicBot to automatically unpause when play commands are used."
            ),
        )
        self.use_opus_audio: bool = self.register.init_option(
            section="Playback",
            option="UseOpusAudio",
            dest="use_opus_audio",
            default=ConfigDefaults.use_opus_audio,
            getter="getboolean",
            comment=_Dd(
                "May reduce CPU usage by avoiding PCM-to-Opus encoding in python.\n"
                "When enabled, volume is controlled via FFmpeg filter instead of python.\n"
                "May cause a short delay when tracks first start for bitrate discovery."
            ),
        )
        self.use_opus_probe: bool = self.register.init_option(
            section="Playback",
            option="UseOpusProbe",
            dest="use_opus_probe",
            default=ConfigDefaults.use_opus_probe,
            getter="getboolean",
            comment=_Dd(
                "Similar to UseOpusAudio, but reduces CPU usage even more where possible.\n"
                "If the media is already Opus encoded (like YouTube) no re-encoding is done.\n"
                "This option will disable speed, volume, and UseExperimentalEqualization options."
            ),
        )
        self.default_search_service: str = self.register.init_option(
            section="Playback",
            option="DefaultSearchService",
            dest="default_search_service",
            default=ConfigDefaults.default_search_service,
            comment=_Dd(
                "This option sets the default search service used by MusicBot through ytdlp.\n"
                "Read ytdlp's list of supported sites to find supported prefixes you can use here.\n"
                "Some prefix examples:   ytsearch, scsearch, gvsearch, yvsearch, bilisearch, nicosearch"
            ),
        )

        ########################################################################
        # Auto Playlist
        ########################################################################
        self.auto_playlist: bool = self.register.init_option(
            section="AutoPlaylist",
            option="UseAutoPlaylist",
            dest="auto_playlist",
            default=ConfigDefaults.auto_playlist,
            getter="getboolean",
            comment=_Dd(
                "Enable MusicBot to automatically play music from the auto playlist when the queue is empty."
            ),
        )
        self.auto_playlist_random: bool = self.register.init_option(
            section="AutoPlaylist",
            option="AutoPlaylistRandom",
            dest="auto_playlist_random",
            default=ConfigDefaults.auto_playlist_random,
            getter="getboolean",
            comment=_Dd("Shuffles the auto playlist tracks before playing them."),
        )
        self.auto_playlist_autoskip: bool = self.register.init_option(
            section="AutoPlaylist",
            option="AutoPlaylistAutoSkip",
            dest="auto_playlist_autoskip",
            default=ConfigDefaults.auto_playlist_autoskip,
            getter="getboolean",
            comment=_Dd(
                "Enable automatic skip of auto playlist songs when a user plays a new song.\n"
                "This only applies to the current playing song if it was added by the auto playlist."
            ),
        )
        self.auto_playlist_remove_on_block: bool = self.register.init_option(
            section="AutoPlaylist",
            option="AutoPlaylistRemoveBlocked",
            dest="auto_playlist_remove_on_block",
            default=ConfigDefaults.auto_playlist_remove_on_block,
            getter="getboolean",
            comment=_Dd(
                "Remove songs from the auto playlist if they are found in the song block list."
            ),
        )
        # write_path not needed, used for display only.
        hist_file = pathlib.Path(DEFAULT_PLAYLIST_DIR).joinpath(APL_FILE_HISTORY)
        self.enable_queue_history_global: bool = self.register.init_option(
            section="AutoPlaylist",
            option="SavePlayedHistoryGlobal",
            dest="enable_queue_history_global",
            default=ConfigDefaults.enable_queue_history_global,
            getter="getboolean",
            comment=_Dd(
                "Enable saving all songs played by MusicBot to a global playlist file:  %(filename)s\n"
                "This will contain all songs from all servers."
            ),
            comment_args={"filename": hist_file},
        )
        self.enable_queue_history_guilds: bool = self.register.init_option(
            section="AutoPlaylist",
            option="SavePlayedHistoryGuilds",
            dest="enable_queue_history_guilds",
            default=ConfigDefaults.enable_queue_history_guilds,
            getter="getboolean",
            comment=_Dd(
                # TRANSLATORS:  [Server ID] is a descriptive placeholder, and can be translated.
                "Enable saving songs played per-server to a playlist file:  %(basename)s[Server ID]%(ext)s"
            ),
            comment_args={
                "basename": hist_file.with_name(hist_file.stem),
                "ext": hist_file.suffix,
            },
        )
        self.remove_ap: bool = self.register.init_option(
            section="AutoPlaylist",
            option="RemoveFromAPOnError",
            dest="remove_ap",
            default=ConfigDefaults.remove_ap,
            getter="getboolean",
            comment=_Dd(
                "Enable MusicBot to automatically remove unplayable entries from the auto playlist."
            ),
        )

        ########################################################################
        # MusicBot
        ########################################################################
        self.autojoin_channels: Set[int] = self.register.init_option(
            section="MusicBot",
            option="AutojoinChannels",
            dest="autojoin_channels",
            default=ConfigDefaults.autojoin_channels,
            getter="getidset",
            comment=_Dd(
                "A list of Voice Channel IDs that MusicBot should automatically join on start up.\n"
                "Use spaces to separate multiple IDs."
            ),
        )
        self.save_videos: bool = self.register.init_option(
            section="MusicBot",
            option="SaveVideos",
            dest="save_videos",
            default=ConfigDefaults.save_videos,
            getter="getboolean",
            comment=_Dd(
                "Allow MusicBot to keep downloaded media, or delete it right away."
            ),
        )
        self.storage_limit_bytes: int = self.register.init_option(
            section="MusicBot",
            option="StorageLimitBytes",
            dest="storage_limit_bytes",
            default=ConfigDefaults.storage_limit_bytes,
            getter="getdatasize",
            comment=_Dd(
                # TRANSLATORS: SaveVideos is not translated.
                "If SaveVideos is enabled, set a limit on how much storage space should be used."
            ),
        )
        self.storage_limit_days: int = self.register.init_option(
            section="MusicBot",
            option="StorageLimitDays",
            dest="storage_limit_days",
            default=ConfigDefaults.storage_limit_days,
            getter="getint",
            comment=_Dd(
                # TRANSLATORS: SaveVideos should not be translated.
                "If SaveVideos is enabled, set a limit on how long files should be kept."
            ),
        )
        self.storage_retain_autoplay: bool = self.register.init_option(
            section="MusicBot",
            option="StorageRetainAutoPlay",
            dest="storage_retain_autoplay",
            default=ConfigDefaults.storage_retain_autoplay,
            getter="getboolean",
            comment=_Dd(
                # TRANSLATORS: SaveVideos should not be translated.
                "If SaveVideos is enabled, never purge auto playlist songs from the cache regardless of limits."
            ),
        )
        self.auto_summon: bool = self.register.init_option(
            section="MusicBot",
            option="AutoSummon",
            dest="auto_summon",
            default=ConfigDefaults.auto_summon,
            getter="getboolean",
            comment=_Dd(
                "Automatically join the owner if they are in an accessible voice channel when bot starts."
            ),
        )
        self.status_message: str = self.register.init_option(
            section="MusicBot",
            option="StatusMessage",
            dest="status_message",
            default=ConfigDefaults.status_message,
            comment=_Dd(
                "Specify a custom message to use as the bot's status. If left empty, the bot\n"
                "will display dynamic info about music currently being played in its status instead.\n"
                "Status messages may also use the following variables:\n"
                " {n_playing}   = Number of currently Playing music players.\n"
                " {n_paused}    = Number of currently Paused music players.\n"
                " {n_connected} = Number of connected music players, in any player state.\n"
                "\n"
                "The following variables give access to information about the player and track.\n"
                "These variables may not be accurate in multi-guild bots:\n"
                " {p0_length}   = The total duration of the track, if available. Ex: [2:34]\n"
                " {p0_title}    = The track title for the currently playing track.\n"
                " {p0_url}      = The track URL for the currently playing track."
            ),
        )
        self.status_include_paused: bool = self.register.init_option(
            section="MusicBot",
            option="StatusIncludePaused",
            dest="status_include_paused",
            default=ConfigDefaults.status_include_paused,
            getter="getboolean",
            comment=_Dd(
                "If enabled, status messages will report info on paused players."
            ),
        )
        self.write_current_song: bool = self.register.init_option(
            section="MusicBot",
            option="WriteCurrentSong",
            dest="write_current_song",
            default=ConfigDefaults.write_current_song,
            getter="getboolean",
            comment=_Dd(
                # TRANSLATORS: [Server ID] is a descriptive placeholder and may be translated.
                "If enabled, MusicBot will save the track title to:  data/[Server ID]/current.txt"
            ),
        )
        self.show_config_at_start: bool = self.register.init_option(
            section="MusicBot",
            option="ShowConfigOnLaunch",
            dest="show_config_at_start",
            default=ConfigDefaults.show_config_at_start,
            getter="getboolean",
            comment=_Dd("Display MusicBot config settings in the logs at startup."),
        )
        self.leavenonowners: bool = self.register.init_option(
            section="MusicBot",
            option="LeaveServersWithoutOwner",
            dest="leavenonowners",
            default=ConfigDefaults.leavenonowners,
            getter="getboolean",
            comment=_Dd(
                "If enabled, MusicBot will leave servers if the owner is not in their member list."
            ),
        )
        self.self_deafen: bool = self.register.init_option(
            section="MusicBot",
            option="SelfDeafen",
            dest="self_deafen",
            default=ConfigDefaults.self_deafen,
            getter="getboolean",
            comment=_Dd(
                "MusicBot will automatically deafen itself when entering a voice channel."
            ),
        )
        self.leave_inactive_channel: bool = self.register.init_option(
            section="MusicBot",
            option="LeaveInactiveVC",
            dest="leave_inactive_channel",
            default=ConfigDefaults.leave_inactive_channel,
            getter="getboolean",
            comment=_Dd(
                # TRANSLATORS: LeaveInactiveVCTimeOut should not be translated.
                "If enabled, MusicBot will leave a voice channel when no users are listening,\n"
                "after waiting for a period set in LeaveInactiveVCTimeOut option.\n"
                "Listeners are channel members, excluding bots, who are not deafened."
            ),
        )
        self.leave_inactive_channel_timeout: float = self.register.init_option(
            section="MusicBot",
            option="LeaveInactiveVCTimeOut",
            dest="leave_inactive_channel_timeout",
            default=ConfigDefaults.leave_inactive_channel_timeout,
            getter="getduration",
            comment=_Dd(
                "Set a period of time to wait before leaving an inactive voice channel.\n"
                "You can set this to a number of seconds or phrase like:  4 hours"
            ),
        )
        self.leave_after_queue_empty: bool = self.register.init_option(
            section="MusicBot",
            option="LeaveAfterQueueEmpty",
            dest="leave_after_queue_empty",
            default=ConfigDefaults.leave_after_queue_empty,
            getter="getboolean",
            comment=_Dd(
                "If enabled, MusicBot will leave the channel immediately when the song queue is empty."
            ),
        )
        self.leave_player_inactive_for: float = self.register.init_option(
            section="MusicBot",
            option="LeavePlayerInactiveFor",
            dest="leave_player_inactive_for",
            default=ConfigDefaults.leave_player_inactive_for,
            getter="getduration",
            comment=_Dd(
                "When paused or no longer playing, wait for this amount of time then leave voice.\n"
                "You can set this to a number of seconds of phrase like:  15 minutes\n"
                "Set it to 0 to disable leaving in this way."
            ),
        )
        self.enable_network_checker: bool = self.register.init_option(
            section="MusicBot",
            option="EnableNetworkChecker",
            dest="enable_network_checker",
            default=ConfigDefaults.enable_network_checker,
            getter="getboolean",
            comment=_Dd(
                "Allow MusicBot to use timed pings to detect network outage and availability.\n"
                "This may be useful if you keep the bot joined to a channel or playing music 24/7.\n"
                "MusicBot must be restarted to enable network testing.\n"
                "By default this is disabled."
            ),
        )

        # This is likely to turn into one option for each separate part.
        # Due to how the support for protocols differs from part to part.
        # ytdlp has its own option that uses requests.
        # aiohttp requires per-call proxy parameter be set.
        # and ffmpeg with stream mode also makes its own direct connections.
        # top it off with proxy for the API. Once we tip the proxy iceberg...
        # In some cases, users might get away with setting environment variables,
        # HTTP_PROXY, HTTPS_PROXY, and others for ytdlp and ffmpeg.
        # While aiohttp would require some other param or config file for that.
        self.ytdlp_proxy: str = self.register.init_option(
            section="MusicBot",
            option="YtdlpProxy",
            dest="ytdlp_proxy",
            default=ConfigDefaults.ytdlp_proxy,
            comment=_Dd(
                "Experimental, HTTP/HTTPS proxy settings to use with ytdlp media downloader.\n"
                "The value set here is passed to `ytdlp --proxy` and aiohttp header checking.\n"
                "Leave blank to disable."
            ),
        )
        self.ytdlp_user_agent: str = self.register.init_option(
            section="MusicBot",
            option="YtdlpUserAgent",
            dest="ytdlp_user_agent",
            default=ConfigDefaults.ytdlp_user_agent,
            comment=_Dd(
                "Experimental option to set a static User-Agent header in yt-dlp.\n"
                "It is not typically recommended by yt-dlp to change the UA string.\n"
                "For examples of what you might put here, check the following two links:\n"
                "   https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent \n"
                "   https://www.useragents.me/ \n"
                "Leave blank to use default, dynamically generated UA strings."
            ),
        )
        self.ytdlp_source_address: str = self.register.init_option(
            section="MusicBot",
            option="YtdlpSourceAddress",
            dest="ytdlp_source_address",
            default=ConfigDefaults.ytdlp_source_address,
            getter="getstr",
            comment=_Dd(
                "Force yt-dlp to bind to a specific IP address or IP version on your system.\n"
                "To force any available IPv4, set this to:  0.0.0.0\n"
                "To force any available IPv6, set this to:  ::\n"
                "To allow either IPv4 or v6, set this to:  *"
            ),
        )

        self.user_blocklist_enabled: bool = self.register.init_option(
            section="MusicBot",
            option="EnableUserBlocklist",
            dest="user_blocklist_enabled",
            default=ConfigDefaults.user_blocklist_enabled,
            getter="getboolean",
            comment=_Dd(
                "Toggle the user block list feature, without emptying the block list."
            ),
        )
        self.song_blocklist_enabled: bool = self.register.init_option(
            section="MusicBot",
            option="EnableSongBlocklist",
            dest="song_blocklist_enabled",
            default=ConfigDefaults.song_blocklist_enabled,
            getter="getboolean",
            comment=_Dd(
                "Enable the song block list feature, without emptying the block list."
            ),
        )

        ########################################################################
        # Files
        ########################################################################
        self.user_blocklist_file: pathlib.Path = self.register.init_option(
            section="Files",
            option="UserBlocklistFile",
            dest="user_blocklist_file",
            default=ConfigDefaults.user_blocklist_file,
            getter="getpathlike",
            comment=_Dd(
                "An optional file path to a text file listing Discord User IDs, one per line."
            ),
            default_is_empty=True,
        )
        self.user_blocklist: UserBlocklist = UserBlocklist(self.user_blocklist_file)
        self.song_blocklist_file: pathlib.Path = self.register.init_option(
            section="Files",
            option="SongBlocklistFile",
            dest="song_blocklist_file",
            default=ConfigDefaults.song_blocklist_file,
            getter="getpathlike",
            comment=_Dd(
                "An optional file path to a text file that lists URLs, words, or phrases one per line.\n"
                "Any song title or URL that contains any line in the list will be blocked."
            ),
            default_is_empty=True,
        )
        self.song_blocklist: SongBlocklist = SongBlocklist(self.song_blocklist_file)
        self.auto_playlist_dir: pathlib.Path = self.register.init_option(
            section="Files",
            option="AutoPlaylistDirectory",
            dest="auto_playlist_dir",
            default=ConfigDefaults.auto_playlist_dir,
            getter="getpathlike",
            comment=_Dd(
                "An optional path to a directory containing auto playlist files.\n"
                "Each file should contain a list of playable URLs or terms, one track per line."
            ),
            default_is_empty=True,
        )

        self.media_file_dir: pathlib.Path = self.register.init_option(
            section="Files",
            option="MediaFileDirectory",
            dest="media_file_dir",
            default=ConfigDefaults.media_file_dir,
            getter="getpathlike",
            comment=_Dd(
                "An optional directory path where playable media files can be stored.\n"
                "All files and sub-directories can then be accessed by using 'file://' as a protocol.\n"
                "Example:  file://some/folder/name/file.ext\n"
                "Maps to:  %(path)s/some/folder/name/file.ext"
            ),
            comment_args={"path": "./media"},
            default_is_empty=True,
        )

        # TODO: add options for default language(s)
        # at least one for guild output language default.
        # log lang may be better off set via CLI / ENV.

        self.audio_cache_path: pathlib.Path = self.register.init_option(
            section="Files",
            option="AudioCachePath",
            dest="audio_cache_path",
            default=ConfigDefaults.audio_cache_path,
            getter="getpathlike",
            comment=_Dd(
                "An optional directory path where MusicBot will store long and short-term cache for playback."
            ),
            default_is_empty=True,
        )

        self.logs_max_kept: int = self.register.init_option(
            section="Files",
            option="LogsMaxKept",
            dest="logs_max_kept",
            default=ConfigDefaults.logs_max_kept,
            getter="getint",
            comment=_Dd(
                "Configure automatic log file rotation at restart, and limit the number of files kept.\n"
                "When disabled, only one log is kept and its contents are replaced each run.\n"
                "Set to 0 to disable.  Maximum allowed number is %(max)s."
            ),
            comment_args={"max": MAXIMUM_LOGS_LIMIT},
        )

        self.logs_date_format: str = self.register.init_option(
            section="Files",
            option="LogsDateFormat",
            dest="logs_date_format",
            default=ConfigDefaults.logs_date_format,
            comment=_Dd(
                "Configure the log file date format used when LogsMaxKept is enabled.\n"
                "If left blank, a warning is logged and the default will be used instead.\n"
                "Learn more about time format codes from the tables and data here:\n"
                "    https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior"
            ),
        )
        #
        # end of config registry.
        #

        if not self.config_file.is_file():
            log.info("Generating new config options files...")
            try:
                ex_file = write_path(EXAMPLE_OPTIONS_FILE)
                self.register.write_default_ini(ex_file)
                shutil.copy(ex_file, self.config_file)
                raise RetryConfigException()
            except OSError as e:
                # pylint: disable=duplicate-code
                raise HelpfulError(
                    # fmt: off
                    "Error creating default config options file.\n"
                    "\n"
                    "Problem:\n"
                    "  MusicBot attempted to generate the config files but failed due to an error:\n"
                    "  %(raw_error)s\n"
                    "\n"
                    "Solution:\n"
                    "  Make sure MusicBot can read and write to your config files.\n",
                    # fmt: on
                    fmt_args={"raw_error": e},
                ) from e
                # pylint: enable=duplicate-code

        # Convert all path constants into config as pathlib.Path objects.
        self.data_path = write_path(DEFAULT_DATA_DIR)
        self.server_names_path = self.data_path.joinpath(DATA_FILE_SERVERS)
        self.cookies_path = self.data_path.joinpath(DATA_FILE_COOKIES)
        self.disabled_cookies_path = self.cookies_path.parent.joinpath(
            f"_{self.cookies_path.name}"
        )
        self.audio_cache_path = self.audio_cache_path.absolute()

        # Validate the config settings match destination values.
        self.register.validate_register_destinations()

        # Make the registry check for missing data in the INI file.
        self.register.update_missing_config()

        if self.register.ini_missing_sections:
            sections_str = ", ".join(
                [f"[{s}]" for s in self.register.ini_missing_sections]
            )
            raise HelpfulError(
                # fmt: off
                "Error while reading config.\n"
                "\n"
                "Problem:\n"
                "  One or more required config option sections are missing.\n"
                "  The missing sections are:\n"
                "  %(sections)s\n"
                "\n"
                "Solution:\n"
                "  Repair your config options file.\n"
                "  Each [Section] must appear only once, with no other text on the same line.\n"
                "  Each section must have at least one option.\n"
                "  Use the example options as a template or copy it from the repository.",
                # fmt: on
                fmt_args={"sections": sections_str},
            )

        # This value gets set dynamically, based on success with API authentication.
        self.spotify_enabled = False

        self.run_checks()

    def run_checks(self) -> None:
        """
        Validation and some sanity check logic for bot settings.

        :raises: musicbot.exceptions.HelpfulError
            if some validation failed that the user needs to correct.
        """
        if self.logs_max_kept > MAXIMUM_LOGS_LIMIT:
            log.warning(
                "Cannot store more than %s log files. Option LogsMaxKept will be limited instead.",
                MAXIMUM_LOGS_LIMIT,
            )
            self.logs_max_kept = MAXIMUM_LOGS_LIMIT
        set_logging_max_kept_logs(self.logs_max_kept)

        if not self.logs_date_format and self.logs_max_kept > 0:
            log.warning(
                "Config option LogsDateFormat is empty and this will break log file rotation. Using default instead."
            )
            self.logs_date_format = DEFAULT_LOGS_ROTATE_FORMAT
        set_logging_rotate_date_format(self.logs_date_format)

        if self.audio_cache_path:
            try:
                acpath = self.audio_cache_path
                if acpath.is_file():
                    raise HelpfulError(
                        # fmt: off
                        "Error while validating config options.\n"
                        "\n"
                        "Problem:\n"
                        "  Config option AudioCachePath is not a directory.\n"
                        "\n"
                        "Solution:\n"
                        "  Make sure the path you configured is a path to a folder / directory."
                        # fmt: on
                    )
                # Might as well test for multiple issues here since we can give feedback.
                if not acpath.is_dir():
                    acpath.mkdir(parents=True, exist_ok=True)
                actest = acpath.joinpath(".bot-test-write")
                actest.touch(exist_ok=True)
                actest.unlink(missing_ok=True)
            except OSError as e:
                log.exception(
                    "An exception was thrown while validating AudioCachePath."
                )
                raise HelpfulError(
                    # fmt: off
                    "Error while validating config options.\n"
                    "\n"
                    "Problem:\n"
                    "  AudioCachePath config option could not be set due to an error:\n"
                    "  %(raw_error)s\n"
                    "\n"
                    "Solution:\n"
                    "  Double check the setting is a valid, accessible directory path.",
                    # fmt: on
                    fmt_args={"raw_error": e},
                ) from e

        log.info("Audio Cache will be stored in:  %s", self.audio_cache_path)

        if not self._login_token:
            # Attempt to fallback to an environment variable.
            env_token = os.environ.get(MUSICBOT_TOKEN_ENV_VAR)
            if env_token:
                self._login_token = env_token
                self.auth = (self._login_token,)
            else:
                raise HelpfulError(
                    # fmt: off
                    "Error while reading config options.\n"
                    "\n"
                    "Problem:\n"
                    "  No bot Token was specified in the config options or environment.\n"
                    "\n"
                    "Solution:\n"
                    "  Set the Token config option or set environment variable %(env_var)s with an App token.",
                    # fmt: on
                    fmt_args={"env_var": MUSICBOT_TOKEN_ENV_VAR},
                )

        else:
            self.auth = (self._login_token,)

        if self.spotify_clientid and self.spotify_clientsecret:
            self.spotify_enabled = True

        self.delete_invoking = self.delete_invoking and self.delete_messages

        if self.status_message and len(self.status_message) > 128:
            log.warning(
                "StatusMessage config option is too long, it will be limited to 128 characters."
            )
            self.status_message = self.status_message[:128]

        if not self.footer_text:
            self.footer_text = ConfigDefaults.footer_text

        if self.default_speed < 0.5 or self.default_speed > 100.0:
            log.warning(
                "The default playback speed must be between 0.5 and 100.0. "
                "The option value of %.3f will be limited instead."
            )
            self.default_speed = max(min(self.default_speed, 100.0), 0.5)

        if self.enable_local_media and not self.media_file_dir.is_dir():
            self.media_file_dir.mkdir(exist_ok=True)

    async def async_validate(self, bot: "MusicBot") -> None:
        """
        Validation logic for bot settings that depends on data from async services.

        :raises: musicbot.exceptions.HelpfulError
            if some validation failed that the user needs to correct.

        :raises: RuntimeError if there is a failure in async service data.
        """
        log.debug("Validating options with service data...")

        # attempt to get the owner ID from app-info.
        if self.owner_id == 0:
            if bot.cached_app_info:
                self.owner_id = bot.cached_app_info.owner.id
                log.debug("Acquired owner ID via API")
            else:
                raise HelpfulError(
                    # fmt: off
                    "Error while fetching 'OwnerID' automatically.\n"
                    "\n"
                    "Problem:\n"
                    "  Discord App info is not available.\n"
                    "  This could be a temporary API outage or a bug.\n"
                    "\n"
                    "Solution:\n"
                    "  Manually set the 'OwnerID' config option or try again later."
                    # fmt: on
                )

        if not bot.user:
            log.critical("MusicBot does not have a user instance, cannot proceed.")
            raise RuntimeError("This cannot continue.")

        if self.owner_id == bot.user.id:
            raise HelpfulError(
                # fmt: off
                "Error validating config options.\n"
                "\n"
                "Problem:\n"
                "  The 'OwnerID' config is the same as your Bot / App ID.\n"
                "\n"
                "Solution:\n"
                "  Do not use the Bot or App ID in the 'OwnerID' field."
                # fmt: on
            )

    def find_config(self) -> None:
        """
        Handle locating or initializing a config file, using a previously set
        config file path.
        If the config file is not found, this will check for a file with `.ini` suffix.
        If neither of the above are found, this will attempt to copy the example config.

        :raises: musicbot.exceptions.HelpfulError
            if config fails to be located or has not been configured.
        """
        config = ExtendedConfigParser()

        # Check for options.ini and copy example ini if missing.
        if not self.config_file.is_file():
            log.warning("Config options file not found. Checking for alternatives...")

            example_file = write_path(EXAMPLE_OPTIONS_FILE)
            try:
                # Check for options.ini.ini because windows.
                ini_file = self.config_file.with_suffix(".ini.ini")
                if sys.platform == "nt" and ini_file.is_file():
                    # shutil.move in 3.8 expects str and not path-like.
                    if sys.version_info >= (3, 9):
                        shutil.move(ini_file, self.config_file)
                    else:
                        shutil.move(str(ini_file), str(self.config_file))
                    log.warning(
                        "Renaming %(ini_file)s to %(option_file)s, you should probably turn file extensions on.",
                        {"ini_file": ini_file, "option_file": self.config_file},
                    )

                # Look for an existing examples file.
                elif os.path.isfile(example_file):
                    shutil.copy(example_file, self.config_file)
                    log.warning(
                        "Copying existing example options file:  %(example_file)s",
                        {"example_file": example_file},
                    )

                # Tell the user we don't have any config to use.
                else:
                    log.error(
                        "Could not locate config options or example options files.\n"
                        "MusicBot will generate the config files at the location:\n"
                        "  %(cfg_file)s",
                        {"cfg_file": self.config_file.parent},
                    )
            except OSError as e:
                log.exception(
                    "Something went wrong while trying to find a config option file."
                )
                raise HelpfulError(
                    # fmt: off
                    "Error locating config.\n"
                    "\n"
                    "Problem:\n"
                    "  Could not find or create a config file due to an error:\n"
                    "  %(raw_error)s\n"
                    "\n"
                    "Solution:\n"
                    "  Verify the config folder and files exist and can be read by MusicBot.",
                    # fmt: on
                    fmt_args={"raw_error": e},
                ) from e

        # try to read / parse the config file.
        try:
            config.read(self.config_file, encoding="utf-8")
        except (OSError, configparser.Error) as e:
            raise HelpfulError(
                # fmt: off
                "Error loading config.\n"
                "\n"
                "Problem:\n"
                "  MusicBot could not read config file due to an error:\n"
                "  %(raw_error)s\n"
                "\n"
                "Solution:\n"
                "  Make sure the file is accessible and error free.\n"
                "  Copy the example file from the repo if all else fails.",
                # fmg: on
                fmt_args={"raw_error": e},
            ) from e

    def update_option(self, option: "ConfigOption", value: str) -> bool:
        """
        Uses option data to parse the given value and update its associated config.
        No data is saved to file however.
        """
        tmp_parser = ExtendedConfigParser()
        tmp_parser.read_dict({option.section: {option.option: value}})

        try:
            get = getattr(tmp_parser, option.getter, None)
            if not get:
                log.critical("Dev Bug! Config option has getter that is not available.")
                return False
            new_conf_val = get(option.section, option.option, fallback=option.default)
            if not isinstance(new_conf_val, type(option.default)):
                log.error(
                    "Dev Bug! Config option has invalid type, getter and default must be the same type."
                )
                return False
            setattr(self, option.dest, new_conf_val)
            return True
        except (HelpfulError, ValueError, TypeError):
            return False

    def save_option(self, option: "ConfigOption") -> bool:
        """
        Converts the current Config value into an INI file value as needed.
        Note: ConfigParser must not use multi-line values. This will break them.
        """
        try:
            cu = configupdater.ConfigUpdater()
            cu.optionxform = str  # type: ignore
            cu.read(self.config_file, encoding="utf8")

            if option.section in list(cu.keys()):
                if option.option not in list(cu[option.section].keys()):
                    log.debug("Option was missing previously.")
                    cu[option.section][option.option] = self.register.to_ini(option)
                    c_bits = option.comment.split("\n")
                    adder = cu[option.section][option.option].add_before
                    adder.space()
                    if len(c_bits) > 1:
                        for line in c_bits:
                            adder.comment(line)
                    else:
                        adder.comment(option.comment)
                    cu[option.section][option.option].add_after.space()
                else:
                    cu[option.section][option.option] = self.register.to_ini(option)
            else:
                log.error(
                    "Config section not in parsed config! Missing: %s", option.section
                )
                return False
            cu.update_file()
            log.info(
                "Saved config option: %(config)s  =  %(value)s",
                {
                    "config": option,
                    "value": cu[option.section][option.option].value,
                },
            )
            return True
        except (
            OSError,
            AttributeError,
            configparser.DuplicateSectionError,
            configparser.ParsingError,
        ):
            log.exception("Failed to save config:  %s", option)
            return False


class ConfigDefaults:
    """
    This class contains default values used mainly as config fallback values.
    None type is not allowed as a default value.
    """

    owner_id: int = 0
    token: str = ""
    dev_ids: Set[int] = set()
    bot_exception_ids: Set[int] = set()

    spotify_clientid: str = ""
    spotify_clientsecret: str = ""

    command_prefix: str = "!"
    commands_via_mention: bool = True
    bound_channels: Set[int] = set()
    unbound_servers: bool = True
    autojoin_channels: Set[int] = set()
    dm_nowplaying: bool = False
    no_nowplaying_auto: bool = False
    nowplaying_channels: Set[int] = set()
    delete_nowplaying: bool = True
    reply_and_mention: bool = True

    default_volume: float = 0.15
    default_speed: float = 1.0
    skips_required: int = 4
    skip_ratio_required: float = 0.5
    save_videos: bool = True
    storage_retain_autoplay: bool = True
    storage_limit_bytes: int = 0
    storage_limit_days: int = 0
    now_playing_mentions: bool = False
    auto_summon: bool = True
    auto_playlist: bool = True
    auto_playlist_random: bool = True
    auto_playlist_autoskip: bool = False
    auto_playlist_remove_on_block: bool = False
    auto_pause: bool = True
    delete_messages: bool = True
    delete_invoking: bool = False
    delete_delay_short: float = 30.0
    delete_delay_long: float = 60.0
    persistent_queue: bool = True
    status_message: str = ""
    status_include_paused: bool = False
    write_current_song: bool = False
    allow_author_skip: bool = True
    use_opus_audio: bool = True
    use_opus_probe: bool = False
    use_experimental_equalization: bool = False
    embeds: bool = True
    queue_length: int = 10
    remove_ap: bool = True
    show_config_at_start: bool = False
    legacy_skip: bool = False
    leavenonowners: bool = False
    usealias: bool = True
    searchlist: bool = False
    self_deafen: bool = True
    leave_inactive_channel: bool = False
    leave_inactive_channel_timeout: float = 300.0
    leave_after_queue_empty: bool = False
    leave_player_inactive_for: float = 0.0
    defaultsearchresults: int = 3
    enable_options_per_guild: bool = False
    footer_text: str = DEFAULT_FOOTER_TEXT
    remove_embed_footer: bool = False
    defaultround_robin_queue: bool = False
    enable_network_checker: bool = False
    enable_local_media: bool = False
    enable_queue_history_global: bool = False
    enable_queue_history_guilds: bool = False
    auto_unpause_on_play: bool = False
    ytdlp_proxy: str = ""
    ytdlp_user_agent: str = ""
    ytdlp_source_address: str = "*"

    pre_download_next_song: bool = True
    default_search_service: str = "ytsearch"

    song_blocklist: Set[str] = set()
    user_blocklist: Set[int] = set()
    song_blocklist_enabled: bool = False
    # default true here since the file being populated was previously how it was enabled.
    user_blocklist_enabled: bool = True

    logs_max_kept: int = DEFAULT_LOGS_KEPT
    logs_date_format: str = DEFAULT_LOGS_ROTATE_FORMAT

    # Create path objects from the constants.
    options_file: pathlib.Path = write_path(DEFAULT_OPTIONS_FILE)
    user_blocklist_file: pathlib.Path = write_path(DEFAULT_USER_BLOCKLIST_FILE)
    song_blocklist_file: pathlib.Path = write_path(DEFAULT_SONG_BLOCKLIST_FILE)
    auto_playlist_dir: pathlib.Path = write_path(DEFAULT_PLAYLIST_DIR)
    media_file_dir: pathlib.Path = write_path(DEFAULT_MEDIA_FILE_DIR)
    audio_cache_path: pathlib.Path = write_path(DEFAULT_AUDIO_CACHE_DIR)

    @staticmethod
    def _debug_level() -> Tuple[str, int]:
        """default values for debug log level configs"""
        debug_level: int = getattr(logging, DEFAULT_LOG_LEVEL, logging.INFO)
        debug_level_str: str = (
            DEFAULT_LOG_LEVEL
            if logging.getLevelName(debug_level) == DEFAULT_LOG_LEVEL
            else logging.getLevelName(debug_level)
        )
        return (debug_level_str, debug_level)


class ConfigOption:
    """Basic data model for individual registered options."""

    def __init__(
        self,
        section: str,
        option: str,
        dest: str,
        default: RegTypes,
        comment: str,
        comment_args: CommentArgs = None,
        getter: str = "get",
        editable: bool = True,
        invisible: bool = False,
        empty_display_val: str = "",
        default_is_empty: bool = False,
    ) -> None:
        """
        Defines a configuration option in MusicBot and attributes used to
        identify the option both at runtime and in the INI file.

        :param: section:    The section this option belongs to, case sensitive.
        :param: option:     The name of this option, case sensitive.
        :param: dest:       The name of a Config attribute the value of this option will be stored in.
        :param: getter:     The name of a callable in ConfigParser used to get this option value.
        :param: default:    The default value for this option if it is missing or invalid.
        :param: comment:    A comment or help text to show for this option.
        :param: editable:   If this option can be changed via commands.
        :param: invisible:  (Permissions only) hide from display when formatted for per-user display.
        :param: empty_display_val   Value shown when the parsed value is empty or None.
        :param: default_is_empty    Save an empty value to INI file when the option value is default.
        """
        self.section = section
        self.option = option
        self.dest = dest
        self.getter = getter
        self.default = default
        self.comment = comment
        self.comment_args = comment_args
        self.editable = editable
        self.invisible = invisible
        self.empty_display_val = empty_display_val
        self.default_is_empty = default_is_empty

    def __str__(self) -> str:
        return f"[{self.section}] > {self.option}"


class ConfigOptionRegistry:
    """
    Management system for registering config options which provides methods to
    query the state of configurations or translate them.
    """

    def __init__(
        self, config: Union[Config, "Permissions"], parser: "ExtendedConfigParser"
    ) -> None:
        """
        Manage a configuration registry that associates config options to their
        parent section, a runtime name, validation for values, and commentary
        or other help text about the option.
        """
        self._config = config
        self._parser = parser

        # registered options.
        self._option_list: List[ConfigOption] = []

        # registered sections.
        self._sections: Set[str] = set()
        self._options: Set[str] = set()
        self._distinct_options: Set[str] = set()
        self._has_resolver: bool = True

        # set up missing config data.
        self.ini_missing_options: Set[ConfigOption] = set()
        self.ini_missing_sections: Set[str] = set()

    @property
    def sections(self) -> Set[str]:
        """Available section names."""
        return self._sections

    @property
    def option_keys(self) -> Set[str]:
        """Available options with section names."""
        return self._options

    @property
    def option_list(self) -> List[ConfigOption]:
        """Non-settable option list."""
        return self._option_list

    @property
    def resolver_available(self) -> bool:
        """Status of option name-to-section resolver. If False, resolving cannot be used."""
        return self._has_resolver

    def update_missing_config(self) -> None:
        """
        Checks over the ini file for options missing from the file.
        It only considers registered options, rather than looking at examples file.
        As such it should be run after all options are registered.
        """
        # load the unique sections and options from the parser.
        p_section_set = set()
        p_key_set = set()
        parser_sections = dict(self._parser.items())
        for section in parser_sections:
            p_section_set.add(section)
            opts = set(parser_sections[section].keys())
            for opt in opts:
                p_key_set.add(f"[{section}] > {opt}")

        # update the missing sections registry.
        self.ini_missing_sections = self._sections - p_section_set

        # populate the missing options registry.
        for option in self._option_list:
            if str(option) not in p_key_set:
                self.ini_missing_options.add(option)

    def get_sections_from_option(self, option_name: str) -> Set[str]:
        """
        Get the Section name(s) associated with the given `option_name` if available.

        :return:  A set containing one or more section names, or an empty set if no option exists.
        """
        if self._has_resolver:
            return set(o.section for o in self._option_list if o.option == option_name)
        return set()

    def get_updated_options(self) -> List[ConfigOption]:
        """
        Get ConfigOptions that have been updated at runtime.
        """
        changed = []
        for option in self._option_list:
            if not hasattr(self._config, option.dest):
                raise AttributeError(
                    f"Dev Bug! Attribute `Config.{option.dest}` does not exist."
                )

            if not hasattr(self._parser, option.getter):
                raise AttributeError(
                    f"Dev Bug! Method `*ConfigParser.{option.getter}` does not exist."
                )

            p_getter = getattr(self._parser, option.getter)
            config_value = getattr(self._config, option.dest)
            parser_value = p_getter(
                option.section, option.option, fallback=option.default
            )

            # We only care about changed options that are editable.
            if config_value != parser_value and option.editable:
                changed.append(option)
        return changed

    def get_config_option(self, section: str, option: str) -> Optional[ConfigOption]:
        """
        Gets the config option if it exists, or returns None
        """
        for opt in self._option_list:
            if opt.section == section and opt.option == option:
                return opt
        return None

    def get_values(self, opt: ConfigOption) -> Tuple[RegTypes, RegTypes, str]:
        """
        Get the values in Config and *ConfigParser for this config option.
        Returned tuple contains parsed value, ini-string, and a display string
        for the parsed config value if applicable.
        Display string may be empty if not used.
        """
        if not opt.editable:
            return ("", "", "")

        if not hasattr(self._config, opt.dest):
            raise AttributeError(
                f"Dev Bug! Attribute `Config.{opt.dest}` does not exist."
            )

        if not hasattr(self._parser, opt.getter):
            raise AttributeError(
                f"Dev Bug! Method `*ConfigParser.{opt.getter}` does not exist."
            )

        p_getter = getattr(self._parser, opt.getter)
        config_value = getattr(self._config, opt.dest)
        parser_value = p_getter(opt.section, opt.option, fallback=opt.default)

        display_config_value = ""
        if opt.empty_display_val:
            display_config_value = opt.empty_display_val

        return (config_value, parser_value, display_config_value)

    def validate_register_destinations(self) -> None:
        """Check all configured options for matching destination definitions."""
        errors = []
        for opt in self._option_list:
            if not hasattr(self._config, opt.dest):
                errors.append(
                    f"Config Option `{opt}` has an missing destination named:  {opt.dest}"
                )
        if errors:
            msg = "Dev Bug!  Some options failed config validation.\n"
            msg += "\n".join(errors)
            raise RuntimeError(msg)

    @overload
    def init_option(
        self,
        section: str,
        option: str,
        dest: str,
        default: str,
        comment: str,
        comment_args: CommentArgs = None,
        getter: str = "get",
        editable: bool = True,
        invisible: bool = False,
        empty_display_val: str = " ",
        default_is_empty: bool = False,
    ) -> str:
        pass

    @overload
    def init_option(
        self,
        section: str,
        option: str,
        dest: str,
        default: bool,
        comment: str,
        comment_args: CommentArgs = None,
        getter: str = "getboolean",
        editable: bool = True,
        invisible: bool = False,
        empty_display_val: str = "",
        default_is_empty: bool = False,
    ) -> bool:
        pass

    @overload
    def init_option(
        self,
        section: str,
        option: str,
        dest: str,
        default: int,
        comment: str,
        comment_args: CommentArgs = None,
        getter: str = "getint",
        editable: bool = True,
        invisible: bool = False,
        empty_display_val: str = "",
        default_is_empty: bool = False,
    ) -> int:
        pass

    @overload
    def init_option(
        self,
        section: str,
        option: str,
        dest: str,
        default: float,
        comment: str,
        comment_args: CommentArgs = None,
        getter: str = "getfloat",
        editable: bool = True,
        invisible: bool = False,
        empty_display_val: str = "",
        default_is_empty: bool = False,
    ) -> float:
        pass

    @overload
    def init_option(
        self,
        section: str,
        option: str,
        dest: str,
        default: Set[int],
        comment: str,
        comment_args: CommentArgs = None,
        getter: str = "getidset",
        editable: bool = True,
        invisible: bool = False,
        empty_display_val: str = " ",
        default_is_empty: bool = False,
    ) -> Set[int]:
        pass

    @overload
    def init_option(
        self,
        section: str,
        option: str,
        dest: str,
        default: Set[str],
        comment: str,
        comment_args: CommentArgs = None,
        getter: str = "getstrset",
        editable: bool = True,
        invisible: bool = False,
        empty_display_val: str = " ",
        default_is_empty: bool = False,
    ) -> Set[str]:
        pass

    @overload
    def init_option(
        self,
        section: str,
        option: str,
        dest: str,
        default: DebugLevel,
        comment: str,
        comment_args: CommentArgs = None,
        getter: str = "getdebuglevel",
        editable: bool = True,
        invisible: bool = False,
        empty_display_val: str = "",
        default_is_empty: bool = False,
    ) -> DebugLevel:
        pass

    @overload
    def init_option(
        self,
        section: str,
        option: str,
        dest: str,
        default: pathlib.Path,
        comment: str,
        comment_args: CommentArgs = None,
        getter: str = "getpathlike",
        editable: bool = True,
        invisible: bool = False,
        empty_display_val: str = "",
        default_is_empty: bool = False,
    ) -> pathlib.Path:
        pass

    def init_option(
        self,
        section: str,
        option: str,
        dest: str,
        default: RegTypes,
        comment: str,
        comment_args: CommentArgs = None,
        getter: str = "get",
        editable: bool = True,
        invisible: bool = False,
        empty_display_val: str = "",
        default_is_empty: bool = False,
    ) -> RegTypes:
        """
        Register an option while getting its configuration value at the same time.

        :param: section:    The section this option belongs to, case sensitive.
        :param: option:     The name of this option, case sensitive.
        :param: dest:       The name of a Config attribute the value of this option will be stored in.
        :param: getter:     The name of a callable in ConfigParser used to get this option value.
        :param: default:    The default value for this option if it is missing or invalid.
        :param: comment:    A comment or help text to show for this option.
        :param: editable:   If this option can be changed via commands.
        """
        # Check that the getter function exists and is callable.
        if not hasattr(self._parser, getter):
            raise ValueError(
                f"Dev Bug! There is no *ConfigParser function by the name of: {getter}"
            )
        if not callable(getattr(self._parser, getter)):
            raise TypeError(
                f"Dev Bug! The *ConfigParser.{getter} attribute is not a callable function."
            )

        # add the option to the registry.
        config_opt = ConfigOption(
            section=section,
            option=option,
            dest=dest,
            default=default,
            getter=getter,
            comment=comment,
            comment_args=comment_args,
            editable=editable,
            invisible=invisible,
            empty_display_val=empty_display_val,
            default_is_empty=default_is_empty,
        )
        self._option_list.append(config_opt)
        self._sections.add(section)
        if str(config_opt) in self._options:
            log.warning(
                "Option names are not unique between INI sections!  Resolver is disabled."
            )
            self._has_resolver = False
        self._options.add(str(config_opt))
        self._distinct_options.add(option)

        # get the current config value.
        getfunc = getattr(self._parser, getter)
        opt: RegTypes = getfunc(section, option, fallback=default)

        # sanity check that default actually matches the type from getter.
        if not isinstance(opt, type(default)):
            raise TypeError(
                "Dev Bug! Are you using the wrong getter for this option?\n"
                f"[{section}] > {option} has type: {type(default)} but got type: {type(opt)}"
            )
        return opt

    def to_ini(self, option: ConfigOption, use_default: bool = False) -> str:
        """
        Convert the parsed config value into an INI value.
        This method does not perform validation, simply converts the value.

        :param: use_default:  return the default value instead of current config.
        """
        if not hasattr(self._config, option.dest):
            raise AttributeError(
                f"Dev Bug! Attribute `Config.{option.dest}` does not exist."
            )

        if use_default:
            conf_value = option.default
        else:
            conf_value = getattr(self._config, option.dest)
        return self._value_to_ini(conf_value, option.getter)

    def _value_to_ini(self, conf_value: RegTypes, getter: str) -> str:
        """Converts a value to an ini string."""
        if getter == "get":
            return str(conf_value)

        if getter == "getint":
            return str(conf_value)

        if getter == "getfloat":
            return f"{conf_value:.3f}"

        if getter == "getboolean":
            return "yes" if conf_value else "no"

        if getter in ["getstrset", "getidset"] and isinstance(conf_value, (list, set)):
            return ", ".join(str(x) for x in conf_value)

        if getter == "getdatasize" and isinstance(conf_value, int):
            if conf_value:
                return format_size_from_bytes(conf_value)
            return str(conf_value)

        if getter == "getduration" and isinstance(conf_value, (int, float)):
            td = datetime.timedelta(seconds=round(conf_value))
            return str(td)

        if getter == "getpathlike":
            return str(conf_value)

        # NOTE: debug_level is not editable, but can be displayed.
        if (
            getter == "getdebuglevel"
            and isinstance(conf_value, tuple)
            and isinstance(conf_value[0], str)
            and isinstance(conf_value[1], int)
        ):
            return str(logging.getLevelName(conf_value[1]))

        return str(conf_value)

    def export_markdown(self) -> str:
        """
        Transform registered config / permissions options into "markdown".
        This is intended to generate documentation from the code for publishing to pages.
        Currently will print options in order they are registered.
        But prints sections in the order ConfigParser loads them.
        """
        basedir = get_write_base()
        if not basedir:
            basedir = os.getcwd()
        md_sections = {}
        for opt in self.option_list:
            dval = self.to_ini(opt, use_default=True)
            if opt.getter == "getpathlike":
                dval = dval.replace(basedir, ".")
            if dval.strip() == "":
                if opt.empty_display_val:
                    dval = f"<code>{opt.empty_display_val}</code>"
                else:
                    dval = "<i>*empty*</i>"
            else:
                dval = f"<code>{dval}</code>"

            # TODO: default values need to be consistent i18n will probably change this.
            # fmt: off
            if opt.comment_args:
                comment = opt.comment % opt.comment_args
            else:
                comment = opt.comment
            comment = comment.replace("\n", "<br>\n")
            md_option = (
                f"<details>\n  <summary>{opt.option}</summary>\n\n"
                f"{comment}<br>  \n"
                f"<strong>Default Value:</strong> {dval}  \n</details>  \n"
            )
            # fmt: on
            if opt.section not in md_sections:
                md_sections[opt.section] = [md_option]
            else:
                md_sections[opt.section].append(md_option)

        markdown = ""
        for sect in self._parser.sections():
            if sect not in md_sections:
                continue
            opts = md_sections[sect]
            markdown += f"#### [{sect}]\n\n{''.join(opts)}\n\n"

        return markdown

    def write_default_ini(self, filename: pathlib.Path) -> bool:
        """Uses config registry to generate an example_options.ini file."""
        try:
            cu = configupdater.ConfigUpdater()
            cu.optionxform = str  # type: ignore

            # Add sections in order.
            for section in MUSICBOT_CONFIG_SECTIONS_ORDERED:
                cu.add_section(section)

            # add comments to head of file.
            adder = cu[MUSICBOT_CONFIG_SECTIONS_ORDERED[0]].add_before
            head_comment = (
                "This is the configuration file for MusicBot. Do not edit this file using Notepad.\n"
                "Use Notepad++ or a code editor like Visual Studio Code.\n"
                "For help, see: https://just-some-bots.github.io/MusicBot/ \n"
                "\n"
                "This file was generated by MusicBot, it contains all options set to their default values."
            )
            for line in head_comment.split("\n"):
                adder.comment(line)
            adder.space()

            for opt in self.option_list:
                if opt.default_is_empty:
                    ini_val = ""
                else:
                    ini_val = self.to_ini(opt, use_default=True)
                cu[opt.section][opt.option] = ini_val
                adder = cu[opt.section][opt.option].add_before
                if opt.comment_args:
                    comment = opt.comment % opt.comment_args
                else:
                    comment = opt.comment
                c_lines = comment.split("\n")
                if len(c_lines) > 1:
                    for line in c_lines:
                        adder.comment(line)
                else:
                    adder.comment(opt.comment)
                cu[opt.section][opt.option].add_after.space()

            with open(filename, "w", encoding="utf8") as fp:
                cu.write(fp)

            return True
        except (
            OSError,
            AttributeError,
            configparser.DuplicateSectionError,
            configparser.ParsingError,
        ):
            log.exception("Failed to save default INI file at:  %s", filename)
            return False


class ExtendedConfigParser(configparser.ConfigParser):
    """
    A collection of typed converters to extend ConfigParser.
    These methods are also responsible for validation and raising HelpfulErrors
    for issues detected with the values.
    """

    def __init__(self) -> None:
        # If empty_lines_in_values is ever true, config editing needs refactor.
        # Probably should use ConfigUpdater package instead.
        super().__init__(interpolation=None, empty_lines_in_values=False)
        self.error_preface = "Error loading config value:"

    def optionxform(self, optionstr: str) -> str:
        """
        This is an override for ConfigParser key parsing.
        by default ConfigParser uses str.lower() we just return to keep the case.
        """
        return optionstr

    def fetch_all_keys(self) -> List[str]:
        """
        Gather all config keys for all sections of this config into a list.
        This -will- return duplicate keys if they happen to exist in config.
        """
        sects = dict(self.items())
        keys = []
        for k in sects:
            s = sects[k]
            keys += list(s.keys())
        return keys

    def getstr(
        self,
        section: str,
        key: str,
        raw: bool = False,
        vars: ConfVars = None,  # pylint: disable=redefined-builtin
        fallback: str = "",
    ) -> str:
        """A version of get which strips spaces and uses fallback / default for empty values."""
        val = self.get(section, key, fallback=fallback, raw=raw, vars=vars).strip()
        if not val:
            return fallback
        return val

    def getboolean(  # type: ignore[override]
        self,
        section: str,
        option: str,
        *,
        raw: bool = False,
        vars: ConfVars = None,  # pylint: disable=redefined-builtin
        fallback: bool = False,
        **kwargs: Optional[Mapping[str, Any]],
    ) -> bool:
        """Make getboolean less bitchy about empty values, so it uses fallback instead."""
        val = self.get(section, option, fallback="", raw=raw, vars=vars).strip()
        if not val:
            return fallback

        try:
            return super().getboolean(section, option, fallback=fallback)
        except ValueError:
            return fallback

    def getownerid(
        self,
        section: str,
        key: str,
        fallback: int = 0,
        raw: bool = False,
        vars: ConfVars = None,  # pylint: disable=redefined-builtin
    ) -> int:
        """get the owner ID or 0 for auto"""
        val = self.get(section, key, fallback="", raw=raw, vars=vars).strip()
        if not val:
            return fallback
        if val.lower() == "auto":
            return 0

        try:
            return int(val)
        except ValueError as e:
            raise HelpfulError(
                # fmt: off
                "Error loading config value.\n"
                "\n"
                "Problem:\n"
                "  The owner ID in [%(section)s] > %(option)s is not valid.\n"
                "\n"
                "Solution:\n"
                "  Set %(option)s to a numerical ID or set it to `auto` or `0` for automatic owner binding.",
                # fmt: on
                fmt_args={"section": section, "option": key},
            ) from e

    def getpathlike(
        self,
        section: str,
        key: str,
        fallback: pathlib.Path,
        raw: bool = False,
        vars: ConfVars = None,  # pylint: disable=redefined-builtin
    ) -> pathlib.Path:
        """
        get a config value and parse it as a Path object.
        the `fallback` argument is required.
        """
        val = self.get(section, key, fallback="", raw=raw, vars=vars).strip()
        if not val and fallback:
            return fallback
        if not val and not fallback:
            raise ValueError(
                f"The option [{section}] > {key} does not have a valid fallback value. This is a bug!"
            )

        try:
            return pathlib.Path(val).resolve(strict=False)
        except RuntimeError as e:
            raise HelpfulError(
                # fmt: off
                "Error loading config value.\n"
                "\n"
                "Problem:\n"
                "  The config option [%(section)s] > %(option)s is not a valid file location.\n"
                "\n"
                "Solution:\n"
                "  Check the path setting and make sure the file exists and is accessible to MusicBot.",
                # fmt: on
                fmt_args={"section": section, "option": key},
            ) from e

    def getidset(
        self,
        section: str,
        key: str,
        fallback: Optional[Set[int]] = None,
        raw: bool = False,
        vars: ConfVars = None,  # pylint: disable=redefined-builtin
    ) -> Set[int]:
        """get a config value and parse it as a set of ID values."""
        val = self.get(section, key, fallback="", raw=raw, vars=vars).strip()
        if not val and fallback:
            return set(fallback)

        str_ids = val.replace(",", " ").split()
        try:
            return set(int(i) for i in str_ids)
        except ValueError as e:
            raise HelpfulError(
                # fmt: off
                "Error loading config value.\n"
                "\n"
                "Problem:\n"
                "  One of the IDs in option [%(section)s] > %(option)s is invalid.\n"
                "\n"
                "Solution:\n"
                "  Ensure all IDs are numerical, and separated only by spaces or commas.",
                # fmt: on
                fmt_args={"section": section, "option": key},
            ) from e

    def getdebuglevel(
        self,
        section: str,
        key: str,
        fallback: str = "",
        raw: bool = False,
        vars: ConfVars = None,  # pylint: disable=redefined-builtin
    ) -> DebugLevel:
        """get a config value an parse it as a logger level."""
        val = self.get(section, key, fallback="", raw=raw, vars=vars).strip().upper()
        if not val and fallback:
            if isinstance(fallback, tuple):
                val = fallback[0]
            else:
                val = fallback

        int_level = 0
        str_level = val
        if hasattr(logging, val):
            int_level = getattr(logging, val)
            return (str_level, int_level)

        int_level = getattr(logging, DEFAULT_LOG_LEVEL, logging.INFO)
        str_level = logging.getLevelName(int_level)
        log.warning(
            'Invalid DebugLevel option "%(value)s" given, falling back to level: %(fallback)s',
            {"value": val, "fallback": str_level},
        )
        return (str_level, int_level)

    def getdatasize(
        self,
        section: str,
        key: str,
        fallback: int = 0,
        raw: bool = False,
        vars: ConfVars = None,  # pylint: disable=redefined-builtin
    ) -> int:
        """get a config value and parse it as a human readable data size"""
        val = self.get(section, key, fallback="", raw=raw, vars=vars).strip()
        if not val and fallback:
            return fallback
        try:
            return format_size_to_bytes(val)
        except ValueError:
            log.warning(
                "Option [%(section)s] > %(option)s has invalid config value '%(value)s' using default instead.",
                {"section": section, "option": key, "value": val},
            )
            return fallback

    def getpercent(
        self,
        section: str,
        key: str,
        fallback: float = 0.0,
        raw: bool = False,
        vars: ConfVars = None,  # pylint: disable=redefined-builtin
    ) -> float:
        """
        Get a config value and parse it as a percentage.
        Always returns a positive value between 0 and 1 inclusive.
        """
        if fallback:
            fallback = max(0.0, min(abs(fallback), 1.0))

        val = self.get(section, key, fallback="", raw=raw, vars=vars).strip()
        if not val and fallback:
            return fallback

        v = 0.0
        # account for literal percentage character: %
        if val.startswith("%") or val.endswith("%"):
            try:
                ival = val.replace("%", "").strip()
                v = abs(int(ival)) / 100
            except (ValueError, TypeError):
                if fallback:
                    return fallback
                raise

        # account for explicit float and implied percentage.
        else:
            try:
                v = abs(float(val))
                # if greater than 1, assume implied percentage.
                if v > 1:
                    v = v / 100
            except (ValueError, TypeError):
                if fallback:
                    return fallback
                raise

        if v > 1:
            log.warning(
                "Option [%(section)s] > %(option)s has a value greater than 100 %% (%(value)s) and will be set to %(fallback)s instead.",
                {
                    "section": section,
                    "option": key,
                    "value": val,
                    "fallback": fallback if fallback else 1,
                },
            )
            v = fallback if fallback else 1

        return v

    def getduration(
        self,
        section: str,
        key: str,
        fallback: Union[int, float] = 0,
        raw: bool = False,
        vars: ConfVars = None,  # pylint: disable=redefined-builtin
    ) -> float:
        """get a config value parsed as a time duration."""
        val = self.get(section, key, fallback="", raw=raw, vars=vars).strip()
        if not val and fallback:
            return float(fallback)
        seconds = format_time_to_seconds(val)
        return float(seconds)

    def getstrset(
        self,
        section: str,
        key: str,
        fallback: Set[str],
        raw: bool = False,
        vars: ConfVars = None,  # pylint: disable=redefined-builtin
    ) -> Set[str]:
        """get a config value parsed as a set of string values."""
        val = self.get(section, key, fallback="", raw=raw, vars=vars).strip()
        if not val and fallback:
            return set(fallback)
        return set(x for x in val.replace(",", " ").split())


class ConfigRenameManager:
    """
    This class provides a method to move or rename config options.
    All renaming is done sequentially, to ensure that older versions of config
    can be carried into newer versions with minimal manual edits.
    """

    def __init__(self, config_file: pathlib.Path) -> None:
        """Register all config remaps, past or present."""
        self._cfg_file = config_file

        # The format of config remap items is as follows:
        # (origin_section, origin_name, new_section, new_name)
        # These values are case sensitive, and must match existing options.
        # If not found, no error/warning is raised, it is assumed they are renamed already.
        self._remap: List[Tuple[str, str, str, str]] = [
            # fmt: off
            # Update #1: Organize old config options into new sections.
            # Chat Commands
            ("Chat", "CommandPrefix",            "ChatCommands", "CommandPrefix"),  # noqa: E241
            ("Chat", "CommandsByMention",        "ChatCommands", "CommandsByMention"),  # noqa: E241
            ("Chat", "BindToChannels",           "ChatCommands", "BindToChannels"),  # noqa: E241
            ("Chat", "AllowUnboundServers",      "ChatCommands", "AllowUnboundServers"),  # noqa: E241
            ("MusicBot", "EnablePrefixPerGuild", "ChatCommands", "EnablePrefixPerGuild"),  # noqa: E241
            ("MusicBot", "UseAlias",             "ChatCommands", "UseAlias"),  # noqa: E241

            # Chat Responses
            ("Chat", "DMNowPlaying",                "ChatResponses", "DMNowPlaying"),  # noqa: E241
            ("Chat", "DisableNowPlayingAutomatic",  "ChatResponses", "DisableNowPlayingAutomatic"),  # noqa: E241
            ("Chat", "NowPlayingChannels",          "ChatResponses", "NowPlayingChannels"),  # noqa: E241
            ("Chat", "DeleteNowPlaying",            "ChatResponses", "DeleteNowPlaying"),  # noqa: E241
            ("MusicBot", "NowPlayingMentions",      "ChatResponses", "NowPlayingMentions"),  # noqa: E241
            ("MusicBot", "DeleteMessages",          "ChatResponses", "DeleteMessages"),  # noqa: E241
            ("MusicBot", "DeleteInvoking",          "ChatResponses", "DeleteInvoking"),  # noqa: E241
            ("MusicBot", "DeleteDelayShort",        "ChatResponses", "DeleteDelayShort"),  # noqa: E241
            ("MusicBot", "DeleteDelayLong",         "ChatResponses", "DeleteDelayLong"),  # noqa: E241
            ("MusicBot", "UseEmbeds",               "ChatResponses", "UseEmbeds"),  # noqa: E241
            ("MusicBot", "QueueLength",             "ChatResponses", "QueueLength"),  # noqa: E241
            ("MusicBot", "CustomEmbedFooter",       "ChatResponses", "CustomEmbedFooter"),  # noqa: E241
            ("MusicBot", "RemoveEmbedFooter",       "ChatResponses", "RemoveEmbedFooter"),  # noqa: E241
            ("MusicBot", "SearchList",              "ChatResponses", "SearchList"),  # noqa: E241
            ("MusicBot", "DefaultSearchResults",    "ChatResponses", "DefaultSearchResults"),  # noqa: E241

            # Playback
            ("MusicBot", "AutoPause",                   "Playback", "AutoPause"),  # noqa: E241
            ("MusicBot", "DefaultVolume",               "Playback", "DefaultVolume"),  # noqa: E241
            ("MusicBot", "DefaultSpeed",                "Playback", "DefaultSpeed"),  # noqa: E241
            ("MusicBot", "SkipsRequired",               "Playback", "SkipsRequired"),  # noqa: E241
            ("MusicBot", "SkipRatio",                   "Playback", "SkipRatio"),  # noqa: E241
            ("MusicBot", "PersistentQueue",             "Playback", "PersistentQueue"),  # noqa: E241
            ("MusicBot", "PreDownloadNextSong",         "Playback", "PreDownloadNextSong"),  # noqa: E241
            ("MusicBot", "AllowAuthorSkip",             "Playback", "AllowAuthorSkip"),  # noqa: E241
            ("MusicBot", "UseExperimentalEqualization", "Playback", "UseExperimentalEqualization"),  # noqa: E241
            ("MusicBot", "LegacySkip",                  "Playback", "LegacySkip"),  # noqa: E241
            ("MusicBot", "RoundRobinQueue",             "Playback", "RoundRobinQueue"),  # noqa: E241
            ("MusicBot", "EnableLocalMedia",            "Playback", "EnableLocalMedia"),  # noqa: E241
            ("MusicBot", "UnpausePlayerOnPlay",         "Playback", "UnpausePlayerOnPlay"),  # noqa: E241
            ("MusicBot", "UseOpusAudio",                "Playback", "UseOpusAudio"),  # noqa: E241
            ("MusicBot", "UseOpusProbe",                "Playback", "UseOpusProbe"),  # noqa: E241

            # Auto Playlist
            ("MusicBot", "UseAutoPlaylist",             "AutoPlaylist", "UseAutoPlaylist"),  # noqa: E241
            ("MusicBot", "AutoPlaylistRandom",          "AutoPlaylist", "AutoPlaylistRandom"),  # noqa: E241
            ("MusicBot", "AutoPlaylistAutoSkip",        "AutoPlaylist", "AutoPlaylistAutoSkip"),  # noqa: E241
            ("MusicBot", "AutoPlaylistRemoveBlocked",   "AutoPlaylist", "AutoPlaylistRemoveBlocked"),  # noqa: E241
            ("MusicBot", "RemoveFromAPOnError",         "AutoPlaylist", "RemoveFromAPOnError"),  # noqa: E241
            ("MusicBot", "SavePlayedHistoryGlobal",     "AutoPlaylist", "SavePlayedHistoryGlobal"),  # noqa: E241
            ("MusicBot", "SavePlayedHistoryGuilds",     "AutoPlaylist", "SavePlayedHistoryGuilds"),  # noqa: E241

            # MusicBot
            ("Chat", "AutojoinChannels", "MusicBot", "AutojoinChannels"),
            # End Update #1
            # fmt: on
        ]
        self.update_config_options()

    def _handle_remap_item(
        self, cu: configupdater.ConfigUpdater, remap: Tuple[str, str, str, str]
    ) -> None:
        """Logic for updating one item from the remap."""
        o_sect, o_opt, n_sect, n_opt = remap

        log.debug(
            "Renaming INI file entry [%(old_s)s] > %(old_o)s  to  [%(new_s)s] > %(new_o)s",
            {"old_s": o_sect, "old_o": o_opt, "new_s": n_sect, "new_o": n_opt},
        )

        opt = cu.get(o_sect, o_opt)
        # Simply rename the config in-place if possible.
        if o_sect == n_sect:
            cu[n_sect][o_opt].key = n_opt

        # Move the option and comments.
        else:
            opt = cu[o_sect][o_opt]
            cu[n_sect][n_opt] = opt.value
            blocks = []
            prev_block = opt.previous_block
            while prev_block is not None:
                if not isinstance(prev_block, (Comment, Space)):
                    break
                if prev_block.has_container():
                    next_up = prev_block.previous_block
                    prev_block.detach()
                else:
                    next_up = None
                blocks.append(prev_block)
                prev_block = next_up

            blocks.reverse()
            for b in blocks:
                if isinstance(b, Comment):
                    cu[n_sect][n_opt].add_before.comment(str(b))
                if isinstance(b, Space):
                    cu[n_sect][n_opt].add_before.space(len(b.lines))
            cu.remove_option(o_sect, o_opt)

    def update_config_options(self) -> None:
        """
        Uses ConfigUpdater to find mapped options and rename them.
        """
        try:
            cu = configupdater.ConfigUpdater()
            cu.optionxform = str  # type: ignore
            cu.read(self._cfg_file, encoding="utf8")

            sections = MUSICBOT_CONFIG_SECTIONS_ORDERED
            updates = 0

            # Make sure config has the required sections, in order.
            for i, sect in enumerate(sections):
                prv = ""
                nxt = ""
                if 0 < i < len(sections):
                    prv = sections[i - 1]
                if i < len(sections) - 2:
                    nxt = sections[i + 1]

                if not cu.has_section(sect):
                    if prv and cu.has_section(prv):
                        cu[prv].add_after.section(sect)
                    elif nxt and cu.has_section(nxt):
                        cu[nxt].add_before.section(sect)
                    else:
                        cu.add_section(sect)
                    updates += 1

            # check if we need to update any options.
            for item in self._remap:
                if cu.has_option(item[0], item[1]):
                    updates += 1
                    self._handle_remap_item(cu, item)

            if updates:
                log.debug("Upgrading config file with renamed options...")
                # Ensure spaces between sections and options.
                for s in cu.iter_sections():
                    # Section end spaces.
                    if not isinstance(s.last_block, Space):
                        s.add_after.space(2)

                    # Option spacing.
                    for opt in s.iter_options():
                        if not isinstance(opt.next_block, Space):
                            opt.add_after.space(1)

                # backup original file.
                dt = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                bkp_file = self._cfg_file.with_suffix(f".ini.old_{dt}")
                try:
                    shutil.copy(self._cfg_file, bkp_file)
                except OSError as e:
                    raise RuntimeError(
                        "Could not create a backup copy of options.ini file."
                    ) from e

                # write the changes to file.
                # cu.first_block.add_before.comment("NOTICE:  Options have been renamed.")
                cu.update_file()

        except (
            OSError,
            AttributeError,
            configparser.DuplicateOptionError,
            configparser.DuplicateSectionError,
            configparser.ParsingError,
        ):
            log.exception(
                "Failed to upgrade config.  You'll need to upgrade it manually."
            )


class Blocklist:
    """
    Base class for more specific block lists.
    """

    def __init__(self, blocklist_file: pathlib.Path, comment_char: str = "#") -> None:
        """
        Loads a block list into memory, ignoring empty lines and commented lines,
        as well as striping comments from string remainders.

        Note: If the default comment character `#` is used, this function will
        strip away discriminators from usernames.
        User IDs should be used instead, if definite ID is needed.

        Similarly, URL fragments will be removed from URLs as well. This typically
        is not an issue as fragments are only client-side by specification.

        :param: blocklist_file:  A file path to a block list, which will be created if it does not exist.
        :param: comment_char:  A character used to denote comments in the file.
        """
        self._blocklist_file: pathlib.Path = blocklist_file
        self._comment_char = comment_char
        self.items: Set[str] = set()

        self.load_blocklist_file()

    def __len__(self) -> int:
        """Gets the number of items in the block list."""
        return len(self.items)

    def load_blocklist_file(self) -> bool:
        """
        Loads (or reloads) the block list file into memory.

        :returns:  True if loading finished False if it could not for any reason.
        """
        if not self._blocklist_file.is_file():
            log.warning("Block list file not found:  %s", self._blocklist_file)
            return False

        try:
            with open(self._blocklist_file, "r", encoding="utf8") as f:
                for line in f:
                    line = line.strip()

                    if line:
                        # Skip lines starting with comments.
                        if self._comment_char and line.startswith(self._comment_char):
                            continue

                        # strip comments from the remainder of a line.
                        if self._comment_char and self._comment_char in line:
                            line = line.split(self._comment_char, maxsplit=1)[0].strip()

                        self.items.add(line)
            return True
        except OSError:
            log.error(
                "Could not load block list from file:  %s",
                self._blocklist_file,
                exc_info=True,
            )

        return False

    def append_items(
        self,
        items: Iterable[str],
        comment: str = "",
        spacer: str = "\t\t%s ",
    ) -> bool:
        """
        Appends the given `items` to the block list file.

        :param: items:  An iterable of strings to be appended.
        :param: comment:  An optional comment added to each new item.
        :param: spacer:
            A format string for placing comments, where %s is replaced with the
            comment character used by this block list.

        :returns: True if updating is successful.
        """
        if not self._blocklist_file.is_file():
            return False

        try:
            space = ""
            if comment:
                space = spacer.format(self._comment_char)
            with open(self._blocklist_file, "a", encoding="utf8") as f:
                for item in items:
                    f.write(f"{item}{space}{comment}\n")
                    self.items.add(item)
            return True
        except OSError:
            log.error(
                "Could not update the block list file:  %s",
                self._blocklist_file,
                exc_info=True,
            )
        return False

    def remove_items(self, items: Iterable[str]) -> bool:
        """
        Find and remove the given `items` from the block list file.

        :returns: True if updating is successful.
        """
        if not self._blocklist_file.is_file():
            return False

        self.items.difference_update(set(items))

        try:
            # read the original file in and remove lines with our items.
            # this is done to preserve the comments and formatting.
            lines = self._blocklist_file.read_text(encoding="utf8").split("\n")
            with open(self._blocklist_file, "w", encoding="utf8") as f:
                for line in lines:
                    # strip comment from line.
                    line_strip = line.split(self._comment_char, maxsplit=1)[0].strip()

                    # don't add the line if it matches any given items.
                    if line in items or line_strip in items:
                        continue
                    f.write(f"{line}\n")

        except OSError:
            log.error(
                "Could not update the block list file:  %s",
                self._blocklist_file,
                exc_info=True,
            )
        return False


class UserBlocklist(Blocklist):
    def __init__(self, blocklist_file: pathlib.Path, comment_char: str = "#") -> None:
        """
        A UserBlocklist manages a block list which contains discord usernames and IDs.
        """
        self._handle_legacy_file(blocklist_file)

        c = comment_char
        create_file_ifnoexist(
            blocklist_file,
            [
                f"{c} MusicBot discord user block list denies all access to bot.\n",
                f"{c} Add one User ID or username per each line.\n",
                f"{c} Nick-names or server-profile names are not checked.\n",
                f"{c} User ID is prefered. Usernames with discriminators (ex: User#1234) may not work.\n",
                f"{c} In this file '{c}' is a comment character. All characters following it are ignored.\n",
            ],
        )
        super().__init__(blocklist_file, comment_char)
        log.debug(
            "Loaded User Block list with %s entries.",
            len(self.items),
        )

    def _handle_legacy_file(self, new_file: pathlib.Path) -> None:
        """
        In case the original, ambiguous block list file exists, lets rename it.
        """
        old_file = write_path(DEPRECATED_USER_BLACKLIST)
        if old_file.is_file() and not new_file.is_file():
            log.warning(
                "We found a legacy blacklist file, it will be renamed to:  %s",
                new_file,
            )
            old_file.rename(new_file)

    def is_blocked(self, user: Union["discord.User", "discord.Member"]) -> bool:
        """
        Checks if the given `user` has their discord username or ID listed in the loaded block list.
        """
        user_id = str(user.id)
        # this should only consider discord username, not nick/ server profile.
        user_name = user.name
        if user_id in self.items or user_name in self.items:
            return True
        return False

    def is_disjoint(
        self, users: Iterable[Union["discord.User", "discord.Member"]]
    ) -> bool:
        """
        Returns False if any of the `users` are listed in the block list.

        :param: users:  A list or set of discord Users or Members.
        """
        return not any(self.is_blocked(u) for u in users)


class SongBlocklist(Blocklist):
    def __init__(self, blocklist_file: pathlib.Path, comment_char: str = "#") -> None:
        """
        A SongBlocklist manages a block list which contains song URLs or other
        words and phrases that should be blocked from playback.
        """
        c = comment_char
        create_file_ifnoexist(
            blocklist_file,
            [
                f"{c} MusicBot discord song block list denies songs by URL or Title.\n",
                f"{c} Add one URL or Title per line. Leading and trailing space is ignored.\n",
                f"{c} This list is matched loosely, with case sensitivity, so adding 'press'\n",
                f"{c} will block 'juice press' and 'press release' but not 'Press'\n",
                f"{c} Block list entries will be tested against input and extraction info.\n",
                f"{c} Lines starting with {c} are comments. All characters follow it are ignored.\n",
            ],
        )
        super().__init__(blocklist_file, comment_char)
        log.debug("Loaded a Song Block list with %s entries.", len(self.items))

    def is_blocked(self, song_subject: str) -> bool:
        """
        Checks if the given `song_subject` contains any entry in the song block list.

        :param: song_subject:  Any input the bot player commands will take or pass to ytdl extraction.
        """
        return any(x in song_subject for x in self.items)
