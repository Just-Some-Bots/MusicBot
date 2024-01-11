import subprocess

try:
    VERSION = (
        subprocess.check_output(["git", "describe", "--tags", "--always"])
        .decode("ascii")
        .strip()
    )
except Exception:
    VERSION = "version_unknown"

DISCORD_MSG_CHAR_LIMIT = 2000

EMOJI_CHECK_MARK_BUTTON = "\u2705"
EMOJI_CROSS_MARK_BUTTON = "\u274E"
EMOJI_IDLE_ICON = "\u23FE"  # same as \N{POWER SLEEP SYMBOL}
EMOJI_PLAY_ICON = "\u25B6"  # add \uFE0F to make button
EMOJI_PAUSE_ICON = "\u23F8\uFE0F"  # add \uFE0F to make button
