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


# Discord and other API constants
DISCORD_MSG_CHAR_LIMIT: int = 2000


EMOJI_CHECK_MARK_BUTTON: str = "\u2705"
EMOJI_CROSS_MARK_BUTTON: str = "\u274E"
EMOJI_IDLE_ICON: str = "\U0001f634"  # same as \N{SLEEPING FACE}
EMOJI_PLAY_ICON: str = "\u25B6"  # add \uFE0F to make button
EMOJI_PAUSE_ICON: str = "\u23F8\uFE0F"  # add \uFE0F to make button
