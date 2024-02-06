import logging
import pathlib
from .bot import MusicBot
from .constructs import BetterLogRecord

__all__ = ["MusicBot"]

logging.setLogRecordFactory(BetterLogRecord)


def _add_logger_level(levelname, level, *, func_name=None):
    """

    :type levelname: str
        The reference name of the level, e.g. DEBUG, WARNING, etc
    :type level: int
        Numeric logging level
    :type func_name: str
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

    exec(
        _func_prototype.format(logger_func_name=func_name, levelname=levelname),
        logging.__dict__,
        locals(),
    )
    setattr(logging.Logger, func_name, eval(func_name))


_add_logger_level("EVERYTHING", 1)
_add_logger_level("NOISY", 4, func_name="noise")
_add_logger_level("FFMPEG", 5)
_add_logger_level("VOICEDEBUG", 6)

log = logging.getLogger(__name__)
log.setLevel(logging.EVERYTHING)

log_file = pathlib.Path("logs/musicbot.log")
if not log_file.parent.is_dir():
    log_file.parent.mkdir(parents=True, exist_ok=True)

fhandler = logging.FileHandler(filename=log_file, encoding="utf-8", mode="w")
fhandler.setFormatter(
    logging.Formatter(
        "[{relativeCreated:.16f}] {asctime} - {levelname} - {name} | "
        "In {filename}::{threadName}({thread}), line {lineno} in {funcName}: {message}",
        style="{",
    )
)
log.addHandler(fhandler)

del _add_logger_level
del fhandler
