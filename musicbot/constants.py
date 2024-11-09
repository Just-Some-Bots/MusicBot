import subprocess
from typing import List

# VERSION is determined by asking the `git` executable about the current repository.
# This fails if not cloned, or if git is not available for some reason.
# VERSION should never be empty though.
# Note this code is duplicated in update.py for stand-alone use.
VERSION: str = ""
try:
    # Get the last release tag, number of commits since, and g{commit_id} as string.
    _VERSION_P1 = (
        subprocess.check_output(["git", "describe", "--tags", "--always"])
        .decode("ascii")
        .strip()
    )
    # Check if any tracked files are modified for -modded version flag.
    _VERSION_P2 = (
        subprocess.check_output(
            ["git", "-c", "core.fileMode=false", "status", "-suno", "--porcelain"]
        )
        .decode("ascii")
        .strip()
    )
    if _VERSION_P2:
        _VERSION_P2 = "-modded"
    else:
        _VERSION_P2 = ""

    VERSION = f"{_VERSION_P1}{_VERSION_P2}"

except (subprocess.SubprocessError, OSError, ValueError) as e:
    print(f"Failed setting version constant, reason:  {str(e)}")
    VERSION = "version_unknown"

# constant string exempt from i18n
DEFAULT_FOOTER_TEXT: str = f"Just-Some-Bots/MusicBot ({VERSION})"
DEFAULT_BOT_NAME: str = "MusicBot"
DEFAULT_BOT_ICON: str = "https://i.imgur.com/gFHBoZA.png"
DEFAULT_OWNER_GROUP_NAME: str = "Owner (auto)"
DEFAULT_PERMS_GROUP_NAME: str = "Default"
# This UA string is used by MusicBot only for the aiohttp session.
# Meaning discord API and spotify API communications.
# NOT used by ytdlp, they have a dynamic UA selection feature.
MUSICBOT_USER_AGENT_AIOHTTP: str = f"MusicBot/{VERSION}"
MUSICBOT_GIT_URL: str = "https://github.com/Just-Some-Bots/MusicBot/"
# The Environment variable MusicBot checks for if no Token is given in the config file.
MUSICBOT_TOKEN_ENV_VAR: str = "MUSICBOT_TOKEN"

# File path constants
DEFAULT_OPTIONS_FILE: str = "config/options.ini"
DEFAULT_PERMS_FILE: str = "config/permissions.ini"
# TODO: Remove this file constant in favor of gettext messages.
DEFAULT_I18N_FILE: str = "config/i18n/en.json"
DEFAULT_I18N_DIR: str = "i18n/"
DEFAULT_I18N_LANG: str = "en_US"
DEFAULT_COMMAND_ALIAS_FILE: str = "config/aliases.json"
DEFAULT_USER_BLOCKLIST_FILE: str = "config/blocklist_users.txt"
DEFAULT_SONG_BLOCKLIST_FILE: str = "config/blocklist_songs.txt"
DEPRECATED_USER_BLACKLIST: str = "config/blacklist.txt"
OLD_DEFAULT_AUTOPLAYLIST_FILE: str = "config/autoplaylist.txt"
OLD_BUNDLED_AUTOPLAYLIST_FILE: str = "config/_autoplaylist.txt"
DEFAULT_PLAYLIST_DIR: str = "config/playlists/"
DEFAULT_MEDIA_FILE_DIR: str = "media/"
DEFAULT_AUDIO_CACHE_DIR: str = "audio_cache/"
DEFAULT_DATA_DIR: str = "data/"

# File names within the DEFAULT_DATA_DIR or guild folders.
DATA_FILE_SERVERS: str = "server_names.txt"
DATA_FILE_CACHEMAP: str = "playlist_cachemap.json"
DATA_FILE_COOKIES: str = "cookies.txt"  # No support for this, go read yt-dlp docs.
DATA_FILE_YTDLP_OAUTH2: str = "oauth2.token"
DATA_GUILD_FILE_QUEUE: str = "queue.json"
DATA_GUILD_FILE_CUR_SONG: str = "current.txt"
DATA_GUILD_FILE_OPTIONS: str = "options.json"

I18N_DISCORD_TEXT_DOMAIN: str = "musicbot_messages"
I18N_LOGFILE_TEXT_DOMAIN: str = "musicbot_logs"

# Example config files.
EXAMPLE_OPTIONS_FILE: str = "config/example_options.ini"
EXAMPLE_PERMS_FILE: str = "config/example_permissions.ini"
EXAMPLE_COMMAND_ALIAS_FILE: str = "config/example_aliases.json"

# Playlist related settings.
APL_FILE_DEFAULT: str = "default.txt"
APL_FILE_HISTORY: str = "history.txt"
APL_FILE_APLCOPY: str = "autoplaylist.txt"

# Logging related constants
DEFAULT_MUSICBOT_LOG_FILE: str = "logs/musicbot.log"
DEFAULT_DISCORD_LOG_FILE: str = "logs/discord.log"
# Default is 0, for no rotation at all.
DEFAULT_LOGS_KEPT: int = 0
MAXIMUM_LOGS_LIMIT: int = 100
# This value is run through strftime() and then sandwiched between
DEFAULT_LOGS_ROTATE_FORMAT: str = ".ended-%Y-%j-%H%m%S"
# Default log level can be one of:
# CRITICAL, ERROR, WARNING, INFO, DEBUG,
# VOICEDEBUG, FFMPEG, NOISY, or EVERYTHING
DEFAULT_LOG_LEVEL: str = "INFO"

# Default target FQDN or IP to ping with network tester.
DEFAULT_PING_TARGET: str = "discord.com"
# Default file location URI used by fallback HTTP network testing.
# This URI must be available via standard HTTP on the above domain/IP target.
DEFAULT_PING_HTTP_URI: str = "/robots.txt"
# Max time in seconds that ping should wait for response.
DEFAULT_PING_TIMEOUT: int = 5
# Time in seconds to wait between pings.
DEFAULT_PING_SLEEP: float = 2
# Ping time settings for HTTP fallback.
FALLBACK_PING_TIMEOUT: int = 15
FALLBACK_PING_SLEEP: float = 4

# Minimum number of seconds to wait for a VoiceClient to connect.
VOICE_CLIENT_RECONNECT_TIMEOUT: int = 5
# Maximum number of retry attempts to make for VoiceClient connection.
# Each retry increases the timeout by multiplying attempts by the above timeout.
VOICE_CLIENT_MAX_RETRY_CONNECT: int = 5

# Maximum number of threads MusicBot will use for downloading and extracting info.
DEFAULT_MAX_INFO_DL_THREADS: int = 2
# Maximum number of seconds to wait for HEAD request on media files.
DEFAULT_MAX_INFO_REQUEST_TIMEOUT: int = 10

# Time to wait before starting pre-download when a new song is playing.
DEFAULT_PRE_DOWNLOAD_DELAY: float = 4.0

# Time in seconds to wait before oauth2 authorization fails.
# This provides time to authorize as well as prevent process hang at shutdown.
DEFAULT_YTDLP_OAUTH2_TTL: float = 180.0

# Default / fallback scopes used for OAuth2 ytdlp plugin.
DEFAULT_YTDLP_OAUTH2_SCOPES: str = (
    "http://gdata.youtube.com https://www.googleapis.com/auth/youtube"
)
# Info Extractors to exclude from OAuth2 patching, when OAuth2 is enabled.
YTDLP_OAUTH2_EXCLUDED_IES: List[str] = [
    "YoutubeBaseInfoExtractor",
    "YoutubeTabBaseInfoExtractor",
]
# Yt-dlp client creators that are not compatible with OAuth2 plugin.
YTDLP_OAUTH2_UNSUPPORTED_CLIENTS: List[str] = [
    "web_creator",
    "android_creator",
    "ios_creator",
]
# Additional Yt-dlp clients to add to the OAuth2 client list.
YTDLP_OAUTH2_CLIENTS: List[str] = ["mweb"]

# Discord and other API constants
DISCORD_MSG_CHAR_LIMIT: int = 2000

# Embed specifics
MUSICBOT_EMBED_COLOR_NORMAL: str = "#7289DA"
MUSICBOT_EMBED_COLOR_ERROR: str = "#CC0000"


EMOJI_CHECK_MARK_BUTTON: str = "\u2705"
EMOJI_CROSS_MARK_BUTTON: str = "\u274E"
EMOJI_STOP_SIGN: str = "\U0001F6D1"
EMOJI_IDLE_ICON: str = "\U0001f634"  # same as \N{SLEEPING FACE}
EMOJI_PLAY_ICON: str = "\u25B6"  # add \uFE0F to make button
EMOJI_PAUSE_ICON: str = "\u23F8\uFE0F"  # add \uFE0F to make button
EMOJI_LAST_ICON: str = "\u23ED\uFE0F"  # next track button
EMOJI_FIRST_ICON: str = "\u23EE\uFE0F"  # last track button
EMOJI_NEXT_ICON: str = "\u23E9"  # fast-forward button
EMOJI_PREV_ICON: str = "\u23EA"  # rewind button
EMOJI_RESTART_SOFT: str = "\u21A9\uFE0F"  # Right arrow curving left
EMOJI_RESTART_FULL: str = "\U0001F504"  # counterclockwise arrows
EMOJI_UPDATE_PIP: str = "\U0001F4E6"  # package / box
EMOJI_UPDATE_GIT: str = "\U0001F5C3\uFE0F"  # card box
EMOJI_UPDATE_ALL: str = "\U0001F310"  # globe with meridians
