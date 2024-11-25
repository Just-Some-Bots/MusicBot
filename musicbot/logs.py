import datetime
import glob
import logging
import os
import sys
from typing import TYPE_CHECKING, Any

from . import write_path

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
)
from .i18n import I18n

# make mypy aware of the type for the dynamic base class.
if TYPE_CHECKING:
    BaseLoggerClass = logging.Logger
else:
    BaseLoggerClass = logging.getLoggerClass()

# Log levels supported by our logger.
CRITICAL = 50
ERROR = 40
WARNING = 30
INFO = 20
DEBUG = 10
# Custom Levels
VOICEDEBUG = 6
FFMPEG = 5
NOISY = 4
EVERYTHING = 1
# End Custom Levels
NOTSET = 0

log_i18n = I18n(auto_install=False).get_log_translations()


class MusicBotLogger(BaseLoggerClass):
    def __init__(self, name: str, level: int = NOTSET) -> None:
        self.i18n = log_i18n
        super().__init__(name, level)

    # TODO: at some point we'll need to handle plurals.
    # maybe add special kwargs "plural" and "n" to select that.
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log debug level message, translating the message first."""
        if self.isEnabledFor(DEBUG):
            msg = self.i18n.gettext(msg)
            kwargs.setdefault("stacklevel", 2)
            super().debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log info level messge, translating the message first."""
        if self.isEnabledFor(INFO):
            msg = self.i18n.gettext(msg)
            kwargs.setdefault("stacklevel", 2)
            super().info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log warning level message, with translation first."""
        if self.isEnabledFor(WARNING):
            msg = self.i18n.gettext(msg)
            kwargs.setdefault("stacklevel", 2)
            super().warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log error level message, with translation first."""
        if self.isEnabledFor(ERROR):
            msg = self.i18n.gettext(msg)
            kwargs.setdefault("stacklevel", 2)
            super().error(msg, *args, **kwargs)

    def exception(  # type: ignore[override]
        self, msg: str, *args: Any, exc_info: bool = True, **kwargs: Any
    ) -> None:
        """
        Log error with exception info.
        Exception text may not be translated.
        """
        kwargs.setdefault("stacklevel", 3)
        self.error(msg, *args, exc_info=exc_info, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log critical level message, with translation first."""
        if self.isEnabledFor(CRITICAL):
            msg = self.i18n.gettext(msg)
            kwargs.setdefault("stacklevel", 2)
            super().critical(msg, *args, **kwargs)

    # Custom log levels defined here.
    def voicedebug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log voicedebug level message, with translation first."""
        if self.isEnabledFor(VOICEDEBUG):
            msg = self.i18n.gettext(msg)
            self._log(VOICEDEBUG, msg, args, **kwargs)

    def ffmpeg(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log ffmpeg level message, with translation first."""
        if self.isEnabledFor(FFMPEG):
            msg = self.i18n.gettext(msg)
            self._log(FFMPEG, msg, args, **kwargs)

    def noise(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log noisy level message, with translation first."""
        if self.isEnabledFor(NOISY):
            msg = self.i18n.gettext(msg)
            self._log(NOISY, msg, args, **kwargs)

    def everything(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an everything level message, with translation first."""
        if self.isEnabledFor(EVERYTHING):
            msg = self.i18n.gettext(msg)
            self._log(EVERYTHING, msg, args, **kwargs)


def setup_loggers() -> None:
    """set up all logging handlers for musicbot and discord.py"""
    if len(logging.getLogger("musicbot").handlers) > 1:
        log = logging.getLogger("musicbot")
        log.debug("Skipping logger setup, already set up")
        return

    # Do some pre-flight checking...
    log_file = write_path(DEFAULT_MUSICBOT_LOG_FILE)
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
    install_logger()

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
                # Organized by level number in descending order.
                "CRITICAL": "{log_color}[{levelname}:{module}] {message}",
                "ERROR": "{log_color}[{levelname}:{module}] {message}",
                "WARNING": "{log_color}{levelname}: {message}",
                "INFO": "{log_color}{message}",
                "DEBUG": "{log_color}[{levelname}:{module}] {message}",
                "VOICEDEBUG": "{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}",
                "FFMPEG": "{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}",
                "NOISY": "{log_color}[{levelname}:{module}] {message}",
                "EVERYTHING": "{log_color}[{levelname}:{module}] {message}",
            },
            log_colors={
                "CRITICAL": "bold_red",
                "ERROR": "red",
                "WARNING": "yellow",
                "INFO": "white",
                "DEBUG": "cyan",
                "VOICEDEBUG": "purple",
                "FFMPEG": "bold_purple",
                "NOISY": "bold_white",
                "EVERYTHING": "bold_cyan",
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

    # Set a flag to indicate our logs are open.
    setattr(logging, "_mb_logs_open", True)


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
    # for console output carriage return post muffled log string.
    print()


def set_logging_level(level: int, override: bool = False) -> None:
    """
    Sets the logging level for musicbot and discord.py loggers.
    If `override` is set True, the log level will be set and future calls
    to this function must also use `override` to set a new level.
    This allows log-level to be set by CLI arguments, overriding the
    setting used in configuration file.
    """
    log = logging.getLogger("musicbot.logs")
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


def set_logging_max_kept_logs(number: int) -> None:
    """Inform the logger how many logs it should keep."""
    setattr(logging, "mb_max_logs_kept", number)


def set_logging_rotate_date_format(sftime: str) -> None:
    """Inform the logger how it should format rotated file date strings."""
    setattr(logging, "mb_rot_date_fmt", sftime)


def shutdown_loggers() -> None:
    """Removes all musicbot and discord log handlers"""
    if not hasattr(logging, "_mb_logs_open"):
        return

    # This is the last log line of the logger session.
    log = logging.getLogger("musicbot.logs")
    log.info("MusicBot loggers have been called to shut down.")

    setattr(logging, "_mb_logs_open", False)

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
    if hasattr(logging, "_mb_logs_rotated"):
        print("Logs already rotated.")
        return

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
        print("No logs rotated.")
        return

    # Format a date that will be used for files rotated now.
    before = datetime.datetime.now().strftime(date_fmt)

    # Rotate musicbot logs
    logfile = write_path(DEFAULT_MUSICBOT_LOG_FILE)
    logpath = logfile.parent
    if logfile.is_file():
        new_name = logpath.joinpath(f"{logfile.stem}{before}{logfile.suffix}")
        # Cannot use logging here, but some notice to console is OK.
        print(
            log_i18n.gettext("Moving the log file from this run to:  %(logpath)s")
            % {"logpath": new_name}
        )
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
    dlogfile = write_path(DEFAULT_DISCORD_LOG_FILE)
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

    setattr(logging, "_mb_logs_rotated", True)


def install_logger() -> None:
    """Install the MusicBotLogger class for logging with translations."""
    base = logging.getLoggerClass()
    if not isinstance(base, MusicBotLogger):
        levels = {
            "VOICEDEBUG": VOICEDEBUG,
            "FFMPEG": FFMPEG,
            "NOISY": NOISY,
            "EVERYTHING": EVERYTHING,
        }
        for name, lvl in levels.items():
            setattr(logging, name, lvl)
            logging.addLevelName(lvl, name)
        logging.setLoggerClass(MusicBotLogger)
