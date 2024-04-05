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
DEFAULT_AUTOPLAYLIST_FILE: str = "config/autoplaylist.txt"
BUNDLED_AUTOPLAYLIST_FILE: str = "config/_autoplaylist.txt"
DEFAULT_AUDIO_CACHE_PATH: str = "audio_cache"
DEFAULT_DATA_PATH: str = "data"
DEFAULT_DATA_NAME_SERVERS: str = "server_names.txt"
DEFAULT_DATA_NAME_QUEUE: str = "queue.json"
DEFAULT_DATA_NAME_CUR_SONG: str = "current.txt"
DEFAULT_DATA_NAME_OPTIONS: str = "options.json"

EXAMPLE_OPTIONS_FILE: str = "config/example_options.ini"
EXAMPLE_PERMS_FILE: str = "config/example_permissions.ini"
EXAMPLE_COMMAND_ALIAS_FILE: str = "config/example_aliases.json"


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
# Max time in seconds that ping should wait for response.
DEFAULT_PING_TIMEOUT: int = 2
# Time in seconds to wait between pings.
DEFAULT_PING_SLEEP: float = 0.8


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
EMOJI_IDLE_ICON: str = "\U0001f634"  # same as \N{SLEEPING FACE}
EMOJI_PLAY_ICON: str = "\u25B6"  # add \uFE0F to make button
EMOJI_PAUSE_ICON: str = "\u23F8\uFE0F"  # add \uFE0F to make button
EMOJI_LAST_ICON: str = "\u23ED\uFE0F"  # next track button
EMOJI_FIRST_ICON: str = "\u23EE\uFE0F"  # last track button
EMOJI_NEXT_ICON: str = "\u23E9"  # fast-forward button
EMOJI_PREV_ICON: str = "\u23EA"  # rewind button
