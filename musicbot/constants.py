import os.path
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
