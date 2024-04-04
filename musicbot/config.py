import configparser
import logging
import os
import pathlib
import shutil
import sys
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Set, Tuple, Union

from .constants import (
    BUNDLED_AUTOPLAYLIST_FILE,
    DEFAULT_AUDIO_CACHE_PATH,
    DEFAULT_AUTOPLAYLIST_FILE,
    DEFAULT_FOOTER_TEXT,
    DEFAULT_I18N_FILE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_OPTIONS_FILE,
    DEFAULT_SONG_BLOCKLIST_FILE,
    DEFAULT_USER_BLOCKLIST_FILE,
    DEPRECATED_USER_BLACKLIST,
    EXAMPLE_OPTIONS_FILE,
)
from .exceptions import HelpfulError
from .utils import format_size_to_bytes, format_time_to_seconds, set_logging_level

if TYPE_CHECKING:
    import discord

    from .bot import MusicBot

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
        self.find_config()

        config = ExtendedConfigParser()
        config.read(config_file, encoding="utf-8")

        confsections = {
            "Credentials",
            "Permissions",
            "Chat",
            "MusicBot",
            "Files",
        }.difference(config.sections())
        if confsections:
            sections_str = ", ".join([f"[{s}]" for s in confsections])
            raise HelpfulError(
                "One or more required config sections are missing.",
                "Fix your config.  Each [Section] should be on its own line with "
                f"nothing else on it.  The following sections are missing: {sections_str}",
                preface="An error has occured parsing the config:\n",
            )

        self._confpreface = "An error has occured reading the config:\n"
        self._confpreface2 = "An error has occured validating the config:\n"

        self._login_token: str = config.get(
            "Credentials", "Token", fallback=ConfigDefaults.token
        )

        self.auth: Tuple[str] = ("",)

        self.spotify_clientid = config.get(
            "Credentials", "Spotify_ClientID", fallback=ConfigDefaults.spotify_clientid
        )
        self.spotify_clientsecret = config.get(
            "Credentials",
            "Spotify_ClientSecret",
            fallback=ConfigDefaults.spotify_clientsecret,
        )

        self.owner_id: int = config.getownerid(
            "Permissions", "OwnerID", fallback=ConfigDefaults.owner_id
        )
        self.dev_ids: Set[int] = config.getidset(
            "Permissions", "DevIDs", fallback=ConfigDefaults.dev_ids
        )
        self.bot_exception_ids = config.getidset(
            "Permissions", "BotExceptionIDs", fallback=ConfigDefaults.bot_exception_ids
        )

        self.command_prefix = config.get(
            "Chat", "CommandPrefix", fallback=ConfigDefaults.command_prefix
        )
        self.bound_channels = config.getidset(
            "Chat", "BindToChannels", fallback=ConfigDefaults.bound_channels
        )
        self.unbound_servers = config.getboolean(
            "Chat", "AllowUnboundServers", fallback=ConfigDefaults.unbound_servers
        )
        self.autojoin_channels = config.getidset(
            "Chat", "AutojoinChannels", fallback=ConfigDefaults.autojoin_channels
        )
        self.dm_nowplaying = config.getboolean(
            "Chat", "DMNowPlaying", fallback=ConfigDefaults.dm_nowplaying
        )
        self.no_nowplaying_auto = config.getboolean(
            "Chat",
            "DisableNowPlayingAutomatic",
            fallback=ConfigDefaults.no_nowplaying_auto,
        )
        self.nowplaying_channels = config.getidset(
            "Chat", "NowPlayingChannels", fallback=ConfigDefaults.nowplaying_channels
        )
        self.delete_nowplaying = config.getboolean(
            "Chat", "DeleteNowPlaying", fallback=ConfigDefaults.delete_nowplaying
        )

        self.default_volume = config.getfloat(
            "MusicBot", "DefaultVolume", fallback=ConfigDefaults.default_volume
        )
        self.skips_required = config.getint(
            "MusicBot", "SkipsRequired", fallback=ConfigDefaults.skips_required
        )
        self.skip_ratio_required = config.getfloat(
            "MusicBot", "SkipRatio", fallback=ConfigDefaults.skip_ratio_required
        )
        self.save_videos = config.getboolean(
            "MusicBot", "SaveVideos", fallback=ConfigDefaults.save_videos
        )
        self.storage_limit_bytes = config.getdatasize(
            "MusicBot", "StorageLimitBytes", fallback=ConfigDefaults.storage_limit_bytes
        )
        self.storage_limit_days = config.getint(
            "MusicBot", "StorageLimitDays", fallback=ConfigDefaults.storage_limit_days
        )
        self.storage_retain_autoplay = config.getboolean(
            "MusicBot",
            "StorageRetainAutoPlay",
            fallback=ConfigDefaults.storage_retain_autoplay,
        )
        self.now_playing_mentions = config.getboolean(
            "MusicBot",
            "NowPlayingMentions",
            fallback=ConfigDefaults.now_playing_mentions,
        )
        self.auto_summon = config.getboolean(
            "MusicBot", "AutoSummon", fallback=ConfigDefaults.auto_summon
        )
        self.auto_playlist = config.getboolean(
            "MusicBot", "UseAutoPlaylist", fallback=ConfigDefaults.auto_playlist
        )
        self.auto_playlist_random = config.getboolean(
            "MusicBot",
            "AutoPlaylistRandom",
            fallback=ConfigDefaults.auto_playlist_random,
        )
        self.auto_pause = config.getboolean(
            "MusicBot", "AutoPause", fallback=ConfigDefaults.auto_pause
        )
        self.delete_messages = config.getboolean(
            "MusicBot", "DeleteMessages", fallback=ConfigDefaults.delete_messages
        )
        self.delete_invoking = config.getboolean(
            "MusicBot", "DeleteInvoking", fallback=ConfigDefaults.delete_invoking
        )
        self.persistent_queue = config.getboolean(
            "MusicBot", "PersistentQueue", fallback=ConfigDefaults.persistent_queue
        )
        self.status_message = config.get(
            "MusicBot", "StatusMessage", fallback=ConfigDefaults.status_message
        )
        self.write_current_song = config.getboolean(
            "MusicBot", "WriteCurrentSong", fallback=ConfigDefaults.write_current_song
        )
        self.allow_author_skip = config.getboolean(
            "MusicBot", "AllowAuthorSkip", fallback=ConfigDefaults.allow_author_skip
        )
        self.use_experimental_equalization = config.getboolean(
            "MusicBot",
            "UseExperimentalEqualization",
            fallback=ConfigDefaults.use_experimental_equalization,
        )
        self.embeds = config.getboolean(
            "MusicBot", "UseEmbeds", fallback=ConfigDefaults.embeds
        )
        self.queue_length = config.getint(
            "MusicBot", "QueueLength", fallback=ConfigDefaults.queue_length
        )
        self.remove_ap = config.getboolean(
            "MusicBot", "RemoveFromAPOnError", fallback=ConfigDefaults.remove_ap
        )
        self.show_config_at_start = config.getboolean(
            "MusicBot",
            "ShowConfigOnLaunch",
            fallback=ConfigDefaults.show_config_at_start,
        )
        self.legacy_skip = config.getboolean(
            "MusicBot", "LegacySkip", fallback=ConfigDefaults.legacy_skip
        )
        self.leavenonowners = config.getboolean(
            "MusicBot",
            "LeaveServersWithoutOwner",
            fallback=ConfigDefaults.leavenonowners,
        )
        self.usealias = config.getboolean(
            "MusicBot", "UseAlias", fallback=ConfigDefaults.usealias
        )
        self.footer_text = config.get(
            "MusicBot", "CustomEmbedFooter", fallback=ConfigDefaults.footer_text
        )
        self.self_deafen = config.getboolean(
            "MusicBot", "SelfDeafen", fallback=ConfigDefaults.self_deafen
        )
        self.leave_inactive_channel = config.getboolean(
            "MusicBot",
            "LeaveInactiveVC",
            fallback=ConfigDefaults.leave_inactive_channel,
        )
        self.leave_inactive_channel_timeout = config.getduration(
            "MusicBot",
            "LeaveInactiveVCTimeOut",
            fallback=ConfigDefaults.leave_inactive_channel_timeout,
        )
        self.leave_after_queue_empty = config.getboolean(
            "MusicBot",
            "LeaveAfterSong",
            fallback=ConfigDefaults.leave_after_queue_empty,
        )
        self.leave_player_inactive_for = config.getduration(
            "MusicBot",
            "LeavePlayerInactiveFor",
            fallback=ConfigDefaults.leave_player_inactive_for,
        )
        self.searchlist = config.getboolean(
            "MusicBot", "SearchList", fallback=ConfigDefaults.searchlist
        )
        self.defaultsearchresults = config.getint(
            "MusicBot",
            "DefaultSearchResults",
            fallback=ConfigDefaults.defaultsearchresults,
        )

        self.enable_options_per_guild = config.getboolean(
            "MusicBot",
            "EnablePrefixPerGuild",
            fallback=ConfigDefaults.enable_options_per_guild,
        )

        self.round_robin_queue = config.getboolean(
            "MusicBot",
            "RoundRobinQueue",
            fallback=ConfigDefaults.defaultround_robin_queue,
        )

        dbg_str, dbg_int = config.getdebuglevel(
            "MusicBot", "DebugLevel", fallback=ConfigDefaults.debug_level_str
        )
        self.debug_level_str: str = dbg_str
        self.debug_level: int = dbg_int
        self.debug_mode: bool = self.debug_level <= logging.DEBUG
        set_logging_level(self.debug_level)

        self.user_blocklist_enabled = config.getboolean(
            "MusicBot",
            "EnableUserBlocklist",
            fallback=ConfigDefaults.user_blocklist_enabled,
        )
        self.user_blocklist_file = config.getpathlike(
            "Files", "UserBlocklistFile", fallback=ConfigDefaults.user_blocklist_file
        )
        self.user_blocklist: "UserBlocklist" = UserBlocklist(self.user_blocklist_file)

        self.song_blocklist_enabled = config.getboolean(
            "MusicBot",
            "EnableSongBlocklist",
            fallback=ConfigDefaults.song_blocklist_enabled,
        )
        self.song_blocklist_file = config.getpathlike(
            "Files", "SongBlocklistFile", fallback=ConfigDefaults.song_blocklist_file
        )
        self.song_blocklist: "SongBlocklist" = SongBlocklist(self.song_blocklist_file)

        self.auto_playlist_file = config.getpathlike(
            "Files", "AutoPlaylistFile", fallback=ConfigDefaults.auto_playlist_file
        )
        self.i18n_file = config.getpathlike(
            "Files", "i18nFile", fallback=ConfigDefaults.i18n_file
        )
        self.audio_cache_path = config.getpathlike(
            "Files", "AudioCachePath", fallback=ConfigDefaults.audio_cache_path
        )

        # This value gets set dynamically, based on success with API authentication.
        self.spotify_enabled = False

        self.run_checks()

        self.missing_keys: Set[str] = set()
        self.check_changes(config)

        self.setup_autoplaylist()

    def check_changes(self, conf: "ExtendedConfigParser") -> None:
        """
        Load the example options file and use it to detect missing config.
        The results are stored in self.missing_keys as a set difference.

        Note that keys from all sections are stored in one list, which is
        then reduced to a set.  If sections contain overlapping key names,
        this logic will not detect a key missing from one section that was
        present in another.

        :param: conf:  the currently loaded config file parser object.
        """
        exfile = pathlib.Path(EXAMPLE_OPTIONS_FILE)
        if exfile.is_file():
            usr_keys = conf.fetch_all_keys()
            exconf = ExtendedConfigParser()
            if not exconf.read(exfile, encoding="utf-8"):
                log.error(
                    "Cannot detect changes in config, example options file is missing."
                )
                return
            ex_keys = exconf.fetch_all_keys()
            if set(usr_keys) != set(ex_keys):
                self.missing_keys = set(ex_keys) - set(
                    usr_keys
                )  # to raise this as an issue in bot.py later

    def run_checks(self) -> None:
        """
        Validation and some sanity check logic for bot settings.

        :raises: musicbot.exceptions.HelpfulError
            if some validation failed that the user needs to correct.
        """
        if self.i18n_file != ConfigDefaults.i18n_file and not os.path.isfile(
            self.i18n_file
        ):
            log.warning(
                "i18n file does not exist. Trying to fallback to: %s",
                ConfigDefaults.i18n_file,
            )
            self.i18n_file = ConfigDefaults.i18n_file

        if not os.path.isfile(self.i18n_file):
            raise HelpfulError(
                "Your i18n file was not found, and we could not fallback.",
                "As a result, the bot cannot launch. Have you moved some files? "
                "Try pulling the recent changes from Git, or resetting your local repo.",
                preface=self._confpreface,
            )

        log.info("Using i18n: %s", self.i18n_file)

        if self.audio_cache_path:
            try:
                acpath = self.audio_cache_path
                if acpath.is_file():
                    raise HelpfulError(
                        "AudioCachePath config option is a file path.",
                        "Change it to a directory / folder path instead.",
                        preface=self._confpreface2,
                    )
                # Might as well test for multiple issues here since we can give feedback.
                if not acpath.is_dir():
                    acpath.mkdir(parents=True, exist_ok=True)
                actest = acpath.joinpath(".bot-test-write")
                actest.touch(exist_ok=True)
                actest.unlink(missing_ok=True)
            except PermissionError as e:
                raise HelpfulError(
                    "AudioCachePath config option cannot be used due to invalid permissions.",
                    "Check that directory permissions and ownership are correct.",
                    preface=self._confpreface2,
                ) from e
            except Exception as e:
                log.exception(
                    "Some other exception was thrown while validating AudioCachePath."
                )
                raise HelpfulError(
                    "AudioCachePath config option could not be set due to some exception we did not expect.",
                    "Double check the setting and maybe report an issue.",
                    preface=self._confpreface2,
                ) from e

        log.info("Audio Cache will be stored in:  %s", self.audio_cache_path)

        if not self._login_token:
            # Attempt to fallback to an environment variable.
            env_token = os.environ.get("MUSICBOT_TOKEN")
            if env_token:
                self._login_token = env_token
                self.auth = (self._login_token,)
            else:
                raise HelpfulError(
                    "No bot token was specified in the config, or as an environment variable.",
                    "As of v1.9.6_1, you are required to use a Discord bot account. "
                    "See https://github.com/Just-Some-Bots/MusicBot/wiki/FAQ for info.",
                    preface=self._confpreface,
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

    # TODO: Add save function for future editing of options with commands
    #       Maybe add warnings about fields missing from the config file

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
                log.debug("Acquired owner id via API")
            else:
                raise HelpfulError(
                    "Discord app info is not available. (Probably a bug!)",
                    "You may need to set OwnerID config manually, and report this.",
                    preface="Error fetching OwnerID automatically:\n",
                )

        if not bot.user:
            log.critical("MusicBot does not have a user instance, cannot proceed.")
            raise RuntimeError("This cannot continue.")

        if self.owner_id == bot.user.id:
            raise HelpfulError(
                "Your OwnerID is incorrect or you've used the wrong credentials.",
                "The bot's user ID and the id for OwnerID is identical. "
                "This is wrong. The bot needs a bot account to function, "
                "meaning you cannot use your own account to run the bot on. "
                "The OwnerID is the id of the owner, not the bot. "
                "Figure out which one is which and use the correct information.",
                preface=self._confpreface2,
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
        config = configparser.ConfigParser(interpolation=None)

        # Check for options.ini and copy example ini if missing.
        if not self.config_file.is_file():
            ini_file = self.config_file.with_suffix(".ini")
            if ini_file.is_file():
                try:
                    # Explicit compat with python 3.8
                    if sys.version_info >= (3, 9):
                        shutil.move(ini_file, self.config_file)
                    else:
                        # shutil.move in 3.8 expects str and not path-like.
                        shutil.move(str(ini_file), str(self.config_file))
                    log.info(
                        "Moving %s to %s, you should probably turn file extensions on.",
                        ini_file,
                        self.config_file,
                    )
                except (
                    OSError,
                    IsADirectoryError,
                    NotADirectoryError,
                    FileExistsError,
                    PermissionError,
                ) as e:
                    log.exception(
                        "Something went wrong while trying to move .ini to config file path."
                    )
                    raise HelpfulError(
                        f"Config file move failed due to error:  {str(e)}",
                        "Verify your config folder and files exist, and can be read by the bot.",
                    ) from e

            elif os.path.isfile(EXAMPLE_OPTIONS_FILE):
                shutil.copy(EXAMPLE_OPTIONS_FILE, self.config_file)
                log.warning(
                    "Options file not found, copying example file:  %s",
                    EXAMPLE_OPTIONS_FILE,
                )

            else:
                raise HelpfulError(
                    "Your config files are missing. Neither options.ini nor example_options.ini were found.",
                    "Grab the files back from the archive or remake them yourself and copy paste the content "
                    "from the repo. Stop removing important files!",
                )

        # load the config and check if settings are configured.
        if not config.read(self.config_file, encoding="utf-8"):
            c = configparser.ConfigParser()
            owner_id = ""
            try:
                c.read(self.config_file, encoding="utf-8")
                owner_id = c.get("Permissions", "OwnerID", fallback="").strip().lower()

                if not owner_id.isdigit() and owner_id != "auto":
                    log.critical(
                        "Please configure settings in '%s' and re-run the bot.",
                        DEFAULT_OPTIONS_FILE,
                    )
                    sys.exit(1)

            except ValueError as e:  # Config id value was changed but its not valid
                raise HelpfulError(
                    "Invalid config value for OwnerID",
                    "The OwnerID option requires a user ID number or 'auto'.",
                ) from e

    def setup_autoplaylist(self) -> None:
        """
        Check for and copy the bundled playlist file if the configured file is empty.
        Also set up file paths for playlist removal audits and for cache-map data.
        """
        if not self.auto_playlist_file.is_file():
            bundle_file = pathlib.Path(BUNDLED_AUTOPLAYLIST_FILE)
            if bundle_file.is_file():
                shutil.copy(bundle_file, self.auto_playlist_file)
                log.debug(
                    "Copying bundled autoplaylist '%s' to '%s'",
                    BUNDLED_AUTOPLAYLIST_FILE,
                    self.auto_playlist_file,
                )
            else:
                log.warning(
                    "Missing bundled autoplaylist file, cannot pre-load playlist."
                )

        # ensure cache map and removed files have values based on the configured file.
        stem = self.auto_playlist_file.stem
        ext = self.auto_playlist_file.suffix

        ap_removed_file = self.auto_playlist_file.with_name(f"{stem}_removed{ext}")
        ap_cachemap_file = self.auto_playlist_file.with_name(f"{stem}.cachemap.json")

        self.auto_playlist_removed_file = ap_removed_file
        self.auto_playlist_cachemap_file = ap_cachemap_file


class ConfigDefaults:
    """
    This class contains default values used mainly as config fallback values.
    """

    owner_id: int = 0
    token: str = ""
    dev_ids: Set[int] = set()
    bot_exception_ids: Set[int] = set()

    spotify_clientid: str = ""
    spotify_clientsecret: str = ""

    command_prefix: str = "!"
    bound_channels: Set[int] = set()
    unbound_servers: bool = False
    autojoin_channels: Set[int] = set()
    dm_nowplaying: bool = False
    no_nowplaying_auto: bool = False
    nowplaying_channels: Set[int] = set()
    delete_nowplaying: bool = True

    default_volume: float = 0.15
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
    auto_pause: bool = True
    delete_messages: bool = True
    delete_invoking: bool = False
    persistent_queue: bool = True

    debug_level: int = getattr(logging, DEFAULT_LOG_LEVEL, logging.INFO)
    debug_level_str: str = (
        DEFAULT_LOG_LEVEL
        if logging.getLevelName(debug_level) == DEFAULT_LOG_LEVEL
        else "INFO"
    )

    status_message: str = ""
    write_current_song: bool = False
    allow_author_skip: bool = True
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
    defaultround_robin_queue: bool = False

    song_blocklist: Set[str] = set()
    user_blocklist: Set[int] = set()
    song_blocklist_enabled: bool = False
    # default true here since the file being populated was previously how it was enabled.
    user_blocklist_enabled: bool = True

    # Create path objects from the constants.
    options_file: pathlib.Path = pathlib.Path(DEFAULT_OPTIONS_FILE)
    user_blocklist_file: pathlib.Path = pathlib.Path(DEFAULT_USER_BLOCKLIST_FILE)
    song_blocklist_file: pathlib.Path = pathlib.Path(DEFAULT_SONG_BLOCKLIST_FILE)
    auto_playlist_file: pathlib.Path = pathlib.Path(DEFAULT_AUTOPLAYLIST_FILE)
    i18n_file: pathlib.Path = pathlib.Path(DEFAULT_I18N_FILE)
    audio_cache_path: pathlib.Path = pathlib.Path(DEFAULT_AUDIO_CACHE_PATH).absolute()


class ExtendedConfigParser(configparser.ConfigParser):
    """
    A collection of typed converters to extend ConfigParser.
    These methods are also responsible for validation and raising HelpfulErrors
    for issues detected with the values.
    """

    def __init__(self) -> None:
        super().__init__(interpolation=None)

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

    def getownerid(
        self,
        section: str,
        key: str,
        fallback: int = 0,
        raw: bool = False,  # pylint: disable=unused-argument
        vars: Any = None,  # pylint: disable=unused-argument,redefined-builtin
    ) -> int:
        """get the owner ID or 0 for auto"""
        val = self.get(section, key, fallback="").strip()
        if not val:
            return fallback
        if val.lower() == "auto":
            return 0

        try:
            return int(val)
        except ValueError as e:
            raise HelpfulError(
                f"OwnerID is not valid. Your setting:  {val}",
                "Set OwnerID to a numerical ID or set it to 'auto' to have the bot find it.",
                preface="Error while loading config:\n",
            ) from e

    def getpathlike(
        self,
        section: str,
        key: str,
        fallback: pathlib.Path,
        raw: bool = False,  # pylint: disable=unused-argument
        vars: Any = None,  # pylint: disable=unused-argument,redefined-builtin
    ) -> pathlib.Path:
        """
        get a config value and parse it as a Path object.
        the `fallback` argument is required.
        """
        val = self.get(section, key, fallback="").strip()
        if not val:
            return fallback
        return pathlib.Path(val)

    def getidset(
        self,
        section: str,
        key: str,
        fallback: Optional[Set[int]] = None,
        raw: bool = False,  # pylint: disable=unused-argument
        vars: Any = None,  # pylint: disable=unused-argument,redefined-builtin
    ) -> Set[int]:
        """get a config value and parse it as a set of ID values."""
        val = self.get(section, key, fallback="").strip()
        if not val and fallback:
            return set(fallback)

        str_ids = val.replace(",", " ").split()
        try:
            return set(int(i) for i in str_ids)
        except ValueError as e:
            raise HelpfulError(
                f"One of the IDs in your config `{key}` is invalid.",
                "Ensure all IDs are numerical, and separated only by spaces or commas.",
                preface="Error while loading config:\n",
            ) from e

    def getdebuglevel(
        self,
        section: str,
        key: str,
        fallback: str = "",
        raw: bool = False,  # pylint: disable=unused-argument
        vars: Any = None,  # pylint: disable=unused-argument,redefined-builtin
    ) -> Tuple[str, int]:
        """get a config value an parse it as a logger level."""
        val = self.get(section, key, fallback="").strip().upper()
        if not val and fallback:
            val = fallback.upper()

        int_level = 0
        str_level = val
        if hasattr(logging, val):
            int_level = getattr(logging, val)
            return (str_level, int_level)

        int_level = getattr(logging, DEFAULT_LOG_LEVEL, logging.INFO)
        str_level = logging.getLevelName(int_level)
        log.warning(
            'Invalid DebugLevel option "%s" given, falling back to level: %s',
            val,
            str_level,
        )
        return (str_level, int_level)

    def getdatasize(
        self,
        section: str,
        key: str,
        fallback: int = 0,
        raw: bool = False,  # pylint: disable=unused-argument
        vars: Any = None,  # pylint: disable=unused-argument,redefined-builtin
    ) -> int:
        """get a config value and parse it as a human readable data size"""
        val = self.get(section, key, fallback="").strip()
        if not val and fallback:
            return fallback
        try:
            return format_size_to_bytes(val)
        except ValueError:
            log.warning(
                "Config '%s' has invalid config value '%s' using default instead.",
                key,
                val,
            )
            return fallback

    def getduration(
        self,
        section: str,
        key: str,
        fallback: Union[int, float] = 0,
        raw: bool = False,  # pylint: disable=unused-argument,
        vars: Any = None,  # pylint: disable=unused-argument,redefined-builtin
    ) -> float:
        """get a config value parsed as a time duration."""
        val = self.get(section, key, fallback="").strip()
        if not val and fallback:
            return float(fallback)
        seconds = format_time_to_seconds(val)
        return float(seconds)

    def getstrset(  # pylint: disable=dangerous-default-value
        self,
        section: str,
        key: str,
        fallback: Set[str] = set(),
        raw: bool = False,  # pylint: disable=unused-argument
        vars: Any = None,  # pylint: disable=unused-argument,redefined-builtin
    ) -> Set[str]:
        """get a config value parsed as a set of string values."""
        val = self.get(section, key, fallback="").strip()
        if not val and fallback:
            return set(fallback)
        return set(x for x in val.replace(",", " ").split())


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
            log.warning("Blocklist file not found:  %s", self._blocklist_file)
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
                "Could not update the blocklist file:  %s",
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
                "Could not update the blocklist file:  %s",
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
            "Loaded User Blocklist with %s entires.",
            len(self.items),
        )

    def _handle_legacy_file(self, new_file: pathlib.Path) -> None:
        """
        In case the original, ambiguous block list file exists, lets rename it.
        """
        old_file = pathlib.Path(DEPRECATED_USER_BLACKLIST)
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
        log.debug("Loaded a Song Blocklist with %s entries.", len(self.items))

    def is_blocked(self, song_subject: str) -> bool:
        """
        Checks if the given `song_subject` contains any entry in the song block list.

        :param: song_subject:  Any input the bot player commands will take or pass to ytdl extraction.
        """
        return any(x in song_subject for x in self.items)
