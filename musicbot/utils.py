import aiohttp
import datetime
import glob
import inspect
import logging
import os
import pathlib
import re
import sys
import unicodedata
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Set,
    Tuple,
    Union,
    Optional,
)

# protected imports to keep run.py from breaking on missing packages.
try:
    import colorlog

    COLORLOG_LOADED = True
except ImportError:
    COLORLOG_LOADED = False

from .constants import (
    DEFAULT_DISCORD_LOG_FILE,
    DEFAULT_LOGS_KEPT,
    DEFAULT_LOGS_ROTATE_FORMAT,
    DEFAULT_MUSICBOT_LOG_FILE,
    DISCORD_MSG_CHAR_LIMIT,
)
from .exceptions import PermissionsError

if TYPE_CHECKING:
    from discord import Member, StageChannel, VoiceChannel

    from .bot import MusicBot

log = logging.getLogger(__name__)


def _add_logger_level(levelname: str, level: int, *, func_name: str = "") -> None:
    """
    Add a logging function and level to the musicbot logger.

    :param: levelname:
        The reference name of the level, e.g. DEBUG, WARNING, etc
    :param: level:
        Numeric logging level
    :param: func_name:
        The name of the logger function to log to a level, e.g. "info" for log.info(...)
    """
    _func_prototype = (
        "def {logger_func_name}(self, message, *args, **kwargs):\n"
        "    if self.isEnabledFor({levelname}):\n"
        "        self._log({levelname}, message, args, **kwargs)"
    )

    func_name = func_name or levelname.lower()

    setattr(logging, levelname, level)
    logging.addLevelName(level, levelname)

    # TODO: this is cool and all, but there is likely a better way to do this.
    # we should probably be extending logging.getLoggerClass() instead
    exec(  # pylint: disable=exec-used
        _func_prototype.format(logger_func_name=func_name, levelname=levelname),
        logging.__dict__,
        locals(),
    )
    setattr(logging.Logger, func_name, eval(func_name))  # pylint: disable=eval-used


def setup_loggers() -> None:
    """set up all logging handlers for musicbot and discord.py"""
    if len(logging.getLogger("musicbot").handlers) > 1:
        log.debug("Skipping logger setup, already set up")
        return

    # Do some pre-flight checking...
    log_file = pathlib.Path(DEFAULT_MUSICBOT_LOG_FILE)
    if not log_file.parent.is_dir():
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise RuntimeError(
                f"Cannot create log file directory due to an error:\n{str(e)}"
            ) from e

    if not log_file.is_file():
        try:
            log_file.touch(exist_ok=True)
        except Exception as e:
            raise RuntimeError(
                f"Cannot create log file due to an error:\n{str(e)}"
            ) from e

    # logging checks done, we should be able to take off.
    _add_logger_level("EVERYTHING", 1)
    _add_logger_level("NOISY", 4, func_name="noise")
    _add_logger_level("FFMPEG", 5)
    _add_logger_level("VOICEDEBUG", 6)

    logger = logging.getLogger("musicbot")
    # initially set logging to everything, it will be changed when config is loaded.
    logger.setLevel(logging.EVERYTHING)  # type: ignore[attr-defined]

    # Setup logging to file for musicbot.
    try:
        # We could use a RotatingFileHandler or TimedRotatingFileHandler
        # however, these require more options than we currently consider
        # such as file size or fixed rotation time.
        # For now, out local implementation should be fine...
        fhandler = logging.FileHandler(
            filename=log_file,
            encoding="utf-8",
            mode="w",
            delay=True,
        )
    except Exception as e:
        raise RuntimeError(
            f"Could not create or use the log file due to an error:\n{str(e)}"
        ) from e

    fhandler.setFormatter(
        logging.Formatter(
            "[{asctime}] {levelname} - {name} | "
            "In {filename}::{threadName}({thread}), line {lineno} in {funcName}: {message}",
            style="{",
        )
    )
    logger.addHandler(fhandler)

    # Setup logging to console for musicbot, handle missing colorlog gracefully.
    shandler = logging.StreamHandler(stream=sys.stdout)
    if COLORLOG_LOADED:
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

    # colorlog import must have failed.
    else:
        sformatter = logging.Formatter(  # type: ignore[assignment]
            "[{name}] {levelname}: {message}",
            style="{",
        )

    shandler.setFormatter(sformatter)  # type: ignore[arg-type]
    logger.addHandler(shandler)

    # Setup logging for discord module.
    dlogger = logging.getLogger("discord")
    dhandler = logging.FileHandler(
        filename=DEFAULT_DISCORD_LOG_FILE,
        encoding="utf-8",
        mode="w",
        delay=True,
    )
    dhandler.setFormatter(
        logging.Formatter("[{asctime}] {levelname} - {name}: {message}", style="{")
    )
    dlogger.addHandler(dhandler)
    # initially set discord logging to debug, it will be changed when config is loaded.
    dlogger.setLevel(logging.DEBUG)


def muffle_discord_console_log() -> None:
    """
    Changes discord console logger output to periods only.
    Kind of like a progress indicator.
    """
    dlog = logging.getLogger("discord")
    dlh = logging.StreamHandler(stream=sys.stdout)
    dlh.terminator = ""
    try:
        dlh.setFormatter(logging.Formatter("."))
    except ValueError:
        dlh.setFormatter(logging.Formatter(".", validate=False))
    dlog.addHandler(dlh)


def mute_discord_console_log() -> None:
    """
    Removes the discord console logger output handler added by muffle_discord_console_log()
    """
    dlogger = logging.getLogger("discord")
    for h in dlogger.handlers:
        if getattr(h, "terminator", None) == "":
            dlogger.removeHandler(h)
            print()


def set_logging_level(level: int, override: bool = False) -> None:
    """
    Sets the logging level for musicbot and discord.py loggers.
    If `override` is set True, the log level will be set and future calls
    to this function must also use `override` to set a new level.
    This allows log-level to be set by CLI arguments, overriding the
    setting used in configuration file.
    """
    if hasattr(logging, "mb_level_override") and not override:
        log.debug(
            "Log level was previously set via override to: %s",
            getattr(logging, "mb_level_override"),
        )
        return

    if override:
        setattr(logging, "mb_level_override", logging.getLevelName(level))

    set_lvl_name = logging.getLevelName(level)
    log.info("Changing log level to:  %s", set_lvl_name)

    logger = logging.getLogger("musicbot")
    logger.setLevel(level)

    dlogger = logging.getLogger("discord")
    if level <= logging.DEBUG:
        dlogger.setLevel(logging.DEBUG)
    else:
        dlogger.setLevel(level)


# TODO: perhaps add config file option for max logs kept.
def set_logging_max_kept_logs(number: int) -> None:
    """Inform the logger how many logs it should keep."""
    setattr(logging, "mb_max_logs_kept", number)


# TODO: perhaps add a config file option for date format.
def set_logging_rotate_date_format(sftime: str) -> None:
    """Inform the logger how it should format rotated file date strings."""
    setattr(logging, "mb_rot_date_fmt", sftime)


def shutdown_loggers() -> None:
    """Removes all musicbot and discord log handlers"""
    # This is the last log line of the logger session.
    log.info("MusicBot loggers have been called to shutdown.")

    logger = logging.getLogger("musicbot")
    for handler in logger.handlers:
        handler.flush()
        handler.close()
    logger.handlers.clear()

    dlogger = logging.getLogger("discord")
    for handler in dlogger.handlers:
        handler.flush()
        handler.close()
    dlogger.handlers.clear()


def rotate_log_files(max_kept: int = -1, date_fmt: str = "") -> None:
    """
    Handles moving and pruning log files.
    By default the primary log file is always kept, and never rotated.
    If `max_kept` is set to 0, no rotation is done.
    If `max_kept` is set 1 or greater, up to this number of logs will be kept.
    This should only be used before setup_loggers() or after shutdown_loggers()

    Note: this implementation uses file glob to select then sort files based
    on their modification time.
    The glob uses the following pattern: `{stem}*.{suffix}`
    Where `stem` and `suffix` are take from the configured log file name.

    :param: max_kept:  number of old logs to keep.
    :param: date_fmt:  format compatible with datetime.strftime() for rotated filename.
    """
    # Use the input arguments or fall back to settings or defaults.
    if max_kept <= -1:
        max_kept = getattr(logging, "mb_max_logs_kept", DEFAULT_LOGS_KEPT)
        if max_kept <= -1:
            max_kept = DEFAULT_LOGS_KEPT

    if date_fmt == "":
        date_fmt = getattr(logging, "mb_rot_date_fmt", DEFAULT_LOGS_ROTATE_FORMAT)
        if date_fmt == "":
            date_fmt = DEFAULT_LOGS_ROTATE_FORMAT

    # Rotation can be disabled by setting 0.
    if not max_kept:
        return

    # Format a date that will be used for files rotated now.
    before = datetime.datetime.now().strftime(date_fmt)

    # Rotate musicbot logs
    logfile = pathlib.Path(DEFAULT_MUSICBOT_LOG_FILE)
    logpath = logfile.parent
    if logfile.is_file():
        new_name = logpath.joinpath(f"{logfile.stem}{before}{logfile.suffix}")
        # Cannot use logging here, but some notice to console is OK.
        print(f"Moving the log file from this run to:  {new_name}")
        logfile.rename(new_name)

    # Clean up old, out-of-limits, musicbot log files
    logstem = glob.escape(logfile.stem)
    logglob = sorted(
        logpath.glob(f"{logstem}*.log"),
        key=os.path.getmtime,
        reverse=True,
    )
    if len(logglob) > max_kept:
        for path in logglob[max_kept:]:
            if path.is_file():
                path.unlink()

    # Rotate discord.py logs
    dlogfile = pathlib.Path(DEFAULT_DISCORD_LOG_FILE)
    dlogpath = dlogfile.parent
    if dlogfile.is_file():
        new_name = dlogfile.parent.joinpath(f"{dlogfile.stem}{before}{dlogfile.suffix}")
        dlogfile.rename(new_name)

    # Clean up old, out-of-limits, discord log files
    logstem = glob.escape(dlogfile.stem)
    logglob = sorted(
        dlogpath.glob(f"{logstem}*.log"), key=os.path.getmtime, reverse=True
    )
    if len(logglob) > max_kept:
        for path in logglob[max_kept:]:
            if path.is_file():
                path.unlink()


def load_file(filename, skip_commented_lines=True, comment_char="#"):
    try:
        with open(filename, encoding="utf8") as f:
            results = []
            for line in f:
                line = line.strip()

                if line and not (
                    skip_commented_lines and line.startswith(comment_char)
                ):
                    results.append(line)

            return results

    except IOError as e:
        print("Error loading", filename, e)
        return []


def write_file(filename, contents):
    with open(filename, "w", encoding="utf8") as f:
        for item in contents:
            f.write(str(item))
            f.write("\n")


def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def paginate(content, *, length=DISCORD_MSG_CHAR_LIMIT, reserve=0):
    """
    Split up a large string or list of strings into chunks for sending to discord.
    """
    if isinstance(content, str):
        contentlist = content.split("\n")
    elif isinstance(content, list):
        contentlist = content
    else:
        raise ValueError("Content must be str or list, not %s" % type(content))

    chunks = []
    currentchunk = ""

    for line in contentlist:
        if len(currentchunk) + len(line) < length - reserve:
            currentchunk += line + "\n"
        else:
            chunks.append(currentchunk)
            currentchunk = ""

    if currentchunk:
        chunks.append(currentchunk)

    return chunks


async def get_header(
    session: aiohttp.ClientSession,
    url: str,
    headerfield: Optional[str] = None,
    *,
    timeout: int = 5,
    allow_redirects: bool = True,
    req_headers: Dict[str, Any] = {},
):
    req_timeout = aiohttp.ClientTimeout(total=timeout)
    async with session.head(
        url, timeout=req_timeout, allow_redirects=allow_redirects, headers=req_headers
    ) as response:
        if headerfield:
            return response.headers.get(headerfield)
        else:
            return response.headers


def fixg(x, dp=2):
    return ("{:.%sf}" % dp).format(x).rstrip("0").rstrip(".")


def ftimedelta(td):
    p1, p2 = str(td).rsplit(":", 1)
    return ":".join([p1, "{:02d}".format(int(float(p2)))])


def safe_print(content, *, end="\n", flush=True):
    sys.stdout.buffer.write((content + end).encode("utf-8", "replace"))
    if flush:
        sys.stdout.flush()


def objdiff(obj1, obj2, *, access_attr=None, depth=0):
    changes = {}

    if access_attr is None:
        attrdir = lambda x: x  # noqa: E731

    elif access_attr == "auto":
        if hasattr(obj1, "__slots__") and hasattr(obj2, "__slots__"):
            attrdir = lambda x: getattr(x, "__slots__")  # noqa: E731

        elif hasattr(obj1, "__dict__") and hasattr(obj2, "__dict__"):
            attrdir = lambda x: getattr(x, "__dict__")  # noqa: E731

        else:
            attrdir = dir

    elif isinstance(access_attr, str):
        attrdir = lambda x: list(getattr(x, access_attr))  # noqa: E731

    else:
        attrdir = dir

    for item in set(attrdir(obj1) + attrdir(obj2)):
        try:
            iobj1 = getattr(obj1, item, AttributeError("No such attr " + item))
            iobj2 = getattr(obj2, item, AttributeError("No such attr " + item))

            if depth:
                idiff = objdiff(iobj1, iobj2, access_attr="auto", depth=depth - 1)
                if idiff:
                    changes[item] = idiff

            elif iobj1 is not iobj2:
                changes[item] = (iobj1, iobj2)

            else:
                pass

        except Exception:
            continue

    return changes


def color_supported():
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


def _func_():
    # emulate __func__ from C++
    return inspect.currentframe().f_back.f_code.co_name


def _get_variable(name):
    stack = inspect.stack()
    try:
        for frames in stack:
            try:
                frame = frames[0]
                current_locals = frame.f_locals
                if name in current_locals:
                    return current_locals[name]
            finally:
                del frame
    finally:
        del stack


def is_empty_voice_channel(
    voice_channel: Union["VoiceChannel", "StageChannel"],
    *,
    exclude_me: bool = True,
    exclude_deaf: bool = True,
    include_bots: List[int] = [],
) -> bool:
    """
    Check if the given `voice_channel` is figuratively or literally empty.

    :param: `exclude_me`: Exclude our bot instance, the default.
    :param: `exclude_deaf`: Excludes members who are self-deaf or server-deaf.
    :param: `include_bots`: A list of bot IDs to include if they are present.
    """

    def _check(member):
        if exclude_me and member == voice_channel.guild.me:
            return False

        if (
            member.voice
            and exclude_deaf
            and any([member.voice.deaf, member.voice.self_deaf])
        ):
            return False

        if member.bot and member.id not in include_bots:
            return False

        return True

    return not sum(1 for m in voice_channel.members if _check(m))


def format_song_duration(ftd):
    duration_array = ftd.split(":")
    return (
        ftd
        if int(duration_array[0]) > 0
        else "{0}:{1}".format(duration_array[1], duration_array[2])
    )


def format_size_from_bytes(size: int):
    suffix = {0: "", 1: "Ki", 2: "Mi", 3: "Gi", 4: "Ti"}
    power = 1024
    i = 0
    while size > power:
        size /= power
        i += 1
    return f"{size:.3f} {suffix[i]}B"


def format_size_to_bytes(size_str: str, strict_si=False) -> int:
    """Convert human-friendly *bytes notation into integer.
    Note: this function is not intended to convert Bits notation.

    Option `strict_si` will use 1000 rather than 1024 for SI suffixes.
    """
    si_units = 1024
    if strict_si:
        si_units = 1000
    suffix_list = {
        "kilobyte": si_units,
        "megabyte": si_units**2,
        "gigabyte": si_units**3,
        "terabyte": si_units**4,
        "petabyte": si_units**5,
        "exabyte": si_units**6,
        "zetabyte": si_units**7,
        "yottabyte": si_units**8,
        "kb": si_units,
        "mb": si_units**2,
        "gb": si_units**3,
        "tb": si_units**4,
        "pb": si_units**5,
        "eb": si_units**6,
        "zb": si_units**7,
        "yb": si_units**8,
        "kibibyte": 1024,
        "mebibyte": 1024**2,
        "gibibyte": 1024**3,
        "tebibyte": 1024**4,
        "pebibyte": 1024**5,
        "exbibyte": 1024**6,
        "zebibyte": 1024**7,
        "yobibyte": 1024**8,
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
        "tib": 1024**4,
        "pib": 1024**5,
        "eib": 1024**6,
        "zib": 1024**7,
        "yib": 1024**8,
    }
    size_str = size_str.lower().strip().strip("s")
    for suffix in suffix_list:
        if size_str.endswith(suffix):
            return int(float(size_str[0 : -len(suffix)]) * suffix_list[suffix])
    else:
        if size_str.endswith("b"):
            size_str = size_str[0:-1]
        elif size_str.endswith("byte"):
            size_str = size_str[0:-4]
    return int(size_str)


def format_time_to_seconds(time_str: Union[str, int]) -> int:
    """Convert a phrase containing time duration(s) to seconds as int
    This function allows for intresting/sloppy time notations like:
    - 1yearand2seconds  = 31556954
    - 8s 1d             = 86408
    - .5 hours          = 1800
    - 99 + 1            = 100
    - 3600              = 3600
    Only partial seconds are not supported, thus ".5s + 1.5s" will be 1 not 2.

    Param `time_str` is assumed to contain a time duration as str or int.
    Returns 0 if no time value is recognised, rather than raise a ValueError.
    """
    if isinstance(time_str, int):
        return time_str

    # TODO: find a good way to make this i18n friendly.
    time_lex = re.compile(r"(\d*\.?\d+)\s*(y|d|h|m|s)?", re.I)
    unit_seconds = {
        "y": 31556952,
        "d": 86400,
        "h": 3600,
        "m": 60,
        "s": 1,
    }
    total_sec = 0
    for value, unit in time_lex.findall(time_str):
        if not unit:
            unit = "s"
        else:
            unit = unit[0].lower().strip()
        total_sec += int(float(value) * unit_seconds[unit])
    return total_sec
