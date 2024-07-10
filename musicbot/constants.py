import subprocess

VERSION: str = ""
try:
    VERSION = (
        subprocess.check_output(["git", "describe", "--tags", "--always", "--dirty"])
        .decode("ascii")
        .strip()
    )
except (subprocess.SubprocessError, OSError, ValueError) as e:
    print(f"Failed setting version constant, reason:  {str(e)}")
    VERSION = "version_unknown"

# constant string exempt from i18n
DEFAULT_FOOTER_TEXT: str = f"Just-Some-Bots/MusicBot ({VERSION})"
DEFAULT_BOT_NAME: str = "MusicBot"
DEFAULT_BOT_ICON: str = "https://i.imgur.com/gFHBoZA.png"
DEFAULT_OWNER_GROUP_NAME: str = "Owner (auto)"
DEFAULT_PERMS_GROUP_NAME: str = "Default"


# File path constants
DEFAULT_OPTIONS_FILE: str = "config/options.ini"
DEFAULT_PERMS_FILE: str = "config/permissions.ini"
DEFAULT_I18N_FILE: str = "config/i18n/en.json"
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
DATA_GUILD_FILE_QUEUE: str = "queue.json"
DATA_GUILD_FILE_CUR_SONG: str = "current.txt"
DATA_GUILD_FILE_OPTIONS: str = "options.json"

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

# Discord and other API constants
DISCORD_MSG_CHAR_LIMIT: int = 2000


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
