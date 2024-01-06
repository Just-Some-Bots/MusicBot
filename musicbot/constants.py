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
